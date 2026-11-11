import copy
import unittest
from hinglish_motion.object_film import validate,graph_for

def scene():
    keys=[[0,0,0,1,0,1],[1,.1,0,1,0,1]]
    return {'background':'#101318','accent':'#ffffff','camera':[[0,0,0,1,0],[1,0,0,1.1,0]],'objects':[{'asset':name,'box':[.1,.1,.3,.3],'keys':copy.deepcopy(keys)} for name in ('photo0','camera','clock')],'effects':[]}

class ObjectFilmTests(unittest.TestCase):
    def test_identical_colour_is_detected_before_visual_delivery(self):
        from hinglish_motion.object_recovery import contrast
        self.assertEqual(contrast('#1a1a1a','#1a1a1a'),1)
        self.assertGreater(contrast('#ffffff','#1a1a1a'),4.5)
    def test_requires_camera_and_independent_nontext_motion(self):
        p={'title':'Test','photo_queries':['night street'],'scenes':[scene()]}
        validate(p,1,{'camera','clock'})
        p['scenes'][0]['camera'][-1][3]=1
        with self.assertRaisesRegex(ValueError,'camera'):validate(p,1,{'camera','clock'})
    def test_camera_changes_world_without_moving_caption(self):
        s=scene();g=graph_for(s,'Exact words stay here.',{n:'data:image/svg+xml;base64,PHN2Zy8+' for n in ('photo0','camera','clock')},8)
        self.assertEqual(sum(n.get('parent')=='camera-world' for n in g['nodes']),3)
        camera=g['nodes'][0];self.assertNotEqual(camera['keys'][0]['scale'],camera['keys'][-1]['scale'])
        cap=g['nodes'][-1];self.assertNotIn('parent',cap);self.assertEqual(cap['text'],'Exact words stay here.')
    def test_native_adapter_keeps_authored_graph(self):
        from hinglish_motion.native_engines import scene_graph
        g=graph_for(scene(),'Exact words.',{n:'data:image/svg+xml;base64,PHN2Zy8+' for n in ('photo0','camera','clock')},8)
        actual=scene_graph({'template':'object_motion','duration':8,'data':{'graph':g}},360,640,30)
        self.assertEqual(actual,g)

if __name__=='__main__':unittest.main()
