"""Screenshot-only photo collection contracts, written before implementation."""
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock

import numpy as np
from PIL import Image,ImageDraw

from hinglish_photos.core import validate_screenshot, detect_tiles, similarity, normalise_reading, photo_filename
from hinglish_photos.network import Fetcher

ROOT=Path(__file__).resolve().parents[1]

def picture(seed=3,size=(640,420)):
    rng=np.random.default_rng(seed)
    image=Image.fromarray(rng.integers(0,255,(size[1],size[0],3),dtype=np.uint8))
    draw=ImageDraw.Draw(image)
    draw.rectangle((30,40,180,230),fill='blue');draw.ellipse((310,80,500,290),fill='gold')
    return image

def png(image):
    out=io.BytesIO();image.save(out,'PNG');return out.getvalue()

class PhotoCoreTests(unittest.TestCase):
    def test_grid_keeps_short_photos_cut_off_by_the_bottom_of_the_screenshot(self):
        screenshot=Image.new('RGB',(1200,900),'#202124')
        for index,x in enumerate((20,400,780)):
            screenshot.paste(picture(index,(360,240)),(x,200))
            # These are real result cards, not horizontal filter chips. Their
            # column alignment and contact with the bottom establish clipping.
            screenshot.paste(picture(index+10,(360,240)),(x,850))
        tiles=detect_tiles(screenshot)
        self.assertEqual(len(tiles),6)
        clipped=[tile for tile in tiles if tile['box'][1]>=840]
        self.assertEqual(len(clipped),3)
        self.assertTrue(all(tile.get('partial') for tile in clipped))
        self.assertTrue(all(tile['box'][1]+tile['box'][3]<=900 for tile in clipped))

    def test_large_screenshots_do_not_silently_drop_detected_photos(self):
        screenshot=Image.new('RGB',(1200,10500),'#202124')
        for index in range(84):
            screenshot.paste(picture(index,(350,230)),(20+(index%3)*390,200+(index//3)*350))
        with self.assertRaisesRegex(ValueError,'80'):
            detect_tiles(screenshot)

    def test_upload_validates_pixels_instead_of_trusting_a_filename(self):
        result=validate_screenshot(png(Image.new('RGB',(1200,1800),'#202124')))
        self.assertEqual((result['width'],result['height']),(1200,1800))
        with self.assertRaisesRegex(ValueError,'screenshot'):
            validate_screenshot(b'<html>not a picture</html>')
        with self.assertRaisesRegex(ValueError,'screenshot'):
            validate_screenshot(png(Image.new('RGB',(20,20))))

    def test_main_photo_detection_excludes_search_bar_and_filter_chips(self):
        screenshot=Image.new('RGB',(1200,900),'#202124');draw=ImageDraw.Draw(screenshot)
        draw.rounded_rectangle((180,20,1000,80),radius=24,fill='#404144')
        for x in (20,250,480):draw.rectangle((x,110,x+180,160),fill='#778899')
        expected=[(20,220,360,240),(400,220,360,240),(780,220,360,240),(20,520,360,240)]
        for index,(x,y,w,h) in enumerate(expected):screenshot.paste(picture(index,(w,h)),(x,y))
        tiles=detect_tiles(screenshot)
        self.assertEqual(len(tiles),4)
        self.assertTrue(all(t['box'][1]>=200 for t in tiles))
        self.assertEqual([t['id'] for t in tiles],[1,2,3,4])

    def test_heading_context_stops_before_the_next_card_in_its_column(self):
        screenshot=Image.new('RGB',(1200,900),'#202124')
        for index,x in enumerate((20,400,780)):
            screenshot.paste(picture(index,(360,240)),(x,200))
            screenshot.paste(picture(index+10,(360,240)),(x,490))
        tiles=detect_tiles(screenshot)
        for tile in tiles:
            if tile['box'][1]<400:
                self.assertLessEqual(tile['context_box'][1]+tile['context_box'][3],490)

    def test_same_photo_survives_resizing_and_crop_but_colour_alone_does_not_match(self):
        original=picture()
        reference=original.crop((30,25,600,390)).resize((285,182))
        self.assertTrue(similarity(reference,original)['matched'])
        self.assertFalse(similarity(reference,picture(17))['matched'])
        self.assertFalse(similarity(reference,Image.new('RGB',(640,420),'blue'))['matched'])

    def test_one_shared_picture_inside_a_collage_is_not_the_whole_collage(self):
        collage=Image.new('RGB',(1280,840))
        for index,(x,y) in enumerate(((0,0),(640,0),(0,420),(640,420))):collage.paste(picture(index+2),(x,y))
        reference=collage.resize((640,420))
        self.assertFalse(similarity(reference,picture(2))['matched'])
        source=picture(3)
        self.assertFalse(similarity(source,source.crop((0,0,640,240)))['matched'])

    def test_added_caption_banners_are_not_confirmed_as_the_unmodified_photo(self):
        source=picture(3);edited=source.copy()
        ImageDraw.Draw(edited).rectangle((0,330,640,420),fill='red')
        self.assertFalse(similarity(source,edited)['matched'])

    def test_framed_photos_report_resolution_of_matching_content_not_added_borders(self):
        source=picture(3);framed=Image.new('RGB',(1280,720),'gray');framed.paste(source,(320,150))
        match=similarity(source,framed)
        self.assertTrue(match['matched'])
        self.assertLess(abs(match['effective_width']-640),10)
        self.assertLess(abs(match['effective_height']-420),10)

    def test_bottom_edge_photos_do_not_merge_into_one_wide_tile(self):
        screenshot=Image.new('RGB',(1200,900),'#202124')
        for index,x in enumerate((20,400,780)):
            screenshot.paste(picture(index,(360,240)),(x,200))
            screenshot.paste(picture(index+10,(360,230)),(x,670))
        ImageDraw.Draw(screenshot).line((20,899,1140,899),fill='white',width=1)
        tiles=detect_tiles(screenshot)
        self.assertEqual(len(tiles),6)
        self.assertTrue(all(row['box'][2]<400 for row in tiles))

    def test_model_labels_bind_to_existing_tiles_and_cannot_add_commands_or_urls(self):
        tiles=[{'id':1,'box':[20,40,300,200]}]
        raw={'query':'MI 2020 IPL season','title':'MI 2020','photos':[{
            'id':1,'include':True,'caption':'Champions 2020','publisher':'Mumbai Indians',
            'query':'Mumbai Indians champions 2020 trophy team photo','description':'Team with trophy'}]}
        plan=normalise_reading(raw,tiles)
        self.assertEqual(plan['photos'][0]['box'],tiles[0]['box'])
        raw['photos'][0]['id']=99
        with self.assertRaises(ValueError):normalise_reading(raw,tiles)
        raw['photos'][0]['id']=1;raw['photos'][0]['query']='https://127.0.0.1/private'
        with self.assertRaises(ValueError):normalise_reading(raw,tiles)

    def test_filenames_cannot_escape_the_collection(self):
        name=photo_filename(1,'../../CON <script> Mumbai / Indians','abc12345','JPEG')
        self.assertTrue(name.startswith('001-'))
        self.assertEqual(Path(name).name,name)
        self.assertNotIn('..',name);self.assertTrue(name.endswith('.jpg'))

class PhotoTransportTests(unittest.TestCase):
    def test_redirect_to_private_network_is_blocked_before_connection(self):
        opened=[]
        def resolver(host,port):return ['93.184.216.34'] if host=='photos.example' else ['127.0.0.1']
        def opener(url,address,timeout):
            opened.append(url)
            response=Mock(status=302)
            response.getheader.side_effect=lambda key,default=None:{'Location':'http://private.example/secret'}.get(key,default)
            return response,Mock()
        fetcher=Fetcher(resolver=resolver,opener=opener)
        with self.assertRaisesRegex(ValueError,'public'):
            fetcher.get('https://photos.example/image.jpg')
        self.assertEqual(opened,['https://photos.example/image.jpg'])

    def test_bad_scheme_and_credentials_are_rejected_without_network(self):
        opener=Mock();fetcher=Fetcher(resolver=lambda *_:['93.184.216.34'],opener=opener)
        for url in ('file:///C:/Windows/win.ini','https://user:pass@photos.example/a.jpg','http://127.0.0.1/a'):
            with self.assertRaises(ValueError):fetcher.get(url)
        opener.assert_not_called()

    def test_oversized_response_is_stopped_before_body_read(self):
        response=Mock(status=200)
        response.getheader.side_effect=lambda key,default=None:{'Content-Type':'image/jpeg','Content-Length':'99999999'}.get(key,default)
        fetcher=Fetcher(resolver=lambda *_:['93.184.216.34'],opener=lambda *_:(response,Mock()))
        with self.assertRaisesRegex(ValueError,'large'):fetcher.get('https://photos.example/a.jpg',limit=1000)
        response.read.assert_not_called()

if __name__=='__main__':unittest.main()
