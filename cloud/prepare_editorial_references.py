"""Curate the user's v9.2 topics and plain language; never execute attached JS."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from radar.analysis import detailed_strategy
from radar.editorial import apply
from radar.engine import save,load
ROOT=Path(__file__).resolve().parents[1]

TOPICS=[
 ('bounty_01','bounty_direct','帮老外干一件小杂活：先甩真实样品，再谈整单','钱是急着解决问题的发帖人给的。你交的不是一张“我会写代码”的简历，而是能验收的表格、脚本、字幕或小功能。发现任务先确认还开不开，做一小段真实结果截图；不要先免费干完整单。'),
 ('bounty_02','pain_saas','帮老板把两张乱表对齐：卖的是省掉手工核对的麻烦','先问两张表靠哪个字段对齐，名字缩写、空格、重复行和空值怎么算。拿脱敏小表做对照，匹配不上或撞名的单列出来给老板确认。收入与工作量要看真实订单，不能把参考资料中的金额当本次到账。'),
 ('nsfw_01','nsfw_adult','成人联盟拉新：老外完成合格注册或订阅，你拿佣金','把“有兴趣的访客→明确告知的推广入口→合格注册或订阅→广告主确认→达到结算条件后回款”串起来。先选国家、计费动作、允许的渠道和扣量规则都清楚的Offer，再做小范围测试。'),
 ('nsfw_03','nsfw_adult','围绕成人创作者收服务费：本地化、经营表和素材整理','付款人也可以是创作者，而不只是订阅用户。把有授权的字幕、翻译、元数据、经营统计或素材管理做成一项能验收的小服务。先给脱敏或获授权的样品，记录人工、推广、抽成和回款。'),
 ('gray_01','gray_arb','免费资源换赞助任务佣金：关键是资源真有用、规则讲清楚','先找别人正在求、且你有权整理或分发的模板、插件或资料。展示文件清单和小样，明确告诉访客完成哪项赞助行为才解锁，再按联盟实际确认的转化结算。商业任务不冒充系统验证码，预填人数和假的99%进度不当成信任证明。'),
 ('bounty_03','bounty_direct','给小众老板做脚本、Telegram机器人和自动化杂活','老板买的是少花时间处理一个具体流程。先搞清输入、输出、数量、接口权限和截止时间；用测试数据做15—20秒真实演示，再谈分段交付、验收和付款。群管理只处理自愿加入并授权管理的成员。'),
 ('gray_03','gray_arb','用免费小工具吸引对口的人：再研究平台允许的分成','先做真正解决一个小问题的计算器、筛选器或对照表，让对口用户愿意用。展示推广关系与实际条款，计费动作、退款、国家和结算要分开核对。流量、注册和到账不是同一个数字，不以借工具诱导赌博为获客步骤。'),
 ('saas_01','pain_saas','别人收月租的小功能：研究能否做成一次买断的本地工具','从公开收入榜找只解决一个小问题的产品，再去原用户讨论里找具体嫌贵或卡住的场景。卖自己的独立实现、代处理或更窄的小功能。先问客户为什么不用现成工具，用真实小样验证，不照抄别人的代码、品牌和数据。'),
 ('web3_01','market_watch','预测网站看真实买卖报价：把价差和能否成交分开算','先拿官方接口的买一、卖一、最小下单量与费用参数。挂牌有差价不代表两边都能成交；排队、深度、库存、费用和地区资格都要算。这里保留数据研究方向，不把模拟盘口或固定收益当实盘。'),
 ('stream_adult_chaturbate','nsfw_adult','成人平台经营与推广分成：先看结算合同，再看流量入口','核对平台允许的业务、素材授权、国家、归因窗口、撤销和付款门槛。订阅收入、打赏流水、联盟分成和已经提现的现金分别记，不能把一个公开比例直接乘成自己的收入。'),
 ('stream_bounty_tg_bot','bounty_direct','给付费社群做入群和到期管理：先拿一个流程当样品','先确认群主真正卡在付款确认、给权限、续费还是到期移除。用沙盒支付事件和测试群演示，做好签名校验、重复通知和失败补救；让老板先验收一条完整流程，再谈部署和维护费。'),
 ('stream_gray_expired_domain','gray_arb','老域名还有旧访客：先查干净历史和真流量，再谈停放','外链多不等于还有人访问。买前核对历史用途、商标和真实访问来源，说明新站与原机构的关系，再看停放或广告规则。把注册费、续费和实际结算算进去，别用“几天回本”替代证据。'),
 ('extra_game_assets','global_business','小众游戏的插件、素材和模组：看谁愿意付费省事','去开发者社区找具体的定制、修复、素材和语言需求，或有明确规则的平台创作者分成。下载量不是收入；先做一小段可运行、可验收且有权交付的样品，确认版本、授权、售后和实际回款。'),
 ('extra_platform_rewards','global_business','平台奖励、测试和地区小任务：先查自己到底能不能领钱','研究奖励门槛、所在地、语言、设备、筛选条件和付款主体。先记录一次任务的真实耗时、是否通过和实际到账；不从别人的时薪截图推定自己也能拿到，不伪造地区或身份。'),
 ('extra_niche_services','global_business','到小众圈子找没人爱干的活：修插件、改格式、补资料、做本地化','别只盯大外包站。看游戏、站长、创作者、开源工具和地区语言社区里反复卡住的具体问题。先帮对方看见一个可检查的小结果，再确认愿不愿为全量交付付费。复用自己的流程，逐单记录客从哪来、花多久和是否回款。'),
]

def extract_array(text,name):
    pos=text.find('const '+name)
    if pos<0:return []
    start=text.find('[',pos);depth=0;quoted=False;escaped=False
    for end in range(start,len(text)):
        char=text[end]
        if quoted:
            if escaped:escaped=False
            elif char=='\\':escaped=True
            elif char=='"':quoted=False
            continue
        if char=='"':quoted=True;continue
        if char=='[':depth+=1
        elif char==']':
            depth-=1
            if not depth:
                data=text[start:end+1];data=re.sub(r'(?m)^(\s*)([A-Za-z_]\w*)\s*:',r'\1"\2":',data)
                data=re.sub(r'([\{,]\s*)([A-Za-z_]\w*)\s*:',r'\1"\2":',data)
                data=re.sub(r',\s*([}\]])',r'\1',data)
                return json.loads(data)
    raise ValueError('Reference array is not complete')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--input');args=parser.parse_args();original={}
    if args.input:
        file=Path(args.input);raw=file.read_bytes();text=raw.decode('utf-8-sig')
        arrays={name:extract_array(text,name) for name in ['INITIAL_UNFILTERED_SIGNALS','UNFILTERED_STREAM_POOL']}
        save(ROOT/'private/v92_reference_content.json',{'filename':file.name,'sha256':hashlib.sha256(raw).hexdigest(),'arrays':arrays,'note':'附件按数据解析，没有执行其中脚本。金额、成功率和预填成交未作为事实导入。'})
        original={row['id']:row for rows in arrays.values() for row in rows}
    elif (ROOT/'private/v92_reference_content.json').exists():original={row['id']:row for rows in load(ROOT/'private/v92_reference_content.json',{})['arrays'].values() for row in rows}
    refs=[]
    for identifier,track,title,body in TOPICS:
        old=original.get(identifier,{})
        item={'id':'v92_reference_'+identifier,'kind':'reference','track':track,'title_zh':title,'raw_title_en':title,'source_platform':'用户v9.2参考路子','platform_id':'reference','source_url':old.get('url') or 'https://github.com/vivi9116/global-opportunity-radar','published_at':None,'fetched_at':None,'reference_only':True,'body_observed':False,'financial_evidence':[],'evidence_excerpt':'','_body':body,'pain_point_zh':body,'solver_case_zh':'这是参考思路；本条没有在本轮独立核验一笔付款，不填收益或成功率。','audit':'从用户v9.2内容整理的参考路子，和刚抓到的原帖分开标记。'}
        item['platform_ecology'],item['action_steps'],item['reverse_model']=detailed_strategy(item,{'format':'用户参考资料整理'})
        apply(item);item.pop('_body');refs.append(item)
    save(ROOT/'data/reference_projects.json',refs)
    print(json.dumps({'reference_topics':len(refs),'original_topics_preserved_privately':len(original)},ensure_ascii=False))
if __name__=='__main__':main()
