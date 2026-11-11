import unittest


class QwenHyperframesProjectTests(unittest.TestCase):
    def test_exact_caption_binding_does_not_change_model_graphics_or_animation(self):
        from tools.qwen_hyperframes_project import bind_captions
        files={'index.html':'ROOT','compositions/scene1.html':'<div id="graphic">ART</div><p data-script-caption="metadata"></p><script>ANIMATION</script>',
               'compositions/scene2.html':'<p data-script-caption="metadata"></p>','compositions/scene3.html':'<p data-script-caption="metadata"></p>'}
        result=bind_captions(files,['One statement.','Exact source words,','but unfinished.'])
        self.assertEqual(result['index.html'],'ROOT')
        self.assertEqual(result['compositions/scene1.html'],'<div id="graphic">ART</div><p data-script-caption>One statement.</p><script>ANIMATION</script>')
    def test_generated_code_cannot_escape_project_or_make_network_calls(self):
        from tools.qwen_hyperframes_project import validate_files
        for files in ({'../outside.html':'x'},{'index.html':'<script>fetch("https://example.com")</script>'}):
            with self.assertRaises(ValueError):validate_files(files)

    def test_model_code_is_not_replaced_with_a_typed_shape_template(self):
        from tools.qwen_hyperframes_project import checked_source
        html='<template><div id="root">authored</div><script>const tl=gsap.timeline({paused:true}); window.__timelines["scene1"]=tl;</script></template>'
        self.assertEqual(checked_source(html),html)
        with self.assertRaises(ValueError):checked_source('<iframe src="file:///private"></iframe>')


if __name__=='__main__':unittest.main()
