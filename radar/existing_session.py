"""Read only an already-open BHW page through its existing debug connection.
Never launches Chrome/ChromeDriver, creates tabs, navigates the UI, reads cookies,
or solves verification. The optional local supplement stops when the PC is off.
"""
import json
import time
import urllib.request
from urllib.parse import urljoin,urlsplit
from .fetch import challenge_title
from .html_sources import Document
from .analysis import analyze,financial_evidence,utc_now
from .parsers import timestamp
from .engine import public_record

class SessionUnavailable(Exception):pass

def public_text(node):
    if node.tag in {'blockquote','script','style'} or 'bbCodeBlock--quote' in node.attrs.get('class',''):return ''
    return ' '.join(public_text(child) if hasattr(child,'tag') else child for child in node.children)

class ExistingSession:
    def __init__(self,port=9222):
        if not isinstance(port,int) or not 1<=port<=65535:raise ValueError('Invalid local debug port')
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            with opener.open(f'http://127.0.0.1:{port}/json/list',timeout=2) as response:tabs=json.load(response)
        except Exception:raise SessionUnavailable('原9222调试会话未运行；没有启动浏览器。') from None
        target=next((tab for tab in tabs if tab.get('type')=='page' and urlsplit(tab.get('url','')).hostname in {'www.blackhatworld.com','blackhatworld.com'}),None)
        if not target:raise SessionUnavailable('现有会话没有BHW标签页；没有新建或切换标签页。')
        ws_url=target.get('webSocketDebuggerUrl','')
        if urlsplit(ws_url).hostname not in {'127.0.0.1','localhost'}:raise SessionUnavailable('调试连接不是本机地址。')
        try:
            import websocket
            self.ws=websocket.create_connection(ws_url,timeout=22,suppress_origin=True)
        except ImportError:raise SessionUnavailable('可选补采组件websocket-client未安装，核心云端抓取不受影响。') from None
        except Exception:raise SessionUnavailable('本机调试端口拒绝后台连接；没有修改浏览器安全设置。') from None
        self.request_id=0
    def close(self):self.ws.close()
    def get(self,url):
        if urlsplit(url).scheme!='https' or urlsplit(url).hostname!='www.blackhatworld.com':raise ValueError('Only public BHW URLs are allowed')
        self.request_id+=1;identifier=self.request_id
        expression='(async()=>{const r=await fetch('+json.dumps(url)+',{credentials:"include",redirect:"follow",signal:AbortSignal.timeout(18000)});return {status:r.status,url:r.url,body:(await r.text()).slice(0,1800000)};})()'
        self.ws.send(json.dumps({'id':identifier,'method':'Runtime.evaluate','params':{'expression':expression,'awaitPromise':True,'returnByValue':True}}))
        deadline=time.monotonic()+24
        while time.monotonic()<deadline:
            message=json.loads(self.ws.recv())
            if message.get('id')!=identifier:continue
            if message.get('error') or message.get('result',{}).get('exceptionDetails'):raise SessionUnavailable('现有会话后台请求未成功；没有操作页面或尝试验证。')
            value=message['result']['result'].get('value',{})
            title=challenge_title(value.get('body',''))
            if title:raise SessionUnavailable('现有会话仍返回验证页（'+title+'）；需要你在原窗口正常验证。')
            if value.get('status')!=200:raise SessionUnavailable('现有会话请求返回HTTP'+str(value.get('status'))+'，未当作成功。')
            if urlsplit(value.get('url','')).hostname!='www.blackhatworld.com':raise SessionUnavailable('响应离开BHW，未继续处理。')
            return value['body']
        raise SessionUnavailable('现有会话读取超时。')

def forum_threads(raw):
    result=[];doc=Document(raw)
    for node in doc.root.walk():
        if not node.has_class('structItem--thread') or 'is-sticky' in node.attrs.get('class',''):continue
        heading=node.first(lambda n:n.has_class('structItem-title'))
        link=heading.first(lambda n:n.tag=='a' and '/seo/' in n.attrs.get('href','')) if heading else None
        if not link:continue
        url=urljoin('https://www.blackhatworld.com',link.attrs['href']).split('?')[0].rstrip('/')+'/latest'
        author=node.attrs.get('data-author')
        if not author:
            user=node.first(lambda n:n.has_class('username'))
            author=user.text() if user else None
        if urlsplit(url).hostname=='www.blackhatworld.com' and author:result.append({'title':heading.text(),'url':url,'thread_author':author})
    return result[:3]

def latest_posts(raw,thread):
    if not thread.get('thread_author'):return []
    rows=[];doc=Document(raw)
    for node in doc.root.walk():
        if node.tag!='article' or not node.has_class('message--post'):continue
        body=node.first(lambda n:n.has_class('bbWrapper'));date=node.first(lambda n:n.tag=='time' and n.attrs.get('datetime'))
        author=node.attrs.get('data-author');post_id=node.attrs.get('data-content','')
        if not body or not post_id.startswith('post-'):continue
        if thread.get('thread_author') and author!=thread['thread_author']:continue
        text=public_text(body)
        if not financial_evidence(thread['title'],text,'business_discussion'):continue
        rows.append({'title':thread['title']+'｜作者最近的金额更新','body':text,'url':thread['url'].removesuffix('/latest')+'/'+post_id,'published_at':timestamp(date.attrs['datetime']) if date else None,'body_scope':'本机已有登录会话读取的作者楼层；引文已去掉，收入仍是作者自述','post_author':author})
    return list(reversed(rows))[:6]

def collect(port=9222):
    session=ExistingSession(port)
    try:
        threads=forum_threads(session.get('https://www.blackhatworld.com/forums/my-journey-discussions.167/'))
        if not threads:raise SessionUnavailable('公开论坛页未识别出主题，未把空列表当作接通。')
        records=[]
        for thread in threads:
            for raw in latest_posts(session.get(thread['url']),thread):
                item=analyze(raw,{'id':'bhw_existing_session','platform':'blackhatworld','name':'BHW 本机已登录会话补采','format':'existing_session','preferred_theme':True},'local-authorized-session')
                if item:
                    item['post_author']=raw.get('post_author');item['audit']+='；电脑关机后此补采来源暂停，不能当云端直连。';records.append(public_record(item))
        return {'environment':'local-authorized-session','captured_at':utc_now(),'scope':'BHW公开Journey作者金额楼层；仅利用已运行的登录会话，未启动/切换浏览器','records':records,'threads_checked':len(threads)}
    finally:session.close()
