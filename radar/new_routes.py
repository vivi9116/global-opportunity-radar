"""Rotate global long-tail searches. Search snippets are candidates, never payment proof."""
from urllib.parse import quote,urlsplit,urlunsplit
import xml.etree.ElementTree as ET
from .fetch import HTTPClient,FetchFailure,safe_public_url
from .analysis import clean,utc_now

QUERIES=[
 '"first payout" "affiliate"','"paid" "telegram bot" "client"',
 '"paid plugin" "first sale"','"domain parking" "revenue"',
 '"creator rewards" "payout"','"CSV" "paid me"',
 '"localization" "commission" "indie game"','"content locking" "case study"',
 '"adult affiliate" "case study"','"lifetime deal" "first customers"',
 '"mod creator" "revenue share"','"niche directory" "sponsor"',
 '"gané" "vendiendo" "plantillas"','"ganhei" "plugin" "cliente"',
 '"заработал" "бот" "клиент"','"副業" "初売上" "ツール"',
 '"premier client" "automatisation"','"microtask" "payment proof"',
 '"public dataset" "license" "revenue"','"paid beta test" "payout"',
 '"Minecraft" "commission" "plugin"','"Discord bot" "paid client"',
 '"digital download" "first sale"','"website flipping" "sold"',
]

def discover(state,candidates):
    cursor=int(state.get('discovery_query_cursor',0));selected=[QUERIES[(cursor+i)%len(QUERIES)] for i in range(2)]
    client=HTTPClient(state,timeout=15);known={x['url'] for x in candidates};report={'queries':selected,'new_candidates':0,'errors':[],'checked_at':utc_now()}
    for query in selected:
        url='https://www.bing.com/search?format=rss&q='+quote(query)
        try:
            raw,meta=client.get(url,'global_query_'+str((cursor+selected.index(query))%len(QUERIES)))
            if not raw:continue
            root=ET.fromstring(raw)
            if root.tag!='rss':raise ValueError('搜索入口没有返回RSS。')
            for node in root.findall('.//item')[:8]:
                target=node.findtext('link') or '';parts=urlsplit(target);target=urlunsplit((parts.scheme,parts.netloc,parts.path,'',''))
                if not safe_public_url(target) or target in known:continue
                title=clean(node.findtext('title'));snippet=clean(node.findtext('description'))[:240]
                if not title:continue
                candidates.append({'url':target,'title':title,'snippet':snippet,'found_at':report['checked_at'],'found_in':url,'query':query,'status':'search_excerpt_only','reason':'搜索发现的新路子/来源；尚未读取原站全文、核验日期或收款，不计入已接通平台。'})
                known.add(target);report['new_candidates']+=1
        except (FetchFailure,ValueError,ET.ParseError) as exc:report['errors'].append(str(exc)[:200])
    state['discovery_query_cursor']=(cursor+2)%len(QUERIES)
    return candidates[-250:],report
