"""Reconnect the same saved YouTube channel without exposing app secrets."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import Mock,patch
from hinglish_publish.providers import connect_youtube,SCOPES

class ReconnectTests(TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'tmp');self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.saved={'channel_id':'cricket-one','name':'Fantasy Legends','credentials':{'client_id':'fixture.apps.googleusercontent.com','client_secret':'fixture-only','token_uri':'https://oauth2.googleapis.com/token','scopes':SCOPES}}
        self.credentials=Mock();self.credentials.to_json.return_value=json.dumps({'fixture':True})
        self.flow=Mock();self.flow.run_local_server.return_value=self.credentials
        self.client=Mock();self.client.channels.return_value.list.return_value.execute.return_value={'items':[{'id':'cricket-one','snippet':{'title':'Fantasy Legends'}}]}
    def run_with(self,path='',channel='cricket-one'):
        self.client.channels.return_value.list.return_value.execute.return_value={'items':[{'id':channel,'snippet':{'title':'Fantasy Legends'}}]}
        with patch('hinglish_publish.providers.secrets.load',return_value=self.saved),patch('hinglish_publish.providers.secrets.save') as save,patch('google_auth_oauthlib.flow.InstalledAppFlow.from_client_config',return_value=self.flow) as config,patch('google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file',return_value=self.flow),patch('googleapiclient.discovery.build',return_value=self.client):
            result=connect_youtube(self.root,path,'cricket');return result,save,config
    def test_reconnect_reuses_saved_app_configuration_without_a_json_file(self):
        result,save,config=self.run_with();self.assertEqual(result['channel_id'],'cricket-one');self.assertTrue(config.called);self.assertEqual(config.call_args.args[0]['installed']['client_id'],self.saved['credentials']['client_id']);self.assertEqual(config.call_args.args[1],SCOPES);save.assert_called_once();self.assertEqual(save.call_args.args[1],'youtube-cricket')
    def test_wrong_channel_does_not_overwrite_existing_binding(self):
        path=self.root/'client.json';path.write_text('{}')
        with patch('hinglish_publish.providers.secrets.load',return_value=self.saved),patch('hinglish_publish.providers.secrets.save') as save,patch('google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file',return_value=self.flow),patch('googleapiclient.discovery.build',return_value=self.client):
            self.client.channels.return_value.list.return_value.execute.return_value={'items':[{'id':'gaming-other','snippet':{'title':'Other Channel'}}]}
            with self.assertRaisesRegex(ValueError,'same|different|Fantasy'):connect_youtube(self.root,str(path),'cricket')
            save.assert_not_called()
    def test_no_saved_app_config_requires_the_original_json_not_a_made_up_key(self):
        with patch('hinglish_publish.providers.secrets.load',side_effect=FileNotFoundError),patch('hinglish_publish.providers.secrets.save') as save:
            with self.assertRaisesRegex(ValueError,'JSON|json'):connect_youtube(self.root,'','cricket')
            save.assert_not_called()

    def test_reconnect_requests_fresh_same_scope_refresh_not_just_a_short_lived_login(self):
        self.run_with();self.assertEqual(self.flow.run_local_server.call_args.kwargs['prompt'],'select_account consent');self.assertEqual(self.flow.run_local_server.call_args.kwargs['access_type'],'offline')
    def test_missing_renewable_token_keeps_existing_connection(self):
        self.credentials.refresh_token=None
        with patch('hinglish_publish.providers.secrets.load',return_value=self.saved),patch('hinglish_publish.providers.secrets.save') as save,patch('google_auth_oauthlib.flow.InstalledAppFlow.from_client_config',return_value=self.flow),patch('googleapiclient.discovery.build',return_value=self.client):
            with self.assertRaisesRegex(ValueError,'renewable'):connect_youtube(self.root,'','cricket')
            save.assert_not_called()

    def test_button_receives_google_url_without_os_browser_launch_or_url_logging(self):
        url='https://accounts.google.com/o/oauth2/auth?state=fixture'
        self.flow.authorization_url.return_value=(url,'fixture')
        self.flow.run_local_server.side_effect=lambda **kw:(self.flow.authorization_url(),self.credentials)[1]
        urls=[]
        with patch('hinglish_publish.providers.secrets.load',return_value=self.saved),patch('hinglish_publish.providers.secrets.save'),patch('google_auth_oauthlib.flow.InstalledAppFlow.from_client_config',return_value=self.flow),patch('googleapiclient.discovery.build',return_value=self.client):
            connect_youtube(self.root,'','cricket',on_authorization=urls.append)
        self.assertEqual(urls,[url]);self.assertFalse(self.flow.run_local_server.call_args.kwargs['open_browser'])
        self.assertIsNone(self.flow.run_local_server.call_args.kwargs['authorization_prompt_message'])
