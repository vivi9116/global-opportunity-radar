"""Optional local supplement: public BHW posts only; never exports browser secrets."""
import base64
import datetime as dt
import json
import os
import subprocess
import urllib.request
import urllib.error
from .engine import load,save,ROOT
from .analysis import utc_now
from .existing_session import collect,SessionUnavailable

def run(root=ROOT,force=False):
    config=load(root/'cloud_config.json',{})
    if not config.get('existing_bhw_supplement'):return
    status_file=root/'private/session_status.json';old=load(status_file,{})
    if not force and old.get('checked_at'):
        try:
            if (dt.datetime.now(dt.timezone.utc)-dt.datetime.fromisoformat(old['checked_at'])).total_seconds()<1200:return
        except ValueError:pass
    status={'checked_at':utc_now(),'browser_launched':False,'tabs_created':False,'cookies_exported':False}
    try:
        payload=collect(int(config.get('chrome_port',9222)))
        save(root/'private/local_supplement_preview.json',payload)
        status.update(status='read_ok',records=len(payload['records']),threads_checked=payload['threads_checked'])
        if not payload['records']:
            status['message']='已有会话能读到页面；本轮作者最新楼层没有匹配金额，不补写收入。';save(status_file,status);return status
        env={**os.environ,'GIT_TERMINAL_PROMPT':'0','GCM_INTERACTIVE':'never'}
        process=subprocess.run(['git','credential','fill'],input='protocol=https\nhost=github.com\n\n',text=True,capture_output=True,timeout=15,env=env)
        fields=dict(line.split('=',1) for line in process.stdout.splitlines() if '=' in line)
        token=fields.get('password')
        if not token:raise SessionUnavailable('已取得补采内容，但本机Git凭据不可用，尚未上传。')
        repo=config.get('repository','')
        if not __import__('re').fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repo):raise SessionUnavailable('补采已完成，但仓库配置无效，未上传。')
        url='https://api.github.com/repos/'+repo+'/contents/data/local_supplement.json'
        headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json','User-Agent':'OpportunityRadar-LocalSupplement','Content-Type':'application/json'}
        sha=None
        try:
            with urllib.request.urlopen(urllib.request.Request(url,headers=headers),timeout=20) as response:sha=json.load(response).get('sha')
        except urllib.error.HTTPError as exc:
            if exc.code!=404:raise
        body={'message':'Update public BHW supplement from an existing local session','content':base64.b64encode(json.dumps(payload,ensure_ascii=False).encode()).decode(),'branch':'main'}
        if sha:body['sha']=sha
        with urllib.request.urlopen(urllib.request.Request(url,data=json.dumps(body).encode(),headers=headers,method='PUT'),timeout=25) as response:result=json.load(response)
        status.update(status='uploaded',message='公开楼层摘录已同步到云端；本机原文、登录状态和Cookies未上传。',commit=result.get('commit',{}).get('sha'))
    except SessionUnavailable as exc:status.update(status='needs_local_session',message=str(exc))
    except Exception as exc:status.update(status='error',message=type(exc).__name__+'；未把失败算成接通。详情需在本机核对。')
    save(status_file,status);return status
