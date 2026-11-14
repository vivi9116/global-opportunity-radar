"""Durable local/cloud scan engine; reading the UI never triggers a scan."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from collections import defaultdict
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import threading
import time
import urllib.parse
import xml.etree.ElementTree as ET
from .analysis import analyze,utc_now
from .catalog import PLATFORMS,default_sources
from .fetch import HTTPClient,FetchFailure,safe_public_url
from .parsers import parse
from .editorial import apply as editorial_apply
from .translation import translate

ROOT=Path(__file__).resolve().parent.parent
def load(path,default):
    try:return json.loads(path.read_text(encoding='utf-8'))
    except (OSError,ValueError):return default
def save(path,data):
    path.parent.mkdir(parents=True,exist_ok=True);temporary=path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8');temporary.replace(path)
def public_record(item):
    result={k:v for k,v in item.items() if not k.startswith('_')}
    # Evidence links suffice for contact; do not publish scraped email addresses.
    def redact(value):
        if isinstance(value,str):
            value=re.sub(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}','[邮箱见原帖]',value)
            return re.sub(r'\b(?:gh[pousr]_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9_-]{20,})\b','[凭据已隐藏]',value)
        if isinstance(value,list):return [redact(x) for x in value]
        if isinstance(value,dict):return {k:redact(v) for k,v in value.items()}
        return value
    return redact(result)

class Engine:
    def __init__(self,root=ROOT):
        self.root=Path(root);self.data=self.root/'data';self.private=self.root/'private'
        self.data.mkdir(exist_ok=True);self.private.mkdir(exist_ok=True)
        self.state=load(self.data/'source_state.json',{'sources':{},'host_backoff':{}})
        self.sources=load(self.root/'sources.json',None)
        if self.sources is None:self.sources=default_sources();save(self.root/'sources.json',self.sources)
        self.environment='github-actions' if os.environ.get('GITHUB_ACTIONS')=='true' else 'local'
        self.db=self.private/'radar_history.sqlite';self.lock=threading.Lock()
        with self.connect() as conn:
            conn.execute('CREATE TABLE IF NOT EXISTS records(id TEXT PRIMARY KEY, document TEXT NOT NULL, first_seen TEXT, last_seen TEXT)')
            conn.execute('CREATE TABLE IF NOT EXISTS source_runs(source_id TEXT, checked_at TEXT, status TEXT, http_status INTEGER, message TEXT, environment TEXT)')
            # A cloud runner is ephemeral. Rehydrate the last published catalog.
            for item in load(self.data/'catalog.json',[]):
                conn.execute('INSERT OR IGNORE INTO records VALUES(?,?,?,?)',(item['id'],json.dumps(item,ensure_ascii=False),item.get('first_seen_at') or item.get('fetched_at'),item.get('fetched_at')))
    @contextmanager
    def connect(self):
        conn=sqlite3.connect(self.db,timeout=15);conn.execute('PRAGMA journal_mode=WAL')
        try:
            with conn:yield conn
        finally:conn.close()
    def one(self,source):
        report={'id':source['id'],'platform':source['platform'],'name':source['name'],'url':source.get('url'),'checked_at':utc_now(),'environment':self.environment,'parsed_count':0,'kept_count':0}
        if not source.get('enabled',True):return [],{**report,'status':'outside_scope' if source.get('scope_disabled') else 'not_connected','message':source.get('reason','未启用，未发送请求。')}
        if source.get('rotation_group'):
            group=source['rotation_group'];cursor=self.state.setdefault('rotation_cursor',{}).get(group,0)
            if source['rotation_slot']!=cursor%source['rotation_total']:
                return [],{**report,'status':'scheduled_later','message':'按低频轮换计划，本轮轮到同平台另一组；此组未请求，不把它算成成功。'}
        try:
            for attempt in range(source.get('transient_attempts',1)):
                try:
                    raw,meta=HTTPClient(self.state,timeout=source.get('timeout',15),max_bytes=source.get('max_bytes',5000000)).get(source['url'],source['id']);meta['attempts']=attempt+1;break
                except FetchFailure as exc:
                    transient=exc.status in {'timeout','network_error'} or source.get('retry_tls_eof') and exc.status=='tls_error' and ('EOF' in str(exc) or 'timed out' in str(exc))
                    if not transient or attempt+1>=source.get('transient_attempts',1):raise
            report.update(meta)
            if raw is None:
                if not self.state.get('sources',{}).get(source['id'],{}).get('last_success_at'):
                    raise FetchFailure('cache_without_validated_data','收到304但本机没有成功解析该入口的记录，不能计为成功采集。',304)
                return [],{**report,'status':'not_modified','message':'源站返回304，沿用此前已抓取的记录；本轮没有新增正文。'}
            snapshot=self.private/'source_snapshots';snapshot.mkdir(exist_ok=True)
            (snapshot/(source['id']+'.txt')).write_text(raw,encoding='utf-8')
            if not raw.strip():raise FetchFailure('invalid_response','HTTP响应成功，但正文为0字节；没有可解析的RSS/JSON内容。',meta.get('http_status'))
            if source['format'] in {'rss','hn','v2ex','cnode','freelancer','github_issues','remotive','remoteok','arbeitnow'} and re.search(r'<!doctype\s+html|<html(?:\s|>)',raw[:1000],re.I):
                raise FetchFailure('invalid_response','HTTP响应成功，但返回HTML页面，而不是所需RSS/JSON；具体是登录、落地页或拦截需查该响应，不猜测封禁原因。',meta.get('http_status'))
            try:items=parse(raw,source)
            except (ValueError,ET.ParseError,TypeError,KeyError) as exc:raise FetchFailure('invalid_response','解析失败：'+str(exc)[:180],meta.get('http_status'))
            report['parsed_count']=len(items);records=[];stale=0;evergreen=0
            for item in items:
                if item.get('published_at'):
                    age=dt.datetime.now(dt.timezone.utc)-dt.datetime.fromisoformat(item['published_at'])
                    if age>dt.timedelta(days=source.get('max_age_days',60)) or age<dt.timedelta(days=-1):stale+=1;continue
                record=analyze(item,source,self.environment)
                if record:
                    if source.get('evergreen') and item.get('published_at') and age>dt.timedelta(days=60):
                        record.update(reference_only=True,provenance_kind='evergreen_source',archival_source=True,max_source_age_days=source.get('max_age_days',730));record['audit']+=' 原文较早，作为长期参考；当前Offer和结算另核。';record['title_zh']='【长期参考】'+record['title_zh'];evergreen+=1
                    records.append(record)
            report.update(status='ok' if records else 'ok_no_matches',kept_count=len(records),stale_filtered=stale,evergreen_reference_count=evergreen,message=f'响应格式有效，读取{len(items)}条，保留{len(records)}条（其中{evergreen}条较早内容标为长期参考）；不等于已成交。',body_sha256=hashlib.sha256(raw.encode()).hexdigest())
            self.state.setdefault('sources',{}).setdefault(source['id'],{})['last_success_at']=report['checked_at']
            return records,report
        except FetchFailure as exc:return [],{**report,'status':exc.status,'http_status':exc.http_status,'message':str(exc)}
        except Exception as exc:return [],{**report,'status':'internal_error','message':type(exc).__name__+': '+str(exc)[:200]}
    def scan(self):
        if not self.lock.acquire(blocking=False):return self.snapshot()
        started=utc_now()
        try:
            groups=defaultdict(list)
            for source in self.sources:groups[urllib.parse.urlsplit(source.get('url','')).hostname or source['id']].append(source)
            def group(sources):return [self.one(source) for source in sources]
            records=[];statuses=[]
            with ThreadPoolExecutor(max_workers=4) as pool:
                for rows in pool.map(group,groups.values()):
                    for found,status in rows:records.extend(found);statuses.append(status)
            supplement=load(self.data/'local_supplement.json',None)
            if supplement and supplement.get('environment')=='local-authorized-session':
                try:
                    age=(dt.datetime.now(dt.timezone.utc)-dt.datetime.fromisoformat(supplement['captured_at'])).total_seconds()
                    fresh=0<=age<=86400
                    imported=[item for item in supplement.get('records',[]) if item.get('environment')=='local-authorized-session' and urllib.parse.urlsplit(item.get('source_url','')).hostname=='www.blackhatworld.com'] if fresh else []
                    records.extend(imported)
                    statuses.append({'id':'bhw_local_supplement','platform':'blackhatworld','name':'BHW 本机已有会话补采（非云端直连）','url':'https://www.blackhatworld.com/','checked_at':supplement['captured_at'],'environment':'local-authorized-session','parsed_count':len(imported),'kept_count':len(imported),'status':'local_supplement' if fresh else 'local_supplement_stale','message':'导入本机已有登录会话读到的公开作者楼层；电脑关机后该来源不刷新。' if fresh else '本机补采快照已超过24小时，不当作本轮新采集。'})
                except (ValueError,KeyError,TypeError):pass
            for group in {s['rotation_group'] for s in self.sources if s.get('rotation_group')}:
                chosen=[s['id'] for s in self.sources if s.get('rotation_group')==group and s['rotation_slot']==self.state.get('rotation_cursor',{}).get(group,0)%s['rotation_total']]
                if any(row['id'] in chosen and row['status'] not in {'paused','scheduled_later'} for row in statuses):self.state['rotation_cursor'][group]=self.state['rotation_cursor'].get(group,0)+1
            with self.connect() as conn:
                for item in records:
                    old=conn.execute('SELECT first_seen FROM records WHERE id=?',(item['id'],)).fetchone()
                    item['first_seen_at']=old[0] if old else item['fetched_at']
                    conn.execute('INSERT OR REPLACE INTO records VALUES(?,?,?,?)',(item['id'],json.dumps(item,ensure_ascii=False),item['first_seen_at'],item['fetched_at']))
                for status in statuses:conn.execute('INSERT INTO source_runs VALUES(?,?,?,?,?,?)',(status['id'],status['checked_at'],status['status'],status.get('http_status'),status.get('message'),self.environment))
                catalog=[json.loads(row[0]) for row in conn.execute('SELECT document FROM records ORDER BY last_seen DESC LIMIT 800')]
            self.pair(catalog)
            # Re-evaluate old rows after parser/filter changes, rather than keeping stale noise.
            catalog=[item for item in catalog if item.get('platform_id')!='hackernews' or item.get('body_observed')]
            now=dt.datetime.now(dt.timezone.utc)
            def current(item):
                try:
                    seen=dt.datetime.fromisoformat(item.get('published_at') or item.get('first_seen_at') or item['fetched_at'])
                    return -1<=(now-seen).total_seconds()/86400<=item.get('max_source_age_days',60)
                except (ValueError,KeyError,TypeError):return False
            catalog=[item for item in catalog if current(item)]
            source_index={source['id']:source for source in self.sources}
            for item in catalog:editorial_apply(item,source_index.get(item.get('source_id'),{}))
            translation_cache=load(self.data/'translation_cache.json',{})
            translation_report=translate(catalog,translation_cache,self.state)
            save(self.data/'translation_cache.json',translation_cache)
            public=[public_record(item) for item in catalog]
            save(self.data/'catalog.json',public)
            configured={s['platform'] for s in self.sources if s.get('enabled',True)}
            ready={s['platform'] for s in statuses if s['status'] in {'ok','ok_no_matches','not_modified'}}
            report={'started_at':started,'completed_at':utc_now(),'environment':self.environment,'configured_platforms':len(configured),'configured_channels':sum(len(s.get('communities',[])) or 1 for s in self.sources if s.get('enabled',True)),'successful_platforms':len(ready),'platforms_with_new_matches':len({s['platform'] for s in statuses if s.get('kept_count',0)>0}),'successful_platform_names':[PLATFORMS.get(p,{'name':p})['name'] for p in sorted(ready)],'failed_or_paused_channels':sum(s['status'] not in {'ok','ok_no_matches','not_modified','not_connected','outside_scope','scheduled_later','local_supplement'} for s in statuses),'not_connected_platforms':len({s['platform'] for s in statuses if s['status']=='not_connected'}),'sources':statuses,'scope_note':'平台、社区/栏目和来源页面分别统计；Reddit分组低频轮换，每轮一个请求；未轮到不计成功，读到内容也不等于已成交。'}
            save(self.data/'source_health.json',report);save(self.data/'source_state.json',self.state)
            refs=load(self.data/'reference_projects.json',[])
            for reference in refs:editorial_apply(reference)
            history=load(self.data/'scan_history.json',[])
            history.append({'started_at':started,'completed_at':report['completed_at'],'environment':self.environment,'run_id':os.environ.get('GITHUB_RUN_ID'),'records':len(public),'preferred_records':sum(bool(i.get('editorial_match')) for i in public),'successful_platforms':len(ready)})
            save(self.data/'scan_history.json',history[-80:])
            payload={'version':'9.3','updated_at':report['completed_at'],'environment':self.environment,'live_count':len(public),'preferred_count':sum(bool(i.get('editorial_match')) for i in public),'signals':public,'reference_signals':refs,'scan_history':history[-80:],'translation':translation_report,'coverage':{k:v for k,v in report.items() if k!='sources'},'cloud':self.cloud_status()}
            save(self.data/'latest.json',payload)
            self.discover(catalog)
            from .new_routes import discover as discover_routes
            candidates,discovery_report=discover_routes(self.state,load(self.data/'discovery_candidates.json',[])) if configured else ([],{'queries':[],'new_candidates':0,'errors':[]})
            save(self.data/'discovery_candidates.json',candidates);save(self.data/'source_state.json',self.state)
            payload['new_routes']=discovery_report;save(self.data/'latest.json',payload)
            self.export_site()
            return payload
        finally:self.lock.release()
    def snapshot(self):
        value=load(self.data/'latest.json',{'version':'9.3','updated_at':None,'environment':self.environment,'live_count':0,'signals':[],'coverage':{}})
        value['reference_signals']=load(self.data/'reference_projects.json',[])
        for item in value['reference_signals']:editorial_apply(item)
        value['cloud']=self.cloud_status()
        value['collecting']=self.lock.locked();return value
    def cloud_status(self):
        config=load(self.root/'cloud_config.json',{})
        return {'configured':bool(os.environ.get('GITHUB_REPOSITORY') or config.get('repository')),'mode':'cloud' if os.environ.get('GITHUB_ACTIONS')=='true' or config.get('mode')=='cloud' else 'local','workflow_file':'.github/workflows/collect.yml','last_run_record':load(self.data/'cloud_last_run.json',None),'note':'工作流文件存在不等于云端已经部署或运行；采集步骤记录不代表整个任务已成功。'}
    def sync_cloud(self):
        config=load(self.root/'cloud_config.json',{});repo=config.get('repository','')
        if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repo):raise ValueError('云端仓库配置无效')
        incoming={};client=HTTPClient(self.state,max_bytes=15000000)
        for name in ['latest.json','source_health.json','discovery_candidates.json']:
            raw,meta=client.get('https://raw.githubusercontent.com/'+repo+'/main/data/'+name,'cloud_'+name)
            incoming[name]=json.loads(raw) if raw is not None else load(self.data/name,None)
            self.state.setdefault('sources',{}).setdefault('cloud_'+name,{})['last_success_at']=utc_now()
        data=incoming['latest.json'];run=data.get('cloud',{}).get('last_run_record',{})
        if data.get('environment')!='github-actions' or not str(run.get('run_url','')).startswith('https://github.com/'+repo+'/actions/runs/'):
            raise ValueError('云端响应没有匹配仓库的真实Actions运行标记，未覆盖当前数据')
        for name,value in incoming.items():save(self.data/name,value)
        save(self.data/'catalog.json',data['signals']);save(self.data/'reference_projects.json',data.get('reference_signals',[]))
        save(self.data/'cloud_last_run.json',run);save(self.data/'source_state.json',self.state)
        self.export_site();return data
    def pair(self,catalog):
        solvers=[s for s in catalog if s.get('financial_evidence') and s.get('kind')=='seller_report' and s.get('body_observed')]
        topics={'csv','excel','spreadsheet','scraping','scraper','automation','workflow','crm','subtitle','caption','translation','video','data','leads','invoice'}
        for item in catalog:
            if item['kind'] not in {'buyer_request','pain_point'}:continue
            tokens=set(re.findall(r'[a-z]+',(item['raw_title_en']+' '+item.get('_body','')).lower()))&topics
            matches=[]
            for solver in solvers:
                if solver['source_url']==item['source_url']:continue
                shared=tokens&(set(re.findall(r'[a-z]+',(solver['raw_title_en']+' '+solver.get('_body','')).lower()))&topics)
                if len(shared)>=2:matches.append({'id':solver['id'],'title':solver['title_zh'],'url':solver['source_url'],'shared_topics':sorted(shared),'relationship':'主题相近的收入自述，仅为候选对照，不证明同一需求已成交。'})
            item['candidate_solver_matches']=matches[:3]
            if matches:item['solver_case_zh']='发现主题相近的作者收入自述，需进一步核对用户类型、任务和交付方式；没有把它当作本需求的成交证据。'
    def discover(self,catalog):
        old=load(self.data/'discovery_candidates.json',[]);known={x['url'] for x in old}
        # Candidate discovery is deliberately not counted as successful monitoring.
        for item in catalog:
            for url in re.findall(r'https?://[^\s<>"\)]+',item.get('_body',''))[:3]:
                parsed=urllib.parse.urlsplit(url)
                url=urllib.parse.urlunsplit((parsed.scheme,parsed.netloc,parsed.path,'',''))
                if safe_public_url(url) and url not in known:old.append({'url':url,'found_in':item['source_url'],'status':'not_validated','reason':'从原帖发现；尚未验证可用入口、内容质量或访问许可，不计入已监控。'});known.add(url)
        save(self.data/'discovery_candidates.json',old[-150:])
    def export_site(self):
        site=self.root/'site';(site/'data').mkdir(parents=True,exist_ok=True)
        for original,target in [('global_arb_radar_workbench.html','index.html'),('app.js','app.js'),('styles.css','styles.css'),('assets/csv_merge_sample.py','assets/csv_merge_sample.py')]:
            file=self.root/original
            if file.exists():
                (site/target).parent.mkdir(parents=True,exist_ok=True);(site/target).write_bytes(file.read_bytes())
        for name in ['latest.json','source_health.json','reference_projects.json','discovery_candidates.json','cloud_last_run.json']:
            file=self.data/name
            if file.exists():(site/'data'/name).write_bytes(file.read_bytes())
