"""Cached translation of public excerpts. Original evidence is never overwritten."""
import hashlib
import json
import re
import time
from urllib.parse import urlencode
from .fetch import HTTPClient,FetchFailure

def needs_chinese(text):
    return bool(re.search(r'[A-Za-z]{4}',text)) and len(re.findall(r'[\u4e00-\u9fff]',text))<len(text)*.25

def split_translation(value,count):
    markers=list(re.finditer(r'⟦R(\d+)⟧',value))
    if [int(m[1]) for m in markers]!=list(range(count)):raise ValueError('翻译分段标识不完整，未把结果错配给项目。')
    return [value[m.end():markers[i+1].start() if i+1<count else len(value)].strip() for i,m in enumerate(markers)]

def public_text(text):
    text=re.sub(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}','[联系方式见原帖]',text)
    return re.sub(r'\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9_-]{20,})\b','[凭据已隐藏]',text)

def translate(records,cache,state,max_requests=40):
    report={'provider':'公共机器翻译入口（不是付费官方API）','requests':0,'new_fields':0,'cached_fields':0,'failures':[]}
    wanted={}
    for target in ['title','excerpt']:
      for item in sorted(records,key=lambda r:not r.get('editorial_match',False)):
        if not item.get('editorial_match'):continue
        for field,text in [(target,item.get('raw_title_en','') if target=='title' else item.get('_body') or item.get('evidence_excerpt',''))]:
            text=text[:360] if field=='excerpt' else text[:220]
            text=public_text(text)
            if not text or not needs_chinese(text):continue
            key=hashlib.sha256(text.encode()).hexdigest()
            wanted[key]=text
    missing=[(key,text) for key,text in wanted.items() if key not in cache]
    client=HTTPClient(state,timeout=25,max_bytes=1500000)
    started=time.monotonic()
    while missing and report['requests']<max_requests and time.monotonic()-started<120:
        batch=[]
        while missing and len(batch)<10:
            candidate=batch+[missing[0]]
            query='\n'.join(f'⟦R{i}⟧\n{text}' for i,(_,text) in enumerate(candidate))
            if len(urlencode({'q':query}))>4000 and batch:break
            batch.append(missing.pop(0))
        query='\n'.join(f'⟦R{i}⟧\n{text}' for i,(_,text) in enumerate(batch))
        url='https://translate.googleapis.com/translate_a/single?'+urlencode({'client':'gtx','sl':'auto','tl':'zh-CN','dt':'t','q':query})
        try:
            report['requests']+=1;raw,meta=client.get(url,'public_translation')
            data=json.loads(raw);translated=''.join(row[0] or '' for row in data[0])
            parts=split_translation(translated,len(batch))
            for (key,text),chinese in zip(batch,parts):cache[key]={'text':chinese,'source_text':text,'provider':report['provider']};report['new_fields']+=1
        except (FetchFailure,ValueError,TypeError,KeyError,IndexError) as exc:
            report['failures'].append(str(exc)[:180])
            if isinstance(exc,FetchFailure) and exc.status in {'timeout','network_error'} and report['requests']<max_requests:
                missing=batch+missing;continue
            break
    for item in records:
        fields={}
        for field,text in [('title',item.get('raw_title_en','')[:220]),('excerpt',(item.get('_body') or item.get('evidence_excerpt',''))[:360])]:
            text=public_text(text)
            key=hashlib.sha256(text.encode()).hexdigest()
            if key in cache:fields[field]=cache[key]['text'];report['cached_fields']+=1
        if fields.get('title'):
            labels={'bounty_direct':'帮老外干杂活','nsfw_adult':'成人联盟/订阅门道','gray_arb':'流量/CPA门道','pain_saas':'靠脚本省事收钱','tools':'卖小工具','market_watch':'预测市场报价'}
            item['title_zh']='【'+('长期参考·' if item.get('archival_source') else '')+labels.get(item['track'],'搞钱线索')+'】'+fields['title']
        if fields.get('excerpt'):item['pain_point_zh']='原帖讲的是：'+fields['excerpt']
        if fields:item['translation_note']='机器翻译＋中文操作拆解；英文原题和金额证据保留原样，点击来源核对。'
    report['pending_fields']=sum(key not in cache for key in wanted)
    return report
