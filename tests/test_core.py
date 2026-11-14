import io
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch,MagicMock
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

from radar.analysis import analyze,financial_evidence
from radar.catalog import default_sources
from radar.engine import Engine,public_record,save
from radar.fetch import HTTPClient,FetchFailure,safe_public_url
from radar.parsers import parse
from radar.server import Handler

SOURCE={'id':'test_source','platform':'reddit','name':'Fixture source','format':'rss','filter_business':False}

class EvidenceTests(unittest.TestCase):
    def test_title_money_is_not_payment_proof(self):
        item=analyze({'title':'My goal: $10000 a month','body':'','url':'https://example.com/a'},SOURCE)
        self.assertFalse(item['body_observed']);self.assertEqual(item['financial_evidence'],[])
    def test_goals_costs_and_income_are_distinct(self):
        self.assertEqual(financial_evidence('','My goal is $5000. I spent $200. I received a refund of $100.','business_discussion'),[])
        result=financial_evidence('','I earned $125 from client work.','business_discussion')
        self.assertEqual(result[0]['amount'],'$125');self.assertIn('未独立',result[0]['verification'])
        self.assertEqual(financial_evidence('','Budget is $200.','buyer_request')[0]['nature'],'买方预算/报价')
    def test_budget_word_does_not_make_software_a_buyer(self):
        item=analyze({'title':'Show HN: Budget tool','body':'A budget app for freelancers','url':'https://example.com/b'},SOURCE)
        self.assertEqual(item['kind'],'tool_launch')
    def test_employer_funding_and_applicant_fees_are_not_salary(self):
        body='Our company is backed by €280M in total funding. We process $16M in annual GMV. You pay $40 for a background check. Compensation is $20 per hour.'
        result=financial_evidence('',body,'job_posting')
        self.assertEqual([x['amount'] for x in result],['$20'])
    def test_seller_offer_and_zero_bounty_are_not_paid_demand(self):
        item=analyze({'title':'[FOR HIRE] Video editor','body':'My rate is $15/hour.','url':'https://example.com/offer'},SOURCE)
        self.assertEqual(item['kind'],'seller_offer');self.assertEqual(item['financial_evidence'][0]['nature'],'卖方服务报价')
        source={**SOURCE,'platform':'github_bounties','buyer_source':True}
        self.assertIsNone(analyze({'title':'[Bounty] Answer this','body':'This is a zero-bounty task: $0.','url':'https://example.com/zero'},source))
    def test_task_has_ecology_specific_deliverables_and_legacy_note(self):
        item=analyze({'title':'[TASK] Clean two CSV files','body':'Need someone to merge two CSV files. Budget is $40.','url':'https://example.com/task'},SOURCE)
        self.assertEqual(item['track'],'bounty_direct');self.assertIn('未核验',item['platform_ecology']['legacy_note'])
        self.assertGreaterEqual(len(item['action_steps']),8);self.assertEqual(len(item['reverse_model']),8)
        self.assertIn('主键',json.dumps(item['action_steps'],ensure_ascii=False))
    def test_generic_income_news_without_body_is_rejected(self):
        source={**SOURCE,'platform':'hackernews'}
        self.assertIsNone(analyze({'title':'Company revenue hits $10B','body':'','url':'https://example.com/news'},source))
    def test_candidate_matching_does_not_invent_a_deal(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine=Engine(tmp)
            buyer=analyze({'title':'[TASK] CSV data automation','body':'Need someone for CSV data automation.','url':'https://example.com/task'},SOURCE)
            seller=analyze({'title':'My CSV data service','body':'I earned $125 with CSV data automation.','url':'https://example.com/result'},SOURCE)
            engine.pair([buyer,seller]);self.assertTrue(buyer['candidate_solver_matches'])
            self.assertIn('不证明',buyer['candidate_solver_matches'][0]['relationship'])
    def test_public_export_omits_body_contact_and_credentials(self):
        record=public_record({'id':'x','_body':'private text','note':'email test@example.com ghp_'+'A'*36})
        self.assertNotIn('_body',record);self.assertNotIn('test@example.com',record['note']);self.assertNotIn('ghp_',record['note'])
    def test_unconnected_sites_are_not_counted_as_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            save(Path(tmp)/'sources.json',[{'id':'a','platform':'unconnected','name':'not connected','enabled':False,'reason':'not configured'}])
            result=Engine(tmp).scan()
            self.assertEqual(result['coverage']['successful_platforms'],0)
            self.assertEqual(result['coverage']['not_connected_platforms'],1)
            self.assertFalse(result['cloud']['last_run_record'])
    def test_cloud_sync_rejects_local_data_masquerading_as_actions(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine=Engine(tmp);save(Path(tmp)/'cloud_config.json',{'repository':'owner/repo','mode':'cloud'})
            incoming=[json.dumps({'environment':'local','signals':[]}),'{"sources":[]}','[]']
            with patch('radar.engine.HTTPClient.get',side_effect=[(raw,{'http_status':200}) for raw in incoming]):
                with self.assertRaises(ValueError):engine.sync_cloud()
            self.assertFalse((engine.data/'latest.json').exists())

class SourceTests(unittest.TestCase):
    def test_parse_atom_body_without_treating_html_as_feed(self):
        raw='<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Task</title><link href="https://example.com/task"/><content type="html">Need CSV work</content><updated>2026-11-14T00:00:00Z</updated></entry></feed>'
        self.assertEqual(parse(raw,SOURCE)[0]['body'],'Need CSV work')
        with self.assertRaises(ValueError):parse('<html><body>Login</body></html>',SOURCE)
    def test_hn_comment_uses_comment_permalink_and_actual_text(self):
        row=parse(json.dumps({'hits':[{'objectID':'123','story_title':'Ask HN','comment_text':'I earned $10.','created_at':'2026-11-14T00:00:00Z'}]}),{**SOURCE,'format':'hn'})[0]
        self.assertEqual(row['url'],'https://news.ycombinator.com/item?id=123');self.assertIn('$10',row['body'])
    def test_429_pauses_host_without_another_request(self):
        state={'sources':{},'host_backoff':{}};client=HTTPClient(state)
        client.opener.open=MagicMock(side_effect=urllib.error.HTTPError('https://example.com/a',429,'rate limit',{'Retry-After':'3600'},io.BytesIO()))
        with self.assertRaises(FetchFailure) as first:client.get('https://example.com/a','a')
        with self.assertRaises(FetchFailure) as second:client.get('https://example.com/b','b')
        self.assertEqual(first.exception.status,'rate_limited');self.assertEqual(second.exception.status,'paused');self.assertEqual(client.opener.open.call_count,1)
    def test_local_urls_are_not_sources(self):
        for url in ['http://localhost/a','http://127.0.0.1/a','file:///etc/passwd','https://user:password@example.com/a']:
            self.assertFalse(safe_public_url(url))
    def test_304_without_validated_cache_is_not_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine=Engine(tmp)
            source={**SOURCE,'url':'https://example.com/feed'}
            with patch('radar.engine.HTTPClient.get',return_value=(None,{'http_status':304})):
                records,status=engine.one(source)
            self.assertEqual(records,[]);self.assertEqual(status['status'],'cache_without_validated_data')
    def test_registry_has_unique_ids_and_disabled_reasons(self):
        sources=default_sources();self.assertEqual(len(sources),len({s['id'] for s in sources}))
        self.assertGreaterEqual(len({s['platform'] for s in sources if s.get('enabled',True)}),20)
        for source in sources:
            if not source.get('enabled',True):self.assertTrue(source['reason'])

class ServerTests(unittest.TestCase):
    def test_reading_cache_does_not_scan_and_private_routes_are_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            engine=Engine(tmp)
            server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
            server.engine=engine;server.interval=1200;server.wake=threading.Event()
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            base='http://127.0.0.1:'+str(server.server_port)
            try:
                with patch.object(engine,'scan',side_effect=AssertionError('GET must not scan')):
                    with urllib.request.urlopen(base+'/api/signals') as r:self.assertEqual(json.load(r)['signals'],[])
                with self.assertRaises(urllib.error.HTTPError) as exc:urllib.request.urlopen(base+'/private/radar_history.sqlite')
                self.assertEqual(exc.exception.code,404)
                request=urllib.request.Request(base+'/api/refresh',data=b'',method='POST',headers={'Origin':'https://untrusted.example'})
                with self.assertRaises(urllib.error.HTTPError) as exc:urllib.request.urlopen(request)
                self.assertEqual(exc.exception.code,403);self.assertFalse(server.wake.is_set())
            finally:server.shutdown();server.server_close();thread.join()

class PublishTests(unittest.TestCase):
    def test_bundle_allowlist_excludes_private_inputs_and_data(self):
        from cloud.build_publish_bundle import build
        with tempfile.TemporaryDirectory() as tmp:
            destination,manifest=build(tmp)
            names=[x['path'] for x in manifest['files']]
            self.assertIn('.github/workflows/collect.yml',names)
            self.assertFalse(any(x.startswith('private/') or x.endswith('.zip') or x in {'data/catalog.json','data/latest.json'} for x in names))
            state=json.loads((destination/'data/source_state.json').read_text())
            self.assertEqual(state,{'sources':{},'host_backoff':{}})

if __name__=='__main__':unittest.main()
