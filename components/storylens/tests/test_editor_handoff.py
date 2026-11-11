import json
from pathlib import Path
import tempfile
import unittest
from PIL import Image

from hinglish_app import capcut_adapter as capcut
from hinglish_app.editor_handoff import catalog,output_folder


class EditorHandoffTests(unittest.TestCase):
    def setup_root(self,name):
        root=Path(name);home=root/'CapCut';base=home/'User Data/Projects/com.lveditor.draft';base.mkdir(parents=True)
        (root/'config.editors.local.json').write_text(json.dumps({'capcut_home':str(home)}))
        (root/'output').mkdir();(root/'cache/assistant').mkdir(parents=True)
        return root,base

    def test_native_project_preserves_existing_index_and_reuses_exact_handoff(self):
        with tempfile.TemporaryDirectory() as tmp:
            root,base=self.setup_root(tmp)
            index={'all_draft_store':[{'draft_id':'owner','draft_name':'Owner project'}],'draft_ids':8,'root_path':str(base)}
            (base/'root_meta_info.json').write_text(json.dumps(index))
            image=root/'output/demo.png';Image.new('RGB',(90,160),'orange').save(image)
            first=capcut.create_project(root,image,'Storylens image','test')
            second=capcut.create_project(root,image,'Storylens image','test')
            self.assertEqual(first,second)
            saved=json.loads((base/'root_meta_info.json').read_text())
            self.assertEqual(saved['all_draft_store'][-1],index['all_draft_store'][0])
            self.assertEqual(saved['draft_ids'],8)
            self.assertEqual(len(saved['all_draft_store']),2)
            draft=json.loads((Path(first['folder'])/'draft_content.json').read_text())
            self.assertEqual(draft['duration'],5_000_000)
            self.assertEqual(draft['materials']['videos'][0]['type'],'photo')
            self.assertEqual(draft['canvas_config']['width'],90)
            manifest=json.loads((Path(first['folder'])/'Timelines/project.json').read_text())
            self.assertEqual(manifest['main_timeline_id'],draft['id'])
            self.assertTrue(Path(draft['materials']['videos'][0]['path']).is_file())
            self.assertEqual(len(list((root/'output/editor-handoffs/capcut-index-backups').glob('*.json'))),1)
            Image.new('RGB',(90,160),'blue').save(image)
            with self.assertRaisesRegex(ValueError,'different video'):capcut.create_project(root,image,'Storylens image','test')

    def test_catalog_reuses_only_matching_generated_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            root,base=self.setup_root(tmp);folder=root/'output/zoom/demo';folder.mkdir(parents=True)
            clip=root/'output/finished.mp4';clip.write_bytes(b'fixture')
            (root/'cache/assistant/chat.json').write_text(json.dumps({'messages':[{'result':{'folder':str(folder)},'videos':[str(clip)]}]}))
            self.assertEqual(catalog(root,folder)['videos'],[str(clip.resolve())])
            another=root/'output/other';another.mkdir()
            self.assertEqual(catalog(root,another)['videos'],[])
            with self.assertRaises(ValueError):output_folder(root,root/'cache')

    def test_source_picker_does_not_accept_unlisted_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root,base=self.setup_root(tmp)
            with self.assertRaisesRegex(ValueError,'missing or moved'):capcut.source(root,'../outside','any')

    def test_cinematic_result_exports_its_own_timeline_and_finished_reel(self):
        with tempfile.TemporaryDirectory() as tmp:
            root,_=self.setup_root(tmp);folder=root/'output/cinematic-reels/example';folder.mkdir(parents=True)
            timeline=folder/'CINEMATIC_REEL.xml';timeline.write_text('<xmeml/>')
            video=folder/'CINEMATIC_REEL.mp4';video.write_bytes(b'fixture')
            (folder/'CINEMATIC_REEL.partial.mp4').write_bytes(b'incomplete')
            (folder/'unrelated.xml').write_text('<xmeml/>')
            result=catalog(root,folder)
            self.assertEqual(result['xml_files'],[str(timeline.resolve())])
            self.assertEqual(result['videos'],[str(video.resolve())])

    def test_caption_comparison_preview_is_used_until_a_studio_render_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            root,_=self.setup_root(tmp);folder=root/'output/captions/script-previews/example';folder.mkdir(parents=True)
            preview=folder/'caption-preview.mp4';preview.write_bytes(b'comparison')
            self.assertEqual(catalog(root,folder)['videos'],[str(preview.resolve())])
            current=folder/'captioned-preview.mp4';current.write_bytes(b'edited studio render')
            self.assertEqual(catalog(root,folder)['videos'],[str(current.resolve())])

    def test_editable_word_project_keeps_text_timing_and_portable_font(self):
        with tempfile.TemporaryDirectory() as tmp:
            root,base=self.setup_root(tmp)
            exe=root/'CapCut/Apps/test/CapCut.exe';exe.parent.mkdir(parents=True);exe.write_bytes(b'fixture')
            image=root/'output/source.png';Image.new('RGB',(720,1280),'black').save(image)
            font=Path(__file__).resolve().parents[1]/'hinglish_captions/fonts/Inter-Bold.otf'
            rows=[{'text':'Hello!','start':.12,'end':.71,'font_path':str(font),'color':'#52C7FF','size_px':56,'layout':{'x':.4,'y':.6}}]
            result=capcut.create_project(root,image,'Word test','word-test',word_rows=rows)
            draft=json.loads((Path(result['folder'])/'draft_content.json').read_text())
            self.assertEqual([t['type'] for t in draft['tracks']],['video','text'])
            word=draft['materials']['texts'][0];self.assertEqual(json.loads(word['content'])['text'],'Hello!')
            self.assertTrue(Path(word['font_path']).is_relative_to(result['folder']))
            self.assertTrue(Path(word['font_path']).is_file())
            self.assertEqual(draft['tracks'][1]['segments'][0]['target_timerange'],{'start':120000,'duration':590000})
            changed=[dict(rows[0],text='Different')]
            with self.assertRaisesRegex(ValueError,'different video'):capcut.create_project(root,image,'Word test','word-test',word_rows=changed)

    def test_saved_draft_placeholder_resolves_inside_its_project(self):
        root=Path('output').resolve()
        self.assertEqual(capcut.media_path(root,'##_draftpath_placeholder_TEST_##/clip.mp4'),root/'clip.mp4')
        with self.assertRaisesRegex(ValueError,'location is invalid'):capcut.media_path(root,'##_draftpath_placeholder_TEST_##/../../private.mp4')

    def test_designed_words_keep_overlapping_words_independent(self):
        from hinglish_app.caption_scene import caption_one
        project={'width':720,'height':1280,'media':{'duration':3,'fps':30},
            'style':'caption_1','font':'template','word_visibility':'phrase',
            'cues':[{'start':.1,'end':2.5,'words':[
                {'text':'Imagine','start':.1,'end':.6},
                {'text':'a','start':.6,'end':.7},
                {'text':'monument','start':.7,'end':2.3}]}]}
        rows=caption_one(project)
        self.assertEqual(len(rows),3)
        self.assertEqual({r['text'] for r in rows},{'Imagine','a','MONUMENT'})
        self.assertEqual(len({r['slot'] for r in rows}),3)
        hero=next(r for r in rows if r['text']=='MONUMENT')
        support=next(r for r in rows if r['text']=='Imagine')
        self.assertGreater(hero['size_px'],support['size_px'])
        self.assertEqual(support['end'],2.5)
        self.assertEqual(hero['start'],.7)
        self.assertLess(support['layout']['y'],hero['layout']['y'])
        self.assertEqual(hero['animation'][0]['alpha'],0)
        self.assertEqual(hero['animation'][-1]['alpha'],1)
        with tempfile.TemporaryDirectory() as tmp:
            root,base=self.setup_root(tmp)
            exe=root/'CapCut/Apps/test/CapCut.exe';exe.parent.mkdir(parents=True);exe.write_bytes(b'fixture')
            picture=root/'output/picture.png';Image.new('RGB',(720,1280),'black').save(picture)
            result=capcut.create_project(root,picture,'Designed words','design-fixture',word_rows=rows)
            draft=json.loads((Path(result['folder'])/'draft_content.json').read_text())
            tracks=[t for t in draft['tracks'] if t['type']=='text']
            self.assertEqual(len(tracks),3)
            self.assertTrue(all(t['segments'][0]['common_keyframes'] for t in tracks))
            self.assertTrue(all(m['type']=='text' for m in draft['materials']['texts']))
