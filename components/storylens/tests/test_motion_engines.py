"""Engine selection and adapter contracts, without GPU jobs or video rendering."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from hinglish_motion.engines import selected_engine,validate_style
from hinglish_motion.native_engines import scene_graph,NativeSceneRenderer
from hinglish_motion.settings import MotionSettings
from hinglish_app.assistant_plan import job_payload,schema,validate_plan


class EngineSelection(unittest.TestCase):
    def test_explicit_engine_and_script_content(self):
        self.assertEqual(selected_engine('Make this using Motion Canvas. SCRIPT: Remotion is a tool.','remotion'),'motion-canvas')
        self.assertEqual(selected_engine('Make animation. SCRIPT: Use Hyperframes today.','remotion'),'remotion')
        with self.assertRaises(ValueError):selected_engine('', 'fake')

    def test_legacy_settings_keep_engine(self):
        self.assertEqual(MotionSettings().engine,'hyperframes')
        self.assertEqual(MotionSettings(engine='motion-canvas').engine,'motion-canvas')
        with self.assertRaises(ValueError):MotionSettings(engine='fake')

    def test_assistant_engine_passes_through(self):
        self.assertEqual(job_payload({'tool':'motion','options':{}},[])['motion_engine'],'remotion')
        for engine in ('remotion','motion-canvas','hyperframes'):
            self.assertEqual(job_payload({'tool':'motion','options':{'motion_engine':engine}},[])['motion_engine'],engine)

    def test_unknown_style_never_changes_renderer(self):
        with self.assertRaisesRegex(ValueError,'style unavailable'):validate_style('remotion','theme:orbit')
        validate_style('hyperframes','theme:orbit')

    def test_scene_content_and_clock(self):
        scene={'template':'motion_title','duration':4,'data':{'title':'Clear motion','label':'Every original word stays here.'}}
        for w,h in ((360,640),(640,360),(360,360)):
            graph=scene_graph(scene,w,h,25)
            self.assertEqual((graph['width'],graph['height'],graph['duration'],graph['fps']),(w,h,4,25))
            self.assertIn('Every original word stays here.', ' '.join(n.get('text','').replace('\n',' ') for n in graph['nodes']))
            for n in graph['nodes']:
                self.assertGreaterEqual(n['x'],0);self.assertLessEqual(n['x']+n['w'],w+.01)

    def test_reference_template_never_silently_substituted(self):
        with self.assertRaisesRegex(ValueError,'style unavailable'):scene_graph({'template':'archive_board','duration':3,'data':{}},360,640,30)

    def test_missing_image_fails_clearly(self):
        with self.assertRaisesRegex(ValueError,'asset unavailable'):scene_graph({'template':'asset_hero','duration':3,'data':{'title':'Photo','assets':[{'src':'missing.png'}]}},360,640,30)

    def test_native_factory_has_no_legacy_browser(self):
        from hinglish_motion.render import SceneRenderer
        with patch('playwright.sync_api.sync_playwright',side_effect=AssertionError('A build check must not launch Chrome')):
            renderer=SceneRenderer(360,640,engine='remotion')
            self.assertIsInstance(renderer,NativeSceneRenderer)
            renderer.close()

    def test_transparent_export_fails_before_render(self):
        renderer=NativeSceneRenderer(360,640,'motion-canvas')
        with tempfile.TemporaryDirectory() as tmp,patch.object(renderer,'_command',side_effect=AssertionError('must not render')):
            with self.assertRaisesRegex(ValueError,'format unavailable'):renderer.render({'mode':'overlay'},Path(tmp)/'out.mov',30)


if __name__=='__main__':unittest.main()
