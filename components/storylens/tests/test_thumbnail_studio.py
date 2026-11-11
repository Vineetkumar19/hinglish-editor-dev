import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch

from PIL import Image

from hinglish_app.assistant_plan import TOOLS, schema, validate_plan, job_payload, quick_plan
from hinglish_niche.image_design import settings, CATEGORIES
from hinglish_niche.thumbnail import run


class ThumbnailStudioTests(unittest.TestCase):
    def test_target_team_recipe_wins_over_an_inspiration_team_mention(self):
        from hinglish_niche.thumbnail_layout import style_for
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name,words in [('kkr',['kkr','under']),('mi',['mumbai','under rated'])]:
                folder=root/'library/thumbnail-styles'/name;folder.mkdir(parents=True)
                (folder/'style.json').write_text(json.dumps({'id':name,'match_all':words}))
            self.assertEqual(style_for(root,'Mumbai Indians UNDER RATED in the KKR look')['id'],'mi')

    def test_saved_owner_references_are_available_to_future_thumbnail_plans(self):
        from hinglish_niche.thumbnail_memory import context
        root=Path(__file__).resolve().parents[1]
        guide=context(root)
        self.assertEqual(len(guide['reference_files']),3)
        self.assertTrue(all(Path(p).is_file() for p in guide['reference_files']))
        self.assertTrue((root/guide['approved_base']).is_file())
        from hinglish_cut.creative_memory import context as retrieved
        memory=retrieved(root,'Make a cricket thumbnail for Mumbai versus Chennai')
        self.assertIn('owner-cricket-thumbnail-reference',[entry['id'] for entry in memory['entries']])

    def test_real_photo_match_never_invokes_diffusion_or_changes_jersey_pixels(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);pack=root/'library/thumbnail-styles/match';pack.mkdir(parents=True)
            photos={}
            for key in ('left','right','background'):
                Image.new('RGBA',(100,100),(12,45,78,255)).save(pack/(key+'.png'))
                photos[key]={'name':key,'path':key+'.png','page':'https://example.org/'+key}
            (pack/'style.json').write_text(json.dumps({'id':'match','match_all':['mumbai','chennai'],'photography':photos}))
            def render(root,folder,config,hook,subtitle,photos,index):
                self.assertEqual(hook,'MUMBAI vs CHENNAI')
                self.assertEqual(photos['left']['name'],'left')
                p=folder/f'thumbnail-{index+1}.png';Image.open(photos['left']['path']).convert('RGB').save(p);Image.open(p).save(p.with_suffix('.jpg'));return p
            with patch('hinglish_niche.photo_thumbnail.render',side_effect=render),patch('hinglish_aigen.engine.generate') as diffusion,patch('hinglish_visuals.brain.open_brain') as brain:
                page=run(root,'Mumbai versus Chennai',generate=False,design={'count':1,'text_mode':'exact','title':'MUMBAI vs CHENNAI'})
            diffusion.assert_not_called();brain.assert_not_called()
            project=json.loads((page.parent/'thumbnail-project.json').read_text('utf-8'))
            self.assertFalse(project['ai_backgrounds']);self.assertFalse(project['local_model_lettering'])
            self.assertEqual(project['sources']['right']['page'],'https://example.org/right')

    def test_only_exact_text_source_backed_jobs_bypass_the_gpu_queue(self):
        from hinglish_niche.photo_thumbnail import cpu_only
        payload={'mode':'thumbnail','thumbnail_design':{'category':'youtube','text_mode':'exact'}}
        with patch('hinglish_niche.thumbnail_layout.style_for',return_value={'photography':{'left':{}}}):
            self.assertTrue(cpu_only('.',payload,'Mumbai versus Chennai'))
            self.assertFalse(cpu_only('.',{**payload,'portrait':'user.png'},'Mumbai versus Chennai'))
            self.assertFalse(cpu_only('.',{**payload,'thumbnail_design':{'text_mode':'auto'}},'Mumbai versus Chennai'))
        with patch('hinglish_niche.thumbnail_layout.style_for',return_value={}):self.assertFalse(cpu_only('.',payload,'Another image'))

    def test_truncated_local_plan_retries_once_before_any_generation(self):
        from hinglish_niche.thumbnail import _plan
        brain=Mock();brain.json.side_effect=[json.JSONDecodeError('cut short','{',1),{'concepts':[]}]
        result=_plan(brain,'Plan image',{'creator_profile':{'keep':'all'}},{},progress=lambda _:None,count=1)
        self.assertEqual(result,{'concepts':[]})
        self.assertEqual(brain.json.call_count,2)
        self.assertEqual(brain.json.call_args.args[1]['creator_profile'],{'keep':'all'})
        self.assertFalse(brain.json.call_args.kwargs['think'])
    def test_creating_a_social_post_never_shortcuts_to_publishing(self):
        for prompt in ('Create an Instagram post about cricket','Make a normal post image','Design a cricket poster'):
            with self.subTest(prompt=prompt):self.assertIsNone(quick_plan(prompt))
    def test_chat_has_one_image_tool_and_migrates_legacy_tool_without_deleting_history(self):
        self.assertNotIn('aiimage', TOOLS)
        self.assertEqual(TOOLS['thumbnail'], 'Thumbnail')
        self.assertNotIn('aiimage', schema()['properties']['steps']['items']['properties']['tool']['enum'])
        plan=validate_plan({'reply':'Create image','question':'','steps':[{'tool':'aiimage','options':{'script':'A red ball'}}]})
        self.assertEqual(plan['steps'][0]['tool'],'thumbnail')
        payload=job_payload(plan['steps'][0],[])
        self.assertEqual(payload['thumbnail_design']['category'],'general')
        self.assertEqual(payload['thumbnail_design']['text_mode'],'none')

    def test_requested_category_text_count_and_size_reach_the_image_job(self):
        step={'tool':'thumbnail','options':{'script':'Cricket night','count':2,'image_category':'poster',
            'image_aspect':'4:5','image_text_mode':'exact','image_title':'LAST OVER','image_subtitle':'Club cricket',
            'ai_style':'illustration','image_seed':21}}
        payload=job_payload(step,['unrelated-video.mp4'])
        design=payload['thumbnail_design']
        self.assertEqual((design['width'],design['height'],design['count']),(1080,1350,2))
        self.assertEqual((design['title'],design['subtitle'],design['style']),('LAST OVER','Club cricket','illustration'))
        self.assertEqual(payload['source_paths'],[])

    def test_invalid_settings_fail_before_generating_images(self):
        for values in ({'count':0},{'count':5},{'count':True},{'category':'unknown'},
                       {'aspect':'giant'},{'text_mode':'exact'},{'seed':-1},{'accent':'red'}):
            with self.subTest(values=values), self.assertRaises(ValueError):settings(values)

    def test_all_categories_make_correctly_sized_png_jpeg_and_zip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);background=root/'reference.jpg';Image.new('RGB',(500,400),'#346178').save(background)
            for category in CATEGORIES:
                with self.subTest(category=category):
                    brain=Mock();brain.json.return_value={'concepts':[{'hook':'Suggested words','background_prompt':'A cricket stadium'}]}
                    config={'category':category,'count':1,'text_mode':'none' if category=='general' else 'exact',
                        'title':'Last over: 2026','subtitle':'Local club cricket'}
                    with patch('hinglish_visuals.brain.open_brain',return_value=brain):
                        page=run(root,'A club cricket design',background=background,generate=False,design=config)
                    project=json.loads((page.parent/'thumbnail-project.json').read_text('utf-8'))
                    expected=settings(config)
                    with Image.open(page.parent/'thumbnail-1.png') as image:self.assertEqual(image.size,(expected['width'],expected['height']))
                    self.assertTrue((page.parent/'thumbnail-1.jpg').is_file())
                    with zipfile.ZipFile(page.parent/'all-images.zip') as bundle:self.assertIn('thumbnail-1.png',bundle.namelist())
                    self.assertEqual(project['concepts'][0]['hook'],'' if category=='general' else 'Last over: 2026')
                    self.assertTrue(brain.json.call_args.args[1]['design'])
                    self.assertIn('creator_profile',brain.json.call_args.args[1])

    def test_general_no_text_preserves_the_photographic_canvas(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);photo=root/'photo.png';Image.new('RGB',(1080,1080),'#336699').save(photo)
            brain=Mock();brain.json.return_value={'concepts':[{'hook':'Must not appear','background_prompt':'Blue image'}]}
            with patch('hinglish_visuals.brain.open_brain',return_value=brain):
                page=run(root,'No words',background=photo,generate=False,design={'category':'general','count':1,'text_mode':'none'})
            with Image.open(page.parent/'thumbnail-1.png') as image:self.assertEqual(image.getpixel((600,900)),(51,102,153))

    def test_model_lettering_is_requested_from_the_local_generator_without_a_text_overlay(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);brain=Mock();brain.json.return_value={'concepts':[{'hook':'MI vs CSK','background_prompt':'Blue and yellow match-poster scene'}]}
            requests=[]
            def generate(root,items,jobs,progress):
                requests.extend(items)
                for item in items:Image.new('RGB',(item['width'],item['height']),'#336699').save(item['out'])
                return {'0':{'out':items[0]['out'],'seconds':1}}
            with patch('hinglish_visuals.brain.open_brain',return_value=brain),patch('hinglish_aigen.engine.doctor',return_value={'ready':True}),patch('hinglish_aigen.engine.generate',side_effect=generate):
                page=run(root,'Mumbai versus Chennai livestream',design={'count':1,'title':'MI vs CSK','subtitle':'LIVE STREAM','text_mode':'exact','text_renderer':'model'})
            self.assertIn('Exact large headline: "MI vs CSK"',requests[0]['prompt'])
            self.assertIn('LIVE STREAM',requests[0]['prompt'])
            with Image.open(page.parent/'thumbnail-1.png') as image:self.assertEqual(image.getextrema(),((51,51),(102,102),(153,153)))


if __name__=='__main__':unittest.main()
