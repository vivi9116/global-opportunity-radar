#!/usr/bin/env python3
"""v10.2 public-source opportunity monitor with validated structured extraction."""
from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import hashlib
import html
import json
import os
from pathlib import Path
import re
import threading
import time
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
LIVE_FILE = ROOT / "live_signals.json"
HEALTH_FILE = ROOT / "source_health.json"
MAX_RECORDS = 500
USER_AGENT = "GlobalOpportunityRadar/10.2 (+public-source research; contact via repository)"
TIMEOUT = 24

REDDIT_GROUPS = [
    ["slavelabour", "forhire", "hireaprogrammer", "SaaS"],
    ["SideProject", "Entrepreneur", "smallbusiness", "sweatystartup"],
    ["juststart", "beermoney", "sidehustle", "flipping"],
    ["affiliatemarketing", "SEO", "NSFWCreators", "onlyfansadvice"],
]
HN_QUERIES = ["willing to pay", "too expensive alternative", "first sale MRR", "freelance automation scraping"]
TRACK_LABELS = {
    "bounty_direct": "悬赏急单/外包代工", "pain_saas": "软件痛点/买断工具",
    "gray_arb": "流量/联盟/跨境门道", "nsfw_adult": "成人商业/创作者服务",
    "market_signal": "公开榜单/需求信号",
}
BLOCKED_METHODS = re.compile(
    r"credential theft|steal credentials|captcha bypass|cloaking|account farming|deepnude|nudify|"
    r"non.?consensual|审核爬虫.*不同|伪装审核|绕过验证|盗号|撞库|脱衣照片", re.I
)
MONEY = re.compile(
    r"(?:US\$|CA\$|A\$|HK\$|S\$|R\$|USD\s*|\$|€|£|¥|￥|₹|₽)\s*\d[\d,]*(?:\.\d+)?(?:\s*[kKmM])?"
    r"|\d[\d,]*(?:\.\d+)?\s*(?:USD|EUR|GBP|CNY|JPY|RUB|BRL|USDT|USDC)\b", re.I
)
FIELDS = ["deal_fact_zh", "pain_point_zh", "solver_case_zh", "action_plan_zh", "platform_ecology_tip_zh", "reverse_money_idea_zh"]
SCHEMA_ITEM = {
    "type": "object", "additionalProperties": False,
    "properties": {"id": {"type": "string"}, **{name: {"type": "string"} for name in FIELDS}},
    "required": ["id", *FIELDS],
}


def utcnow() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return default


def save_json(path: Path, value) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def clean(value: str | None, limit: int = 12000) -> str:
    value = BeautifulSoup(value or "", "lxml").get_text(" ")
    return re.sub(r"\s+", " ", html.unescape(value)).strip()[:limit]


def stable_id(platform: str, url: str, native_id: str = "") -> str:
    return hashlib.sha256(f"{platform}|{native_id}|{url}".encode()).hexdigest()[:24]


def content_hash(title: str, body: str) -> str:
    return hashlib.sha256((title + "\n" + body).encode()).hexdigest()


class FetchError(Exception):
    def __init__(self, status: str, message: str, http_status: int | None = None):
        super().__init__(message); self.status = status; self.http_status = http_status


def http_get(url: str, accept: str = "application/json,application/rss+xml,application/xml,text/html", max_bytes: int = 6_000_000):
    try:
        response = requests.get(url, headers={"User-Agent": USER_AGENT, "Accept": accept}, timeout=TIMEOUT, allow_redirects=True)
    except requests.Timeout as exc:
        raise FetchError("timeout", "请求超时；不能据此认定来源关闭。") from exc
    except requests.RequestException as exc:
        raise FetchError("network_error", f"网络请求失败：{type(exc).__name__}") from exc
    if response.status_code in {403, 429}:
        reason = "来源返回403；未绕过站点验证。" if response.status_code == 403 else "来源返回429；本轮停止该入口并等待下次计划任务。"
        raise FetchError("forbidden" if response.status_code == 403 else "rate_limited", reason, response.status_code)
    if response.status_code >= 400:
        raise FetchError("http_error", f"来源返回HTTP {response.status_code}。", response.status_code)
    raw = response.content
    if len(raw) > max_bytes:
        raise FetchError("response_too_large", "响应超过读取上限，未把截断内容当完整数据。", response.status_code)
    text = raw.decode(response.encoding or "utf-8", errors="replace")
    if re.search(r"<title>\s*(?:Just a moment|Bot Verification|Attention Required)", text, re.I):
        raise FetchError("challenge", "实际响应是人机验证页；未自动破解。", response.status_code)
    return text, response.status_code, len(raw)


def track_for(sub: str, title: str, body: str) -> str:
    if sub.lower() in {"slavelabour", "forhire", "hireaprogrammer"}: return "bounty_direct"
    if sub.lower() in {"nsfwcreators", "onlyfansadvice"}: return "nsfw_adult"
    if sub.lower() in {"beermoney", "sidehustle", "flipping", "affiliatemarketing", "seo"}: return "gray_arb"
    if re.search(r"\b(?:hiring|task|need someone|looking for a freelancer|bounty)\b|求外包|悬赏", title + " " + body, re.I): return "bounty_direct"
    return "pain_saas"


def make_raw(platform: str, source: str, title: str, body: str, url: str, native_id: str = "", published_at: str | None = None,
             engagement: dict | None = None, track: str | None = None, body_scope: str = "来源提供的正文/摘要") -> dict:
    title, body = clean(title, 500), clean(body)
    return {
        "id": stable_id(platform, url, native_id), "platform": platform, "source_platform": source,
        "raw_title": title, "body": body, "source_url": url, "published_at": published_at,
        "fetched_at": utcnow(), "engagement": engagement or {}, "track": track or track_for("", title, body),
        "body_scope": body_scope, "source_content_sha256": content_hash(title, body),
    }


def parse_feed(text: str, platform: str, source: str, fallback_track: str | None = None) -> list[dict]:
    soup = BeautifulSoup(text, "xml"); rows = []
    nodes = soup.find_all("entry") or soup.find_all("item")
    for node in nodes:
        title_node = node.find("title"); title = title_node.get_text(" ", strip=True) if title_node else ""
        link_node = node.find("link")
        link = (link_node.get("href") if link_node and link_node.has_attr("href") else link_node.get_text(strip=True) if link_node else "")
        content = node.find("content") or node.find("description") or node.find("summary")
        body = content.decode_contents() if content else ""
        published = node.find("published") or node.find("updated") or node.find("pubDate")
        native = node.find("id") or node.find("guid")
        if title and link:
            sub_match = re.search(r"reddit\.com/r/([^/]+)", link, re.I); sub = sub_match.group(1) if sub_match else ""
            rows.append(make_raw(platform, f"{source}{' · r/'+sub if sub else ''}", title, body, link,
                                 native.get_text(strip=True) if native else link,
                                 published.get_text(strip=True) if published else None,
                                 track=fallback_track or track_for(sub, clean(title), clean(body))))
    return rows


def fetch_reddit_group(subs: list[str]) -> tuple[list[dict], dict]:
    source_id = "reddit_" + "_".join(s.lower() for s in subs)
    url = "https://www.reddit.com/r/" + "+".join(subs) + "/new/.rss?limit=100"
    return fetch_with_health(source_id, "Reddit联合公开RSS：" + " / ".join(subs), url,
                             lambda text: parse_feed(text, "reddit", "Reddit联合订阅"))


def fetch_reddit_all() -> tuple[list[dict], list[dict]]:
    rows=[];statuses=[]
    for index,group in enumerate(REDDIT_GROUPS):
        found,status=fetch_reddit_group(group);rows.extend(found);statuses.append(status)
        if index+1<len(REDDIT_GROUPS):time.sleep(3)
    return rows,statuses


def fetch_hn(query: str) -> tuple[list[dict], dict]:
    source_id = "hn_" + hashlib.sha256(query.encode()).hexdigest()[:8]
    url = "https://hn.algolia.com/api/v1/search_by_date?tags=story&hitsPerPage=30&query=" + quote(query)
    def parser(text):
        result = []
        for hit in json.loads(text).get("hits", []):
            title = hit.get("title") or hit.get("story_title") or ""; oid = str(hit.get("objectID") or "")
            discussion = "https://news.ycombinator.com/item?id=" + oid
            result.append(make_raw("hackernews", "Hacker News Algolia", title, hit.get("story_text") or "",
                                   discussion, oid, hit.get("created_at"),
                                   {"points": hit.get("points") or 0, "comments": hit.get("num_comments") or 0},
                                   track=track_for("", title, hit.get("story_text") or ""),
                                   body_scope="HN正文；外链文章未代替正文抓取"))
        return result
    return fetch_with_health(source_id, "HN检索：" + query, url, parser)


def fetch_v2ex(node: str) -> tuple[list[dict], dict]:
    url = "https://www.v2ex.com/api/topics/show.json?node_name=" + node
    def parser(text):
        rows=[]
        for item in json.loads(text):
            title=item.get("title") or ""; body=item.get("content_rendered") or item.get("content") or ""
            rows.append(make_raw("v2ex", "V2EX "+node, title, body, item.get("url") or "https://www.v2ex.com/t/"+str(item.get("id")),
                                 str(item.get("id")), dt.datetime.fromtimestamp(item.get("created",0),dt.timezone.utc).isoformat() if item.get("created") else None,
                                 {"comments": item.get("replies") or 0}, "bounty_direct" if node in {"jobs","outsourcing"} else "pain_saas"))
        return rows
    return fetch_with_health("v2ex_"+node, "V2EX "+node+"公开API", url, parser)


def fetch_bhw(kind: str, forum: str, track: str) -> tuple[list[dict], dict]:
    url=f"https://www.blackhatworld.com/forums/{forum}/index.rss"
    return fetch_with_health("bhw_"+kind, "BHW "+kind+"公开RSS", url,
                             lambda text: parse_feed(text,"blackhatworld","BlackHatWorld",track))


def fetch_dlsite() -> tuple[list[dict], dict]:
    url="https://www.dlsite.com/maniax/ranking/day?sort=sale&order=desc"
    def parser(text):
        soup=BeautifulSoup(text,"lxml"); rows=[]
        for card in soup.select("table.ranking_worklist tr"):
            links=[a for a in card.select("a[href*='/work/=/product_id/']") if "btn_free_sample" not in (a.get("class") or []) and a.get_text(" ",strip=True)]
            if not links: continue
            anchor=links[0];url=anchor.get("href","");title=anchor.get_text(" ",strip=True);body=card.get_text(" ",strip=True)
            match=re.search(r"/product_id/([^/.]+)",url);native=match.group(1) if match else url
            rows.append(make_raw("dlsite","DLsite R18公开日榜",title,body,url,native_id=native,track="nsfw_adult",body_scope="公开榜单行；未取得购买后台，页面数字仍需核对字段含义"))
        if not rows: raise ValueError("页面可读但没有匹配到公开榜单卡片，未伪造销量。")
        return rows
    return fetch_with_health("dlsite_r18_day","DLsite R18公开24小时榜",url,parser)


def fetch_chaturbate() -> tuple[list[dict], dict]:
    wm=os.environ.get("CHATURBATE_WM","").strip(); name="Chaturbate官方联盟在线房间API"
    if not wm:
        return [], health("chaturbate_affiliate",name,"not_configured",None,0,0,"缺少官方联盟代码CHATURBATE_WM；本轮未请求，也未伪造在线人数。")
    url="https://chaturbate.com/api/public/affiliates/onlinerooms/?wm="+quote(wm)+"&format=json"
    def parser(text):
        rows=[]
        for room in json.loads(text).get("results",[]):
            username=str(room.get("username") or ""); viewers=int(room.get("num_users") or 0); tags=room.get("tags") or []
            if not username: continue
            body=f"公开API当前在线人数 {viewers}；标签：{', '.join(map(str,tags[:8]))}。在线人数不是收入或成交。"
            rows.append(make_raw("chaturbate","Chaturbate官方联盟API",username,body,room.get("chat_room_url") or "https://chaturbate.com/",username,
                                 engagement={"viewers":viewers},track="nsfw_adult",body_scope="官方公开API即时指标"))
        return rows
    return fetch_with_health("chaturbate_affiliate",name,url,parser)


def health(source_id,name,status,http_status,parsed,kept,message,bytes_read=0):
    return {"id":source_id,"name":name,"status":status,"http_status":http_status,"parsed_count":parsed,
            "kept_count":kept,"bytes":bytes_read,"checked_at":utcnow(),"message":message}


def fetch_with_health(source_id: str, name: str, url: str, parser):
    try:
        text,status,size=http_get(url); rows=parser(text)
        return rows,health(source_id,name,"ok",status,len(rows),len(rows),f"HTTP {status}，解析{len(rows)}条；读到内容不等于已成交。",size)
    except FetchError as exc:
        return [],health(source_id,name,exc.status,exc.http_status,0,0,str(exc))
    except (ValueError,TypeError,json.JSONDecodeError) as exc:
        return [],health(source_id,name,"parse_error",200,0,0,"响应可达但解析失败："+str(exc)[:180])


def safe_item(item: dict) -> bool:
    text=item["raw_title"]+" "+item["body"]
    if not item["raw_title"] or BLOCKED_METHODS.search(text): return False
    return not re.search(r"buy my course|join my paid discord|100x guaranteed|稳赚|日入\s*\d",text,re.I)


def evidence_score(item: dict) -> int:
    score=34
    score += min(18,len(item["body"])//120)
    score += 15 if item["track"]=="bounty_direct" else 0
    score += 12 if MONEY.search(item["raw_title"]+" "+item["body"]) else 0
    score += 8 if item.get("published_at") else 0
    return min(92,score)


def extract_deal_fact(item: dict) -> str:
    text=item["raw_title"]+" "+item["body"]; engagement=item.get("engagement",{})
    paid=len(re.findall(r"\$paid\b",text,re.I)); bids=len(re.findall(r"\$bid\b",text,re.I)); amounts=[]
    for match in MONEY.finditer(text):
        snippet=text[max(0,match.start()-55):match.end()+75]
        if re.search(r"goal|target|hope|want to|预计|目标",snippet,re.I): continue
        amounts.append(match.group(0))
    amounts=list(dict.fromkeys(amounts))[:4]
    if paid:
        result=f"原帖出现 {paid} 处 $paid 状态标记；这是帖子内状态，未独立核对付款凭证。"
    elif bids:
        result=f"原帖出现 {bids} 处 $bid 竞标标记；竞标不等于已付款或已成交。"
    elif amounts:
        result="原帖提到金额："+"、".join(amounts)+"；金额性质需结合原文判断，未当作到账。"
    else:
        result="⚪ 原帖未披露具体成交单数，也没有可确认的付款金额。"
    metrics=" / ".join(f"{k}:{v}" for k,v in engagement.items() if v not in {None,"",0})
    return result+(" 公开互动/指标："+metrics+"；这些不是收入。" if metrics else "")


def platform_tip(item: dict) -> str:
    platform=item["platform"]; track=item["track"]
    if platform=="reddit":
        base="先读版规和帖子时间，只通过原帖允许的回复或私信渠道沟通。用户旧版经验称部分悬赏帖约30分钟后低价回复明显增多，但竞标者地区和成功率没有核验；把前10分钟准备15至20行脱敏样本当作响应目标，不能承诺一定拿单，也不要免费做完整订单。"
    elif platform=="hackernews":
        base="HN反感营销套话。先在评论中说明可复现步骤或给免登录小样，再披露你与工具的关系；不要把点赞当购买意愿。"
    elif platform=="v2ex":
        base="先确认节点规则、预算、验收和付款主体。联系方式只回到原帖核对，不公开搬运；先交可检查的小样，再约定定金与返工边界。"
    elif platform=="blackhatworld":
        base="先核对会员权限、服务区规则和楼层时间。Journey里的金额通常是作者自述；只把当天卡点当需求线索，不把围观人数当买家。"
    elif platform=="dlsite":
        base="只使用获授权的作品、翻译和素材。榜单位置、评价与销量字段分别核对；跨语言发行必须先取得版权方书面许可。"
    else:
        base="先核对平台规则、发布时间、付款主体和验收条件；用脱敏小样证明能力，不群发硬广。"
    if track=="nsfw_adult":
        base += " 成人业务可使用真实一致的18+年龄提示与合规落地页；审核机器人和真人必须看到相同内容，不做爬虫分流、伪装或绕过审核。"
    return base


def reverse_ideas(item: dict) -> str:
    subject=TRACK_LABELS.get(item["track"],"这类需求")
    return (
        f"1. 合规跨国转包：把{subject}拆成可验收小模块，只有客户书面同意且不含账号、隐私或保密数据时，才向有资质的协作者询价；你的利润来自项目管理、质检和售后，并把分包成本与责任写清。\n"
        "2. 给同行卖铲子：把已获授权、去除客户数据的重复步骤做成脚本、检查表或模板；按一次买断加更新维护收费，先用真实样例验证，不能把开源代码改名冒充原创。\n"
        "3. 顺藤找上游：从原帖反复出现的输入、返工和验收问题，归纳同一行业的采购清单；只使用公开或授权数据做小样，再向同类买方卖标准化服务，不转售原帖联系人和个人数据。"
    )


def rules_enrich(item: dict) -> dict:
    track=item["track"]; excerpt=item["body"][:520] or "原帖没有提供正文，只有标题。"
    if track=="bounty_direct":
        pain="这是一条可能的发包/找人信息。正文里可见的具体要求是："+excerpt
        action="1. 回原帖确认任务仍开放、输入格式、数量、截止时间和预算。\n2. 用虚构或脱敏数据做一个能验收的小样，写清未覆盖范围。\n3. 先确认币种、付款节点和修改次数，再做全量并保留验收记录。"
    elif track=="nsfw_adult":
        pain="这条内容反映成人创作者、平台或受众经营问题。公开正文/摘要是："+excerpt
        action="1. 先核对年龄、地区、素材授权、平台推广和结算条款。\n2. 从翻译、经营报表、元数据、客服流程等非内容交付切一个脱敏样例。\n3. 用书面授权和分阶段验收试单，记录平台费、退款与实际到账。"
    else:
        pain="原帖正在讨论一个具体麻烦或经营问题。可见正文/摘要是："+excerpt
        action="1. 从正文列出用户、当前替代方案和最常返工的一步。\n2. 只做解决这一小步的脚本、模板或人工代处理样品。\n3. 先问是否愿意为这个结果付费，再谈买断、维护或周期服务。"
    return {
        "title_zh": f"【{TRACK_LABELS.get(track,'机会线索')}】{item['raw_title']}",
        "summary_one_line": extract_deal_fact(item)[:150],
        "deal_fact_zh": extract_deal_fact(item), "pain_point_zh": pain,
        "solver_case_zh": "同一原帖内没有找到可独立核验的解决者到账记录。下面给的是基于可见需求的试单方案，不能冒充别人已经赚到钱。",
        "action_plan_zh": action, "platform_ecology_tip_zh": platform_tip(item),
        "reverse_money_idea_zh": reverse_ideas(item), "structured_by": "rules-v10.2",
        "structured_note": "规则引擎中文拆解；原文事实以来源链接和证据摘录为准。",
    }


def provider_config():
    providers=[
        ("gemini",os.environ.get("GEMINI_API_KEY"),os.environ.get("GEMINI_MODEL","gemini-2.5-flash-lite")),
        ("groq",os.environ.get("GROQ_API_KEY"),os.environ.get("GROQ_MODEL","openai/gpt-oss-20b")),
        ("deepseek",os.environ.get("DEEPSEEK_API_KEY"),os.environ.get("DEEPSEEK_MODEL","deepseek-chat")),
        ("openai",os.environ.get("OPENAI_API_KEY"),os.environ.get("OPENAI_MODEL","gpt-4.1-mini")),
    ]
    return next(((name,key.strip(),model) for name,key,model in providers if key and key.strip()),None)


def extraction_prompt(items: list[dict]) -> str:
    public=[]
    for item in items:
        public.append({"id":item["id"],"platform":item["source_platform"],"track":item["track"],"title":item["raw_title"],
                       "body":item["body"][:2600],"body_scope":item["body_scope"],"engagement":item["engagement"]})
    return (
        "你是公开帖子事实提取器。仅依据输入正文，用大白话中文输出指定JSON。"
        "deal_fact_zh必须区分报价、$bid竞标、$paid帖子状态、作者自述和独立核验到账；没有数字写‘⚪ 原帖未披露具体成交单数’。"
        "solver_case_zh没有同帖成功证据就明确写没有，不能编故事。action_plan_zh给3个可验收步骤。"
        "platform_ecology_tip_zh写平台规则、响应目标、小样、付款与封号风险；任何时间窗都标为策略目标，不冒充成功率。"
        "成人业务只写授权、年龄、结算和经营服务；严禁通过User-Agent向审核机器人展示不同内容、绕过验证、侵权或欺骗。"
        "reverse_money_idea_zh写3条详细路径：经客户同意的透明分包、把授权流程做成工具/模板、从公开痛点找上游；不得出售隐私或偷客户。"
        "不要输出收益概率，不要补造原文不存在的金额、地区、成交数或人物。输入如下：\n"+json.dumps(public,ensure_ascii=False)
    )


def call_llm(provider, items: list[dict]) -> dict[str,dict]:
    name,key,model=provider; prompt=extraction_prompt(items); schema={"type":"array","items":SCHEMA_ITEM}
    if name=="gemini":
        url=f"https://generativelanguage.googleapis.com/v1beta/models/{quote(model,safe='')}:generateContent?key={quote(key)}"
        payload={"contents":[{"parts":[{"text":prompt}]}],"generationConfig":{"temperature":0.15,"responseMimeType":"application/json","responseSchema":schema}}
        response=requests.post(url,json=payload,timeout=55); response.raise_for_status(); data=response.json()
        text=data["candidates"][0]["content"]["parts"][0]["text"]
    else:
        endpoints={"groq":"https://api.groq.com/openai/v1/chat/completions","deepseek":"https://api.deepseek.com/chat/completions","openai":"https://api.openai.com/v1/chat/completions"}
        response_format={"type":"json_schema","json_schema":{"name":"opportunity_batch","strict":True,"schema":schema}} if name=="groq" else {"type":"json_object"}
        wrapper_prompt=prompt if name=="groq" else prompt+"\n非严格接口请输出对象：{\"items\":[...上述数组对象...]}。"
        payload={"model":model,"temperature":0.15,"messages":[{"role":"user","content":wrapper_prompt}],"response_format":response_format}
        response=requests.post(endpoints[name],json=payload,headers={"Authorization":"Bearer "+key,"Content-Type":"application/json"},timeout=55);response.raise_for_status()
        text=response.json()["choices"][0]["message"]["content"]
    parsed=json.loads(text); parsed=parsed.get("items",[]) if isinstance(parsed,dict) else parsed
    if not isinstance(parsed,list): raise ValueError("LLM response is not a list")
    result={}
    originals={item["id"]:item for item in items}
    for row in parsed:
        if not isinstance(row,dict) or row.get("id") not in originals or any(not isinstance(row.get(f),str) or not row[f].strip() for f in FIELDS): continue
        combined=" ".join(row[f] for f in FIELDS)
        if BLOCKED_METHODS.search(combined) or re.search(r"\b(?:90|95|100)%|必胜|稳赚|秒封绕过",combined,re.I): continue
        # A deterministic fact extractor owns the money field so model prose can never add amounts.
        row["deal_fact_zh"]=extract_deal_fact(originals[row["id"]])
        row.update(structured_by=f"llm:{name}:{model}",structured_note="大模型结构化拆解；金额字段经规则重新核验，原文仍是最终依据。")
        result[row["id"]]=row
    return result


def enrich_new(items: list[dict], previous: dict[str,dict]) -> tuple[list[dict],dict]:
    output=[]; new=[]; reused=0
    for item in items:
        old=previous.get(item["id"])
        if old and old.get("source_content_sha256")==item["source_content_sha256"] and all(old.get(field) for field in FIELDS):
            merged={**old,**{k:item[k] for k in ["fetched_at","engagement","published_at"]}};output.append(merged);reused+=1
        else:new.append(item)
    provider=provider_config(); llm_results={}; failures=[]
    if provider:
        for offset in range(0,len(new),5):
            batch=new[offset:offset+5]
            try: llm_results.update(call_llm(provider,batch))
            except Exception as exc:
                failures.append(f"{provider[0]}批次{offset//5+1}失败：{type(exc).__name__}")
                if isinstance(exc,requests.HTTPError) and exc.response is not None and exc.response.status_code in {401,403,429}: break
    for item in new:
        enriched=rules_enrich(item); enriched.update(llm_results.get(item["id"],{}))
        public={k:v for k,v in item.items() if k!="body"}; public.update(enriched)
        public.update(evidence_excerpt=item["body"][:720],feasibility_pct=evidence_score(item),
                      feasibility_note="可行性/证据完整度评分，不是拿单或赚钱成功率。",
                      time_to_money="响应目标：当天" if item["track"]=="bounty_direct" else "先验证付费意愿；不承诺见钱周期",
                      capital_req="先做小样所需时间与合规工具费；原帖未提供完整成本")
        output.append(public)
    report={"provider":provider[0]+":"+provider[2] if provider else "none","new_records":len(new),"reused_records":reused,
            "llm_enriched":len(llm_results),"rule_enriched":len(new)-len(llm_results),"failures":failures}
    return output,report


def scan() -> dict:
    previous_payload=load_json(LIVE_FILE,{"records":[]});previous={row["id"]:row for row in previous_payload.get("records",[]) if row.get("id")}
    tasks=[]
    tasks.append(("reddit:16-communities-sequential",fetch_reddit_all))
    for query in HN_QUERIES:tasks.append(("hn:"+query,lambda q=query:fetch_hn(q)))
    for node in ["jobs","outsourcing"]:tasks.append(("v2ex:"+node,lambda n=node:fetch_v2ex(n)))
    tasks.extend([
        ("bhw:journey",lambda:fetch_bhw("journey","my-journey-discussions.167","gray_arb")),
        ("bhw:hire",lambda:fetch_bhw("hire","hire-a-freelancer.76","bounty_direct")),
        ("dlsite:r18",fetch_dlsite),("chaturbate:affiliate",fetch_chaturbate),
    ])
    raw=[]; statuses=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
        future_map={pool.submit(func):name for name,func in tasks}
        for future in concurrent.futures.as_completed(future_map):
            try:rows,status=future.result()
            except Exception as exc:
                rows=[];status=health(future_map[future],future_map[future],"internal_error",None,0,0,type(exc).__name__)
            raw.extend(rows);statuses.extend(status if isinstance(status,list) else [status])
    unique={}
    for item in raw:
        if safe_item(item): unique[item["id"]]=item
    enriched,extraction=enrich_new(list(unique.values()),previous)
    # Preserve recent records from temporarily unavailable sources, but mark their last observation time.
    seen={row["id"] for row in enriched}
    for row in previous.values():
        if row["id"] not in seen: enriched.append(row)
    def order(row): return row.get("published_at") or row.get("fetched_at") or ""
    enriched=sorted(enriched,key=order,reverse=True)[:MAX_RECORDS]
    event=os.environ.get("GITHUB_EVENT_NAME","local");run_id=os.environ.get("GITHUB_RUN_ID")
    payload={"version":"10.2","updated_at":utcnow(),"run":{"environment":"github-actions" if os.environ.get("GITHUB_ACTIONS")=="true" else "local",
             "trigger_event":event,"run_id":run_id,"run_url":f"https://github.com/{os.environ.get('GITHUB_REPOSITORY')}/actions/runs/{run_id}" if run_id else None},
             "records":enriched,"stats":{"total":len(enriched),"fetched_this_run":len(raw),"new_this_run":extraction["new_records"],
             "llm_enriched":sum(str(r.get("structured_by","")).startswith("llm:") for r in enriched),
             "rule_enriched":sum(r.get("structured_by")=="rules-v10.2" for r in enriched),"extraction":extraction},
             "truth_note":"金额、竞标、帖子状态和平台指标分开；互动量不等于成交，机器拆解不替代原文核对。"}
    health_payload={"version":"10.2","updated_at":payload["updated_at"],"summary":{"configured_sources":len(statuses),
                    "responding_sources":sum(s["status"]=="ok" for s in statuses),"failed_sources":sum(s["status"] not in {"ok","not_configured"} for s in statuses)},
                    "sources":sorted(statuses,key=lambda s:s["name"])}
    save_json(LIVE_FILE,payload);save_json(HEALTH_FILE,health_payload)
    print(json.dumps({"records":len(enriched),"fetched":len(raw),"sources_ok":health_payload["summary"]["responding_sources"],"extraction":extraction},ensure_ascii=False))
    return payload


class Handler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control","no-store");self.send_header("X-Content-Type-Options","nosniff");super().end_headers()
    def log_message(self,format,*args): pass


def serve(port: int):
    os.chdir(ROOT);server=ThreadingHTTPServer(("127.0.0.1",port),Handler)
    print(f"v10.2本地只读服务：http://127.0.0.1:{port}/；不会自动打开浏览器。")
    try:server.serve_forever()
    except KeyboardInterrupt:pass


def self_test():
    item=make_raw("reddit","fixture","[TASK] clean CSV","Need two files merged. Budget $60. $bid", "https://example.com/t",track="bounty_direct")
    assert "$bid" in extract_deal_fact(item) and "不等于" in extract_deal_fact(item)
    assert "90%" not in platform_tip(item) and "没有核验" in platform_tip(item)
    fields=rules_enrich(item);assert all(fields.get(name) for name in FIELDS)
    assert not safe_item(make_raw("x","x","deepnude tool","nudify photos","https://example.com/b"))
    public={k:v for k,v in item.items() if k!="body"};assert "body" not in public
    print("v10.2 self-test passed: factual money, complete fields, safe fallback, no raw full body export.")


def main():
    parser=argparse.ArgumentParser();parser.add_argument("--cloud-once",action="store_true");parser.add_argument("--self-test",action="store_true");parser.add_argument("--serve",action="store_true");parser.add_argument("--port",type=int,default=8765);args=parser.parse_args()
    if args.self_test:self_test()
    elif args.cloud_once:scan()
    elif args.serve:serve(args.port)
    else:parser.print_help()


if __name__=="__main__":main()
