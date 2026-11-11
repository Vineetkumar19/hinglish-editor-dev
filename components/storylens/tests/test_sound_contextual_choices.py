"""The new director must keep context while allowing justified recurring motifs."""
from pathlib import Path
import tempfile
import unittest

from hinglish_sound.acoustic import project_palette,palette_query,reusable,source_identity
from hinglish_sound.layers import plan_layers
from hinglish_sound.pipeline import _rank


class SoundContextualChoicesTests(unittest.TestCase):
    def test_palette_keeps_project_specific_character_and_does_not_search_exclusions(self):
        p=project_palette(dict(identity='Dry comic frustration',textures=['short detuned plucks','muted low stings'],
                               avoid=['bright notification bells','literal horses']),'comedic')
        q=palette_query(p)
        self.assertIn('detuned plucks',q)
        self.assertNotIn('horses',q)
        self.assertNotIn('notification',q)
        self.assertEqual(p['delivery'],'comedic')

    def test_unrelated_context_cannot_copy_the_same_source(self):
        history={'file':[dict(group_id='setup',role='detail',type='poke')]}
        ok,why=reusable('file',dict(group_id='punchline',role='detail',type='poke'),history)
        self.assertFalse(ok)
        self.assertIn('narrative reason',why)

    def test_deliberate_motif_needs_identity_reason_and_acoustic_role(self):
        original=dict(group_id='list-1',type='poke',role='detail',reuse_key='list-tick',reuse_reason='A recurring count in the same escalating list')
        later=dict(original,group_id='list-2')
        history={'file':[original]}
        self.assertTrue(reusable('file',later,history)[0])
        for change in ({'reuse_reason':''},{'reuse_key':'different'},{'role':'tail'},{'group_id':'list-1'}):
            self.assertFalse(reusable('file',dict(later,**change),history)[0])

    def test_rename_does_not_hide_an_exact_duplicate_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            a=Path(tmp)/'click.wav';b=Path(tmp)/'renamed.wav';c=Path(tmp)/'different.wav'
            a.write_bytes(b'exact stored audio bytes');b.write_bytes(a.read_bytes());c.write_bytes(b'other source')
            self.assertEqual(source_identity(a),source_identity(b))
            self.assertNotEqual(source_identity(a),source_identity(c))

    def test_explicit_model_rejection_has_no_fallback_candidate(self):
        self.assertEqual(_rank(-1,6),[])

    def test_contextual_speech_authors_layers_and_retains_legacy_opt_in(self):
        event=dict(id='word-1',time=2.,end=2.3,kind='speech',precision='speech',word='Again',line_text='Again, it failed.',word_index=0,line_id=1)
        class Brain:
            def ask(self,system,data,schema,**kw):
                self.system,self.data,self.schema=system,data,schema
                return {'layers':[dict(event_id='word-1',role='detail',type='awkward',
                    intent='brief downward comic brass sting',why='The repeated failure lands here',strength=2,
                    offset=.02,duration=.4,level_db=-10,reuse_key='',reuse_reason='')]}
        brain=Brain()
        rows=plan_layers(brain,[event],'A dry failure joke','comedic',2,['awkward','poke','foley','ambience'],
            composition=dict(seconds=5,sound_palette=dict(identity='dry comic frustration')))
        self.assertIn('layers',brain.schema['properties'])
        self.assertIn('dry comic frustration',str(brain.data))
        self.assertEqual(rows[0]['word'],'Again')
        self.assertEqual(rows[0]['target'],2.02)
        self.assertEqual(rows[0]['intent'],'brief downward comic brass sting')
        class Legacy(Brain):
            def ask(self,system,data,schema,**kw):
                self.schema=schema
                return {'motifs':[dict(event_id='word-1',motif='list_tick',why='A saved list motif',strength=2)]}
        old=Legacy()
        legacy=plan_layers(old,[event],'A list','comedic',2,['poke','cute'],composition=dict(seconds=5,authoring='legacy_motifs'))
        self.assertIn('motifs',old.schema['properties'])
        self.assertTrue(legacy)


if __name__=='__main__':unittest.main()
