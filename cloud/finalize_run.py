"""Record collector outcome without pretending to know the job's final conclusion."""
import json
import os
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from radar.engine import Engine,save,load
from radar.analysis import utc_now

def main():
    if os.environ.get('GITHUB_ACTIONS')!='true' or not os.environ.get('GITHUB_RUN_ID'):
        raise SystemExit('Only a real GitHub Actions run can create a cloud run record.')
    engine=Engine()
    record={'run_id':os.environ['GITHUB_RUN_ID'],
        'run_url':f'https://github.com/{os.environ["GITHUB_REPOSITORY"]}/actions/runs/{os.environ["GITHUB_RUN_ID"]}',
        'collector_outcome':os.environ.get('SCAN_OUTCOME','unknown'),
        'recorded_at':utc_now(),'status':'这是采集步骤结果；推送和整个任务是否成功，仍以GitHub运行页最终结论为准。'}
    save(engine.data/'cloud_last_run.json',record)
    data=engine.snapshot();data['cloud']=engine.cloud_status();save(engine.data/'latest.json',data)
    engine.export_site()
    summary=os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        health=load(engine.data/'source_health.json',{})
        with open(summary,'a',encoding='utf-8') as out:
            out.write('## Actual collection results\n\n')
            out.write(f'Collector: {record["collector_outcome"]}; platforms responding: {health.get("successful_platforms",0)}; stored records: {data.get("live_count",0)}\n\n')
            out.write('| Source | Status | HTTP | Kept | Reason |\n|---|---|---|---|---|\n')
            for source in health.get('sources',[]):
                cells=[source['name'],source['status'],str(source.get('http_status') or 'not obtained'),str(source.get('kept_count',0)),source.get('message','')]
                out.write('| '+' | '.join(x.replace('|','/').replace('\n',' ') for x in cells)+' |\n')

if __name__=='__main__':main()
