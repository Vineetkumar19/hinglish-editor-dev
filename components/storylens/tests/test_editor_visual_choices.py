import tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from PIL import Image
from hinglish_visuals.references import collect
from hinglish_visuals.web import Entity,Media
from hinglish_visuals.evaluator import Verdict

class EditorVisualChoicesTests(unittest.TestCase):
 def test_two_and_five_choices_finish_without_false_shortfall(self):
  for count in (2,5):
   with self.subTest(count=count),tempfile.TemporaryDirectory() as temp:
    root=Path(temp);folder=root/'output';folder.mkdir();candidates=[]
    for i in range(7):
     path=root/f'{i}.png';Image.new('RGB',(320,400),(i*30,80,150)).save(path)
     candidates.append(Media('image','web',str(i),'Kohli RCB photo','https://example.com/'+str(i),path=str(path)))
    entry={'index':0,'start':0.,'end':2.,'text':'Kohli plays for RCB','quote':'Kohli','meaning':'Kohli in RCB kit',
      'visual':'Virat Kohli RCB','queries':['Virat Kohli RCB'],'priority':3,'entity':'kohli','label':'Virat Kohli',
      'show':'photo','display':'popup','category':'cricket player','reference_type':'identity','evidence_terms':[],
      'chosen':None,'clip':None,'evaluation':None,'rejected':[],'options':[],'alternatives':[]}
    project={'slots':[entry],'summary':{'topic':'IPL'},'entities':{'kohli':Entity('kohli','Virat Kohli','person').to_dict()}}
    evaluator=SimpleNamespace(vlm=True,image=lambda path,info:Verdict(True,1.,seen='RCB player'))
    with patch('hinglish_visuals.references.gather',return_value=candidates),patch('hinglish_visuals.references.judge',side_effect=lambda b,m,e,c,**kw:c),patch('hinglish_visuals.pipeline.write_outputs'),patch('hinglish_visuals.report.write_report'):
     collect(root,[(SimpleNamespace(orientation='portrait',width=720,height=1280),folder,project)],None,SimpleNamespace(session=None),None,
             SimpleNamespace(vision_check_model='local',options_per_moment=count),lambda _:None,evaluator)
    self.assertEqual(len(entry['options']),count);self.assertEqual(entry['shortfall'],0)
    self.assertEqual(project['options_per_moment'],count);self.assertIsNone(entry['chosen'])
    self.assertTrue(all((folder/o['asset']).is_file() for o in entry['options']))
