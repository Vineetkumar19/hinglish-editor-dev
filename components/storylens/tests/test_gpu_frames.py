import sys, unittest
from types import SimpleNamespace
from unittest.mock import patch


class GpuFramePolicyTests(unittest.TestCase):
    def test_readonly_decoder_pixels_are_copied_before_tensor_upload(self):
        import numpy as np
        from hinglish_cut.gpu_frames import CudaFrames
        pixels=np.zeros((2,2,3),np.uint8);pixels.flags.writeable=False
        class Tensor:
            ndim=3;shape=(2,2,3)
            def permute(self,*a):return self
            def unsqueeze(self,*a):return self
            def float(self):return self
        def upload(array,device):
            self.assertTrue(array.flags.writeable);self.assertEqual(device,'cuda');return Tensor()
        gpu=object.__new__(CudaFrames);gpu.torch=SimpleNamespace(as_tensor=upload);gpu.device='cuda'
        gpu.upload(pixels)
        self.assertFalse(pixels.flags.writeable)
    def test_transparent_exports_stop_before_creating_a_software_movie(self):
        import tempfile
        from pathlib import Path
        from hinglish_captions.renderer import render_overlay
        from hinglish_visuals.render import popup_clip,cutout_clip
        from hinglish_zoom.overlays import add_overlays
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'tmp') as folder:
            target=Path(folder)/'blocked.mov'
            with self.assertRaisesRegex(RuntimeError,'CPU fallback is disabled'):
                render_overlay(target,[],256,144,1,device='cuda')
            with self.assertRaisesRegex(RuntimeError,'CPU fallback is disabled'):
                popup_clip(None,None,1,256,144,30,target,device='cuda')
            with self.assertRaisesRegex(RuntimeError,'CPU fallback is disabled'):
                cutout_clip(None,1,256,144,30,target,device='cuda')
            with self.assertRaisesRegex(RuntimeError,'CPU fallback is disabled'):
                add_overlays(None,folder,None,None,[{'overlay':'soft_flash'}],device='cuda')
            self.assertFalse(target.exists())
            self.assertFalse((Path(folder)/'transitions').exists())

    def test_gpu_visual_requests_use_the_gpu_implementation(self):
        from hinglish_visuals.render import still_clip,video_clip
        with patch('hinglish_visuals.gpu_render.still',return_value='gpu-still') as still:
            self.assertEqual(still_clip('source.png',1,256,144,30,'out.mp4',device='cuda'),'gpu-still')
            self.assertEqual(still.call_args.kwargs['device'],'cuda')
        with patch('hinglish_visuals.gpu_render.video',return_value='gpu-video') as video:
            self.assertEqual(video_clip('source.mp4',0,1,256,144,30,'out.mp4',device='cuda'),'gpu-video')
            self.assertEqual(video.call_args.kwargs['device'],'cuda')

    def test_static_gpu_graphic_remains_a_still_in_the_editable_xml(self):
        import xml.etree.ElementTree as ET
        from hinglish_shorts.xml import _file
        root=ET.Element('clipitem')
        file=_file(root,'static','graphic.png',30,60,1080,1920)
        self.assertEqual(file.findtext('stillframe'),'TRUE')
        self.assertEqual(file.findtext('duration'),'60')

    def test_missing_cuda_fails_before_any_cpu_frame_processing(self):
        from hinglish_cut.gpu_frames import CudaFrames
        fake = SimpleNamespace(cuda=SimpleNamespace(is_available=lambda: False))
        with patch.dict(sys.modules, {'torch': fake}):
            with self.assertRaisesRegex(RuntimeError, 'CPU fallback is disabled'):
                CudaFrames()

    def test_zoom_box_preserves_center_and_zoom_extent(self):
        from hinglish_cut.gpu_frames import zoom_box
        self.assertEqual(zoom_box(200, 100, 1), (0, 0, 200, 100))
        self.assertEqual(zoom_box(200, 100, 2), (50, 25, 150, 75))
        with self.assertRaises(ValueError): zoom_box(200, 100, 0)

    def test_alpha_software_export_is_rejected_only_by_strict_owner_policy(self):
        from hinglish_cut.compute_policy import require_gpu_implementation
        with patch('hinglish_cut.model_preferences.preferences', return_value={'heavy_workloads_gpu_only': True}):
            with self.assertRaisesRegex(RuntimeError, 'transparent'):
                require_gpu_implementation('.', 'transparent caption export', False)
            require_gpu_implementation('.', 'GPU frame processing', True)
        with patch('hinglish_cut.model_preferences.preferences', return_value={}):
            require_gpu_implementation('.', 'transparent caption export', False)


if __name__ == '__main__': unittest.main()
