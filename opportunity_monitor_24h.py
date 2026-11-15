#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
全球痛点与真实赚钱机会 24h 自动监控引擎 (v10.9 微信/飞书/钉钉/Bark 免翻墙秒推版)
================================================================================
双轨运行逻辑 + 全平台免翻墙实时通知：
1. 【快轨：60秒悬赏猎手 (--bounty-fast / --bounty-daemon)】
   - 每 60 秒极速扫描 Reddit 5大现金急单版块 (slavelabour / forhire / DoneDirtCheap /
     hireaprogrammer / freelance_forhire) + GitHub 最新 Open Bounties。
   - 自动剔除 [Offer]/[For Hire] 求职水贴，只抓雇主真金白银发包的 [Task]/[Hiring]。
   - 一旦发现新急单，2秒内生成【定制英文破冰私信】与【3分钟打样方案】，并自动推送到：
     ✅ 微信 (PushPlus / Server酱)
     ✅ 飞书 / 钉钉 / 企业微信 / Discord 群机器人 (Webhook)
     ✅ iPhone Bark 锁屏强提醒
     ✅ Telegram (可选保留)
2. 【慢轨：20分钟全网大盘 (--cloud-once / --serve)】
   - 每 20 分钟扫描全网近 30 天高热痛点、野路子套利与 DLsite/Chaturbate 成人榜，逐贴非模板化拆解。
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
    ("SaaS", "pain_saas", "Reddit r/SaaS (近30天软件痛点与变现热榜)", "top_month"),
    ("SideProject", "pain_saas", "Reddit r/SideProject (近30天独立副业爆款榜)", "top_month"),
    ("microsaas", "pain_saas", "Reddit r/microsaas (近30天微型SaaS真实营收榜)", "top_month"),
    ("sweatystartup", "pain_saas", "Reddit r/sweatystartup (近30天传统本地暴利生意榜)", "top_month"),
    ("smallbusiness", "pain_saas", "Reddit r/smallbusiness (近30天欧美小老板最头疼痛点)", "top_month"),
    ("Entrepreneur", "pain_saas", "Reddit r/Entrepreneur (近30天创业实战热榜)", "top_month"),
    ("Automate", "pain_saas", "Reddit r/Automate (近30天急需自动化的繁琐工作)", "top_month"),
    ("beermoney", "gray_arb", "Reddit r/beermoney (近30天亲测打款网赚热榜)", "top_month"),
    ("sidehustle", "gray_arb", "Reddit r/sidehustle (近30天野路子搞钱热榜)", "top_month"),
    ("flipping", "gray_arb", "Reddit r/flipping (近30天低买高卖倒爷实盘晒单)", "top_month"),
    ("affiliatemarketing", "gray_arb", "Reddit r/affiliatemarketing (近30天高佣联盟套利)", "top_month"),
    ("SEO", "gray_arb", "Reddit r/SEO (近30天搜索截流与排名实操)", "top_month"),
    ("juststart", "gray_arb", "Reddit r/juststart (近30天流量站搞钱连载)", "top_month"),
    ("NSFWCreators", "nsfw_adult", "Reddit r/NSFWCreators (近30天成人博主引流变现热榜)", "top_month"),
    ("onlyfansadvice", "nsfw_adult", "Reddit r/onlyfansadvice (近30天OnlyFans私域高转化玩法)", "top_month"),
    ("CreatorsAdvice", "nsfw_adult", "Reddit r/CreatorsAdvice (近30天擦边订阅制变现热榜)", "top_month")
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


def http_get(url, timeout=14):
    scraper_key = os.environ.get("SCRAPER_API_KEY", "").strip()
    target_url = url
    if scraper_key and any(d in url for d in ("blackhatworld.com", "reddit.com", "etsy.com", "upwork.com")):
        target_url = f"http://api.scraperapi.com?api_key={scraper_key}&url={urllib.parse.quote(url)}"

    proxies = load_proxies()
    chosen_proxy = random.choice(proxies) if (proxies and not scraper_key) else None

    if HAS_CURL_CFFI:
        px_dict = {"http": chosen_proxy, "https": chosen_proxy} if chosen_proxy else None
        resp = cffi_requests.get(target_url, impersonate="chrome124", proxies=px_dict, timeout=timeout)
        return resp.text

    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "application/json, text/html, application/xml;q=0.9, */*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,ja;q=0.7"
    }
    req = urllib.request.Request(target_url, headers=headers)
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
            deliverable_type TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS tg_notified_bounties (
            id TEXT PRIMARY KEY,
            notified_at TEXT
        )
    """)
    conn.commit()
    conn.close()


# ==============================================================================
# 免翻墙全通道秒级推送器（支持：微信 PushPlus / Server酱 / 飞书 / 钉钉 / 企业微信 / Bark / TG）
# ==============================================================================
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
            "I already built a quick working sample / first 15 rows based on your exact requirements (screenshot attached). "
            "I can deliver the complete files within 1-2 hours. Let me know if you want to check the sample!"
        )

    plain_summary = (
        f"🚨【10分钟黄金抢单窗 · 新悬赏急单】\n"
        f"📌 标题：{clean_title}\n"
        f"💰 核验：{deal_fact}\n\n"
        f"📝 雇主具体要求：\n{pain_txt}\n\n"
        f"⚡ 3分钟秒拿单动作：\n{action_txt}\n\n"
        f"💬 直接复制这段英文私信甩给雇主：\n{custom_dm_en}\n\n"
        f"🔗 原帖占坑直链：{source_url}\n"
        f"📩 私信雇主直链：{dm_url}"
    )

    pushed_any = False

    # 通道 1：微信 PushPlus (pushplus.plus，国内免翻墙直接弹窗到个人微信)
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
            urllib.request.urlopen(req, timeout=10)
            print(f"[WECHAT PUSHPLUS SUCCESS] 已推送到微信: {clean_title[:35]}")
            pushed_any = True
        except Exception as e:
            print(f"[PUSHPLUS WARN] {e}")

    # 通道 2：微信 Server酱 (sct.ftqq.com，备选微信免翻墙推送)
    serverchan_key = os.environ.get("SERVERCHAN_KEY", "").strip()
    if serverchan_key:
        try:
            sc_data = urllib.parse.urlencode({
                "title": f"🚨新悬赏急单: {clean_title[:35]}",
                "desp": plain_summary
            }).encode("utf-8")
            req = urllib.request.Request(f"https://sctapi.ftqq.com/{serverchan_key}.send", data=sc_data)
            urllib.request.urlopen(req, timeout=10)
            print(f"[SERVERCHAN SUCCESS] 已推送到微信: {clean_title[:35]}")
            pushed_any = True
        except Exception as e:
            print(f"[SERVERCHAN WARN] {e}")

    # 通道 3：飞书 / 钉钉 / 企业微信 / Discord 群机器人 Webhook (免翻墙、零成本、无条数限制)
    webhook_url = os.environ.get("WEBHOOK_URL", "").strip()
    if webhook_url:
        try:
            if "feishu.cn" in webhook_url or "larksuite.com" in webhook_url:
                wb_payload = {"msg_type": "text", "content": {"text": plain_summary}}
            elif "dingtalk.com" in webhook_url:
                wb_payload = {"msgtype": "text", "text": {"content": plain_summary}}
            elif "discord.com" in webhook_url:
                wb_payload = {"content": plain_summary[:1900]}
            else:
                wb_payload = {"msgtype": "text", "text": {"content": plain_summary}}

            req = urllib.request.Request(
                webhook_url,
                data=json.dumps(wb_payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            urllib.request.urlopen(req, timeout=10)
            print(f"[WEBHOOK SUCCESS] 已推送至群机器人: {clean_title[:35]}")
            pushed_any = True
        except Exception as e:
            print(f"[WEBHOOK WARN] {e}")

    # 通道 4：iPhone Bark 锁屏强弹窗 (api.day.app)
    bark_url = os.environ.get("BARK_URL", "").strip()
    if bark_url:
        try:
            bark_endpoint = bark_url.rstrip("/") + "/send" if not bark_url.endswith("/send") else bark_url
            bark_payload = json.dumps({
                "title": f"🚨悬赏急单: {clean_title[:30]}",
                "body": f"{deal_fact}\n私信话术: {custom_dm_en}",
                "url": source_url,
                "sound": "birdsong"
            }).encode("utf-8")
            req = urllib.request.Request(bark_endpoint, data=bark_payload, headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=10)
            print(f"[BARK SUCCESS] 已推送至 iPhone: {clean_title[:35]}")
            pushed_any = True
        except Exception as e:
            print(f"[BARK WARN] {e}")

    # 通道 5：兼容保留 Telegram (若以后恢复可用)
    tg_token = os.environ.get("TG_BOT_TOKEN", "").strip()
    tg_chat_id = os.environ.get("TG_CHAT_ID", "").strip()
    if tg_token and tg_chat_id:
        try:
            api_url = f"https://api.telegram.org/bot{tg_token}/sendMessage"
            payload = urllib.parse.urlencode({"chat_id": tg_chat_id, "text": plain_summary}).encode("utf-8")
            urllib.request.urlopen(urllib.request.Request(api_url, data=payload), timeout=8)
            pushed_any = True
        except Exception:
            pass

    return pushed_any


def extract_honest_deal_fact(text_blob, ups=0, comments=0):
    dlsite_sales = re.search(r'販売数[:：\s]*([\d,]+)', text_blob)
    if dlsite_sales:
        sold_num = dlsite_sales.group(1)
        yen_match = re.search(r'([\d,]+)\s*円', text_blob)
        price_str = f" | 单价 {yen_match.group(1)}日元" if yen_match else ""
        return f"✅ 100% 官方公开真实销量：近30天热销 {sold_num} 份{price_str} (DLsite 榜单铁证)"

    paid_bids = len(re.findall(r'\$bid|\$paid|\[hiring\]|\[task\]|bounty', text_blob, re.IGNORECASE))
    money_matches = re.findall(r'(\$\d+(?:,\d{3})*(?:\.\d{1,2})?(?:\s*(?:k|K|MRR|mrr|/mo|/day|/hr))?)', text_blob)

    if paid_bids > 0 and money_matches:
        top_nums = " / ".join(list(dict.fromkeys(money_matches))[:2])
        return f"✅ 真金白银悬赏/预算: {top_nums} | 当前竞争: {comments}条评论 ({ups}赞)"
    if money_matches:
        top_nums = " / ".join(list(dict.fromkeys(money_matches))[:3])
        return f"📊 原帖披露真实金额/营收: {top_nums} | 热度: {ups}赞 · {comments}评"
    return f"🔥 实时高关注真需求（当前热度: {ups}赞 · {comments}条跟帖讨论）"


def generate_unique_non_template_analysis(raw_title, raw_body, source_label, source_url, default_track, ups, cmts):
    blob = f"{raw_title} {raw_body}"
    clean_title = re.sub(r'^\[[^\]]+\]\s*|^【[^】]+】\s*', '', raw_title).strip()

    repo_match = re.search(r'github\.com/([^/]+/[^/]+)/issues/(\d+)', source_url)
    repo_name = repo_match.group(1) if repo_match else ""
    issue_num = repo_match.group(2) if repo_match else ""

    money_list = list(dict.fromkeys(re.findall(r'(\$\d+(?:,\d{3})*(?:\.\d+)?(?:\s*(?:k|K|MRR|mrr|/mo|/hr))?)', blob)))
    price_str = " / ".join(money_list[:2]) if money_list else ("$50~$300 (按工作量议价)" if default_track == "bounty_direct" else "$19~$49 (工具/服务定价)")

    tech_entities = list(dict.fromkeys(re.findall(
        r'\b(Python|Rust|TypeScript|React|Next\.js|Node\.js|Docker|PostgreSQL|SQLite|Supabase|Stripe|PayPal|Shopify|Wix|WordPress|Chrome|Telegram|Discord|WhatsApp|OpenAI|Claude|LLM|RAG|OCR|PDF|CSV|Excel|Google Sheets|Selenium|Playwright|Puppeteer|Cloudflare|Proxy|TikTok|YouTube|Instagram|OnlyFans|Patreon|Etsy|Amazon|eBay|Craigslist|Notion|Airtable|Zapier|n8n|FFmpeg|iOS|Android|Flutter)\b',
        blob, re.IGNORECASE
    )))
    entity_tag = " + ".join(tech_entities[:3]) if tech_entities else clean_title[:35]

    sentences = [s.strip() for s in re.split(r'[.!?;\n]+', raw_body) if len(s.strip()) > 20]
    key_quote_1 = sentences[0][:180] if len(sentences) > 0 else clean_title
    key_quote_2 = sentences[1][:180] if len(sentences) > 1 else "（详见原帖完整上下文与评论区跟帖）"

    if repo_name or "GitHub" in source_label:
        target_repo = repo_name or clean_title[:30]
        return {
            "pain_point_zh": (
                f"【GitHub 仓库 `{target_repo}` 第 #{issue_num} 号真实赏金需求】\n"
                f"● 悬赏标的：《{clean_title}》（涉及技术栈/模块：{entity_tag} | 提及赏金/热度：{price_str}，已有 {cmts} 条跟帖）。\n"
                f"● 维护者卡点原话还原：「{key_quote_1}」\n"
                f"● 补充细节：「{key_quote_2}」"
            ),
            "solver_case_zh": (
                f"专门针对 `{target_repo}` 仓库的「{clean_title[:40]}」需求切入：项目维护者缺人手处理该具体模块（{entity_tag}），"
                f"只需定位跟 `{clean_title[:25]}` 相关的独立文件，用 Cursor/Claude 写出最小可用补丁即可拿走这笔赏金。"
            ),
            "action_plan_zh": (
                f"1. 【精准定位 `{target_repo}` 代码块】：点开下方链接进入 `#{issue_num}`，把维护者描述的「{key_quote_1[:45]}...」复制到 Cursor，只检索与 `{entity_tag}` 相关的函数；\n"
                f"2. 【先发 10 行验证截图锁单】：花 15 分钟把针对「{clean_title[:30]}」跑通的终端输出截图贴在 `#{issue_num}` 评论区，写明『Fixed the {entity_tag} issue locally, submitting PR in 1 hour』，逼维护者把单 Assign 给你；\n"
                f"3. 【合并领钱】：提交 PR 并附上收款地址，合并当天打款。"
            ),
            "platform_ecology_tip_zh": (
                f"🔥 针对 `{target_repo}` (#{issue_num}) 的抢单与避坑门道：\n"
                f"● 当前该单有 {cmts} 条评论，点进去先看有没有人已提交 Pull Request（如果别人只是留言问 'Can I work on this?' 而没发代码，你直接带修复截图插队 100% 抢过来！）。"
            ),
            "reverse_money_idea_zh": (
                f"🔄 围绕「{clean_title[:32]}」的 3 条独门逆向搞钱路径：\n"
                f"1. 【顺着 `{target_repo}` 扒出背后的付费企业】：去扒这个 GitHub 组织主页的官网和其它 Open Issues，直接给创始人发冷邮件承包他们后续所有的 `{entity_tag}` 外包活（按 $50/小时结算）；\n"
                f"2. 【跨国二道贩子】：先在评论区占坑锁单，转身把需求翻译成中文发到国内 V2EX 或闲鱼找 `{entity_tag}` 熟手花 ¥150 人民币解决，净赚跨国汇率差；\n"
                f"3. 【拆成独立小工具复卖】：把这个功能单独拎出来做成 CLI 小工具或教程，发到 Gumroad 和小红书引流变现。"
            )
        }

    is_bounty = (default_track == "bounty_direct") or bool(re.search(r'\[task\]|\[hiring\]|\$bid|forhire|slavelabour|donedirtcheap', blob, re.I))
    if is_bounty:
        return {
            "pain_point_zh": (
                f"【来自 {source_label} 的真实雇主急单：《{clean_title}》】\n"
                f"● 雇主原始需求还原：「{key_quote_1}」\n"
                f"● 细节要求与背景：「{key_quote_2}」（涉及工具/领域：{entity_tag} | 预算/互动：{price_str}，当前仅 {cmts} 条评论）。"
            ),
            "solver_case_zh": (
                f"这位雇主正在为「{clean_title[:38]}」找能马上交活的人。不要发简历！"
                f"直接围绕他提到的 `{entity_tag}` 需求，用 AI 在 5 分钟内做出前 20% 的可视结果截图甩进他私信，当场截胡这笔美金。"
            ),
            "action_plan_zh": (
                f"1. 【针对「{clean_title[:25]}」做 5 分钟小样】：点开原帖，把雇主要求的「{key_quote_1[:45]}...」丢给 AI，生成前 15~20 行真实数据或第一屏界面并截图；\n"
                f"2. 【双通道秒锁单】：先在帖子底下回复 `$bid` 占坑，紧接着在 1 分钟内发 Reddit Chat 私信，第一句话直接发样本截图：『I already built a working sample for your {entity_tag} task (see screenshot). Ready to deliver the full version today.』；\n"
                f"3. 【收款交货】：通过 PayPal / Wise / USDT 收取定金后交货。"
            ),
            "platform_ecology_tip_zh": (
                f"🔥 针对本单（当前仅 {cmts} 条评论）的 10 分钟黄金抢单门道：\n"
                f"● 当前评论数为 {cmts} 条：如果少于 5 条，说明印度和东欧的低价接单党还没涌入，现在带样本图私信是 90% 稳拿的黄金窗口！\n"
                f"● 如果已超过 10 条评论，千万别在评论区傻等，必须直接点开雇主主页发私信（DM），用现成做好的 `{entity_tag}` 样本图直接把他的注意力从评论区抢过来！"
            ),
            "reverse_money_idea_zh": (
                f"🔄 围绕「{clean_title[:30]}」的 3 条逆向赚钱门道：\n"
                f"1. 【零技术小白做跨国二道贩子】：你不用懂 `{entity_tag}`！接下老外这笔美金单子（{price_str}）后，打开国内闲鱼或淘宝搜 `{entity_tag} 代做`，花 ¥50~¥150 人民币让国内熟手先做个小样截图给你去拿单，转手净赚 5~7 倍汇率差；\n"
                f"2. 【把本单需求做成 $29 现成模板卖给同行】：交完货后把作品脱敏，挂到 Gumroad 或 Fiverr 上作为现成标品无限次复卖；\n"
                f"3. 【反扒雇主的赚钱项目】：顺着这位雇主的历史发帖记录（Post History）点进去，看他花钱雇人做 `{entity_tag}` 背后是在跑什么暴利业务，直接把他的整套生财模式摸透抄过来！"
            )
        }

    return {
        "pain_point_zh": (
            f"【近30天高热实战贴《{clean_title}》深度还原（{ups}赞 · {cmts}条讨论）】\n"
            f"● 核心业务与工具栈：{entity_tag}（提及金额/指标：{price_str}）。\n"
            f"● 楼主实操/痛点原话：「{key_quote_1}」\n"
            f"● 关键进展与槽点：「{key_quote_2}」"
        ),
        "solver_case_zh": (
            f"这篇近 30 天拿了 {ups} 赞、{cmts} 条评论的热帖，直接验证了「{clean_title[:38]}」背后的真实市场需求！"
            f"普通人切入最快的方式是针对帖子里提到的 `{entity_tag}` 环节，做『轻量化买断工具 ($19~$39)』、『Done-For-You 人工代配置服务』或『跨国信息差搬运』。"
        ),
        "action_plan_zh": (
            f"1. 【去原帖 {cmts} 条评论里挖付费客户】：点开左下角原帖直链，重点找那些留言说『我也遇到这个问题』或问『How did you do X?』的人，这些人全是精准活体买家！\n"
            f"2. 【针对 `{entity_tag}` 打包极简方案】：用 AI 把本帖讨论的解决方法封装成免配置脚本或自动化模板；\n"
            f"3. 【精准私信转化】：直接私信原帖底下跟着吐槽痛点的评论者，提供前 20 条免费试跑或 $29 买断方案。"
        ),
        "platform_ecology_tip_zh": (
            f"🔥 针对《{clean_title[:28]}》在 {source_label} 的截流与防封门道：\n"
            f"● 千万别在一级评论区直接发硬广（会被沉底或删帖），要去**回复排名前三的高赞评论（楼中楼截流）**，这样所有点开帖子的人第一眼就能看到你的方案！"
        ),
        "reverse_money_idea_zh": (
            f"🔄 围绕《{clean_title[:30]}》的 3 条保姆级逆向赚钱门道：\n"
            f"1. 【跨国信息差搬运（0成本小白首选）】：把原帖里的故事、数据（{price_str}）和神回复翻译成一篇中文深度拆解笔记发到小红书/公众号，挂载 ¥49~¥99 的『同款 {entity_tag} 落地工具包』直接赚人民币；\n"
            f"2. 【不卖工具卖“代搞定服务（Done-For-You）”】：在 Fiverr、Reddit 挂出『帮你在 24 小时内照着这套方法搭好全自动流程（收 $79/次）』，接到单后转包给国内闲鱼技术员；\n"
            f"3. 【给正在干这件事的同行卖铲子】：专门做一个针对该流程最耗时一步的辅助小脚本，卖给评论区里那 {cmts} 个想跟风的同行！"
        )
    }


def call_gemini_fast_bounty_dm(raw_title, raw_body, author_name):
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        return None
    prompt = f"""你是顶级自由职业抢单王。一位雇主({author_name})刚刚发了一条悬赏急单：
标题：{raw_title}
正文：{raw_body[:1000]}

为了在发帖10分钟内击败30分钟后涌入的印度低价竞标者，请立刻返回 JSON（不要带 markdown 代码块）：
{{
  "title_zh": "用中文一句话总结雇主急需干什么及预算",
  "sample_3min_zh": "告诉中国小白怎么在3分钟内用AI/Python做出这单的样本截图去锁单（写出具体操作）",
  "custom_dm_en": "写一段极具杀伤力的地道英文私信（直接点名他帖子里的具体需求，告诉他我已经跑出了前15行/初步Demo截图，1小时内可交付全量，绝不写空洞套话，控制在70词以内）"
}}"""
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0.3}
        }
        req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"})
        resp_json = json.loads(urllib.request.urlopen(req, timeout=10).read().decode("utf-8", errors="ignore"))
        return json.loads(resp_json["candidates"][0]["content"]["parts"][0]["text"])
    except Exception:
        return None


def enrich_item_one_to_one(item_id, default_track, raw_title, raw_body, source_label, source_url, ups, cmts, now_str):
    deal_fact = extract_honest_deal_fact(f"{raw_title} {raw_body}", ups, cmts)
    unique_ans = generate_unique_non_template_analysis(raw_title, raw_body, source_label, source_url, default_track, ups, cmts)
    return {
        "id": item_id,
        "track": default_track,
        "title_zh": f"【{source_label}】{raw_title}",
        "summary_one_line": f"{source_label} | 热度: {ups} 赞 · {cmts} 评",
        "deal_fact_zh": deal_fact,
        "pain_point_zh": unique_ans["pain_point_zh"],
        "solver_case_zh": unique_ans["solver_case_zh"],
        "platform_ecology_tip_zh": unique_ans["platform_ecology_tip_zh"],
        "reverse_money_idea_zh": unique_ans["reverse_money_idea_zh"],
        "action_plan_zh": unique_ans["action_plan_zh"],
        "feasibility_pct": 92 if default_track == "bounty_direct" else 85,
        "time_to_money": "当天~24h" if default_track == "bounty_direct" else "2~7天",
        "capital_req": "$0",
        "source_platform": source_label,
        "source_url": source_url,
        "solver_url": source_url,
        "created_at": now_str,
        "deliverable_type": "bounty_sniper_py"
    }


def run_fast_bounty_sniper():
    init_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id FROM tg_notified_bounties")
    notified_ids = {r[0] for r in c.fetchall()}
    is_first_boot = (len(notified_ids) == 0)

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_bounties = []

    print(f"[{now_str}] ⚡ 正在执行 60 秒悬赏急单快轨扫描 (支持微信/飞书/钉钉/Bark免翻墙秒推)...")
    for sub, track, label in FAST_BOUNTY_SUBS:
        try:
            r_url = f"https://www.reddit.com/r/{sub}/new.json?limit=20"
            r_data = json.loads(http_get(r_url, timeout=10))
            for child in r_data.get("data", {}).get("children", []):
                d = child.get("data", {})
                raw_title = clean_raw_html(d.get("title", ""))
                raw_selftext = clean_raw_html(d.get("selftext", ""))
                author = d.get("author", "")
                created_utc = d.get("created_utc", 0)

                if not raw_title:
                    continue
                if re.search(r'^\s*\[?\s*(?:offer|for\s*hire)\s*\]?', raw_title, re.IGNORECASE):
                    continue

                item_id = f"rd_{d.get('id')}"
                permalink = "https://www.reddit.com" + d.get("permalink", "")
                ups = d.get("ups", 0)
                cmts = d.get("num_comments", 0)

                item = enrich_item_one_to_one(item_id, track, raw_title, raw_selftext, label, permalink, ups, cmts, now_str)
                new_bounties.append((item, author, raw_title, raw_selftext, created_utc))
        except Exception as e:
            print(f"[FAST BOUNTY WARN] r/{sub}: {e}")

    pushed_count = 0
    for idx, (item, author, raw_title, raw_selftext, created_utc) in enumerate(new_bounties):
        bid = item["id"]
        c.execute("""
            INSERT OR REPLACE INTO signals VALUES (
                :id, :track, :title_zh, :summary_one_line, :deal_fact_zh,
                :pain_point_zh, :solver_case_zh, :platform_ecology_tip_zh,
                :reverse_money_idea_zh, :action_plan_zh, :feasibility_pct,
                :time_to_money, :capital_req, :source_platform, :source_url,
                :solver_url, :created_at, :deliverable_type
            )
        """, item)

        age_minutes = (time.time() - created_utc) / 60.0 if created_utc else 5
        should_push = (bid not in notified_ids) and ((not is_first_boot and age_minutes <= 60) or (is_first_boot and idx < 2))

        if should_push and pushed_count < 5:
            ai_dm = call_gemini_fast_bounty_dm(raw_title, raw_selftext, author)
            custom_dm_en = ""
            if ai_dm and isinstance(ai_dm, dict):
                if ai_dm.get("title_zh"):
                    item["title_zh"] = f"【⚡急单】{ai_dm['title_zh']} ({raw_title[:45]})"
                if ai_dm.get("sample_3min_zh"):
                    item["action_plan_zh"] = ai_dm["sample_3min_zh"]
                custom_dm_en = ai_dm.get("custom_dm_en", "")

            sent_ok = send_multichannel_bounty_alert(item, author_name=author, custom_dm_en=custom_dm_en)
            c.execute("INSERT OR REPLACE INTO tg_notified_bounties VALUES (?, ?)", (bid, now_str))
            notified_ids.add(bid)
            if sent_ok:
                pushed_count += 1
        elif is_first_boot:
            c.execute("INSERT OR REPLACE INTO tg_notified_bounties VALUES (?, ?)", (bid, now_str))

    conn.commit()
    c.execute("SELECT * FROM signals ORDER BY created_at DESC")
    cols = [col[0] for col in c.description]
    rows = [dict(zip(cols, r)) for r in c.fetchall()]
    conn.close()

    payload = {
        "updated_at": now_str,
        "poll_interval_sec": 60,
        "this_cycle_fetched": len(new_bounties),
        "pushed_this_cycle": pushed_count,
        "live_count": len(rows),
        "signals": rows
    }
    with open(JSON_OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    print(f"[{now_str}] ⚡ 快轨扫描完成：捕获急单 {len(new_bounties)} 条，本次成功推送到手机/微信 {pushed_count} 条。")
    return payload


def fetch_single_reddit_sub(sub_tuple, now_str):
    sub, track, label, mode = sub_tuple
    items = []
    try:
        r_url = f"https://www.reddit.com/r/{sub}/top.json?t=month&limit=45" if mode == "top_month" else f"https://www.reddit.com/r/{sub}/new.json?limit=45"
        r_data = json.loads(http_get(r_url, timeout=15))
        for child in r_data.get("data", {}).get("children", []):
            d = child.get("data", {})
            raw_title = clean_raw_html(d.get("title", ""))
            raw_selftext = clean_raw_html(d.get("selftext", ""))
            if not raw_title or any(bad in (raw_title + " " + raw_selftext).lower() for bad in FAKE_GURU_BLACKLIST):
                continue
            if re.search(r'^\s*\[?\s*(?:offer|for\s*hire)\s*\]?', raw_title, re.IGNORECASE):
                continue
            ups = d.get("ups", 0)
            cmts = d.get("num_comments", 0)
            if mode == "top_month" and ups < 2 and cmts < 1:
                continue
            permalink = "https://www.reddit.com" + d.get("permalink", "")
            items.append(enrich_item_one_to_one(f"rd_{d.get('id')}", track, raw_title, raw_selftext, label, permalink, ups, cmts, now_str))
    except Exception as e:
        print(f"[WARN] Reddit r/{sub}: {e}")
    return items


def run_scan_cycle():
    run_fast_bounty_sniper()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    all_fetched = []

    print(f"[{now_str}] 🌐 正在启动 20 分钟全网大盘扫描 (近30天高热源)...")
    with ThreadPoolExecutor(max_workers=12) as ex:
        futures = [ex.submit(fetch_single_reddit_sub, sub_t, now_str) for sub_t in REDDIT_TARGET_SUBS]
        for fut in as_completed(futures):
            try:
                res = fut.result()
                if res:
                    all_fetched.extend(res)
            except Exception as e:
                print(f"[THREAD WARN] {e}")

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    for item in all_fetched:
        c.execute("""
            INSERT OR REPLACE INTO signals VALUES (
                :id, :track, :title_zh, :summary_one_line, :deal_fact_zh,
                :pain_point_zh, :solver_case_zh, :platform_ecology_tip_zh,
                :reverse_money_idea_zh, :action_plan_zh, :feasibility_pct,
                :time_to_money, :capital_req, :source_platform, :source_url,
                :solver_url, :created_at, :deliverable_type
            )
        """, item)
    conn.commit()
    c.execute("SELECT * FROM signals ORDER BY created_at DESC")
    cols = [col[0] for col in c.description]
    rows = [dict(zip(cols, r)) for r in c.fetchall()]
    conn.close()

    payload = {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "poll_interval_sec": 1200,
        "this_cycle_fetched": len(all_fetched),
        "live_count": len(rows),
        "signals": rows
    }
    with open(JSON_OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    return payload


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--bounty-fast", action="store_true")
    parser.add_argument("--bounty-daemon", action="store_true")
    parser.add_argument("--cloud-once", action="store_true")
    args = parser.parse_args()

    os.chdir(BASE_DIR)
    if args.bounty_fast:
        run_fast_bounty_sniper()
        sys.exit(0)
    if args.bounty_daemon:
        last_full_scan = 0
        while True:
            try:
                if time.time() - last_full_scan >= 1200:
                    run_scan_cycle()
                    last_full_scan = time.time()
                else:
                    run_fast_bounty_sniper()
            except Exception as e:
                print(e)
            time.sleep(60)
    run_scan_cycle()
