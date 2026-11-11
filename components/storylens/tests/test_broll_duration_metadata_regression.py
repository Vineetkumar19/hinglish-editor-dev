"""Recorded timing regressions; synthetic files/checks, no inference or render."""
import copy
import json
from pathlib import Path
import unittest

from tests import test_broll_candidate_manifest as fixtures


class EncodedDurationRegressionTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.CandidateManifestTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.observed = json.loads((Path(__file__).parent / 'fixtures' /
            'broll-keyword-guard' / 'observed-duration-metadata.json').read_text(encoding='utf-8'))['rows']
        self.configure(self.observed[0])

    def configure(self, observed):
        slot = self.fixture.project['slots'][0]
        slot['options'] = slot['options'][:1]
        option = slot['options'][0]
        option['source_duration'] = observed['declared']
        self.metadata = self.fixture.metadata[str(self.fixture.root / option['clip'])]
        self.metadata.update({k: copy.deepcopy(observed[k]) for k in
                              ('duration', 'fps', 'time_base', 'frame_timing')})

    def build(self):
        return self.fixture.build()['slots'][0]

    def assert_rejected(self):
        row = self.build()
        self.assertEqual(row['candidates'], [])
        self.assertEqual(len(row['rejected_candidates']), 1)
        return row['rejected_candidates'][0]['issue']['code']

    def test_eight_recorded_frame_extents_survive_muxed_duration_rounding(self):
        self.assertEqual(len(self.observed), 8)
        for observed in self.observed:
            with self.subTest(candidate=observed['candidate_id']):
                self.configure(observed)
                row = self.build()
                self.assertEqual(len(row['candidates']), 1, row['rejected_candidates'])
                self.assertTrue(row['candidates'][0]['selectable'])
                self.assertEqual(row['candidates'][0]['prepared']['duration'], observed['duration'])

    def test_unknown_frame_evidence_does_not_create_duration_slack(self):
        self.metadata.pop('frame_timing')
        self.assert_rejected()

    def test_one_additional_stream_tick_drift_is_not_the_recorded_edit_rounding(self):
        from fractions import Fraction
        self.metadata['duration'] -= float(Fraction(self.metadata['time_base']))
        self.metadata['frame_timing']['stream_duration_ticks'] -= 1
        self.assert_rejected()

    def test_rational_ntsc_rate_requires_its_exact_packet_and_edit_grid(self):
        from fractions import Fraction
        count=181;fps=Fraction(30000,1001);ticks=1001
        nominal=Fraction(count,fps);edit=int(nominal*1000);stream=round(Fraction(edit,1000)*30000)
        observed=copy.deepcopy(self.observed[0])
        observed.update(declared=float(nominal),duration=float(Fraction(stream,30000)),
                        fps=str(fps),time_base='1/30000')
        observed['frame_timing'].update(base_rate=str(fps),ticks_per_frame=ticks,last_pts=(count-1)*ticks,
            min_pts_step=ticks,max_pts_step=ticks,edit_duration_ticks=edit,stream_duration_ticks=stream)
        self.configure(observed)
        self.fixture.project['timeline']['fps']=str(fps)
        row=self.build()
        self.assertEqual(len(row['candidates']),1,row['rejected_candidates'])
        self.assertTrue(row['candidates'][0]['selectable'])

    def test_receipt_uses_proven_frame_end_but_rejects_one_tick_actual_overrun(self):
        from hinglish_broll.candidate_manifest import checked_window_receipt,CandidateContractError
        slot=self.fixture.project['slots'][0];option=slot['options'][0]
        kwargs=dict(prepared_origin_in_original=0,prepared_source_in=3,
            active_duration=option['source_duration']-3,
            crop=option['checked_window']['crop'],verdict=slot['checks'][0],
            media_reader=lambda p:self.fixture.metadata[str(p)])
        raw=self.fixture.root/'raw-0.mp4';prepared=self.fixture.root/option['clip']
        receipt=checked_window_receipt(raw,prepared,**kwargs)
        self.assertAlmostEqual(receipt['end'],option['source_duration'])
        kwargs['active_duration']+=1/15360
        with self.assertRaises(CandidateContractError):checked_window_receipt(raw,prepared,**kwargs)

    def test_vfr_or_missing_packet_evidence_cannot_justify_duration_extension(self):
        original = copy.deepcopy(self.metadata)
        mutations = [lambda p: p.update(min_pts_step=p['ticks_per_frame']-1),
                     lambda p: p.update(packet_count=p['frame_count']-1),
                     lambda p: p.update(packet_durations_match=False),
                     lambda p: p.update(base_rate='25'),
                     lambda p: p.update(movie_time_base='0/1')]
        for mutate in mutations:
            with self.subTest(mutate=mutations.index(mutate)):
                self.metadata.clear(); self.metadata.update(copy.deepcopy(original))
                mutate(self.metadata['frame_timing'])
                self.assert_rejected()

    def test_declared_extra_frame_is_not_metadata_rounding(self):
        self.fixture.project['slots'][0]['options'][0]['source_duration'] += 1/30
        self.assertEqual(self.assert_rejected(), 'broll_trim_invalid')

    def test_actual_prepared_active_overrun_stays_rejected(self):
        slot = self.fixture.project['slots'][0]
        slot['options'][0]['source_in'] = slot['options'][0]['source_duration'] - 29/30 + 1/15360
        self.assertEqual(self.assert_rejected(), 'broll_trim_invalid')

    def test_actual_original_range_overrun_stays_rejected(self):
        option = self.fixture.project['slots'][0]['options'][0]
        option['original_offset'] = 20 - option['source_duration'] + 1/15360
        self.assertEqual(self.assert_rejected(), 'broll_trim_invalid')

    def test_mismatched_or_invalid_frame_rate_is_rejected(self):
        for rate in ('25', '0', 'not-a-rate'):
            with self.subTest(rate=rate):
                self.metadata['fps'] = rate
                self.assert_rejected()


if __name__ == '__main__':
    unittest.main()
