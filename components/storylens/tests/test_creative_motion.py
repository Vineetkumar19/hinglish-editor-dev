import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from hinglish_motion.creative import plan_creative, planning_guidance, TEMPLATES
from hinglish_motion.creative_export import build
from hinglish_motion.settings import MotionSettings
from hinglish_motion.curves import ease


class CreativeMotionTests(unittest.TestCase):
    def test_model_cannot_invent_claims_or_drop_source_lines(self):
        line = SimpleNamespace(id=1, start=0, text='Storylens keeps your words and your style')
        result = {'line':1,'template':'motion_title','title':{'start':0,'count':1},'label':{'start':1,'count':6},'value':{'start':0,'count':0},'items':[]}
        brain = SimpleNamespace(json=lambda *a, **kw: {'scenes':[result]})
        settings = MotionSettings(style='theme:gsap')
        self.assertEqual(plan_creative(brain,[line],settings,lambda _:None)[0].data['title'],'Storylens')
        result['title'] = {'start':100,'count':1}
        with self.assertRaisesRegex(ValueError,'outside the script'):
            plan_creative(brain,[line],settings,lambda _:None)
        brain.json = lambda *a, **kw: {'scenes':[]}
        with self.assertRaisesRegex(ValueError,'every script line'):
            plan_creative(brain,[line],settings,lambda _:None)

    def test_old_themes_do_not_start_selecting_new_templates(self):
        from hinglish_motion.plan import active_templates
        self.assertFalse(set(active_templates()) & set(TEMPLATES))

    def test_style_switch_keeps_edited_words_and_assets(self):
        from hinglish_motion.creative import apply_style
        scene={'template':'motion_title','data':{'title':'My edited title','label':'Keep this too'},'assets':[{'file':'owner.png'}]}
        apply_style(scene,'theme:orbit')
        self.assertEqual(scene['template'],'orbital_title')
        self.assertEqual(scene['data'],{'title':'My edited title','label':'Keep this too'})
        self.assertEqual(scene['assets'],[{'file':'owner.png'}])

    def test_key_moments_respect_requested_count(self):
        lines = [SimpleNamespace(id=i,start=i*4,end=(i+1)*4,text='Keep the story clear') for i in range(6)]
        pick={'line':3,'template':'motion_title','title':{'start':0,'count':4},'label':{'start':0,'count':0},'items':[]}
        brain = SimpleNamespace(json=lambda *a, **kw: {'scenes':[pick]})
        result = plan_creative(brain, lines, MotionSettings(style='theme:gsap',count='1'), lambda _:None, full=False)
        self.assertEqual([s.line for s in result],[3])

    def test_quality_keeps_photo_requirement_for_original_templates(self):
        from hinglish_eval.specs import motion_checks
        with tempfile.TemporaryDirectory() as folder:
            scene={'index':1,'line':0,'start':0,'duration':3,'template':'motion_title','mode':'full','data':{'title':'Your story'},'assets':[]}
            project={'scenes':[scene],'lines':[{'id':0,'text':'Your story'}],'style':'theme:gsap'}
            checks=motion_checks(folder,project)
            self.assertNotIn('motion.pictures',[c.rule for c in checks])
            self.assertFalse(next(c for c in checks if c.rule=='motion.files').passed)
            scene['template']='cutout_hero';project['style']='theme:archive'
            checks=motion_checks(folder,project)
            self.assertFalse(next(c for c in checks if c.rule=='motion.pictures').passed)

    def test_guidance_has_sources_and_stays_bounded(self):
        guidance = planning_guidance('visuals','show this real person at the spoken word')
        self.assertLess(len(json.dumps(guidance)),5000)
        self.assertTrue(all(row['source'].startswith('https://github.com/') for row in guidance['recipes']))

    def test_export_preserves_words_and_copies_offline_runtime(self):
        with tempfile.TemporaryDirectory() as folder:
            scene={'template':'motion_title','duration':4,'mode':'full','data':{'title':'</script> & words'}}
            output=build(scene,Path(folder)/'preview.mp4',360,640,30)
            text=(output/'index.html').read_text('utf-8')
            self.assertNotIn('"title": "</script>',text)
            self.assertIn('data-width="360"',text)
            self.assertIn('id="composition" data-composition-id="main"',text)
            self.assertIn('<main id="stage"></main></div>',text)
            self.assertTrue((output/'vendor/gsap.min.js').is_file())
            self.assertEqual(json.loads((output/'scene.json').read_text('utf-8'))['data']['title'],'</script> & words')

    def test_gsap_easing_has_correct_endpoints_and_is_monotonic(self):
        for name in ('power3.out','power2.in','sine.inOut'):
            values=[ease(name,i/1000) for i in range(1001)]
            self.assertEqual(values[0],0)
            self.assertEqual(values[-1],1)
            self.assertEqual(values,sorted(values))


if __name__ == '__main__': unittest.main()
