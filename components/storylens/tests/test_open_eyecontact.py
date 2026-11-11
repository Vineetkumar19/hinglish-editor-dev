import unittest
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import patch,Mock
import numpy as np
from hinglish_eyecontact.open_gaze import Corrector, anchor_maps, eye_openness, solve_angles


class OpenEyeContactTests(unittest.TestCase):
    def test_cuda_health_reports_the_gpu_instead_of_cpu(self):
        from hinglish_eyecontact import open_gaze
        gpu=SimpleNamespace(name='NVIDIA RTX test')
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(open_gaze,'configuration',return_value={'provider':'CUDAExecutionProvider'}),patch('hinglish_eyecontact.maxine.gpus',return_value=[gpu]):
                health=open_gaze.doctor(folder)
                self.assertIs(health.gpu,gpu)
                self.assertIn('CUDA',health.label)

    def test_anchor_offsets_keep_the_published_x_y_order(self):
        points = np.array([[10,20],[12,18],[18,18],[20,20],[18,22],[12,22]])
        maps = anchor_maps(points,(0,0),(48,64))
        self.assertEqual(maps.shape,(1,48,64,12))
        np.testing.assert_array_equal(maps[0,20,10,:2],[0,0])
        np.testing.assert_array_equal(maps[0,21,12,:4],[2,1,0,3])

    def test_angle_solver_accounts_for_model_axis_direction(self):
        jacobian = np.array([[0,-.2],[.1,0]],np.float32)
        np.testing.assert_allclose(solve_angles(jacobian,[2,1],20),[10,-10])
        np.testing.assert_allclose(solve_angles(jacobian,[20,10],20),[20,-20])

    def test_unstable_or_invalid_response_leaves_the_eye_alone(self):
        self.assertIsNone(solve_angles(np.zeros((2,2)),[1,1],20))
        self.assertIsNone(solve_angles(np.array([[float('nan'),0],[0,1]]),[1,1],20))

    def test_closed_eye_is_detected_before_redirection(self):
        closed = [[0,0],[3,0],[7,0],[10,0],[7,0],[3,0]]
        opened = [[0,0],[3,-2],[7,-2],[10,0],[7,2],[3,2]]
        self.assertEqual(eye_openness(closed),0)
        self.assertGreater(eye_openness(opened),.25)

    def test_no_face_keeps_exact_pixels_and_resets_temporal_state(self):
        engine = object.__new__(Corrector)
        engine.np = np
        engine.mp = SimpleNamespace(Image=lambda **kwargs:kwargs,ImageFormat=SimpleNamespace(SRGB=1))
        engine.detector = SimpleNamespace(detect_for_video=lambda *_:SimpleNamespace(face_landmarks=[]))
        engine.stats = dict(frames=0)
        engine.last_ms = -1
        engine.smooth = {'L':np.ones(2)}
        image = np.full((100,100,3),128,np.uint8)
        self.assertIs(engine.correct(image,0),image)
        self.assertEqual(engine.smooth,{})
        self.assertEqual(engine.stats['frames'],1)

    def test_cached_export_keeps_actual_corrected_frame_counts(self):
        from hinglish_eyecontact import pipeline
        from hinglish_eyecontact.settings import EyeSettings
        root=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(dir=root/'tmp') as folder:
            folder=Path(folder);source=folder/'source.mp4';source.write_bytes(b'fixture')
            settings=EyeSettings(backend='hsu_onnx')
            target=folder/('source_EYECONTACT_'+pipeline.media_key(source,settings)+'.mp4')
            target.write_bytes(b'cached-export')
            target.with_suffix('.mp4.stats.json').write_text(json.dumps({'corrected_frames':17}))
            info=SimpleNamespace(container_suffix='.mp4',duration=1,frames=30)
            engine=Mock()
            with patch.object(pipeline,'probe',return_value=info):
                _,_,stats=pipeline.correct(source,folder,engine,settings,[],lambda _:None)
            self.assertEqual(stats['corrected_frames'],17)
            self.assertTrue(stats['reused']);engine.assert_not_called()


if __name__ == '__main__':
    unittest.main()
