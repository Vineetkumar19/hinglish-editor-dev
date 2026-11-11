import unittest
from hinglish_app.template_text_editor import select_headings

class FinalEditorTests(unittest.TestCase):
    def slot(self):
        return {'id':'s','template_layer_id':'t','text_id':'1','policy':'choose','existing_date':False,
                'font_size':60,'bounds':{'width':600},'runs':[{'start':0,'end':4}],'max_words':4,
                'words':[{'text':t,'script_index':i} for i,t in enumerate('Rohit Sharma batting'.split())]}
    def test_local_editor_only_selects_validated_vocabulary_from_that_scene(self):
        calls=[]
        def ask(system,data,schema,tokens):
            calls.append(data)
            if 'narration' in data:return {'phrases':['Rohit Sharma','Virat Kohli']}
            self.assertEqual(data['scenes'][0]['choices'],{'0':'Rohit Sharma'})
            return {'choices':{'0':0}}
        slot=self.slot();action={'id':'s','template_layer_id':'t','text_id':'1','action':'hide','role':'body','text':'','word_indices':[]}
        result=select_headings([slot],[action],ask,lambda *a:None,lambda *a:None)
        self.assertEqual(result[0]['text'],'Rohit Sharma');self.assertEqual(len(calls),2)
    def test_incomplete_model_response_never_becomes_an_applied_hide_only_pass(self):
        def ask(system,data,schema,tokens):
            return {'phrases':['Rohit Sharma']} if 'narration' in data else {'choices':{}}
        with self.assertRaises(ValueError):select_headings([self.slot()],[],ask,lambda *a:None,lambda *a:None)
    def test_density_preference_never_forces_an_uncertain_heading(self):
        def ask(system,data,schema,tokens):
            return {'phrases':['Rohit Sharma']} if 'narration' in data else {'choices':{'0':-1}}
        slot=self.slot();action={'id':'s','template_layer_id':'t','text_id':'1','action':'hide','role':'body','text':'','word_indices':[]}
        result=select_headings([slot],[action],ask,lambda *a:None,lambda *a:None)
        self.assertEqual(result[0]['action'],'hide')

    def test_three_scene_group_allows_one_heading_or_additional_supported_headings(self):
        for choices in ({'0':0,'1':-1,'2':-1},{'0':0,'1':-1,'2':0}):
            slots=[];actions=[]
            for i in range(3):
                slot=self.slot();slot.update(id=str(i),text_id=str(i),runs=[{'start':i*5,'end':i*5+4}])
                slot['words']=[{**w,'script_index':i*3+w['script_index']} for w in slot['words']]
                slots.append(slot);actions.append({'id':str(i),'action':'hide','role':'body','text':'','word_indices':[]})
            def ask(system,data,schema,tokens):
                if 'narration' in data:return {'phrases':['Rohit Sharma']}
                self.assertEqual(len(data['scenes']),3)
                return {'choices':choices}
            result=select_headings(slots,actions,ask,lambda *a:None,lambda *a:None)
            self.assertEqual([a['id'] for a in result if a['action']=='replace'],[k for k,v in choices.items() if v==0])

if __name__=='__main__':unittest.main()

