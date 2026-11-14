"""Wait briefly for a successfully uploaded Pages artifact to be listed by GitHub."""
import json
import os
import time
import urllib.error
import urllib.request

def main():
    if os.environ.get('GITHUB_ACTIONS')!='true':raise SystemExit('Cloud runner only.')
    repo=os.environ['GITHUB_REPOSITORY'];run=os.environ['GITHUB_RUN_ID']
    request=urllib.request.Request(f'https://api.github.com/repos/{repo}/actions/runs/{run}/artifacts',headers={'Authorization':'Bearer '+os.environ['GITHUB_TOKEN'],'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28','User-Agent':'OpportunityRadar/pages-artifact-check'})
    deadline=time.monotonic()+45;attempt=0
    while time.monotonic()<deadline:
        attempt+=1
        try:
            with urllib.request.urlopen(request,timeout=10) as response:data=json.load(response)
            found=[item for item in data.get('artifacts',[]) if item['name']=='github-pages' and not item.get('expired') and item.get('size_in_bytes',0)>0]
            if found:
                print(json.dumps({'pages_artifact_visible':True,'artifact_id':found[0]['id'],'checks':attempt}))
                time.sleep(3)
                return
        except urllib.error.HTTPError as exc:
            if exc.code not in {429,500,502,503,504}:raise
            # Do not repeatedly hit an explicit API rate limit.
            if exc.code==429:raise SystemExit('GitHub artifact API rate-limited; deployment remains failed.')
        except (urllib.error.URLError,TimeoutError):pass
        time.sleep(3)
    raise SystemExit('Uploaded Pages artifact was not visible within 45 seconds; did not claim deployment success.')

if __name__=='__main__':main()
