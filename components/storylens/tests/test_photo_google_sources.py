import unittest
from hinglish_photos.sources import indexed_images

class ImageIndexTests(unittest.TestCase):
    def test_public_image_tuples_return_full_sources_and_ignore_small_thumbnails(self):
        html=r'''<script>data=[["https://encrypted-tbn0.gstatic.com/small.jpg",160,200],["https://publisher.example/original.jpg?x=1\u0026y=2",3000,2000],["http://127.0.0.1/private.png",2000,2000]];</script>'''
        values=indexed_images(html)
        self.assertEqual(len(values),1);self.assertEqual(values[0]['url'],'https://publisher.example/original.jpg?x=1&y=2')
        self.assertEqual(values[0]['width'],3000)
    def test_challenge_pages_are_reported_without_trying_to_solve_them(self):
        with self.assertRaisesRegex(ValueError,'unavailable'):indexed_images('<html>Our systems have detected unusual traffic</html>')
        with self.assertRaisesRegex(ValueError,'unavailable'):indexed_images('<noscript><a href="/httpservice/retry/enablejs">enable JavaScript</a></noscript>')

if __name__=='__main__':unittest.main()
