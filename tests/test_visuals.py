import hashlib
import json
import tempfile
import unittest
from fractions import Fraction
from pathlib import Path
from unittest.mock import patch
import xml.etree.ElementTree as ET

import av
import numpy as np
from PIL import Image, ImageDraw

from hinglish_broll.phrases import build_phrases
from hinglish_broll.timeline import parse_xmeml, path_key
from hinglish_cut.model import Cut, Media as SourceMedia, Word
from hinglish_cut.xml_export import export_xml
from hinglish_visuals import render
from hinglish_visuals.gather import gather, locked
from hinglish_visuals.planner import VisualMoment, validate_plan
from hinglish_visuals.settings import profiles_for
from hinglish_visuals.timing import mention_time, popup_slots
from hinglish_visuals.web import Entity, Media, Web, pick_derivative


def write_video(path, seconds, width, height, fps=30, audio=True, codec='libx264', color=(40, 80, 120)):
    """Small real video (moving bar, optional tone) so decode/encode paths run for real."""
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    with av.open(str(path), 'w') as out:
        video = out.add_stream(codec, rate=fps)
        video.width, video.height, video.pix_fmt = width, height, 'yuv420p'
        sound = out.add_stream('aac', rate=48000) if audio else None
        if sound: sound.layout = 'mono'
        frames = round(seconds * fps)
        for i in range(frames):
            pixels = np.empty((height, width, 3), np.uint8); pixels[:] = color
            x = (i * 4) % max(1, width - 10)
            pixels[:, x:x + 10] = (230, 190, 100)
            frame = av.VideoFrame.from_ndarray(pixels, format='rgb24'); frame.pts = i
            for packet in video.encode(frame): out.mux(packet)
        for packet in video.encode(): out.mux(packet)
        if sound:
            tone = (.1 * np.sin(2 * np.pi * 440 * np.arange(int(seconds * 48000)) / 48000) * 32767).astype(np.int16)
            for i in range(0, len(tone), 1024):
                af = av.AudioFrame.from_ndarray(tone[i:i + 1024].reshape(1, -1), format='s16', layout='mono')
                af.sample_rate, af.pts = 48000, i
                for packet in sound.encode(af): out.mux(packet)
            for packet in sound.encode(): out.mux(packet)
    return path


def gandhi():
    return Entity('gandhi', 'Mahatma Gandhi', 'person', 'Q1001', 'Mahatma Gandhi', 'Indian independence leader',
                  ['Bapu', 'Gandhi', 'Gandhiji', 'M. K. Gandhi', 'Mahatma'], 'Mahatma Gandhi', 'Mahatma Gandhi')


def media(**values):
    base = dict(kind='image', source='commons', id='commons:File:x.jpg', title='x', url='https://x.test/x.jpg',
                width=1200, height=900)
    base.update(values)
    return Media(**base)


class EvidenceTests(unittest.TestCase):
    def test_a_gandhi_story_only_accepts_files_about_mahatma_gandhi(self):
        entity = gandhi()
        self.assertFalse(locked(media(title='Indira Gandhi at a rally', text='Indira Gandhi 1971'), entity))
        self.assertFalse(locked(media(title='Rahul Gandhi', text='Category Rahul Gandhi'), entity))
        self.assertFalse(locked(media(title='Gandhi Nagar railway station'), entity))
        self.assertTrue(locked(media(title='Gandhi at Dandi', text='Salt March | Mahatma Gandhi in 1930'), entity))
        self.assertTrue(locked(media(title='Bapu spinning khadi'), entity))
        self.assertTrue(locked(media(title='anything', official=True), entity))

    def test_logo_search_keeps_the_official_logo_first(self):
        zomato = Entity('zomato', 'Zomato', 'brand', 'Q1', 'Zomato', 'Indian food delivery company',
                        files={'logo': ['Zomato logo.png']})

        class FakeWeb:
            def files(self, names, **_):
                return [media(id='commons:File:Zomato logo.png', title='Zomato logo', width=800, height=300)] if names else []
            def lead_image(self, title): return None
            def commons_search(self, query, filetype, limit):
                return [media(id='commons:File:Zomato rider.jpg', title='Zomato delivery rider', text='Zomato'),
                        media(id='commons:File:Zomato old logo.svg', title='Zomato old logo', text='Zomato')]
            def site_icon(self, website): return None
        moment = VisualMoment(0, 'Zomato app logo', ['Zomato'], 3, 'Zomato se', '', 'zomato', 'Jomato', 'logo', 'popup')
        found = gather(FakeWeb(), moment, zomato, 2.0, 'portrait', (1080, 1920))
        self.assertEqual(found[0].id, 'commons:File:Zomato logo.png')
        self.assertTrue(found[0].official)
        self.assertNotIn('commons:File:Zomato rider.jpg', [m.id for m in found])   # a photo is not a logo


    def test_stock_clip_must_show_the_place_itself_not_just_echo_the_query(self):
        from hinglish_broll.stock import Candidate
        from hinglish_visuals.gather import _stock_media
        temple = Entity('temple', 'Meenakshi Amman Temple', 'place', label='Meenakshi Amman Temple')
        echo = Candidate('pexels', 'pexels:1', 'Meenakshi Amman Temple', 8, 1080, 1920,
                         page_url='https://www.pexels.com/video/woman-dancing-in-studio-1/')
        real = Candidate('pexels', 'pexels:2', 'Meenakshi Amman Temple', 8, 1080, 1920,
                         page_url='https://www.pexels.com/video/meenakshi-amman-temple-madurai-2/')
        self.assertFalse(locked(_stock_media(echo, 'Meenakshi Amman Temple'), temple))
        self.assertTrue(locked(_stock_media(real, 'Meenakshi Amman Temple'), temple))


class WebTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def fake(self, payloads):
        class Response:
            def __init__(self, data): self.data, self.status_code, self.headers = data, 200, {}
            def raise_for_status(self): pass
            def json(self): return self.data

        class Session:
            headers = {}
            def get(self, url, params=None, timeout=None):
                for key, data in payloads.items():
                    if key in json.dumps(params):
                        return Response(data)
                raise AssertionError(f'unexpected request {params}')
        return Web(self.root, session=Session())

    def test_wikidata_item_gives_names_and_its_own_media(self):
        claim = lambda value, rank='normal': {'rank': rank, 'mainsnak': {'snaktype': 'value', 'datavalue': {'value': value}}}
        web = self.fake({'wbgetentities': {'entities': {'Q1001': {
            'labels': {'en': {'value': 'Mahatma Gandhi'}},
            'descriptions': {'en': {'value': 'Indian independence activist (1869-1948)'}},
            'aliases': {'en': [{'value': 'Bapu'}, {'value': 'Mohandas Karamchand Gandhi'}]},
            'sitelinks': {'enwiki': {'title': 'Mahatma Gandhi'}},
            'claims': {'P18': [claim('Portrait Gandhi.jpg'), claim('Gandhi smiling.jpg', 'preferred'),
                               claim('Fake.jpg', 'deprecated')],
                       'P10': [claim('Gandhi 1931.webm')], 'P373': [claim('Mahatma Gandhi')]}}}}})
        entity = web.entity('gandhi', 'Gandhi', 'person', 'Q1001')
        self.assertEqual(entity.label, 'Mahatma Gandhi')
        self.assertEqual(entity.files['portrait'], ['Gandhi smiling.jpg', 'Portrait Gandhi.jpg'])
        self.assertEqual(entity.files['video'], ['Gandhi 1931.webm'])
        self.assertIn('Mohandas Karamchand Gandhi', entity.names())

    def test_commons_video_uses_a_small_transcode_and_keeps_licence(self):
        page = {'title': 'File:Gandhi Salt March.webm', 'index': 1, 'videoinfo': [{
            'url': 'https://upload.wikimedia.org/wikipedia/commons/a/ab/Gandhi_Salt_March.webm',
            'descriptionurl': 'https://commons.wikimedia.org/wiki/File:Gandhi_Salt_March.webm',
            'width': 1440, 'height': 1080, 'size': 900_000_000, 'duration': 95.5, 'mime': 'video/webm',
            'mediatype': 'VIDEO', 'derivatives': [
                {'src': 'https://x/1080p.webm', 'type': 'video/webm; codecs="vp9, opus"', 'width': 1440, 'height': 1080},
                {'src': 'https://x/720p.webm', 'type': 'video/webm; codecs="vp9, opus"', 'width': 960, 'height': 720},
                {'src': 'https://x/360p.webm', 'type': 'video/webm; codecs="vp9, opus"', 'width': 480, 'height': 360},
                {'src': 'https://x/audio.ogg', 'type': 'audio/ogg; codecs="vorbis"'}],
            'extmetadata': {'Artist': {'value': '<a href="x">British Pathé</a>'},
                            'LicenseShortName': {'value': 'Public domain'},
                            'Categories': {'value': 'Mahatma Gandhi in 1930|Salt March'}}}]}
        web = self.fake({'gsrsearch': {'query': {'pages': [page]}}})
        found = web.commons_search('"Mahatma Gandhi"', 'video')
        self.assertEqual(len(found), 1)
        video = found[0]
        self.assertEqual((video.kind, video.url, video.height, video.duration), ('video', 'https://x/720p.webm', 720, 95.5))
        self.assertEqual((video.author, video.license), ('British Pathé', 'Public domain'))
        self.assertIn('Salt March', video.text)
        self.assertTrue(video.thumb.endswith('/480px--Gandhi_Salt_March.webm.jpg'))

    def test_huge_original_without_transcode_is_not_downloaded(self):
        self.assertEqual(pick_derivative([], 'https://x/big.webm', 1920, 1080, 2_000_000_000)[0], '')


class PlanTests(unittest.TestCase):
    def test_quote_decides_the_line_and_brand_rules_apply(self):
        group = build_phrases([Word(t, i * .5, i * .5 + .4) for i, t in enumerate(
            'Kal raat maine Jomato se biryani mangwayi. Phir Gandhi ji ki kahani padhi. Unhone namak kanoon toda.'.split())])
        entities = {}
        raw = {'story': 'Food order then a Gandhi story', 'entities': [
            {'key': 'zomato', 'name': 'Zomato', 'kind': 'brand', 'about': 'food delivery app'},
            {'key': 'gandhi', 'name': 'Mahatma Gandhi', 'kind': 'person', 'about': 'freedom fighter'},
            {'key': 'salt', 'name': 'Salt March', 'kind': 'event', 'about': '1930 protest'}],
            'moments': [
                {'id': 99, 'quote': 'maine Jomato se', 'entity': 'zomato', 'mention': 'Jomato', 'meaning': 'ordered food',
                 'show': 'photo', 'display': 'fullscreen', 'visual': 'Zomato logo', 'search': ['food app'], 'priority': 3},
                {'id': 0, 'quote': 'namak kanoon toda', 'entity': 'gandhi', 'mention': '', 'meaning': 'broke salt law',
                 'show': 'video', 'display': 'popup', 'visual': 'Gandhi Salt March', 'search': ['Salt March'], 'priority': 3},
                {'id': 0, 'quote': 'kahani padhi', 'entity': 'nobody', 'mention': '', 'meaning': '', 'show': 'photo',
                 'display': 'popup', 'visual': 'x', 'search': ['x'], 'priority': 1}]}
        moments = validate_plan(raw, group, entities)
        self.assertEqual(len(moments), 2)
        logo, story = moments
        self.assertEqual((logo.show, logo.display), ('logo', 'popup'))          # brands are logo pop-ups
        self.assertIn('Jomato', group[logo.phrase_id].text)                      # quote wins over the bad id
        self.assertEqual(logo.queries, ['Zomato food app'])                     # searches name the entity
        self.assertEqual((story.show, story.display), ('video', 'fullscreen'))  # footage replaces the speaker
        self.assertIn('namak', group[story.phrase_id].text)


class TimingTests(unittest.TestCase):
    def test_popup_lands_on_the_misspelt_brand_word_and_is_not_repeated(self):
        text = 'Kal maine Jomato se order kiya. Bahut der lagi. Phir se Jomato kholi.'
        words = [Word(t, i * .45, i * .45 + .35) for i, t in enumerate(text.split())]
        self.assertAlmostEqual(mention_time(words, 0, 3, 'Zomato', ['Zomato']), .9)
        phrases, lines = build_phrases(words), build_phrases(words, merge=False)
        _, pop = profiles_for(30)
        make = lambda pid, quote: VisualMoment(pid, 'Zomato logo', ['Zomato'], 3, quote, '', 'zomato', 'Jomato', 'logo', 'popup')
        second = next(p.id for p in phrases if 'kholi' in p.text)
        slots = popup_slots([make(0, 'maine Jomato se'), make(second, 'se Jomato kholi')], phrases, lines, words,
                            pop, 30, [], {'zomato': ['Zomato']})
        self.assertEqual(len(slots), 1)                   # same logo again within 45 s is noise
        self.assertAlmostEqual(slots[0].start, .9 - .12)  # pops exactly as "Jomato" is said
        self.assertGreaterEqual(slots[0].duration, pop.min_len)

    def test_popup_never_covers_a_full_screen_visual(self):
        words = [Word(t, i * .45, i * .45 + .35) for i, t in enumerate('Maine Swiggy use kiya aaj.'.split())]
        phrases, lines = build_phrases(words), build_phrases(words, merge=False)
        _, pop = profiles_for(30)
        m = VisualMoment(0, 'Swiggy logo', ['Swiggy'], 3, 'Maine Swiggy', '', 'swiggy', 'Swiggy', 'logo', 'popup')
        self.assertEqual(popup_slots([m], phrases, lines, words, pop, 30, [(0.0, 3.0)]), [])

    def test_face_card_ends_just_before_that_persons_footage(self):
        words = [Word(t, i * .4, i * .4 + .3) for i, t in enumerate(
            'Saal 1921 mein Gandhi ji Madurai aaye. Unhone dhoti pehni.'.split())]
        phrases, lines = build_phrases(words), build_phrases(words, merge=False)
        _, pop = profiles_for(30)
        footage = next(l for l in lines if l.text.startswith('Unhone')).start
        m = VisualMoment(0, 'Gandhi portrait', ['Mahatma Gandhi'], 3, 'mein Gandhi ji', '', 'gandhi', 'Gandhi', 'photo', 'popup')
        slots = popup_slots([m], phrases, lines, words, pop, 30, [(footage, footage + 1.5)])
        self.assertEqual(len(slots), 1)
        self.assertAlmostEqual(slots[0].start, 1.2 - .12)
        self.assertAlmostEqual(slots[0].end, footage - .15)


class RenderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.dir = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def logo(self):
        image = Image.new('RGBA', (300, 100), (0, 0, 0, 0))
        ImageDraw.Draw(image).rounded_rectangle((0, 0, 299, 99), 20, fill=(226, 55, 68, 255))
        image.save(self.dir / 'logo.png')
        return self.dir / 'logo.png'

    def test_popup_is_transparent_outside_the_card_pops_in_and_sits_above_the_face(self):
        card, position = render.popup_card(self.logo(), 270, 480, 'logo')
        clip = render.popup_clip(card, position, 1.5, 270, 480, 30, self.dir / 'pop.mov')
        with av.open(str(clip)) as c:
            stream = c.streams.video[0]
            self.assertEqual((stream.codec_context.name, stream.codec_context.pix_fmt), ('qtrle', 'argb'))
            frames = [f.to_ndarray(format='rgba') for f in c.decode(stream)]
        self.assertEqual(len(frames), 45)
        self.assertEqual(frames[0][..., 3].max(), 0)                  # starts invisible
        middle = frames[20][..., 3]
        rows = np.nonzero(middle.max(1))[0]
        self.assertLess(rows[-1], 480 * .3)                           # top of a 9:16 frame, above the face
        self.assertGreater(middle.max(), 240)                         # card fully visible while held
        self.assertLess((middle > 0).mean(), .25)                     # the rest stays transparent
        self.assertLess(frames[-1][..., 3].max(), 60)                 # fades out

    def test_card_moves_off_the_face(self):
        from hinglish_visuals.layout import place_card
        self.assertEqual(place_card(400, 200, 1080, 1920), (1.0, ((1080 - 400) // 2, round(1920 * .07))))
        head_at_top = (380, 80, 700, 520)            # wide shot: head near the top centre
        scale, (x, y) = place_card(300, 200, 1080, 1920, head_at_top)
        self.assertTrue(x + 300 * scale <= 380 or x >= 700)   # beside the head, not on it
        self.assertLess(y, 1920 * .2)                          # still at the top
        card, (x, y) = render.popup_card(self.logo(), 1080, 1920, 'logo', avoid=(100, 0, 980, 700))
        self.assertTrue(y >= 700 or x + card.width <= 100 or x >= 980)
        self.assertLessEqual(y + card.height, 1920 * .62)      # above the caption area

    def test_face_card_on_youtube_sits_beside_the_face(self):
        photo = Image.new('RGB', (400, 500), (120, 110, 100)); photo.save(self.dir / 'p.jpg')
        card, (x, y) = render.popup_card(self.dir / 'p.jpg', 480, 270, 'photo', 'Mahatma Gandhi')
        self.assertGreater(x, 480 * .6)

    def test_full_screen_photo_pushes_in_and_fits_a_wide_photo_over_a_blur(self):
        wide = Image.new('RGB', (800, 450), (30, 90, 160))
        ImageDraw.Draw(wide).rectangle((300, 150, 500, 300), fill=(240, 200, 40)); wide.save(self.dir / 'w.jpg')
        clip = render.still_clip(self.dir / 'w.jpg', 1.0, 144, 256, 30, self.dir / 'still.mp4')
        with av.open(str(clip)) as c:
            frames = [f.to_ndarray(format='rgb24').astype(int) for f in c.decode(c.streams.video[0])]
        self.assertEqual((len(frames), frames[0].shape[:2]), (30, (256, 144)))
        self.assertGreater(np.abs(frames[0] - frames[-1]).mean(), 1.0)   # it moves
        top_band = frames[0][:40].mean(axis=(0, 1))
        self.assertLess(top_band.max(), 120)                             # blurred, darkened fill, not a crop

    def test_archival_4_3_video_keeps_its_whole_picture_and_exact_length(self):
        source = write_video(self.dir / 'old.webm', 3, 160, 120, 25, audio=False, codec='libvpx-vp9')
        clip = render.video_clip(source, .5, 1.2, 144, 256, 30, self.dir / 'v.mp4')
        with av.open(str(clip)) as c:
            stream = c.streams.video[0]
            frames = [f for f in c.decode(stream)]
        self.assertEqual(len(frames), 36)
        self.assertEqual(len(av.open(str(clip)).streams.audio), 0)


class PipelineTests(unittest.TestCase):
    """The whole agent on a real (synthetic) video: scripted brain + recorded internet answers."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_end_to_end_places_logo_popup_and_full_screen_footage(self):
        root = self.root
        source = write_video(root / 'input' / 'talk.mp4', 12, 144, 256, 30)
        src = SourceMedia('talk', str(source), 12, '30', 144, 256, 1, 48000)
        xml = root / 'EDITED_SEQUENCE.xml'
        export_xml(xml, [Cut('talk', 0, 360, 0)], {'talk': src}, None)
        text = ('Doston aaj ek baat bataunga. Kal maine Jomato se khana mangwaya. Phir maine Gandhi ji ki '
                'kahani padhi. Unhone namak kanoon toda aur Dandi tak chale. Yeh sach mein inspiring hai.')
        words = [Word(t, .3 + i * .38, .3 + i * .38 + .3) for i, t in enumerate(text.split())]

        # Recorded internet: files already in the local cache, answers as Wikimedia would give them.
        def cached(url, maker):
            target = root / 'cache' / 'visuals' / 'media' / (hashlib.sha1(url.encode()).hexdigest()[:20] + Path(url).suffix)
            target.parent.mkdir(parents=True, exist_ok=True)
            maker(target)
        logo_url, video_url = 'https://upload.test/Zomato_logo.png', 'https://upload.test/Salt_March.webm'
        cached(logo_url, lambda p: Image.new('RGBA', (400, 150), (226, 55, 68, 255)).save(p))
        cached(video_url, lambda p: write_video(p, 6, 320, 240, 25, audio=False, codec='libvpx-vp9', color=(90, 90, 90)))

        class FakeWeb:
            session = None
            def search_entities(self, name, limit=6):
                return [{'id': {'Zomato': 'Q1', 'Mahatma Gandhi': 'Q1001'}[name], 'label': name, 'description': ''}]
            def entity(self, key, name, kind, qid):
                if key == 'zomato':
                    return Entity(key, name, kind, qid, 'Zomato', 'Indian food delivery company', files={'logo': ['Zomato logo.png']})
                return gandhi()
            def files(self, names, **_):
                if 'Zomato logo.png' in names:
                    return [Media('image', 'commons', 'commons:File:Zomato logo.png', 'Zomato logo', logo_url,
                                  width=400, height=150, license='Public domain')]
                return []
            def commons_search(self, query, filetype, limit=20):
                if filetype == 'video' and 'Gandhi' in query:
                    return [Media('video', 'commons', 'commons:File:Salt March.webm', 'Gandhi Salt March 1930', video_url,
                                  width=320, height=240, duration=6, author='British Pathé', license='Public domain',
                                  text='Mahatma Gandhi in 1930 | Salt March'),
                            Media('video', 'commons', 'commons:File:Indira.webm', 'Indira Gandhi speech', video_url,
                                  width=320, height=240, duration=60, text='Indira Gandhi')]
                return []
            def lead_image(self, title): return None
            def site_icon(self, website): return None

        class ScriptedBrain:
            name = 'scripted test brain'
            def json(self, system, data, schema, max_tokens=0, think=False):
                props = schema['properties']
                if 'visual_world' in props:
                    return {'topic': 'food order and Gandhi story', 'country': 'India', 'places': [], 'subjects': [],
                            'mood': 'warm', 'visual_world': 'India'}
                if 'moments' in props:
                    ids = {p['text'].split()[0]: p['id'] for p in data['phrases']}
                    return {'story': 'Zomato order, then the Salt March story of Gandhi', 'entities': [
                        {'key': 'zomato', 'name': 'Zomato', 'kind': 'brand', 'about': 'food delivery app'},
                        {'key': 'gandhi', 'name': 'Mahatma Gandhi', 'kind': 'person', 'about': 'freedom fighter'}],
                        'moments': [
                            {'id': 0, 'quote': 'maine Jomato se', 'entity': 'zomato', 'mention': 'Jomato',
                             'meaning': 'ordered food on Zomato', 'show': 'logo', 'display': 'popup',
                             'visual': 'Zomato logo', 'search': ['Zomato'], 'priority': 3},
                            {'id': 0, 'quote': 'namak kanoon toda', 'entity': 'gandhi', 'mention': '',
                             'meaning': 'he broke the salt law and walked to Dandi', 'show': 'video',
                             'display': 'fullscreen', 'visual': 'Gandhi Salt March to Dandi',
                             'search': ['Gandhi Salt March'], 'priority': 3}]}
                if 'pick' in props:
                    return {'thinking': 'the Salt March file shows Gandhi walking', 'pick': 0, 'backups': []}
                return {'id': ''}

        with patch('hinglish_visuals.pipeline.transcripts_for',
                   lambda root, sources, device, progress: ({path_key(s): words for s in sources}, [])):
            page = __import__('hinglish_visuals.pipeline', fromlist=['run']).run(
                root, xml, web=FakeWeb(), brain=ScriptedBrain(), scorer=False, progress=lambda m: None,
                use_web=False)
        folder = page.parent
        project = json.loads((folder / 'visuals-project.json').read_text(encoding='utf-8'))
        placed = {s['label']: s for s in project['slots'] if s['clip']}
        self.assertEqual(set(placed), {'Zomato', 'Mahatma Gandhi'})
        logo, story = placed['Zomato'], placed['Mahatma Gandhi']
        said = {w.text: w.start for w in words}
        self.assertEqual(logo['display'], 'popup')
        self.assertAlmostEqual(logo['start'], said['Jomato'] - .12, places=2)       # lands on the brand word
        self.assertEqual(story['chosen']['id'], 'commons:File:Salt March.webm')     # never the Indira file
        line = [w for w in words if w.text in ('Unhone', 'chale.')]
        self.assertAlmostEqual(story['start'], line[0].start, places=2)            # exactly the spoken line
        self.assertAlmostEqual(story['end'], line[1].end, places=2)
        tracks = ET.parse(folder / 'VISUALS_SEQUENCE.xml').getroot().findall('sequence/media/video/track')
        self.assertEqual(len(tracks), 3)
        self.assertEqual(tracks[1].find('clipitem').get('id'), 'visual-clip-1')
        self.assertEqual(tracks[2].find('clipitem').get('id'), 'popup-clip-1')
        self.assertTrue(tracks[2].find('clipitem/file/pathurl').text.endswith('.mov'))
        self.assertTrue((folder / 'preview.mp4').exists())
        credits = (folder / 'CREDITS.txt').read_text(encoding='utf-8')
        self.assertIn('British Pathé', credits)
        self.assertIn('Save &amp; rebuild', (folder / 'report.html').read_text(encoding='utf-8'))
        timeline = parse_xmeml(folder / 'VISUALS_SEQUENCE.xml')
        self.assertTrue(Path(timeline.clips[0].path).samefile(source))              # talking head untouched

        # Same video, nothing on Wikipedia: the web agent alone finds the logo PNG and the footage.
        class EmptyWiki(FakeWeb):
            def files(self, names, **_): return []
            def commons_search(self, query, filetype, limit=20): return []
        web_logo = root / 'web-logo.png'
        Image.new('RGBA', (600, 240), (226, 55, 68, 255)).save(web_logo)
        web_clip = write_video(root / 'web-clip.mp4', 8, 640, 360, 30, audio=False)

        class WebFinder:
            def images(self, query, limit=30, transparent=False):
                return [Media('image', 'web', 'web:zlogo', 'Zomato Logo PNG', 'https://logos.test/zomato-logo.png',
                              page_url='https://logos.test/zomato', width=600, height=240, license='from the web',
                              text='Zomato Logo PNG zomato logo', role='web')] if 'Zomato' in query else []
            def videos(self, query, limit=12):
                return [Media('video', 'web', 'web:yt1', 'Mahatma Gandhi Salt March 1930 real footage',
                              'https://www.youtube.com/watch?v=abcdefghijk', duration=300, author='History TV',
                              text='Mahatma Gandhi Salt March 1930 real footage', role='web')] if 'Gandhi' in query else []
            def download_image(self, m, target): return web_logo
            def download_video(self, m, need): return web_clip, 36.0
        with patch('hinglish_visuals.pipeline.transcripts_for',
                   lambda root, sources, device, progress: ({path_key(s): words for s in sources}, [])):
            page = __import__('hinglish_visuals.pipeline', fromlist=['run']).run(
                root, xml, web=EmptyWiki(), brain=ScriptedBrain(), scorer=False, progress=lambda m: None,
                finder=WebFinder())
        project = json.loads((page.parent / 'visuals-project.json').read_text(encoding='utf-8'))
        placed = {s['label']: s['chosen'] for s in project['slots'] if s['clip']}
        self.assertEqual(placed['Zomato']['source'], 'web')
        self.assertEqual(placed['Mahatma Gandhi']['url'], 'https://www.youtube.com/watch?v=abcdefghijk')
        self.assertIn('History TV', (page.parent / 'CREDITS.txt').read_text(encoding='utf-8'))



class WebAgentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def finder(self, images=(), videos=(), youtube=()):
        from hinglish_visuals.websearch import WebSearch

        class FakeDDGS:
            def images(self, query, **options):
                self.last = options
                return list(images)
            def videos(self, query, **options):
                return list(videos)
        return WebSearch(self.root, lambda m: None, ddgs=FakeDDGS(), youtube=lambda q, n: list(youtube))

    def test_web_image_search_keeps_real_images_and_drops_watermarked_stock(self):
        finder = self.finder(images=[
            {'title': 'Zomato Logo PNG Transparent', 'image': 'https://logos.example/zomato-logo.png',
             'thumbnail': 'https://tse.example/t.jpg', 'url': 'https://logos.example/zomato', 'width': '2000',
             'height': '800', 'source': 'Bing'},
            {'title': 'Zomato logo', 'image': 'https://image.shutterstock.com/zomato.jpg',
             'url': 'https://www.shutterstock.com/x', 'width': '1000', 'height': '600'}])
        found = finder.images('Zomato logo png', transparent=True)
        self.assertEqual([m.url for m in found], ['https://logos.example/zomato-logo.png'])
        self.assertEqual((found[0].source, found[0].width, found[0].height), ('web', 2000, 800))
        self.assertEqual(finder.ddgs().last['type_image'], 'transparent')

    def test_web_and_youtube_videos_are_merged_once(self):
        finder = self.finder(
            videos=[{'content': 'https://www.youtube.com/watch?v=abcdefghijk', 'title': 'Meenakshi Amman Temple 4K',
                     'duration': '4:13', 'publisher': 'YouTube', 'images': {'large': 'https://i.example/l.jpg'}}],
            youtube=[{'url': 'https://www.youtube.com/watch?v=abcdefghijk', 'title': 'same video', 'duration': 253},
                     {'url': 'https://www.youtube.com/watch?v=zyxwvutsrqp', 'title': 'Madurai Meenakshi temple drone',
                      'duration': 95, 'channel': 'Travel'}])
        found = finder.videos('Meenakshi Amman Temple')
        self.assertEqual(len(found), 2)
        self.assertEqual(found[0].duration, 253.0)
        self.assertEqual(found[1].author, 'Travel')

    def test_gather_uses_the_whole_web_and_still_demands_proof(self):
        temple = Entity('temple', 'Meenakshi Amman Temple', 'place', label='Meenakshi Amman Temple')
        finder = self.finder(
            images=[{'title': 'Meenakshi Amman Temple towers', 'image': 'https://a.example/meenakshi.jpg',
                     'url': 'https://a.example/p', 'width': '1920', 'height': '1080'},
                    {'title': 'Golden Temple Amritsar', 'image': 'https://b.example/golden.jpg',
                     'url': 'https://b.example/p', 'width': '1920', 'height': '1080'}],
            youtube=[{'url': 'https://www.youtube.com/watch?v=zyxwvutsrqp', 'title': 'Meenakshi Amman Temple Madurai 4K',
                      'duration': 95},
                     {'url': 'https://www.youtube.com/watch?v=aaaaaaaaaaa', 'title': 'Top 10 temples of India',
                      'duration': 600}])

        class NoWiki:
            def files(self, names, **_): return []
            def lead_image(self, title): return None
            def commons_search(self, *a, **k): return []
        moment = VisualMoment(0, 'Meenakshi temple towers', ['Meenakshi Amman Temple'], 3, 'q', '', 'temple', '',
                              'video', 'fullscreen')
        found = gather(NoWiki(), moment, temple, 3.0, 'portrait', (1080, 1920), finder=finder)
        titles = [m.title for m in found]
        self.assertEqual(titles[0], 'Meenakshi Amman Temple Madurai 4K')      # real footage first
        self.assertIn('Meenakshi Amman Temple towers', titles)                 # real photo as fallback
        self.assertNotIn('Golden Temple Amritsar', titles)
        self.assertNotIn('Top 10 temples of India', titles)

    def test_long_web_video_downloads_only_a_section(self):
        from hinglish_visuals.websearch import WebSearch
        calls = {}

        class FakeYDL:
            def __init__(self, options): calls['options'] = options
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def download(self, urls):
                Path(calls['options']['outtmpl'].replace('%(ext)s', 'mp4')).write_bytes(b'video')
        with patch('yt_dlp.YoutubeDL', FakeYDL):
            finder = WebSearch(self.root, lambda m: None)
            path, start = finder.download_video(media(kind='video', source='web', url='https://youtu.be/x', duration=1200), 3)
        self.assertTrue(path.exists())
        self.assertGreater(start, 100)
        self.assertIn('download_ranges', calls['options'])
        self.assertIn('ffmpeg_location', calls['options'])


if __name__ == '__main__':
    unittest.main()
