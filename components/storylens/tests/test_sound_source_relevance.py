"""Authoritative source subjects must not be replaced by CLAP guesses."""
import unittest
from types import SimpleNamespace


def asset(name,text=''):
    return SimpleNamespace(name=name,text=text)


class SourceRelevanceTests(unittest.TestCase):
    def test_walking_cannot_use_keyboard_combat_or_designed_impacts(self):
        from hinglish_sound.relevance import source_matches
        for name in ('Typing on a laptop keyboard','Training with punching bag','Body cutting impact',
                     'Cinematic transition swoosh heartbeat trailer','Spy hit'):
            self.assertFalse(source_matches(asset(name),'foley','Walking through mud')[0],name)
        self.assertTrue(source_matches(asset('Footsteps in the forest ground'),'foley','Stepping on mud')[0])

    def test_natural_water_cannot_use_soda_or_a_storm_riser(self):
        from hinglish_sound.relevance import source_matches
        for name in ('Pouring soda in a glass','Storm Riser','Underwater cinematic drone'):
            self.assertFalse(source_matches(asset(name),'ambience','Water cascading over rocks')[0],name)
        self.assertTrue(source_matches(asset('Waterfall water flowing'),'ambience','Water cascading over rocks')[0])

    def test_delivery_label_is_not_an_acoustic_search_intent(self):
        from hinglish_sound.relevance import delivery_label_only
        self.assertTrue(delivery_label_only('Normal, reflective','normal reflective'))
        self.assertFalse(delivery_label_only('soft reflective bell decay','normal reflective'))
        self.assertFalse(delivery_label_only('water flowing',''))

    def test_real_morning_birds_cannot_answer_electrical_buzz_or_radio_static(self):
        from hinglish_sound.relevance import source_matches
        birds=asset('Morning birds','morning birds ambience forest bird song mixkit39')
        for intent in ('flickering fluorescent light buzz','faint distorted radio static'):
            with self.subTest(intent=intent):
                ok,reason=source_matches(birds,'ambience',intent)
                self.assertFalse(ok)
                self.assertIn('birds',reason)

    def test_real_heels_recording_cannot_answer_cloth(self):
        from hinglish_sound.relevance import source_matches
        ok,reason=source_matches(asset('Footsteps on heels on pavement','footsteps walking heels pavement'),
                                 'foley','quiet dry fabric rubbing')
        self.assertFalse(ok)
        self.assertIn('footsteps',reason)
        self.assertIn('cloth',reason)

    def test_positive_physical_subjects_are_supported(self):
        from hinglish_sound.relevance import source_matches
        pairs=[('Morning birds','quiet birds chirping'),('Crickets and cicadas','distant insects'),
               ('Horse hooves galloping','horse gallop'),('Leaves rustling','soft foliage movement'),
               ('Boots walking on pavement','quiet footsteps'),('Jacket fabric movement','cloth rubbing'),
               ('Wooden door creaking','door opens'),('River water splashing','running water'),
               ('Heavy rain falling','rain and downpour'),('Wind gust in trees','steady wind'),
               ('Street traffic','distant car traffic'),('Fluorescent lighting buzz','electrical room hum'),
               ('Radio static crackling','faint electronic static'),('Crowd cheering','audience applause')]
        for name,intent in pairs:
            with self.subTest(name=name):
                self.assertTrue(source_matches(asset(name),'foley',intent)[0])

    def test_synthetic_categories_allow_abstract_wind_swoosh(self):
        from hinglish_sound.relevance import source_matches
        for family in ('whoosh','impact','riser','poke','cute'):
            self.assertTrue(source_matches(asset('Wind swoosh','wind sweep'),'whoosh' if family=='whoosh' else family,
                                           'short abstract transition accent')[0])

    def test_multi_subject_intent_can_match_any_explicit_requested_subject(self):
        from hinglish_sound.relevance import source_matches
        self.assertTrue(source_matches(asset('Morning birds'),'ambience','birds and gentle wind')[0])
        self.assertTrue(source_matches(asset('Street traffic'),'ambience','rain with distant traffic')[0])
        self.assertFalse(source_matches(asset('Horse hooves'),'foley','rain with distant traffic')[0])

    def test_running_water_is_not_running_footsteps(self):
        from hinglish_sound.relevance import source_matches
        self.assertFalse(source_matches(asset('Running water from a faucet'),'foley','running footsteps')[0])
        self.assertFalse(source_matches(asset('Running on gravel'),'foley','river water')[0])
        self.assertTrue(source_matches(asset('Running water'),'ambience','water flowing')[0])

    def test_generic_rustle_or_buzz_does_not_invent_a_material(self):
        from hinglish_sound.relevance import source_matches
        for name,intent in [('Rustle recording','quiet fabric rubbing'),('Soft buzzing recording','room hum')]:
            ok,reason=source_matches(asset(name),'foley',intent)
            self.assertTrue(ok)
            self.assertIn('unknown',reason.lower())

    def test_unknown_metadata_remains_for_the_listening_evaluator(self):
        from hinglish_sound.relevance import source_matches
        ok,reason=source_matches(asset('effect_039','original audio sample'),'ambience','distant radio static')
        self.assertTrue(ok)
        self.assertIn('unknown',reason.lower())

    def test_boundaries_and_negated_subjects_are_not_false_matches(self):
        from hinglish_sound.relevance import source_matches
        self.assertFalse(source_matches(asset('Birds'),'ambience','quiet room tone without birds')[0])
        ok,reason=source_matches(asset('Shadow field','recording of sound'),'ambience','room hum')
        self.assertTrue(ok)
        self.assertIn('unknown',reason.lower())
        # Generic clock winding and digital chirps are not evidence of wind or birds.
        self.assertTrue(source_matches(asset('Wind-up clock mechanism'),'foley','small mechanical sound')[0])
        self.assertFalse(source_matches(asset('Electronic notification chirp'),'foley','small mechanical sound')[0])
        self.assertTrue(source_matches(asset('Electronic notification chirp'),'poke','electronic chirp')[0])

    def test_known_source_with_no_explicit_matching_request_is_rejected(self):
        from hinglish_sound.relevance import source_matches
        self.assertFalse(source_matches(asset('Morning birds'),'ambience','quiet background ambience')[0])


if __name__=='__main__':unittest.main()
