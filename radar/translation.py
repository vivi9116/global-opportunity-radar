"""Cached translation of public excerpts. Original evidence is never overwritten."""
import hashlib
import json
import re
import time
import os
from collections import Counter
from pathlib import Path
from urllib.parse import urlencode
from .fetch import HTTPClient,FetchFailure

def needs_chinese(text):
    return bool(re.search(r'[A-Za-z]{4}',text)) and len(re.findall(r'[\u4e00-\u9fff]',text))<len(text)*.25

def split_translation(value,count):
    markers=list(re.finditer(r'⟦R(\d+)⟧',value))
    if [int(m[1]) for m in markers]!=list(range(count)):raise ValueError('翻译分段标识不完整，未把结果错配给项目。')
    return [value[m.end():markers[i+1].start() if i+1<count else len(value)].strip() for i,m in enumerate(markers)]

def offline_english(missing,cache):
    root=Path(os.environ.get('RADAR_OFFLINE_MODEL_DIR',''))
    if not all((root/name).is_file() for name in ['model/model.bin','source.spm','target.spm']):return missing,0,'离线模型还未就绪'
    import ctranslate2
    import sentencepiece as spm
    import langid
    selected=[];pending=[]
    for key,text in missing:
        language,_=langid.classify(text)
        if language=='en':selected.append((key,text))
        else:pending.append((key,text))
    if not selected:return pending,0,None
    source=spm.SentencePieceProcessor(model_file=str(root/'source.spm'));target=spm.SentencePieceProcessor(model_file=str(root/'target.spm'))
    translator=ctranslate2.Translator(str(root/'model'),device='cpu',compute_type='int8',intra_threads=2,inter_threads=1)
    for offset in range(0,len(selected),24):
        batch=selected[offset:offset+24]
        tokens=[['>>cmn_Hans<<']+source.encode(text,out_type=str) for _,text in batch]
        results=translator.translate_batch(tokens,beam_size=2,max_batch_size=24,max_input_length=256,max_decoding_length=256)
        for (key,text),result in zip(batch,results):
            chinese=target.decode(result.hypotheses[0]);chinese=re.sub(r'>>[^<]+<<','',chinese).strip()
            if not chinese or not numbers_preserved(text,chinese):pending.append((key,text));continue
            cache[key]={'text':chinese,'source_text':text,'provider':'GitHub运行器离线OPUS模型（英→简体中文）'}
    return pending,sum(key in cache for key,_ in selected),None

def public_text(text):
    text=re.sub(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}','[联系方式见原帖]',text)
    return re.sub(r'\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9_-]{20,})\b','[凭据已隐藏]',text)

def numbers_preserved(source,target):
    def values(text):return Counter(re.sub(r'[^0-9]','',part) for part in re.findall(r'\d[\d.,]*',text))
    required=values(source);actual=values(target)
    return all(actual[key]>=count for key,count in required.items())

def translate(records,cache,state,max_requests=40):
    report={'provider':'公共机器翻译入口（不是付费官方API）','requests':0,'new_fields':0,'offline_fields':0,'cached_fields':0,'failures':[]}
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
    if os.environ.get('RADAR_OFFLINE_MODEL_DIR') and missing:
        try:
            missing,count,error=offline_english(missing,cache)
            report['offline_fields']=count;report['new_fields']+=count;report['provider']='云端离线英→中＋缓存；其它语言保留待补或公共翻译'
            if error:report['failures'].append(error)
        except (ImportError,OSError,ValueError,RuntimeError) as exc:report['failures'].append('离线翻译未完成：'+type(exc).__name__)
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
            for (key,text),chinese in zip(batch,parts):
                if not chinese or not numbers_preserved(text,chinese):continue
                cache[key]={'text':chinese,'source_text':text,'provider':report['provider']};report['new_fields']+=1
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
