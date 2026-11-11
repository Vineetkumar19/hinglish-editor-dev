import importlib.util
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from fractions import Fraction
from unittest.mock import Mock
from hinglish_app.aftereffects_adapter import cut_manifest,result_manifest
from hinglish_cut.xml_export import export_xml
from hinglish_cut.model import Media,Cut
from hinglish_app.server import AppState


class IntegrationTests(unittest.TestCase):
    def setUp(self):self.temp=tempfile.TemporaryDirectory();self.folder=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()

    def timeline(self,fps='30'):
        path=self.folder/'cuts.xml';media=Media('one',str(self.folder/'source.mp4'),5,fps,640,360,2,48000)
        export_xml(path,[Cut('one',30,60,0),Cut('one',90,120,1)],{'one':media})
        return path

    def test_ae_cut_timings_preserve_source_and_destination(self):
        manifest=cut_manifest(self.timeline());video=[c for c in manifest['clips'] if c['kind']=='video']
        self.assertEqual(manifest['duration'],2);self.assertEqual(len(video),2)
        self.assertEqual((video[0]['start'],video[0]['end'],video[0]['source_in']),(0,1,1))
        self.assertEqual((video[1]['start'],video[1]['end'],video[1]['source_in']),(1,2,3))
        self.assertEqual(manifest['width'],640)
        self.assertEqual(len([c for c in manifest['clips'] if c['kind']=='audio']),2)

    def test_ae_ntsc_timing(self):
        manifest=cut_manifest(self.timeline('30000/1001'))
        self.assertAlmostEqual(manifest['fps'],30000/1001)
        self.assertAlmostEqual(manifest['duration'],2.002)

    def test_ae_unrepresentable_effects_need_rendered_result(self):
        path=self.timeline();root=ET.parse(path);ET.SubElement(root.find('.//clipitem'),'filter');root.write(path)
        with self.assertRaises(ValueError):cut_manifest(path)
        job={'status':'complete','mode':'captions','result':{'xml_files':[str(path)],'previews':['captions.mp4']}}
        self.assertEqual(result_manifest(job)['type'],'rendered')
        job['result']['previews']=[]
        with self.assertRaises(ValueError):result_manifest(job)

    def test_ae_rejects_nonlocal_timeline_media(self):
        path=self.timeline();root=ET.parse(path);root.find('.//pathurl').text='https://attacker.example/x.mp4';root.write(path)
        with self.assertRaises(ValueError):cut_manifest(path)

    def test_licensed_runtime_blocks_jobs_before_starting_engine(self):
        license=Mock();license.ensure.side_effect=ValueError('Subscription required.')
        license.edition='desktop'
        state=AppState(self.folder,license_client=license)
        with self.assertRaisesRegex(ValueError,'Subscription required'):state.create_job({'mode':'clean','source_paths':[]})
        self.assertEqual(state.jobs,{})

    def test_resolve_adapter_imports_new_timeline_and_handles_failure(self):
        file=Path(__file__).resolve().parents[1]/'editor_plugins/davinci-resolve-studio/Hinglish Editor.py'
        spec=importlib.util.spec_from_file_location('resolve_panel',file);panel=importlib.util.module_from_spec(spec);spec.loader.exec_module(panel)
        project=Mock();project.GetMediaPool().ImportTimelineFromFile.return_value.GetName.return_value='New generated timeline'
        self.assertEqual(panel.import_result(project,{'xml_files':['cuts.xml']}),['New generated timeline'])
        project.GetMediaPool().ImportTimelineFromFile.return_value=None
        with self.assertRaises(RuntimeError):panel.import_result(project,{'xml_files':['cuts.xml']})

    def test_resolve_media_selection_uses_selected_paths(self):
        file=Path(__file__).resolve().parents[1]/'editor_plugins/davinci-resolve-studio/Hinglish Editor.py'
        spec=importlib.util.spec_from_file_location('resolve_panel',file);panel=importlib.util.module_from_spec(spec);spec.loader.exec_module(panel)
        project=Mock();one=Mock();one.GetClipProperty.return_value='clip.mp4';project.GetMediaPool().GetSelectedClips.return_value={1:one,2:one}
        self.assertEqual(panel.selected_media(project),['clip.mp4'])

    def test_shared_runtime_checks_the_requested_edition(self):
        desktop=Mock();desktop.edition='desktop';plugins=Mock();plugins.edition='plugins'
        desktop.ensure.side_effect=ValueError('Desktop access required.')
        plugins.ensure.side_effect=ValueError('Plugin access required.')
        state=AppState(self.folder,license_client=desktop);state.license_clients['plugins']=plugins
        with self.assertRaisesRegex(ValueError,'Plugin access required'):
            state.create_job({'mode':'clean','host':'premiere'})
        plugins.ensure.assert_called_once_with('premiere');desktop.ensure.assert_not_called()
        with self.assertRaisesRegex(ValueError,'Desktop access required'):
            state.create_job({'mode':'clean'})
        desktop.ensure.assert_called_once_with('standalone')
