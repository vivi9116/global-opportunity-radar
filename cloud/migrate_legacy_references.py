"""Keep useful v6 topics without importing its unsupported verification/money claims."""
from pathlib import Path
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from radar.analysis import detailed_strategy
from radar.engine import save,load

ROOT=Path(__file__).resolve().parents[1]
TOPICS=[
 ('gray_arb','预测市场规则与研究工具：先核对数据、费用与执行风险','原资料含“无风险”“本金翻百倍”等未经核验表述，不作为收益依据；只保留数据研究工具这个方向，不能据静态样例推定可成交或可盈利。'),
 ('pain_saas','CSV 清洗与匹配服务：先验收字段和真实文件','原资料引用的首单、月收入和时间均未在本轮核验；保留从表格痛点做小样、代处理和工具交付的思路。'),
 ('gray_arb','BHW 视觉内容与联盟经营：核对流量许可和到账证据','连载目标、方法讨论、联盟后台收入与实际到账需要分开。只保留获准渠道、授权素材和透明推广的经营分析，不沿用免审或防封保证。'),
 ('global_business','用户研究与小任务平台：核对资格、时间成本和提现','研究招募是否面向所在国家、语言和人群，是否还有名额，均需看当前具体任务；不承诺固定时薪，不替用户抢受限名额。'),
 ('global_business','数字手账与解谜资料：先验证题材需求和交付质量','可验证的价值是原创内容、排版、可打印文件、使用说明与售后；原资料没有可独立验证的销量，不能据热帖推定市场已买单。'),
 ('global_business','本地服务商户预约流程：从实际运营问题找服务机会','先确认商户是否需要线上预约、现有工具为何不够、谁负责维护；不把原文求助改写成已经购买网站的客户。用户无需以经营独立站为主业。'),
 ('gray_arb','跨平台数据比较与告警工具：先验证时间戳与数据一致性','原资料关于重新定价滞后的秒数和套利结论未核验；数据延迟、费用、可成交量与规则变化都会影响结果。保留研究与告警需求，不提供盈利承诺。'),
 ('pain_saas','聊天机器人与表格自动化：拆清权限、流程和维护','从一个真实重复工作开始，用测试数据验证触发、转换、写入与异常告警；原资料收入不能当作已经实现的客户收益。'),
 ('tools','车内用品内容服务：核对卖家需求和素材权限','保留产品演示、拍摄与授权内容服务的方向；原资料没有本轮已核验的GMV、转化率或成交，不把它当作当前爆品榜单。'),
 ('global_business','宠物主题内容与联盟：先验证受众、授权和Offer','原创或获授权内容先解决真实受众问题；点击、播放与佣金到账分开，不承诺挂一个商品就能成交。'),
 ('tools','日用喷雾演示内容：先确认产品证据和广告主需求','原资料中的三秒效果、销量和佣金没有在本轮核验；如做内容服务，只承诺能验收的素材交付，不虚构使用效果。'),
 ('global_business','食品过程类内容：从拍摄、剪辑与品牌素材交付验证需求','先确认素材使用权、真实制作过程和客户需求；制作可检查的短样片，不能把视觉热度直接当商品销量。'),
 ('pain_saas','离线客户跟进工具：从订阅成本痛点验证买断需求','先问用户必须的字段、导入导出、备份和使用频率；原资料销量和金额未核验，不能据此补写成交。'),
 ('global_business','授权短视频再编辑服务：明确版权与交付边界','保留剪辑、字幕与多尺寸输出需求；镜像、变速和加边框不等于获得版权或平台允许，不能把规避重复检测当作卖点。'),
]

def main():
    legacy=load(ROOT/'private/legacy_evidence/v6-original-content.json',{})
    original=legacy.get('arrays',{}).get('INITIAL_SIGNALS',[])
    refs=[r for r in load(ROOT/'data/reference_projects.json',[]) if not r['id'].startswith('v6_reference_')]
    for index,(track,title,body) in enumerate(TOPICS):
        if index>=len(original):break
        old=original[index]
        item={'id':'v6_reference_'+str(index),'kind':'reference','track':track,'title_zh':title,'raw_title_en':title,'source_platform':'原v6 HTML资料 · '+old.get('source','待核验来源'),'platform_id':'reference','source_url':old.get('url',''),'published_at':None,'fetched_at':None,'reference_only':True,'body_observed':False,'body_length':0,'evidence_excerpt':'','_body':body,'financial_evidence':[],'pain_point_zh':body,'solver_case_zh':'旧版资料中的案例、链接匹配和金额尚未独立核验，不将其归为真实成交。','audit':'从原v6 HTML内容迁移。原“已核验”、分数、成功率、预填成交、盘口样例和收入数字未作为事实沿用；完整原始内容保存在本地private/legacy_evidence。','strategy_label':'这是保留的参考方向和操作建议，不是本轮抓取的新项目或已验证收益。'}
        item['platform_ecology'],item['action_steps'],item['reverse_model']=detailed_strategy(item,{'format':'本地旧HTML内容迁移'})
        item.pop('_body');refs.append(item)
    save(ROOT/'data/reference_projects.json',refs)
    print('Reference projects after preserving v6:',len(refs))

if __name__=='__main__':main()
