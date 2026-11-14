"""Explicit source registry. A configured source is not a successful crawl."""
PLATFORMS={
 'monetag':{'name':'Monetag 广告分成','docs':'https://monetag.com/','ecology':'先弄清广告格式、允许的网站和流量、扣量及结算条件；案例的流量来源与花费要一起看。'},
 'curseforge':{'name':'CurseForge 创作者生态','docs':'https://blog.curseforge.com/','ecology':'游戏模组的下载、奖励和现金收入分开；核对原创/授权、平台奖励资格和提现地区。'},
 'roblox':{'name':'Roblox 开发者社区','docs':'https://devforum.roblox.com/','ecology':'找明确的插件、素材、定制或分成需求；平台虚拟币、报价与已提现现金不混算。'},
 'lowendtalk':{'name':'LowEndTalk 小众站长与服务','docs':'https://lowendtalk.com/','ecology':'先看具体服务需求、履约和付款主体；低价主机广告不直接当盈利项目，退款与维护要算进成本。'},
 'domainnamewire':{'name':'Domain Name Wire 域名生意','docs':'https://domainnamewire.com/','ecology':'域名新闻、挂牌价和报道成交分别标记；历史成交不能证明新注册域名能卖同样价格。'},
 'itchio':{'name':'itch.io 独立作品与工具','docs':'https://itch.io/','ecology':'免费发布、下载量和销量不同；看授权、定价、平台分成、更新维护和实际付费反馈。'},
 'crakrevenue':{'name':'CrakRevenue 成人联盟','docs':'https://www.crakrevenue.com/blog/','ecology':'先看Offer允许的国家、流量来源、计费动作、扣量和付款门槛；博客收入案例是平台披露，不能直接当自己的到账。'},
 'adsterra':{'name':'Adsterra 流量变现','docs':'https://adsterra.com/blog/','ecology':'分开看展示/点击/转化报价、买流量花费和实际到账；平台案例不是每个新账号都能复现的结果。'},
 'propellerads':{'name':'PropellerAds CPA/流量','docs':'https://propellerads.com/blog/','ecology':'投放案例必须同时看广告费、转化、扣量、净利和获准来源，不能只抄收入截图。'},
 'namepros':{'name':'NamePros 域名与停放','docs':'https://www.namepros.com/','ecology':'标价、出价、卖方自述和完成交易分开；老域名先看历史、商标与真实流量，不把挂价当成交。'},
 'trustmrr':{'name':'TrustMRR 小工具收入榜','docs':'https://trustmrr.com/','ecology':'公开MRR是平台显示的订阅指标，不是净利润，也不是本监控台核验的银行到账；看小功能、客源和成本能否复用。'},
 'polymarket':{'name':'Polymarket 公开市场数据','docs':'https://docs.polymarket.com/','ecology':'公开买卖报价不是保证能吃到的利润；需要另核成交深度、费用、库存和适用地区。此处只读数据。'},
 'ruby_china':{'name':'Ruby China','docs':'https://ruby-china.org/','ecology':'社区技术讨论与招聘分开；先核对地区、技术要求、联系渠道和任务状态。'},
 'cnode':{'name':'CNode','docs':'https://cnodejs.org/api','ecology':'技术求助不等于付费外包，先确认任务范围、预算和是否允许服务推广。'},
 'vc_ru':{'name':'VC.ru','docs':'https://vc.ru/','ecology':'俄语商业经验区分作者自述和广告；国家、收付款和语言要求需要逐项确认。'},
 'zenn':{'name':'Zenn 日本开发者社区','docs':'https://zenn.dev/','ecology':'付费内容、产品经验与教程分别看；日本市场语言和收付款要求不能从技术文章推定。'},
 'tabnews':{'name':'TabNews 巴西社区','docs':'https://www.tabnews.com.br/','ecology':'葡语社区的技术经验只作需求/工具线索；预算、客户和交易需要另外确认。'},
 'nichepursuits':{'name':'Niche Pursuits','docs':'https://www.nichepursuits.com/','ecology':'访谈和经营复盘是被访者自述，须检查收入、成本与推广利益关系，不能视为复现保证。'},
 'sidehustlenation':{'name':'Side Hustle Nation','docs':'https://www.sidehustlenation.com/','ecology':'副业访谈与推广文章需核对来源时间、客源和成本；受访者成绩不是读者可实现收益。'},
 'sitepoint':{'name':'SitePoint Community','docs':'https://www.sitepoint.com/community/','ecology':'先解决具体客户/技术问题，是否允许自荐按当前版规和发帖区域确认。'},
 'devto':{'name':'DEV Community','docs':'https://dev.to/','ecology':'开发者产品发布主要是工具/需求线索；作者自述销售额与独立支付证明区分。'},
 'github_bounties':{'name':'GitHub 公开赏金需求','docs':'https://docs.github.com/en/rest/search/search#search-issues-and-pull-requests','ecology':'赏金标签只是线索；先确认维护者接受方案、赏金仍有效及领取条件，不抢做未获确认的整项开发。'},
 'freelancer':{'name':'Freelancer','docs':'https://developer.freelancer.com/','ecology':'预算是买方报价，竞标人数不是成交人数；核对技能、投标资格、托管里程碑和费用。'},
 'problogger':{'name':'ProBlogger Jobs','docs':'https://problogger.com/jobs/about/','ecology':'职位来自第三方广告主；核对细分领域、署名与版权、字数、修改轮次及付款主体。'},
 'discourse':{'name':'Discourse Marketplace','docs':'https://meta.discourse.org/c/marketplace/14','ecology':'社区付费定制要说明版本、插件、验收与维护范围，先确认需求仍然有效。'},
 'obsidian':{'name':'Obsidian Forum','docs':'https://forum.obsidian.md/','ecology':'用户求助不必然愿意付费；先确认插件能力、文件隐私和社区推广规则。'},
 'afflift':{'name':'affLIFT','docs':'https://afflift.com/','ecology':'联盟实验要同时核对广告花费、收入、扣量、时间和Offer条款；仅收入截图不能推导利润。'},
 'digitalpoint':{'name':'Digital Point','docs':'https://forums.digitalpoint.com/','ecology':'服务区展示报价不等于已付款；先看交易范围、信誉、样品与交付验收。'},
 'warriorforum':{'name':'Warrior Forum','docs':'https://www.warriorforum.com/','ecology':'营销方法帖区分销售软文与实盘；没有成本和付款证据时保留为待验证线索。'},
 'xbiz':{'name':'XBIZ 成人商业资讯','docs':'https://www.xbiz.com/','ecology':'行业消息只是经营背景，不是个人收入证明；重点核对平台条款、结算与渠道变化。'},
 'reddit':{'name':'Reddit','docs':'https://www.reddit.com/wiki/rss','ecology':'按各社区当前版规回复；是否允许私信、自荐或$bid需要逐帖核对。'},
 'hackernews':{'name':'Hacker News','docs':'https://news.ycombinator.com/newsguidelines.html','ecology':'先回应具体问题，披露利益关系，不能把技术讨论区当成群发广告入口。'},
 'v2ex':{'name':'V2EX','docs':'https://www.v2ex.com/help/api','ecology':'核对节点主题和发布要求；远程、招聘、外包的合同性质不同。'},
 'blackhatworld':{'name':'BlackHatWorld','docs':'https://www.blackhatworld.com/forums/my-journey-discussions.167/','ecology':'连载目标、更新、报价与到账自述要分开；帖子热度不是收入证明。'},
 'producthunt':{'name':'Product Hunt','docs':'https://www.producthunt.com/feed','ecology':'新产品是竞品/工具线索，投票和上榜不等于收入。'},
 'n8n':{'name':'n8n Community','docs':'https://community.n8n.io/','ecology':'先复现流程和报错；社区求助不一定是付费委托，接单要确认预算。'},
 'make':{'name':'Make Community','docs':'https://community.make.com/','ecology':'明确模块、数据量、连接权限与异常处理，先给小范围可复现方案。'},
 'remoteok':{'name':'Remote OK','docs':'https://remoteok.com/faq','ecology':'按原始岗位申请；地区、签证、时区、合同和薪资均以原帖为准。'},
 'remotive':{'name':'Remotive','docs':'https://remotive.com/api/remote-jobs','ecology':'聚合岗位可能存在发布延迟；回到原招聘页确认仍开放。'},
 'weworkremotely':{'name':'We Work Remotely','docs':'https://weworkremotely.com/remote-jobs.rss','ecology':'核对公司、申请域名和地区限制，招聘薪资不是已实现收入。'},
 'arbeitnow':{'name':'Arbeitnow','docs':'https://www.arbeitnow.com/api/job-board-api','ecology':'有些职位限定欧洲或当地工作资格，不能只凭remote判断能申请。'},
 'wordpress':{'name':'WordPress Support','docs':'https://wordpress.org/support/','ecology':'先提供可复现的帮助；免费支持问题不自动等于付费获客许可。'},
}

def default_sources():
    result=[]
    communities=['forhire','slavelabour','SaaS','Entrepreneur','sidehustle','beermoney','beermoneyglobal','WorkOnline','freelance','sweatystartup','smallbusiness','Affiliatemarketing','CreatorsAdvice','onlyfansadvice','adops','marketing','flipping','passive_income']
    for slot in range(3):
        group=communities[slot*6:(slot+1)*6]
        result.append({'id':'reddit_group_'+str(slot),'platform':'reddit','name':'Reddit 联合订阅第'+str(slot+1)+'组（每轮只轮到一组）','url':'https://www.reddit.com/r/'+'+'.join(group)+'/new/.rss?limit=100','format':'rss','limit':100,'communities':group,'rotation_group':'reddit','rotation_slot':slot,'rotation_total':3,'preferred_theme':True,'enabled':True})
    for index,query in enumerate(['first sale','paying customers','MRR','willing to pay','alternative to','freelance','revenue']):
        from urllib.parse import quote
        result.append({'id':'hn_'+str(index),'platform':'hackernews','name':'HN · '+query,'url':'https://hn.algolia.com/api/v1/search_by_date?query='+quote(query)+'&tags=story&hitsPerPage=15','format':'hn','enabled':True})
    result.extend([
      {'id':'monetag_posts','platform':'monetag','name':'小站流量、弹窗与广告分成','url':'https://monetag.com/feed/','format':'rss','preferred_theme':True,'commercial_publisher':True,'enabled':True},
      {'id':'curseforge_creators','platform':'curseforge','name':'游戏模组创作者与平台奖励','url':'https://blog.curseforge.com/rss/','format':'rss','enabled':True},
      {'id':'roblox_creators','platform':'roblox','name':'游戏插件、素材与创作者需求','url':'https://devforum.roblox.com/latest.rss','format':'rss','enabled':True},
      {'id':'lowendtalk_niches','platform':'lowendtalk','name':'海外小站长与技术杂活','url':'https://lowendtalk.com/discussions/feed.rss','format':'rss','enabled':True},
      {'id':'domainnamewire','platform':'domainnamewire','name':'域名交易、停放与遗留流量','url':'https://domainnamewire.com/feed/','format':'rss','preferred_theme':True,'enabled':True},
      {'id':'itchio_devlogs','platform':'itchio','name':'独立作品、插件和数字交付','url':'https://itch.io/devlogs.xml','format':'rss','enabled':True},
      {'id':'crakrevenue_blog','platform':'crakrevenue','name':'成人联盟拉新与经营案例（较早文章标作长期参考）','url':'https://www.crakrevenue.com/blog/feed/','format':'rss','adult':True,'preferred_theme':True,'evergreen':True,'max_age_days':730,'commercial_publisher':True,'enabled':True},
      {'id':'adsterra_blog','platform':'adsterra','name':'Adsterra 流量与广告分成','url':'https://adsterra.com/blog/feed/','format':'rss','preferred_theme':True,'commercial_publisher':True,'enabled':True},
      {'id':'propellerads_blog','platform':'propellerads','name':'PropellerAds CPA与流量案例','url':'https://propellerads.com/blog/feed/','format':'rss','preferred_theme':True,'commercial_publisher':True,'enabled':True},
      {'id':'namepros_domains','platform':'namepros','name':'域名、老流量与停放门道','url':'https://www.namepros.com/forums/-/index.rss','format':'rss','preferred_theme':True,'enabled':True},
      {'id':'trustmrr_public','platform':'trustmrr','name':'小工具公开订阅收入表格','url':'https://trustmrr.com/','format':'trustmrr_html','preferred_theme':True,'filter_business':False,'enabled':True},
      {'id':'polymarket_public','platform':'polymarket','name':'预测市场官方公开报价','url':'https://gamma-api.polymarket.com/markets/keyset?closed=false&limit=10','format':'gamma_markets','filter_business':False,'preferred_theme':True,'enabled':True},
      {'id':'sidehustle_podcast','platform':'sidehustlenation','name':'Side Hustle Show 官方播客经营案例（博客验证时的公开补充）','url':'https://feeds.megaphone.fm/YAP9195874886','format':'rss','max_bytes':12000000,'timeout':25,'preferred_theme':True,'enabled':True},
      {'id':'ruby_china','platform':'ruby_china','name':'Ruby China 技术与远程需求','url':'https://ruby-china.org/topics/feed','format':'rss','enabled':True},
      {'id':'cnode','platform':'cnode','name':'CNode 官方RSS（已迁离失效旧API）','url':'https://cnodejs.org/rss','format':'rss','timeout':25,'transient_attempts':2,'retry_tls_eof':True,'enabled':True},
      {'id':'vc_ru','platform':'vc_ru','name':'VC.ru 俄语商业内容','url':'https://vc.ru/rss','format':'rss','timeout':30,'transient_attempts':2,'enabled':True},
      {'id':'zenn','platform':'zenn','name':'Zenn 日本产品与经营线索','url':'https://zenn.dev/feed','format':'rss','enabled':True},
      {'id':'tabnews','platform':'tabnews','name':'TabNews 葡语产品经验','url':'https://www.tabnews.com.br/rss','format':'rss','enabled':True},
      {'id':'nichepursuits','platform':'nichepursuits','name':'Niche Pursuits 经营复盘','url':'https://www.nichepursuits.com/feed/','format':'rss','enabled':True},
      {'id':'sidehustlenation','platform':'sidehustlenation','name':'Side Hustle Nation 副业案例','url':'https://www.sidehustlenation.com/feed/','format':'rss','enabled':True},
      {'id':'sitepoint','platform':'sitepoint','name':'SitePoint 客户与开发需求','url':'https://www.sitepoint.com/community/latest.rss','format':'rss','enabled':True},
      {'id':'devto','platform':'devto','name':'DEV SaaS/数字产品经验','url':'https://dev.to/feed/tag/saas','format':'rss','enabled':True},
      {'id':'github_bounties','platform':'github_bounties','name':'GitHub 开放赏金议题','url':'https://api.github.com/search/issues?q=is%3Aissue%20is%3Aopen%20label%3Abounty&sort=updated&order=desc&per_page=20','format':'github_issues','buyer_source':True,'filter_business':False,'enabled':True},
      {'id':'freelancer_active','platform':'freelancer','name':'Freelancer 公开项目','url':'https://www.freelancer.com/api/projects/0.1/projects/active/?limit=20&full_description=true','format':'freelancer','buyer_source':True,'filter_business':False,'enabled':True},
      {'id':'problogger_jobs','platform':'problogger','name':'ProBlogger 内容写作委托','url':'https://problogger.com/jobs/wpjobboard/xml/rss/?filter=active&hide_filled%5B0%5D=1&sort_order=t1.is_featured+DESC%2C+t1.job_created_at+DESC%2C+t1.id+DESC','format':'rss','job_source':True,'filter_business':False,'enabled':True},
      {'id':'discourse_marketplace','platform':'discourse','name':'Discourse 付费定制与服务','url':'https://meta.discourse.org/c/marketplace/14.rss','format':'rss','enabled':True},
      {'id':'obsidian_business','platform':'obsidian','name':'Obsidian 用户痛点','url':'https://forum.obsidian.md/latest.rss','format':'rss','enabled':True},
      {'id':'afflift_public','platform':'afflift','name':'affLIFT 公开联盟实验','url':'https://afflift.com/f/forums/-/index.rss','format':'rss','enabled':True},
      {'id':'digitalpoint_services','platform':'digitalpoint','name':'Digital Point 服务需求','url':'https://forums.digitalpoint.com/forums/services.60/index.rss','format':'rss','enabled':True},
      {'id':'warrior_marketing','platform':'warriorforum','name':'Warrior 公开最新讨论（已迁离空RSS）','url':'https://www.warriorforum.com/discussions/latest/','format':'warrior_html','preferred_theme':True,'enabled':True},
      {'id':'xbiz_business','platform':'xbiz','name':'XBIZ 成人平台与技术经营','url':'https://www.xbiz.com/rss/news/web-tech.xml','format':'rss','adult':True,'enabled':True},
      {'id':'xbiz_business_features','platform':'xbiz','name':'XBIZ 成人经营趋势','url':'https://www.xbiz.com/rss/features/business.xml','format':'rss','adult':True,'enabled':True},
      {'id':'v2ex_latest','platform':'v2ex','name':'V2EX 最新主题（旧版公开接口，实测状态为准）','url':'https://www.v2ex.com/api/topics/latest.json','format':'v2ex','enabled':True},
      {'id':'bhw_journey','platform':'blackhatworld','name':'BHW Journey RSS','url':'https://www.blackhatworld.com/forums/my-journey-discussions.167/index.rss','format':'rss','enabled':True},
      {'id':'producthunt','platform':'producthunt','name':'Product Hunt 产品线索','url':'https://www.producthunt.com/feed','format':'rss','tool_source':True,'enabled':True},
      {'id':'n8n_latest','platform':'n8n','name':'n8n 社区流程与服务需求','url':'https://community.n8n.io/latest.rss','format':'rss','enabled':True},
      {'id':'make_latest','platform':'make','name':'Make 社区流程与服务需求','url':'https://community.make.com/latest.rss','format':'rss','enabled':True},
      {'id':'remoteok','platform':'remoteok','name':'Remote OK 招聘','url':'https://remoteok.com/api','format':'remoteok','filter_business':False,'enabled':True},
      {'id':'remotive','platform':'remotive','name':'Remotive 招聘','url':'https://remotive.com/api/remote-jobs','format':'remotive','filter_business':False,'enabled':True},
      {'id':'weworkremotely','platform':'weworkremotely','name':'We Work Remotely 招聘','url':'https://weworkremotely.com/remote-jobs.rss','format':'rss','job_source':True,'filter_business':False,'enabled':True},
      {'id':'arbeitnow','platform':'arbeitnow','name':'Arbeitnow 招聘','url':'https://www.arbeitnow.com/api/job-board-api','format':'arbeitnow','filter_business':False,'enabled':True},
      {'id':'wordpress_support','platform':'wordpress','name':'WordPress 支持需求','url':'https://wordpress.org/support/rss/','format':'rss','enabled':True},
    ])
    for source in result:
        if source['platform'] in {'remoteok','remotive','weworkremotely','arbeitnow','problogger'}:
            source.update(enabled=False,scope_disabled=True,reason='按用户选题要求，普通岗位从默认采集移入扩展资料；不会用招聘信息填充赚钱野路子。')
    for index,query in enumerate(['first sale','paying customers']):
        from urllib.parse import quote
        result.append({'id':'hn_comments_'+str(index),'platform':'hackernews','name':'HN 用户经验 · '+query,'url':'https://hn.algolia.com/api/v1/search_by_date?query='+quote(query)+'&tags=comment&hitsPerPage=15','format':'hn','enabled':True})
    for identifier,name,reason in [
      ('upwork','Upwork','尚未配置官方API授权，也未验证可用的公开采集入口；不计入已监控。'),
      ('fiverr','Fiverr','尚未接入允许自动读取的稳定接口；不凭页面标题声称已抓到订单。'),
      ('x','X / Twitter','尚未配置API授权；没有尝试读取登录后的时间线。'),
      ('facebook_groups','Facebook Groups','私密群组内容没有账号及群组授权，未发送采集请求。'),
      ('private_telegram','Telegram 私密群组','没有群组访问授权与明确采集范围，未发送请求。'),
      ('paid_analytics','Kalodata / FastMoss 付费内部数据','没有启用授权接口；按用户要求，不控制已登录浏览器。'),
      ('dlsite','DLsite 成人作品经营数据','尚未验证可无需年龄确认或账号交互的稳定数据入口；不绕过确认页面。'),
    ]:result.append({'id':identifier,'platform':identifier,'name':name,'url':'','format':'unconnected','enabled':False,'reason':reason})
    return result
