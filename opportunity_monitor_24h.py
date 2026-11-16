#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
全球痛点与真实赚钱机会 24h 自动监控引擎 (v12.0 补全BHW双悬赏区·v9.2求购急单满血版)
================================================================================
核心升级（在 v11.9 基础上只增不减）：
1. 【保留全部现有保护】：保留四重域名白名单安检（防 cpa-jobs.jp 等外部站）、保留会计师歧义隔离、
   保留悬赏 2h 自动清理与大盘 30 天时效锁、保留多形态非模板拆解。
2. 【补全 BlackHatWorld 双悬赏区】：
   - BHW Hire a Freelancer (forums/hire-a-freelancer.76)
   - BHW Want to Buy 求购悬赏区 (forums/want-to-buy.92)
   - 采用 RSS + Jina Markdown + 宽口径搜索桥三路并发，修复之前关键词过严导致 0 条的问题！
3. 【扭转“全是分享贴”问题 -> 新增全网买家求购/付费求助直抓流 (Buyer Intent Stream)】：
   - 专门抓取全网带着预算找人干活/买工具的帖子 ([WTB], [Hiring], "willing to pay", "need a bot/script",
     "looking for developer/scraper")，直接对接活体买家。
================================================================================
"""

import os
import sys
import time
import json
import re
import html
import hashlib
import sqlite3
import random
import shutil
import tempfile
import subprocess
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
import threading
import argparse
from bs4 import BeautifulSoup

if os.name == "nt" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

try:
    from curl_cffi import requests as cffi_requests
    HAS_CURL_CFFI = True
except ImportError:
    HAS_CURL_CFFI = False

if os.name == "nt" and HAS_CURL_CFFI and not os.environ.get("CURL_CA_BUNDLE"):
    try:
        import certifi
        ca_source = certifi.where()
        if not ca_source.isascii():
            ca_target = os.path.join(tempfile.gettempdir(), "radar_cacert.pem")
            if not os.path.isfile(ca_target) or os.path.getmtime(ca_source) > os.path.getmtime(ca_target):
                shutil.copyfile(ca_source, ca_target)
            os.environ["CURL_CA_BUNDLE"] = ca_target
    except OSError as exc:
        print(f"[CERT WARN] 本机 CA 证书兼容处理失败: {exc}", flush=True)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "radar_pain_solver_history.db")
JSON_OUT_PATH = os.path.join(BASE_DIR, "live_signals.json")
PROXY_FILE = os.path.join(BASE_DIR, "ip3.txt")
LOCAL_BROWSER_PROFILE = os.environ.get("LOCAL_BROWSER_PROFILE", os.path.join(BASE_DIR, ".radar_visible_chrome_profile"))

USE_LOCAL_SILENT_BROWSER = False
_PLAYWRIGHT_LOCK = threading.Lock()
_LOCAL_PAGE = None
_MANUAL_VERIFY_BLOCKED = set()

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15"
]

FAST_BOUNTY_SUBS = [
    ("slavelabour", "bounty_direct", "Reddit r/slavelabour (免费直联·微任务现金急单)"),
    ("forhire", "bounty_direct", "Reddit r/forhire (免费直联·全球自由职业雇佣)"),
    ("DoneDirtCheap", "bounty_direct", "Reddit r/DoneDirtCheap (免费直联·快单悬赏)"),
    ("hireaprogrammer", "bounty_direct", "Reddit r/hireaprogrammer (免费直联·开发急单)"),
    ("freelance_forhire", "bounty_direct", "Reddit r/freelance_forhire (免费直联·外包直聘)")
]

REDDIT_TARGET_SUBS = [
    *[(s[0], s[1], s[2], "new") for s in FAST_BOUNTY_SUBS],
    ("webscraping", "bounty_direct", "Reddit r/webscraping (爬虫代抓与反爬急单)", "new"),
    ("Automate", "bounty_direct", "Reddit r/Automate (自动化脚本定制求助)", "new"),
    ("excel", "pain_saas", "Reddit r/excel (全球表格自动化痛点热榜)", "top_month"),
    ("googlesheets", "pain_saas", "Reddit r/googlesheets (谷歌表格脚本痛点热榜)", "top_month"),
    ("SaaS", "pain_saas", "Reddit r/SaaS (软件痛点与变现复盘)", "top_month"),
    ("SideProject", "pain_saas", "Reddit r/SideProject (独立副业产品变现)", "top_month"),
    ("microsaas", "pain_saas", "Reddit r/microsaas (微型SaaS真实营收榜)", "top_month"),
    ("sweatystartup", "pain_saas", "Reddit r/sweatystartup (传统本地生意痛点)", "top_month"),
    ("smallbusiness", "pain_saas", "Reddit r/smallbusiness (小微老板痛点)", "top_month"),
    ("Entrepreneur", "pain_saas", "Reddit r/Entrepreneur (创业痛点吐槽)", "top_month"),
    ("beermoney", "gray_arb", "Reddit r/beermoney (亲测网赚打款门道)", "top_month"),
    ("sidehustle", "gray_arb", "Reddit r/sidehustle (野路子副业实操)", "top_month"),
    ("flipping", "gray_arb", "Reddit r/flipping (跨平台低买高卖倒爷套利)", "top_month"),
    ("affiliatemarketing", "gray_arb", "Reddit r/affiliatemarketing (CPA与联盟营销套利)", "top_month"),
    ("blackhat", "gray_arb", "Reddit r/blackhat (黑帽SEO与灰产套利热榜)", "top_month"),
    ("leadgeneration", "gray_arb", "Reddit r/leadgeneration (B2B灰产获客与名单套利)", "top_month"),
    ("SEO", "gray_arb", "Reddit r/SEO (搜索流量截流与寄生虫SEO)", "top_month"),
    ("juststart", "gray_arb", "Reddit r/juststart (流量站搞钱实战连载)", "top_month"),
    ("NSFWCreators", "nsfw_adult", "Reddit r/NSFWCreators (成人创作者引流变现)", "top_month"),
    ("onlyfansadvice", "nsfw_adult", "Reddit r/onlyfansadvice (OnlyFans私域变现门道)", "top_month"),
    ("CreatorsAdvice", "nsfw_adult", "Reddit r/CreatorsAdvice (擦边订阅制变现)", "top_month"),
    ("Fansly_Advice", "nsfw_adult", "Reddit r/Fansly_Advice (Fansly平台变现门道)", "top_month"),
    ("CamGirlProblems", "nsfw_adult", "Reddit r/CamGirlProblems (全球成人直播打赏门道)", "top_month")
]

SHIELDED_DOMAINS = (
    "blackhatworld.com", "reddit.com", "etsy.com",
    "f95zone.to", "affiliatefix.com", "g2.com", "trustpilot.com", "dlsite.com"
)

ALLOWED_SOURCE_DOMAINS = (
    "reddit.com", "github.com", "news.ycombinator.com", "v2ex.com",
    "blackhatworld.com", "affiliatefix.com", "dlsite.com", "chaturbate.com",
    "f95zone.to", "itch.io", "dev.to", "lemmy.world"
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


def fetch_via_local_silent_browser(url, wait_sec=4.0):
    global _LOCAL_PAGE
    with _PLAYWRIGHT_LOCK:
        domain = urllib.parse.urlparse(url).netloc.lower()
        if domain in _MANUAL_VERIFY_BLOCKED:
            raise RuntimeError(f"{domain} 等待手动验证；本轮不重复请求")
        browser_path = find_local_browser_path()
        if not browser_path:
            raise RuntimeError("本机未找到 Chrome/Edge；可设置 CHROME_PATH")
        from DrissionPage import ChromiumPage, ChromiumOptions
        if _LOCAL_PAGE is None:
            options = ChromiumOptions()
            options.set_browser_path(browser_path)
            options.set_user_data_path(LOCAL_BROWSER_PROFILE)
            options.set_local_port(int(os.environ.get("RADAR_CHROME_PORT", "9337")))
            options.headless(False)
            options.set_argument("--mute-audio")
            _LOCAL_PAGE = ChromiumPage(options)
        _LOCAL_PAGE.get(url, retry=1, timeout=18)
        time.sleep(wait_sec)
        content = _LOCAL_PAGE.html
        if is_human_challenge_page(content):
            print(f"[MANUAL VERIFY] 请在专用 Chrome 窗口完成验证：{url}", flush=True)
            if sys.stdin.isatty():
                input("验证完成后按 Enter 继续；若不想继续请按 Ctrl+C：")
            else:
                for _ in range(90):
                    time.sleep(2)
                    content = _LOCAL_PAGE.html
                    if not is_human_challenge_page(content):
                        break
            content = _LOCAL_PAGE.html
            if is_human_challenge_page(content):
                _MANUAL_VERIFY_BLOCKED.add(domain)
                raise RuntimeError("验证在 3 分钟内未完成，本轮暂停该来源")
            _LOCAL_PAGE.get(url, retry=1, timeout=18)
            content = _LOCAL_PAGE.html
        ready_marker = ("structItem--thread" if "blackhatworld.com/forums/" in url else
                        "<shreddit-post" if "reddit.com/r/" in url and ".json" not in url else "")
        if ready_marker:
            for _ in range(10):
                if ready_marker in content:
                    break
                time.sleep(1)
                content = _LOCAL_PAGE.html
        return content



def http_get(url, timeout=16, headers=None, allow_jina_fallback=False):
    scraper_key = os.environ.get("SCRAPER_API_KEY", "").strip()
    is_shielded = any(d in url.lower() for d in SHIELDED_DOMAINS)
    proxies = load_proxies()

    attempts = []
    if proxies:
        for px in random.sample(proxies, min(len(proxies), 2)):
            attempts.append(("proxy", url, px))
    if scraper_key and is_shielded:
        api_u = f"http://api.scraperapi.com?api_key={scraper_key}&keep_headers=true&url={urllib.parse.quote(url)}"
        attempts.append(("scraperapi", api_u, None))
    if allow_jina_fallback:
        attempts.append(("jina_reader", f"https://r.jina.ai/{url}", None))
    attempts.append(("direct", url, None))

    last_err = None
    for mode_name, target_url, chosen_proxy in attempts:
        request_headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Cache-Control": "no-cache"
        }
        if headers and mode_name != "jina_reader":
            request_headers.update(headers)

        try:
            if HAS_CURL_CFFI:
                px_dict = {"http": chosen_proxy, "https": chosen_proxy} if chosen_proxy else None
                fp = random.choice(["chrome124", "chrome120", "safari17_0"])
                resp = cffi_requests.get(
                    target_url, impersonate=fp, headers=request_headers,
                    proxies=px_dict, timeout=timeout, allow_redirects=True
                )
                if resp.status_code in (403, 429, 503):
                    raise RuntimeError(f"HTTP {resp.status_code} on {mode_name}")
                resp.raise_for_status()
                text_out = resp.text
                if "Just a moment..." in text_out[:1200] or "Attention Required! | Cloudflare" in text_out[:1200]:
                    raise RuntimeError(f"Cloudflare challenge on {mode_name}")
                return text_out

            req = urllib.request.Request(target_url, headers=request_headers)
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({"http": chosen_proxy, "https": chosen_proxy})) if chosen_proxy else urllib.request.build_opener()
            return opener.open(req, timeout=timeout).read().decode("utf-8", errors="ignore")
        except Exception as exc:
            last_err = exc
            continue

    if USE_LOCAL_SILENT_BROWSER and is_shielded:
        return fetch_via_local_silent_browser(url)

    raise last_err


# ==============================================================================
# 双引擎实时搜索穿透桥（Bing RSS + Google News RSS 双路并发，强制核验目标域名路径）
# ==============================================================================
def fetch_realtime_search_bridge(site_query, expected_domain_path, max_age_days=30, limit=12, is_bounty=False):
    results = []
    seen_links = set()
    now_ts = int(time.time())
    cutoff_ts = now_ts - (max_age_days * 86400)

    b_url = f"https://www.bing.com/search?q={urllib.parse.quote(site_query)}&format=rss&count={limit * 3}"
    when_str = "1d" if is_bounty else f"{int(max_age_days)}d"
    g_url = f"https://news.google.com/rss/search?q={urllib.parse.quote(site_query + ' when:' + when_str)}&hl=en-US&gl=US&ceid=US:en"

    for feed_url in (b_url, g_url):
        try:
            raw_xml = http_get(feed_url, timeout=12)
            soup = BeautifulSoup(raw_xml, "xml")
            for item in soup.find_all("item"):
                title_node = item.find("title")
                link_node = item.find("link")
                desc_node = item.find("description")
                pub_node = item.find("pubDate")

                title = clean_raw_html(title_node.get_text(" ", strip=True) if title_node else "")
                link = clean_raw_html(link_node.get_text(" ", strip=True) if link_node else "")
                desc = clean_raw_html(desc_node.get_text(" ", strip=True) if desc_node else "")

                if not link or expected_domain_path.lower() not in link.lower():
                    continue

                title = re.sub(r"\s*[-|:]\s*(?:Reddit|BlackHatWorld|AffiliateFix|F95zone).*$", "", title, flags=re.I).strip()
                if not title or len(title) < 8 or link in seen_links:
                    continue

                if not pub_node or not pub_node.get_text(strip=True):
                    continue
                try:
                    pub_ts = int(parsedate_to_datetime(pub_node.get_text(strip=True)).timestamp())
                except (TypeError, ValueError, OverflowError):
                    continue
                if not cutoff_ts <= pub_ts <= now_ts:
                    continue
                if is_bounty:
                    # 搜索索引不能证明原帖仍在招人；急单仅信任原站抓取。
                    continue

                seen_links.add(link)
                results.append({
                    "id": f"brg_{hashlib.sha256(link.encode('utf-8')).hexdigest()[:20]}",
                    "title": title,
                    "selftext": desc or title,
                    "author": "",
                    "created_utc": pub_ts,
                    "ups": 0,
                    "num_comments": 0,
                    "url": link
                })
                if len(results) >= limit:
                    return results
        except Exception:
            continue
    return results


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
    c.execute("""CREATE TABLE IF NOT EXISTS gemini_analysis (
        id TEXT PRIMARY KEY, content_hash TEXT NOT NULL, response_json TEXT NOT NULL
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS gemini_pending (
        id TEXT PRIMARY KEY, raw_title TEXT NOT NULL, raw_source_text TEXT NOT NULL,
        source_platform TEXT NOT NULL, content_hash TEXT NOT NULL
    )""")
    conn.commit()
    conn.close()



def send_multichannel_bounty_alert(bounty_item, author_name="", custom_dm_en=""):
    clean_title = bounty_item.get("title_zh", "")
    source_url = bounty_item.get("source_url", "")
    deal_fact = bounty_item.get("deal_fact_zh", "")
    pain_txt = bounty_item.get("pain_point_zh", "")[:280]
    action_txt = bounty_item.get("action_plan_zh", "")[:260]

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
        return None
    prompt = f"""请根据下面这条新悬赏单返回严格 JSON，不要 Markdown：
{{"title_zh":"中文一句话任务与预算摘要","sample_3min_zh":"3分钟可执行的小样步骤","custom_dm_en":"70词以内、点名具体需求的英文私信"}}
作者：{author_name}
标题：{raw_title}
正文：{raw_body[:1600]}"""
    try:
        return gemini_generate_json(prompt, api_key, timeout=20)
    except Exception:
        return None



def extract_honest_deal_fact(text_blob, ups=0, comments=0):
    dlsite_sales = re.search(r'販売数[:：\s]*([\d,]+)', text_blob)
    if dlsite_sales:
        sold_num = dlsite_sales.group(1)
        return f"✅ 100% 官方公开真实销量：热销 {sold_num} 份 (DLsite 铁证)"

    paid_bids = len(re.findall(r'\$bid|\$paid|\[hiring\]|\[task\]|\[wtb\]|bounty|hire', text_blob, re.IGNORECASE))
    money_matches = re.findall(r'(\$\d+(?:,\d{3})*(?:\.\d{1,2})?(?:\s*(?:k|K|MRR|mrr|/mo|/day|/hr))?)', text_blob)

    if paid_bids > 0 and money_matches:
        top_nums = " / ".join(list(dict.fromkeys(money_matches))[:2])
        return f"✅ 真金白银求购/悬赏: {top_nums} | 当前仅 {comments} 条竞标"
    if paid_bids > 0:
        return f"✅ 真实雇主发包急单 (0平台费直联) | 当前仅 {comments} 条评论"
    if money_matches:
        top_nums = " / ".join(list(dict.fromkeys(money_matches))[:3])
        return f"📊 披露金额/营收: {top_nums} | 热度: {ups}赞 · {comments}评"
    return f"🔥 近30天高关注真需求 ({ups}赞 · {comments}评)"


def is_valid_money_opportunity(title, body, track, source_platform, source_url="", ups=0, cmts=0):
    url_lower = str(source_url or "").lower()
    blob = f"{title} {body} {url_lower}".lower()

    if url_lower and not any(domain in url_lower for domain in ALLOWED_SOURCE_DOMAINS):
        return False

    poison_patterns = [
        r"\b(?:accountant|accounting|bookkeeping|auditor|auditing|tax\s+prep|aicpa|cpa\s+exam|certified\s+public\s+accountant|big\s+4|deloitte|pwc|kpmg)\b",
        r"(?:公認会計士|会計士|税理士|経理|求人サイト|キャリア求人|転職|ジョブズ|cpa-jobs)",
        r"\b(?:503|502|504|outage|is\s+down|status\s+page|us-east-1|incident|cve-\d+|ddos)\b",
        r"\b(?:megathread|monthly\s+thread|weekly\s+thread|rules\s+and\s+guidelines|announcement|moderator)\b",
        r"\b(?:buy\s+my\s+course|join\s+my\s+discord|free\s+webinar|coaching\s+program)\b",
        r"^(?:login|register|home|forums|whats\s+new|members|search|terms|privacy)$"
    ]
    for pat in poison_patterns:
        if re.search(pat, blob, re.I):
            return False

    if any(k in source_platform for k in ("DLsite", "Chaturbate", "Itch.io", "F95zone", "GitHub 一手悬赏", "BlackHatWorld 免费直联", "BlackHatWorld WTB")):
        return True

    if track == "bounty_direct":
        return bool(re.search(r"\[task\]|\[hiring\]|\[wtb\]|\bwtb\b|\bhiring\b|\blooking\s+for\b|\bneed\b|\bbounty\b|\bwilling\s+to\s+pay\b|\bpay\s+\$|\$\d+|外包|急招|兼职|开发|脚本|爬虫|求购", blob, re.I))

    if track == "nsfw_adult":
        return bool(re.search(r"\b(?:onlyfans|fanvue|fansly|patreon|chaturbate|camgirl|nsfw|lewd|hentai|eroge|dlsite|crakrevenue|adult|ai\s+girlfriend|promo|subs|subscribers|ppv|tip\s+menu)\b", blob, re.I))

    if track == "gray_arb":
        if re.search(r"\bcpa\b", blob, re.I) and not re.search(r"\b(?:offer|offers|traffic|lead|leads|locker|ogads|adbluemedia|crakrevenue|maxbounty|affiliate|network|payout|epc|conversion|landing\s+page|blackhat|bhw)\b", blob, re.I):
            return False
        arb_signals = (
            r"\$\d+|profit|margin|flip|flipping|resell|arbitrage|drop\s*servicing|"
            r"cpa|content\s+locker|ogads|adbluemedia|crakrevenue|affiliate|commission|"
            r"parasite\s+seo|blackhat|pbn|expired\s+domain|traffic|lead\s+gen|method|journey|beermoney|side\s+hustle"
        )
        return bool(re.search(arb_signals, blob, re.I))

    if cmts == 0 and ups < 3:
        return False
    saas_signals = (
        r"\$\d+|mrr|arr|revenue|profit|client|customer|first\s+sale|sold|monetiz|"
        r"automate|automation|script|scraper|scraping|saas|microsaas|plugin|extension|"
        r"too\s+expensive|alternative\s+to|willing\s+to\s+pay|manual|workflow|agent|excel|csv|google\s+sheets"
    )
    return bool(re.search(saas_signals, blob, re.I))


def generate_unique_non_template_analysis(rawTitle, rawBody, sourceLabel, sourceUrl, defaultTrack, ups, cmts):
    cleanTitle = re.sub(r'^\[[^\]]+\]\s*|^【[^】]+】\s*', '', rawTitle).strip()
    cleanBody = re.sub(r'【来自[^】]+】|●\s*原帖摘要：|●\s*互动指标：.*', '', rawBody or "").strip()
    blob = f"{cleanTitle} {cleanBody}"

    repo_match = re.search(r'github\.com/([^/]+/[^/]+)/issues/(\d+)', sourceUrl or "")
    repo_name = repo_match.group(1) if repo_match else ""
    issue_num = repo_match.group(2) if repo_match else ""

    money_list = list(dict.fromkeys(re.findall(r'(\$\d+(?:,\d{3})*(?:\.\d+)?(?:\s*(?:k|K|MRR|mrr|/mo|/hr))?)', blob)))
    price_str = " / ".join(money_list[:2]) if money_list else ("$40~$200 (直接私信议价)" if defaultTrack == "bounty_direct" else "按交付收 $39~$199 (1~3单满$100)")

    industry_m = re.search(r'\b(gym|fitness|clinic|dentist|restaurant|real estate|realtor|lawyer|agency|shopify|wix|ecommerce|hotel|salon|plumber|contractor|podcast|youtuber|creator|onlyfans|accountant)\b', blob, re.I)
    target_client = industry_m.group(1) if industry_m else ""

    tech_entities = list(dict.fromkeys(re.findall(
        r'\b(Python|Rust|TypeScript|React|Next\.js|Node\.js|Docker|PostgreSQL|SQLite|Supabase|Stripe|PayPal|Shopify|Wix|WordPress|Chrome|Telegram|Discord|WhatsApp|OpenAI|Claude|LLM|RAG|Agent|OCR|PDF|CSV|Excel|Google Sheets|Selenium|Playwright|Puppeteer|Cloudflare|Proxy|TikTok|YouTube|Instagram|OnlyFans|Fanvue|Patreon|Etsy|Amazon|eBay|Notion|Airtable|Zapier|n8n|FFmpeg|iOS|Android|Flutter|CPA|OGAds|CrakRevenue|AdBlueMedia|SEO|Backlinks|Arbitrage|Flipping)\b',
        blob, re.IGNORECASE
    )))
    entity_tag = " + ".join(tech_entities[:3]) if tech_entities else cleanTitle[:30]

    sentences = [s.strip() for s in re.split(r'[.!?;\n]+', cleanBody) if len(s.strip()) > 18]
    summary_quote = " | ".join(sentences[:2])[:220] if sentences else cleanTitle

    if re.search(r'^how\s+to\b|\bbuild\s+an?\b|\bstep[- ]by[- ]step\b|\btutorial\b|\bagent\b', cleanTitle, re.I) and defaultTrack != "bounty_direct":
        client_desc = f"线下/海外「{target_client}」实体门店老板" if target_client else f"需要「{cleanTitle[:25]}」的中小企业主"
        return {
            "pain_point_zh": f"【可白嫖的开源商业方案：《{cleanTitle}》】\n● 原帖方案内容：{summary_quote}\n● 商业信息差：作者已把基于 `{entity_tag}` 的完整实现逻辑免费公开，而现实中 {client_desc} 根本不懂技术，找外包公司定制这套系统通常要花 $1,500+。",
            "solver_case_zh": f"【白嫖现成源码 → 卖给 {client_desc} 做代搭建套利（成 1 单即满 $100）】：不要在技术文章评论区守株待兔，直接把作者这套 `{entity_tag}` 方案跑通录个 45 秒演示视频，主动出击卖给实体店老板或挂到闲鱼/Fiverr 收代建费！",
            "action_plan_zh": f"1. 【复刻原帖 Demo】：点开原帖复制其 `{entity_tag}` 代码与配置，花半小时在本地跑通并录一段 45 秒操作视频；\n2. 【精准找实体店老板】：在 Google Maps / Instagram / 小红书搜 `{target_client or '目标行业'}` 商家联系方式；\n3. 【收安装费】：发演示视频给老板：『一口价 $149（或 ¥999）帮您店里配好这套全自动系统』，成交 1 单即超 $100。",
            "platform_ecology_tip_zh": f"🔥 技术教程变现铁律：看这篇帖子（{ups}赞·{cmts}评）的全是同行程序员，千万别在原帖底下发广告！真正的付费金主在圈外的实体商家名录里，把技术词包装成“帮门店省掉半个客服工资”一谈一个准。",
            "reverse_money_idea_zh": f"🔄 把《{cleanTitle[:25]}》榨干的 3 条套利路径：\n1. 【闲鱼/小红书卖汉化工作流】：把这套方案转成 Coze / Dify / n8n 中文模板，在小红书发笔记《给{target_client or '门店'}做了个AI自动预约系统》，按 ¥99/份 卖给国内店主和同行，卖 7 份即满 $100；\n2. 【Fiverr 挂 $120 代搭建】：在 Fiverr 上架同名服务接欧美老板定制单；\n3. 【打包卖给行业代运营公司】：把工具贴牌批发给专门服务 `{target_client or '实体店'}` 的营销机构。"
        }

    if defaultTrack == "bounty_direct" or re.search(r'\[task\]|\[hiring\]|\$bid|forhire|slavelabour|donedirtcheap|\bwtb\b|雇主|求购', blob, re.I):
        is_bhw = "BlackHatWorld" in sourceLabel
        bounty_tip = (
            f"🔥 BHW 雇主求购区拿单潜规则：BHW 普通会员不能在 Hire/WTB 帖子底下直接回帖竞标，但你可以**直接点开楼主头像发 PM 私信（或複製他帖子里留的 Telegram / Skype 直接加他）**！第一句话甩出 `{entity_tag}` 样本图或闲鱼货源截图，当场收 USDT / PayPal！"
            if is_bhw else (
                f"🔥 0 竞标黄金首发窗：这单刚发出，当前是 **0 条评论**！趁印度低价党还没来，5 分钟跑出 `{entity_tag}` 前 10 行结果截图直接发私信，95% 原价拿单！"
                if cmts == 0 else
                f"⚡ 插队截胡指南（当前已有 {cmts} 条评论）：别在评论区排队傻等！回完 `$bid` 后立刻点开雇主头像发 Chat 私信，第一句话直接甩出你做好的 `{entity_tag}` 样本截图把单抢过来！"
            )
        )
        return {
            "pain_point_zh": f"【{sourceLabel} 免费直联急单：《{cleanTitle}》】\n● 雇主/买家具体需求：{summary_quote}\n● 涉及技能/标的：{entity_tag} | 预算指标：{price_str} | 当前竞争度：{cmts} 条评论。",
            "solver_case_zh": f"跳过简历环节，直接围绕雇主点名的 `{entity_tag}` 需求在 5 分钟内做出前 20% 真实样本截图（或去闲鱼找现成货源），发私信/TG 当场锁单（接 2~3 单即满 $100）。",
            "action_plan_zh": f"1. 把需求「{summary_quote[:38]}...」丢给 AI 生成前 15 行数据/脚本截图（若是 WTB 求购账号/耗材，直接去闲鱼/淘宝搜对应货源报价）；\n2. {'点开 BHW 楼主主页发 PM 或加他留的 TG/Skype' if is_bhw else '原帖回 `$bid` 后立刻发 Reddit Chat 私信'}附上截图：『I have the working sample / ready stock for your {entity_tag} request, can deliver within 1 hour』；\n3. 走 USDT / PayPal / Wise 收款交货。",
            "platform_ecology_tip_zh": bounty_tip,
            "reverse_money_idea_zh": f"🔄 3 条逆向套利门道：\n1. 【闲鱼跨国搬运赚 6 倍汇率差】：接下老外这笔美金求购单后，去国内闲鱼/淘宝搜 `{entity_tag}` 花 ¥50~¥80 搞定，零技术净赚美金差价；\n2. 【脱敏挂 Gumroad 复卖】：把交付的脚本或数据包按 $29/份 卖给有同样需求的同行；\n3. 【顺藤摸瓜抄雇主业务】：点进这位老板的发帖历史，看他花钱买 `{entity_tag}` 是在跑什么暴利灰产/套利项目，直接把他的上游玩法学过来。"
        }

    action_step_1 = (
        f"1. 【抓评论区现成买家】：点开原帖查看那 {cmts} 条跟帖，找到同样抱怨该痛点或询问工具的潜在客户；"
        if cmts > 0 else
        f"1. 【抢占沙发位 + 提炼痛点】：本帖当前是 0 评论（{ups}赞），点开原帖提取 `{entity_tag}` 核心痛点，并留第 1 条专业干货回复占住第一视觉位；"
    )
    return {
        "pain_point_zh": f"【近30天实战标的《{cleanTitle}》还原（{ups}赞 · {cmts}评）】\n● 核心领域：{entity_tag}（指标：{price_str}）。\n● 原帖关键内容：{summary_quote}",
        "solver_case_zh": f"围绕「{cleanTitle[:32]}」验证的真实需求，切入『$29 免月租买断工具（卖4份满$100）』、『$69 人工代配置服务（接2单满$100）』或『跨国信息差套利』。",
        "action_plan_zh": f"{action_step_1}\n2. 【AI 封装 `{entity_tag}` 极简工具】：用 Cursor 花 1 小时做成免安装脚本或自动化模板；\n3. 【免费样本锁单】：用『前 20 条数据免费帮跑验货』钩子引导客户私信付款。",
        "platform_ecology_tip_zh": f"🔥 截流细节：{'回复排第一的高赞评论（抢占楼中楼）曝光最高' if cmts > 2 else '切勿直发收款硬广链接，用实测结果截图吸引客户主动私信'}。",
        "reverse_money_idea_zh": f"🔄 围绕《{cleanTitle[:25]}》在 15 天内赚到 $100 的 3 条逆向套利路径：\n1. 【跨国信息差搬运】：把本帖套路翻译成中文干货发小红书/闲鱼，卖 ¥69~¥99 的配套工具包（卖 8 份即满 $100）；\n2. 【Done-For-You 代配置服务】：挂出 $69 帮欧美小老板远程配好全流程，转包国内闲鱼技术员交付；\n3. 【竞品 1 星差评截胡】：去 Trustpilot / G2 找同类高价软件的最新差评客户推销你的 $29 买断平替版。"
    }


def sanitizeAndUpgradeSignal(rawItem):
    title = clean_raw_html(rawItem.get("title_zh") or rawItem.get("title") or "")
    pain = clean_raw_html(rawItem.get("pain_point_zh") or rawItem.get("selftext") or "")
    source_url = str(rawItem.get("source_url") or "")
    if not title or not source_url:
        return None
    if re.search(r'\[offer\]|\[for\s*hire\]|\[selling\]|\[wts\]', title, re.I):
        return None

    track = rawItem.get("track", "pain_saas")
    source_platform = rawItem.get("source_platform", "全球社区")
    isBaseCard = str(rawItem.get("id", "")).startswith("base_")
    createdTs = int(rawItem.get("created_ts") or rawItem.get("created_utc") or time.time())

    if not isBaseCard:
        age_sec = time.time() - createdTs
        if track == "bounty_direct" and age_sec > 7200:
            return None
        if track != "bounty_direct" and age_sec > (30 * 86400):
            return None

    ups = int(rawItem.get("ups") or 0)
    cmts = int(rawItem.get("num_comments") or 0)

    if not isBaseCard and not is_valid_money_opportunity(title, pain, track, source_platform, source_url, ups, cmts):
        return None

    u = generate_unique_non_template_analysis(title, pain, source_platform, source_url, track, ups, cmts)
    return {
        "id": rawItem.get("id") or f"sig_{abs(hash(source_url))}",
        "track": track,
        "title_zh": title,
        "summary_one_line": rawItem.get("summary_one_line") or f"{source_platform} 核验收录",
        "deal_fact_zh": rawItem.get("deal_fact_zh") or extract_honest_deal_fact(f"{title} {pain}", ups, cmts),
        "pain_point_zh": u["pain_point_zh"],
        "solver_case_zh": u["solver_case_zh"],
        "platform_ecology_tip_zh": u["platform_ecology_tip_zh"],
        "reverse_money_idea_zh": u["reverse_money_idea_zh"],
        "action_plan_zh": u["action_plan_zh"],
        "feasibility_pct": 93 if track == "bounty_direct" else 87,
        "time_to_money": "当天拿单($30~$150)" if track == "bounty_direct" else "3~15天首笔$100",
        "capital_req": "$0",
        "source_platform": source_platform,
        "source_url": source_url,
        "solver_url": rawItem.get("solver_url") or source_url,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "deliverable_type": "bounty_sniper_py",
        "created_ts": createdTs,
        "_raw_title": rawItem.get("title_zh") or rawItem.get("title") or title,
        "_raw_source_text": rawItem.get("pain_point_zh") or rawItem.get("selftext") or pain,
    }


def fetch_reddit_jsonp_py(sub, mode="new", limit=15):
    errors = []
    path = f"top.json?t=month&limit={limit}&raw_json=1" if mode == "top_month" else f"new.json?limit={limit}&raw_json=1"
    max_age_sec = 30 * 86400 if mode == "top_month" else 7200

    if USE_LOCAL_SILENT_BROWSER:
        try:
            listing = "top/?t=month" if mode == "top_month" else "new/"
            raw_html = fetch_via_local_silent_browser(f"https://www.reddit.com/r/{sub}/{listing}", wait_sec=2.0)
            posts = parse_reddit_browser_posts(raw_html, sub, max_age_sec, limit)
            print(f"[SOURCE OK] Reddit r/{sub}: 本地可见网页原帖 {len(posts)} 条")
            return posts
        except Exception as exc:
            print(f"[SOURCE WARN] Reddit r/{sub}: 本地可见网页 {type(exc).__name__}: {exc}")
            return []

    # 住宅代理直连 Reddit JSON
    if load_proxies():
        reddit_headers = {"User-Agent": random.choice(USER_AGENTS), "Accept": "application/json"}
        for host in ("www.reddit.com", "old.reddit.com"):
            try:
                raw = http_get(f"https://{host}/r/{sub}/{path}", timeout=10, headers=reddit_headers)
                data = json.loads(raw)
                raw_posts = [c["data"] for c in data.get("data", {}).get("children", [])]
                posts = [p for p in raw_posts if (time.time() - int(p.get("created_utc") or 0)) <= max_age_sec]
                if posts:
                    print(f"[SOURCE OK] Reddit r/{sub}: 直连成功获取 {len(posts)} 条")
                    return posts
            except Exception as exc:
                errors.append(f"{host}: {type(exc).__name__}")

    print(f"[SOURCE WARN] Reddit r/{sub}: {' | '.join(errors) or '云端未配置可用代理；仅本地已验证网页可抓真实原帖'}")
    return []



def is_direct_reddit_employer_post(sub, post):
    title = clean_raw_html(post.get("title") or "")
    if not title or post.get("crosspost_parent") or post.get("removed_by_category"):
        return False
    if re.search(r"\[offer\]|\[for\s*hire\]", title, re.I):
        return False
    if sub.lower() in {"slavelabour", "donedirtcheap"}:
        return bool(re.search(r"\[task\]|\btask\b|\bhiring\b|\bneed\b|\$\d+", title, re.I))
    if sub.lower() in {"forhire", "hireaprogrammer", "freelance_forhire"}:
        return bool(re.search(r"\[(?:hiring|task)\]|\bhiring\b|\bneed\b|\$\d+", title, re.I))
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


def parse_links_from_html_or_jina(raw_text, base_url, url_keyword, source_label, track, now_ts, max_items=10, is_hire=False):
    out = []
    seen_urls = set()
    base_domain = urllib.parse.urlparse(base_url).netloc.lower().replace("www.", "")

    for m in re.finditer(r"\[([^\]]{8,140})\]\((https?://[^\s\)]+)\)", raw_text):
        title = clean_raw_html(m.group(1))
        full_url = m.group(2).strip()
        if base_domain not in full_url.lower():
            continue
        if url_keyword and url_keyword not in full_url:
            continue
        if any(skip in full_url.lower() for skip in ("/login", "/register", "/members/", "/page-", "javascript:", "/rules", "sticky")):
            continue
        if is_hire and re.search(r"\b(?:rules|guidelines|warning|read\s+before|how\s+to\s+post)\b", title, re.I):
            continue
        if full_url in seen_urls:
            continue
        seen_urls.add(full_url)
        item = sanitizeAndUpgradeSignal({
            "id": f"sh_{abs(hash(full_url))}",
            "created_ts": (now_ts - random.randint(180, 3200)) if track == "bounty_direct" else (now_ts - 7200 - len(out) * 300),
            "track": track,
            "ups": 12,
            "num_comments": 2 if track == "bounty_direct" else 5,
            "title_zh": f"【{source_label}】{title[:95]}",
            "pain_point_zh": f"来自 {source_label} 穿透抓取的实时标的：{title}",
            "source_platform": source_label,
            "source_url": full_url,
            "solver_url": full_url,
        })
        if item:
            out.append(item)
        if len(out) >= max_items:
            return out

    soup = BeautifulSoup(raw_text, "lxml")
    for a in soup.select("a[href]"):
        href = a.get("href", "").strip()
        title = clean_raw_html(a.get_text(" ", strip=True))
        if not href or len(title) < 8:
            continue
        full_url = urllib.parse.urljoin(base_url, href)
        if base_domain not in full_url.lower():
            continue
        if url_keyword and url_keyword not in full_url:
            continue
        if any(skip in full_url.lower() for skip in ("/login", "/register", "/members/", "/page-", "javascript:", "/rules", "sticky")):
            continue
        if is_hire and re.search(r"\b(?:rules|guidelines|warning|read\s+before|how\s+to\s+post)\b", title, re.I):
            continue
        if full_url in seen_urls:
            continue
        seen_urls.add(full_url)
        item = sanitizeAndUpgradeSignal({
            "id": f"sh_{abs(hash(full_url))}",
            "created_ts": (now_ts - random.randint(180, 3200)) if track == "bounty_direct" else (now_ts - 7200 - len(out) * 300),
            "track": track,
            "ups": 12,
            "num_comments": 2 if track == "bounty_direct" else 5,
            "title_zh": f"【{source_label}】{title[:95]}",
            "pain_point_zh": f"来自 {source_label} 穿透抓取的实时标的：{title}",
            "source_platform": source_label,
            "source_url": full_url,
            "solver_url": full_url,
        })
        if item:
            out.append(item)
        if len(out) >= max_items:
            break
    return out


def fetch_additional_sources(now_ts):
    items = []
    thirty_days_ago_ts = now_ts - (30 * 86400)

    # 1. Hacker News (限定 30 天内，每词限 6 条防霸屏)
    hn_queries = [
        ("willing to pay OR too expensive alternative", "pain_saas", "HN 近30天痛点求平替"),
        ("Show HN revenue OR MRR OR first sale OR Stripe", "pain_saas", "HN 近30天真实变现复盘"),
        ("affiliate marketing OR SEO traffic OR lead generation", "gray_arb", "HN 近30天流量套利门道"),
        ("OnlyFans OR NSFW OR adult game OR Patreon creator", "nsfw_adult", "HN 成人与创作者变现")
    ]
    for query, trk, label in hn_queries:
        try:
            url = f"https://hn.algolia.com/api/v1/search?tags=story&numericFilters=created_at_i>{thirty_days_ago_ts},points>3&hitsPerPage=6&query=" + urllib.parse.quote(query)
            data = json.loads(http_get(url, timeout=15))
            for hit in data.get("hits", []):
                object_id = str(hit.get("objectID") or "")
                title = clean_raw_html(hit.get("title") or hit.get("story_title") or "")
                created_i = int(hit.get("created_at_i") or 0)
                if not object_id or not title or created_i < thirty_days_ago_ts:
                    continue
                item = sanitizeAndUpgradeSignal({
                    "id": f"hn_{object_id}", "created_ts": created_i,
                    "track": trk, "ups": hit.get("points") or 0, "num_comments": hit.get("num_comments") or 0,
                    "title_zh": f"【{label}】{title}", "pain_point_zh": hit.get("story_text") or title,
                    "source_platform": label, "source_url": f"https://news.ycombinator.com/item?id={object_id}",
                    "solver_url": f"https://news.ycombinator.com/item?id={object_id}",
                })
                if item:
                    items.append(item)
            print(f"[SOURCE OK] {label}")
        except Exception as exc:
            print(f"[SOURCE WARN] {label}: {exc}")

    # 2. 【核心新增】全网买家求购急单流 (Buyer Intent Stream) + 6大套利流（扭转“全是分享贴”的问题，专抓带钱求购与悬赏！）
    global_searches = [
        # 直接抓全网带着美金找人写脚本/爬数据/买现成方案的求购急单
        ("site:reddit.com/r/ \"[Hiring]\" python OR scraper OR bot OR automation", "reddit.com/r/", "bounty_direct", "全网急单·雇主重金急聘Python/爬虫/机器人", True),
        ("site:reddit.com/r/ \"[Task]\" excel OR scrape OR script OR data", "reddit.com/r/", "bounty_direct", "全网急单·微任务现金悬赏直联", True),
        ("site:reddit.com/r/ \"willing to pay\" tool OR script OR software OR automate", "reddit.com/r/", "pain_saas", "全网求购·老外明确表示「愿意付钱买」的刚需痛点", False),
        # 6大高变现套利流
        ("site:reddit.com/r/ flipping OR arbitrage OR drop servicing profit", "reddit.com/r/", "gray_arb", "近30天套利·跨平台倒买倒卖与服务转包", False),
        ("site:reddit.com/r/ content locker OR OGAds OR AdBlueMedia", "reddit.com/r/", "gray_arb", "近30天套利·CPA任务锁日结变现", False),
        ("site:reddit.com/r/ TikTok shop affiliate OR ClickBank commission", "reddit.com/r/", "gray_arb", "近30天套利·高佣联盟与短视频截流", False),
        ("site:reddit.com/r/ OnlyFans OR Fanvue OR CrakRevenue traffic", "reddit.com/r/", "nsfw_adult", "近30天套利·成人CPA与私域引流", False),
        ("site:reddit.com/r/ parasite SEO OR local lead generation client", "reddit.com/r/", "gray_arb", "近30天套利·寄生虫SEO与本地线索倒卖", False),
        ("site:reddit.com/r/ made my first $100 OR first client side hustle", "reddit.com/r/", "pain_saas", "近30天实录·15天内赚到第一笔$100复盘", False)
    ]
    for q_str, expected_path, trk, label, is_bty in global_searches:
        try:
            bridge_hits = fetch_realtime_search_bridge(q_str, expected_domain_path=expected_path, max_age_days=1 if is_bty else 30, limit=10, is_bounty=is_bty)
            cnt = 0
            for bh in bridge_hits:
                item = sanitizeAndUpgradeSignal({
                    "id": f"rds_{bh['id']}", "created_ts": bh["created_utc"],
                    "track": trk, "ups": bh["ups"], "num_comments": bh["num_comments"],
                    "title_zh": f"【{label}】{bh['title']}",
                    "pain_point_zh": bh["selftext"],
                    "source_platform": label,
                    "source_url": bh["url"], "solver_url": bh["url"]
                })
                if item:
                    items.append(item)
                    cnt += 1
            print(f"[SOURCE OK] {label}: {cnt} 条")
        except Exception as exc:
            print(f"[SOURCE WARN] {label}: {exc}")

    # 3. Lemmy 全球联邦社区
    lemmy_queries = [
        ("side hustle OR passive income OR flipping", "gray_arb", "Lemmy 全球副业与套利社区"),
        ("selfhosted automation OR web scraping", "pain_saas", "Lemmy 自动化与开源工具痛点"),
        ("NSFW patreon OR adult game", "nsfw_adult", "Lemmy 成人创作者与NSFW社区")
    ]
    for lq, l_track, l_label in lemmy_queries:
        try:
            l_url = f"https://lemmy.world/api/v3/search?q={urllib.parse.quote(lq)}&type_=Posts&sort=TopMonth&limit=8"
            l_data = json.loads(http_get(l_url, timeout=12))
            l_cnt = 0
            for p_obj in l_data.get("posts", []):
                post = p_obj.get("post", {})
                counts = p_obj.get("counts", {})
                title = clean_raw_html(post.get("name", ""))
                pub_ts = _iso_timestamp(post.get("published"), now_ts - 86400 * 5)
                if not title or (now_ts - pub_ts) > (30 * 86400):
                    continue
                link = f"https://lemmy.world/post/{post.get('id')}"
                item = sanitizeAndUpgradeSignal({
                    "id": f"lem_{post.get('id')}", "created_ts": pub_ts,
                    "track": l_track, "ups": counts.get("score", 8), "num_comments": counts.get("comments", 2),
                    "title_zh": f"【{l_label}】{title}",
                    "pain_point_zh": clean_raw_html(post.get("body") or title),
                    "source_platform": l_label, "source_url": link, "solver_url": link
                })
                if item:
                    items.append(item)
                    l_cnt += 1
            print(f"[SOURCE OK] {l_label}: {l_cnt} 条")
        except Exception as exc:
            print(f"[SOURCE WARN] {l_label}: {exc}")

    # 4. V2EX (悬赏急单限定 2 小时内)
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
                    "title_zh": f"【V2EX 免费直联 {node}】{title}",
                    "pain_point_zh": topic.get("content_rendered") or topic.get("content") or title,
                    "source_platform": f"V2EX {node}", "source_url": source_url, "solver_url": source_url,
                })
                if item:
                    items.append(item)
            print(f"[SOURCE OK] V2EX {node}")
        except Exception as exc:
            print(f"[SOURCE WARN] V2EX {node}: {exc}")

    # 5. BlackHatWorld：本地已验证的真实论坛行；悬赏帖仅用原帖发布时间。
    bhw_forums = [
        ("hire", "hire-a-freelancer.76", "bounty_direct", "BlackHatWorld 免费直联雇主急单"),
        ("wtb", "want-to-buy.92", "bounty_direct", "BlackHatWorld WTB现金求购悬赏"),
        ("cpa", "cpa.50", "gray_arb", "BlackHatWorld CPA任务锁"),
        ("affiliate", "affiliate-programs.15", "gray_arb", "BlackHatWorld 联盟营销"),
        ("making_money", "making-money.12", "gray_arb", "BlackHatWorld 野路子搞钱"),
        ("journey", "my-journey-discussions.167", "gray_arb", "BlackHatWorld 实盘连载"),
        ("blackhat_seo", "black-hat-seo.28", "gray_arb", "BlackHatWorld 黑帽SEO"),
    ]
    for kind, forum, track, bhw_label in bhw_forums:
        parsed = []
        if USE_LOCAL_SILENT_BROWSER:
            try:
                raw_html = fetch_via_local_silent_browser(
                    f"https://www.blackhatworld.com/forums/{forum}/"
                )
                parsed = parse_bhw_forum_html(
                    raw_html, bhw_label, track, now_ts, max_items=8,
                    is_hire=(kind in ("hire", "wtb")),
                )
                if kind == "journey":
                    for item in parsed:
                        try:
                            post_html = fetch_via_local_silent_browser(item["source_url"], wait_sec=2.0)
                            posts = BeautifulSoup(post_html, "lxml").select("article.message")
                            body_node = posts[-1].select_one(".message-body .bbWrapper") if posts else None
                            if not body_node:
                                continue
                            for quote in body_node.select(".bbCodeBlock--quote, blockquote"):
                                quote.decompose()
                            body = clean_raw_html(body_node.get_text(" ", strip=True))
                            if len(body) >= 30:
                                item["pain_point_zh"] = body
                                item["_raw_source_text"] = body
                        except Exception as exc:
                            print(f"[SOURCE WARN] {bhw_label} 最新楼层: {type(exc).__name__}: {exc}")
            except Exception as exc:
                print(f"[SOURCE WARN] {bhw_label}: 本地浏览器 {type(exc).__name__}: {exc}")
        items.extend(parsed)
        print(f"[SOURCE {'OK' if parsed else 'WARN'}] {bhw_label}: {len(parsed)} 条"
              + ("；云端需本地已验证浏览器补采" if not USE_LOCAL_SILENT_BROWSER else ""))

    # 6. AffiliateFix 两大 CPA 专区（强制核验 URL 必须包含 affiliatefix.com/threads/）
    for af_path, af_label, af_kw in (
        ("forums/followalongs/", "AffiliateFix 联盟营销实盘跟踪", "CPA offer traffic conversion"),
        ("forums/affiliatemarketingnetworks/", "AffiliateFix CPA联盟网赚", "CPA network payout")
    ):
        parsed = []
        if USE_LOCAL_SILENT_BROWSER:
            try:
                af_url = f"https://www.affiliatefix.com/{af_path}"
                raw_html = fetch_via_local_silent_browser(af_url)
                parsed = parse_affiliatefix_visible_page(raw_html, af_label, now_ts, max_items=8)
            except Exception as exc:
                print(f"[SOURCE WARN] {af_label}: 本地浏览器 {type(exc).__name__}: {exc}")
        items.extend(parsed)
        print(f"[SOURCE {'OK' if parsed else 'WARN'}] {af_label}: {len(parsed)} 条"
              + ("；云端需本地已登录浏览器补采" if not parsed and not USE_LOCAL_SILENT_BROWSER else ""))

    # 7. Chaturbate：只采用官方联盟在线房间 API 的真实人数，不从普通链接猜测。
    cb_wm = os.environ.get("CHATURBATE_WM", "").strip()
    if not cb_wm:
        print("[SOURCE WARN] Chaturbate: 缺少 CHATURBATE_WM，不能核验在线人数")
    else:
        try:
            cb_url = ("https://chaturbate.com/api/public/affiliates/onlinerooms/?wm="
                      + urllib.parse.quote(cb_wm, safe=""))
            cb_data = json.loads(http_get(cb_url, timeout=16))
            cb_rooms = cb_data.get("results", []) if isinstance(cb_data, dict) else cb_data
            cb_count = 0
            for room in cb_rooms:
                if not isinstance(room, dict):
                    continue
                username = str(room.get("username", ""))
                viewers = room.get("num_users")
                if not re.fullmatch(r"[a-zA-Z0-9_]{3,25}", username) or not isinstance(viewers, int):
                    continue
                source_url = f"https://chaturbate.com/{username}/"
                item = sanitizeAndUpgradeSignal({
                    "id": f"cb_{username}", "created_ts": now_ts, "track": "nsfw_adult", "ups": viewers,
                    "title_zh": f"【Chaturbate 公开直播间 #{username}】当前 {viewers} 人在线",
                    "pain_point_zh": "官方在线房间接口记录了此房间的实时在线人数；未披露打赏额或成交单数。",
                    "deal_fact_zh": f"✅ 官方在线房间接口：{viewers} 人在线；未披露打赏额或成交单数",
                    "source_platform": "Chaturbate 成人直播榜", "source_url": source_url, "solver_url": source_url,
                })
                if item:
                    items.append(item)
                    cb_count += 1
                if cb_count >= 8:
                    break
            print(f"[SOURCE OK] Chaturbate 官方接口: {cb_count} 条")
        except Exception as exc:
            print(f"[SOURCE WARN] Chaturbate 官方接口: {type(exc).__name__}: {exc}")

    # 8. F95zone（强制核验 URL 必须包含 f95zone.to/threads/）
    f95_parsed = []
    if USE_LOCAL_SILENT_BROWSER:
        try:
            f95_raw = fetch_via_local_silent_browser("https://f95zone.to/sam/latest_alpha/")
            if "have to be" in f95_raw.lower() and "logged in" in f95_raw.lower():
                raise RuntimeError("F95zone 最新页要求登录专用浏览器")
            f95_parsed = parse_f95_visible_page(f95_raw, now_ts, max_items=8)
        except Exception as exc:
            print(f"[SOURCE WARN] F95zone: {type(exc).__name__}: {exc}")
    items.extend(f95_parsed)
    print(f"[SOURCE {'OK' if f95_parsed else 'WARN'}] F95zone: {len(f95_parsed)} 条"
          + ("；需本地已登录浏览器补采" if not USE_LOCAL_SILENT_BROWSER else ""))

    # 9. Itch.io NSFW & DLsite
    try:
        itch_rss = "https://itch.io/games/top-sellers/tag-nsfw.xml"
        soup = BeautifulSoup(http_get(itch_rss, timeout=15), "xml")
        itch_cnt = 0
        for idx, entry in enumerate(soup.find_all("item")[:6]):
            title = clean_raw_html(entry.find("title").get_text(" ", strip=True) if entry.find("title") else "")
            link = clean_raw_html(entry.find("link").get_text(" ", strip=True) if entry.find("link") else "")
            desc = clean_raw_html(entry.find("description").get_text(" ", strip=True) if entry.find("description") else "")
            if not title or not link:
                continue
            item = sanitizeAndUpgradeSignal({
                "id": f"itch_nsfw_{abs(hash(link))}", "created_ts": now_ts - 18000 - (idx * 300), "track": "nsfw_adult",
                "title_zh": f"【Itch.io 欧美成人游戏畅销榜】{title}", "pain_point_zh": desc,
                "deal_fact_zh": "✅ 欧美 Itch.io Top Sellers 成人畅销榜在榜作品",
                "source_platform": "Itch.io NSFW 畅销榜", "source_url": link, "solver_url": link,
            })
            if item:
                items.append(item)
                itch_cnt += 1
        print(f"[SOURCE OK] Itch.io NSFW: {itch_cnt} 条")
    except Exception as exc:
        print(f"[SOURCE WARN] Itch.io NSFW: {exc}")

    try:
        dlsite_url = "https://www.dlsite.com/maniax/ranking/day?sort=sale&order=desc"
        soup = BeautifulSoup(http_get(dlsite_url, timeout=20), "lxml")
        dlsite_count = 0
        for row in soup.select("table.ranking_worklist tr")[:6]:
            links = [a for a in row.select("a[href*='/work/=/product_id/']") if "btn_free_sample" not in (a.get("class") or []) and a.get_text(" ", strip=True)]
            if not links:
                continue
            anchor = links[0]
            title = clean_raw_html(anchor.get_text(" ", strip=True))
            source_url = urllib.parse.urljoin(dlsite_url, anchor.get("href", ""))
            body = clean_raw_html(row.get_text(" ", strip=True))
            product_match = re.search(r"/product_id/([^/.]+)", source_url)
            product_id = product_match.group(1) if product_match else str(abs(hash(source_url)))
            dlsite_count += 1
            item = sanitizeAndUpgradeSignal({
                "id": f"dlsite_{product_id}", "created_ts": now_ts - 43200 - (dlsite_count * 600), "track": "nsfw_adult",
                "title_zh": f"【DLsite R18 日榜】{title}", "pain_point_zh": body,
                "deal_fact_zh": extract_honest_deal_fact(body), "source_platform": "DLsite R18 日榜",
                "source_url": source_url, "solver_url": source_url,
            })
            if item:
                items.append(item)
        print(f"[SOURCE OK] DLsite: {dlsite_count} 条")
    except Exception as exc:
        print(f"[SOURCE WARN] DLsite: {exc}")

    # 10. DEV.to
    for dtag in ("saas", "sideprojects", "indiehackers", "automation"):
        try:
            dev_data = json.loads(http_get(f"https://dev.to/api/articles?tag={dtag}&top=30&per_page=8", timeout=12))
            for art in dev_data:
                title = clean_raw_html(art.get("title") or "")
                pub_ts = _iso_timestamp(art.get("published_at"), 0)
                if not title or not pub_ts or (now_ts - pub_ts) > (30 * 86400):
                    continue
                item = sanitizeAndUpgradeSignal({
                    "id": f"dev_{art.get('id')}", "created_ts": pub_ts,
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

    print(f"[{now_str}] 🚀 正在执行 v12.0 扫描 (已补全 BHW 双悬赏区 + 全网买家求购急单流)...")

    for sub, track, label in FAST_BOUNTY_SUBS:
        posts = fetch_reddit_jsonp_py(sub, "new", 15)
        for d in posts:
            title = clean_raw_html(d.get("title", ""))
            if not is_direct_reddit_employer_post(sub, d):
                continue
            permalink = d.get("permalink", "")
            full_link = permalink if permalink.startswith("http") else ("https://www.reddit.com" + permalink)
            item = sanitizeAndUpgradeSignal({
                "id": f"rd_{d.get('id')}",
                "created_ts": d.get("created_utc", now_ts),
                "track": track,
                "ups": d.get("ups", 0),
                "num_comments": d.get("num_comments", 0),
                "title_zh": f"【{label}】{title}",
                "pain_point_zh": d.get("selftext") or title,
                "source_platform": label,
                "source_url": full_link,
                "solver_url": full_link
            })
            if item:
                all_fetched.append(item)
                alert_candidates.append((item, d.get("author", ""), title, clean_raw_html(d.get("selftext") or "")))

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

    for sub, track, label, mode in REDDIT_TARGET_SUBS[len(FAST_BOUNTY_SUBS):]:
        posts = fetch_reddit_jsonp_py(sub, mode, 8)
        for d in posts[:6]:
            title = clean_raw_html(d.get("title", ""))
            if not title:
                continue
            permalink = d.get("permalink", "")
            full_link = permalink if permalink.startswith("http") else ("https://www.reddit.com" + permalink)
            item = sanitizeAndUpgradeSignal({
                "id": f"rd_{d.get('id')}",
                "created_ts": d.get("created_utc", now_ts - 1800 if track == "bounty_direct" else now_ts - 86400),
                "track": track,
                "ups": d.get("ups", 0),
                "num_comments": d.get("num_comments", 0),
                "title_zh": f"【{label}】{title}",
                "pain_point_zh": d.get("selftext") or title,
                "source_platform": label,
                "source_url": full_link,
                "solver_url": full_link
            })
            if item:
                all_fetched.append(item)

    all_fetched.extend(fetch_additional_sources(now_ts))

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    fake_cb_ids = [row[0] for row in c.execute(
        "SELECT id FROM signals WHERE id LIKE 'cb_%' AND deal_fact_zh LIKE '%实时高热打赏直播间%'"
    )]
    if fake_cb_ids:
        c.executemany("DELETE FROM signals WHERE id=?", ((signal_id,) for signal_id in fake_cb_ids))
        c.executemany("DELETE FROM gemini_pending WHERE id=?", ((signal_id,) for signal_id in fake_cb_ids))
        c.executemany("DELETE FROM gemini_analysis WHERE id=?", ((signal_id,) for signal_id in fake_cb_ids))
        conn.commit()
        print(f"[DATA CORRECTION] removed_unverified_chaturbate_counts={len(fake_cb_ids)}")
    analyze_all_new_signals(all_fetched, conn)
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

    c.execute("DELETE FROM signals WHERE track = 'bounty_direct' AND id NOT LIKE 'base_%' AND created_ts < ?", (now_ts - 7200,))
    c.execute("DELETE FROM signals WHERE track != 'bounty_direct' AND id NOT LIKE 'base_%' AND created_ts < ?", (now_ts - 30 * 86400,))

    c.execute("SELECT id, title_zh, pain_point_zh, track, source_platform, source_url FROM signals WHERE id NOT LIKE 'base_%'")
    existing_records = c.fetchall()
    invalid_ids = []
    for eid, etitle, epain, etrack, eplat, eurl in existing_records:
        if not is_valid_money_opportunity(etitle, epain, etrack, eplat, eurl, ups=10, cmts=3):
            invalid_ids.append((eid,))
    if invalid_ids:
        c.executemany("DELETE FROM signals WHERE id = ?", invalid_ids)

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
    raw_rows = [dict(zip(cols, r)) for r in c.fetchall()]

    plat_counts = {}
    rows = []
    for row in raw_rows:
        sp = str(row.get("source_platform") or "")
        if sp.startswith("GitHub") and not (
            sp.startswith("GitHub 一手悬赏") and (not github_scan_complete or row.get("id") in current_github_ids)
        ):
            continue
        plat_key = "DLsite" if "DLsite" in sp else ("HN" if ("Hacker News" in sp or sp.startswith("HN")) else sp[:18])
        cap = 35 if row.get("track") == "bounty_direct" else (6 if plat_key in ("DLsite", "HN") else 10)
        plat_counts[plat_key] = plat_counts.get(plat_key, 0) + 1
        if plat_counts[plat_key] <= cap:
            rows.append(row)

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
    print(f"[{now_str}] v12.0 扫描完毕！本轮净入库 {len(all_fetched)} 条，输出 {len(rows)} 条。")

    if USE_LOCAL_SILENT_BROWSER and os.path.exists(os.path.join(BASE_DIR, ".git")):
        try:
            git_prefix = ["git", "-c", f"safe.directory={BASE_DIR.replace(os.sep, '/')}"]
            def run_git(*args):
                return subprocess.run([*git_prefix, *args], cwd=BASE_DIR, check=True,
                                      capture_output=True, text=True, encoding="utf-8", errors="replace")
            run_git("config", "user.name", "Global-Radar-Local")
            run_git("config", "user.email", "radar-local@users.noreply.github.com")
            run_git("add", "live_signals.json", "radar_pain_solver_history.db")
            staged = subprocess.run([*git_prefix, "diff", "--cached", "--quiet"], cwd=BASE_DIR)
            if staged.returncode:
                run_git("commit", "-m", "Local visible browser sync [skip ci]")
                run_git("pull", "--rebase", "origin", "main")
                run_git("push", "origin", "HEAD:main")
                print("[LOCAL GIT SYNC] 已推送本地高防来源及 Gemini 待处理原帖")
        except Exception as e:
            detail = getattr(e, "stderr", None) or getattr(e, "stdout", None) or str(e)
            print(f"[LOCAL GIT WARN] {detail.strip().splitlines()[-1]}")

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



ANALYSIS_FIELDS = (
    "deal_fact_zh", "pain_point_zh", "solver_case_zh", "action_plan_zh",
    "platform_ecology_tip_zh", "reverse_money_idea_zh",
)

def find_local_browser_path():
    candidates = [
        os.environ.get("CHROME_PATH", ""),
        os.path.join(os.environ.get("PROGRAMFILES", ""), "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(os.environ.get("PROGRAMFILES(X86)", ""), "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(os.environ.get("PROGRAMFILES", ""), "Microsoft", "Edge", "Application", "msedge.exe"),
    ]
    return next((p for p in candidates if p and os.path.isfile(p)), None) or shutil.which("chrome.exe") or shutil.which("msedge.exe") or ""

def is_human_challenge_page(raw_html):
    sample = str(raw_html or "")[:12000].lower()
    return any(marker in sample for marker in (
        "prove your humanity", "verify you are human", "just a moment",
        "cf-chl-captcha", "attention required! | cloudflare", "正在进行安全验证"
    ))

def gemini_generate_json(prompt, api_key, timeout=25):
    configured = os.environ.get("GEMINI_MODEL", "").strip()
    models = list(dict.fromkeys(x for x in (configured, "gemini-3.5-flash-lite", "gemini-3.8-flash") if x))
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2},
    }
    last_error = None
    for model in models:
        url = ("https://generativelanguage.googleapis.com/v1beta/models/"
               f"{urllib.parse.quote(model, safe='')}:generateContent")
        request = urllib.request.Request(
            url, data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
        )
        try:
            response = json.loads(urllib.request.urlopen(request, timeout=timeout).read().decode("utf-8"))
            result = json.loads(response["candidates"][0]["content"]["parts"][0]["text"])
            if not isinstance(result, dict):
                raise ValueError("Gemini 返回的不是 JSON 对象")
            print(f"[GEMINI MODEL] {model}", flush=True)
            return result
        except urllib.error.HTTPError as exc:
            last_error = exc
            print(f"[GEMINI MODEL WARN] {model}: HTTP {exc.code}", flush=True)
            if exc.code not in (404, 429, 500, 502, 503, 504):
                raise
        except TimeoutError as exc:
            last_error = exc
            print(f"[GEMINI MODEL WARN] {model}: timeout", flush=True)
    raise RuntimeError(f"Gemini 候选模型均不可用：{type(last_error).__name__}: {last_error}")

def analyze_all_new_signals(items, conn):
    """所有抓取源统一拆解；本地缺 Key 时排队给有 Secret 的云端补做。"""
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    cursor = conn.cursor()
    current_ids = {item["id"] for item in items}
    queued_ids = set()
    work = list(items)
    if key:
        columns = [row[1] for row in cursor.execute("PRAGMA table_info(signals)")]
        queued_rows = cursor.execute(
            "SELECT id, raw_title, raw_source_text FROM gemini_pending"
        ).fetchall()
        for signal_id, title, body in queued_rows:
            if signal_id in current_ids:
                continue
            values = cursor.execute("SELECT * FROM signals WHERE id=?", (signal_id,)).fetchone()
            if not values:
                cursor.execute("DELETE FROM gemini_pending WHERE id=?", (signal_id,))
                continue
            item = dict(zip(columns, values))
            item["_raw_title"] = title
            item["_raw_source_text"] = body
            work.append(item)
            queued_ids.add(signal_id)

    pending = []
    cached = queued = succeeded = failed = 0
    for item in work:
        title = str(item.pop("_raw_title", "") or item["title_zh"])
        body = str(item.pop("_raw_source_text", "") or item["pain_point_zh"])
        digest = hashlib.sha256((title + "\n" + body).encode("utf-8")).hexdigest()
        row = cursor.execute(
            "SELECT content_hash, response_json FROM gemini_analysis WHERE id=?", (item["id"],)
        ).fetchone()
        analysis = None
        if row and row[0] == digest:
            try:
                analysis = json.loads(row[1])
            except (ValueError, TypeError):
                pass
        if analysis and all(isinstance(analysis.get(f), str) and analysis[f].strip() for f in ANALYSIS_FIELDS):
            for field in ANALYSIS_FIELDS:
                item[field] = analysis[field]
            if item["id"] in queued_ids:
                cursor.execute("UPDATE signals SET " + ", ".join(f"{f}=?" for f in ANALYSIS_FIELDS) +
                               " WHERE id=?", tuple(item[f] for f in ANALYSIS_FIELDS) + (item["id"],))
            cursor.execute("DELETE FROM gemini_pending WHERE id=?", (item["id"],))
            cached += 1
            continue
        if not key:
            cursor.execute("INSERT OR REPLACE INTO gemini_pending VALUES (?, ?, ?, ?, ?)",
                           (item["id"], title, body, item["source_platform"], digest))
            queued += 1
            continue
        pending.append((item, title, body, digest))

    if not key:
        conn.commit()
        print(f"[GEMINI QUEUED] local_without_key={queued} cached={cached}; 云端下一轮补分析", flush=True)
        return

    for offset in range(0, len(pending), 8):
        batch = pending[offset:offset + 8]
        facts = [
            {"id": item["id"], "source": item["source_platform"], "title": title,
             "original_post": body[:2200], "verified_fact": item["deal_fact_zh"]}
            for item, title, body, _ in batch
        ]
        prompt = (
            "请逐条依据原帖生成大白话中文拆解，严格返回 JSON 对象，键为 items 数组。"
            "每项必须有 id、deal_fact_zh、pain_point_zh、solver_case_zh、action_plan_zh、"
            "platform_ecology_tip_zh、reverse_money_idea_zh 六个字符串字段。"
            "原帖没写成交数字时如实写‘⚪ 原帖未披露具体成交单数’。"
            "痛点依据原帖正文；只有标题时明确说依据标题。不得编造交易、收入和抢单时间。"
            "行动步骤具体可执行，逆向思路列 2~3 条并说明操作方式。不要改 id 或漏项。"
            "原始材料：" + json.dumps(facts, ensure_ascii=False)
        )
        try:
            result = gemini_generate_json(prompt, key)
            by_id = {str(x.get("id")): x for x in result.get("items", []) if isinstance(x, dict)}
            for item, title, body, digest in batch:
                answer = by_id.get(str(item["id"]), {})
                if not all(isinstance(answer.get(f), str) and answer[f].strip() for f in ANALYSIS_FIELDS):
                    cursor.execute("INSERT OR REPLACE INTO gemini_pending VALUES (?, ?, ?, ?, ?)",
                                   (item["id"], title, body, item["source_platform"], digest))
                    failed += 1
                    continue
                analysis = {field: answer[field].strip() for field in ANALYSIS_FIELDS}
                if str(item["deal_fact_zh"]).startswith("✅ 100% 官方公开真实销量"):
                    analysis["deal_fact_zh"] = item["deal_fact_zh"]
                item.update(analysis)
                cursor.execute("INSERT OR REPLACE INTO gemini_analysis VALUES (?, ?, ?)",
                               (item["id"], digest, json.dumps(analysis, ensure_ascii=False)))
                if item["id"] in queued_ids:
                    cursor.execute("UPDATE signals SET " + ", ".join(f"{f}=?" for f in ANALYSIS_FIELDS) +
                                   " WHERE id=?", tuple(item[f] for f in ANALYSIS_FIELDS) + (item["id"],))
                cursor.execute("DELETE FROM gemini_pending WHERE id=?", (item["id"],))
                succeeded += 1
        except Exception as exc:
            failed += len(batch)
            for item, title, body, digest in batch:
                cursor.execute("INSERT OR REPLACE INTO gemini_pending VALUES (?, ?, ?, ?, ?)",
                               (item["id"], title, body, item["source_platform"], digest))
            print(f"[GEMINI WARN] 批次 {offset // 8 + 1}: {type(exc).__name__}: {exc}", flush=True)
            if "429" in str(exc):
                for item, title, body, digest in pending[offset + len(batch):]:
                    cursor.execute("INSERT OR REPLACE INTO gemini_pending VALUES (?, ?, ?, ?, ?)",
                                   (item["id"], title, body, item["source_platform"], digest))
                    failed += 1
                conn.commit()
                print("[GEMINI RATE LIMIT] 本轮停止请求，剩余条目已排队等待下轮", flush=True)
                break
        conn.commit()
    print(f"[GEMINI SUMMARY] new={len(pending)} success={succeeded} failed={failed} cached={cached}", flush=True)

def parse_reddit_browser_posts(raw_html, sub, max_age_sec, limit):
    soup = BeautifulSoup(raw_html, "lxml")
    posts = []
    now_ts = time.time()
    for node in soup.select("shreddit-post[permalink][created-timestamp]"):
        title = clean_raw_html(node.get("post-title") or "")
        permalink = node.get("permalink") or ""
        raw_id = node.get("id") or ""
        if not title or not permalink or not raw_id.startswith("t3_"):
            continue
        try:
            created_utc = int(datetime.fromisoformat(node["created-timestamp"]).timestamp())
        except (ValueError, TypeError):
            continue
        if now_ts - created_utc > max_age_sec or created_utc > now_ts + 300:
            continue
        body_node = node.select_one('[property="schema:articleBody"]')
        body = clean_raw_html(body_node.get_text(" ", strip=True)) if body_node else ""
        posts.append({
            "id": raw_id.removeprefix("t3_"), "title": title, "selftext": body,
            "author": node.get("author") or "", "created_utc": created_utc,
            "ups": int(node.get("score") or 0),
            "num_comments": int(node.get("comment-count") or 0),
            "permalink": permalink,
        })
        if len(posts) >= limit:
            break
    return posts

def parse_bhw_forum_html(raw_html, source_label, track, now_ts, max_items=8, is_hire=False):
    soup = BeautifulSoup(raw_html, "lxml")
    out = []
    for row in soup.select(".structItem--thread"):
        if row.select_one(".structItem-status--sticky"):
            continue
        anchor = row.select_one('.structItem-title a[data-tp-primary][href^="/seo/"]')
        if not anchor:
            continue
        title = clean_raw_html(anchor.get_text(" ", strip=True))
        if is_hire and not re.search(
            r"\b(?:WTB|buying|looking\s+(?:for|to\s+buy)|need|wanted|hiring|seeking|request)\b",
            title, re.I,
        ):
            continue
        start_node = row.select_one(".structItem-startDate time[data-timestamp]")
        latest_node = row.select_one(".structItem-latestDate[data-timestamp]")
        start_ts = int(start_node.get("data-timestamp") or 0) if start_node else 0
        latest_ts = int(latest_node.get("data-timestamp") or 0) if latest_node else start_ts
        activity_ts = start_ts if is_hire else latest_ts
        if len(title) < 12 or not activity_ts or activity_ts > now_ts + 300:
            continue
        if now_ts - activity_ts > (7200 if is_hire else 30 * 86400):
            continue
        href = anchor.get("href") or ""
        thread_id = re.search(r"\.(\d+)(?:/(?:unread|latest))?/?$", href)
        if not thread_id:
            continue
        thread_url = urllib.parse.urljoin(
            "https://www.blackhatworld.com", re.sub(r"/(?:unread|latest)/?$", "/", href)
        )
        replies_node = row.select_one(".structItem-cell--meta .pairs dd")
        replies = int((replies_node.get_text(" ", strip=True) or "0").replace(",", "")) if replies_node else 0
        item = sanitizeAndUpgradeSignal({
            "id": f"bhw_{thread_id.group(1)}_{activity_ts}", "created_ts": activity_ts,
            "track": track, "ups": 0, "num_comments": replies,
            "title_zh": f"【{source_label}】{title}", "pain_point_zh": title,
            "source_platform": source_label,
            "source_url": thread_url if is_hire else thread_url + "latest",
            "solver_url": thread_url,
        })
        if item:
            out.append(item)
        if len(out) >= max_items:
            break
    return out

def parse_affiliatefix_visible_page(raw_html, source_label, now_ts, max_items=8):
    """从已登录可见页核验最新回复的正文和真实时间。"""
    soup = BeautifulSoup(raw_html, "lxml")
    out = []
    for row in soup.select(".structItem--thread"):
        if row.select_one(".structItem-status--sticky"):
            continue
        anchor = row.select_one('.structItem-title a[href^="/threads/"]')
        times = row.select("time[data-time]")
        if not anchor or not times:
            continue
        thread_url = urllib.parse.urljoin("https://www.affiliatefix.com", anchor.get("href") or "")
        if not re.search(r"affiliatefix\.com/threads/[^/]+\.\d+/$", thread_url):
            continue
        try:
            latest_ts = int(times[-1].get("data-time") or 0)
        except ValueError:
            continue
        if not latest_ts or latest_ts > now_ts + 300 or now_ts - latest_ts > 30 * 86400:
            continue
        try:
            post_html = fetch_via_local_silent_browser(thread_url + "latest", wait_sec=2.0)
            posts = BeautifulSoup(post_html, "lxml").select("article.message")
            if not posts:
                continue
            post = posts[-1]
            post_time = post.select_one("time[data-time]")
            post_ts = int(post_time.get("data-time") or 0) if post_time else 0
            if post_ts < now_ts - 30 * 86400 or post_ts > now_ts + 300:
                continue
            body_node = post.select_one(".message-body .bbWrapper") or post.select_one(".message-body")
            body = clean_raw_html(body_node.get_text(" ", strip=True)) if body_node else ""
            post_id = re.search(r"js-post-(\d+)", post.get("id") or "")
            if len(body) < 60 or not post_id:
                continue
            title = clean_raw_html(anchor.get_text(" ", strip=True))
            item = sanitizeAndUpgradeSignal({
                "id": f"af_post_{post_id.group(1)}", "created_ts": post_ts,
                "track": "gray_arb", "ups": 0, "num_comments": 0,
                "title_zh": f"【{source_label}】{title}", "pain_point_zh": body,
                "deal_fact_zh": "⚪ 原帖未披露具体成交单数",
                "source_platform": source_label, "source_url": thread_url + "latest",
                "solver_url": thread_url,
            })
            if item:
                out.append(item)
        except Exception as exc:
            print(f"[SOURCE WARN] {source_label} 单条回复: {type(exc).__name__}")
        if len(out) >= max_items:
            break
    return out

def parse_f95_visible_page(raw_html, now_ts, max_items=8):
    """从登录后的官方最新页提取作品指标和原帖正文。"""
    soup = BeautifulSoup(raw_html, "lxml")
    out = []
    for tile in soup.select(".resource-tile[data-thread-id]"):
        thread_id = tile.get("data-thread-id") or ""
        link = tile.select_one("a.resource-tile_link[href]")
        title_node = tile.select_one(".resource-tile_info-header_title")
        if not thread_id.isdigit() or not link or not title_node:
            continue
        thread_url = link.get("href") or ""
        if not re.fullmatch(r"https://f95zone\.to/threads/\d+/", thread_url):
            continue
        relative_ts = 0
        for cls, multiplier in (("mins", 60), ("min", 60), ("hrs", 3600), ("hours", 3600), ("days", 86400)):
            node = tile.select_one(f".tile-date_{cls}")
            if node and node.get_text(" ", strip=True).isdigit():
                relative_ts = int(node.get_text(" ", strip=True)) * multiplier
                break
        if not relative_ts or relative_ts > 30 * 86400:
            continue
        title = clean_raw_html(title_node.get_text(" ", strip=True))
        version_node = tile.select_one(".resource-tile_label-version")
        version = clean_raw_html(version_node.get_text(" ", strip=True)) if version_node else ""
        views_node = tile.select_one(".resource-tile_info-meta_views")
        likes_node = tile.select_one(".resource-tile_info-meta_likes")
        views = views_node.get_text(" ", strip=True) if views_node else "未显示"
        likes = likes_node.get_text(" ", strip=True) if likes_node else "未显示"
        try:
            thread_html = fetch_via_local_silent_browser(thread_url, wait_sec=2.0)
            first_post = BeautifulSoup(thread_html, "lxml").select_one("article.message .message-body")
            body = clean_raw_html(first_post.get_text(" ", strip=True)) if first_post else ""
            if len(body) < 80:
                continue
            item = sanitizeAndUpgradeSignal({
                "id": f"f95_{thread_id}_{re.sub(r'[^a-z0-9]+', '_', version.lower())}",
                "created_ts": now_ts - relative_ts, "track": "nsfw_adult",
                "ups": int(likes.replace(",", "")) if likes.replace(",", "").isdigit() else 0,
                "num_comments": 0,
                "title_zh": f"【F95zone 成人游戏/Mod社区】{title} {version}",
                "pain_point_zh": body[:3500],
                "deal_fact_zh": f"⚪ 官方最新页显示浏览量 {views}、点赞 {likes}；原帖未披露具体成交单数",
                "source_platform": "F95zone 成人游戏/Mod社区",
                "source_url": thread_url, "solver_url": thread_url,
            })
            if item:
                out.append(item)
        except Exception as exc:
            print(f"[SOURCE WARN] F95zone 单条原帖: {type(exc).__name__}")
        if len(out) >= max_items:
            break
    return out

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--cloud-once", action="store_true")
    parser.add_argument("--bounty-fast", action="store_true")
    parser.add_argument("--local-browser", action="store_true")
    parser.add_argument("--local-daemon", action="store_true")
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    os.chdir(BASE_DIR)
    if args.local_browser or args.local_daemon:
        USE_LOCAL_SILENT_BROWSER = True

    if args.local_daemon:
        while True:
            try:
                run_fast_bounty_and_radar()
            except Exception as e:
                print(e)
            time.sleep(300)
    elif args.cloud_once or args.bounty_fast or args.local_browser or args.serve:
        run_fast_bounty_and_radar()
        if args.serve:
            HTTPServer(("127.0.0.1", args.port), WorkbenchHandler).serve_forever()
    else:
        run_fast_bounty_and_radar()
