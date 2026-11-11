import base64
import json
from pathlib import Path
import unittest

from hinglish_app.support_call_actions import interpret
from hinglish_app.support_call_controls import (
    _OTHER, _STATIC, _WORKFLOW, _description, _read, _routes,
    control_guidance, decode_snapshot,
)
from hinglish_app.support_call_knowledge import FEATURES


class SupportCallControlTests(unittest.TestCase):
    def test_shared_button_names_follow_explicit_tool(self):
        self.assertIn('resets the intro clock',
                      control_guidance('What does Stop do in Intro Create?', 'cinematic'))
        self.assertIn('current extraction',
                      control_guidance('Cinematic Footage में Stop बटन क्या करता है?', 'introCreate'))
        self.assertIn('saved test calls', control_guidance('What does Refresh do in Call QA?', 'voiceover'))

    def test_conditional_control_can_be_explained_without_opening_it(self):
        answer = control_guidance('What does Resume interrupted extraction do in Cinematic Footage?', 'clean')
        self.assertIn('incomplete extraction', answer)
        self.assertNotIn('Enabled', answer)

    def test_generated_control_uses_live_type_and_state(self):
        value = base64.b64encode(json.dumps([
            ['My edit · part 2', False, 'scheduled-item'],
            ['Invalid', 'false'],
        ]).encode()).decode()
        answer = control_guidance('What does My edit part 2 do?', 'scheduledPosts', decode_snapshot(value))
        self.assertIn('opens its details for review', answer)
        self.assertIn('Disabled', answer)
        self.assertNotIn('Invalid', answer)

    def test_caption_card_uses_selection_behavior(self):
        self.assertIn('Chooses this named caption style',
                      control_guidance('What does Caption 08 Kinetic Gold do?', 'captions'))

    def test_named_hinglish_command_keeps_label_and_tool(self):
        reply = interpret(Path.cwd(), 'Intro Create में Play Intro बटन दबाओ', 'hi', 'clean')
        self.assertEqual(reply.action, {'type': 'click_button', 'label': 'Play Intro', 'tool': 'introCreate'})

    def test_static_controls_on_registered_surfaces_have_a_purpose(self):
        scopes = {}
        for tool in FEATURES:
            file = _OTHER.get(tool) or _routes().get(tool) or 'index.html'
            scopes.setdefault(_STATIC / file, []).append(tool)
        scopes[_STATIC / 'editor-panel.html'].extend(('clean', 'broll', 'sound', 'visuals'))
        for name, tool in (('intro-create.html', 'introCreate'), ('auto-captions.html', 'captions'),
                           ('auto-caption-2.html', 'captions'), ('publisher.html', 'preparePost'),
                           ('cricket-desk.html', 'cricketDesk')):
            scopes[_STATIC / name] = [tool]
        for tool, folder in (('cricketDesk', 'cricket-meme-inbox'), ('gamingDesk', 'gaming-meme-inbox')):
            page = _WORKFLOW / folder / 'index.html'
            if page.is_file():
                scopes[page] = [tool]
        for page, tools in scopes.items():
            for name, title, handler in _read(page):
                with self.subTest(page=page.parent.name + '/' + page.name, label=name):
                    self.assertTrue(any(_description(name, title, handler, tool) for tool in tools))


if __name__ == '__main__':
    unittest.main()
