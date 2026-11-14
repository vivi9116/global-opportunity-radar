"""Curate the supplied v9.3 scenarios without carrying over invented proof."""
from pathlib import Path
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from radar.analysis import detailed_strategy,utc_now
from radar.engine import save

ROOT=Path(__file__).resolve().parents[1]
rows=[
 ('v93_reference_csv','pain_saas','表格清洗与名录整理：从付费抱怨验证代处理或买断工具需求','原v9.3资料 · SaaS/表格需求','https://www.reddit.com/r/SaaS/','用户可能只偶尔需要合并CSV、匹配客户表格或整理公开名录。需要先核对实际文件、重复规则、字段和数据权限，不能仅凭抱怨就认定愿意付费。'),
 ('v93_reference_bounty','bounty_direct','海外论坛悬赏接单：用真实小样截图证明交付能力','原v9.3资料 · 海外公开接单社区','https://www.reddit.com/r/forhire/new/','这是观察公开任务帖和制作任务相关小样的策略，不是一张已经验证成交的具体订单。关注CSV、公开数据整理与自动化任务时，先确认任务仍开放、预算、交付规格、时区与支付节点。'),
 ('v93_reference_adult','nsfw_adult','成人订阅与联盟项目：核对流量、Offer条款、授权和结算证据','原v9.3资料 · 成人商业/联盟','https://www.blackhatworld.com/forums/my-journey-discussions.167/','只研究成人内容平台的经营、订阅、合法素材授权、广告和联盟结算。原资料里的佣金、分成和日收入未得到独立验证，因此不展示为真实收益；需要核对当前Offer、国家、渠道限制与退款扣量。'),
 ('v93_reference_resources','gray_arb','授权资源整理与赞助解锁：先验证授权、任务告知和真实需求','原v9.3资料 · 资源整理/CPA风险','https://ogads.com/','资源求助可能对应整理、修复链接或授权分发服务，但免费可下载不代表允许再次分发。需要透明说明赞助任务，不能把商业任务伪装成系统验证码或虚假的99%进度。原资料佣金没有在本轮得到验证。'),
 ('v93_reference_localization','nsfw_adult','数字作品本地化与经营分析：从授权服务和公开销售指标验证需求','原v9.3资料 · 授权本地化服务','https://www.dlsite.com/','可研究平台经营指标、授权翻译、字幕、元数据和语言服务需求，不从作品排行榜推定自己也能复制销量。需要核对作品授权、翻译许可、平台内容规则和公开计数的时间口径；没有验证的销量与收入不填写。'),
]
result=[]
for identifier,track,title,platform,url,body in rows:
    item={'id':identifier,'kind':'reference','track':track,'title_zh':title,'raw_title_en':title,'source_platform':platform,'platform_id':'reference','source_url':url,'published_at':None,'fetched_at':None,'reference_only':True,'body_observed':False,'body_length':0,'evidence_excerpt':'','_body':body,'financial_evidence':[],'pain_point_zh':body,'solver_case_zh':'这是原资料整理的业务方向，不是本轮抓到并核验的一笔成交；没有对应的已核验付款数据。','audit':'原v9.3参考方案；原文的金额、可行性百分比、见钱周期与“已核验”标签未作为事实沿用。','strategy_label':'以下是详细执行建议与商业推理，需要逐项验证；不代表已实现收益。'}
    item['platform_ecology'],item['action_steps'],item['reverse_model']=detailed_strategy(item,{'format':'用户提供的参考资料'})
    item.pop('_body',None);result.append(item)
save(ROOT/'data/reference_projects.json',result)
print('Curated reference projects:',len(result))
