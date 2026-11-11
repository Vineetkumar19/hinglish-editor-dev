import copy
from pathlib import Path
import unittest
from unittest.mock import Mock,patch

from hinglish_app.assistant_image_plan import requested,plan


class LocalPhotoStudioTests(unittest.TestCase):
    def test_image_router_bounds_schema_and_keeps_full_request_and_profile(self):
        from hinglish_niche.profiles import use,CURRENT
        text='Generate a new thumbnail for Chennai Super Kings from the attached style reference. Do not publish anything.'
        brain=Mock();brain.root=Path.cwd()
        seen=[]
        def answer(system,data,schema,**options):
            seen.append((data,schema,copy.deepcopy(CURRENT.get())))
            return {'reply':'Starting.','question':'','combine':False,'steps':[{'tool':'thumbnail','options':{'script':'a shortened creative prompt','image_workflow':'photo','image_reference_role':'style'}}]}
        brain.json.side_effect=answer
        profile={'profile':'gaming','feedback':'Keep the complete saved creator guidance.'}
        with use(profile):result=plan(brain,text,[],[{'name':'thumbnail.png','kind':'.png'}],{})
        self.assertEqual(seen[0][0]['request'],text)
        self.assertEqual(seen[0][2],profile)
        spec=seen[0][1]['properties']['steps']['items']['properties']
        self.assertEqual(spec['tool']['enum'],['thumbnail'])
        self.assertNotIn('instagram_action',spec['options']['properties'])
        self.assertEqual(result['steps'][0]['options']['script'],text)
        self.assertEqual(result['steps'][0]['options']['image_reference_role'],'style')
        self.assertEqual(result['steps'][0]['options']['count'],1)
        self.assertFalse(result['combine'])

    def test_router_does_not_take_publishing_or_video_work(self):
        self.assertTrue(requested('Make a thumbnail. Do not publish anything.'))
        self.assertFalse(requested('Make a thumbnail then upload the video.'))
        self.assertFalse(requested('Extract shorts and make a thumbnail.'))

    def test_reference_and_photo_workflow_survive_job_payload(self):
        from hinglish_app.assistant_plan import job_payload
        result=job_payload({'tool':'thumbnail','options':{'script':'Keep exact brief','image_workflow':'photo'}},[],root=Path.cwd())
        self.assertEqual(result['thumbnail_design']['workflow'],'photo')
        self.assertEqual(result['script'],'Keep exact brief')

    def test_model_layout_rejects_paths_code_and_clipped_headline(self):
        from hinglish_niche.local_photo_studio import layout_error
        cfg={'text_mode':'exact','title':'EXACT WORDS','width':1280,'height':720}
        layer=dict(id='subject',layer='subject',kind='person',fit='contain',name='Model choice',query='Model query',cutout=True,x=100,y=100,w=600,h=500,rotation=0,opacity=1,glow='#ffffff',glow_size=5)
        value=dict(headline='other',reason='Model choice',background_prompt='',background_color='#000000',accent='#ffffff',assets=[layer],title=dict(x=20,y=550,w=1240,h=150,band='none',band_color='#000000',text_color='#ffffff',font='impact'))
        self.assertEqual(layout_error(value,cfg),'');self.assertEqual(value['headline'],'EXACT WORDS')
        value['assets'][0]['id']='../source';self.assertTrue(layout_error(value,cfg))
        value['assets'][0]['id']='subject';value['title']['w']=1280;self.assertIn('headline',layout_error(value,cfg))

    def test_observed_unsupported_year_and_occluding_layers_are_returned_as_feedback(self):
        from hinglish_niche.local_photo_studio import layout_error
        cfg={'text_mode':'auto','width':1280,'height':720}
        person=dict(id='person',layer='subject',kind='person',fit='contain',name='Model choice',query='Model choice team 2026 portrait',cutout=True,x=100,y=0,w=500,h=600,rotation=0,opacity=1,glow='#ffffff',glow_size=4)
        place={**person,'id':'place','kind':'place','query':'A real stadium','name':'Stadium','cutout':False}
        logo={**person,'id':'logo','kind':'brand','query':'Authentic team crest','name':'Team crest','cutout':False}
        value=dict(headline='Chosen headline',reason='Model choice',background_prompt='Team logo watermark in smoke',background_color='#000000',accent='#ffffff',assets=[person,place,logo],title=dict(x=20,y=550,w=1240,h=150,band='none',band_color='#000000',text_color='#ffffff',font='impact'))
        before=copy.deepcopy(value)
        error=layout_error(value,cfg,'Make a team thumbnail.')
        for text in ('2026','layer=background','cutout=true','background_prompt'):self.assertIn(text,error)
        self.assertEqual(value,before) # feedback, never hand-author the correction

    def test_layout_tool_cannot_invent_a_headline_photo_or_change_source_identity(self):
        import jsonschema
        from hinglish_niche.local_photo_studio import layout_schema_for_sources
        schema=layout_schema_for_sources([{'id':'verified_photo'}])['properties']['assets']['items']
        asset=dict(id='verified_photo',layer='subject',fit='contain',x=100,y=20,w=500,h=600,rotation=0,opacity=1,glow='#ffffff',glow_size=5)
        jsonschema.validate(asset,schema)
        asset['id']='headline'
        with self.assertRaises(jsonschema.ValidationError):jsonschema.validate(asset,schema)
        asset['id']='verified_photo';asset['query']='Replace with another person'
        with self.assertRaises(jsonschema.ValidationError):jsonschema.validate(asset,schema)

    def test_current_team_scope_excludes_negated_reference_team(self):
        from hinglish_niche.local_photo_studio import requested_teams,source_scope_errors
        text='Generate a thumbnail for Chennai Super Kings. The reference is not a source of Mumbai Indians faces for the CSK image.'
        teams=requested_teams(Path.cwd(),text)
        self.assertEqual(teams,['Chennai Super Kings'])
        invalid=[{'kind':'person','name':'Model choice','query':'A cached official portrait'},
                 {'kind':'brand','name':'Mumbai Indians logo','query':'A cached team crest'}]
        self.assertEqual(len(source_scope_errors(Path.cwd(),invalid,teams)),2)
        self.assertFalse(source_scope_errors(Path.cwd(),[{'kind':'person','name':'Model choice','query':'Model choice Chennai Super Kings kit portrait'}],teams))

    def test_reference_measurements_must_use_actual_canvas(self):
        from hinglish_niche.local_photo_studio import validate_reference
        value={k:'Model observation' for k in ('composition','typography','palette','lighting_effects','reuse_limits')}
        value['regions']=[dict(role='person',x=1120,y=120,w=320,h=480)]
        with self.assertRaisesRegex(ValueError,'actual 1280x720'):validate_reference(value,1280,720)


if __name__=='__main__':unittest.main()
