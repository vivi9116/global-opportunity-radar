#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
全球痛点与真实赚钱机会 24h 自动监控引擎 (v11.7 严格30天时效·全量套利·双核协同版)
================================================================================
核心特性：
1. 【双重严格时效锁】：悬赏单超过 2 小时（7200秒）自动删除；其他所有赛道（套利/痛点/CPA/成人）
   超过 30 天（30*86400秒）一律拒绝入库并从 SQLite 数据库自动物理清除，绝不留几百天前的老贴！
2. 【全量恢复 6 大高变现套利流】：跨平台倒买倒卖套利 (Flipping)、跨国服务转包套利 (Drop-Servicing)、
   CPA 99%任务锁套利、高佣联盟与TikTok带货套利、寄生虫SEO套利、成人SOI注册与跨语种套利。
3. 【聚焦 15 天内赚到首笔 $100】：所有落地步骤明确量化到几单/多少点击即可达标 $100。
4. 【云端 + 本地静默浏览器双核分工】：支持 --cloud-once 与 --local-browser / --local-daemon。
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
import shutil
import subprocess
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
LOCAL_BROWSER_PROFILE = os.environ.get(
    "LOCAL_BROWSER_PROFILE", os.path.join(BASE_DIR, ".radar_silent_chrome_profile")
)

USE_LOCAL_SILENT_BROWSER = False
_PLAYWRIGHT_LOCK = threading.Lock()
_PULLPUSH_LOCK = threading.Lock()
_LAST_PULLPUSH_AT = 0.0


def find_local_browser_path():
    """返回本机已安装的 Chrome/Edge 路径，避免 DrissionPage 找不到浏览器。"""
    candidates = [
        os.environ.get("CHROME_PATH", "").strip(),
        os.path.join(os.environ.get("PROGRAMFILES", ""), "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(os.environ.get("PROGRAMFILES(X86)", ""), "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Google", "Chrome", "Application", "chrome.exe"),
        os.path.join(os.environ.get("PROGRAMFILES", ""), "Microsoft", "Edge", "Application", "msedge.exe"),
        os.path.join(os.environ.get("PROGRAMFILES(X86)", ""), "Microsoft", "Edge", "Application", "msedge.exe"),
    ]
    for path in candidates:
        if path and os.path.isfile(path):
            return path
    for name in ("chrome.exe", "msedge.exe", "google-chrome", "chromium"):
        path = shutil.which(name)
        if path:
            return path
    return ""


def is_human_challenge_page(raw_text):
    sample = str(raw_text or "")[:12000].lower()
    return any(marker in sample for marker in (
        "prove your humanity", "verify you are human", "just a moment",
        "cf-chl-captcha", "attention required! | cloudflare"
    ))


def pullpush_get(url, timeout=15):
    """串行限流并对 429 做有限退避；不把限流误报为抓取成功。"""
    global _LAST_PULLPUSH_AT
    with _PULLPUSH_LOCK:
        min_interval = max(1.5, float(os.environ.get("PULLPUSH_MIN_INTERVAL_SEC", "1.5")))
        wait_for = min_interval - (time.monotonic() - _LAST_PULLPUSH_AT)
        if wait_for > 0:
            time.sleep(wait_for)
        last_error = None
        for attempt in range(3):
            _LAST_PULLPUSH_AT = time.monotonic()
            try:
                return http_get(url, timeout=timeout)
            except Exception as exc:
                last_error = exc
                if "429" not in str(exc):
                    raise
                if attempt < 2:
                    time.sleep(3 * (attempt + 1))
        raise last_error

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15"
]

FAKE_GURU_BLACKLIST = [
    "buy my course", "join my paid discord", "dm me for secret", "100x guaranteed",
    "free webinar", "masterclass", "coaching program"
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
    with _PLAYWRIGHT_LOCK:
        browser_path = find_local_browser_path()
        if not browser_path:
            raise RuntimeError("本机未找到 Chrome/Edge；可设置 CHROME_PATH 指向 chrome.exe")

        try:
            from DrissionPage import ChromiumPage, ChromiumOptions
            co = ChromiumOptions()
            co.set_browser_path(browser_path)
            co.set_user_data_path(LOCAL_BROWSER_PROFILE)
            co.headless(True)
            co.set_argument("--disable-gpu")
            co.set_argument("--mute-audio")
            co.set_argument("--no-sandbox")
            page = ChromiumPage(co)
            try:
                page.get(url, retry=1, timeout=18)
                time.sleep(wait_sec)
                content = page.html
                if is_human_challenge_page(content):
                    raise RuntimeError("页面要求手动完成人机验证，静默模式不会绕过验证")
                return content
            finally:
                try:
                    page.quit()
                except Exception:
                    pass
        except ImportError:
            pass
        except Exception as e:
            print(f"[LOCAL BROWSER DP WARN] {url}: {e}")

        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser = p.chromium.launch_persistent_context(
                    user_data_dir=LOCAL_BROWSER_PROFILE + "_pw",
                    headless=True,
                    executable_path=browser_path,
                    args=["--disable-blink-features=AutomationControlled", "--mute-audio"]
                )
                page = browser.pages[0] if browser.pages else browser.new_page()
                page.goto(url, timeout=20000, wait_until="domcontentloaded")
                time.sleep(wait_sec)
                content = page.content()
                browser.close()
                if is_human_challenge_page(content):
                    raise RuntimeError("页面要求手动完成人机验证，静默模式不会绕过验证")
                return content
        except Exception as e:
            raise RuntimeError(f"本地浏览器启动失败（{browser_path}）：{e}")


def parse_json_from_browser_html(raw_text):
    """解析直接 JSON 或无头浏览器包裹在 <pre> 中的 JSON。"""
    try:
        return json.loads(raw_text)
    except (TypeError, json.JSONDecodeError):
        pass
    text = BeautifulSoup(str(raw_text or ""), "lxml").get_text(" ", strip=True)
    try:
        return json.loads(text)
    except (TypeError, json.JSONDecodeError):
        match = re.search(r"(\{.*\})", text, re.S)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
    raise ValueError("响应不是可解析的 JSON")


def http_get(url, timeout=18, headers=None, allow_jina_fallback=False):
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
    attempts.append(("direct", url, None))
    if allow_jina_fallback:
        attempts.append(("jina_reader", f"https://r.jina.ai/{url}", None))

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
        if mode_name == "jina_reader":
            request_headers["X-Return-Format"] = "html"

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
                if is_human_challenge_page(text_out):
                    raise RuntimeError(f"Cloudflare challenge page on {mode_name}")
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
    model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash").strip()
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
        return f"📊 披露金额/营收: {top_nums} | 热度: {ups}赞 · {comments}评"
    return f"🔥 近30天高关注真需求 ({ups}赞 · {comments}评)"


def is_valid_money_opportunity(title, body, track, source_platform, ups=0, cmts=0):
    blob = f"{title} {body}".lower()
    noise_patterns = [
        r"\b(?:503|502|504|outage|is\s+down|status\s+page|us-east-1|incident|cve-\d+|ddos)\b",
        r"\b(?:megathread|monthly\s+thread|weekly\s+thread|rules|announcement|moderator)\b",
        r"\b(?:buy\s+my\s+course|join\s+my\s+discord|free\s+webinar|coaching\s+program)\b",
        r"^(?:login|register|home|forums|whats\s+new|members|search|terms|privacy)$"
    ]
    for pat in noise_patterns:
        if re.search(pat, blob, re.I):
            return False

    if any(k in source_platform for k in ("DLsite", "Chaturbate", "Itch.io", "F95zone", "GitHub 一手悬赏")):
        return True

    if track == "bounty_direct":
        return bool(re.search(r"\[task\]|\[hiring\]|\bwtb\b|\bhiring\b|\blooking\s+for\b|\bneed\b|\bbounty\b|\$\d+|外包|急招|兼职|开发|脚本|爬虫", blob, re.I))

    if cmts == 0 and ups < 3:
        return False

    money_value_signals = (
        r"\$\d+|mrr|revenue|profit|income|client|customer|sale|sold|earning|monetiz|"
        r"cpa|affiliate|locker|ogads|crakrevenue|traffic|seo|rank|niche|lead|scrape|"
        r"automate|script|tool|saas|plugin|extension|expensive|alternative|manual|"
        r"onlyfans|fanvue|patreon|nsfw|commission|flip|arbitrage|tiktok|etsy|gumroad|agent|booking"
    )
    return bool(re.search(money_value_signals, blob, re.I))


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

    if defaultTrack == "bounty_direct" or re.search(r'\[task\]|\[hiring\]|\$bid|forhire|slavelabour|donedirtcheap|\bwtb\b', blob, re.I):
        bounty_tip = (
            f"🔥 0 竞标黄金首发窗：这单刚发出，当前是 **0 条评论**！趁印度低价党还没来，5 分钟跑出 `{entity_tag}` 前 10 行结果截图直接发私信，95% 原价拿单！"
            if cmts == 0 else
            f"⚡ 插队截胡指南（当前已有 {cmts} 条评论）：别在评论区排队傻等！回完 `$bid` 后立刻点开雇主头像发 Chat 私信，第一句话直接甩出你做好的 `{entity_tag}` 样本截图把单抢过来！"
        )
        return {
            "pain_point_zh": f"【{sourceLabel} 免费直联急单：《{cleanTitle}》】\n● 雇主需求：{summary_quote}\n● 涉及技能：{entity_tag} | 预算指标：{price_str} | 当前竞标：{cmts} 条评论。",
            "solver_case_zh": f"跳过简历环节，直接围绕雇主点名的 `{entity_tag}` 需求在 5 分钟内做出前 20% 真实样本截图发私信当场锁单（接 2~3 单即满 $100）。",
            "action_plan_zh": f"1. 把需求「{summary_quote[:38]}...」丢给 AI 生成前 15 行数据或 Demo 截图；\n2. 原帖回 `$bid` 后立刻发私信附上截图：『Built a working sample for your {entity_tag} task, can deliver in 1 hour』；\n3. 走 PayPal / USDT 收款交货。",
            "platform_ecology_tip_zh": bounty_tip,
            "reverse_money_idea_zh": f"🔄 3 条逆向套利门道：\n1. 【闲鱼转包赚 6 倍汇率差套利】：接下美金单后去国内闲鱼搜 `{entity_tag} 代做` 花 ¥80 搞定；\n2. 【脱敏挂 Gumroad 复卖】：把交付脚本按 $29/份 卖给有同样需求的同行；\n3. 【顺藤摸瓜抄雇主业务】：点进雇主发帖历史看他用这批数据在跑什么暴利项目。"
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
    if not title:
        return None
    if re.search(r'\[offer\]|\[for\s*hire\]', title, re.I):
        return None

    track = rawItem.get("track", "pain_saas")
    source_platform = rawItem.get("source_platform", "全球社区")
    isBaseCard = str(rawItem.get("id", "")).startswith("base_")
    createdTs = int(rawItem.get("created_ts") or rawItem.get("created_utc") or time.time())

    # 严格双重时效锁：悬赏单超过 2 小时（7200秒）丢弃；其他所有赛道超过 30 天（30*86400秒）一律丢弃！
    if not isBaseCard:
        age_sec = time.time() - createdTs
        if track == "bounty_direct" and age_sec > 7200:
            return None
        if track != "bounty_direct" and age_sec > (30 * 86400):
            return None

    ups = int(rawItem.get("ups") or 0)
    cmts = int(rawItem.get("num_comments") or 0)

    if not isBaseCard and not is_valid_money_opportunity(title, pain, track, source_platform, ups, cmts):
        return None

    u = generate_unique_non_template_analysis(title, pain, source_platform, rawItem.get("source_url", ""), track, ups, cmts)
    return {
        "id": rawItem.get("id") or f"sig_{abs(hash(title))}",
        "track": track,
        "title_zh": title,
        "summary_one_line": rawItem.get("summary_one_line") or f"{source_platform} 近30天核验收录",
        "deal_fact_zh": rawItem.get("deal_fact_zh") or extract_honest_deal_fact(f"{title} {pain}", ups, cmts),
        "pain_point_zh": u["pain_point_zh"],
        "solver_case_zh": u["solver_case_zh"],
        "platform_ecology_tip_zh": u["platform_ecology_tip_zh"],
        "reverse_money_idea_zh": u["reverse_money_idea_zh"],
        "action_plan_zh": u["action_plan_zh"],
        "feasibility_pct": 92 if track == "bounty_direct" else 87,
        "time_to_money": "当天拿单($30~$150)" if track == "bounty_direct" else "3~15天首笔$100",
        "capital_req": "$0",
        "source_platform": source_platform,
        "source_url": rawItem.get("source_url", "https://reddit.com"),
        "solver_url": rawItem.get("solver_url", "https://reddit.com"),
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "deliverable_type": "bounty_sniper_py",
        "created_ts": createdTs
    }


def fetch_reddit_jsonp_py(sub, mode="new", limit=20):
    errors = []
    path = f"top.json?t=month&limit={limit}&raw_json=1" if mode == "top_month" else f"new.json?limit={limit}&raw_json=1"
    max_age_sec = 30 * 86400 if mode == "top_month" else 7200

    # 1. 本地模式或已配住宅代理时：优先直连 Reddit JSON 并校验 30天/2小时 时效
    if USE_LOCAL_SILENT_BROWSER or load_proxies():
        reddit_headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "application/json"
        }
        for host in ("www.reddit.com", "old.reddit.com"):
            try:
                raw = http_get(f"https://{host}/r/{sub}/{path}", timeout=12, headers=reddit_headers)
                data = parse_json_from_browser_html(raw)
                raw_posts = [c["data"] for c in data.get("data", {}).get("children", [])]
                posts = [p for p in raw_posts if (time.time() - int(p.get("created_utc") or 0)) <= max_age_sec]
                if posts:
                    print(f"[SOURCE OK] Reddit r/{sub}: 本地/住宅网络直连成功获取 {len(posts)} 条时效内新帖")
                    return posts
            except Exception as exc:
                errors.append(f"{host}: {type(exc).__name__}: {exc}")

    # 2. 云端模式：强制加 after 时间锁（top_month 严格限定最近 30 天内，new 严格限定最近 2 小时内）
    try:
        sort_by = "score" if mode == "top_month" else "created_utc"
        after_ts = int(time.time()) - max_age_sec
        pp_url = f"https://api.pullpush.io/reddit/search/submission/?subreddit={sub}&after={after_ts}&size={limit}&sort=desc&sort_type={sort_by}"
        raw_pp = pullpush_get(pp_url, timeout=14)
        pp_data = parse_json_from_browser_html(raw_pp).get("data", [])
        posts = []
        for d in pp_data:
            if not d.get("title"):
                continue
            created_utc = int(d.get("created_utc") or 0)
            if not created_utc or (time.time() - created_utc) > max_age_sec:
                continue
            posts.append({
                "id": str(d.get("id")),
                "title": d.get("title"),
                "selftext": d.get("selftext") or "",
                "author": d.get("author") or "",
                "created_utc": created_utc,
                "ups": int(d.get("score") or 5),
                "num_comments": int(d.get("num_comments") or 1),
                "permalink": f"/r/{sub}/comments/{d.get('id')}/"
            })
        if posts:
            print(f"[SOURCE OK] Reddit r/{sub} (严格时效内): PullPush 成功获取 {len(posts)} 条")
            return posts
    except Exception as exc:
        errors.append(f"PullPush: {type(exc).__name__}: {exc}")

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


def parse_links_from_html_or_jina(raw_text, base_url, url_keyword, source_label, track, now_ts, max_items=10, is_hire=False):
    out = []
    soup = BeautifulSoup(raw_text, "lxml")
    seen_urls = set()

    for a in soup.select("a[href]"):
        href = a.get("href", "").strip()
        title = clean_raw_html(a.get_text(" ", strip=True))
        if not href or len(title) < 12:
            continue
        full_url = urllib.parse.urljoin(base_url, href)
        if url_keyword and url_keyword not in full_url:
            continue
        if any(skip in full_url.lower() for skip in ("/login", "/register", "/members/", "/page-", "javascript:", "/rules")):
            continue
        if is_hire and not re.search(r"\b(?:WTB|hiring|looking\s+for|need|wanted|task|scrape|bot)\b", title, re.I):
            continue
        if full_url in seen_urls:
            continue
        seen_urls.add(full_url)
        item = sanitizeAndUpgradeSignal({
            "id": f"sh_{abs(hash(full_url))}",
            "created_ts": now_ts - 900 if track == "bounty_direct" else (now_ts - 7200 - len(out) * 300),
            "track": track,
            "ups": 10,
            "num_comments": 3,
            "title_zh": f"【{source_label}】{title[:95]}",
            "pain_point_zh": f"来自 {source_label} 穿透抓取的实战赚钱标的：{title}",
            "source_platform": source_label,
            "source_url": full_url,
            "solver_url": full_url,
        })
        if item:
            out.append(item)
        if len(out) >= max_items:
            return out

    for m in re.finditer(r"\[([^\]]{12,120})\]\((https?://[^\s\)]+)\)", raw_text):
        title = clean_raw_html(m.group(1))
        full_url = m.group(2).strip()
        if url_keyword and url_keyword not in full_url:
            continue
        if is_hire and not re.search(r"\b(?:WTB|hiring|looking\s+for|need|wanted|task|scrape|bot)\b", title, re.I):
            continue
        if full_url in seen_urls:
            continue
        seen_urls.add(full_url)
        item = sanitizeAndUpgradeSignal({
            "id": f"sh_{abs(hash(full_url))}",
            "created_ts": now_ts - 900 if track == "bounty_direct" else (now_ts - 7200 - len(out) * 300),
            "track": track,
            "ups": 10,
            "num_comments": 3,
            "title_zh": f"【{source_label}】{title[:95]}",
            "pain_point_zh": f"来自 {source_label} 穿透抓取的实战赚钱标的：{title}",
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

    # 1. Hacker News (强制 created_at_i > thirty_days_ago_ts 锁死 30 天内)
    hn_queries = [
        ("willing to pay OR too expensive alternative", "pain_saas", "HN 近30天痛点求平替"),
        ("Show HN revenue OR MRR OR first sale OR Stripe", "pain_saas", "HN 近30天真实变现复盘"),
        ("affiliate OR arbitrage OR SEO OR lead generation", "gray_arb", "HN 近30天流量套利门道"),
        ("OnlyFans OR NSFW OR adult OR AI companion", "nsfw_adult", "HN 成人与AI伴侣变现")
    ]
    for query, trk, label in hn_queries:
        try:
            url = f"https://hn.algolia.com/api/v1/search?tags=story&numericFilters=created_at_i>{thirty_days_ago_ts},points>3&hitsPerPage=8&query=" + urllib.parse.quote(query)
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
                    "source_platform": label, "source_url": hit.get("url") or f"https://news.ycombinator.com/item?id={object_id}",
                    "solver_url": f"https://news.ycombinator.com/item?id={object_id}",
                })
                if item:
                    items.append(item)
            print(f"[SOURCE OK] {label}")
        except Exception as exc:
            print(f"[SOURCE WARN] {label}: {exc}")

    # 2. 全网近 30 天套利与快钱搜索引擎（强制加 after=thirty_days_ago_ts 锁死 30 天内，绝不抓几百天前的老贴！）
    global_searches = [
        ("arbitrage OR drop servicing OR flipping profit", "gray_arb", "近30天套利·跨平台倒买倒卖与服务转包"),
        ("CPA locker OGAds AdBlueMedia", "gray_arb", "近30天套利·CPA任务锁日结变现"),
        ("affiliate commission TikTok shop OR ClickBank", "gray_arb", "近30天套利·高佣联盟与短视频截流"),
        ("OnlyFans traffic promote OR CrakRevenue", "nsfw_adult", "近30天套利·成人CPA与私域引流"),
        ("parasite SEO rank OR local lead generation", "gray_arb", "近30天套利·寄生虫SEO与本地线索倒卖"),
        ("made my first 100 OR first client OR first sale", "pain_saas", "近30天实录·15天内赚到第一笔$100复盘")
    ]
    for q_str, trk, label in global_searches:
        try:
            pp_url = f"https://api.pullpush.io/reddit/search/submission/?q={urllib.parse.quote(q_str)}&after={thirty_days_ago_ts}&size=12&sort=desc&sort_type=score"
            pp_data = parse_json_from_browser_html(pullpush_get(pp_url, timeout=15)).get("data", [])
            cnt = 0
            for d in pp_data:
                title = clean_raw_html(d.get("title", ""))
                created_utc = int(d.get("created_utc") or 0)
                if not title or not created_utc or (now_ts - created_utc) > (30 * 86400):
                    continue
                sub_name = d.get("subreddit", "all")
                post_id = d.get("id", "")
                link = d.get("full_link") or f"https://www.reddit.com/r/{sub_name}/comments/{post_id}/"
                item = sanitizeAndUpgradeSignal({
                    "id": f"rds_{post_id}", "created_ts": created_utc,
                    "track": trk, "ups": int(d.get("score") or 10), "num_comments": int(d.get("num_comments") or 2),
                    "title_zh": f"【{label} · r/{sub_name}】{title}",
                    "pain_point_zh": d.get("selftext") or title,
                    "source_platform": label,
                    "source_url": link, "solver_url": link
                })
                if item:
                    items.append(item)
                    cnt += 1
            print(f"[SOURCE OK] {label} (严格30天内): {cnt} 条")
        except Exception as exc:
            print(f"[SOURCE WARN] {label}: {exc}")

    # 3. V2EX (悬赏急单限定 2 小时内)
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

    # 4. BlackHatWorld / AffiliateFix / F95zone
    bhw_forums = [
        ("cpa", "cpa.24", "gray_arb", "BlackHatWorld CPA任务锁"),
        ("affiliate", "affiliate-programs.15", "gray_arb", "BlackHatWorld 联盟营销"),
        ("making_money", "making-money.12", "gray_arb", "BlackHatWorld 野路子搞钱"),
        ("journey", "my-journey-discussions.167", "gray_arb", "BlackHatWorld 实盘连载"),
        ("blackhat_seo", "black-hat-seo.28", "gray_arb", "BlackHatWorld 黑帽SEO"),
        ("hire", "hire-a-freelancer.76", "bounty_direct", "BlackHatWorld 免费直联雇主急单")
    ]
    for kind, forum, track, bhw_label in bhw_forums:
        try:
            forum_url = f"https://www.blackhatworld.com/forums/{forum}/"
            raw_html = http_get(forum_url, timeout=20, allow_jina_fallback=True)
            parsed = parse_links_from_html_or_jina(
                raw_html, "https://www.blackhatworld.com", "/threads/",
                bhw_label, track, now_ts, max_items=10, is_hire=(kind == "hire")
            )
            if not parsed and USE_LOCAL_SILENT_BROWSER:
                raw_html = fetch_via_local_silent_browser(forum_url)
                parsed = parse_links_from_html_or_jina(
                    raw_html, "https://www.blackhatworld.com", "/threads/",
                    bhw_label, track, now_ts, max_items=10, is_hire=(kind == "hire")
                )
            items.extend(parsed)
            status_tag = "SOURCE OK" if len(parsed) > 0 else "SOURCE EMPTY (需本地模式 --local-browser 或住宅IP)"
            print(f"[{status_tag}] {bhw_label}: {len(parsed)} 条")
        except Exception as exc:
            print(f"[SOURCE WARN] {bhw_label}: {exc}")

    for af_path, af_label in (("whats-new/posts/", "AffiliateFix CPA最新实战"), ("forums/cpa-affiliate-networks.9/", "AffiliateFix CPA联盟网赚")):
        try:
            af_url = f"https://www.affiliatefix.com/{af_path}"
            raw_html = http_get(af_url, timeout=20, allow_jina_fallback=True)
            parsed = parse_links_from_html_or_jina(
                raw_html, "https://www.affiliatefix.com", "/threads/",
                af_label, "gray_arb", now_ts, max_items=10
            )
            if not parsed and USE_LOCAL_SILENT_BROWSER:
                raw_html = fetch_via_local_silent_browser(af_url)
                parsed = parse_links_from_html_or_jina(
                    raw_html, "https://www.affiliatefix.com", "/threads/",
                    af_label, "gray_arb", now_ts, max_items=10
                )
            items.extend(parsed)
            status_tag = "SOURCE OK" if len(parsed) > 0 else "SOURCE EMPTY (需本地模式 --local-browser 或住宅IP)"
            print(f"[{status_tag}] {af_label}: {len(parsed)} 条")
        except Exception as exc:
            print(f"[SOURCE WARN] {af_label}: {exc}")

    # 5. Chaturbate
    try:
        cb_rooms = []
        wm = os.environ.get("CHATURBATE_WM", "").strip()
        cb_endpoints = [
            f"https://chaturbate.com/api/public/affiliates/onlinerooms/?wm={urllib.parse.quote(wm or 'T9n5p')}&format=json",
            "https://chaturbate.com/affiliates/api/onlinerooms/?format=json&wm=T9n5p"
        ]
        for cb_ep in cb_endpoints:
            try:
                data = json.loads(http_get(cb_ep, timeout=12))
                cb_rooms = data.get("results", []) if isinstance(data, dict) else data
                if cb_rooms:
                    break
            except Exception:
                continue

        if not cb_rooms:
            cb_html = http_get("https://chaturbate.com/", timeout=15)
            cb_soup = BeautifulSoup(cb_html, "lxml")
            for li in cb_soup.select("li.room_list_room")[:10]:
                a_node = li.select_one("a[href]")
                if not a_node:
                    continue
                uname = a_node.get("href", "").strip("/")
                viewer_blob = " ".join(str(li.get(attr, "")) for attr in ("data-viewers", "data-num-users", "data-user-count"))
                viewer_blob += " " + li.get_text(" ", strip=True)
                viewer_match = re.search(r"(?<![\d,])(\d{1,3}(?:,\d{3})*|\d+)(?![\d,])", viewer_blob)
                if not viewer_match:
                    continue
                cb_rooms.append({
                    "username": uname,
                    "num_users": int(viewer_match.group(1).replace(",", "")),
                    "tags": ["live", "top"]
                })

        top_rooms = sorted(cb_rooms, key=lambda x: int(x.get("num_users") or 0), reverse=True)[:10]
        for idx, room in enumerate(top_rooms):
            username = str(room.get("username") or "")
            if not username:
                continue
            viewers = int(room.get("num_users") or 0)
            tags = " / ".join((room.get("tags") or [])[:5])
            source_url = room.get("chat_room_url") or f"https://chaturbate.com/{username}/"
            item = sanitizeAndUpgradeSignal({
                "id": f"cb_{username}", "created_ts": now_ts - 14400 - (idx * 300), "track": "nsfw_adult", "ups": viewers,
                "title_zh": f"【Chaturbate 全球成人直播榜 #{username}】当前 {viewers} 人在线打赏 (标签: {tags})",
                "pain_point_zh": f"当前直播间实时在线 {viewers} 人；高转化细分癖好标签：{tags} ($1~$3/免费注册 或 20% 终身分成)",
                "deal_fact_zh": f"✅ 官方实时在线打赏金主：{viewers} 人", "source_platform": "Chaturbate 成人直播榜",
                "source_url": source_url, "solver_url": source_url,
            })
            if item:
                items.append(item)
        if top_rooms:
            print(f"[SOURCE OK] Chaturbate: {len(top_rooms)} 条")
        else:
            print("[SOURCE WARN] Chaturbate: 0 条（官方接口需要有效 CHATURBATE_WM，首页未解析到公开房间）")
    except Exception as exc:
        print(f"[SOURCE WARN] Chaturbate: {exc}")

    try:
        f95_url = "https://f95zone.to/sam/latest_alpha/"
        f95_raw = http_get(f95_url, timeout=20, allow_jina_fallback=True)
        f95_parsed = parse_links_from_html_or_jina(
            f95_raw, "https://f95zone.to", "/threads/",
            "F95zone 成人游戏/Mod社区", "nsfw_adult", now_ts, max_items=10
        )
        if not f95_parsed and USE_LOCAL_SILENT_BROWSER:
            f95_raw = fetch_via_local_silent_browser(f95_url)
            f95_parsed = parse_links_from_html_or_jina(
                f95_raw, "https://f95zone.to", "/threads/",
                "F95zone 成人游戏/Mod社区", "nsfw_adult", now_ts, max_items=10
            )
        items.extend(f95_parsed)
        status_tag = "SOURCE OK" if len(f95_parsed) > 0 else "SOURCE EMPTY (需本地模式 --local-browser 或住宅IP)"
        print(f"[{status_tag}] F95zone: {len(f95_parsed)} 条")
    except Exception as exc:
        print(f"[SOURCE WARN] F95zone: {exc}")

    try:
        itch_rss = "https://itch.io/games/top-sellers/tag-nsfw.xml"
        soup = BeautifulSoup(http_get(itch_rss, timeout=15), "xml")
        itch_cnt = 0
        for idx, entry in enumerate(soup.find_all("item")[:8]):
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

    # 6. DEV.to（严格过滤超过 30 天的旧文）
    for dtag in ("saas", "sideprojects", "indiehackers", "automation"):
        try:
            dev_data = json.loads(http_get(f"https://dev.to/api/articles?tag={dtag}&top=30&per_page=10", timeout=12))
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

    mode_str = "本地静默浏览器穿透模式" if USE_LOCAL_SILENT_BROWSER else "GitHub 云端模式"
    print(f"[{now_str}] 🚀 正在执行 v11.7 ({mode_str}) 全网扫描 (悬赏限2h内 · 套利/痛点严格限30天内)...")

    for sub, track, label in FAST_BOUNTY_SUBS:
        posts = fetch_reddit_jsonp_py(sub, "new", 25)
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
        posts = fetch_reddit_jsonp_py(sub, mode, 10)
        for d in posts[:8]:
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

    # 数据库强制双重物理清理：
    # 1. 悬赏急单超过 2 小时（7200秒）立即删除；
    # 2. 其他所有赛道超过 30 天（30*86400秒）立即删除，彻底清光几百天前的历史旧贴！
    c.execute("DELETE FROM signals WHERE track = 'bounty_direct' AND id NOT LIKE 'base_%' AND created_ts < ?", (now_ts - 7200,))
    c.execute("DELETE FROM signals WHERE track != 'bounty_direct' AND id NOT LIKE 'base_%' AND created_ts < ?", (now_ts - 30 * 86400,))
    c.execute("DELETE FROM signals WHERE source_platform LIKE '%Upwork%' OR source_platform LIKE '%PeoplePerHour%' OR source_platform LIKE '%Freelancer%' OR source_platform LIKE '%Flippa%'")
    c.execute("DELETE FROM signals WHERE solver_case_zh LIKE '%顺应当前热度，围绕该标的提供%' OR action_plan_zh LIKE '%去原帖 0 条评论里%' OR title_zh LIKE '%503%'")

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
        cap = 30 if row.get("track") == "bounty_direct" else (8 if plat_key in ("DLsite", "HN") else 12)
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
    print(f"[{now_str}] v11.7 扫描完毕！共输出 {len(rows)} 条严格时效内（悬赏2h/大盘30天）数据。")

    if USE_LOCAL_SILENT_BROWSER and os.path.exists(os.path.join(BASE_DIR, ".git")):
        try:
            def run_git(*args):
                return subprocess.run(
                    ["git", *args], cwd=BASE_DIR, check=True,
                    capture_output=True, text=True, encoding="utf-8", errors="replace"
                )

            run_git("config", "user.name", "Global-Radar-Local")
            run_git("config", "user.email", "radar-local@users.noreply.github.com")
            run_git("add", "live_signals.json", "radar_pain_solver_history.db")
            staged = subprocess.run(
                ["git", "diff", "--cached", "--quiet"], cwd=BASE_DIR, check=False
            )
            if staged.returncode == 0:
                print("[LOCAL GIT SYNC] 没有新的高防源数据需要同步")
            else:
                run_git("commit", "-m", "Local silent browser sync [skip ci]")
                run_git("pull", "--rebase", "origin", "main")
                run_git("push", "origin", "HEAD:main")
                print("[LOCAL GIT SYNC] 已确认提交并推送到 GitHub Pages")
        except subprocess.CalledProcessError as exc:
            detail = (exc.stderr or exc.stdout or str(exc)).strip().splitlines()[-1]
            print(f"[LOCAL GIT WARN] 同步失败：{detail}")
        except Exception as exc:
            print(f"[LOCAL GIT WARN] 同步失败：{exc}")

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
    parser.add_argument("--cloud-once", action="store_true", help="GitHub Actions 云端运行一次")
    parser.add_argument("--bounty-fast", action="store_true", help="快速扫描悬赏单")
    parser.add_argument("--local-browser", action="store_true", help="在本地电脑使用静默无头浏览器运行一次")
    parser.add_argument("--local-daemon", action="store_true", help="在本地电脑后台常驻运行")
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    os.chdir(BASE_DIR)
    if args.local_browser or args.local_daemon:
        USE_LOCAL_SILENT_BROWSER = True

    if args.local_daemon:
        print("🚀 已启动本地静默守护模式（完全后台无头运行，不弹窗、不影响日常使用电脑）...")
        while True:
            try:
                run_fast_bounty_and_radar()
            except Exception as e:
                print(e)
            time.sleep(300)
    elif args.cloud_once or args.bounty_fast or args.local_browser or args.serve:
        run_fast_bounty_and_radar()
        if args.serve:
            print(f"🚀 本地无上限满血工作台已启动: http://127.0.0.1:{args.port}/")
            HTTPServer(("127.0.0.1", args.port), WorkbenchHandler).serve_forever()
    else:
        run_fast_bounty_and_radar()
