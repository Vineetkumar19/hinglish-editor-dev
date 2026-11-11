import json
import tempfile
import unittest
from pathlib import Path

from hinglish_niche.documentary import ANIMATIONS, apply_style_settings, catalogue
from hinglish_niche.profiles import Profiles


class DocumentarySetTests(unittest.TestCase):
    def test_switching_sets_keeps_reference_rules_isolated_and_general_unchanged(self):
        with tempfile.TemporaryDirectory() as root:
            folder=Path(root)/'library/creator-profiles';folder.mkdir(parents=True)
            for key,rule in [('beneath-documentary-edit','Road camera travels right'),
                             ('crick-edit-editing-style','New reference pacing')]:
                (folder/(key+'.json')).write_text(json.dumps({'name':key,'rules':[rule]}),encoding='utf-8')
            profiles=Profiles(root)
            self.assertEqual(profiles.context('cricket')['documentary_reference']['rules'],['Road camera travels right'])
            profiles.save('cricket',{'documentary_style':'crick-edit-editing-style'})
            self.assertEqual(Profiles(root).context('cricket')['documentary_reference']['rules'],['New reference pacing'])
            profiles.save('cricket',{'documentary_style':'beneath-documentary-edit'})
            self.assertEqual(profiles.context('cricket')['documentary_reference']['rules'],['Road camera travels right'])
            for profile in ['general','gaming']:
                self.assertNotIn('documentary_reference',profiles.context(profile))
            self.assertEqual(len(catalogue(root)),2)
            with self.assertRaises(ValueError):profiles.save('gaming',{'documentary_style':'beneath-documentary-edit'})
            with self.assertRaises(ValueError):profiles.save('cricket',{'documentary_style':'../../outside'})

    def test_preset_selects_actual_motion_and_does_not_replace_unrelated_graphics(self):
        root=Path(__file__).resolve().parents[1]
        for setting in ANIMATIONS:
            scene={'template':'archive_board','data':{'archive_style':'map','archive_variant':0,'archive_composition':'road-travel','label':'Existing words'}}
            style='card:card_beneath_'+setting['id'].replace('-','_')
            apply_style_settings(root,style,scene)
            self.assertEqual(scene['data']['archive_composition'],setting['id'])
            self.assertEqual(scene['data']['archive_style'],setting['archive_style'])
            self.assertEqual(scene['data']['archive_variant'],setting['archive_variant'])
            self.assertEqual(scene['data']['label'],'Existing words')
            other={'template':'headline','data':{'title':'Keep the headline'}}
            apply_style_settings(root,style,other)
            self.assertEqual(other,{'template':'headline','data':{'title':'Keep the headline'}})

    def test_beneath_auto_selection_stays_within_the_five_saved_animations(self):
        root=Path(__file__).resolve().parents[1]
        scene={'template':'archive_board','data':{'archive_style':'map','archive_composition':'orbit'}}
        apply_style_settings(root,'card:card_cricket_documentary_user',scene)
        self.assertEqual(scene['data']['archive_composition'],'road-travel')
        self.assertEqual(len(ANIMATIONS),5)


if __name__=='__main__':unittest.main()
