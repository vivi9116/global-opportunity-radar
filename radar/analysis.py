"""Separate observed evidence from tailored, explicitly labelled strategy."""
import datetime as dt
import hashlib
import html
import re
from .business_profiles import profile_for,observed_constraints
from .catalog import PLATFORMS

MONEY=re.compile(r'(?:US\$|R\$|CA\$|A\$|HK\$|S\$|NT\$|USD\s*|\$|€|£|¥|￥|₽|₹|₩)\s*\d[\d,]*(?:\.\d+)?(?:\s*[kKmMbB]\b)?|\d[\d,]*(?:\.\d+)?\s*(?:美元|日元|元|円|USDT\b|USDC\b|USD\b|EUR\b|GBP\b|BRL\b|JPY\b|CNY\b|RUB\b|BTC\b|ETH\b|руб\b|€|£|₽)',re.I)
GOAL=re.compile(r'\b(?:goal|target|aim|hope|hoping|plan|would|could|want to|expect|projected|potential|forecast|journey to)\b|目标|计划|希望|预计',re.I)
OUTCOME=re.compile(r'\b(?:earned|paid me|received|made|generated|netted|first sale|sold)\b|\b(?:revenue|profit|income)\s*[:=]|到账|实收|赚了|营收[：:]',re.I)
BUYER=re.compile(r'\[\s*(?:hiring|task)\s*\]|\b(?:bounty|need someone|looking for (?:a |an )?(?:freelancer|developer|designer|writer|someone)|willing to pay someone|hiring (?:a|an))\b|悬赏|求开发|求外包|招募',re.I)
PAIN=re.compile(r'tired of paying|too expensive|alternative to|manual process|takes? hours|willing to pay|looking for a tool|frustrat|太贵|求推荐|手工|痛点',re.I)
BUSINESS=re.compile(r'\b(?:revenue|profit|income|earned|earnings|paid|paying|payout|money|monetiz\w*|mrr|subscription|client\w*|customer\w*|hiring|budget|bounty|freelanc\w*|affiliate\w*|commission|business\w*|first sale|sales|sold|side.?hustle)\b|收入|赚钱|营收|收款|佣金|接单|预算|外包|付费|销售|变现',re.I)
PROMO=re.compile(r'buy my course|join my paid discord|dm me for secret|100x guaranteed|free webinar|masterclass|稳赚不赔|保证日入',re.I)

def clean(value):return re.sub(r'\s+',' ',html.unescape(re.sub(r'<[^>]+>',' ',value or ''))).strip()

def utc_now():return dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')

def kind_for(title,body,source):
    text=(title+' '+body).lower()
    if source.get('format')=='gamma_markets':return 'market_observation','market_watch'
    if source.get('format')=='trustmrr_html':return 'platform_metrics','pain_saas'
    if source.get('job_source') or source.get('format') in {'remoteok','remotive','arbeitnow'}:return 'job_posting','remote_work'
    if source.get('adult') or re.search(r'\badult\b|nsfw|onlyfans|fanvue|fansly|成人',text):return 'business_discussion','nsfw_adult'
    if re.search(r'\[\s*for\s*hire\s*\]',title,re.I):return 'seller_offer','global_business'
    if re.search(r'bulk gmail|bulk.*account creation|captcha bypass|cloaking|account farming',text):return 'method_discussion','gray_arb'
    if BUYER.search(title+' '+body[:1000]):return 'buyer_request','bounty_direct'
    if source.get('buyer_source'):return 'buyer_request','bounty_direct'
    if re.search(r'account network|cloaking|black.?hat|gr[ae]y.?hat|cpa|content lock|账号网络|灰色|灰产|流量套利',text):return 'method_discussion','gray_arb'
    if source.get('platform') in {'adsterra','propellerads','monetag','namepros','domainnamewire'}:return 'method_discussion','gray_arb'
    if PAIN.search(title+' '+body):return 'pain_point','pain_saas'
    if source.get('tool_source') or title.startswith('Show HN:'):return 'tool_launch','tools'
    return 'business_discussion','global_business'

def financial_evidence(title,body,kind):
    evidence=[]
    for sentence in re.split(r'\n+|(?<=[.!?。])\s+',body or ''):
        sentence=clean(sentence)
        if not MONEY.search(sentence):continue
        if GOAL.search(sentence):continue
        if re.search(r'\b(?:refund|loan|spent|invested|lost|cost me|funding|funded|backed by|market in|annual gmv|background check|phone benefits|referral program)\b|退款|借款|亏了|融资',sentence,re.I):continue
        label='买方预算/报价' if kind=='buyer_request' else '招聘薪资描述' if kind=='job_posting' else '卖方服务报价' if kind=='seller_offer' else '原文收入说法'
        if kind not in {'buyer_request','job_posting','seller_offer'} and not OUTCOME.search(sentence):continue
        match=MONEY.search(sentence)
        try:
            if float(re.sub(r'[^\d.]','',match.group()))==0:continue
        except ValueError:continue
        context=sentence[max(0,match.start()-110):match.end()+110]
        if kind=='job_posting' and not re.search(r'\b(?:salary|compensation|base pay|pay|hourly|per hour|per word|per task|stipend|wage|rate of pay)\b|薪资|时薪|月薪|报酬',context,re.I):continue
        if kind=='buyer_request' and not re.search(r'\b(?:budget|bounty|reward|payment|pay|paid|rate|offer|compensation|prize|orçamento|premiar)\b|预算|报价|悬赏|报酬|支付',context,re.I):continue
        amount=match.group()
        range_end=re.match(r'\s*[–—-]\s*(?:US\$|USD\s*|\$|€|£|¥|￥)?\s*\d[\d,]*(?:\.\d+)?(?:[kKmM]\b)?',sentence[match.end():])
        if range_end:amount+=range_end.group()
        excerpt=sentence[max(0,match.start()-65):match.end()+85]
        if any(e['amount']==amount and e['quote']==excerpt[:180] for e in evidence):continue
        evidence.append({'amount':amount,'nature':label,'quote':excerpt[:180],'verification':'来源正文中的说法，未独立核验支付或到账'})
        if len(evidence)==3:break
    return evidence

def service_subject(title,body):
    text=(title+' '+body).lower()
    for words,subject,sample in [
        (r'csv|excel|spreadsheet|表格','表格清洗与匹配','用两份小样表演示去重、字段映射和匹配结果，保留处理前后对照'),
        (r'scrap|crawl|directory|名录|爬虫','公开数据整理','只用有权访问的数据做5—10条样例，展示字段、来源链接和去重结果'),
        (r'video|caption|subtitle|视频|字幕','视频或字幕交付','用获授权的短片做一段带时间轴的字幕或剪辑前后对照'),
        (r'translat|localiz|翻译|本地化','翻译与本地化服务','先做一小段有授权的双语样例，说明术语选择、格式及验收方式'),
        (r'automat|workflow|n8n|make\.com|自动化','流程自动化','做一个输入到输出的最小流程，展示异常处理和节省的人工步骤'),
        (r'design|logo|设计','设计交付','用对方明确要求的一个页面或元素做有水印的局部预览'),
        (r'crm|customer|client|客户','客户流程或资料处理','用虚构数据演示一个完整操作，记录输入、输出及边界条件'),
    ]:
        if re.search(words,text):return subject,sample
    return '这条需求对应的服务','围绕原帖最核心的一项要求做最小样例，标明输入、输出和未覆盖范围'

def detailed_strategy(item,source):
    title=item['raw_title_en'];body=item.get('_body','');kind=item['kind'];track=item['track'];platform=item['source_platform']
    subject,sample=service_subject(title,body)
    age='原帖未提供可靠发布时间'
    if item.get('published_at'):
        try:
            minutes=max(0,int((dt.datetime.now(dt.timezone.utc)-dt.datetime.fromisoformat(item['published_at'].replace('Z','+00:00'))).total_seconds()/60))
            age=f'本次发现时，原帖已发布约{minutes}分钟；这不代表仍可接单'
        except ValueError:pass
    observed=[f'来源：{platform}；采集方式：{source.get("format","公开来源")}。',age]
    if item.get('reply_count') is not None:observed.append(f'源站返回的回复数：{item["reply_count"]}；没有据此推算拿单概率。')
    if item.get('location'):observed.append('源站地区/地点字段：'+item['location']+'；remote不等于全球均可申请。')
    ecology={'observed':observed,'recommendations':[],'legacy_note':None}
    if kind=='buyer_request' or track=='bounty_direct':
        ecology['legacy_note']='按用户对v9.1的回忆保留：印度、东欧等时区也可能有接单者，公开急单可能很快出现竞争；原先“30分钟很多人抢、10分钟发截图基本拿下”属于未核验的经验说法，不是当前统计或成交保证。'
        ecology['recommendations']=[
            '发现后先用约2分钟确认帖子是否仍开放、任务范围、语言与时区要求；旧帖或已有受雇标记时，不把抢首响应当作优势。',
            '把“发现后10分钟内做一张真实样例截图”当作响应目标；云端定时抓取有排队延迟，不能保证在发帖10分钟内发现。急单可结合平台原生通知。',
            sample+'；截图只展示你实际完成的内容，不写“全量已经做完”来冒充进度。',
            '先读当前版规和帖主要求；只有明确要求$bid时才照做，也不默认可以私信或批量发相同话术。',
            '第一条回复先说你理解的交付结果、样例和还缺的一个关键信息；随后才给报价、交付时间与返工边界。',
            '不要免费做完整订单；先约定验收样本、分段付款或平台托管，确认后再做全量交付。',
        ]
        steps=[('确认机会仍有效','打开原帖看是否关闭、是否要求特定国家或技能；无法确认时把状态记为待确认。'),('拆成交付规格',f'围绕“{subject}”列出输入、输出格式、数量、截止时间和不可做范围，原帖没有写清的逐项追问。'),('制作证明能力的小样',sample+'；把源文件、脚本版本或操作记录留在自己手里。'),('写具体响应','用“我理解你要的是X；这里是一个真实小样；还需确认Y；确认后按Z交付”组织回复，不承诺没测试过的速度。'),('报价与确认','只有原帖预算有证据时才引用预算；否则按样例耗时、难度与返工量给区间，并明确币种、支付节点和手续费承担方。'),('交付与验收','先交可检查的一小部分，核对数量、字段或效果；留存验收记录，再按约定交最终文件。'),('形成复购','交付后问是否有周期任务；把可复用步骤做成模板，记录实际耗时和回款，别把一次报价当作持续收入。')]
        reverse=[('谁付钱','有明确需求和预算权限的发帖人；平台用户名、帖子热度本身不等于支付能力。'),('付钱买什么',f'买的是“{subject}”的可验收结果、节省的等待与返工，而不是你用了哪种AI。'),('收入入口','原帖允许的回复、申请或私信渠道；优先保留能回到同一来源的沟通记录。'),('信任如何形成','用与该任务直接相关的小样降低验收不确定性；速度有帮助，但不能代替准确性和付款确认。'),('成本与毛利','记录样品耗时、全量处理耗时、工具/API费、平台费和返工；这些未披露时不能推导利润率。'),('如何提高机会','在同样预算下缩小交付歧义、明确时间窗口；不用“我什么都会”的泛化简历堆信息。'),('怎样复制','只复用已经验证的清洗/自动化/设计流程；每个新客户的数据、权限和验收标准重新确认。'),('停止条件','任务已关闭、付款条款不明、要求越权操作或样品反复扩大时，先停止投入并补证据。')]
    elif kind=='job_posting':
        ecology['recommendations']=['核对招聘来源和申请域名，原帖的地区、工作许可和雇佣形式比“remote”标签更重要。','优先按职位要求做针对性的作品样例；把相关经历放在首屏，避免套用同一份长简历。','薪资区间只是招聘报价，不是你已经获得的收入；合同、试用期与发薪方式要另外确认。','把发布时间和岗位是否仍开放一起看，不能因为聚合站刚收录就认定是刚发布。']
        steps=[('确认适配条件','核对地区、语言、时区、雇佣形式和必须技能，不符合硬条件时不盲投。'),('研究实际交付','从岗位描述提取最常出现的3项成果，选择你能够证明确实做过的一项。'),('准备针对性样例',sample+'；不要使用前雇主的保密数据。'),('通过原始申请入口提交','使用原招聘页给的渠道，保存职位链接和提交日期；不向陌生联系人支付入职费用。'),('核验雇佣条件','面试后核对公司、薪资币种、付款周期和合同，不把招聘页薪资当作已成交。')]
        reverse=[('付款人','招聘公司或有预算的项目团队，而不是聚合网站。'),('他们买的成果',subject+'相关的持续交付、沟通和稳定性。'),('获客入口','官方申请页、明确的招聘联系人或平台申请系统。'),('竞争方式','用符合岗位的作品和具体成果降低筛选成本；不从国籍或浏览量猜竞争强度。'),('成本','准备作品、面试和试做的时间；无合同前不投入长周期免费项目。'),('收入判断','只有录用和实际发薪才能验证收入，招聘薪资与佣金不混为一谈。'),('可复制部分','把作品、问题清单和面试反馈沉淀成可调整的申请材料。'),('待验证','岗位有效性、地区资格、合同主体及发薪安排。')]
    else:
        adult=track=='nsfw_adult';grey=track=='gray_arb'
        ecology['recommendations']=[
            '区分原作者在描述目标、进行中实验、报价还是已收到款项；有金额不等于已成交。',
            '先阅读平台当前规则：支持社区、产品发布区和招聘区的沟通习惯不同；先解决原帖问题，再披露与你的产品或服务的关系。',
            '观察原帖里实际提出问题的人、已有替代方案和反对意见；点赞、流量与收藏不能直接当作付费需求。',
            ('成人平台只分析经营、授权、分成与结算：核对允许的国家、推广渠道、素材授权和实际Offer条款；不沿用原资料里未经核验的佣金或日收入。' if adult else '把可复用能力缩成一个明确的交付；先以小样验证需求，不因为“有人做过”就承诺自己一定能赚。'),
            ('灰色业务要把扣量、退款、权限、账号损耗和平台限制当作实际成本；不把绕过审核、伪装验证码或无授权资源分发作为获客优势。' if grey else '记录对方真正愿意付费的功能或结果；如果只有泛泛讨论，应先验证需求，不直接做完整产品。'),
        ]
        steps=[('还原原帖事实',f'从“{title[:120]}”对应的正文里，摘出用户是谁、遇到什么问题、现在怎样解决；缺正文时先打开源链接补证。'),('列出替代方案','核对用户当前付给谁、自己要花多少时间，以及为什么不满意；没有这些信息就不假定一定有人愿意买。'),('界定最小交付',sample+'；说明这个样例解决哪一项痛点、哪些还没覆盖。'),('找到允许的接触点','按原平台规则在相关讨论、服务区或官方申请入口沟通；不自动群发，不假装已有客户成绩。'),('小规模验证报价','引用有来源的价格或预算；没有证据时先问验收与付款意愿，再做小范围试单。'),('记录真实单位经济','记录投入时间、工具费、平台费、退款与实际到账；把试单验证与规模化收入分开。'),('决定是否复制','只有交付、回款、获客成本和平台许可都清楚时，再复用流程；否则保留为待验证线索。')]
        reverse=[('付款人','从原帖明确提到的客户、雇主、订阅者、广告主或联盟网络确认；没有出现时标记未知。'),('交易价值',f'围绕“{subject}”找节省的时间、提高的准确性或降低的麻烦，不能仅凭抱怨推定付费需求。'),('交易路径','还原“发现问题→接触解决者→看样例→验收→付款”的链条，缺哪一环就先验证哪一环。'),('案例与痛点如何匹配','只把同一任务、用户类型和交付方式的案例当作对照；同属一个赛道不是收入佐证。'),('获客细节','看用户是否正在找人、是否仍未解决、是否允许自荐；用针对性示例代替一条泛化推广链接。'),('成本与毛利','缺流量成本、工具费、抽成、退款或人工时间时，只能列待验证项，不能计算净利润。'),('复制与变体','可复制的是需求识别、样例、交付和售后流程；原作者的粉丝、资源和历史信誉不能直接复制。'),('验证顺序','先验证可接触客户，再验证小样，再验证支付，最后考虑放大；每一步都留下可回溯记录。')]
    profile=profile_for(title,body,track)
    ecology['recommendations'].insert(0,source.get('ecology') or PLATFORMS.get(item.get('platform_id'),{}).get('ecology','先核对原来源当前规则和实际需求，推广许可与采购意愿分别确认。'))
    ecology['recommendations'].extend([profile[1],profile[2]])
    facts=observed_constraints(body)
    if facts:ecology['observed'].extend('原文条件摘录（未改写为保证）：'+quote for quote in facts)
    steps.insert(2,('针对“'+profile[0]+'”的交付样例',profile[2]))
    steps.append(('本项目怎样定价与复购',profile[3]+' '+profile[4]))
    reverse[1]=('具体卖什么及怎样验收',profile[2])
    reverse[4]=('本项目的成本与定价边界',profile[3])
    reverse[6]=('本项目怎样形成复购',profile[4])
    return ecology,[{'step':i+1,'title':title,'detail':detail} for i,(title,detail) in enumerate(steps)],[{'dimension':title,'detail':detail} for title,detail in reverse]

def analyze(raw,source,environment='local'):
    if raw.get('community'):
        source={**source,'name':'Reddit r/'+raw['community']+'（联合订阅）','adult':raw['community'].lower() in {'creatorsadvice','onlyfansadvice'}}
    title=clean(raw.get('title',''));body=clean(raw.get('body',''))
    if re.search(r'\bnudify\b|\bdeepnude\b|non.?consensual|undress(?:ing)?.{0,30}photo|remove clothes.{0,30}photo|脱衣.{0,15}照片|深度伪造.{0,15}裸',title+' '+body,re.I):return None
    if not title or PROMO.search(title+' '+body):return None
    multilingual=re.search(r'ingresos|clientes|ganar dinero|revenus|gagner|выручк|доход|клиент|заработ|receita|clientes|faturamento|売上|収益|副業|顧客|案件|有料|報酬|受注',title+' '+body,re.I)
    if source.get('filter_business',True) and not multilingual and not BUSINESS.search(title+' '+body) and not PAIN.search(title+' '+body) and not BUYER.search(title+' '+body):return None
    if source.get('platform')=='github_bounties' and re.search(r'\$\s*0(?:\]|\s|\.|$)|zero.bounty|不付钱',title+' '+body,re.I):return None
    if source.get('platform')=='hackernews' and (not body or re.search(r'\b(?:stock|shares|scandal|election|deepfake scam|annualized revenue)\b',title,re.I)):return None
    if 'github.com/' in raw.get('external_url','') and not body:return None
    kind,track=kind_for(title,body,source)
    subject,_=service_subject(title,body)
    labels={'buyer_request':'付费需求','seller_offer':'卖方服务/竞品报价','job_posting':'招聘机会','pain_point':'需求痛点','tool_launch':'工具/竞品线索','method_discussion':'方法与风险讨论','business_discussion':'商业讨论'}
    item={'id':hashlib.sha256((raw['url']+'|'+source['platform']).encode()).hexdigest()[:24],
        'kind':kind,'track':track,'title_zh':'【'+labels.get(kind,'商业线索')+'】'+title,'raw_title_en':title,
        'source_platform':source['name'],'platform_id':source['platform'],'source_id':source['id'],
        'source_url':raw['url'],'published_at':raw.get('published_at'),'fetched_at':utc_now(),
        'environment':environment,'body_observed':bool(body),'body_length':len(body),'_body':body[:12000],
        'evidence_excerpt':body[:180] if body else '', 'reply_count':raw.get('reply_count'),
        'location':raw.get('location'),'reference_only':False,'body_scope':raw.get('body_scope','来源提供的正文/摘要'),
        'audit':'已读取来源提供的正文/摘要；观点与收款说法未独立核验' if body else '只有来源标题/链接；没有补写赚钱故事'}
    if raw.get('body_scope'):item['audit']=raw['body_scope']+'；金额与到账另看证据。'
    if raw.get('platform_metrics'):item['platform_metrics']=raw['platform_metrics']
    if raw.get('market_quote'):item['market_quote']=raw['market_quote']
    item['financial_evidence']=financial_evidence(title,body,kind)
    if kind in {'market_observation','platform_metrics'}:item['financial_evidence']=[]
    if kind not in {'buyer_request','job_posting','seller_offer'} and item['financial_evidence']:
        item['kind']='seller_report';item['title_zh']='【正文收入说法·待核验】'+title
    item['pain_point_zh']=('正文可见的需求/背景：'+body[:260]) if body else '缺少正文证据，请展开源链接核对具体需求；不从标题补写故事。'
    item['solver_case_zh']='尚未找到与该需求严格对应、可核验的付费解决案例。'
    if item['kind']=='seller_report':item['solver_case_zh']='这条是原文披露的收入说法，下面保留金额和语境。没有独立核对付款凭证，也没把它冒充与你要做的需求完全相同的成交。'
    if item['kind']=='platform_metrics':item['solver_case_zh']='这里是平台公开展示的订阅/营收指标，可以反过来看它卖什么。它不是净利润，也不是本监控台审计过的银行到账。'
    item['platform_ecology'],item['action_steps'],item['reverse_model']=detailed_strategy(item,source)
    item['strategy_label']='以下是基于来源内容的执行建议与商业推理，不是已经验证的收益。'
    from .editorial import apply
    apply(item,source)
    return item
