"""Bounded, cached, no-browser HTTP with factual per-host backoff."""
import datetime as dt
import ipaddress
import re
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from email.utils import parsedate_to_datetime

def challenge_title(raw):
    match=re.search(r'<title[^>]*>\s*(.*?)\s*</title>',raw[:40000],re.I|re.S)
    title=re.sub(r'\s+',' ',match.group(1)) if match else ''
    if re.search(r'just a moment|attention required|bot verification|verify.*human|验证|请稍候|請稍候',title,re.I) or re.search(r'cf-chl-|lsrecaptcha-form|<altcha-widget',raw[:40000],re.I):return title or '验证组件标识'
    return None

def retry_delay(value,minimum=1800):
    try:delay=float(value)
    except (ValueError,TypeError):
        try:delay=parsedate_to_datetime(value).timestamp()-time.time()
        except (ValueError,TypeError,AttributeError):delay=minimum
    return max(minimum,min(86400,delay))

class FetchFailure(Exception):
    def __init__(self,status,message,http_status=None):
        super().__init__(message);self.status=status;self.http_status=http_status

def safe_public_url(url):
    parsed=urllib.parse.urlsplit(url)
    if parsed.scheme not in {'https','http'} or parsed.username or not parsed.hostname:return False
    if parsed.hostname.lower() in {'localhost','localhost.localdomain'} or parsed.hostname.endswith(('.local','.internal')):return False
    try:return ipaddress.ip_address(parsed.hostname).is_global
    except ValueError:return True

class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        if not safe_public_url(newurl):raise FetchFailure('unsafe_redirect','重定向到了非公网地址，未继续请求。')
        return super().redirect_request(req,fp,code,msg,headers,newurl)

class HTTPClient:
    def __init__(self,state,timeout=10,max_bytes=5000000):
        self.state=state;self.timeout=timeout;self.max_bytes=max_bytes
        self.opener=urllib.request.build_opener(SafeRedirect())
    def get(self,url,source_id):
        if not safe_public_url(url):raise FetchFailure('invalid_url','不是允许读取的公网HTTP地址。')
        host=urllib.parse.urlsplit(url).hostname
        until=self.state.setdefault('host_backoff',{}).get(host,0)
        if until>time.time():
            reason=self.state.get('host_pause_reason',{}).get(host,'此前同一来源触发暂停规则。')
            raise FetchFailure('paused',reason+' 本轮未发送请求。恢复UTC：'+dt.datetime.fromtimestamp(until,dt.timezone.utc).isoformat())
        old=self.state.setdefault('sources',{}).get(source_id,{})
        headers={'User-Agent':'OpportunityRadar/9.3 (+public-source research; bounded requests)','Accept':'application/json,application/atom+xml,application/rss+xml,application/xml,text/html;q=0.8'}
        if old.get('etag') and old.get('last_success_at'):headers['If-None-Match']=old['etag']
        if old.get('last_modified') and old.get('last_success_at'):headers['If-Modified-Since']=old['last_modified']
        try:
            with self.opener.open(urllib.request.Request(url,headers=headers),timeout=self.timeout) as response:
                content=response.read(self.max_bytes+1)
                if len(content)>self.max_bytes:raise FetchFailure('response_too_large','响应超过本轮读取上限，未将截断内容当作完整正文。')
                raw=content.decode(response.headers.get_content_charset() or 'utf-8',errors='replace')
                title=challenge_title(raw)
                if title:
                    self.state['host_backoff'][host]=time.time()+3600
                    reason='实际响应为人机验证页（'+title+'），已暂停；需要正常站点验证或授权接口，不自动破解。'
                    self.state.setdefault('host_pause_reason',{})[host]=reason
                    raise FetchFailure('challenge',reason,response.status)
                self.state['sources'][source_id]={**old,'etag':response.headers.get('ETag'),'last_modified':response.headers.get('Last-Modified')}
                return raw,{'http_status':response.status,'final_url':response.url,'bytes':len(content)}
        except urllib.error.HTTPError as exc:
            if exc.code==304:return None,{'http_status':304,'bytes':0,'final_url':url}
            title=challenge_title(exc.read(40000).decode('utf-8','replace')) if exc.code in {401,403} else None
            if title:
                reason='HTTP'+str(exc.code)+'，实际响应为人机验证页（'+title+'）；需站点正常验证或授权接口。'
                self.state['host_backoff'][host]=time.time()+3600;self.state.setdefault('host_pause_reason',{})[host]=reason
                raise FetchFailure('challenge',reason,exc.code) from None
            if exc.code in {403,429}:
                delay=retry_delay(exc.headers.get('Retry-After'))
                self.state['host_backoff'][host]=time.time()+delay
            status={401:'needs_credentials',403:'http_forbidden',404:'not_found',429:'rate_limited'}.get(exc.code,'http_error')
            reason={401:'接口要求身份凭据，当前请求没有可用授权。',403:'源站返回403；除非响应明确说明，不能断言是封IP、地区或账号问题。',404:'入口返回404，不能当作正常采集；需要修正或移除该入口。',429:'源站明确返回429限流，已暂停同一来源。'}.get(exc.code,'源站返回HTTP错误。')
            if exc.code in {403,429}:self.state.setdefault('host_pause_reason',{})[host]=reason
            raise FetchFailure(status,reason,exc.code) from None
        except urllib.error.URLError as exc:
            reason=str(exc.reason)
            raise FetchFailure('tls_error' if 'SSL' in reason or 'CERTIFICATE' in reason else 'network_error',reason[:250]) from None
        except (TimeoutError,socket.timeout):raise FetchFailure('timeout','请求超时；不能据此认定网站关闭。') from None
