"""Refresh stored body evidence after analysis changes without sending requests."""
from pathlib import Path
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from radar.analysis import analyze
from radar.engine import Engine,public_record,load,save

def main():
    engine=Engine();sources={s['id']:s for s in engine.sources}
    kept=[];removed=0
    with engine.connect() as conn:
        rows=conn.execute('SELECT id,document,first_seen,last_seen FROM records ORDER BY last_seen DESC').fetchall()
        for identifier,document,first,last in rows:
            old=json.loads(document);source=sources.get(old.get('source_id'))
            # Never pretend a public cached excerpt is the original full body.
            if source is None or '_body' not in old:kept.append(old);continue
            raw={'title':old['raw_title_en'],'body':old['_body'],'url':old['source_url'],'published_at':old.get('published_at'),'reply_count':old.get('reply_count'),'location':old.get('location')}
            new=analyze(raw,source,old.get('environment','local'))
            if new is None:
                conn.execute('DELETE FROM records WHERE id=?',(identifier,));removed+=1;continue
            new['first_seen_at']=first;new['fetched_at']=old['fetched_at']
            new['analysis_refreshed_at']=__import__('radar.analysis',fromlist=['utc_now']).utc_now()
            conn.execute('UPDATE records SET document=? WHERE id=?',(json.dumps(new,ensure_ascii=False),identifier));kept.append(new)
    engine.pair(kept);public=[public_record(item) for item in kept[:800]];save(engine.data/'catalog.json',public)
    latest=engine.snapshot();latest['signals']=public;latest['live_count']=len(public)
    latest['reference_signals']=load(engine.data/'reference_projects.json',[])
    save(engine.data/'latest.json',latest);engine.export_site()
    print(json.dumps({'refreshed_records':len(public),'filtered_old_noise':removed,'network_requests':0},ensure_ascii=False))

if __name__=='__main__':main()
