"""An allowlist keeps private evidence, original uploads and credentials off GitHub."""
import hashlib
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[1]
FILES=['.gitignore','README.md','opportunity_monitor_24h.py','start_workbench.py','start_hidden.vbs','start_local_workbench.bat','app.js','styles.css','global_arb_radar_workbench.html','sources.json']
TREES=['radar','tests','cloud','.github','docs']
PUBLIC_DATA=['reference_projects.json']

def build(destination=None):
    destination=Path(destination or ROOT/'private/publish_bundle')
    destination.mkdir(parents=True,exist_ok=True)
    copied=[]
    def copy(file):
        relative=file.relative_to(ROOT)
        target=destination/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(file,target)
        copied.append({'path':relative.as_posix(),'bytes':file.stat().st_size,'sha256':hashlib.sha256(file.read_bytes()).hexdigest()})
    for name in FILES:
        if (ROOT/name).is_file():copy(ROOT/name)
    for name in TREES:
        for file in (ROOT/name).rglob('*'):
            if file.is_file() and '__pycache__' not in file.parts and file.suffix not in {'.pyc','.zip','.log'}:copy(file)
    for name in PUBLIC_DATA:
        if (ROOT/'data'/name).is_file():copy(ROOT/'data'/name)
    # Start cloud without local cached source status/backoff or locally collected bodies.
    (destination/'data').mkdir(exist_ok=True)
    (destination/'data/source_state.json').write_text('{"sources":{},"host_backoff":{}}\n',encoding='utf-8')
    manifest={'note':'首次上传仅包含程序与标明待核验的参考资料；真实公开结果由云端首次运行生成。','files':copied}
    (ROOT/'private').mkdir(exist_ok=True)
    (ROOT/'private/publish_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    return destination,manifest

if __name__=='__main__':
    destination,manifest=build();print(json.dumps({'directory':str(destination),'files':len(manifest['files'])},ensure_ascii=False))
