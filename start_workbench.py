"""Hidden local starter. Does not open a browser or interact with desktop apps."""
from pathlib import Path
import json
import os
import subprocess
import sys
import time
import urllib.request

ROOT=Path(__file__).resolve().parent
def health():
    try:
        with urllib.request.urlopen('http://127.0.0.1:8765/api/health',timeout=1) as r:return json.load(r)
    except (OSError,ValueError):return None
def main():
    value=health()
    if value and value.get('version')!='9.3-evidence':raise SystemExit('8765由其他服务占用；请核对旧服务。')
    if not value:
        python=ROOT.parent/'.venv/Scripts/python.exe'
        if not python.exists():python=Path(sys.executable)
        (ROOT/'private').mkdir(exist_ok=True)
        with (ROOT/'private/monitor.stdout.log').open('a',encoding='utf-8') as out,(ROOT/'private/monitor.stderr.log').open('a',encoding='utf-8') as err:
            process=subprocess.Popen([str(python),str(ROOT/'opportunity_monitor_24h.py'),'--serve'],cwd=ROOT,env={**os.environ,'PYTHONIOENCODING':'utf-8'},stdout=out,stderr=err,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0)|getattr(subprocess,'BELOW_NORMAL_PRIORITY_CLASS',0))
        for _ in range(30):
            if health():break
            if process.poll() is not None:raise SystemExit('启动失败，查看private/monitor.stderr.log。')
            time.sleep(.2)
        else:raise SystemExit('服务未就绪。')
    (ROOT/'private/launcher.status.log').write_text('v9.3已静默运行；需要查看时手动访问 http://127.0.0.1:8765/\n',encoding='utf-8')
if __name__=='__main__':main()
