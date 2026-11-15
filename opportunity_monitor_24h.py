def is_valid_money_opportunity(title, body, track, source_platform, ups=0, cmts=0):
    blob = f"{title} {body}".lower()
    # 1. 严厉剔除服务器宕机报错 (如 AWS 503 / Outage)、安全漏洞通报、版规水贴、卖课骗子
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

    # 非悬赏单：剔除 0 评论且低于 3 赞的无人关注水贴
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
    price_str = " / ".join(money_list[:2]) if money_list else ("$40~$200 (直接私信议价)" if defaultTrack == "bounty_direct" else "按交付收 $39~$199")

    industry_m = re.search(r'\b(gym|fitness|clinic|dentist|restaurant|real estate|realtor|lawyer|agency|shopify|wix|ecommerce|hotel|salon|plumber|contractor|podcast|youtuber|creator|onlyfans|accountant)\b', blob, re.I)
    target_client = industry_m.group(1) if industry_m else ""

    tech_entities = list(dict.fromkeys(re.findall(
        r'\b(Python|Rust|TypeScript|React|Next\.js|Node\.js|Docker|PostgreSQL|SQLite|Supabase|Stripe|PayPal|Shopify|Wix|WordPress|Chrome|Telegram|Discord|WhatsApp|OpenAI|Claude|LLM|RAG|Agent|OCR|PDF|CSV|Excel|Google Sheets|Selenium|Playwright|Puppeteer|Cloudflare|Proxy|TikTok|YouTube|Instagram|OnlyFans|Fanvue|Patreon|Etsy|Amazon|eBay|Notion|Airtable|Zapier|n8n|FFmpeg|iOS|Android|Flutter|CPA|OGAds|CrakRevenue|AdBlueMedia|SEO|Backlinks)\b',
        blob, re.IGNORECASE
    )))
    entity_tag = " + ".join(tech_entities[:3]) if tech_entities else cleanTitle[:30]

    sentences = [s.strip() for s in re.split(r'[.!?;\n]+', cleanBody) if len(s.strip()) > 18]
    summary_quote = " | ".join(sentences[:2])[:220] if sentences else cleanTitle

    # 形态 1：How to Build / 实战开发教程复刻变现型（直接拿开源方案卖给线下/垂直行业老板，绝不去 0 评论区找买家！）
    if re.search(r'^how\s+to\b|\bbuild\s+an?\b|\bstep[- ]by[- ]step\b|\btutorial\b|\bagent\b', cleanTitle, re.I) and defaultTrack != "bounty_direct":
        client_desc = f"线下/海外「{target_client}」实体门店老板" if target_client else f"需要「{cleanTitle[:25]}」的中小企业主"
        return {
            "pain_point_zh": f"【可白嫖的开源商业方案：《{cleanTitle}》】\n● 原帖方案内容：{summary_quote}\n● 商业信息差：作者已把基于 `{entity_tag}` 的完整实现逻辑免费公开，而现实中 {client_desc} 根本不懂技术，找外包公司定制这套系统通常要花 $1,500+。",
            "solver_case_zh": f"【白嫖现成源码 → 卖给 {client_desc} 做代搭建（Drop-Servicing）】：不要在技术文章评论区守株待兔，直接把作者这套 `{entity_tag}` 方案跑通录个 45 秒演示视频，主动出击卖给实体店老板或挂到闲鱼/Fiverr 收代建费！",
            "action_plan_zh": f"1. 【复刻原帖 Demo】：点开原帖复制其 `{entity_tag}` 代码与配置，花半小时在本地跑通并录一段 45 秒操作视频；\n2. 【精准找实体店老板】：在 Google Maps / Instagram / 小红书搜 `{target_client or '目标行业'}` 商家联系方式；\n3. 【收安装费+包月维护】：发演示视频给老板：『一口价 $199（或 ¥999）帮您店里配好这套全自动系统，每月 $29 维护』。 ",
            "platform_ecology_tip_zh": f"🔥 技术教程变现铁律：看这篇帖子（{ups}赞·{cmts}评）的全是同行程序员，千万别在原帖底下发广告！真正的付费金主在圈外的实体商家名录里，把技术词包装成“帮门店省掉半个客服工资”一谈一个准。",
            "reverse_money_idea_zh": f"🔄 把《{cleanTitle[:25]}》榨干的 3 条路径：\n1. 【闲鱼/小红书卖汉化工作流】：把这套方案转成 Coze / Dify / n8n 中文模板，在小红书发笔记《给{target_client or '门店'}做了个AI自动预约系统》，按 ¥99/份 卖给国内店主和同行；\n2. 【Fiverr 挂 $199 代搭建】：在 Fiverr 上架同名服务接欧美老板定制单；\n3. 【打包卖给行业代运营公司】：把工具贴牌批发给专门服务 `{target_client or '实体店'}` 的营销机构。"
        }

    # 形态 2：免费直联悬赏急单（严格区分 0 评论首发窗 vs 多评论插队）
    if defaultTrack == "bounty_direct" or re.search(r'\[task\]|\[hiring\]|\$bid|forhire|slavelabour|donedirtcheap|\bwtb\b', blob, re.I):
        bounty_tip = (
            f"🔥 0 竞标黄金首发窗：这单刚发出，当前是 **0 条评论**！趁印度低价党还没来，5 分钟跑出 `{entity_tag}` 前 10 行结果截图直接发私信，95% 原价拿单！"
            if cmts == 0 else
            f"⚡ 插队截胡指南（当前已有 {cmts} 条评论）：别在评论区排队傻等！回完 `$bid` 后立刻点开雇主头像发 Chat 私信，第一句话直接甩出你做好的 `{entity_tag}` 样本截图把单抢过来！"
        )
        return {
            "pain_point_zh": f"【{sourceLabel} 免费直联急单：《{cleanTitle}》】\n● 雇主需求：{summary_quote}\n● 涉及技能：{entity_tag} | 预算指标：{price_str} | 当前竞标：{cmts} 条评论。",
            "solver_case_zh": f"跳过简历环节，直接围绕雇主点名的 `{entity_tag}` 需求在 5 分钟内做出前 20% 真实样本截图发私信当场锁单。",
            "action_plan_zh": f"1. 把需求「{summary_quote[:38]}...」丢给 AI 生成前 15 行数据或 Demo 截图；\n2. 原帖回 `$bid` 后立刻发私信附上截图：『Built a working sample for your {entity_tag} task, can deliver in 1 hour』；\n3. 走 PayPal / USDT 收款交货。",
            "platform_ecology_tip_zh": bounty_tip,
            "reverse_money_idea_zh": f"🔄 3 条逆向赚钱门道：\n1. 【闲鱼转包赚 6 倍汇率差】：接下美金单后去国内闲鱼搜 `{entity_tag} 代做` 花 ¥80 搞定；\n2. 【脱敏挂 Gumroad 复卖】：把交付脚本按 $29/份 卖给有同样需求的同行；\n3. 【顺藤摸瓜抄雇主业务】：点进雇主发帖历史看他用这批数据在跑什么暴利项目。"
        }

    # 形态 3：成人 NSFW / CPA / 痛点复盘（根据 cmts 真实数值动态生成动作，绝不出现“去 0 条评论抓人”）
    action_step_1 = (
        f"1. 【抓评论区现成买家】：点开原帖查看那 {cmts} 条跟帖，找到同样抱怨该痛点或询问工具的潜在客户；"
        if cmts > 0 else
        f"1. 【抢占沙发位 + 提炼痛点】：本帖当前是 0 评论（{ups}赞），点开原帖提取 `{entity_tag}` 核心痛点，并留第 1 条专业干货回复占住第一视觉位；"
    )
    return {
        "pain_point_zh": f"【实战标的《{cleanTitle}》还原（{ups}赞 · {cmts}评）】\n● 核心领域：{entity_tag}（指标：{price_str}）。\n● 原帖关键内容：{summary_quote}",
        "solver_case_zh": f"围绕「{cleanTitle[:32]}」验证的真实需求，切入『$29 免月租买断工具』、『$69 人工代配置服务』或『跨国信息差搬运』。",
        "action_plan_zh": f"{action_step_1}\n2. 【AI 封装 `{entity_tag}` 极简工具】：用 Cursor 花 1 小时做成免安装脚本或自动化模板；\n3. 【免费样本锁单】：用『前 20 条数据免费帮跑验货』钩子引导客户私信付款。",
        "platform_ecology_tip_zh": f"🔥 截流细节：{'回复排第一的高赞评论（抢占楼中楼）曝光最高' if cmts > 2 else '切勿直发收款硬广链接，用实测结果截图吸引客户主动私信'}。",
        "reverse_money_idea_zh": f"🔄 围绕《{cleanTitle[:25]}》的 3 条逆向变现路径：\n1. 【跨国信息差搬运】：把本帖套路翻译成中文干货发小红书/闲鱼，卖 ¥49~¥99 的配套工具包；\n2. 【Done-For-You 代配置服务】：挂出 $79 帮欧美小老板远程配好全流程，转包国内闲鱼技术员交付；\n3. 【竞品 1 星差评截胡】：去 Trustpilot / G2 找同类高价软件的最新差评客户推销你的 $29 买断平替版。"
    }
