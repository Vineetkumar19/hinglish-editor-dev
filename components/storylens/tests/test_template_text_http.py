"""Real authenticated HTTP round trips; worker/native receipt are explicit fixtures."""
import json
from pathlib import Path
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request,urlopen
from hinglish_app.server import serve
from hinglish_app.template_text import service,save
from test_template_text import snapshot
from test_template_text_service import workspace_temp,Process

class TemplateTextHTTPTests(unittest.TestCase):
    def setUp(self):
        self.tmp=workspace_temp();self.root=Path(self.tmp.__enter__());self.server,self.state=serve(self.root,0);self.server.RequestHandlerClass.log_message=lambda *args:None;self.url='http://127.0.0.1:'+str(self.state.port);self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
    def tearDown(self):self.server.shutdown();self.server.server_close();self.thread.join(2);self.tmp.__exit__(None,None,None)
    def request(self,path,value=None,authorized=True):
        headers={'Content-Type':'application/json'}
        if authorized:headers['X-Hinglish-Token']=self.state.token
        with urlopen(Request(self.url+path,data=json.dumps(value).encode() if value is not None else None,headers=headers),timeout=10) as response:return json.load(response)
    def test_routes_require_the_local_panel_token(self):
        for path,value in [('/api/panel/template-text-start',{}),('/api/panel/template-text-stop',{}),('/api/panel/template-text-job?id='+('a'*24),None),('/api/panel/template-text-plan?id='+('a'*24),None)]:
            with self.subTest(path=path),self.assertRaises(HTTPError) as error:self.request(path,value,False)
            self.assertEqual(error.exception.code,403)
    def test_scan_to_plan_to_native_confirmation_protocol(self):
        with patch('hinglish_app.template_text.subprocess.Popen',Process):job=self.request('/api/panel/template-text-start',{'script':'Mumbai wins in 2020','snapshot':snapshot()})
        jobs=service(self.root);folder=jobs.folder(job['id']);plan={'job_id':job['id'],'project_id':'owner.aep','composition_id':'42','fingerprint':'native-1','actions':[{'id':'9/20:1','action':'replace','text':'Mumbai wins'}]};save(folder/'plan.json',plan);save(folder/'status.json',{**job,'status':'ready'})
        self.assertEqual(self.request('/api/panel/template-text-plan?id='+job['id']),plan)
        result=self.request('/api/panel/template-text-receipt',{'id':job['id'],'receipt':{'ok':True,'job_id':job['id'],'project_id':'owner.aep','composition_id':'42','changed':1,'hidden':0}})
        self.assertEqual(result['status'],'applied');self.assertTrue((folder/'native-receipt.json').exists())
    def test_invalid_input_uses_shared_plain_error_not_traceback(self):
        with self.assertRaises(HTTPError) as caught:self.request('/api/panel/template-text-start',{'script':'','snapshot':snapshot()})
        error=json.load(caught.exception);self.assertIn('script',error['error'].lower());self.assertNotIn('Traceback',error['error']);self.assertIn('error_details',error)
    def test_main_panel_serves_button_and_controller(self):
        with urlopen(self.url+'/editor-panel.html') as response:page=response.read().decode()
        self.assertIn('templateTextRun',page);self.assertIn('template-text.js',page);self.assertNotIn('__APP_TOKEN__',page)

    def test_realistic_multi_template_scan_over_one_megabyte_reaches_the_worker_contract(self):
        scan=snapshot();original=scan['templates'][0]['texts'][0]
        scan['templates'][0]['texts']=[{**original,'id':'slot-'+str(i),'text':'Template paragraph '*80} for i in range(1100)]
        payload={'script':'Mumbai wins in 2020','snapshot':scan}
        self.assertGreater(len(json.dumps(payload).encode()),1024**2)
        with patch('hinglish_app.template_text.subprocess.Popen',Process):result=self.request('/api/panel/template-text-start',payload)
        self.assertEqual(result['status'],'queued')

if __name__=='__main__':unittest.main()
