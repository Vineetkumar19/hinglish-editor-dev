import struct
import tempfile
import unittest
import wave
from pathlib import Path
from hinglish_cut.media import probe, extract_audio, assemble_audio, conform_video, rotation_from_display_matrix, oriented_dimensions
from hinglish_cut.demo import create_demo_media
from hinglish_cut.model import Cut


class MediaTests(unittest.TestCase):
    def test_phone_display_matrix_rotates_pixels_to_portrait(self):
        # This is the display matrix embedded in the supplied phone recordings.
        matrix=struct.pack('<9i',0,65536,0,-65536,0,0,0,0,1073741824)
        rotation=rotation_from_display_matrix(matrix)
        self.assertEqual(rotation,270)
        self.assertEqual(oriented_dimensions(1920,1080,rotation),(1080,1920))

    def test_variable_rate_phone_video_is_converted_to_premiere_safe_30fps_copy(self):
        import av
        import numpy as np
        from fractions import Fraction
        with tempfile.TemporaryDirectory() as d:
            source=Path(d)/'phone-vfr.mkv'
            with av.open(str(source),'w') as out:
                video=out.add_stream('libx264',rate=1000)
                video.width=64; video.height=48; video.pix_fmt='yuv420p'; video.time_base=Fraction(1,1000)
                audio=out.add_stream('aac',rate=48000); audio.layout='mono'
                for index,pts in enumerate((0,16,34,53,72,126,145,163,214,232)):
                    frame=av.VideoFrame.from_ndarray(np.full((48,64,3),index*20,dtype=np.uint8),format='rgb24')
                    frame.pts=pts; frame.time_base=Fraction(1,1000)
                    for packet in video.encode(frame): out.mux(packet)
                for packet in video.encode(): out.mux(packet)
                samples=np.zeros((1,14400),dtype=np.float32)
                for start in range(0,14400,1024):
                    chunk=samples[:,start:start+1024]
                    frame=av.AudioFrame.from_ndarray(chunk,format='fltp',layout='mono')
                    frame.sample_rate=48000; frame.pts=start; frame.time_base=Fraction(1,48000)
                    for packet in audio.encode(frame): out.mux(packet)
                for packet in audio.encode(): out.mux(packet)
            with self.assertRaises(ValueError):
                probe(source)
            copy=Path(d)/'conformed.mp4'
            media=conform_video(source,copy)
            self.assertEqual(media.fps,'30')
            self.assertTrue(copy.exists())
            self.assertGreater(media.duration,.2)

    def test_real_media_audio_and_timeline_duration(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'raw & test.mp4'
            create_demo_media(p,seconds=3,frequency=440)
            m=probe(p)
            self.assertEqual(m.fps,'25')
            self.assertEqual(m.channels,2)
            wav=Path(d)/'source.wav'
            extract_audio(m,wav)
            out=Path(d)/'cut.wav'
            assemble_audio([Cut(m.id,5,15,0),Cut(m.id,30,50,0)],{m.id:m},{m.id:wav},out)
            with wave.open(str(out),'rb') as w:
                self.assertEqual(w.getnframes(),19200)
                self.assertEqual(w.getframerate(),16000)


if __name__=='__main__':
    unittest.main()
