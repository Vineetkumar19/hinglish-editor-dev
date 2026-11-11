"""Production review/result integration, CPU-only synthetic fixtures."""
import hashlib
import json
import shutil
import subprocess
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from tests import test_visuals_source_bank as fixtures


class SourceResultTests(unittest.TestCase):
    setUp = fixtures.SourceBankTests.setUp
    save = fixtures.SourceBankTests.save

    def test_completed_production_report_emits_source_manifest_and_request_hook(self):
        from hinglish_visuals.report import write_report
        original = self.file.read_bytes(), self.asset.read_bytes()
        write_report(self.folder / 'report.html', self.project)
        active = self.folder / 'source-banks' / 'active.json'
        self.assertTrue(active.is_file())
        pointer = json.loads(active.read_text('utf-8'))
        manifest = json.loads((active.parent / pointer['manifest']).read_text('utf-8'))
        self.assertEqual(manifest['banks'][0]['target'], 2)
        self.assertEqual(manifest['banks'][0]['selection']['state'], 'unreviewed')
        page = (self.folder / 'report.html').read_text('utf-8')
        self.assertIn('Source assets', page)
        self.assertIn('storylensVisualsSourceBank', page)
        self.assertIn('smart_visuals.source_bank.select', page)
        self.assertEqual((self.file.read_bytes(), self.asset.read_bytes()), original)

    def test_production_decisions_are_explicit_resumable_and_never_render(self):
        from hinglish_visuals.source_result import ensure_source_result, apply_source_request
        self.project['slots'].append({**self.slot, 'index': 1, 'start': 1.6, 'end': 2.6})
        self.save()
        baseline = self.file.read_bytes(), self.asset.read_bytes()
        initial = ensure_source_result(self.file)
        payload = {'type': 'smart_visuals.source_bank.select', 'version': 1,
            'project_path': str(self.file.resolve()), 'base_manifest': initial['manifest_path'],
            'base_manifest_sha256': initial['manifest_sha256'], 'choices': {'0': 'web:fixture', '1': ''}}
        with patch('hinglish_visuals.pipeline.render_slot', side_effect=AssertionError('No render')):
            result = apply_source_request(payload)
        self.assertEqual(len(result['selected_sources']), 1)
        self.assertFalse(result['auto_insert'])
        manifest = json.loads(self.folder.joinpath(result['manifest_relative']).read_text('utf-8'))
        self.assertEqual(manifest['banks'][1]['selection']['state'], 'no_visual')
        self.assertEqual(ensure_source_result(self.file)['manifest_sha256'], result['manifest_sha256'])
        self.assertEqual((self.file.read_bytes(), self.asset.read_bytes()), baseline)
        # Two stale open reviews must not overwrite a newer user decision.
        with self.assertRaises(ValueError): apply_source_request(payload)
        self.assertTrue(self.folder.joinpath(initial['manifest_relative']).is_file())

    def test_changed_bytes_or_saved_model_lineage_invalidates_existing_result(self):
        from hinglish_visuals.source_result import ensure_source_result, apply_source_request
        initial = ensure_source_result(self.file)
        payload = {'type': 'smart_visuals.source_bank.select', 'version': 1,
            'project_path': str(self.file), 'base_manifest': initial['manifest_path'],
            'base_manifest_sha256': initial['manifest_sha256'], 'choices': {'0': 'web:fixture'}}
        self.project['model_lineage'] = {'provider': 'local-fixture', 'model_digest': 'changed'}
        self.save()
        with self.assertRaises(ValueError): ensure_source_result(self.file)
        with self.assertRaises(ValueError): apply_source_request(payload)
        self.project.pop('model_lineage')
        self.save()
        self.asset.write_bytes(b'changed image')
        with self.assertRaises(ValueError): ensure_source_result(self.file)
        with self.assertRaises(ValueError): apply_source_request(payload)

    def test_collecting_or_unbound_report_never_advertises_a_source_result(self):
        from hinglish_visuals.report import write_report
        self.project['collecting'] = True
        write_report(self.folder / 'report.html', self.project)
        self.assertFalse((self.folder / 'source-banks' / 'active.json').exists())
        self.project.pop('collecting')
        self.project['brain'] = 'in-memory value differs from saved state'
        write_report(self.folder / 'report.html', self.project)
        page = (self.folder / 'report.html').read_text('utf-8')
        self.assertNotIn('href="source-banks/', page)
        self.assertFalse((self.folder / 'source-banks' / 'active.json').exists())

    def test_invalid_choice_and_unknown_request_do_not_write_a_new_decision(self):
        from hinglish_visuals.source_result import ensure_source_result, apply_source_request
        initial = ensure_source_result(self.file)
        active = self.folder / 'source-banks' / 'active.json'
        before = active.read_bytes()
        payload = {'type': 'smart_visuals.source_bank.select', 'version': 1,
            'project_path': str(self.file), 'base_manifest': initial['manifest_path'],
            'base_manifest_sha256': initial['manifest_sha256'], 'choices': {'0': 'not-offered'}}
        with self.assertRaises(ValueError): apply_source_request(payload)
        payload['type'] = 'unknown'
        with self.assertRaises(ValueError): apply_source_request(payload)
        self.assertEqual(active.read_bytes(), before)

    def test_ordinary_result_writer_keeps_legacy_outputs_and_exposes_raw_bank(self):
        from hinglish_visuals.pipeline import write_outputs
        self.project['options_per_moment'] = 5
        self.slot['clip'] = None
        with patch('hinglish_visuals.pipeline.parse_xmeml', return_value=SimpleNamespace(
                name='Fixture', fps=30, width=1280, height=720, duration=3.)), \
             patch('hinglish_visuals.pipeline.export_tracks_xml', return_value=self.folder/'VISUALS_SEQUENCE.xml') as xml, \
             patch('hinglish_visuals.pipeline.render_slot', side_effect=AssertionError('No render')):
            returned = write_outputs(self.folder, self.folder, self.project, preview=False)
        self.assertEqual(returned, self.folder / 'VISUALS_SEQUENCE.xml')
        xml.assert_called_once()
        self.assertTrue((self.folder/'CREDITS.txt').is_file())
        self.assertTrue((self.folder/'EVALUATION.json').is_file())
        active = json.loads((self.folder/'source-banks/active.json').read_text('utf-8'))
        manifest = json.loads((self.folder/'source-banks'/active['manifest']).read_text('utf-8'))
        self.assertEqual(manifest['options_per_moment'], 5)
        self.assertEqual(manifest['banks'][0]['shortfall'], 4)
        self.assertEqual(manifest['banks'][0]['selection']['state'], 'unreviewed')

    def test_review_click_payload_contains_only_actual_control_decisions(self):
        from hinglish_visuals.report import SCRIPT
        from hinglish_visuals.source_result import ensure_source_result, apply_source_request
        node = shutil.which('node')
        if not node:
            self.skipTest('Node is needed for the CPU-only review-script fixture')
        descriptor = ensure_source_result(self.file)
        project = {'project_path':str(self.file.resolve()), 'source_bank':descriptor,
                   'collecting':False,'slots':[{'clip':None}]}
        # Minimal deterministic DOM fixture. No browser, HTTP, model or host.
        harness = r'''
const vm=require('node:vm');
const saved=new Map(), nodes={};
function element(){return {disabled:true,hidden:true,textContent:'',classList:{toggle(){}},setAttribute(){}}}
for(const id of ['#save','#discard','#status','#editors'])nodes[id]=element();
const card={dataset:{slot:'0'},classList:{toggle(){}},querySelectorAll(){return []}};
const button=element();button.dataset={id:'web:fixture'};button.closest=()=>card;
const none=element();none.dataset={};none.closest=()=>card;
const document={querySelector(s){return s.startsWith('[data-slot')?card:(nodes[s]||null)},
 querySelectorAll(s){return s==='.option,.none'?[button,none]:[]}};
const context={document,window:{},location:{protocol:'http:',origin:'http://local.fixture'},
 sessionStorage:{getItem:k=>saved.get(k)||null,setItem:(k,v)=>saved.set(k,v),removeItem:k=>saved.delete(k)},
 fetch(){throw Error('No transport allowed')},setTimeout(){throw Error('No background work allowed')}};
vm.createContext(context);vm.runInContext(SCRIPT,context);
const initial=context.window.storylensVisualsSourceBank.request();
button.onclick();const picked=context.window.storylensVisualsSourceBank.request();
none.onclick();const removed=context.window.storylensVisualsSourceBank.request();
process.stdout.write(JSON.stringify({initial,picked,removed}));
'''
        script = SCRIPT.replace('__PROJECT__',json.dumps(project)).replace('__FOLDER__',json.dumps(str(self.folder))).replace('__BRIDGE__','http://local.fixture')
        code='const SCRIPT='+json.dumps(script)+';\n'+harness
        completed=subprocess.run([node,'-e',code],capture_output=True,text=True,check=True,timeout=10)
        payload=json.loads(completed.stdout)
        self.assertEqual(payload['initial']['choices'], {})
        self.assertEqual(payload['picked']['choices'], {'0':'web:fixture'})
        self.assertEqual(payload['removed']['choices'], {'0':''})
        result=apply_source_request(payload['picked'])
        self.assertEqual(result['selected_sources'][0]['media_id'],'web:fixture')
        self.assertEqual(result['selected_sources'][0]['source']['page_url'],self.option['page_url'])

    def test_stale_report_uses_shared_error_presentation_and_no_raw_link(self):
        from hinglish_visuals.report import write_report
        write_report(self.folder / 'report.html', self.project)
        self.asset.write_bytes(b'changed bytes')
        write_report(self.folder / 'report.html', self.project)
        page=(self.folder/'report.html').read_text('utf-8')
        self.assertIn('Source assets unavailable',page)
        self.assertIn('Technical details',page)
        self.assertNotIn('href="source-banks/',page)
        self.assertNotIn('Traceback (most recent call last)',page)

if __name__ == '__main__':
    unittest.main()
