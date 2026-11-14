"""The supplied v9.2 is a topic/style reference, never a source of verified income."""
import re

THEMES={'nsfw_adult':'成人联盟/订阅生意','gray_arb':'CPA、流量与域名门道','bounty_direct':'帮老外干杂活收服务费','pain_saas':'表格、脚本与买断小工具','tools':'卖小工具与数字交付','market_watch':'预测市场公开报价','global_business':'其他搞钱线索','remote_work':'普通岗位（扩展资料）'}
TOPIC=re.compile(r'affiliate|cpa|content.lock|monetiz|payout|popunder|push traffic|ad revenue|domain park|expired domain|one.time|lifetime deal|first sale|telegram bot|csv|excel|scrap|automation|digital product|template|creator|onlyfans|fanvue|成人|联盟|佣金|弹窗|域名|流量变现|买断|接单|表格|脚本|数字产品|自动化|首单',re.I)
LONG_TAIL=re.compile(r'royalt|paid plugin|asset store|commission|rev.?share|reward|paid test|localiz|translation|microtask|revenue.share|patreon|gumroad|ko.?fi|license|付费插件|游戏素材|模组分成|平台奖励|测试报酬|本地化|授权费|跨区|配音|字幕',re.I)

def apply(item,source=None):
    source=source or {};track=item.get('track','global_business');kind=item.get('kind','')
    text=item.get('raw_title_en','')+' '+item.get('_body',item.get('pain_point_zh',''))
    preferred=track in {'nsfw_adult','gray_arb','bounty_direct','pain_saas','market_watch'} or bool(source.get('preferred_theme')) or bool(TOPIC.search(text)) or bool(LONG_TAIL.search(text))
    if kind=='job_posting' or re.search(r'full.time|permanent position|senior.*engineer|nurse practitioner',item.get('raw_title_en',''),re.I):preferred=False
    if item.get('platform_id')=='trustmrr':
        metric=next((m['value'] for m in item.get('platform_metrics',[]) if m['label']=='MRR'),'')
        match=re.search(r'[\d,]+(?:\.\d+)?',metric)
        if match and float(match.group().replace(',',''))>20000:preferred=False
    technical_communities={'make','n8n','wordpress','sitepoint','obsidian','cnode','ruby_china','zenn','devto','roblox','curseforge'}
    if item.get('platform_id') in technical_communities and kind not in {'buyer_request','seller_report','seller_offer'} and not re.search(r'\b(?:paid|pay|budget|hiring|hire|commission|revenue|sale|income|payout|monetiz\w*|reward|donation)\b|预算|付费|报价|外包|赚|收入|佣金|嫌.*贵|月租|買い|売上|報酬',text,re.I):preferred=False
    item['editorial_match']=preferred;item['plain_track_zh']=THEMES.get(track,'其他搞钱线索')
    item['editorial_note']='按用户v9.2参考的选题收录；来源原文、报价和实际到账分别看。' if preferred else '保留在扩展资料里，默认不挤占赚钱门道看板。'
    item['strategy_label']='下面讲怎么试第一单、怎么拿样品找客户；是操作思路，不是保赚承诺。'
    headings={'还原原帖事实':'先搞清这人到底在烦什么','列出替代方案':'他现在找谁干，为啥还不满意','界定最小交付':'先做哪一小块，让他一眼能验收','找到允许的接触点':'第一条回复去哪里发、说什么','小规模验证报价':'先把钱和活对上，再谈报价','记录真实单位经济':'这一单花多久，到手还剩多少','决定是否复制':'哪一步跑通，下次就复用哪一步','确认机会仍有效':'先看活还在不在，别给旧帖白干','拆成交付规格':'把要交的东西问具体','制作证明能力的小样':'先甩一张真实样品截图','写具体响应':'少说我会干，摆出样品和缺的条件','报价与确认':'钱、时间、改几次，先说清','交付与验收':'先验收一小段，再交全量','形成复购':'问问这活是不是每周每月都要干','本项目怎样定价与复购':'第一单怎么报价，第二单怎么再来'}
    for step in item.get('action_steps',[]):step['title']=headings.get(step['title'],step['title'])
    dimensions={'谁付钱':'钱从谁口袋出','付款人':'钱从谁口袋出','具体卖什么及怎样验收':'你交哪样东西，让人愿意付钱','收入入口':'第一批对口的人，到哪找','获客入口':'第一批对口的人，到哪找','信任如何形成':'别人凭啥先信你，样品摆啥','交易路径':'从看到你到真付款，中间几步','本项目的成本与定价边界':'别光看收多少，还得扣掉什么','本项目怎样形成复购':'同一套本事，下次还能卖给谁'}
    for dimension in item.get('reverse_model',[]):dimension['dimension']=dimensions.get(dimension['dimension'],dimension['dimension'])
    return item
