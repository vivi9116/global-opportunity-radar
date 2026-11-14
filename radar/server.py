import json
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import threading
import datetime as dt
import urllib.parse
from .engine import Engine,ROOT,load

class Handler(BaseHTTPRequestHandler):
    def allowed(self):
        hosts={f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}'}
        origin=self.headers.get('Origin')
        return self.headers.get('Host') in hosts and (not origin or origin in {'http://'+host for host in hosts})
    def send(self,data,status=200,mime='application/json; charset=utf-8'):
        body=data if isinstance(data,bytes) else json.dumps(data,ensure_ascii=False).encode()
        self.send_response(status);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(body)))
        self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.end_headers()
        try:self.wfile.write(body)
        except (BrokenPipeError,ConnectionResetError):pass
    def do_GET(self):
        if not self.allowed():return self.send({'error':'仅允许本地监控台同源访问'},403)
        path=urllib.parse.urlsplit(self.path).path;engine=self.server.engine
        if path=='/api/health':return self.send({'status':'ok','version':'9.3-evidence','quiet':True,'browser_automation':False,'mode':load(engine.root/'cloud_config.json',{}).get('mode','local'),'collecting':engine.lock.locked(),'poll_interval_sec':self.server.interval})
        if path in {'/api/signals','/api/live-signals'}:return self.send(engine.snapshot())
        if path=='/api/sources':return self.send(load(engine.data/'source_health.json',{'sources':[],'note':'尚未完成首次采集，不能据配置名声称已抓取。'}))
        if path=='/api/discovery':return self.send(load(engine.data/'discovery_candidates.json',[]))
        assets={'/':('global_arb_radar_workbench.html','text/html; charset=utf-8'),'/index.html':('global_arb_radar_workbench.html','text/html; charset=utf-8'),'/global_arb_radar_workbench.html':('global_arb_radar_workbench.html','text/html; charset=utf-8'),'/app.js':('app.js','text/javascript; charset=utf-8'),'/styles.css':('styles.css','text/css; charset=utf-8')}
        assets['/assets/csv_merge_sample.py']=('assets/csv_merge_sample.py','text/plain; charset=utf-8')
        if path in assets:
            filename,mime=assets[path];return self.send((engine.root/filename).read_bytes(),mime=mime)
        if path=='/favicon.ico':return self.send(b'',204,'image/x-icon')
        return self.send({'error':'Not found'},404)
    def do_POST(self):
        if not self.allowed():return self.send({'error':'仅允许同源访问'},403)
        if urllib.parse.urlsplit(self.path).path!='/api/refresh':return self.send({'error':'Not found'},404)
        busy=self.server.engine.lock.locked()
        if not busy:self.server.wake.set()
        cloud=load(self.server.engine.root/'cloud_config.json',{}).get('mode')=='cloud'
        return self.send({'accepted':not busy,'message':'已有采集进行中' if busy else '已安排同步云端快照；不会从本机访问各来源' if cloud else '已安排扫描；缓存与来源暂停规则仍然有效'},202)
    def log_message(self,fmt,*args):pass

def serve(port=8765,interval=1200):
    engine=Engine();wake=threading.Event();stop=threading.Event()
    interval=300 if load(engine.root/'cloud_config.json',{}).get('mode')=='cloud' else max(300,interval)
    def worker():
        latest=engine.snapshot().get('updated_at')
        if latest:
            try:
                elapsed=(dt.datetime.now(dt.timezone.utc)-dt.datetime.fromisoformat(latest)).total_seconds()
                wake.wait(max(0,max(300,interval)-elapsed))
            except (TypeError,ValueError):pass
        while not stop.is_set():
            wake.clear()
            try:
                if load(engine.root/'cloud_config.json',{}).get('mode')=='cloud':
                    engine.sync_cloud()
                    if load(engine.root/'cloud_config.json',{}).get('existing_bhw_supplement'):
                        from .session_bridge import run as supplement
                        supplement(engine.root)
                else:engine.scan()
            except Exception as exc:print('采集失败：'+type(exc).__name__+': '+str(exc),flush=True)
            wake.wait(max(300,interval))
    server=ThreadingHTTPServer(('127.0.0.1',port),Handler);server.daemon_threads=True
    server.engine=engine;server.interval=max(300,interval);server.wake=wake
    (ROOT/'private/monitor.pid').write_text(str(__import__('os').getpid()),encoding='ascii')
    threading.Thread(target=worker,name='quiet-source-worker',daemon=True).start()
    print(f'v9.3后台已启动：http://127.0.0.1:{port}/；不自动打开或操作浏览器。',flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:stop.set();wake.set();server.server_close()
