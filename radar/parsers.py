import datetime as dt
from email.utils import parsedate_to_datetime
import json
import xml.etree.ElementTree as ET
from .analysis import clean

def timestamp(value):
    if value is None:return None
    try:
        if isinstance(value,(float,int)):return dt.datetime.fromtimestamp(value,dt.timezone.utc).isoformat(timespec='seconds')
        result=dt.datetime.fromisoformat(str(value).replace('Z','+00:00'))
    except ValueError:
        try:result=parsedate_to_datetime(value)
        except (ValueError,TypeError):return None
    if result.tzinfo is None:result=result.replace(tzinfo=dt.timezone.utc)
    return result.isoformat(timespec='seconds')

def parse(raw,source):
    format=source['format'];items=[]
    if format=='rss':
        root=ET.fromstring(raw);ns={'a':'http://www.w3.org/2005/Atom'}
        if root.tag.split('}')[-1] not in {'rss','feed','RDF'}:raise ValueError('响应不是RSS/Atom，未把HTML页面当作成功数据。')
        for node in root.findall('a:entry',ns) or root.findall('.//item'):
            def field(key):
                value=node.find('a:'+key,ns)
                if value is None:value=node.find(key)
                return ''.join(value.itertext()) if value is not None else ''
            link=next((x.get('href','') for x in node.findall('a:link',ns) if x.get('rel','alternate')=='alternate'),'') or field('link')
            encoded=node.find('{http://purl.org/rss/1.0/modules/content/}encoded')
            items.append({'title':clean(field('title')),'body':field('content') or field('summary') or field('description') or (encoded.text if encoded is not None else ''),'url':link,'published_at':timestamp(field('published') or field('updated') or field('pubDate'))})
    elif format=='hn':
        for hit in json.loads(raw).get('hits',[]):
            items.append({'title':hit.get('title') or hit.get('story_title') or '', 'body':hit.get('story_text') or hit.get('comment_text') or '', 'url':'https://news.ycombinator.com/item?id='+str(hit.get('objectID')),'external_url':hit.get('url') or '', 'published_at':timestamp(hit.get('created_at')),'reply_count':hit.get('num_comments')})
    elif format=='github_issues':
        data=json.loads(raw)
        if not isinstance(data.get('items'),list):raise ValueError('GitHub响应缺少items列表。')
        for hit in data['items']:
            if hit.get('pull_request'):continue
            items.append({'title':hit.get('title',''),'body':hit.get('body') or '', 'url':hit.get('html_url',''),'published_at':timestamp(hit.get('created_at')),'reply_count':hit.get('comments')})
    elif format=='freelancer':
        data=json.loads(raw)
        if data.get('status')!='success' or not isinstance(data.get('result',{}).get('projects'),list):raise ValueError('Freelancer响应不是有效项目列表。')
        for hit in data['result']['projects']:
            slug=hit.get('seo_url');url='https://www.freelancer.com/projects/'+slug if slug else ''
            items.append({'title':hit.get('title',''),'body':hit.get('description') or hit.get('preview_description') or '', 'url':url,'published_at':timestamp(hit.get('time_submitted')),'reply_count':hit.get('bid_stats',{}).get('bid_count')})
    elif format=='cnode':
        data=json.loads(raw)
        if not data.get('success') or not isinstance(data.get('data'),list):raise ValueError('CNode响应不是有效主题列表。')
        for hit in data['data']:items.append({'title':hit.get('title',''),'body':hit.get('content') or '', 'url':'https://cnodejs.org/topic/'+hit['id'],'published_at':timestamp(hit.get('create_at')),'reply_count':hit.get('reply_count')})
    elif format=='v2ex':
        data=json.loads(raw)
        if not isinstance(data,list):raise ValueError('V2EX响应不是主题列表。')
        for hit in data:items.append({'title':hit.get('title',''),'body':hit.get('content') or hit.get('content_rendered') or '', 'url':hit.get('url',''),'published_at':timestamp(hit.get('created')),'reply_count':hit.get('replies')})
    elif format in {'remoteok','remotive','arbeitnow'}:
        data=json.loads(raw)
        rows=data if format=='remoteok' else data.get('jobs',[]) if format=='remotive' else data.get('data',[])
        for hit in rows:
            title=hit.get('position') or hit.get('title')
            if not title:continue
            items.append({'title':title,'body':hit.get('description',''),'url':hit.get('url',''),'published_at':timestamp(hit.get('epoch') or hit.get('created_at') or hit.get('publication_date') or hit.get('date')),'location':hit.get('candidate_required_location') or hit.get('location'),'salary':hit.get('salary') or None})
    else:raise ValueError('尚未实现该来源的解析器。')
    return [x for x in items if x.get('title') and x.get('url','').startswith(('http://','https://'))][:40]
