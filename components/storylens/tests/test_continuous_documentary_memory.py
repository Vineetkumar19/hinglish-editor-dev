import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch,MagicMock
import cv2
import numpy as np
from hinglish_niche.continuous_motion import ContinuousMotionScan,continuity_review
from hinglish_niche.documentary_memory import install,context,export,chunks
from hinglish_niche.reference_dna import StyleDatabase
from hinglish_niche.style_memory import search
from hinglish_niche.profiles import inject,use

class ContinuousDocumentaryMemoryTests(unittest.TestCase):
    def test_hold_is_distinguished_from_camera_pan_and_no_points_is_unknown(self):
        rng=np.random.default_rng(22);image=rng.integers(0,256,(144,256,3),dtype=np.uint8)
        with tempfile.TemporaryDirectory() as tmp:
            scan=ContinuousMotionScan(Path(tmp)/'pan')
            for i in range(30):
                frame=cv2.warpAffine(image,np.float32([[1,0,i*.5],[0,1,0]]),(256,144))
                scan(frame,i/30,i,2)
            rows=scan.close();self.assertEqual(rows[0]['native_frames'],30)
            self.assertGreater(rows[0]['median']['dx'],12)
            self.assertGreater(rows[0]['motion_fraction_of_measurable_time'],.95)
            hold=ContinuousMotionScan(Path(tmp)/'hold')
            for i in range(30):hold(image,i/30,i,0)
            self.assertLess(hold.close()[0]['motion_fraction_of_measurable_time'],.01)
            blank=ContinuousMotionScan(Path(tmp)/'blank')
            for i in range(30):blank(np.zeros_like(image),i/30,i,0)
            row=blank.close()[0];self.assertEqual(row['classification'],'unmeasurable')
            self.assertIsNone(row['motion_fraction_of_measurable_time'])

    def test_cut_does_not_become_a_huge_camera_move(self):
        with tempfile.TemporaryDirectory() as tmp:
            scan=ContinuousMotionScan(tmp)
            scan(np.zeros((144,256,3),np.uint8),0,0,0)
            scan(np.full((144,256,3),255,np.uint8),1/30,1,255)
            row=scan.close()[0];self.assertEqual(row['cut_candidates'],1)
            self.assertIsNone(row['median']['dx'])

    def test_grain_or_local_noise_is_not_a_camera_pass_and_unknown_is_not_called_static(self):
        base={'start':0,'end':1,'tracked_frame_fraction':1,'median':{'dx':0,'dy':0,'zoom':0,'rotation':0,'residual':20}}
        self.assertTrue(continuity_review([base])['needs_review'])
        unknown={**base,'tracked_frame_fraction':0,'median':{**base['median'],'dx':None}}
        result=continuity_review([unknown]);self.assertFalse(result['needs_review']);self.assertTrue(result['unmeasurable_ranges'])

    def test_projected_photo_movement_passes_while_a_frozen_photo_and_late_hold_fail(self):
        from hinglish_niche.photo_continuity import review
        image={'id':0,'src':'photo.jpg','x':.2,'y':.2,'width':.4,'height':.5}
        frozen=[[image] for i in range(90)]
        self.assertTrue(review(frozen,30)['needs_review'])
        moving=[[{**image,'x':.2+i*.0002}] for i in range(90)]
        self.assertFalse(review(moving,30)['needs_review'])
        tail=moving[:30]+[[moving[29][0]] for i in range(60)]
        self.assertTrue(review(tail,30)['needs_review'])
        self.assertFalse(review([[] for i in range(90)],30)['available'])

    def test_old_positional_motion_settings_keep_cpu_argument(self):
        from hinglish_motion.settings import MotionSettings
        settings=MotionSettings('medium','theme:archive','auto','auto','auto',30,'all',True,'auto',2)
        self.assertEqual(settings.cpu_threads,2);self.assertEqual(settings.brain_model,'qwen3:8b')

    def test_render_loop_audits_every_frame_and_saves_a_stationary_photo_warning(self):
        from hinglish_motion.render import SceneRenderer
        image=np.random.default_rng(17).integers(0,256,(144,256,3),dtype=np.uint8)
        renderer=object.__new__(SceneRenderer);renderer.load=lambda s:None;renderer.frame=lambda t,a:image
        class Writer:
            count=0
            def write(self,pixels,format):self.count+=1
        writer=Writer()
        with tempfile.TemporaryDirectory() as tmp:
            count=renderer.write_scene(writer,{'duration':2},30,audit_folder=Path(tmp))
            review=json.loads((Path(tmp)/'review.json').read_text())
            rows=json.loads((Path(tmp)/'motion-seconds.json').read_text())
            self.assertEqual(count,60);self.assertEqual(writer.count,60)
            self.assertEqual(sum(r['native_frames'] for r in rows),60);self.assertTrue(review['needs_review'])

    def test_global_track_without_enough_points_per_cell_is_not_a_crash_or_fake_local_motion(self):
        points=np.array([[20,20],[110,20],[200,20],[20,70],[110,70],[200,70],[20,120],[110,120]],np.float32).reshape(-1,1,2)
        with tempfile.TemporaryDirectory() as tmp:
            scan=ContinuousMotionScan(tmp);image=np.zeros((144,256,3),np.uint8)
            scan(image,0,0,0)
            with patch('cv2.goodFeaturesToTrack',return_value=points),patch('cv2.calcOpticalFlowPyrLK',return_value=(points,np.ones((8,1),np.uint8),np.zeros((8,1),np.float32))),patch('cv2.estimateAffinePartial2D',return_value=(np.float64([[1,0,0],[0,1,0]]),np.ones((8,1),np.uint8))):
                scan(image,1/30,1,0)
            row=scan.close()[0];self.assertIsNone(row['median']['moving_cells']);self.assertEqual(row['median']['dx'],0)

    def install(self,root):
        files={}
        for name in ['motion-graphics-editor-brain','motion-graphics-animator-brain']:
            p=root/(name+'.md');p.write_text('## Universal principles\nEverything floats.\n## N. Non-negotiables\nCamera continues.\n',encoding='utf8');files[name]=p
        return install(root,files)

    def test_new_model_reads_same_preferences_and_revision_but_general_is_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.install(root)
            data={'script':'Spoken fact'}
            with use({'profile':'cricket','documentary_style':'beneath-documentary-edit'}):
                first=inject('planner',data,root=root)
                second=inject('planner',data,root=root)
            memory=first[1]['creator_profile']['documentary_operating_memory']
            self.assertEqual(memory,second[1]['creator_profile']['documentary_operating_memory'])
            self.assertEqual(len(memory['brains']),2)
            self.assertTrue(any('after entry' in r for r in memory['user_requirements']))
            with use({'profile':'general'}):self.assertEqual(inject('planner',data,root=root),('planner',data))
            with use({'profile':'gaming'}):
                self.assertNotIn('documentary_operating_memory',inject('planner',data,root=root)[1]['creator_profile'])

    def test_switching_actual_local_model_adapter_preserves_both_brains_in_request(self):
        from hinglish_visuals.brain import OllamaBrain
        session=MagicMock();session.get.return_value.json.return_value={'models':[{'name':'small-local'},{'name':'large-local'}]}
        session.post.return_value.status_code=200
        session.post.return_value.json.return_value={'message':{'content':'{}'}}
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.install(root)
            with patch('hinglish_visuals.brain.requests.Session',return_value=session),use({'profile':'cricket','documentary_style':'crick-edit-editing-style'}):
                for name in ['small-local','large-local']:
                    brain=OllamaBrain(root,name);self.assertEqual(brain.root,root)
                    brain.json('planner',{'script':'facts'},{'type':'object'});brain.close()
            requests=[c.kwargs['json'] for c in session.post.call_args_list]
            payloads=[json.loads(r['messages'][1]['content']) for r in requests]
            self.assertEqual([r['model'] for r in requests],['small-local','large-local'])
            self.assertEqual(payloads[0]['creator_profile']['documentary_operating_memory'],payloads[1]['creator_profile']['documentary_operating_memory'])
            self.assertEqual(len(payloads[0]['creator_profile']['documentary_operating_memory']['brains']),2)

    def test_late_guidance_and_future_preferences_are_preserved_on_reinstallation(self):
        text=' '.join('technique'+str(i) for i in range(300))+' LAST TECHNIQUE'
        parts=chunks(text);self.assertEqual(' '.join(parts),text)
        self.assertTrue(all(len(p)<=700 for p in parts));self.assertIn('LAST TECHNIQUE',parts[-1])
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.install(root)
            file=root/'library/creator-profiles/documentary-memory/preferences.json';data=json.loads(file.read_text())
            data['requirements'].append('Future user correction');file.write_text(json.dumps(data))
            self.install(root);self.assertIn('Future user correction',json.loads(file.read_text())['requirements'])

    def test_different_embedding_model_cannot_compare_same_width_vectors_and_keyword_fallback_works(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);db=StyleDatabase(root/'library/creator-profiles/editing-dna.sqlite3')
            db.replace_source('beneath-documentary-edit','source',[{'kind':'continuous-motion-second','text':'foreground camera parallax',
                'vector':[1,0],'model':'old-encoder'}])
            self.assertEqual(db.search_vector('beneath-documentary-edit',[1,0],model='new-encoder'),[])
            db.close()
            with patch('hinglish_niche.style_memory._embedder',side_effect=OSError('Encoder unavailable')):
                result=search(root,'beneath-documentary-edit','camera parallax')
            self.assertEqual(result[0]['retrieval_method'],'keyword fallback')

    def test_portable_export_retains_full_brains_database_and_preferences(self):
        import zipfile
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.install(root);db=StyleDatabase(root/'library/creator-profiles/editing-dna.sqlite3')
            db.replace_source('beneath-documentary-edit','source',[{'kind':'scene','text':'camera travel'}]);db.close()
            evidence=root/'output/reference-analysis/cricket-documentaries/source';evidence.mkdir(parents=True)
            np.save(evidence/'audio-features.npy',np.zeros((4,7),np.float32))
            (evidence/'visual-features.csv').write_text('frame,seconds\n0,0\n')
            (evidence/'original.mp4').write_bytes(b'Excluded original video')
            package=export(root,root/'memory.zip')
            with zipfile.ZipFile(package) as z:
                self.assertIn('library/creator-profiles/editing-dna.sqlite3',z.namelist())
                self.assertIn('library/creator-profiles/documentary-memory/brains/motion-graphics-animator-brain.md',z.namelist())
                self.assertIn('library/creator-profiles/documentary-memory/preferences.json',z.namelist())
                self.assertIn('output/reference-analysis/cricket-documentaries/source/audio-features.npy',z.namelist())
                self.assertIn('output/reference-analysis/cricket-documentaries/source/visual-features.csv',z.namelist())
                self.assertFalse(any(n.endswith('.mp4') for n in z.namelist()))

if __name__=='__main__':unittest.main()
