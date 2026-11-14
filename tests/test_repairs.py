import csv
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch,MagicMock
import urllib.error
from radar.analysis import analyze
from radar.catalog import default_sources
from radar.engine import Engine
from radar.fetch import HTTPClient,FetchFailure,retry_delay,challenge_title
from radar.html_sources import warrior,trustmrr
from radar.translation import split_translation,translate

class RepairTests(unittest.TestCase):
    def test_actual_bot_page_is_a_challenge_even_with_http200(self):
        self.assertEqual(challenge_title('<html><title>Bot Verification</title></html>'),'Bot Verification')
        self.assertIsNone(challenge_title('<html><title>Business ideas</title></html>'))
    def test_cloudflare403_explains_observed_challenge(self):
        state={'sources':{},'host_backoff':{}};client=HTTPClient(state)
        client.opener.open=MagicMock(side_effect=urllib.error.HTTPError('https://example.com',403,'forbidden',{},io.BytesIO(b'<title>Just a moment...</title><script src="/cf-chl-"></script>')))
        with self.assertRaises(FetchFailure) as exc:client.get('https://example.com','fixture')
        self.assertEqual(exc.exception.status,'challenge');self.assertIn('Just a moment',str(exc.exception));self.assertTrue(state['host_backoff'])
    def test_retry_after_http_date_is_respected(self):
        with patch('radar.fetch.time.time',return_value=0):self.assertEqual(retry_delay('Thu, 01 Jan 1970 02:00:00 GMT'),7200)
    def test_reddit_is_one_combined_request_not_18_bursts(self):
        active=[s for s in default_sources() if s['platform']=='reddit' and s['enabled']]
        self.assertEqual(len(active),3);self.assertEqual(sum(len(s['communities']) for s in active),18);self.assertTrue(all(len(s['communities'])<=6 for s in active));self.assertIn('+',active[0]['url'])
    def test_warrior_html_reads_public_excerpt_and_date(self):
        raw='<article class="ArticleSnapshot"><h3 class="ArticleSnapshot-title"><a href="https://www.warriorforum.com/test/123-job.html?utm_source=x">Paid CSV task</a></h3><time datetime="2026-11-14T10:00:00Z"></time><p itemprop="description">Need a small CSV cleanup.</p></article>'
        rows=warrior(raw);self.assertEqual(len(rows),1);self.assertEqual(rows[0]['url'],'https://www.warriorforum.com/test/123-job.html');self.assertIn('摘要',rows[0]['body_scope'])
    def test_platform_mrr_is_not_invented_profit(self):
        raw='<table><tr><th>#</th><th>Startup</th><th>Founder</th><th>MRR</th><th>MoM Growth</th></tr><tr><a href="/startup/test"><td>1</td><td>CSV tool</td><td>A</td><td>$1,200</td><td>5%</td></a></tr></table>'
        row=trustmrr(raw)[0]
        item=analyze(row,{'id':'mrr','platform':'trustmrr','name':'TrustMRR','format':'trustmrr_html','filter_business':False})
        self.assertEqual(item['financial_evidence'],[]);self.assertEqual(item['platform_metrics'][0]['value'],'$1,200')
    def test_translation_segments_cannot_be_silently_misassigned(self):
        self.assertEqual(split_translation('⟦R0⟧\n第一条\n⟦R1⟧\n第二条',2),['第一条','第二条'])
        with self.assertRaises(ValueError):split_translation('⟦R1⟧\n内容',2)
    def test_translation_preserves_original_evidence(self):
        item={'id':'a','track':'bounty_direct','editorial_match':True,'raw_title_en':'CSV cleanup request','_body':'','title_zh':'raw','financial_evidence':[{'amount':'$60','quote':'Budget $60'}]}
        response=json.dumps([[['⟦R0⟧\n清理CSV表格需求',None]]])
        with patch('radar.translation.HTTPClient.get',return_value=(response,{})):report=translate([item],{}, {'sources':{},'host_backoff':{}})
        self.assertIn('清理CSV',item['title_zh']);self.assertEqual(item['raw_title_en'],'CSV cleanup request');self.assertEqual(item['financial_evidence'][0]['quote'],'Budget $60');self.assertEqual(report['new_fields'],1)
    def test_csv_sample_flags_ambiguity_instead_of_losing_rows(self):
        file=Path(__file__).resolve().parents[1]/'assets/csv_merge_sample.py';spec=importlib.util.spec_from_file_location('csv_sample',file);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as tmp:
            a=Path(tmp)/'a.csv';b=Path(tmp)/'b.csv';out=Path(tmp)/'out.csv'
            a.write_text('company,left\n ACME ,1\nDuplicate,2\n,3\n',encoding='utf-8');b.write_text('company,value\nacme,yes\nDuplicate,a\nDuplicate,b\n',encoding='utf-8')
            self.assertEqual(module.merge(a,b,'company',out),3)
            with out.open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
            self.assertEqual([r['match_status'] for r in rows],['matched','ambiguous','missing_key']);self.assertEqual(rows[0]['right_value'],'yes');self.assertEqual(rows[1]['right_value'],'')
            with self.assertRaises(ValueError):module.merge(a,b,'company',a)
