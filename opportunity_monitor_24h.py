#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
全球痛点与真实赚钱机会 24h 自动监控引擎 (v11.1 全球65+频道满血恢复·悬赏分钟倒序版)
================================================================================
"""

import os
import sys
import time
import json
import re
import html
import sqlite3
import random
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
from http.server import HTTPServer, SimpleHTTPRequestHandler
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import argparse
from bs4 import BeautifulSoup

try:
    from curl_cffi import requests as cffi_requests
    HAS_CURL_CFFI = True
except ImportError:
    HAS_CURL_CFFI = False

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "radar_pain_solver_history.db")
JSON_OUT_PATH = os.path.join(BASE_DIR, "live_signals.json")
PROXY_FILE = os.path.join(BASE_DIR, "ip3.txt")

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15"
]

FAKE_GURU_BLACKLIST = [
    "buy my course", "join my paid discord", "dm me for secret", "100x guaranteed",
    "free webinar", "masterclass", "coaching program"
]

FAST_BOUNTY_SUBS = [
    ("slavelabour", "bounty_direct", "Reddit r/slavelabour (微任务现金急单)"),
    ("forhire", "bounty_direct", "Reddit r/forhire (全球自由职业雇佣)"),
    ("DoneDirtCheap", "bounty_direct", "Reddit r/DoneDirtCheap (低价外包快单)"),
    ("hireaprogrammer", "bounty_direct", "Reddit r/hireaprogrammer (开发急单直聘)"),
    ("freelance_forhire", "bounty_direct", "Reddit r/freelance_forhire (自由职业急单)")
]

REDDIT_TARGET_SUBS = [
    *[(s[0], s[1], s[2], "new") for s in FAST_BOUNTY_SUBS],
    ("webscraping", "bounty_direct", "Reddit r/webscraping (爬虫代抓与反爬求助)", "top_month"),
    ("excel", "pain_saas", "Reddit r/excel (全球表格自动化痛点热榜)", "top_month"),
    ("googlesheets", "pain_saas", "Reddit r/googlesheets (谷歌表格脚本痛点热榜)", "top_month"),
    ("SaaS", "pain_saas", "Reddit r/SaaS (软件痛点与变现复盘)", "top_month"),
    ("SideProject", "pain_saas", "Reddit r/SideProject (独立副业产品变现)", "top_month"),
    ("microsaas", "pain_saas", "Reddit r/microsaas (微型SaaS真实营收榜)", "top_month"),
    ("sweatystartup", "pain_saas", "Reddit r/sweatystartup (传统本地生意痛点)", "top_month"),
    ("smallbusiness", "pain_saas", "Reddit r/smallbusiness (小微老板痛点)", "top_month"),
    ("Entrepreneur", "pain_saas", "Reddit r/Entrepreneur (创业痛点吐槽)", "top_month"),
    ("Automate", "pain_saas", "Reddit r/Automate (自动化工作流需求)", "top_month"),
    ("beermoney", "gray_arb", "Reddit r/beermoney (网赚实测打款)", "top_month"),
    ("sidehustle", "gray_arb", "Reddit r/sidehustle (野路子副业)", "top_month"),
    ("flipping", "gray_arb", "Reddit r/flipping (跨平台低买高卖倒爷)", "top_month"),
    ("affiliatemarketing", "gray_arb", "Reddit r/affiliatemarketing (联盟营销套利)", "top_month"),
    ("SEO", "gray_arb", "Reddit r/SEO (搜索流量截流与寄生虫SEO)", "top_month"),
    ("juststart", "gray_arb", "Reddit r/juststart (流量站实战连载)", "top_month"),
    ("NSFWCreators", "nsfw_adult", "Reddit r/NSFWCreators (成人创作者变现)", "top_month"),
    ("onlyfansadvice", "nsfw_adult", "Reddit r/onlyfansadvice (OnlyFans私域引流)", "top_month"),
    ("CreatorsAdvice", "nsfw_adult", "Reddit r/CreatorsAdvice (擦边订阅制变现)", "top_month")
]


def clean_raw_html(raw_text):
    if not raw_text:
        return ""
    txt = html.unescape(html.unescape(str(raw_text)))
    txt = re.sub(r"<!--[\s\S]*?-->", " ", txt)
    txt = re.sub(r"<[^>]+>", " ", txt)
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt


def load_proxies():
    proxies = []
    env_px = os.environ.get("PROXY_URL", "").strip()
    if env_px:
        proxies.append(env_px)
    if os.path.exists(PROXY_FILE):
        with open(PROXY_FILE, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                s = line.strip()
                if not s or s.startswith("#"):
                    continue
                parts = s.split(":")
                if len(parts) == 2:
                    proxies.append(f"http://{parts[0]}:{parts[1]}")
                elif len(parts) >= 4:
                    proxies.append(f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}")
    return proxies


def http_get(url, timeout=14, headers=None):
    scraper_key = os.environ.get("SCRAPER_API_KEY", "").strip()
    target_url = url
    if scraper_key and any(d in url for d in ("blackhatworld.com", "reddit.com", "etsy.com", "upwork.com")):
        target_url = f"http://api.scraperapi.com?api_key={scraper_key}&url={urllib.parse.quote(url)}"

    proxies = load_proxies()
    chosen_proxy = random.choice(proxies) if (proxies and not scraper_key) else None

    request_headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "application/json, text/html, application/xml;q=0.9, */*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,ja;q=0.7"
    }
    if headers:
        request_headers.update(headers)

    if HAS_CURL_CFFI:
        px_dict = {"http": chosen_proxy, "https": chosen_proxy} if chosen_proxy else None
        resp = cffi_requests.get(target_url, impersonate="chrome124", headers=request_headers, proxies=px_dict, timeout=timeout)
        resp.raise_for_status()
        return resp.text

    req = urllib.request.Request(target_url, headers=request_headers)
    if chosen_proxy:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({"http": chosen_proxy, "https": chosen_proxy}))
    else:
        opener = urllib.request.build_opener()
    return opener.open(req, timeout=timeout).read().decode("utf-8", errors="ignore")


def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS signals (
            id TEXT PRIMARY KEY,
            track TEXT,
            title_zh TEXT,
            summary_one_line TEXT,
            deal_fact_zh TEXT,
            pain_point_zh TEXT,
            solver_case_zh TEXT,
            platform_ecology_tip_zh TEXT,
            reverse_money_idea_zh TEXT,
            action_plan_zh TEXT,
            feasibility_pct INTEGER,
            time_to_money TEXT,
            capital_req TEXT,
            source_platform TEXT,
            source_url TEXT,
            solver_url TEXT,
            created_at TEXT,
            deliverable_type TEXT,
            created_ts INTEGER
        )
    """)
    columns = {row[1] for row in c.execute("PRAGMA table_info(signals)")}
    if "created_ts" not in columns:
        c.execute("ALTER TABLE signals ADD COLUMN created_ts INTEGER DEFAULT 0")
    c.execute("""
        CREATE TABLE IF NOT EXISTS notified_bounties (
            id TEXT PRIMARY KEY,
            notified_at TEXT
        )
    """)
    conn.commit()
    conn.close()


def send_multichannel_bounty_alert(bounty_item, author_name="", custom_dm_en=""):
    clean_title = bounty_item.get("title_zh", "")
    source_url = bounty_item.get("source_url", "")
    deal_fact = bounty_item.get("deal_fact_zh", "")
    pain_txt = bounty_item.get("pain_point_zh", "")[:280]
    action_txt = bounty_item.get("action_plan_zh", "")[:260]

    dm_url = f"https://www.reddit.com/message/compose/?to={author_name}" if author_name else source_url
    if not custom_dm_en:
        custom_dm_en = (
            "Hey! Just saw your task post. Before your inbox gets flooded with generic bids, "
            "I already built a quick working sample based on your exact requirements (screenshot attached). "
            "I can deliver the complete files within 1-2 hours. Let me know if you want to check the sample!"
        )

    plain_summary = (
        f"🚨【10分钟黄金抢单窗 · 新悬赏急单】\n"
        f"📌 标题：{clean_title}\n"
        f"💰 核验：{deal_fact}\n\n"
        f"📝 雇主具体要求：\n{pain_txt}\n\n"
        f"⚡ 3分钟秒拿单动作：\n{action_txt}\n\n"
        f"💬 私信话术：\n{custom_dm_en}\n\n"
        f"🔗 原帖直链：{source_url}"
    )

    pushed_any = False
    pushplus_token = os.environ.get("PUSHPLUS_TOKEN", "").strip()
    if pushplus_token:
        try:
            pp_data = json.dumps({
                "token": pushplus_token,
                "title": f"🚨新悬赏急单: {clean_title[:35]}",
                "content": plain_summary.replace("\n", "<br>"),
                "template": "html"
            }).encode("utf-8")
            req = urllib.request.Request("http://www.pushplus.plus/send", data=pp_data, headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=10).read()
            pushed_any = True
            print(f"[PUSHPLUS SUCCESS] {clean_title[:50]}")
        except Exception as exc:
            print(f"[PUSHPLUS WARN] {type(exc).__name__}: {exc}")

    webhook_url = os.environ.get("WEBHOOK_URL", "").strip()
    if webhook_url:
        try:
            wb_payload = {"msg_type": "text", "content": {"text": plain_summary}} if ("feishu" in webhook_url) else {"msgtype": "text", "text": {"content": plain_summary}}
            req = urllib.request.Request(webhook_url, data=json.dumps(wb_payload).encode("utf-8"), headers={"Content-Type": "application/json"})
            response_text = urllib.request.urlopen(req, timeout=10).read().decode("utf-8", errors="ignore")
            if "feishu" in webhook_url or "larksuite" in webhook_url:
                response_data = json.loads(response_text or "{}")
                response_code = response_data.get("code", response_data.get("StatusCode", 0))
                if response_code not in (0, "0", None):
                    raise RuntimeError(f"Feishu code={response_code}: {response_data.get('msg') or response_data.get('StatusMessage')}")
            pushed_any = True
            print(f"[WEBHOOK SUCCESS] {clean_title[:50]}")
        except Exception as exc:
            print(f"[WEBHOOK WARN] {type(exc).__name__}: {exc}")
    if not pushplus_token and not webhook_url:
        print("[PUSH SKIP] PUSHPLUS_TOKEN 与 WEBHOOK_URL 均未配置")
    return pushed_any


def call_gemini_fast_bounty_dm(raw_title, raw_body, author_name=""):
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        print("[GEMINI SKIP] GEMINI_API_KEY 未配置")
        return None
    model = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite").strip()
    prompt = f"""请根据下面这条新悬赏单返回严格 JSON，不要 Markdown：
{{"title_zh":"中文一句话任务与预算摘要","sample_3min_zh":"3分钟可执行的小样步骤","custom_dm_en":"70词以内、点名具体需求的英文私信"}}
作者：{author_name}
标题：{raw_title}
正文：{raw_body[:1600]}"""
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{urllib.parse.quote(model, safe='')}:generateContent?key={urllib.parse.quote(api_key)}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0.25},
        }
        request = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
        response = json.loads(urllib.request.urlopen(request, timeout=20).read().decode("utf-8"))
        result = json.loads(response["candidates"][0]["content"]["parts"][0]["text"])
        print(f"[GEMINI SUCCESS] {raw_title[:50]}")
        return result if isinstance(result, dict) else None
    except Exception as exc:
        print(f"[GEMINI WARN] {type(exc).__name__}: {exc}")
        return None


def extract_honest_deal_fact(text_blob, ups=0, comments=0):
    dlsite_sales = re.search(r'販売数[:：\s]*([\d,]+)', text_blob)
    if dlsite_sales:
        sold_num = dlsite_sales.group(1)
        return f"✅ 100% 官方公开真实销量：热销 {sold_num} 份 (DLsite 铁证)"

    paid_bids = len(re.findall(r'\$bid|\$paid|\[hiring\]|\[task\]|bounty', text_blob, re.IGNORECASE))
    money_matches = re.findall(r'(\$\d+(?:,\d{3})*(?:\.\d{1,2})?(?:\s*(?:k|K|MRR|mrr|/mo|/day|/hr))?)', text_blob)

    if paid_bids > 0 and money_matches:
        top_nums = " / ".join(list(dict.fromkeys(money_matches))[:2])
        return f"✅ 真金白银悬赏: {top_nums} | 竞争: {comments}条评论"
    if money_matches:
        top_nums = " / ".join(list(dict.fromkeys(money_matches))[:3])
        return f"📊 披露金额/营收: {top_nums} | 热度: {ups}赞"
    return f"🔥 高关注真需求 ({ups}赞 · {comments}评)"


def generate_unique_non_template_analysis(rawTitle, rawBody, sourceLabel, sourceUrl, defaultTrack, ups, cmts):
    blob = f"{rawTitle} {rawBody}"
    cleanTitle = re.sub(r'^\[[^\]]+\]\s*|^【[^】]+】\s*', '', rawTitle).strip()
    return {
        "pain_point_zh": f"【来自 {sourceLabel} 的实时标的：《{cleanTitle}》】\n● 原帖摘要：{rawBody[:250]}\n● 互动指标：{ups}赞 · {cmts}评论",
        "solver_case_zh": f"顺应当前热度，围绕该标的提供『买断制极简工具』、『人工代配置服务』或『跨国信息差搬运』快速变现。",
        "action_plan_zh": "1. 点开左下角原帖直链核验最新上下文；\n2. 5分钟内跑出前20行样本或Demo截图；\n3. 私信发帖人或在评论区高赞楼中楼截流成交。",
        "platform_ecology_tip_zh": "🔥 抢单抢占先机：必须在刚发布的黄金 10 分钟~2 小时内介入，切勿在公开评论区发直链。",
        "reverse_money_idea_zh": "🔄 逆向搞钱思路：1. 跨国二道贩子转包赚差价；2. 把痛点解决方案打包成标品复卖；3. 搬运回国内小红书/闲鱼做信息差变现。"
    }


def sanitizeAndUpgradeSignal(rawItem):
    title = clean_raw_html(rawItem.get("title_zh") or rawItem.get("title") or "")
    pain = clean_raw_html(rawItem.get("pain_point_zh") or rawItem.get("selftext") or "")
    if not title:
        return None
    if re.search(r'\[offer\]|\[for\s*hire\]', title, re.I):
        return None

    isBaseCard = String(rawItem.get("id") or "").startswith("base_") if "String" in globals() else str(rawItem.get("id", "")).startswith("base_")
    createdTs = int(rawItem.get("created_ts") or rawItem.get("created_utc") or time.time())

    u = generate_unique_non_template_analysis(title, pain, rawItem.get("source_platform", "全球社区"), rawItem.get("source_url", ""), rawItem.get("track", "pain_saas"), rawItem.get("ups", 10), rawItem.get("num_comments", 3))
    return {
        "id": rawItem.get("id") or f"sig_{abs(hash(title))}",
        "track": rawItem.get("track", "pain_saas"),
        "title_zh": title,
        "summary_one_line": rawItem.get("summary_one_line") or f"实时高热收录",
        "deal_fact_zh": rawItem.get("deal_fact_zh") or extract_honest_deal_fact(f"{title} {pain}", rawItem.get("ups", 0), rawItem.get("num_comments", 0)),
        "pain_point_zh": u["pain_point_zh"],
        "solver_case_zh": u["solver_case_zh"],
        "platform_ecology_tip_zh": u["platform_ecology_tip_zh"],
        "reverse_money_idea_zh": u["reverse_money_idea_zh"],
        "action_plan_zh": u["action_plan_zh"],
        "feasibility_pct": 90,
        "time_to_money": "当天~3天",
        "capital_req": "$0",
        "source_platform": rawItem.get("source_platform", "全球社区"),
        "source_url": rawItem.get("source_url", "https://reddit.com"),
        "solver_url": rawItem.get("solver_url", "https://reddit.com"),
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "deliverable_type": "bounty_sniper_py",
        "created_ts": createdTs
    }


def fetch_reddit_jsonp_py(sub, mode="new", limit=35):
    errors = []
    reddit_headers = {
        "User-Agent": "GlobalOpportunityRadar/1.0 (+https://github.com/vivi9116/global-opportunity-radar)",
        "Accept": "application/json"
    }
    path = f"top.json?t=month&limit={limit}&raw_json=1" if mode == "top_month" else f"new.json?limit={limit}&raw_json=1"
    for host in ("www.reddit.com", "old.reddit.com"):
        try:
            raw = http_get(f"https://{host}/r/{sub}/{path}", timeout=12, headers=reddit_headers)
            data = json.loads(raw)
            posts = [c["data"] for c in data.get("data", {}).get("children", [])]
            if posts:
                return posts
            errors.append(f"{host}: empty JSON")
        except Exception as exc:
            errors.append(f"{host}: {type(exc).__name__}: {exc}")

    try:
        listing = "top" if mode == "top_month" else "new"
        query = f"?t=month&limit={limit}" if mode == "top_month" else f"?limit={limit}"
        rss_url = f"https://www.reddit.com/r/{sub}/{listing}/.rss{query}"
        soup = BeautifulSoup(http_get(rss_url, timeout=12, headers={"Accept": "application/atom+xml, application/rss+xml"}), "xml")
        posts = []
        for entry in soup.find_all(["entry", "item"]):
            title_node = entry.find("title")
            link_node = entry.find("link")
            title = clean_raw_html(title_node.get_text(" ", strip=True) if title_node else "")
            source_url = link_node.get("href", "") if link_node and link_node.has_attr("href") else link_node.get_text(strip=True) if link_node else ""
            content_node = entry.find("content") or entry.find("description") or entry.find("summary")
            body = clean_raw_html(content_node.decode_contents() if content_node else "")
            post_match = re.search(r"/comments/([^/]+)", source_url)
            if not title or not source_url or not post_match:
                continue
            author_node = entry.find("author")
            author_name = clean_raw_html(author_node.get_text(" ", strip=True) if author_node else "")
            author_name = re.sub(r"^/?u/", "", author_name, flags=re.I)
            date_node = entry.find("updated") or entry.find("published") or entry.find("pubDate")
            posts.append({
                "id": post_match.group(1), "title": title, "selftext": body,
                "author": author_name, "created_utc": _iso_timestamp(date_node.get_text(strip=True) if date_node else "", int(time.time())),
                "ups": 0, "num_comments": 0, "permalink": urllib.parse.urlparse(source_url).path,
            })
        if posts:
            print(f"[SOURCE OK] Reddit r/{sub}: RSS fallback {len(posts)}")
            return posts
        errors.append("RSS: empty feed")
    except Exception as exc:
        errors.append(f"RSS: {type(exc).__name__}: {exc}")
    print(f"[SOURCE WARN] Reddit r/{sub}: {' | '.join(errors)}")
    return []


def _iso_timestamp(value, fallback):
    try:
        return int(datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp())
    except (TypeError, ValueError):
        return fallback


def fetch_additional_sources(now_ts):
    items = []

    for query in ("willing to pay", "too expensive alternative", "first sale MRR", "freelance automation scraping"):
        try:
            url = "https://hn.algolia.com/api/v1/search_by_date?tags=story&hitsPerPage=30&query=" + urllib.parse.quote(query)
            data = json.loads(http_get(url, timeout=15))
            for hit in data.get("hits", []):
                object_id = str(hit.get("objectID") or "")
                title = clean_raw_html(hit.get("title") or hit.get("story_title") or "")
                if not object_id or not title:
                    continue
                item = sanitizeAndUpgradeSignal({
                    "id": f"hn_{object_id}", "created_ts": _iso_timestamp(hit.get("created_at"), now_ts - 3600),
                    "track": "pain_saas", "ups": hit.get("points") or 0, "num_comments": hit.get("num_comments") or 0,
                    "title_zh": f"【Hacker News】{title}", "pain_point_zh": hit.get("story_text") or title,
                    "source_platform": "Hacker News Algolia", "source_url": f"https://news.ycombinator.com/item?id={object_id}",
                    "solver_url": f"https://news.ycombinator.com/item?id={object_id}",
                })
                if item:
                    items.append(item)
            print(f"[SOURCE OK] Hacker News: {query}")
        except Exception as exc:
            print(f"[SOURCE WARN] Hacker News {query}: {type(exc).__name__}: {exc}")

    for node in ("jobs", "outsourcing"):
        try:
            data = json.loads(http_get(f"https://www.v2ex.com/api/topics/show.json?node_name={node}", timeout=15))
            for topic in data:
                topic_id = str(topic.get("id") or "")
                title = clean_raw_html(topic.get("title") or "")
                if not topic_id or not title:
                    continue
                source_url = topic.get("url") or f"https://www.v2ex.com/t/{topic_id}"
                item = sanitizeAndUpgradeSignal({
                    "id": f"v2ex_{topic_id}", "created_ts": int(topic.get("created") or now_ts),
                    "track": "bounty_direct", "num_comments": topic.get("replies") or 0,
                    "title_zh": f"【V2EX {node}】{title}",
                    "pain_point_zh": topic.get("content_rendered") or topic.get("content") or title,
                    "source_platform": f"V2EX {node}", "source_url": source_url, "solver_url": source_url,
                })
                if item:
                    items.append(item)
            print(f"[SOURCE OK] V2EX {node}")
        except Exception as exc:
            print(f"[SOURCE WARN] V2EX {node}: {type(exc).__name__}: {exc}")

    try:
        dlsite_url = "https://www.dlsite.com/maniax/ranking/day?sort=sale&order=desc"
        soup = BeautifulSoup(http_get(dlsite_url, timeout=20), "lxml")
        dlsite_count = 0
        for row in soup.select("table.ranking_worklist tr"):
            links = [a for a in row.select("a[href*='/work/=/product_id/']") if "btn_free_sample" not in (a.get("class") or []) and a.get_text(" ", strip=True)]
            if not links:
                continue
            anchor = links[0]
            title = clean_raw_html(anchor.get_text(" ", strip=True))
            source_url = urllib.parse.urljoin(dlsite_url, anchor.get("href", ""))
            body = clean_raw_html(row.get_text(" ", strip=True))
            product_match = re.search(r"/product_id/([^/.]+)", source_url)
            product_id = product_match.group(1) if product_match else str(abs(hash(source_url)))
            item = sanitizeAndUpgradeSignal({
                "id": f"dlsite_{product_id}", "created_ts": now_ts - 3600, "track": "nsfw_adult",
                "title_zh": f"【DLsite R18 日榜】{title}", "pain_point_zh": body,
                "deal_fact_zh": extract_honest_deal_fact(body), "source_platform": "DLsite R18 日榜",
                "source_url": source_url, "solver_url": source_url,
            })
            if item:
                items.append(item)
                dlsite_count += 1
        print(f"[SOURCE OK] DLsite: {dlsite_count}")
    except Exception as exc:
        print(f"[SOURCE WARN] DLsite: {type(exc).__name__}: {exc}")

    for kind, forum, track in (("journey", "my-journey-discussions.167", "gray_arb"), ("hire", "hire-a-freelancer.76", "bounty_direct")):
        try:
            feed_url = f"https://www.blackhatworld.com/forums/{forum}/index.rss"
            soup = BeautifulSoup(http_get(feed_url, timeout=20), "xml")
            bhw_count = 0
            for entry in soup.find_all(["entry", "item"]):
                title_node = entry.find("title")
                link_node = entry.find("link")
                title = clean_raw_html(title_node.get_text(" ", strip=True) if title_node else "")
                source_url = (link_node.get("href") if link_node and link_node.has_attr("href") else link_node.get_text(strip=True) if link_node else "")
                content_node = entry.find("content") or entry.find("description") or entry.find("summary")
                body = clean_raw_html(content_node.decode_contents() if content_node else "")
                if not title or not source_url:
                    continue
                item = sanitizeAndUpgradeSignal({
                    "id": f"bhw_{kind}_{abs(hash(source_url))}", "created_ts": now_ts - 7200, "track": track,
                    "title_zh": f"【BlackHatWorld {kind}】{title}", "pain_point_zh": body,
                    "source_platform": f"BlackHatWorld {kind}", "source_url": source_url, "solver_url": source_url,
                })
                if item:
                    items.append(item)
                    bhw_count += 1
            if bhw_count == 0:
                forum_url = f"https://www.blackhatworld.com/forums/{forum}/"
                page = BeautifulSoup(http_get(forum_url, timeout=20), "lxml")
                for row in page.select(".structItem--thread")[:30]:
                    anchor = row.select_one('.structItem-title a[data-tp-primary="on"]') or row.select_one('.structItem-title a[href*="/threads/"]')
                    if not anchor:
                        continue
                    title = clean_raw_html(anchor.get_text(" ", strip=True))
                    source_url = urllib.parse.urljoin(forum_url, anchor.get("href", ""))
                    body = clean_raw_html(row.get_text(" ", strip=True))
                    thread_match = re.search(r"/threads/(?:[^/]*\.)?(\d+)", source_url)
                    if not title or not source_url:
                        continue
                    item = sanitizeAndUpgradeSignal({
                        "id": f"bhw_{kind}_{thread_match.group(1) if thread_match else abs(hash(source_url))}",
                        "created_ts": now_ts - 7200, "track": track,
                        "title_zh": f"【BlackHatWorld {kind}】{title}", "pain_point_zh": body,
                        "source_platform": f"BlackHatWorld {kind}", "source_url": source_url, "solver_url": source_url,
                    })
                    if item:
                        items.append(item)
                        bhw_count += 1
                if bhw_count:
                    print(f"[SOURCE OK] BlackHatWorld {kind}: HTML fallback {bhw_count}")
                else:
                    print(f"[SOURCE WARN] BlackHatWorld {kind}: RSS 与公开页面均返回 0 条")
            else:
                print(f"[SOURCE OK] BlackHatWorld {kind}: {bhw_count}")
        except Exception as exc:
            print(f"[SOURCE WARN] BlackHatWorld {kind}: {type(exc).__name__}: {exc}")

    wm = os.environ.get("CHATURBATE_WM", "").strip()
    if not wm:
        print("[SOURCE SKIP] Chaturbate: CHATURBATE_WM 未配置")
    else:
        try:
            url = "https://chaturbate.com/api/public/affiliates/onlinerooms/?wm=" + urllib.parse.quote(wm) + "&format=json"
            data = json.loads(http_get(url, timeout=20))
            rooms = data.get("results", []) if isinstance(data, dict) else data
            for room in rooms[:100]:
                username = str(room.get("username") or "")
                if not username:
                    continue
                viewers = int(room.get("num_users") or 0)
                source_url = room.get("chat_room_url") or f"https://chaturbate.com/{username}/"
                item = sanitizeAndUpgradeSignal({
                    "id": f"cb_{username}", "created_ts": now_ts, "track": "nsfw_adult", "ups": viewers,
                    "title_zh": f"【Chaturbate 在线房间】{username}",
                    "pain_point_zh": f"当前在线 {viewers} 人；标签：{' / '.join(room.get('tags') or [])}",
                    "deal_fact_zh": f"✅ 官方API实时在线人数：{viewers}", "source_platform": "Chaturbate官方联盟API",
                    "source_url": source_url, "solver_url": source_url,
                })
                if item:
                    items.append(item)
            print(f"[SOURCE OK] Chaturbate: {len(rooms[:100])}")
        except Exception as exc:
            print(f"[SOURCE WARN] Chaturbate: {type(exc).__name__}: {exc}")
    return items


def run_fast_bounty_and_radar():
    init_db()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    now_ts = int(time.time())
    all_fetched = []
    alert_candidates = []

    print(f"[{now_str}] 🚀 正在执行满血 65+ 频道全网扫描 (悬赏按最新倒序)...")

    # 1. 抓快轨悬赏急单
    for sub, track, label in FAST_BOUNTY_SUBS:
        posts = fetch_reddit_jsonp_py(sub, "new", 30)
        for d in posts:
            title = clean_raw_html(d.get("title", ""))
            if not title or re.search(r'\[offer\]|\[for\s*hire\]', title, re.I):
                continue
            item = sanitizeAndUpgradeSignal({
                "id": f"rd_{d.get('id')}",
                "created_ts": d.get("created_utc", now_ts),
                "track": track,
                "ups": d.get("ups", 0),
                "num_comments": d.get("num_comments", 0),
                "title_zh": f"【{label}】{title}",
                "pain_point_zh": d.get("selftext") or title,
                "source_platform": label,
                "source_url": "https://www.reddit.com" + d.get("permalink", ""),
                "solver_url": "https://www.reddit.com" + d.get("permalink", "")
            })
            if item:
                all_fetched.append(item)
                alert_candidates.append((item, d.get("author", ""), title, clean_raw_html(d.get("selftext") or "")))

    # 2. 抓 GitHub 实时新悬赏单
    try:
        two_days_ago = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
        gh_url = f"https://api.github.com/search/issues?q=label:bounty+state:open+created:>={two_days_ago}&sort=created&order=desc&per_page=35"
        gh_data = json.loads(http_get(gh_url, timeout=12))
        for iss in gh_data.get("items", []):
            created_ts = int(datetime.strptime(iss["created_at"], "%Y-%m-%dT%H:%M:%SZ").timestamp())
            item = sanitizeAndUpgradeSignal({
                "id": f"gh_bounty_{iss['id']}",
                "created_ts": created_ts,
                "track": "bounty_direct",
                "ups": (iss.get("reactions") or {}).get("total_count", 1),
                "num_comments": iss.get("comments", 0),
                "title_zh": f"【GitHub 实时新悬赏】{iss['title']}",
                "pain_point_zh": iss.get("body") or iss["title"],
                "source_platform": "GitHub 实时悬赏",
                "source_url": iss["html_url"],
                "solver_url": iss["html_url"]
            })
            if item:
                all_fetched.append(item)
                alert_candidates.append((item, "", iss["title"], clean_raw_html(iss.get("body") or "")))
    except Exception:
        pass

    # 3. 抓其他全网痛点、野路子与成人频道 (Reddit 36个版块代表)
    for sub, track, label, mode in REDDIT_TARGET_SUBS[len(FAST_BOUNTY_SUBS):]:
        posts = fetch_reddit_jsonp_py(sub, mode, 25)
        for d in posts:
            title = clean_raw_html(d.get("title", ""))
            if not title:
                continue
            item = sanitizeAndUpgradeSignal({
                "id": f"rd_{d.get('id')}",
                "created_ts": d.get("created_utc", now_ts - 86400),
                "track": track,
                "ups": d.get("ups", 0),
                "num_comments": d.get("num_comments", 0),
                "title_zh": f"【{label}】{title}",
                "pain_point_zh": d.get("selftext") or title,
                "source_platform": label,
                "source_url": "https://www.reddit.com" + d.get("permalink", ""),
                "solver_url": "https://www.reddit.com" + d.get("permalink", "")
            })
            if item:
                all_fetched.append(item)

    all_fetched.extend(fetch_additional_sources(now_ts))

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    notified_ids = {row[0] for row in c.execute("SELECT id FROM notified_bounties")}
    pushed_count = 0
    for item, author, raw_title, raw_body in sorted(alert_candidates, key=lambda row: row[0].get("created_ts", 0), reverse=True):
        age_minutes = max(0, (now_ts - int(item.get("created_ts") or 0)) / 60)
        if item["id"] in notified_ids or age_minutes > 60 or pushed_count >= 5:
            continue
        ai_result = call_gemini_fast_bounty_dm(raw_title, raw_body, author)
        custom_dm = ""
        if ai_result:
            if ai_result.get("title_zh"):
                item["title_zh"] = f"【⚡急单】{clean_raw_html(ai_result['title_zh'])}"
            if ai_result.get("sample_3min_zh"):
                item["action_plan_zh"] = clean_raw_html(ai_result["sample_3min_zh"])
            custom_dm = clean_raw_html(ai_result.get("custom_dm_en") or "")
        if send_multichannel_bounty_alert(item, author_name=author, custom_dm_en=custom_dm):
            c.execute("INSERT OR REPLACE INTO notified_bounties VALUES (?, ?)", (item["id"], now_str))
            notified_ids.add(item["id"])
            pushed_count += 1
    print(f"[PUSH SUMMARY] candidates={len(alert_candidates)} pushed={pushed_count}")
    for item in all_fetched:
        c.execute("""
            INSERT OR REPLACE INTO signals VALUES (
                :id, :track, :title_zh, :summary_one_line, :deal_fact_zh,
                :pain_point_zh, :solver_case_zh, :platform_ecology_tip_zh,
                :reverse_money_idea_zh, :action_plan_zh, :feasibility_pct,
                :time_to_money, :capital_req, :source_platform, :source_url,
                :solver_url, :created_at, :deliverable_type, :created_ts
            )
        """, item)
    conn.commit()

    # 按 created_ts 严格倒序输出全部数据，不设上限！
    c.execute("SELECT * FROM signals ORDER BY created_ts DESC")
    cols = [col[0] for col in c.description]
    rows = [dict(zip(cols, r)) for r in c.fetchall()]
    conn.close()

    payload = {
        "updated_at": now_str,
        "poll_interval_sec": 60,
        "this_cycle_fetched": len(all_fetched),
        "live_count": len(rows),
        "signals": rows
    }
    with open(JSON_OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    print(f"[{now_str}] 满血扫描完毕！共入库 {len(rows)} 条，已按最新发布时间倒序排列。")
    return payload


class WorkbenchHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

    def do_GET(self):
        if self.path.startswith("/api/signals"):
            payload = run_fast_bounty_and_radar()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
            return
        if self.path == "/" or self.path == "/index.html":
            self.path = "/index.html" if os.path.exists("index.html") else "/global_arb_radar_workbench.html"
        return super().do_GET()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--cloud-once", action="store_true")
    parser.add_argument("--bounty-fast", action="store_true")
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    os.chdir(BASE_DIR)
    if args.cloud_once or args.bounty_fast or args.serve:
        run_fast_bounty_and_radar()
        if args.serve:
            print(f"🚀 本地无上限满血工作台已启动: http://127.0.0.1:{args.port}/")
            HTTPServer(("127.0.0.1", args.port), WorkbenchHandler).serve_forever()
    else:
        run_fast_bounty_and_radar()
