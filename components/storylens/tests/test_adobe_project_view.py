import unittest
import time
from unittest.mock import patch

from hinglish_app.adobe_project_view import restore_positions


class ProjectScrollTests(unittest.TestCase):
    def test_thumb_restore_uses_captured_geometry_and_rejects_unknown_position(self):
        from hinglish_app.adobe_project_view import thumb_position
        self.assertEqual(thumb_position(.75,(10,20,30,220),(10,20,30,40),'vertical'),(20,165))
        self.assertIsNone(thumb_position(None,(10,20,30,220),(10,20,30,40),'vertical'))
        self.assertIsNone(thumb_position(2,(10,20,30,220),(10,20,30,40),'vertical'))

    def test_invalidated_native_scroll_controls_are_reacquired_after_paste(self):
        from hinglish_app import adobe_project_view as view
        snapshot={'project_id':r'D:\recovery.aep','captured':time.time()}
        def stale():raise OSError('Member not found')
        cached={'identity':{'project_id':snapshot['project_id']},'read':stale,'write':lambda *_:None}
        class Reacquired(Exception):pass
        with patch.object(view.sys,'platform','win32'),patch.object(view,'_last_capture',cached),patch.object(view,'native_runtime',side_effect=Reacquired):
            with self.assertRaises(Reacquired):view.project_view(snapshot['project_id'],snapshot)

    def test_only_native_reset_to_top_is_repaired(self):
        writes = []
        restored = restore_positions({'vertical': 315.0, 'horizontal': 0.0},
                                     {'vertical': 0.0, 'horizontal': 0.0},
                                     lambda *v: writes.append(v))
        self.assertEqual(restored, ['vertical'])
        self.assertEqual(writes, [('vertical', 315.0)])

    def test_new_user_position_is_kept(self):
        writes = []
        self.assertEqual(restore_positions({'vertical': 315.0}, {'vertical': 125.0},
                                          lambda *v: writes.append(v)), [])
        self.assertEqual(writes, [])

    def test_missing_or_invalid_axis_does_not_write(self):
        writes = []
        restore_positions({'vertical': float('nan'), 'horizontal': 50.0},
                          {'vertical': 0.0}, lambda *v: writes.append(v))
        self.assertEqual(writes, [])

    def test_delayed_native_repaint_reset_is_restored_without_a_background_listener(self):
        from hinglish_app.adobe_project_view import settle_positions
        positions={'vertical':315.0};reads=iter([315.0,0.0,315.0]);writes=[]
        def read():positions['vertical']=next(reads,positions['vertical']);return dict(positions)
        def write(axis,value):writes.append((axis,value));positions[axis]=value
        result=settle_positions({'vertical':315.0},read,write,lambda _:None)
        self.assertEqual(writes,[('vertical',315.0)]);self.assertTrue(result['ok'])

    def test_a_new_nonzero_user_scroll_is_never_overridden_during_settle(self):
        from hinglish_app.adobe_project_view import settle_positions
        writes=[]
        result=settle_positions({'vertical':315.0},lambda:{'vertical':120.0},lambda *v:writes.append(v),lambda _:None)
        self.assertEqual(writes,[]);self.assertTrue(result['ok'])


if __name__ == '__main__':
    unittest.main()
