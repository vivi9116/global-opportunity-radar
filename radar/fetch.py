"""Bounded, cached, no-browser HTTP with factual per-host backoff."""
import datetime as dt
import ipaddress
import re
import socket
import time
import urllib.error
import urllib.parse
import urllib.request

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
        if until>time.time():raise FetchFailure('paused','同一来源处于暂停期；本条入口本轮未发送请求。恢复UTC：'+dt.datetime.fromtimestamp(until,dt.timezone.utc).isoformat())
        old=self.state.setdefault('sources',{}).get(source_id,{})
        headers={'User-Agent':'OpportunityRadar/9.3 (+public-source research; bounded requests)','Accept':'application/json,application/atom+xml,application/rss+xml,application/xml,text/html;q=0.8'}
        if old.get('etag') and old.get('last_success_at'):headers['If-None-Match']=old['etag']
        if old.get('last_modified') and old.get('last_success_at'):headers['If-Modified-Since']=old['last_modified']
        try:
            with self.opener.open(urllib.request.Request(url,headers=headers),timeout=self.timeout) as response:
                content=response.read(self.max_bytes+1)
                if len(content)>self.max_bytes:raise FetchFailure('response_too_large','响应超过本轮读取上限，未将截断内容当作完整正文。')
                raw=content.decode(response.headers.get_content_charset() or 'utf-8',errors='replace')
                if re.search(r'<title>\s*(?:just a moment|attention required|请稍候|請稍候)|cf-chl-|verify you are human',raw[:30000],re.I):
                    self.state['host_backoff'][host]=time.time()+3600
                    raise FetchFailure('challenge','响应中检测到人机验证标识，已暂停该来源，不打开浏览器或反复验证。',response.status)
                self.state['sources'][source_id]={**old,'etag':response.headers.get('ETag'),'last_modified':response.headers.get('Last-Modified')}
                return raw,{'http_status':response.status,'final_url':response.url,'bytes':len(content)}
        except urllib.error.HTTPError as exc:
            if exc.code==304:return None,{'http_status':304,'bytes':0,'final_url':url}
            if exc.code in {403,429}:
                try:delay=max(1800,min(86400,int(exc.headers.get('Retry-After','1800'))))
                except (TypeError,ValueError):delay=1800
                self.state['host_backoff'][host]=time.time()+delay
            status={401:'needs_credentials',403:'http_forbidden',404:'not_found',429:'rate_limited'}.get(exc.code,'http_error')
            reason={401:'接口要求身份凭据，当前请求没有可用授权。',403:'源站返回403；除非响应明确说明，不能断言是封IP、地区或账号问题。',404:'入口返回404，不能当作正常采集；需要修正或移除该入口。',429:'源站明确返回429限流，已暂停同一来源。'}.get(exc.code,'源站返回HTTP错误。')
            raise FetchFailure(status,reason,exc.code) from None
        except urllib.error.URLError as exc:
            reason=str(exc.reason)
            raise FetchFailure('tls_error' if 'SSL' in reason or 'CERTIFICATE' in reason else 'network_error',reason[:250]) from None
        except (TimeoutError,socket.timeout):raise FetchFailure('timeout','请求超时；不能据此认定网站关闭。') from None
