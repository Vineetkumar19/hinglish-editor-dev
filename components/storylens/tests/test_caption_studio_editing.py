import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.request import Request,urlopen
from urllib.error import HTTPError

from hinglish_captions.core import CaptionCue,CaptionWord,retime_cue_text
from hinglish_captions.editing import apply_timings,layouts_for
from hinglish_captions.renderer import draw_editor_caption
from hinglish_captions.subtitles import write_srt

ROOT=Path(__file__).resolve().parents[1]


class CaptionStudioEditingTests(unittest.TestCase):
    def cue(self):return CaptionCue((CaptionWord('Kissi',1,1.4),CaptionWord('khwab',1.8,2.2)),1,2.5)

    def test_original_animation_builds_and_holds_each_lyric_group_in_all_five_styles(self):
        from PIL import ImageDraw
        from hinglish_captions.styles import template
        original=ImageDraw.ImageDraw.text
        words='Haan tujhe dekhta raha'.split()
        for number in range(1,6):
            style=f'typography_{number}'
            layout={'x':.5,'y':template(style).get('default_position',.7),'size':1}
            cue=CaptionCue(tuple(CaptionWord(word,1+i*.5,1.25+i*.5) for i,word in enumerate(words)),1,3)
            # Include silent gaps and the final hold after the last word ends.
            for timestamp,count in ((.9,0),(1.15,1),(1.4,1),(1.65,2),(1.9,2),(2.15,3),(2.4,3),(2.65,4),(2.95,4),(3,0)):
                painted=[]
                def record(draw,xy,text,*args,**kwargs):
                    colors=[kwargs.get('fill'),kwargs.get('stroke_fill')]
                    if any(isinstance(color,int) and color>0 or isinstance(color,tuple) and len(color)==4 and color[3]>0 for color in colors):
                        painted.extend(str(text).casefold().split())
                    return original(draw,xy,text,*args,**kwargs)
                with self.subTest(style=style,time=timestamp),patch.object(ImageDraw.ImageDraw,'text',record):
                    image=draw_editor_caption(360,640,cue,timestamp,style,'template',layout,'phrase')
                self.assertEqual(set(painted),set(word.casefold() for word in words[:count]),(style,timestamp))
                self.assertEqual(image.getbbox() is not None,count>0)
            # No premature fade, defocus or disappearing words at group end.
            held=draw_editor_caption(360,640,cue,2.85,style,'template',layout,'phrase')
            last=draw_editor_caption(360,640,cue,2.999,style,'template',layout,'phrase')
            self.assertEqual(held.tobytes(),last.tobytes(),style)

    def test_original_animation_word_timing_covers_all_eight_typography_one_compositions(self):
        from PIL import ImageDraw
        original=ImageDraw.ImageDraw.text
        words='Haan tujhe dekhta raha'.split()
        for variant in range(8):
            start=variant/30
            cue=CaptionCue(tuple(CaptionWord(word,start+.1+i*.4,start+.3+i*.4) for i,word in enumerate(words)),start,start+2)
            for count in range(1,5):
                painted=[]
                def record(draw,xy,text,*args,**kwargs):
                    colors=[kwargs.get('fill'),kwargs.get('stroke_fill')]
                    if any(isinstance(color,tuple) and len(color)==4 and color[3]>0 for color in colors):painted.extend(str(text).casefold().split())
                    return original(draw,xy,text,*args,**kwargs)
                with self.subTest(variant=variant,count=count),patch.object(ImageDraw.ImageDraw,'text',record):
                    draw_editor_caption(360,640,cue,start+.35+(count-1)*.4,'typography_1','template',{'x':.5,'y':.7,'size':1},'phrase')
                self.assertEqual(set(painted),set(word.casefold() for word in words[:count]))

    def test_all_five_keep_styled_glyphs_only_inside_the_spoken_word_interval(self):
        from PIL import ImageDraw
        from hinglish_captions.styles import template
        original=ImageDraw.ImageDraw.text
        for number in range(1,6):
            style=f'typography_{number}';layout={'x':.5,'y':template(style).get('default_position',.7),'size':1}
            for timestamp,expected in ((1.2,'kissi'),(1.6,None),(2,'khwab'),(2.4,None)):
                painted=[]
                def record(draw,xy,text,*args,**kwargs):
                    fill=kwargs.get('fill');stroke=kwargs.get('stroke_fill')
                    visible=lambda color:isinstance(color,int) and color>0 or isinstance(color,tuple) and len(color)==4 and color[3]>0
                    if visible(fill) or visible(stroke):painted.extend(str(text).casefold().split())
                    return original(draw,xy,text,*args,**kwargs)
                with self.subTest(style=style,time=timestamp),patch.object(ImageDraw.ImageDraw,'text',record):
                    image=draw_editor_caption(360,640,self.cue(),timestamp,style,'template',layout,'styled_spoken')
                    if expected is None:self.assertIsNone(image.getbbox())
                    else:
                        self.assertIsNotNone(image.getbbox())
                        self.assertTrue(painted)
                        self.assertEqual(set(painted),{expected})

    def test_typography_five_support_interlocks_with_the_red_hero_for_song_phrases(self):
        import numpy as np
        from hinglish_captions.renderer import draw_caption
        overlaps=[]
        for phrase in ('Haan tujhe dekhta raha','Kissi khwab ki tarah','Jo ab samne hai tu'):
            cue=CaptionCue(tuple(CaptionWord(word,i*.12,(i+1)*.12) for i,word in enumerate(phrase.split())),0,1.4)
            pixels=np.asarray(draw_caption(720,1280,cue,1.2,'typography_5',position=.22))
            red=(pixels[:,:,0]>150)&(pixels[:,:,1]<110)&(pixels[:,:,3]>120)
            white=(pixels[:,:,:3].min(axis=2)>190)&(pixels[:,:,3]>120)
            rows=np.where(red.any(axis=1))[0]
            self.assertGreater(len(rows),0)
            overlaps.append(bool(white[rows.min():rows.max()+1].any()))
            bounds=draw_caption(720,1280,cue,1.2,'typography_5',position=.22).getbbox()
            self.assertLess(bounds[3]-bounds[1],165,phrase)
        # Tall calligraphic swashes interlock; short lowercase forms retain
        # the same compact origins without manufacturing a glyph collision.
        self.assertTrue(any(overlaps))

    def test_typography_one_word_timing_covers_all_eight_compositions(self):
        from PIL import ImageDraw
        original=ImageDraw.ImageDraw.text
        for variant in range(8):
            start=variant/30
            cue=CaptionCue(tuple(CaptionWord(word,start+.1+i*.3,start+.35+i*.3) for i,word in enumerate('Haan tujhe dekhta raha'.split())),start,start+1.4)
            for offset,expected in ((.2,'haan'),(.5,'tujhe'),(.8,'dekhta'),(1.1,'raha')):
                painted=[]
                def record(draw,xy,text,*args,**kwargs):
                    colors=[kwargs.get('fill'),kwargs.get('stroke_fill')]
                    if any(isinstance(color,tuple) and len(color)==4 and color[3]>0 for color in colors):painted.extend(str(text).casefold().split())
                    return original(draw,xy,text,*args,**kwargs)
                with self.subTest(variant=variant,word=expected),patch.object(ImageDraw.ImageDraw,'text',record):
                    draw_editor_caption(360,640,cue,start+offset,'typography_1','template',{'x':.5,'y':.7,'size':1},'styled_spoken')
                self.assertEqual(set(painted),{expected})

    def test_saving_scale_links_every_group_for_each_typography_and_keeps_positions(self):
        from hinglish_captions.project import write_project,rebuild_project
        from hinglish_cut.model import Media
        for number in range(1,6):
            with self.subTest(style=number),tempfile.TemporaryDirectory(dir=ROOT/'tmp') as folder:
                folder=Path(folder);source=folder/'source.mp4';source.write_bytes(b'fixture')
                media=Media('test',str(source),3,'30',360,640,2,48000)
                cues=[self.cue(),CaptionCue((CaptionWord('tarah',2.6,2.9),),2.6,3)]
                project=folder/'caption-project.json';write_project(project,media,cues,f'typography_{number}','source','source.mp4')
                layouts=[{'x':.3,'y':.2,'size':.5},{'x':.6,'y':.4,'size':1.3}]
                with patch('hinglish_captions.project.render_overlay'),patch('hinglish_captions.project.export_caption_xml'):
                    rebuild_project(project,{'size':.62,'cue_layouts':layouts,'word_visibility':'styled_spoken'},progress=lambda _:None)
                result=json.loads(project.read_text(encoding='utf-8'))
                self.assertEqual([row['size'] for row in result['cue_layouts']],[.62,.62])
                self.assertEqual([(row['x'],row['y']) for row in result['cue_layouts']],[(.3,.2),(.6,.4)])

    def test_all_five_original_presets_survive_editor_without_pixel_changes(self):
        from hinglish_captions.renderer import draw_caption
        from hinglish_captions.styles import template
        for number in range(1,6):
            style=f'typography_{number}';position=template(style).get('default_position',.7)
            cue=CaptionCue(tuple(CaptionWord(word,i*.15,(i+1)*.15) for i,word in enumerate('vakt aur fasle ko par'.split())),0,1.3)
            for timestamp in (.04,.27,.65,1.2):
                with self.subTest(style=style,timestamp=timestamp):
                    original=draw_caption(360,640,cue,timestamp,style,position=position)
                    edited=draw_editor_caption(360,640,cue,timestamp,style,'template',{'x':.5,'y':position,'size':1},'phrase')
                    self.assertEqual(original.tobytes(),edited.tobytes())

    def test_template_movement_translates_original_frame_without_recentering_its_ink(self):
        import numpy as np
        from hinglish_captions.renderer import draw_caption
        cue=CaptionCue(tuple(CaptionWord(word,i*.2,(i+1)*.2) for i,word in enumerate('vakt aur fasle ko par'.split())),0,1.3)
        for timestamp in (.04,.5,.9):
            original=np.asarray(draw_caption(400,640,cue,timestamp,'typography_1',position=.7))
            moved=np.asarray(draw_editor_caption(400,640,cue,timestamp,'typography_1','template',{'x':.55,'y':.7,'size':1},'phrase'))
            self.assertTrue(np.array_equal(original[:,:-20],moved[:,20:]))

    def test_exact_word_intervals_do_not_show_early_late_or_in_gaps(self):
        cue=self.cue();layout={'x':.5,'y':.5,'size':1}
        def image(t):return draw_editor_caption(320,180,cue,t,'typography_2','arial',layout,'spoken')
        for t in (.9,1.4,1.6,2.2,2.5):self.assertIsNone(image(t).getbbox(),t)
        for t in (1,1.2,1.8,2.19):self.assertIsNotNone(image(t).getbbox(),t)

    def test_dragged_position_and_small_scale_reach_the_rendered_pixels(self):
        cue=self.cue()
        def bounds(x,y,size):return draw_editor_caption(640,360,cue,1.2,'typography_2','arial',{'x':x,'y':y,'size':size},'spoken').getbbox()
        normal=bounds(.5,.5,1);small=bounds(.25,.3,.15)
        self.assertLess(small[2]-small[0],(normal[2]-normal[0])/2)
        self.assertAlmostEqual((small[0]+small[2])/2,640*.25,delta=2)
        self.assertAlmostEqual((small[1]+small[3])/2,360*.3,delta=2)

    def test_spelling_or_style_edit_preserves_existing_recognized_timing(self):
        changed=retime_cue_text(self.cue(),'Kisi khwaab')
        self.assertEqual([(w.start,w.end) for w in changed.words],[(1,1.4),(1.8,2.2)])

    def test_timeline_edits_validate_all_words_and_preserve_selected_changes(self):
        rows=[{'start':2,'end':4,'words':[{'start':2,'end':2.5},{'start':3,'end':3.8}]}]
        cue=apply_timings([self.cue()],rows,5)[0]
        self.assertEqual(cue.words[1].start,3)
        for start,end in ((float('nan'),4),(-1,4),(2,6),(4,2)):
            bad=copy.deepcopy(rows);bad[0].update(start=start,end=end)
            with self.assertRaises(ValueError):apply_timings([self.cue()],bad,5)
        bad=copy.deepcopy(rows);bad[0]['words'][1]['start']=2.1
        with self.assertRaises(ValueError):apply_timings([self.cue()],bad,5)
        layout=layouts_for([cue],[{'x':.2,'y':.1,'size':.08}])[0]
        self.assertEqual(layout['size'],.08)

    def test_word_only_srt_preserves_real_gaps(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as folder:
            path=Path(folder)/'captions.srt';write_srt(path,[self.cue()],'spoken')
            text=path.read_text(encoding='utf-8-sig')
            self.assertIn('00:00:01,000 --> 00:00:01,400\nKissi',text)
            self.assertIn('00:00:01,800 --> 00:00:02,200\nkhwab',text)

    def test_import_accepts_editor_rounding_but_rejects_real_word_overflow(self):
        cue=CaptionCue((CaptionWord('the',11.8073,12.4),CaptionWord('moon',12.4,13.28954)),11.8073,13.28954)
        rows=[{'start':11.8073,'end':13.2895,'words':[{'start':11.8073,'end':12.40004},{'start':12.4,'end':13.28954}]}]
        saved=apply_timings([cue],rows,30)[0]
        self.assertEqual(saved.words[-1].end,saved.end)
        self.assertEqual(saved.words[1].start,saved.words[0].end)
        rows[0]['words'][-1]['end']=13.30
        with self.assertRaises(ValueError):apply_timings([cue],rows,30)

    def test_real_export_uses_changed_canvas_and_keeps_audio(self):
        import av
        from hinglish_cut.demo import create_demo_media
        from hinglish_captions.renderer import render_overlay
        from hinglish_captions.export_video import render_captioned_video
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as folder:
            folder=Path(folder);source=folder/'source.mp4';create_demo_media(source,seconds=1)
            cue=CaptionCue((CaptionWord('Test',.2,.7),),.1,.9)
            overlay=folder/'overlay.mov'
            render_overlay(overlay,[cue],180,320,1,25,word_visibility='spoken',progress=lambda _:None)
            output=folder/'export.mp4';render_captioned_video(source,overlay,output,device='cpu')
            with av.open(str(output)) as media:
                self.assertEqual((media.streams.video[0].width,media.streams.video[0].height),(180,320))
                self.assertTrue(media.streams.audio)
                self.assertEqual(sum(1 for _ in media.decode(video=0)),25)


class ConnectedStudioTests(unittest.TestCase):
    def test_old_typography_report_gets_zoom_profile_before_first_draw(self):
        from hinglish_app.presentation import caption_html
        content=b'<body><script>const project={style:"typography_3",kinetic_profile:{}};</script><script>// Direct editing augments the existing template library without losing edits.\noldEditor();</script></body>'
        html=caption_html(content,ROOT/'output/captions/example','test-only').decode('utf-8')
        self.assertLess(html.index('project.kinetic_profile='),html.index('// Direct editing augments'))
        self.assertIn('"zoom_styles":',html)
        self.assertNotIn('oldEditor();',html)

    def test_retired_styles_are_removed_from_saved_picker_but_keep_project(self):
        from hinglish_app.presentation import caption_html
        from hinglish_captions.styles import SELECTABLE_TEMPLATES, template
        retired=('typography_1','typography_2','minimal')
        cards=''.join(f'<button class="template-card" data-style="{key}"><div>sample</div></button>' for key in (*retired,'caption_1'))
        content=('<body><script>const project={style:"typography_1",text:"owner edit"};</script>'+cards+'</body>').encode()
        html=caption_html(content,ROOT/'output/captions/example','test-only').decode('utf-8')
        for key in retired:
            self.assertNotIn(key,SELECTABLE_TEMPLATES)
            self.assertNotIn(f'data-style="{key}"',html)
            self.assertTrue(template(key))
        self.assertIn('data-style="caption_1"',html)
        self.assertIn('style:"typography_1",text:"owner edit"',html)

    def test_old_reference_guard_uses_renderer_capability_not_bridge_identity(self):
        from hinglish_app.presentation import caption_html
        from hinglish_captions.project import caption_export_capabilities
        content=b'<body><script>const project={cues:[{text:"owner edit"}]};</script><script>// Kinetic Documentary uses a canvas\nconst stale_engine_sha256="old-token";</script></body>'
        html=caption_html(content,ROOT/'output/captions/example','test-only').decode('utf-8')
        self.assertIn('owner edit',html)
        self.assertNotIn('stale_engine_sha256',html)
        self.assertIn("'/api/captions/capabilities'",html)
        self.assertIn('runtime.reference_layout_revision>=2',html)
        self.assertIn('project.kinetic_profile=',html)
        self.assertIn('"echo_zoom":',html)
        self.assertGreaterEqual(caption_export_capabilities()['reference_layout_revision'],2)

    def test_old_caption_three_preview_gets_current_design_without_losing_edits(self):
        from hinglish_app.presentation import caption_html
        from hinglish_captions.caption_three import profile
        content=b'<body><script>const project={cues:[{text:"owner edit"}]};</script><script>// Caption 3 uses the same compositions\noldPreview();</script></body>'
        html=caption_html(content,ROOT/'output/captions/example','test-only').decode('utf-8')
        self.assertIn('owner edit',html)
        self.assertNotIn('oldPreview();',html)
        self.assertIn('"readable_line_gap": '+str(profile()['readable_line_gap']),html)
        self.assertIn("font-family:'Caption Three Serif'",html)
        self.assertIn('function layoutFor',html)

    def test_hosted_report_range_media_and_origin_protection(self):
        import threading
        from hinglish_app.server import serve
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as folder:
            root=Path(folder);output=root/'output/captions/session';output.mkdir(parents=True)
            (output/'report.html').write_text('<b>Caption studio</b>')
            (output/'source.mp4').write_bytes(b'0123456789')
            (root/'private.txt').write_text('private')
            server,state=serve(root,0);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            base=f'http://127.0.0.1:{state.port}'
            try:
                with urlopen(base+'/caption-output/session/report.html') as r:self.assertIn(b'Caption studio',r.read())
                with urlopen(Request(base+'/caption-output/session/source.mp4',headers={'Range':'bytes=2-5'})) as r:
                    self.assertEqual(r.status,206);self.assertEqual(r.read(),b'2345')
                for path in ('/caption-output/%2e%2e/%2e%2e/private.txt','/caption-output/session/missing.mp4'):
                    with self.assertRaises(HTTPError):urlopen(base+path)
                with self.assertRaises(HTTPError) as denied:urlopen(Request(base+'/api/bridge',headers={'Origin':'null'}))
                self.assertEqual(denied.exception.code,403)
                with urlopen(Request(base+'/api/bridge',headers={'Origin':base})) as r:self.assertEqual(json.load(r)['token'],state.token)
            finally:server.shutdown();server.server_close();thread.join()


if __name__=='__main__':unittest.main()


class DirectCaptionImportTests(unittest.TestCase):
    def test_save_design_without_rendering_preserves_size_and_position(self):
        from hinglish_captions.project import rebuild_project
        source={'media':{'id':'test','path':'source.mp4','duration':2,'fps':'30','width':360,'height':640,'channels':2,'sample_rate':48000},'source_relative':'source.mp4','cues':[{'start':0,'end':2,'words':[{'text':'Hello','start':0,'end':1},{'text':'world','start':1,'end':2}]}]}
        source['cues']=source['cues'][:1]
        source['word_colors']=[[None]*len(source['cues'][0]['words'])]
        source.pop('cue_layouts',None)
        for style in ('caption_1','caption_2','caption_3','caption_4','caption_5','typography_5','documentary_echo'):
            with self.subTest(style=style),tempfile.TemporaryDirectory() as directory:
                path=Path(directory)/'caption-project.json';path.write_text(json.dumps(source),encoding='utf-8')
                with patch('hinglish_captions.project.render_overlay') as render,patch('hinglish_captions.project.write_report'):
                    result=rebuild_project(path,{'save_project_only':True,'style':style,'size':.65,'cue_layouts':[{'x':.3,'y':.4,'size':.65}]})
                render.assert_not_called()
                saved=json.loads(path.read_text('utf-8'))
                self.assertEqual(saved['style'],style)
                self.assertEqual(saved['cue_layouts'][0],{'x':.3,'y':.4,'size':.65})
                self.assertTrue(saved['preview_stale'])
                self.assertIsNone(result['video'])
