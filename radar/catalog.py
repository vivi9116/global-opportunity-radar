"""Explicit source registry. A configured source is not a successful crawl."""
PLATFORMS={
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
    for community in ['forhire','slavelabour','SaaS','Entrepreneur','sidehustle','beermoney','beermoneyglobal','WorkOnline','freelance','sweatystartup','smallbusiness','Affiliatemarketing','CreatorsAdvice','onlyfansadvice','adops','marketing','flipping','passive_income']:
        result.append({'id':'reddit_'+community.lower(),'platform':'reddit','name':'Reddit r/'+community,'url':f'https://www.reddit.com/r/{community}/new/.rss?limit=15','format':'rss','adult':community in {'CreatorsAdvice','onlyfansadvice'},'enabled':True})
    for index,query in enumerate(['first sale','paying customers','MRR','willing to pay','alternative to','freelance','revenue']):
        from urllib.parse import quote
        result.append({'id':'hn_'+str(index),'platform':'hackernews','name':'HN · '+query,'url':'https://hn.algolia.com/api/v1/search_by_date?query='+quote(query)+'&tags=story&hitsPerPage=15','format':'hn','enabled':True})
    result.extend([
      {'id':'ruby_china','platform':'ruby_china','name':'Ruby China 技术与远程需求','url':'https://ruby-china.org/topics/feed','format':'rss','enabled':True},
      {'id':'cnode','platform':'cnode','name':'CNode 中文开发者需求','url':'https://cnodejs.org/api/v1/topics?limit=20','format':'cnode','enabled':True},
      {'id':'vc_ru','platform':'vc_ru','name':'VC.ru 俄语商业内容','url':'https://vc.ru/rss','format':'rss','enabled':True},
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
      {'id':'warrior_marketing','platform':'warriorforum','name':'Warrior Forum 公开营销讨论','url':'https://www.warriorforum.com/external.php?type=RSS2&forumids=3','format':'rss','enabled':True},
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
