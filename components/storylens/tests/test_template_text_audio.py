import array
from pathlib import Path
import unittest
import wave
from hinglish_app.template_text_audio import decode_map,cache_key,local_file
from test_template_text_service import workspace_temp

class TemplateTextAudioTests(unittest.TestCase):
    def source(self,folder):
        path=Path(folder)/'narration.wav';samples=array.array('h',[1000]*16000+[10000]*16000)
        with wave.open(str(path),'wb') as stream:stream.setparams((1,2,16000,0,'NONE','not compressed'));stream.writeframes(samples.tobytes())
        return path
    def test_real_audio_decode_keeps_source_trim_gap_and_master_duration(self):
        with workspace_temp() as folder:
            source=self.source(folder);output=Path(folder)/'final.wav'
            scan={'duration':3,'audio':[{'path':str(source),'start':0,'end':1,'source_in':1,'rate':1,'gain':1},{'path':str(source),'start':2,'end':3,'source_in':0,'rate':1,'gain':1}]}
            decode_map(scan,output)
            with wave.open(str(output),'rb') as stream:self.assertEqual(stream.getnframes(),48000);data=array.array('h',stream.readframes(48000))
            self.assertGreater(sum(abs(v) for v in data[:15000]),5*sum(abs(v) for v in data[33000:48000]));self.assertEqual(max(abs(v) for v in data[16500:31500]),0)
    def test_audio_ending_before_timeline_refuses_without_partial_output(self):
        with workspace_temp() as folder:
            source=self.source(folder);output=Path(folder)/'final.wav'
            with self.assertRaises(ValueError):decode_map({'duration':10,'audio':[{'path':str(source),'start':0,'end':10,'source_in':0,'rate':1,'gain':1}]},output)
            self.assertFalse(output.exists())
    def test_network_sources_and_arbitrary_document_files_are_rejected(self):
        for source in ['https://example.com/private.wav',r'\\server\share\audio.wav','file:///C:/audio.wav']:
            with self.assertRaises(ValueError):local_file(source)
    def test_audio_cache_fingerprint_changes_with_trim(self):
        with workspace_temp() as folder:
            source=self.source(folder);scan={'duration':1,'audio':[{'path':str(source),'start':0,'end':1,'source_in':0,'rate':1,'gain':1}]};before=cache_key(scan);scan['audio'][0]['source_in']=1;self.assertNotEqual(before,cache_key(scan))

if __name__=='__main__':unittest.main()
