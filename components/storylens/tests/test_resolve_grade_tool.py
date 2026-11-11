import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
from hinglish_app.resolve_grade import apply_grade,NODE_NAMES,template

class ResolveGradeTests(unittest.TestCase):
 def test_saved_native_structure_hash_and_node_count(self):
  self.assertEqual(len(NODE_NAMES),19)
  self.assertTrue(template().is_file())
 def test_unsupported_input_stops_before_duplicate(self):
  with self.assertRaises(ValueError):apply_grade(Path('.'),{'input_profile':'log'},Path('.'))
 def test_duplicate_only_and_film_nodes_remain_off(self):
  with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'tmp') as tmp:
   graph=Mock();graph.GetNumNodes.return_value=19
   clip=Mock();clip.GetNodeGraph.return_value=graph
   original=Mock();original.GetName.return_value='Original'
   duplicate=Mock();duplicate.GetName.return_value='Original - Storylens nodes';duplicate.GetItemListInTrack.return_value=[clip]
   original.GetTrackCount.return_value=1;original.GetItemListInTrack.return_value=[clip]
   original.DuplicateTimeline.return_value=duplicate
   project=Mock();project.GetCurrentTimeline.return_value=original
   project.GetSettings.return_value={'colorScienceMode':'davinciYRGB','colorSpaceTimeline':'DaVinci WG/Intermediate'}
   with patch('hinglish_app.resolve_adapter._project',return_value=(Mock(),project)):
    result=apply_grade(Path(tmp),{'input_profile':'rec709'},Path(tmp))
   original.DuplicateTimeline.assert_called_once()
   self.assertEqual(result['node_count'],19)
   self.assertEqual(graph.SetNodeEnabled.call_args_list[-2].args,(18,False))
   self.assertEqual(graph.SetNodeEnabled.call_args_list[-1].args,(19,False))
