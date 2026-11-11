import json,tempfile,unittest
from pathlib import Path
from unittest.mock import Mock
from PIL import Image
from hinglish_niche.historical import select_player_asset,attach_context,anchor_player_scenes,mentioned_years
from hinglish_niche.profiles import use,Profiles
from hinglish_motion.assets import Asset,AssetFinder
from hinglish_motion.plan import plan_schema,Scene,scene_data
from hinglish_motion.pipeline import fallback
from hinglish_cut.model import Word
from hinglish_broll.phrases import Phrase

class HistoricalTests(unittest.TestCase):
    def setup_assets(self,root):
        base=Path(root)/'library/cricket-assets';base.mkdir(parents=True)
        Image.new('RGB',(32,32),'blue').save(base/'player.png')
        entry={'file':'player.png','player':'Rohit Sharma','aliases':['Hitman'],'year':2020,'team':'Mumbai Indians','match_id':'final-2020','evidence_url':'https://www.iplt20.com/','verified':True,'approved':True,'rights':'owned'}
        (base/'manifest.json').write_text(json.dumps({'assets':[entry]}))
        return base,entry

    def test_year_team_match_and_approval_all_must_match(self):
        with tempfile.TemporaryDirectory() as root:
            base,entry=self.setup_assets(root)
            self.assertIsNotNone(select_player_asset(root,'Rohit Sharma',2020,'Mumbai Indians','final-2020'))
            for args in [('Rohit Sharma',2021,'Mumbai Indians','final-2020'),('Rohit Sharma',2020,'Delhi Capitals','final-2020'),('Rohit Sharma',2020,'Mumbai Indians','another-match'),('Unmentioned Player',2020,'','')]:
                self.assertIsNone(select_player_asset(root,*args))
            for changes in [{'approved':False},{'verified':False},{'rights':'unknown'},{'file':'../../../outside.jpg'},{'match_id':''}]:
                (base/'manifest.json').write_text(json.dumps({'assets':[{**entry,**changes}]}))
                self.assertIsNone(select_player_asset(root,'Rohit Sharma',2020,'Mumbai Indians','final-2020'))

    def test_unknown_year_and_ambiguous_alias_are_not_guessed(self):
        with tempfile.TemporaryDirectory() as root:
            base,entry=self.setup_assets(root)
            with self.assertRaises(ValueError):select_player_asset(root,'Rohit Sharma',None)
            other={**entry,'player':'Another Player','aliases':['Hitman']}
            (base/'manifest.json').write_text(json.dumps({'assets':[entry,other]}))
            self.assertIsNone(select_player_asset(root,'Hitman',2020))

    def test_finder_blocks_missing_archival_record_before_any_web_search(self):
        with tempfile.TemporaryDirectory() as root,use({'profile':'cricket'}):
            finder=object.__new__(AssetFinder);finder.root=Path(root);finder._web_pictures=Mock()
            asset=Asset('person','Rohit Sharma 2020','Rohit Sharma',historical={'year':2020,'team':'Mumbai Indians','match_id':'final-2020'})
            finder.picture(asset,Path(root),'test',False)
            self.assertIn('needs review',asset.error);finder._web_pictures.assert_not_called()
            with self.assertRaises(ValueError):fallback({'assets_all':[asset.to_dict()],'assets':[],'data':{'word':'Rohit'},'template':'cutout_hero'})

    def test_verified_local_asset_is_selected_without_wikipedia_fallback(self):
        with tempfile.TemporaryDirectory() as root,use({'profile':'cricket'}):
            self.setup_assets(root);finder=object.__new__(AssetFinder);finder.root=Path(root)
            asset=Asset('person','Rohit Sharma 2020','Rohit Sharma',historical={'year':2020,'team':'Mumbai Indians','match_id':'final-2020'})
            result=finder.picture(asset,Path(root)/'job','test',False)
            self.assertEqual(result.source,'verified-cricket-library');self.assertTrue((Path(root)/'job'/result.file).is_file())

    def test_missing_historical_player_is_not_silently_dropped_from_a_populated_board(self):
        found=[{'file':'first.jpg'},{'file':'second.jpg'}]
        missing={'file':'','error':'Historical player image needs review: Rohit Sharma 2020'}
        with self.assertRaisesRegex(ValueError,'needs review'):
            fallback({'template':'archive_board','data':{'label':'MI'},
                      'assets':found+[missing],'assets_all':found+[missing]})

    def test_saved_historical_asset_stays_guarded_after_switching_to_general(self):
        with tempfile.TemporaryDirectory() as root,use({'profile':'general'}):
            finder=object.__new__(AssetFinder);finder.root=Path(root);finder._web_pictures=Mock()
            asset=Asset('person','Rohit Sharma','Rohit Sharma',historical={'year':2020})
            finder.picture(asset,Path(root),'test',False)
            self.assertIn('needs review',asset.error);finder._web_pictures.assert_not_called()

    def test_only_cricket_receives_archive_schema_and_context(self):
        general=plan_schema(2)['properties']['moments']['items']['properties']
        self.assertNotIn('archive_board',general['template']['enum'])
        self.assertNotIn('historical',general['assets']['items']['properties'])
        with use({'profile':'cricket'}):
            cricket=plan_schema(2)['properties']['moments']['items']['properties']
            self.assertIn('archive_board',cricket['template']['enum'])
            self.assertIn('historical',cricket['assets']['items']['properties'])
            scene=Scene(1,0,0,4,'2020 Rohit Sharma','cutout_hero','full',assets=[{'kind':'person','query':'Rohit Sharma 2025','name':'Rohit Sharma','historical':{'year':2025}}])
            attach_context([scene],[Phrase(0,0,4,'2020 Rohit Sharma')])
            self.assertIsNone(scene.assets[0]['historical']['year'])
        self.assertNotIn('historical',Asset('person','Thomas Edison','Thomas Edison').to_dict())

    def test_player_scene_anchors_on_aligned_name_without_changing_general(self):
        scene={'line':0,'start':0,'assets':[{'kind':'person','name':'Rohit Sharma'}]}
        words=[Word('then',0,1),Word('Rohit',1.2,1.5),Word('Sharma',1.5,1.9)]
        for w in words:w.aligned=True
        lines=[Phrase(0,0,3,'then Rohit Sharma')]
        anchor_player_scenes([scene],lines,words);self.assertEqual(scene['start'],0)
        with use({'profile':'cricket'}):anchor_player_scenes([scene],lines,words)
        self.assertEqual(scene['start'],1.2)

    def test_reference_memory_is_personal_and_not_in_general_or_gaming(self):
        with tempfile.TemporaryDirectory() as root:
            folder=Path(root)/'library/creator-profiles';folder.mkdir(parents=True)
            (folder/'cricket-documentary.json').write_text(json.dumps({'rules':['Photo parallax']}))
            self.assertIn('documentary_reference',Profiles(root).context('cricket'))
            self.assertNotIn('documentary_reference',Profiles(root).context('general'))
            self.assertNotIn('documentary_reference',Profiles(root).context('gaming'))

    def test_season_context_follows_the_chapter_not_a_year_elsewhere(self):
        lines=[Phrase(0,0,4,'2020 season'),Phrase(1,4,8,'Rohit Sharma'),Phrase(2,8,12,'do hazaar pachchis season'),Phrase(3,12,16,'Rohit Sharma')]
        scenes=[Scene(i,i,lines[i].start,4,lines[i].text,'cutout_hero', 'full',assets=[{'kind':'person','query':'Rohit Sharma','name':'Rohit Sharma','historical':{'year':2025}}]) for i in (1,3)]
        with use({'profile':'cricket'}):attach_context(scenes,lines)
        self.assertEqual([s.assets[0]['historical']['year'] for s in scenes],[2020,2025])
        self.assertEqual(mentioned_years('two thousand twenty-four versus २०२०'),{2024,2020})

    def test_comparison_does_not_guess_the_next_line_season(self):
        lines=[Phrase(0,0,4,'2020 versus 2025'),Phrase(1,4,8,'Rohit Sharma')]
        scene=Scene(1,1,4,4,'Rohit Sharma','cutout_hero','full',assets=[{'kind':'person','query':'Rohit Sharma','name':'Rohit Sharma'}])
        with use({'profile':'cricket'}):attach_context([scene],lines)
        self.assertIsNone(scene.assets[0]['historical']['year'])

    def test_multiple_players_get_separate_entry_times_in_a_full_scene(self):
        scene={'line':0,'start':0,'data':{},'assets':[{'kind':'person','name':'Rohit Sharma'},{'kind':'person','name':'Jasprit Bumrah'}]}
        words=[Word('Rohit',1,1.4),Word('Sharma',1.4,1.8),Word('Jasprit',4,4.4),Word('Bumrah',4.4,4.8)]
        for word in words:word.aligned=True
        with use({'profile':'cricket'}):anchor_player_scenes([scene],[Phrase(0,0,5,'Rohit Sharma and Jasprit Bumrah')],words,move_scene=False)
        self.assertEqual(scene['start'],0)
        self.assertEqual([entry['seconds'] for entry in scene['data']['player_entries']],[1,4])

class DocumentaryReportTests(unittest.TestCase):
    def test_explicit_timeline_motion_survives_palette_variation(self):
        from hinglish_motion.render import SceneRenderer
        with use({'profile':'cricket'}):
            schema=plan_schema(3)
        props=schema['properties']['moments']['items']['properties']
        self.assertIn('road-travel',props['archive_composition']['enum'])
        data=scene_data({'template':'archive_board','label':'A journey','archive_style':'map','archive_composition':'road-travel'})
        self.assertEqual(data['archive_composition'],'road-travel')
        with tempfile.TemporaryDirectory() as tmp:
            image=Path(tmp)/'photo.png';Image.new('RGB',(160,240),'blue').save(image)
            data.update(archive_variant=1,assets=[{'src':image.as_uri(),'enter_at':.05},{'src':image.as_uri(),'enter_at':2}])
            renderer=SceneRenderer(640,360)
            try:
                renderer.load({'template':'archive_board','mode':'full','duration':6,'speed':1,'data':data})
                self.assertEqual(renderer.page.locator('.archive-world').get_attribute('data-composition'),'road-travel')
            finally:renderer.close()

    def test_review_options_keep_general_separate_and_escape_historical_context(self):
        from hinglish_motion.report import write_report
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'report.html'
            project={'width':640,'height':360,'style':'paper','scenes':[]}
            for profile in ('general','gaming','cricket'):
                project['creator_profile']=profile
                write_report(path,project)
                page=path.read_text(encoding='utf-8')
                self.assertEqual('"archive_board": [' in page,profile=='cricket')
            project['scenes']=[{'index':1,'start':0,'duration':3,'text':'Rohit Sharma',
                'template':'archive_board','mode':'full','data':{},
                'assets_all':[{'kind':'person','name':'Rohit Sharma','historical':
                    {'year':2020,'team':'MI <team>','match_id':'final-2020'}}]}]
            project['creator_profile']='general'
            write_report(path,project)
            page=path.read_text(encoding='utf-8')
            self.assertIn('"archive_board": [',page)
            self.assertIn('Historical context: 2020',page)
            self.assertIn('MI &lt;team&gt;',page)
            self.assertIn('final-2020',page)

class ArchiveRenderTests(unittest.TestCase):
    def test_road_camera_carries_previous_images_out_and_next_image_in_from_right(self):
        from hinglish_motion.render import SceneRenderer
        with tempfile.TemporaryDirectory() as tmp:
            image=Path(tmp)/'photo.png';Image.new('RGB',(240,300),'blue').save(image)
            renderer=SceneRenderer(640,360)
            try:
                scene={'template':'archive_board','mode':'full','duration':12,'speed':1,
                    'data':{'archive_style':'map','archive_variant':0,
                        'assets':[{'src':image.as_uri(),'enter_at':at} for at in (.05,4,8)]}}
                renderer.load(scene)
                rects='ns=>ns.map(e=>{let r=e.getBoundingClientRect();return {left:r.left,right:r.right,centre:(r.left+r.right)/2}})'
                renderer.frame(5.8)
                positions=renderer.page.locator('.archive-photo').evaluate_all(rects)
                self.assertLess(positions[0]['right'],0)
                self.assertGreater(positions[1]['left'],0)
                renderer.frame(8.4);early=renderer.page.locator('.archive-photo').evaluate_all(rects)
                renderer.frame(10);late=renderer.page.locator('.archive-photo').evaluate_all(rects)
                self.assertLess(late[1]['right'],0)
                self.assertGreater(early[2]['centre']-late[2]['centre'],1920*.25)
                self.assertGreater(late[2]['left'],0)
                self.assertLess(late[2]['right'],1920)
                depths=renderer.page.locator('.archive-photo').evaluate_all('ns=>ns.map(e=>new DOMMatrix(getComputedStyle(e).transform).m43)')
                self.assertGreater(len(set(depths)),1)
            finally:renderer.close()

    def test_reel_has_equal_aligned_windows_and_keeps_every_photo_inside_its_window(self):
        from hinglish_motion.render import SceneRenderer
        with tempfile.TemporaryDirectory() as tmp:
            images=[]
            for index,size in enumerate([(160,240),(480,240),(240,320)]):
                path=Path(tmp)/f'photo-{index}.png';Image.new('RGB',size,'blue').save(path);images.append(path)
            renderer=SceneRenderer(640,360)
            try:
                scene={'template':'archive_board','mode':'full','duration':12,'speed':1,
                    'data':{'archive_style':'slate','archive_variant':1,
                        'assets':[{'src':p.as_uri(),'enter_at':at} for p,at in zip(images,[.05,4,8])]}}
                renderer.load(scene)
                rects='ns=>ns.map(e=>{let r=e.getBoundingClientRect();return {left:r.left,right:r.right,top:r.top,bottom:r.bottom,width:r.width,height:r.height}})'
                positions=[]
                for t in (6,10):
                    renderer.frame(t)
                    windows=renderer.page.locator('.film-window').evaluate_all(rects)
                    photos=renderer.page.locator('.archive-photo').evaluate_all(rects)
                    for field in ('top','bottom','width','height'):
                        self.assertLess(max(r[field] for r in windows)-min(r[field] for r in windows),1)
                    for photo,window in zip(photos,windows):
                        for field in ('left','top'):self.assertGreaterEqual(photo[field]+1,window[field])
                        for field in ('right','bottom'):self.assertLessEqual(photo[field]-1,window[field])
                    positions.append(windows)
                displacements=[a['left']-b['left'] for a,b in zip(*positions)]
                self.assertLess(max(displacements)-min(displacements),1)
                self.assertGreater(min(displacements),300)
            finally:renderer.close()

    def test_scene_geometry_is_distinct_without_relying_on_background_colours(self):
        from hinglish_motion.render import SceneRenderer
        with tempfile.TemporaryDirectory() as tmp:
            image=Path(tmp)/'photo.png';Image.new('RGB',(240,240),'blue').save(image)
            renderer=SceneRenderer(640,360)
            try:
                fingerprints=[]
                for style in ('night','slate','map','ink','sepia','glass','album'):
                    scene={'template':'archive_board','mode':'full','duration':12,'speed':1,
                        'data':{'archive_style':style,'archive_variant':1 if style=='slate' else 0,
                            'assets':[{'src':image.as_uri(),'enter_at':at} for at in (.05,2,4)]}}
                    renderer.load(scene);renderer.frame(6)
                    fingerprint=renderer.page.locator('.archive-photo,.archive-album-memory').evaluate_all('''ns=>ns.filter(e=>{
                        for(let n=e;n&&n.id!=='stage';n=n.parentElement)if(Number(getComputedStyle(n).opacity)<.05)return false;
                        let r=e.getBoundingClientRect();return r.right>0&&r.left<1920&&r.bottom>0&&r.top<1080;
                    }).map(e=>{let r=e.getBoundingClientRect();return [Math.round((r.left+r.right)/192),Math.round((r.top+r.bottom)/108),Math.round(r.width/96),Math.round(r.height/54)]}).sort()''')
                    fingerprints.append(json.dumps(fingerprint))
                self.assertEqual(len(set(fingerprints)),7,fingerprints)
            finally:renderer.close()

    def test_background_copies_do_not_reveal_players_before_their_cues(self):
        from hinglish_motion.render import SceneRenderer
        with tempfile.TemporaryDirectory() as tmp:
            photo=Path(tmp)/'portrait.png';Image.new('RGB',(160,240),(35,110,165)).save(photo)
            renderer=SceneRenderer(640,360)
            try:
                for style in ('slate','map','ink','sepia','glass','album','night'):
                    scene={'template':'archive_board','mode':'full','duration':6,'speed':1,
                        'data':{'archive_style':style,'assets':
                                [{'src':photo.as_uri(),'enter_at':at} for at in (1,2.6,3.5)]}}
                    renderer.load(scene);renderer.frame(.6)
                    nodes=renderer.page.locator('.archive-background img')
                    self.assertTrue(all(float(op)==0 for op in nodes.evaluate_all('(ns)=>ns.map(e=>getComputedStyle(e).opacity)')),style)
                    renderer.frame(2)
                    self.assertGreater(float(nodes.first.evaluate('e=>getComputedStyle(e).opacity')),0,style)
                    self.assertTrue(all(float(op)==0 for op in renderer.page.locator('.archive-background img[data-asset="1"],.archive-background img[data-asset="2"]').evaluate_all('(ns)=>ns.map(e=>getComputedStyle(e).opacity)')),style)
                    self.assertTrue(renderer.page.locator('.archive-world').get_attribute('data-background'),style)
            finally:renderer.close()

    def test_portrait_and_wide_cards_keep_their_source_aspect_ratio(self):
        from hinglish_motion.render import SceneRenderer
        with tempfile.TemporaryDirectory() as tmp:
            portrait=Path(tmp)/'portrait.png';Image.new('RGB',(160,240),'blue').save(portrait)
            wide=Path(tmp)/'wide.png';Image.new('RGB',(480,240),'green').save(wide)
            renderer=SceneRenderer(640,360)
            try:
                for style in ('slate','map','ink','sepia','glass','album','night'):
                    for width,height in ((640,360),(360,640)):
                        scene={'template':'archive_board','mode':'full','duration':6,'speed':1,
                            'data':{'archive_style':style,'assets':
                                    [{'src':p.as_uri(),'enter_at':.05} for p in (portrait,wide)]}}
                        # Reload in the requested design orientation on the same page.
                        renderer.page.set_viewport_size({'width':1920 if width>height else 1080,'height':1080 if width>height else 1920})
                        renderer.design=(width,height);renderer.load(scene);renderer.frame(2)
                        ratios=renderer.page.locator('.archive-photo').evaluate_all('(ns)=>ns.map(e=>parseFloat(e.style.width)/parseFloat(e.style.height))')
                        self.assertAlmostEqual(ratios[0],2/3,places=3)
                        self.assertAlmostEqual(ratios[1],2,places=3)
            finally:renderer.close()

    def test_filmstrip_keeps_first_photo_readable_before_travelling(self):
        from hinglish_motion.render import SceneRenderer
        with tempfile.TemporaryDirectory() as tmp:
            image=Path(tmp)/'photo.png';Image.new('RGB',(240,240),(60,150,240)).save(image)
            renderer=SceneRenderer(640,360)
            try:
                scene={'template':'archive_board','mode':'full','duration':6,'speed':1,'data':
                    {'archive_style':'slate','archive_variant':1,'assets':
                     [{'src':image.as_uri(),'enter_at':t} for t in (.05,1.4,2.9)]}}
                renderer.load(scene);renderer.frame(.95)
                visible=renderer.page.locator('.archive-photo').first.evaluate('''e=>{
                    const r=e.getBoundingClientRect(),w=e.closest('.archive-world').getBoundingClientRect();
                    return Math.max(0,Math.min(r.right,w.right)-Math.max(r.left,w.left))/r.width;
                }''')
                self.assertGreater(visible,.7)
            finally:renderer.close()

    def test_alternate_sequences_change_the_motion_and_keep_name_gates(self):
        from hinglish_motion.render import SceneRenderer
        import numpy as np
        with tempfile.TemporaryDirectory() as tmp:
            image=Path(tmp)/'photo.png';Image.new('RGB',(240,240),(60,150,240)).save(image)
            renderer=SceneRenderer(640,360)
            try:
                for style in ('slate','sepia','ink','map','glass','album','night'):
                    frames=[]
                    for variant in (0,1):
                        scene={'template':'archive_board','mode':'full','duration':6,'speed':.9,
                            'data':{'label':'Cricket Journey','archive_style':style,'archive_variant':variant,
                                'assets':[{'src':image.as_uri(),'enter_at':1.2},{'src':image.as_uri(),'enter_at':2.6},{'src':image.as_uri(),'enter_at':3.5}]}}
                        self.assertEqual(renderer.check(scene),[],(style,variant))
                        renderer.load(scene);renderer.frame(.6)
                        self.assertTrue(all(float(x)==0 for x in renderer.page.locator('.archive-photo').evaluate_all('(nodes)=>nodes.map(e=>getComputedStyle(e).opacity)')))
                        early=renderer.frame(1.6);later=renderer.frame(2.2)
                        self.assertGreater(np.abs(early.astype(float)-later.astype(float)).mean(),1,(style,variant))
                        self.assertEqual(float(renderer.page.locator('.archive-photo').nth(2).evaluate('(e)=>getComputedStyle(e).opacity')),0)
                        frames.append(renderer.frame(3.8))
                    self.assertGreater(np.abs(frames[0].astype(float)-frames[1].astype(float)).mean(),2,style)
            finally:renderer.close()

    def test_chapter_variants_and_spoken_entry_times_render(self):
        from hinglish_motion.render import SceneRenderer
        import numpy as np
        with tempfile.TemporaryDirectory() as tmp:
            image=Path(tmp)/'photo.png';Image.new('RGB',(240,240),(60,150,240)).save(image)
            renderer=SceneRenderer(640,360)
            try:
                looks=[]
                for style in ('slate','sepia','ink','map','glass','album','night'):
                    scene={'template':'archive_board','mode':'full','duration':5,'speed':.9,'data':{'label':'Cricket Journey','archive_style':style,'assets':[{'src':image.as_uri(),'enter_at':1.2},{'src':image.as_uri(),'enter_at':2.6}]}}
                    self.assertEqual(renderer.check(scene),[],style)
                    renderer.load(scene);renderer.frame(.6)
                    self.assertEqual(float(renderer.page.locator('.archive-photo').first.evaluate('(e)=>getComputedStyle(e).opacity')),0,style)
                    renderer.frame(2.4)
                    self.assertGreater(float(renderer.page.locator('.archive-photo').first.evaluate('(e)=>getComputedStyle(e).opacity')),.95,style)
                    self.assertEqual(float(renderer.page.locator('.archive-photo').nth(1).evaluate('(e)=>getComputedStyle(e).opacity')),0,style)
                    looks.append(renderer.frame(3.8))
                self.assertTrue(all(np.abs(looks[0].astype(float)-look.astype(float)).mean()>4 for look in looks[1:]))
                scene['data'].update(archive_style='ink',archive_grade='monochrome')
                renderer.load(scene);renderer.frame(3.8)
                self.assertIn('grayscale(1)',renderer.page.locator('.archive-ink-hero').evaluate('(e)=>getComputedStyle(e).filter'))
            finally:renderer.close()

if __name__=='__main__':unittest.main()
