import copy,json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from hinglish_sound.scenes import SCHEMA,read_scene_response


class Session:
    def __init__(self,answers):self.answers=iter(answers);self.calls=[]
    def post(self,url,json,timeout):
        self.calls.append(copy.deepcopy(json));data=next(self.answers)
        return SimpleNamespace(raise_for_status=lambda:None,json=lambda:data)


class SceneResponseTests(unittest.TestCase):
    def good(self):return dict(setting='Road and motorcycle',mood='confident',action='Riding',ambience='',confidence=.9)
    def test_truncated_answer_retries_without_fabricating_a_scene(self):
        good=self.good();session=Session([dict(message={'content':'{"setting":"cut'},done_reason='length'),dict(message={'content':json.dumps(good)},done_reason='stop')])
        judge=SimpleNamespace(model='local-vision',url='http://local',session=session)
        with tempfile.TemporaryDirectory() as temp:
            answer=read_scene_response(judge,{'format':SCHEMA,'options':{'num_predict':1100},'messages':[]},Path(temp),'scene-2',lambda _:None)
            self.assertEqual(answer,good)
            self.assertEqual(len(list(Path(temp).glob('scene-2-response-*.json'))),2)
        self.assertEqual(len(session.calls),2)
        self.assertFalse(session.calls[0]['think'])
        self.assertGreater(session.calls[1]['options']['num_predict'],session.calls[0]['options']['num_predict'])

    def test_missing_fields_are_not_accepted_as_an_empty_success(self):
        session=Session([dict(message={'content':'{}'})]*2)
        judge=SimpleNamespace(model='local-vision',url='http://local',session=session)
        with tempfile.TemporaryDirectory() as temp,self.assertRaisesRegex(ValueError,'complete scene'):
            read_scene_response(judge,{'format':SCHEMA,'options':{},'messages':[]},Path(temp),'scene',lambda _:None)


if __name__=='__main__':unittest.main()
