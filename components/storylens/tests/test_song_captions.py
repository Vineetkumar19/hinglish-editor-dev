import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from hinglish_captions.core import CaptionWord
from hinglish_captions.lyrics import mapped_reference_words,reference_cues
from hinglish_cut.recognition_quality import checked_transcript
from hinglish_eval.specs import caption_checks,Evaluation

ROOT=Path(__file__).resolve().parents[1]
LINES=['Haan tujhe dekhta raha','Kissi khwab ki tarah','Jo ab samne hai tu','Ho kaise yakeen bhala']


class SongCaptionTests(unittest.TestCase):
    def test_rejected_speech_retries_independent_full_audio_and_records_recovery(self):
        from hinglish_captions.core import CaptionCue
        from hinglish_captions.pipeline import run
        from hinglish_cut.model import Media
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as folder:
            root=Path(folder);source=root/'song.mp4';source.write_bytes(b'media fixture')
            (root/'config.phase2.json').write_text('{}')
            media=Media('song',str(source),2,'30',320,180,2,48000)
            cue=CaptionCue((CaptionWord('Haan',.3,.7),CaptionWord('tujhe',.8,1.2)),.3,1.3)
            error={'source':str(source),'error':'Invalid placeholder','reason':'invalid_recognition'}
            with patch('hinglish_captions.pipeline.analyze_sources',return_value=([],{},[error])), \
                 patch('hinglish_cut.media.prepare_media',return_value=(media,None)), \
                 patch('hinglish_captions.lyrics.transcribe_song',return_value=([cue],{'device':'cuda'})) as retry, \
                 patch('hinglish_captions.pipeline.render_overlay'), \
                 patch('hinglish_captions.pipeline.export_caption_xml'):
                output=run(root,source,'minimal','cuda',reference_script='Haan tujhe',progress=lambda _:None)
            retry.assert_called_once()
            project=json.loads(next(output.rglob('caption-project.json')).read_text(encoding='utf-8'))
            self.assertEqual(project['caption_content'],'lyrics')
            self.assertEqual(project['word_visibility'],'spoken')
            self.assertEqual(project['transcription']['fallback_reason'],'invalid_recognition')
            self.assertEqual(project['reference_script'],'Haan tujhe')

    def test_non_recognition_errors_do_not_trigger_song_retry(self):
        from hinglish_captions.pipeline import run
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as folder:
            root=Path(folder);source=root/'song.mp4';source.write_bytes(b'media fixture')
            (root/'config.phase2.json').write_text('{}')
            with patch('hinglish_captions.pipeline.analyze_sources',return_value=([],{},[{'source':str(source),'error':'Unreadable audio'}])), \
                 patch('hinglish_captions.lyrics.transcribe_song') as retry:
                with self.assertRaisesRegex(ValueError,'Unreadable audio'):
                    run(root,source,'minimal','cuda',progress=lambda _:None)
            retry.assert_not_called()

    def test_song_caption_requests_select_full_song_mode_and_readable_style(self):
        from hinglish_app.assistant_plan import quick_plan
        for request in ('Add Hinglish captions to this song','Generate song lyrics'):
            options=quick_plan(request)['steps'][0]['options']
            self.assertEqual(options['caption_content'],'lyrics')
            self.assertEqual(options['caption_style'],'minimal')
        self.assertEqual(quick_plan('Add lyrics in Typography 2')['steps'][0]['options']['caption_style'],'typography_2')

    def test_exact_user_lines_and_spelling_survive_timing_transfer(self):
        expected=' '.join(LINES).split()
        heard=[{'text':word,'start':i*.7,'end':(i+1)*.7} for i,word in enumerate(expected)]
        heard[0]['text']='aur';heard[13]['text']='ko';heard[15]['text']='yadi'
        words,corrections=mapped_reference_words(LINES,heard,lambda value:value)
        self.assertEqual([word.text for word in words],expected)
        self.assertEqual(len(corrections),3)
        cues=reference_cues(LINES,words,15.4)
        self.assertEqual([cue.text for cue in cues],LINES)
        self.assertEqual(len(cues[2].words),5)

    def test_unrelated_audio_cannot_receive_confident_reference_timing(self):
        heard=[{'text':'unrelated','start':i,'end':i+.8} for i in range(17)]
        words,_=mapped_reference_words(LINES,heard,lambda value:value)
        self.assertIsNone(words)

    def test_placeholder_output_and_the_previous_bad_export_fail_quality(self):
        for text in ('nan','nan nan nan','undefined null'):
            with self.assertRaises(ValueError):checked_transcript(text)
        self.assertEqual(checked_transcript('Kissi khwab ki tarah'),'Kissi khwab ki tarah')
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as folder:
            project={'media':{'duration':15.4},'width':1080,'height':1920,'cues':[
                {'start':i,'end':i+.5,'words':[{'text':'nan','start':i,'end':i+.4}]} for i in (1,7,13)]}
            evaluation=Evaluation('captions',folder,caption_checks(folder,project))
            self.assertFalse(evaluation.passed)
            self.assertIn('captions.valid_recognition',[check.rule for check in evaluation.hard_failed])
            self.assertEqual(evaluation.score,0)

    def test_song_phrases_support_five_words_and_sustained_notes(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as folder:
            words=[CaptionWord(word,i*.8,(i+1)*.8) for i,word in enumerate(LINES[2].split())]
            cue=reference_cues([LINES[2]],words,5)[0]
            from hinglish_captions.project import cues_to_data
            project={'caption_content':'lyrics','media':{'duration':5},'width':1080,'height':1920,'cues':cues_to_data([cue])}
            self.assertTrue(Evaluation('captions',folder,caption_checks(folder,project)).passed)
            project['caption_content']='speech'
            self.assertFalse(Evaluation('captions',folder,caption_checks(folder,project)).passed)

    def test_rtx_policy_prevents_a_cpu_payload_from_disabling_inference_gpu(self):
        from hinglish_app.server import AppState
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as folder:
            root=Path(folder);video=root/'source.mp4';video.write_bytes(b'fixture')
            (root/'config.models.local.json').write_text(json.dumps({'device':'cuda','require_cuda_inference':True}))
            state=AppState(root)
            with patch('hinglish_app.server.threading.Thread') as thread:
                job=state.create_job({'mode':'captions','source_paths':[str(video)],'device':'cpu'})
                self.assertEqual(job['device'],'cuda')
                self.assertEqual(thread.call_args.kwargs['args'][1]['device'],'cuda')


if __name__=='__main__':unittest.main()
