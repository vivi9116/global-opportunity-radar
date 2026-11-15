#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
全球痛点与真实赚钱机会 24h 自动监控引擎 (v11.2 全平台带盾穿透·悬赏2h自动清理版)
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
    ("webscraping", "bounty_direct", "Reddit r/webscraping (爬虫代抓与反爬求助)", "new"),
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
    ("affiliatemarketing", "gray_arb", "Reddit r/affiliatemarketing (CPA与联盟营销套利)", "top_month"),
    ("blackhat", "gray_arb", "Reddit r/blackhat (黑帽SEO与灰产技术热榜)", "top_month"),
    ("leadgeneration", "gray_arb", "Reddit r/leadgeneration (B2B灰产获客与名单倒卖)", "top_month"),
    ("SEO", "gray_arb", "Reddit r/SEO (搜索流量截流与寄生虫SEO)", "top_month"),
    ("bigseo", "gray_arb", "Reddit r/bigseo (高阶搜索套利与PBN矩阵)", "top_month"),
    ("juststart", "gray_arb", "Reddit r/juststart (流量站实战连载)", "top_month"),
    ("NSFWCreators", "nsfw_adult", "Reddit r/NSFWCreators (成人创作者变现)", "top_month"),
    ("onlyfansadvice", "nsfw_adult", "Reddit r/onlyfansadvice (OnlyFans私域引流)", "top_month"),
    ("CreatorsAdvice", "nsfw_adult", "Reddit r/CreatorsAdvice (擦边订阅制变现)", "top_month"),
    ("Fansly_Advice", "nsfw_adult", "Reddit r/Fansly_Advice (Fansly平台变现门道)", "top_month"),
    ("CamGirlProblems", "nsfw_adult", "Reddit r/CamGirlProblems (全球成人直播打赏门道)", "top_month"),
    ("Sexsells", "nsfw_adult", "Reddit r/Sexsells (成人内容C2C直卖热榜)", "top_month")
]

# 高防带盾域名清单（配置住宅 IP 或 SCRAPER_API_KEY 后自动启用穿透与轮换重试）
SHIELDED_DOMAINS = (
    "blackhatworld.com", "reddit.com", "etsy.com", "upwork.com",
    "f95zone.to", "affiliatefix.com", "g2.com", "trustpilot.com",
    "peopleperhour.com", "freelancer.com", "flippa.com", "dlsite.com"
)


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
        for raw_line in re.split(r"[\r\n,;]+", env_px):
            s = raw_line.strip()
            if s:
                proxies.append(s if "://" in s else f"http://{s}")
    if os.path.exists(PROXY_FILE):
        with open(PROXY_FILE, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                s = line.strip()
                if not s or s.startswith("#"):
                    continue
                if "://" in s:
                    proxies.append(s)
                else:
                    parts = s.split(":")
                    if len(parts) == 2:
                        proxies.append(f"http://{parts[0]}:{parts[1]}")
                    elif len(parts) >= 4:
                        proxies.append(f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}")
    return proxies


def http_get(url, timeout=16, headers=None):
    scraper_key = os.environ.get("SCRAPER_API_KEY", "").strip()
    is_shielded = any(d in url.lower() for d in SHIELDED_DOMAINS)
    proxies = load_proxies()

    max_attempts = 2 if (proxies and is_shielded) else 1
    last_err = None

    for attempt in range(max_attempts):
        target_url = url
        if scraper_key and is_shielded and not proxies:
            target_url = f"http://api.scraperapi.com?api_key={scraper_key}&render=false&url={urllib.parse.quote(url)}"

        chosen_proxy = random.choice(proxies) if proxies else None
        request_headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,ja;q=0.7",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache"
        }
        if headers:
            request_headers.update(headers)

        try:
            if HAS_CURL_CFFI:
                px_dict = {"http": chosen_proxy, "https": chosen_proxy} if chosen_proxy else None
                fp = random.choice(["chrome124", "chrome120", "safari17_0"])
                resp = cffi_requests.get(
                    target_url, impersonate=fp, headers=request_headers,
                    proxies=px_dict, timeout=timeout, allow_redirects=True
                )
                resp.raise_for_status()
                return resp.text

            req = urllib.request.Request(target_url, headers=request_headers)
            if chosen_proxy:
                opener = urllib.request.build_opener(urllib.request.ProxyHandler({"http": chosen_proxy, "https": chosen_proxy}))
            else:
                opener = urllib.request.build_opener()
            return opener.open(req, timeout=timeout).read().decode("utf-8", errors="ignore")
        except Exception as exc:
            last_err = exc
            continue
    raise last_err


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

    isBaseCard = str(rawItem.get("id", "")).startswith("base_")
    createdTs = int(rawItem.get("created_ts") or rawItem.get("created_utc") or time.time())
    # 悬赏单（bounty_direct）一旦超过 2 小时（7200秒），直接丢弃不入库
    if not isBaseCard and rawItem.get("track") == "bounty_direct":
        if (time.time() - createdTs) > 7200:
            return None

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


def is_direct_reddit_employer_post(sub, post):
    title = clean_raw_html(post.get("title") or "")
    if not title or post.get("crosspost_parent") or post.get("removed_by_category"):
        return False
    if re.search(r"\[offer\]|\[for\s*hire\]", title, re.I):
        return False
    if sub.lower() in {"slavelabour", "donedirtcheap"}:
        return bool(re.search(r"\[task\]", title, re.I))
    if sub.lower() in {"forhire", "hireaprogrammer", "freelance_forhire"}:
        return bool(re.search(r"\[(?:hiring|task)\]", title, re.I))
    return True


def _iso_timestamp(value, fallback):
    try:
        return int(datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp())
    except (TypeError, ValueError):
        return fallback


_GITHUB_REPO_CACHE = {}


def github_api_get(url, timeout=18):
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return json.loads(http_get(url, timeout=timeout, headers=headers))


def extract_markdown_section(markdown_text, heading_terms, max_chars=1800):
    lines = str(markdown_text or "").splitlines()
    captured = []
    active = False
    for line in lines:
        heading = re.match(r"^\s{0,3}#{1,6}\s+(.+?)\s*$", line)
        if heading:
            heading_text = clean_raw_html(heading.group(1)).lower()
            if active:
                break
            active = any(term.lower() in heading_text for term in heading_terms)
        if active:
            captured.append(line.rstrip())
    section = "\n".join(captured).strip()
    return section[:max_chars]


def verify_first_party_github_bounty(issue):
    if issue.get("pull_request") or issue.get("state") != "open":
        return None, "不是开放 Issue"

    repo_url = str(issue.get("repository_url") or "")
    repo_full_name = repo_url.split("/repos/", 1)[-1].strip("/")
    issue_number = int(issue.get("number") or 0)
    body = str(issue.get("body") or "")
    user = issue.get("user") or {}
    association = str(issue.get("author_association") or "").upper()

    if not repo_full_name or not issue_number:
        return None, "缺少原仓库地址"
    if user.get("type") == "Bot" or str(user.get("login") or "").lower().endswith("[bot]"):
        return None, "机器人发布"
    if association not in {"OWNER", "MEMBER", "COLLABORATOR"}:
        return None, f"发布者不是仓库维护者({association or 'NONE'})"
    if issue.get("assignees"):
        return None, "已经分配给他人"

    linked_issue_urls = re.findall(r"https://github\.com/([^/]+/[^/]+)/(?:issues|pull)/(\d+)", body, re.I)
    if any(linked_repo.lower() != repo_full_name.lower() for linked_repo, _ in linked_issue_urls):
        return None, "正文指向其他仓库原帖，属于转发"
    issue_title = str(issue.get("title") or "")
    relay_blob = f"{repo_full_name} {issue_title} {body[:800]}".lower()
    if re.search(r"bounty[-_ ]?bot|bounty encontrado|original bounty|mirrored from|aggregat(?:or|ed)", relay_blob):
        return None, "机器人/聚合转发"
    if re.search(r"bot[-_ ]?trap|ai\s+benchmark\s+arena", relay_blob):
        return None, "机器人诱捕/基准测试任务"
    if re.search(r"\[\s*\$0(?:\.0+)?\s*\]", issue_title, re.I):
        return None, "标题明确标注零赏金"

    try:
        repo = _GITHUB_REPO_CACHE.get(repo_full_name)
        if repo is None:
            repo = github_api_get(repo_url)
            _GITHUB_REPO_CACHE[repo_full_name] = repo
        repo_description = str(repo.get("description") or "").lower()
        if repo.get("archived") or repo.get("disabled") or repo.get("fork"):
            return None, "仓库已归档/停用或为 Fork"
        if re.search(r"bounty\s*(?:bot|aggregator|monitor)|aggregate.*bount", repo_description):
            return None, "仓库本身是悬赏聚合器"
    except Exception as exc:
        return None, f"仓库身份核验失败:{type(exc).__name__}"

    try:
        comments = github_api_get(f"{issue.get('comments_url')}?per_page=100") if issue.get("comments") else []
        timeline = github_api_get(f"{issue.get('timeline_url')}?per_page=100")
    except Exception as exc:
        return None, f"评论/Timeline核验失败:{type(exc).__name__}"

    for event in timeline if isinstance(timeline, list) else []:
        related = ((event.get("source") or {}).get("issue") or {})
        if related.get("pull_request"):
            pr_state = str(related.get("state") or "").lower()
            merged_at = (related.get("pull_request") or {}).get("merged_at")
            if pr_state == "open" or merged_at:
                return None, f"已有关联 PR #{related.get('number')}"

    comment_texts = [str(comment.get("body") or "") for comment in comments if isinstance(comment, dict)]
    all_comments = "\n".join(comment_texts)
    busy_pattern = re.compile(
        r"\b(?:queued|filled|claimed|taken|first[- ]in[- ]line|already\s+passed|awaiting\s+(?:founder\s+)?merge|"
        r"pr\s*#\d+[^\n]{0,100}(?:open|submitted|passed|queued|review))\b",
        re.I,
    )
    if busy_pattern.search(all_comments):
        return None, "最新评论显示已认领/排队/已有通过测试的PR"

    latest_maintainer_comment = ""
    for comment in reversed(comments if isinstance(comments, list) else []):
        if str(comment.get("author_association") or "").upper() in {"OWNER", "MEMBER", "COLLABORATOR"}:
            latest_maintainer_comment = str(comment.get("body") or "")
            break

    objective = extract_markdown_section(body, ["objective", "goal", "任务目标"])
    checklist = extract_markdown_section(body, ["required pr submission checklist", "submission checklist", "requirements"])
    fixture_section = extract_markdown_section(all_comments, ["submission & fixture path", "fixture path", "submission path"])
    fixture_lines = []
    for line in f"{body}\n{all_comments}".splitlines():
        if re.search(r"bounties/submissions/|verify_bounty_submission\.py|submission\s*&\s*fixture\s*path", line, re.I):
            cleaned = line.strip()
            if cleaned and cleaned not in fixture_lines:
                fixture_lines.append(cleaned)
    fixture_text = fixture_section or "\n".join(fixture_lines[:8])
    if not objective:
        objective = body[:1200]

    copy_pack = (
        f"【Objective｜核心任务目标】\n{objective}\n\n"
        f"【Required PR Submission Checklist｜提交格式】\n{checklist or '原帖没有单独的 Checklist 标题，请打开原帖按完整要求执行。'}\n\n"
        f"【Submission & Fixture Path｜文件路径与验证命令】\n{fixture_text or '原帖及最新评论未给出单独的 Fixture Path。'}"
    )
    latest_context = clean_raw_html(latest_maintainer_comment)[:700] or "维护者最新评论未出现 assigned / queued / filled / 已有通过测试 PR。"
    return {
        "issue": issue,
        "repo_full_name": repo_full_name,
        "copy_pack": copy_pack,
        "latest_context": latest_context,
        "author": str(user.get("login") or ""),
        "comments": comments,
    }, "一手原帖已核验"


def fetch_additional_sources(now_ts):
    items = []
    thirty_days_ago_ts = now_ts - (30 * 86400)

    # 1. Hacker News 近30天痛点、变现、灰产与成人全量搜索
    hn_queries = [
        ("willing to pay OR too expensive alternative", "pain_saas", "HN 近30天痛点求平替"),
        ("Show HN revenue OR MRR OR first sale OR Stripe", "pain_saas", "HN 近30天真实变现复盘"),
        ("affiliate OR arbitrage OR SEO OR lead generation", "gray_arb", "HN 近30天流量套利门道"),
        ("OnlyFans OR NSFW OR adult OR AI companion", "nsfw_adult", "HN 成人与AI伴侣变现")
    ]
    for query, trk, label in hn_queries:
        try:
            url = f"https://hn.algolia.com/api/v1/search?tags=story&numericFilters=created_at_i>{thirty_days_ago_ts},points>2&hitsPerPage=35&query=" + urllib.parse.quote(query)
            data = json.loads(http_get(url, timeout=15))
            for hit in data.get("hits", []):
                object_id = str(hit.get("objectID") or "")
                title = clean_raw_html(hit.get("title") or hit.get("story_title") or "")
                if not object_id or not title:
                    continue
                item = sanitizeAndUpgradeSignal({
                    "id": f"hn_{object_id}", "created_ts": int(hit.get("created_at_i") or (now_ts - 3600)),
                    "track": trk, "ups": hit.get("points") or 0, "num_comments": hit.get("num_comments") or 0,
                    "title_zh": f"【{label}】{title}", "pain_point_zh": hit.get("story_text") or title,
                    "source_platform": label, "source_url": hit.get("url") or f"https://news.ycombinator.com/item?id={object_id}",
                    "solver_url": f"https://news.ycombinator.com/item?id={object_id}",
                })
                if item:
                    items.append(item)
        except Exception as exc:
            print(f"[SOURCE WARN] HN {query}: {exc}")

    # 2. Reddit 全站关键词主动搜索引擎（专抓近1个月全球怎么赚钱、CPA、黑帽、成人引流）
    reddit_global_searches = [
        ("CPA marketing OR content locker OR OGAds OR AdBlueMedia", "gray_arb", "全网搜索·CPA与任务锁门道"),
        ("CrakRevenue OR adult affiliate OR Fanvue OR AI NSFW", "nsfw_adult", "全网搜索·成人CPA与AI擦边"),
        ("parasite SEO OR blackhat SEO OR expired domains", "gray_arb", "全网搜索·黑帽寄生虫SEO"),
        ("how I made $ OR made my first $1000 OR side hustle worked", "pain_saas", "全网搜索·近30天亲测赚钱复盘"),
        ("TikTok shop affiliate OR Etsy digital product OR Gumroad", "gray_arb", "全网搜索·短视频带货与虚拟品套利")
    ]
    for q_str, trk, label in reddit_global_searches:
        try:
            s_url = f"https://www.reddit.com/search.json?q={urllib.parse.quote(q_str)}&sort=top&t=month&limit=35&raw_json=1"
            s_data = json.loads(http_get(s_url, timeout=14))
            for child in s_data.get("data", {}).get("children", []):
                d = child.get("data", {})
                title = clean_raw_html(d.get("title", ""))
                if not title:
                    continue
                item = sanitizeAndUpgradeSignal({
                    "id": f"rds_{d.get('id')}", "created_ts": int(d.get("created_utc") or (now_ts - 7200)),
                    "track": trk, "ups": d.get("ups", 0), "num_comments": d.get("num_comments", 0),
                    "title_zh": f"【{label} · r/{d.get('subreddit')}】{title}",
                    "pain_point_zh": d.get("selftext") or title,
                    "source_platform": label,
                    "source_url": "https://www.reddit.com" + d.get("permalink", ""),
                    "solver_url": "https://www.reddit.com" + d.get("permalink", "")
                })
                if item:
                    items.append(item)
        except Exception as exc:
            print(f"[SOURCE WARN] Reddit Search {label}: {exc}")

    # 3. V2EX 外包与酷工作急单 (超过2小时会在 sanitizeAndUpgradeSignal 中被自动过滤)
    for node in ("jobs", "outsourcing"):
        try:
            data = json.loads(http_get(f"https://www.v2ex.com/api/topics/show.json?node_name={node}", timeout=15))
            for topic in data:
                topic_id = str(topic.get("id") or "")
                title = clean_raw_html(topic.get("title") or "")
                if not topic_id or not title:
                    continue
                direct_post_blob = f"{title} {clean_raw_html(topic.get('content') or '')}"
                if re.search(r"转载|转发|代发|猎头|中介|职位汇总", direct_post_blob, re.I):
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
        except Exception as exc:
            print(f"[SOURCE WARN] V2EX {node}: {exc}")

    # 4. 【带盾高防】BlackHatWorld 6大核心分版 (RSS + HTML 双通道穿透，配住宅IP后满血)
    bhw_forums = [
        ("cpa", "cpa.24", "gray_arb", "BlackHatWorld CPA任务锁"),
        ("affiliate", "affiliate-programs.15", "gray_arb", "BlackHatWorld 联盟营销"),
        ("making_money", "making-money.12", "gray_arb", "BlackHatWorld 野路子搞钱"),
        ("journey", "my-journey-discussions.167", "gray_arb", "BlackHatWorld 实盘连载"),
        ("blackhat_seo", "black-hat-seo.28", "gray_arb", "BlackHatWorld 黑帽SEO"),
        ("hire", "hire-a-freelancer.76", "bounty_direct", "BlackHatWorld 雇主急单")
    ]
    for kind, forum, track, bhw_label in bhw_forums:
        try:
            feed_url = f"https://www.blackhatworld.com/forums/{forum}/index.rss"
            soup = BeautifulSoup(http_get(feed_url, timeout=18), "xml")
            bhw_count = 0
            for entry in soup.find_all(["entry", "item"])[:25]:
                title_node = entry.find("title")
                link_node = entry.find("link")
                title = clean_raw_html(title_node.get_text(" ", strip=True) if title_node else "")
                source_url = (link_node.get("href") if link_node and link_node.has_attr("href") else link_node.get_text(strip=True) if link_node else "")
                content_node = entry.find("content") or entry.find("description") or entry.find("summary")
                body = clean_raw_html(content_node.decode_contents() if content_node else "")
                date_node = entry.find("updated") or entry.find("published") or entry.find("pubDate")
                entry_ts = _iso_timestamp(date_node.get_text(strip=True) if date_node else "", now_ts - 1800)
                if not title or not source_url:
                    continue
                if kind == "hire" and not re.search(r"\b(?:WTB|hiring|looking\s+for|need|wanted)\b", title, re.I):
                    continue
                item = sanitizeAndUpgradeSignal({
                    "id": f"bhw_{kind}_{abs(hash(source_url))}", "created_ts": entry_ts, "track": track,
                    "title_zh": f"【{bhw_label}】{title}", "pain_point_zh": body,
                    "source_platform": bhw_label, "source_url": source_url, "solver_url": source_url,
                })
                if item:
                    items.append(item)
                    bhw_count += 1
            if bhw_count == 0:
                forum_url = f"https://www.blackhatworld.com/forums/{forum}/"
                page = BeautifulSoup(http_get(forum_url, timeout=18), "lxml")
                for row in page.select(".structItem--thread")[:25]:
                    anchor = row.select_one('.structItem-title a[data-tp-primary="on"]') or row.select_one('.structItem-title a[href*="/threads/"]')
                    if not anchor:
                        continue
                    title = clean_raw_html(anchor.get_text(" ", strip=True))
                    source_url = urllib.parse.urljoin(forum_url, anchor.get("href", ""))
                    body = clean_raw_html(row.get_text(" ", strip=True))
                    time_node = row.select_one("time.u-dt")
                    entry_ts = int(time_node.get("data-time")) if (time_node and time_node.get("data-time")) else (now_ts - 1800)
                    if kind == "hire" and not re.search(r"\b(?:WTB|hiring|looking\s+for|need|wanted)\b", title, re.I):
                        continue
                    item = sanitizeAndUpgradeSignal({
                        "id": f"bhw_{kind}_{abs(hash(source_url))}", "created_ts": entry_ts, "track": track,
                        "title_zh": f"【{bhw_label}】{title}", "pain_point_zh": body,
                        "source_platform": bhw_label, "source_url": source_url, "solver_url": source_url,
                    })
                    if item:
                        items.append(item)
        except Exception as exc:
            print(f"[SOURCE WARN] {bhw_label}: {exc}")

    # 5. 【带盾高防】AffiliateFix (全球顶级 CPA / 成人联盟 / Media Buy 论坛)
    for af_path, af_label in (("whats-new/posts/", "AffiliateFix CPA最新实战"), ("forums/cpa-affiliate-networks.9/", "AffiliateFix CPA联盟网赚")):
        try:
            af_url = f"https://www.affiliatefix.com/{af_path}"
            page = BeautifulSoup(http_get(af_url, timeout=18), "lxml")
            for row in page.select(".structItem--thread")[:25]:
                anchor = row.select_one('.structItem-title a[href*="/threads/"]')
                if not anchor:
                    continue
                title = clean_raw_html(anchor.get_text(" ", strip=True))
                source_url = urllib.parse.urljoin("https://www.affiliatefix.com", anchor.get("href", ""))
                body = clean_raw_html(row.get_text(" ", strip=True))
                item = sanitizeAndUpgradeSignal({
                    "id": f"afffix_{abs(hash(source_url))}", "created_ts": now_ts - 3600, "track": "gray_arb",
                    "title_zh": f"【{af_label}】{title}", "pain_point_zh": body,
                    "source_platform": af_label, "source_url": source_url, "solver_url": source_url,
                })
                if item:
                    items.append(item)
        except Exception as exc:
            print(f"[SOURCE WARN] {af_label}: {exc}")

    # 6. 【带盾高防】Upwork / PeoplePerHour / Freelancer.com 全球外包实时悬赏急单 (仅保留2小时内新单)
    freelance_targets = [
        ("https://www.peopleperhour.com/freelance-jobs?sort=latest", "PeoplePerHour 实时悬赏急单", ".job-list-item, [class*='item__container']"),
        ("https://www.freelancer.com/jobs/?sort=latest", "Freelancer.com 实时外包急单", ".JobSearchCard-item"),
        ("https://www.upwork.com/nx/search/jobs/?q=python%20scrape%20OR%20automation%20OR%20excel&sort=recency", "Upwork 实时最新急单", "article, [data-test='JobTile']")
    ]
    for fl_url, fl_label, css_sel in freelance_targets:
        try:
            page = BeautifulSoup(http_get(fl_url, timeout=18), "lxml")
            for card in page.select(css_sel)[:25]:
                anchor = card.select_one("a[href]")
                if not anchor:
                    continue
                title = clean_raw_html(anchor.get_text(" ", strip=True))
                source_url = urllib.parse.urljoin(fl_url, anchor.get("href", ""))
                body = clean_raw_html(card.get_text(" ", strip=True))
                if len(title) < 6:
                    continue
                item = sanitizeAndUpgradeSignal({
                    "id": f"fl_{abs(hash(source_url))}", "created_ts": now_ts - 600, "track": "bounty_direct",
                    "title_zh": f"【{fl_label}】{title}", "pain_point_zh": body,
                    "source_platform": fl_label, "source_url": source_url, "solver_url": source_url,
                })
                if item:
                    items.append(item)
        except Exception as exc:
            print(f"[SOURCE WARN] {fl_label}: {exc}")

    # 7. 【带盾+免盾全覆盖】全球成人暴利矩阵：F95zone + DLsite 3大榜 + Chaturbate + Itch.io NSFW
    try:
        f95_url = "https://f95zone.to/sam/latest_alpha/"
        f95_soup = BeautifulSoup(http_get(f95_url, timeout=18), "lxml")
        for row in f95_soup.select("a[href*='/threads/']")[:25]:
            title = clean_raw_html(row.get_text(" ", strip=True))
            if len(title) < 8:
                continue
            source_url = urllib.parse.urljoin("https://f95zone.to", row.get("href", ""))
            item = sanitizeAndUpgradeSignal({
                "id": f"f95_{abs(hash(source_url))}", "created_ts": now_ts - 2400, "track": "nsfw_adult",
                "title_zh": f"【F95zone 全球成人游戏/Mod实时热榜】{title}",
                "pain_point_zh": f"欧美最大成人游戏与3D同人社区 F95zone 实时更新热帖：{title}（极适合提取热门人设做 Patreon / OGAds 内容锁或汉化倒卖）",
                "source_platform": "F95zone 成人游戏社区", "source_url": source_url, "solver_url": source_url,
            })
            if item:
                items.append(item)
    except Exception as exc:
        print(f"[SOURCE WARN] F95zone: {exc}")

    dlsite_boards = [
        ("https://www.dlsite.com/maniax/ranking/day?sort=sale&order=desc", "DLsite R18 同人日榜"),
        ("https://www.dlsite.com/maniax/ranking/month?sort=sale&order=desc", "DLsite R18 近30天月销榜"),
        ("https://www.dlsite.com/books/ranking/month?sort=sale&order=desc", "DLsite R18 成人漫画月榜")
    ]
    for dl_url, dl_label in dlsite_boards:
        try:
            soup = BeautifulSoup(http_get(dl_url, timeout=18), "lxml")
            for row in soup.select("table.ranking_worklist tr")[:25]:
                links = [a for a in row.select("a[href*='/work/=/product_id/']") if "btn_free_sample" not in (a.get("class") or []) and a.get_text(" ", strip=True)]
                if not links:
                    continue
                anchor = links[0]
                title = clean_raw_html(anchor.get_text(" ", strip=True))
                source_url = urllib.parse.urljoin(dl_url, anchor.get("href", ""))
                body = clean_raw_html(row.get_text(" ", strip=True))
                product_match = re.search(r"/product_id/([^/.]+)", source_url)
                product_id = product_match.group(1) if product_match else str(abs(hash(source_url)))
                item = sanitizeAndUpgradeSignal({
                    "id": f"dlsite_{product_id}", "created_ts": now_ts - 3600, "track": "nsfw_adult",
                    "title_zh": f"【{dl_label}】{title}", "pain_point_zh": body,
                    "deal_fact_zh": extract_honest_deal_fact(body), "source_platform": dl_label,
                    "source_url": source_url, "solver_url": source_url,
                })
                if item:
                    items.append(item)
        except Exception as exc:
            print(f"[SOURCE WARN] {dl_label}: {exc}")

    wm = os.environ.get("CHATURBATE_WM", "Z1n2p").strip() or "Z1n2p"
    try:
        cb_url = f"https://chaturbate.com/affiliates/api/onlinerooms/?format=json&wm={urllib.parse.quote(wm)}"
        data = json.loads(http_get(cb_url, timeout=15))
        rooms = data.get("results", []) if isinstance(data, dict) else data
        top_rooms = sorted(rooms, key=lambda x: int(x.get("num_users") or 0), reverse=True)[:50]
        for room in top_rooms:
            username = str(room.get("username") or "")
            if not username:
                continue
            viewers = int(room.get("num_users") or 0)
            tags = " / ".join((room.get("tags") or [])[:5])
            source_url = room.get("chat_room_url") or f"https://chaturbate.com/{username}/"
            item = sanitizeAndUpgradeSignal({
                "id": f"cb_{username}", "created_ts": now_ts - 1200, "track": "nsfw_adult", "ups": viewers,
                "title_zh": f"【Chaturbate 全球成人直播榜 #{username}】当前 {viewers} 人在线打赏 (热搜标签: {tags})",
                "pain_point_zh": f"当前直播间实时在线 {viewers} 人；高转化细分癖好标签：{tags}",
                "deal_fact_zh": f"✅ 官方API实时在线打赏金主：{viewers} 人", "source_platform": "Chaturbate 成人直播榜",
                "source_url": source_url, "solver_url": source_url,
            })
            if item:
                items.append(item)
    except Exception as exc:
        print(f"[SOURCE WARN] Chaturbate: {exc}")

    try:
        itch_rss = "https://itch.io/games/top-sellers/tag-nsfw.xml"
        soup = BeautifulSoup(http_get(itch_rss, timeout=15), "xml")
        for entry in soup.find_all("item")[:25]:
            title = clean_raw_html(entry.find("title").get_text(" ", strip=True) if entry.find("title") else "")
            link = clean_raw_html(entry.find("link").get_text(" ", strip=True) if entry.find("link") else "")
            desc = clean_raw_html(entry.find("description").get_text(" ", strip=True) if entry.find("description") else "")
            if not title or not link:
                continue
            item = sanitizeAndUpgradeSignal({
                "id": f"itch_nsfw_{abs(hash(link))}", "created_ts": now_ts - 4800, "track": "nsfw_adult",
                "title_zh": f"【Itch.io 欧美成人游戏畅销榜】{title}", "pain_point_zh": desc,
                "deal_fact_zh": "✅ 欧美 Itch.io Top Sellers 成人畅销榜在榜作品",
                "source_platform": "Itch.io NSFW 畅销榜", "source_url": link, "solver_url": link,
            })
            if item:
                items.append(item)
    except Exception as exc:
        print(f"[SOURCE WARN] Itch.io NSFW: {exc}")

    # 8. 【带盾高防】Etsy 暴利虚拟品 / Trustpilot 软件差评池 / Flippa 赚钱网站交易池
    shielded_biz_targets = [
        ("https://www.etsy.com/search?q=digital+planner+template&explicit=1&order=most_relevant", "pain_saas", "Etsy 畅销虚拟品套利", "a.listing-link"),
        ("https://www.trustpilot.com/categories/software_company?sort=latest_review", "pain_saas", "Trustpilot 软件痛点差评池", "a[name='business-unit-card']"),
        ("https://flippa.com/search?filter[property_type]=saas,website&filter[revenue_generating]=T", "gray_arb", "Flippa 已验证月入美金站点池", "a[href*='flippa.com/']")
    ]
    for sb_url, sb_track, sb_label, sb_sel in shielded_biz_targets:
        try:
            page = BeautifulSoup(http_get(sb_url, timeout=18), "lxml")
            for node in page.select(sb_sel)[:20]:
                title = clean_raw_html(node.get_text(" ", strip=True))
                href = node.get("href", "")
                if len(title) < 6 or not href:
                    continue
                source_url = urllib.parse.urljoin(sb_url, href)
                item = sanitizeAndUpgradeSignal({
                    "id": f"sb_{abs(hash(source_url))}", "created_ts": now_ts - 5000, "track": sb_track,
                    "title_zh": f"【{sb_label}】{title[:90]}", "pain_point_zh": title,
                    "source_platform": sb_label, "source_url": source_url, "solver_url": source_url,
                })
                if item:
                    items.append(item)
        except Exception as exc:
            print(f"[SOURCE WARN] {sb_label}: {exc}")

    # 9. DEV.to 近30天独立开发与自动化变现热榜
    for dtag in ("saas", "sideprojects", "indiehackers", "automation"):
        try:
            dev_data = json.loads(http_get(f"https://dev.to/api/articles?tag={dtag}&top=30&per_page=30", timeout=12))
            for art in dev_data:
                title = clean_raw_html(art.get("title") or "")
                if not title:
                    continue
                item = sanitizeAndUpgradeSignal({
                    "id": f"dev_{art.get('id')}", "created_ts": _iso_timestamp(art.get("published_at"), now_ts - 86400),
                    "track": "pain_saas", "ups": art.get("public_reactions_count") or 0, "num_comments": art.get("comments_count") or 0,
                    "title_zh": f"【DEV.to 近30天变现热榜 #{dtag}】{title}",
                    "pain_point_zh": clean_raw_html(art.get("description") or title),
                    "source_platform": f"DEV.to #{dtag}", "source_url": art.get("url"), "solver_url": art.get("url"),
                })
                if item:
                    items.append(item)
        except Exception as exc:
            print(f"[SOURCE WARN] DEV.to {dtag}: {exc}")

    return items


def run_fast_bounty_and_radar():
    init_db()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    now_ts = int(time.time())
    all_fetched = []
    alert_candidates = []

    print(f"[{now_str}] 🚀 正在执行满血 65+ 频道全网扫描 (悬赏限定2h内并按最新倒序)...")

    # 1. 抓快轨悬赏急单
    for sub, track, label in FAST_BOUNTY_SUBS:
        posts = fetch_reddit_jsonp_py(sub, "new", 30)
        for d in posts:
            title = clean_raw_html(d.get("title", ""))
            if not is_direct_reddit_employer_post(sub, d):
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

    # 2. 抓 GitHub 一手实时悬赏（限定过去 2 小时内新开，并核验最新评论、认领状态与关联 PR）
    github_scan_complete = False
    current_github_ids = set()
    try:
        two_hours_ago = (datetime.utcnow() - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
        gh_query = f"is:issue is:open label:bounty created:>={two_hours_ago}"
        gh_url = "https://api.github.com/search/issues?" + urllib.parse.urlencode({
            "q": gh_query, "sort": "created", "order": "desc", "per_page": 100,
        })
        gh_data = github_api_get(gh_url)
        gh_rejected = {}
        gh_accepted = 0
        for iss in gh_data.get("items", []):
            verified, reason = verify_first_party_github_bounty(iss)
            if not verified:
                gh_rejected[reason] = gh_rejected.get(reason, 0) + 1
                continue
            created_ts = int(datetime.strptime(iss["created_at"], "%Y-%m-%dT%H:%M:%SZ").timestamp())
            copy_pack = verified["copy_pack"]
            latest_context = verified["latest_context"]
            deal_fact = extract_honest_deal_fact(f"{iss['title']} {iss.get('body') or ''}", (iss.get("reactions") or {}).get("total_count", 0), iss.get("comments", 0))
            item = sanitizeAndUpgradeSignal({
                "id": f"gh_bounty_{iss['id']}",
                "created_ts": created_ts,
                "track": "bounty_direct",
                "ups": (iss.get("reactions") or {}).get("total_count", 1),
                "num_comments": iss.get("comments", 0),
                "title_zh": f"【GitHub 一手悬赏·已查评论/PR】{iss['title']}",
                "deal_fact_zh": f"{deal_fact} | ✅ 一手维护者原帖，当前无 Assignee、无关联在做 PR、无 queued/filled",
                "pain_point_zh": iss.get("body") or iss["title"],
                "source_platform": "GitHub 一手悬赏（已查评论/PR）",
                "source_url": iss["html_url"],
                "solver_url": iss["html_url"]
            })
            if item:
                item["summary_one_line"] = "一手维护者原帖；已检查最新评论、Assignee 与关联 PR"
                item["pain_point_zh"] = f"【一手状态核验】{latest_context}\n\n{copy_pack}"
                item["action_plan_zh"] = copy_pack
                item["platform_ecology_tip_zh"] = "⚡ 已自动检查原帖最底部最新评论、Assignee 和 Timeline 关联 PR；发现 assigned、queued、filled、claimed、在做 PR 或已通过测试即剔除，不推送。"
                all_fetched.append(item)
                current_github_ids.add(item["id"])
                alert_body = f"{copy_pack}\n\n【维护者最新评论】\n{latest_context}"
                alert_candidates.append((item, verified["author"], iss["title"], alert_body))
                gh_accepted += 1
        github_scan_complete = True
        print(f"[GITHUB PRIMARY] examined={len(gh_data.get('items', []))} accepted={gh_accepted} rejected={sum(gh_rejected.values())} reasons={gh_rejected}")
    except Exception as exc:
        print(f"[SOURCE WARN] GitHub 一手悬赏: {type(exc).__name__}: {exc}")

    # 3. 抓其他全网痛点、CPA、灰产野路子与多平台成人频道
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
                ai_action = clean_raw_html(ai_result["sample_3min_zh"])
                if item.get("source_platform", "").startswith("GitHub 一手悬赏"):
                    item["action_plan_zh"] = f"{item['action_plan_zh']}\n\n【Gemini 3分钟执行建议】\n{ai_action}"
                else:
                    item["action_plan_zh"] = ai_action
            custom_dm = clean_raw_html(ai_result.get("custom_dm_en") or "")
        if send_multichannel_bounty_alert(item, author_name=author, custom_dm_en=custom_dm):
            c.execute("INSERT OR REPLACE INTO notified_bounties VALUES (?, ?)", (item["id"], now_str))
            notified_ids.add(item["id"])
            pushed_count += 1
    print(f"[PUSH SUMMARY] candidates={len(alert_candidates)} pushed={pushed_count}")

    # 自动从数据库删除所有已经超过 2 小时（7200秒）的悬赏急单！
    c.execute("DELETE FROM signals WHERE track = 'bounty_direct' AND id NOT LIKE 'base_%' AND created_ts < ?", (now_ts - 7200,))

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

    c.execute("SELECT * FROM signals ORDER BY created_ts DESC")
    cols = [col[0] for col in c.description]
    rows = [dict(zip(cols, r)) for r in c.fetchall()]
    rows = [
        row for row in rows
        if not str(row.get("source_platform") or "").startswith("GitHub")
        or (
            str(row.get("source_platform") or "").startswith("GitHub 一手悬赏")
            and (not github_scan_complete or row.get("id") in current_github_ids)
        )
    ]
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
    print(f"[{now_str}] 满血扫描完毕！共入库 {len(rows)} 条（超2h旧悬赏已自动清理），已按最新发布时间倒序排列。")
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
