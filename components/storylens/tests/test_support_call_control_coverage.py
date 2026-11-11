import unittest
from hinglish_app.support_call_controls import controls, form_fields, select_fields, search_controls

class ControlCoverageTests(unittest.TestCase):
    def test_detached_broll_dialog_belongs_to_broll_only(self):
        self.assertIn('brollOptionsPerMoment', {r['id'] for r in select_fields('broll')})
        self.assertNotIn('brollOptionsPerMoment', {r['id'] for r in select_fields('clean')})
        self.assertIn('usePexels', {r['id'] for r in form_fields('broll')})
        self.assertNotIn('pexelsKey', {r['id'] for r in form_fields('broll')})

    def test_native_sections_do_not_leak_into_unrelated_tool(self):
        self.assertFalse(select_fields('templateImport'))
        self.assertIn('animationPresetTarget', {r['id'] for r in select_fields('animationPresets')})
        self.assertNotIn('animationPresetTarget', {r['id'] for r in select_fields('nativeCaptions')})
        self.assertIn('captionStyle', {r['id'] for r in select_fields('nativeCaptions')})

    def test_empty_dynamic_select_is_not_missing(self):
        handoff={r['id']:r for r in select_fields('editorLink')}
        self.assertTrue(handoff['source']['dynamic'])
        self.assertTrue(handoff['kind']['dynamic'])
        self.assertEqual(handoff['kind']['label'],'Send')
        self.assertIn('resolveBuiltinLut', {r['id'] for r in select_fields('colorGrade')})

    def test_cross_feature_nested_option_is_found_without_active_parent(self):
        rows=search_controls('What is Hyper Frame?', 'clean')
        matches=[r for r in rows if r['tool']=='motion']
        self.assertEqual(matches[0]['label'],'Render engine')
        self.assertEqual(matches[0]['matched_options'][0]['value'],'hyperframes')
        self.assertEqual(search_controls('What is Quasar Pineapple?', 'clean'),())

    def test_live_dropdown_choices_override_static_choices(self):
        fields=[{'id':'motionEngine','label':'Render engine','disabled':True,
                 'options':[{'value':'new','label':'New renderer','disabled':False}]}]
        rows=search_controls('Hyperframes','motion',fields=fields)
        self.assertFalse(any(r['tool']=='motion' and r.get('id')=='motionEngine' for r in rows))
        rows=search_controls('New renderer','motion',fields=fields)
        self.assertTrue(rows[0]['disabled'])
        self.assertTrue(rows[0]['live'])

    def test_explicit_feature_prevents_generic_option_hijack(self):
        rows=search_controls('What options are in Render engine in Motion Graphics?', 'captions')
        self.assertTrue(rows)
        self.assertTrue(all(row['tool']=='motion' for row in rows))
        self.assertEqual(rows[0]['id'],'motionEngine')
        rows=search_controls('Explained Auto Connector Feature','captions')
        self.assertFalse(any(row.get('matched_options') for row in rows))
        self.assertFalse(any(row['tool'] in ('aivideo','thumbnail') for row in rows))
        rows=search_controls('What is Hyperframes?','clean')
        self.assertTrue(any(row['tool']=='motion' for row in rows))
        self.assertEqual(search_controls('What is Auto?','clean'),())

    def test_voice_and_schedule_do_not_inherit_host_page_controls(self):
        self.assertNotIn('Import test recording', {row[0] for row in controls('storylensCall')})
        self.assertNotIn('Choose thumbnail', {row[0] for row in controls('scheduledPosts')})
        self.assertFalse(select_fields('storylensCall'))
        self.assertFalse(select_fields('scheduledPosts'))

    def test_source_field_constraints_are_known_without_values(self):
        row=next(r for r in form_fields('colorGrade') if r['id']=='gradeSaturation')
        self.assertEqual(row['min'],'0.8')
        self.assertEqual(row['max'],'1.2')
        self.assertNotIn('value',row)

if __name__=='__main__': unittest.main()
