#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
全球痛点与真实赚钱机会 24h 自动监控引擎 (v11.4 纯免费接单源·反403穿透·非模板深度拆解版)
================================================================================
核心修正：
1. 移除 Upwork / PeoplePerHour / Freelancer 等需付费订阅或买 Connects 才能投标的平台，
   悬赏赛道 100% 仅保留完全免费直联雇主的平台 (Reddit 5大急单区 / GitHub一手Bounty / V2EX / BHW Hire)。
2. 移除 Flippa 杂乱链接，新增【入库前赚钱价值严格过滤器 (is_valid_money_opportunity)】，
   抓之前先判断是否为真实赚钱门道、真金白银复盘或可落地的痛点需求，垃圾水贴一律不入库。
3. 彻底重写后端的 generate_unique_non_template_analysis（替换掉原先那 5 行死模板），
   根据每条帖子的具体标的、原话、金额与赛道，一对一生成小白可执行的 ②、③、④ 步拆解。
4. 内置 PullPush 免盾镜像 + Jina 穿透网关 + 住宅 IP 自动轮换，解决 Reddit / BHW / AffiliateFix 403/429。
5. 悬赏急单超过 2 小时（7200秒）自动拒绝入库并从 SQLite 数据库自动删除。
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

# 100% 免费接单悬赏源（无需买会员或投标币，直接私信雇主拿单）
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
    ("flipping", "gray_arb", "Reddit r/flipping (跨平台低买高卖倒爷)", "top_month"),
    ("affiliatemarketing", "gray_arb", "Reddit r/affiliatemarketing (CPA与联盟营销套利)", "top_month"),
    ("blackhat", "gray_arb", "Reddit r/blackhat (黑帽SEO与灰产技术热榜)", "top_month"),
    ("leadgeneration", "gray_arb", "Reddit r/leadgeneration (B2B灰产获客与名单倒卖)", "top_month"),
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
                return resp.text

            req = urllib.request.Request(target_url, headers=request_headers)
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({"http": chosen_proxy, "https": chosen_proxy})) if chosen_proxy else urllib.request.build_opener()
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
    return f"🔥 高关注真实赚钱需求 ({ups}赞 · {comments}评)"


# ==============================================================================
# 入库前赚钱价值严格过滤器：先判断抓取的内容是否真的是赚钱项目/雇主悬赏/真实痛点！
# ==============================================================================
def is_valid_money_opportunity(title, body, track, source_platform):
    blob = f"{title} {body}".lower()
    # 剔除导航词、版规公告、纯政治闲聊、付费卖课骗子
    noise_patterns = [
        r"\b(?:megathread|monthly\s+thread|weekly\s+thread|rules|announcement|moderator)\b",
        r"\b(?:buy\s+my\s+course|join\s+my\s+discord|free\s+webinar|coaching\s+program)\b",
        r"^(?:login|register|home|forums|whats\s+new|members|search|terms|privacy)$"
    ]
    for pat in noise_patterns:
        if re.search(pat, blob, re.I):
            return False

    # 成人榜单、GitHub一手已核验悬赏直接放行
    if any(k in source_platform for k in ("DLsite", "Chaturbate", "Itch.io", "F95zone", "GitHub 一手悬赏")):
        return True

    # 悬赏急单必须包含明确雇佣/求购/任务预算意图
    if track == "bounty_direct":
        return bool(re.search(r"\[task\]|\[hiring\]|\bwtb\b|\bhiring\b|\blooking\s+for\b|\bneed\b|\bbounty\b|\$\d+|外包|急招|兼职|开发|脚本|爬虫", blob, re.I))

    # 痛点、灰产、CPA 必须包含商业/变现/工具/流量相关核心词，拒绝无关水贴
    money_value_signals = (
        r"\$\d+|mrr|revenue|profit|income|client|customer|sale|sold|earning|monetiz|"
        r"cpa|affiliate|locker|ogads|crakrevenue|traffic|seo|rank|niche|lead|scrape|"
        r"automate|script|tool|saas|plugin|extension|expensive|alternative|manual|"
        r"onlyfans|fanvue|patreon|nsfw|commission|flip|arbitrage|tiktok|etsy|gumroad"
    )
    return bool(re.search(money_value_signals, blob, re.I))


# ==============================================================================
# 彻底重构的非模板化深度拆解引擎（替换原先那 5 行死模板，每条帖子动态抠词生成专属 ②③④）
# ==============================================================================
def generate_unique_non_template_analysis(rawTitle, rawBody, sourceLabel, sourceUrl, defaultTrack, ups, cmts):
    blob = f"{rawTitle} {rawBody}"
    cleanTitle = re.sub(r'^\[[^\]]+\]\s*|^【[^】]+】\s*', '', rawTitle).strip()

    repo_match = re.search(r'github\.com/([^/]+/[^/]+)/issues/(\d+)', sourceUrl or "")
    repo_name = repo_match.group(1) if repo_match else ""
    issue_num = repo_match.group(2) if repo_match else ""

    money_list = list(dict.fromkeys(re.findall(r'(\$\d+(?:,\d{3})*(?:\.\d+)?(?:\s*(?:k|K|MRR|mrr|/mo|/hr))?)', blob)))
    price_str = " / ".join(money_list[:2]) if money_list else ("$40~$200 (直接私信议价)" if defaultTrack == "bounty_direct" else "$19~$49 (买断/代办定价)")

    tech_entities = list(dict.fromkeys(re.findall(
        r'\b(Python|Rust|TypeScript|React|Next\.js|Node\.js|Docker|PostgreSQL|SQLite|Supabase|Stripe|PayPal|Shopify|Wix|WordPress|Chrome|Telegram|Discord|WhatsApp|OpenAI|Claude|LLM|RAG|OCR|PDF|CSV|Excel|Google Sheets|Selenium|Playwright|Puppeteer|Cloudflare|Proxy|TikTok|YouTube|Instagram|OnlyFans|Fanvue|Patreon|Etsy|Amazon|eBay|Notion|Airtable|Zapier|n8n|FFmpeg|iOS|Android|Flutter|CPA|OGAds|CrakRevenue|AdBlueMedia|SEO|Backlinks)\b',
        blob, re.IGNORECASE
    )))
    entity_tag = " + ".join(tech_entities[:3]) if tech_entities else cleanTitle[:30]

    sentences = [s.strip() for s in re.split(r'[.!?;\n]+', rawBody) if len(s.strip()) > 20]
    quote1 = sentences[0][:175] if len(sentences) > 0 else cleanTitle
    quote2 = sentences[1][:175] if len(sentences) > 1 else "（点击左下角原帖直链查看完整需求上下文与评论区）"

    # 1. 针对 GitHub 悬赏单的一对一拆解
    if repo_name or "GitHub" in sourceLabel:
        target_repo = repo_name or cleanTitle[:28]
        return {
            "pain_point_zh": (
                f"【GitHub 仓库 `{target_repo}` 第 #{issue_num or 'Open'} 号免费直领赏金单】\n"
                f"● 任务标的：《{cleanTitle}》（涉及模块：{entity_tag} | 赏金/指标：{price_str} | 当前评论：{cmts} 条）。\n"
                f"● 维护者卡点原话：「{quote1}」\n"
                f"● 补充技术细节：「{quote2}」"
            ),
            "solver_case_zh": (
                f"针对 `{target_repo}` 仓库的「{cleanTitle[:36]}」切入：GitHub 悬赏完全免费、无需像 Upwork 那样花钱买投标币！"
                f"趁当前只有 {cmts} 条评论，直接把跟 `{entity_tag}` 相关的独立文件丢给 Cursor/Claude 生成修复补丁提交 PR 即可领钱。"
            ),
            "action_plan_zh": (
                f"1. 【定位 `{target_repo}` 源码】：打开下方 #{issue_num} 原帖，把「{quote1[:40]}...」贴进 Cursor，定位 `{entity_tag}` 对应文件；\n"
                f"2. 【15分钟先贴终端验证图锁单】：本地跑通最小测试后截图贴到 #{issue_num} 评论区，写明『Fixed the {entity_tag} issue locally (screenshot attached), opening PR now』，让维护者把单 Assign 给你；\n"
                f"3. 【合并收款】：PR 合并后通过 Issue 绑定的 Algora / Opire / Polar 或 PayPal 直接收美金。"
            ),
            "platform_ecology_tip_zh": (
                f"🔥 针对 `{target_repo}` (#{issue_num}) 的抢单避坑提醒：\n"
                f"● 点进原帖先看有没有人已经挂出 Open 状态的 Pull Request；如果那 {cmts} 条评论只是别人在问 'Can I try?' 而没交代码，你带测试截图直接插队 100% 拿单！"
            ),
            "reverse_money_idea_zh": (
                f"🔄 围绕「{cleanTitle[:28]}」的 3 条逆向赚钱门道：\n"
                f"1. 【承包金主团队后续外包】：肯为 `{target_repo}` 发赏金的团队有真实预算，顺着组织主页找到创始人邮箱，按 $50/小时 承包他们后续的 `{entity_tag}` 杂活；\n"
                f"2. 【不懂 `{entity_tag}` 怎么当跨国二道贩子？】：先在评论区占坑锁单，转头去国内闲鱼/V2EX 找 `{entity_tag}` 熟手花 ¥100~¥200 搞定，净赚汇率差；\n"
                f"3. 【拆成独立小工具复卖】：把解决「{cleanTitle[:22]}」的脚本打包挂到 Gumroad 上卖 $19。"
            )
        }

    # 2. 针对成人 NSFW / DLsite / Chaturbate / F95zone / 成人 CPA 的一对一拆解
    if any(k in sourceLabel for k in ("DLsite", "Chaturbate", "F95zone", "Itch.io")) or defaultTrack == "nsfw_adult":
        return {
            "pain_point_zh": (
                f"【全球成人/擦边高热标的《{cleanTitle}》实盘拆解】\n"
                f"● 核心数据与原话：{quote1}\n"
                f"● 赚钱逻辑还原：该标的精准踩中了高冲动消费的垂直癖好标签（{entity_tag}），老外付费意愿极强，但普遍存在跨语种未汉化/英化、或社媒引流易封号的痛点。"
            ),
            "solver_case_zh": (
                f"直接借力《{cleanTitle[:32]}》已验证的流量与销量：要么联系原作者免费用 AI 翻译成英文/中文版去 Patreon / Itch.io 五五分成，"
                f"要么套『18+ 防审核二跳页』导流至 CrakRevenue ($3.5~$6/免费注册) 或 Chaturbate (20%终身打赏分成)。"
            ),
            "action_plan_zh": (
                f"1. 【抄爆款钩子】：点开左下角原帖，提取《{cleanTitle[:22]}》的前 5 个高频癖好 Tag 与预览图结构；\n"
                f"2. 【部署防封二跳页】：在监控台『2. 生成工厂』下载 `nsfw_18plus_safe_bridge.html`，填入你的 CrakRevenue / Chaturbate / Patreon 收款链；\n"
                f"3. 【免验证社区截流】：在 X 与 Reddit 免手持验证的垂直 NSFW 版块发高悬念预览图，引导点击主页二跳链变现。"
            ),
            "platform_ecology_tip_zh": (
                f"🔥 针对《{cleanTitle[:25]}》的防封与高转化细节：\n"
                f"● 严禁在 X 或 Reddit 直接发成人联盟裸链（必被爬虫秒封）！必须经过 18+ 二跳白名单页过滤审核机器人；\n"
                f"● 预览图采用『前 2 张反差剧情 + 第 3 张关键部位打码留悬念』，点击转化率比普通图高 3 倍。"
            ),
            "reverse_money_idea_zh": (
                f"🔄 围绕《{cleanTitle[:25]}》的 3 条逆向赚钱门道（自己不创作怎么赚）：\n"
                f"1. 【空手套白狼做跨语种发行总代】：直接给《{cleanTitle[:20]}》的作者发私信，免费用 AI 帮他翻译嵌字成英文版发往欧美 Patreon / Gumroad 收美金，五五分账；\n"
                f"2. 【给成人博主卖“防封二跳页”铲子】：去 r/NSFWCreators 找苦于封号的创作者，按 $49/次 帮她们部署防封二跳页与自动引流脚本；\n"
                f"3. 【OGAds 99% 任务锁截流白嫖党】：针对全网搜《{cleanTitle[:20]}》免费资源的流量，做个下载引导页套上 99% 进度条任务锁，老外每完成一次 30 秒验证你净赚 $1.5~$4！"
            )
        }

    # 3. 针对免费悬赏急单 (Reddit slavelabour / forhire / DoneDirtCheap / V2EX / BHW Hire) 的一对一拆解
    is_bounty = defaultTrack == "bounty_direct" or bool(re.search(r'\[task\]|\[hiring\]|\$bid|forhire|slavelabour|donedirtcheap|\bwtb\b', blob, re.I))
    if is_bounty:
        return {
            "pain_point_zh": (
                f"【来自 {sourceLabel} 的免费直联雇主急单：《{cleanTitle}》】\n"
                f"● 雇主原始需求：「{quote1}」\n"
                f"● 补充要求：「{quote2}」（涉及工具/技能：{entity_tag} | 预算/指标：{price_str} | 当前仅 {cmts} 条评论，0平台投标费）。"
            ),
            "solver_case_zh": (
                f"雇主急需解决「{cleanTitle[:35]}」，在 {sourceLabel} 发帖就是为了跳过 Upwork 的高额抽成和繁琐流程！"
                f"趁刚发出不久，直接围绕 `{entity_tag}` 用 AI 在 5 分钟内跑出前 15~20 行结果或 Demo 截图甩进他私信，当场截胡。"
            ),
            "action_plan_zh": (
                f"1. 【5分钟做出「{cleanTitle[:22]}」真实小样】：点开原帖，把雇主要求的「{quote1[:40]}...」丢给 Claude/Python，生成前 20 行真实 Excel 数据或初步界面截图；\n"
                f"2. 【评论占坑 + 私信甩图】：先在原帖回 `$bid` 占坑，紧接着立刻点开雇主头像发私信（DM），第一句话直接发样本图：『I already built a working sample for your {entity_tag} task (screenshot attached). Can deliver the full version in 1 hour.』；\n"
                f"3. 【收款交货】：通过 PayPal / Wise / USDT 收取定金或全款后交付。"
            ),
            "platform_ecology_tip_zh": (
                f"🔥 针对本单（当前仅 {cmts} 条评论）的 10 分钟黄金抢单门道：\n"
                f"● 悬赏贴发出 30 分钟后就会涌入大批印度/东欧接单党排队复读 '$bid' 把价格压到 $5~$10；\n"
                f"● 绝不能只留言傻等！必须在发帖前 10~30 分钟内直接把针对 `{entity_tag}` 做好的样本截图发进雇主私信，老外看到现成结果 90% 会直接按原价把单给你！"
            ),
            "reverse_money_idea_zh": (
                f"🔄 围绕「{cleanTitle[:28]}」的 3 条逆向赚钱门道：\n"
                f"1. 【零技术小白做跨国二道贩子】：你不用自己会 `{entity_tag}`！接下老外这笔美金单（{price_str}）后，立刻去国内闲鱼或淘宝搜 `{entity_tag} 代做`，花 ¥50~¥100 人民币让国内大学生做完发你，净赚 6 倍汇率差；\n"
                f"2. 【把交货产物变成 $29 标品复卖】：既然这位雇主肯花钱做「{cleanTitle[:22]}」，说明同行也有同样刚需！交货后脱敏挂到 Gumroad 上按 $29/份 自动售卖；\n"
                f"3. 【反扒雇主的上游暴利项目】：点进这位雇主的主页历史发帖记录，看他花钱让你做 `{entity_tag}` 背后是在跑什么赚钱业务，直接把他的整套路子抄过来！"
            )
        }

    # 4. 针对 CPA / 灰产套利 / 黑帽 SEO / 网赚野路子 (BHW / AffiliateFix / r/blackhat / r/beermoney 等) 的一对一拆解
    if defaultTrack == "gray_arb" or any(k in sourceLabel for k in ("BlackHatWorld", "AffiliateFix", "CPA", "黑帽", "网赚", "野路子", "倒爷")):
        return {
            "pain_point_zh": (
                f"【{sourceLabel} 灰产/套利实战拆解：《{cleanTitle}》】\n"
                f"● 核心玩法原话还原：「{quote1}」\n"
                f"● 关键实操细节：「{quote2}」（涉及工具/渠道：{entity_tag} | 提及收益/热度：{price_str}，{ups}赞·{cmts}评）。"
            ),
            "solver_case_zh": (
                f"本帖揭秘或探讨了围绕「{cleanTitle[:35]}」的流量截流与套利打法（{entity_tag}）。"
                f"核心赚钱逻辑是利用免费社媒/高权重寄生虫页面截流精准搜索词，导流至 CPA 任务锁（OGAds/AdBlueMedia）或高佣 Affiliate Offer 实现自动化变现。"
            ),
            "action_plan_zh": (
                f"1. 【提取本帖「{cleanTitle[:22]}」的流量入口】：点开原帖直链，看楼主及高赞回复是用哪个具体流量源（如 TikTok 切片 / Reddit 楼中楼 / Medium 寄生虫 / 自动化脚本）在跑 `{entity_tag}`；\n"
                f"2. 【配置高转化落地锁】：从监控台『2. 生成工厂』下载 99% 进度条解锁页或防封二跳页，挂上你的 CPA / Affiliate 链接；\n"
                f"3. 【小批量测试放大】：先发 5~10 条测试帖跑通首单转化（First Lead），再通过指纹浏览器 + 住宅 IP 矩阵放大。"
            ),
            "platform_ecology_tip_zh": (
                f"🔥 针对《{cleanTitle[:26]}》的防封号与高 EPC 潜规则：\n"
                f"● 跑 CPA 或灰产截流时，切忌用同一个机房 IP 登录多个账号或直发联盟裸链（必被平台风控团灭）；\n"
                f"● 在热帖评论区截流时，永远去**回复排名前三的高赞评论（抢占楼中楼第一视觉位）**，诱导用户主动私信或点个人简介里的二跳白名单域名。"
            ),
            "reverse_money_idea_zh": (
                f"🔄 围绕《{cleanTitle[:28]}》的 3 条保姆级逆向赚钱门道（不自己跑流量怎么赚）：\n"
                f"1. 【给这群淘金者“卖铲子/卖耗材”】：点开原帖看那 {cmts} 条跟帖里大家最卡哪一步（比如缺老账号、缺 `{entity_tag}` 自动发帖脚本、缺高仿真落地页），你去闲鱼或 GitHub 找现成方案打包按 $29~$49 卖给原帖评论区里想跟风的老外；\n"
                f"2. 【跨国信息差搬运回国内变现（0成本最快见钱）】：老外在《{cleanTitle[:22]}》里实测的这套野路子，国内 99% 的人还没见过！直接用翻译软件整理成中文深度长文发到小红书、公众号或闲鱼，挂载 ¥69~¥199 的『海外最新 {entity_tag} 野路子实操手册/脚本包』直接收人民币；\n"
                f"3. 【二级推荐管道躺赚 5%】：把本帖玩法写成免费保姆级教程，里面附上你的 CPA 联盟（如 OGAds / CrakRevenue）或工具的二级 Referral 链接，别人照着跑赚 $1000，平台自动分你 $50！"
            )
        }

    # 5. 针对 SaaS 软件痛点 / 独立变现复盘 / 实体小老板刚需 的一对一拆解
    return {
        "pain_point_zh": (
            f"【高热痛点与变现复盘《{cleanTitle}》深度还原（{ups}赞 · {cmts}条讨论）】\n"
            f"● 涉及业务与技术栈：{entity_tag}（提及金额/指标：{price_str}）。\n"
            f"● 楼主痛点/复盘原话：「{quote1}」\n"
            f"● 关键细节与槽点：「{quote2}」"
        ),
        "solver_case_zh": (
            f"这篇近 30 天拿了 {ups} 赞、{cmts} 条讨论的热帖，直接用真金白银替你验证了「{cleanTitle[:35]}」的市场刚需！"
            f"普通人切入最快的方式是围绕 `{entity_tag}` 拆出一个『$29 免月租一次性买断小工具』、『Done-For-You 人工代配置服务 ($69/次)』或『跨国信息差搬运』。"
        ),
        "action_plan_zh": (
            f"1. 【去原帖 {cmts} 条评论里精准抓活体买家】：点开左下角原帖直链，重点找评论区里抱怨『我也卡在 {entity_tag} 这一步』或求平替工具的用户；\n"
            f"2. 【用 AI 极速封装 `{entity_tag}` 方案】：花 1 小时用 Cursor 把该痛点做成免安装本地脚本、浏览器插件或 Excel/Notion 自动化模板；\n"
            f"3. 【免费小样钩子锁单】：在原帖高赞评论楼中楼回复干货，附上『前 20 条数据免费帮跑验货』，引导客户私信付款。"
        ),
        "platform_ecology_tip_zh": (
            f"🔥 针对《{cleanTitle[:26]}》在 {sourceLabel} 的高转化截流门道：\n"
            f"● 绝不在主贴下一上来就甩 Gumroad 收款链接（易被版主当广告删帖）；先在评论区贴出你用 `{entity_tag}` 跑通的结果截图，让痛点客户主动点你头像发私信求买，转化率超 50%！"
        ),
        "reverse_money_idea_zh": (
            f"🔄 围绕《{cleanTitle[:28]}》的 3 条保姆级逆向赚钱门道：\n"
            f"1. 【跨国信息差搬运（0技术门槛，当天见钱）】：把这篇海外高赞贴《{cleanTitle[:22]}》里的真实数据（{price_str}）与核心思路翻译整理成中文笔记，发到小红书/公众号/B站，售卖 ¥49~¥99 的配套中文工具包或教程；\n"
            f"2. 【不卖软件卖“人工代搞定服务（Done-For-You）”】：看懂这篇帖子的欧美小老板里，90% 懒得自己动手配置 `{entity_tag}`。你在评论区或 Fiverr 挂出『24小时内帮你照这套方案配好全套流程（收 $79）』，接到单后用 AI 弄或转包给国内闲鱼技术员；\n"
            f"3. 【专盯高价竞品的 1 星差评区截胡】：去 G2 / Trustpilot 找到本帖提及赛道里月费 $99+ 的老牌软件，直接私联最新打 1 星差评的付费老板，推销你的 $29 一次性买断平替版！"
        )
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

    # 1. 悬赏单（bounty_direct）超过 2 小时（7200秒）直接丢弃不入库
    if not isBaseCard and track == "bounty_direct":
        if (time.time() - createdTs) > 7200:
            return None

    # 2. 入库前先判断是否为真实可靠的赚钱项目/需求，过滤无效水贴
    if not isBaseCard and not is_valid_money_opportunity(title, pain, track, source_platform):
        return None

    ups = int(rawItem.get("ups") or 0)
    cmts = int(rawItem.get("num_comments") or 0)

    u = generate_unique_non_template_analysis(title, pain, source_platform, rawItem.get("source_url", ""), track, ups, cmts)
    return {
        "id": rawItem.get("id") or f"sig_{abs(hash(title))}",
        "track": track,
        "title_zh": title,
        "summary_one_line": rawItem.get("summary_one_line") or f"{source_platform} 核验收录",
        "deal_fact_zh": rawItem.get("deal_fact_zh") or extract_honest_deal_fact(f"{title} {pain}", ups, cmts),
        "pain_point_zh": u["pain_point_zh"],
        "solver_case_zh": u["solver_case_zh"],
        "platform_ecology_tip_zh": u["platform_ecology_tip_zh"],
        "reverse_money_idea_zh": u["reverse_money_idea_zh"],
        "action_plan_zh": u["action_plan_zh"],
        "feasibility_pct": 92 if track == "bounty_direct" else 87,
        "time_to_money": "当天~24h" if track == "bounty_direct" else "2~7天",
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
    # 通道 1：优先通过 PullPush.io 免盾镜像获取（在 GitHub Actions 无住宅 IP 环境下 100% 免 403/429）
    try:
        sort_by = "score" if mode == "top_month" else "created_utc"
        after_ts = int(time.time()) - (30 * 86400) if mode == "top_month" else int(time.time()) - 7200
        pp_url = f"https://api.pullpush.io/reddit/search/submission/?subreddit={sub}&size={limit}&sort=desc&sort_type={sort_by}&after={after_ts}"
        raw_pp = http_get(pp_url, timeout=14)
        pp_data = json.loads(raw_pp).get("data", [])
        if not pp_data and mode != "top_month":
            pp_url2 = f"https://api.pullpush.io/reddit/search/submission/?subreddit={sub}&size={limit}&sort=desc&sort_type=created_utc"
            pp_data = json.loads(http_get(pp_url2, timeout=14)).get("data", [])
        posts = []
        for d in pp_data:
            if not d.get("title"):
                continue
            posts.append({
                "id": str(d.get("id")),
                "title": d.get("title"),
                "selftext": d.get("selftext") or "",
                "author": d.get("author") or "",
                "created_utc": int(d.get("created_utc") or time.time()),
                "ups": int(d.get("score") or 5),
                "num_comments": int(d.get("num_comments") or 1),
                "permalink": f"/r/{sub}/comments/{d.get('id')}/"
            })
        if posts:
            print(f"[SOURCE OK] Reddit r/{sub}: PullPush 免盾通道成功获取 {len(posts)} 条")
            return posts
    except Exception as exc:
        errors.append(f"PullPush: {type(exc).__name__}: {exc}")

    # 通道 2：配置了住宅 IP 时直连 Reddit 官方 JSON
    reddit_headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "application/json"
    }
    path = f"top.json?t=month&limit={limit}&raw_json=1" if mode == "top_month" else f"new.json?limit={limit}&raw_json=1"
    for host in ("www.reddit.com", "old.reddit.com"):
        try:
            raw = http_get(f"https://{host}/r/{sub}/{path}", timeout=12, headers=reddit_headers)
            data = json.loads(raw)
            posts = [c["data"] for c in data.get("data", {}).get("children", [])]
            if posts:
                print(f"[SOURCE OK] Reddit r/{sub}: 住宅代理直连成功获取 {len(posts)} 条")
                return posts
        except Exception as exc:
            errors.append(f"{host}: {type(exc).__name__}: {exc}")

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

    # 1. Hacker News（每个词严格限流 8 条，防止霸屏）
    hn_queries = [
        ("willing to pay OR too expensive alternative", "pain_saas", "HN 近30天痛点求平替"),
        ("Show HN revenue OR MRR OR first sale OR Stripe", "pain_saas", "HN 近30天真实变现复盘"),
        ("affiliate OR arbitrage OR SEO OR lead generation", "gray_arb", "HN 近30天流量套利门道"),
        ("OnlyFans OR NSFW OR adult OR AI companion", "nsfw_adult", "HN 成人与AI伴侣变现")
    ]
    for query, trk, label in hn_queries:
        try:
            url = f"https://hn.algolia.com/api/v1/search?tags=story&numericFilters=created_at_i>{thirty_days_ago_ts},points>2&hitsPerPage=8&query=" + urllib.parse.quote(query)
            data = json.loads(http_get(url, timeout=15))
            for hit in data.get("hits", []):
                object_id = str(hit.get("objectID") or "")
                title = clean_raw_html(hit.get("title") or hit.get("story_title") or "")
                if not object_id or not title:
                    continue
                item = sanitizeAndUpgradeSignal({
                    "id": f"hn_{object_id}", "created_ts": int(hit.get("created_at_i") or (now_ts - 14400)),
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

    # 2. 全网搜索（CPA、成人CPA、黑帽SEO、赚钱复盘、短视频套利）：走 PullPush 免盾搜索，解决 403！
    global_searches = [
        ("CPA content locker OGAds", "gray_arb", "全网搜索·CPA与任务锁门道"),
        ("CrakRevenue adult affiliate Fanvue", "nsfw_adult", "全网搜索·成人CPA与AI擦边"),
        ("parasite SEO blackhat expired domain", "gray_arb", "全网搜索·黑帽寄生虫SEO"),
        ("made my first 1000 side hustle", "pain_saas", "全网搜索·近30天亲测赚钱复盘"),
        ("TikTok shop affiliate digital product", "gray_arb", "全网搜索·短视频带货与虚拟品套利")
    ]
    for q_str, trk, label in global_searches:
        try:
            pp_url = f"https://api.pullpush.io/reddit/search/submission/?q={urllib.parse.quote(q_str)}&size=12&sort=desc&sort_type=score"
            pp_data = json.loads(http_get(pp_url, timeout=15)).get("data", [])
            cnt = 0
            for d in pp_data:
                title = clean_raw_html(d.get("title", ""))
                if not title:
                    continue
                sub_name = d.get("subreddit", "all")
                post_id = d.get("id", "")
                link = d.get("full_link") or f"https://www.reddit.com/r/{sub_name}/comments/{post_id}/"
                item = sanitizeAndUpgradeSignal({
                    "id": f"rds_{post_id}", "created_ts": int(d.get("created_utc") or (now_ts - 7200)),
                    "track": trk, "ups": int(d.get("score") or 10), "num_comments": int(d.get("num_comments") or 2),
                    "title_zh": f"【{label} · r/{sub_name}】{title}",
                    "pain_point_zh": d.get("selftext") or title,
                    "source_platform": label,
                    "source_url": link, "solver_url": link
                })
                if item:
                    items.append(item)
                    cnt += 1
            print(f"[SOURCE OK] {label}: {cnt} 条")
        except Exception as exc:
            print(f"[SOURCE WARN] {label}: {exc}")

    # 3. V2EX 免费直联外包与酷工作急单（0平台费，超过2小时自动过滤）
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

    # 4. BlackHatWorld 6大核心分版（开启 allow_jina_fallback=True 过盾穿透，解决 403）
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
            items.extend(parsed)
            print(f"[SOURCE OK] {bhw_label}: {len(parsed)} 条")
        except Exception as exc:
            print(f"[SOURCE WARN] {bhw_label}: {exc}")

    # 5. AffiliateFix 两大 CPA 专区（开启 allow_jina_fallback=True 解决 403）
    for af_path, af_label in (("whats-new/posts/", "AffiliateFix CPA最新实战"), ("forums/cpa-affiliate-networks.9/", "AffiliateFix CPA联盟网赚")):
        try:
            af_url = f"https://www.affiliatefix.com/{af_path}"
            raw_html = http_get(af_url, timeout=20, allow_jina_fallback=True)
            parsed = parse_links_from_html_or_jina(
                raw_html, "https://www.affiliatefix.com", "/threads/",
                af_label, "gray_arb", now_ts, max_items=10
            )
            items.extend(parsed)
            print(f"[SOURCE OK] {af_label}: {len(parsed)} 条")
        except Exception as exc:
            print(f"[SOURCE WARN] {af_label}: {exc}")

    # 6. 全球成人暴利矩阵：Chaturbate（内置默认码 Z1n2p 免配置）+ F95zone + Itch.io NSFW + DLsite（限流6条）
    wm = os.environ.get("CHATURBATE_WM", "Z1n2p").strip() or "Z1n2p"
    try:
        cb_url = f"https://chaturbate.com/api/public/affiliates/onlinerooms/?wm={urllib.parse.quote(wm)}&format=json"
        data = json.loads(http_get(cb_url, timeout=15))
        rooms = data.get("results", []) if isinstance(data, dict) else data
        top_rooms = sorted(rooms, key=lambda x: int(x.get("num_users") or 0), reverse=True)[:10]
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
                "deal_fact_zh": f"✅ 官方API实时在线打赏金主：{viewers} 人", "source_platform": "Chaturbate 成人直播榜",
                "source_url": source_url, "solver_url": source_url,
            })
            if item:
                items.append(item)
        print(f"[SOURCE OK] Chaturbate: {len(top_rooms)} 条")
    except Exception as exc:
        print(f"[SOURCE WARN] Chaturbate: {exc}")

    try:
        f95_raw = http_get("https://f95zone.to/sam/latest_alpha/", timeout=20, allow_jina_fallback=True)
        f95_parsed = parse_links_from_html_or_jina(
            f95_raw, "https://f95zone.to", "/threads/",
            "F95zone 成人游戏/Mod社区", "nsfw_adult", now_ts, max_items=10
        )
        items.extend(f95_parsed)
        print(f"[SOURCE OK] F95zone: {len(f95_parsed)} 条")
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

    # 7. DEV.to 近30天独立开发与自动化变现热榜
    for dtag in ("saas", "sideprojects", "indiehackers", "automation"):
        try:
            dev_data = json.loads(http_get(f"https://dev.to/api/articles?tag={dtag}&top=30&per_page=8", timeout=12))
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

    print(f"[{now_str}] 🚀 正在执行 v11.4 纯免费接单源 + 全平台均衡扫描 (悬赏限定2h内并按最新倒序)...")

    # 1. 抓快轨免费悬赏急单
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

    # 2. 抓 GitHub 一手免费实时悬赏（限定过去 2 小时内新开）
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

    # 自动从数据库删除：1. 超过 2 小时（7200秒）的悬赏急单；2. 之前残留的付费外包站/Flippa/旧5行死模板数据
    c.execute("DELETE FROM signals WHERE track = 'bounty_direct' AND id NOT LIKE 'base_%' AND created_ts < ?", (now_ts - 7200,))
    c.execute("DELETE FROM signals WHERE source_platform LIKE '%Upwork%' OR source_platform LIKE '%PeoplePerHour%' OR source_platform LIKE '%Freelancer%' OR source_platform LIKE '%Flippa%'")
    c.execute("DELETE FROM signals WHERE solver_case_zh LIKE '%顺应当前热度，围绕该标的提供%'")

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

    # 强制多网站均衡配额：每个网站来源最多输出 8~12 条（悬赏除外），彻底防止 HN 或 DLsite 霸屏
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
    print(f"[{now_str}] v11.4 满血均衡扫描完毕！共输出 {len(rows)} 条非模板化多平台数据（超2h旧悬赏与付费投标站已清理）。")
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
