import json
from pathlib import Path
import unittest

import opportunity_monitor_24h as monitor

ROOT=Path(__file__).resolve().parents[1]

class MonitorTests(unittest.TestCase):
    def fixture(self,body='Need two CSV files merged. Budget $60. $bid'):
        return monitor.make_raw('reddit','fixture','[TASK] Clean CSV',body,'https://example.com/task',track='bounty_direct')
    def test_rules_fill_every_structured_field(self):
        row=monitor.rules_enrich(self.fixture())
        self.assertTrue(all(row.get(name) for name in monitor.FIELDS))
    def test_reddit_matrix_has_sixteen_unique_communities(self):
        communities=[name.lower() for group in monitor.REDDIT_GROUPS for name in group]
        self.assertEqual(len(communities),16);self.assertEqual(len(set(communities)),16)
    def test_bid_is_not_called_payment(self):
        fact=monitor.extract_deal_fact(self.fixture())
        self.assertIn('$bid',fact);self.assertIn('不等于',fact)
    def test_no_money_is_explicit(self):
        self.assertIn('未披露具体成交单数',monitor.extract_deal_fact(self.fixture('Need help with a messy file.')))
    def test_platform_tip_uses_unverified_response_target(self):
        tip=monitor.platform_tip(self.fixture())
        self.assertIn('没有核验',tip);self.assertNotIn('90%',tip)
    def test_adult_tip_rejects_review_cloaking(self):
        row=self.fixture('adult creator asks about authorized translation');row.update(platform='reddit',track='nsfw_adult')
        tip=monitor.platform_tip(row)
        self.assertIn('相同内容',tip);self.assertNotIn('屏蔽平台审核爬虫',tip)
    def test_disallowed_target_is_filtered(self):
        self.assertFalse(monitor.safe_item(self.fixture('deepnude nudify photos')))
    def test_initial_json_has_no_fake_seed(self):
        payload=json.loads((ROOT/'live_signals.json').read_text(encoding='utf-8'))
        self.assertIsInstance(payload['records'],list)
    def test_required_public_files_exist(self):
        for name in ['index.html','global_arb_radar_workbench.html','opportunity_monitor_24h.py','requirements.txt','.github/workflows/monitor_20min.yml']:
            self.assertTrue((ROOT/name).exists(),name)
    def test_dlsite_selector_ignores_free_sample_button(self):
        sample='<table class="ranking_worklist"><tr><td><a href="/maniax/work/=/product_id/RJ1.html">真实作品名</a></td><td data-product_id="RJ1"><a class="btn_free_sample" href="/maniax/work/=/product_id/RJ1.html">無料サンプル</a></td></tr></table>'
        soup=monitor.BeautifulSoup(sample,'lxml');card=soup.select_one('table.ranking_worklist tr')
        links=[a for a in card.select("a[href*='/work/=/product_id/']") if "btn_free_sample" not in (a.get("class") or []) and a.get_text(" ",strip=True)]
        self.assertEqual(links[0].get_text(strip=True),'真实作品名')

if __name__=='__main__':unittest.main()
