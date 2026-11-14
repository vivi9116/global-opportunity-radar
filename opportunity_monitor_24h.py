#!/usr/bin/env python3
"""v9.3: factual global opportunity collection, local UI and cloud batch mode."""
import argparse
import json
import os
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parent

def main():
    parser=argparse.ArgumentParser(description='全球赚钱机会 v9.3：证据、生态和详细执行拆解')
    parser.add_argument('--serve',action='store_true')
    parser.add_argument('--once',action='store_true',help='只抓取一轮，适用于GitHub Actions')
    parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--interval',type=int,default=1200)
    parser.add_argument('--self-test',action='store_true')
    parser.add_argument('--export-public',action='store_true')
    args=parser.parse_args()
    os.chdir(ROOT)
    if args.self_test:
        suite=unittest.defaultTestLoader.discover(str(ROOT/'tests'))
        raise SystemExit(0 if unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful() else 1)
    if args.once or args.export_public:
        from radar.engine import Engine,save
        engine=Engine()
        if args.once:
            data=engine.scan()
            if os.environ.get('GITHUB_ACTIONS')=='true' and os.environ.get('GITHUB_RUN_ID') and os.environ.get('GITHUB_REPOSITORY'):
                run={'run_id':os.environ['GITHUB_RUN_ID'],'run_url':'https://github.com/'+os.environ['GITHUB_REPOSITORY']+'/actions/runs/'+os.environ['GITHUB_RUN_ID'],'status':'采集步骤完成；完整任务结论需打开GitHub运行页核对','collected_at':data['updated_at']}
                save(engine.data/'cloud_last_run.json',run)
                data['cloud']=engine.cloud_status();save(engine.data/'latest.json',data)
            engine.export_site()
            print(json.dumps({'records':data['live_count'],'coverage':data['coverage'],'cloud_run':os.environ.get('GITHUB_ACTIONS')=='true'},ensure_ascii=False))
            if data['coverage'].get('successful_platforms',0)==0:raise SystemExit(2)
        else:engine.export_site()
        return
    from radar.server import serve
    serve(args.port,max(300,args.interval))

if __name__=='__main__':main()
