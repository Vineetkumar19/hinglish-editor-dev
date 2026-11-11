import unittest
from hinglish_photos.sources import original_urls,ImagesInPage

class OriginalSourceTests(unittest.TestCase):
    def test_only_known_public_image_transformations_are_removed(self):
        url='https://img1.hscicdn.com/image/upload/f_auto,t_ds_w_640/lsci/db/PICTURES/CMS/123.jpg'
        self.assertEqual(original_urls(url)[0],'https://img1.hscicdn.com/image/upload/lsci/db/PICTURES/CMS/123.jpg')
        query='https://images.news18.com/ibnlive/uploads/2020/team.jpg?width=640&height=360&impolicy=website&article=42'
        self.assertEqual(original_urls(query)[0],'https://images.news18.com/ibnlive/uploads/2020/team.jpg?article=42')
        private='https://private.example/photo.jpg?width=640&token=keep'
        self.assertEqual(original_urls(private),[private])
        legacy='https://images.hindustantimes.com/rf/image_size_960x540/HT/p2/2020/team.jpg'
        self.assertEqual(original_urls(legacy)[0],'https://images.hindustantimes.com/rf/HT/p2/2020/team.jpg')
    def test_responsive_source_uses_largest_width_not_last_srcset_entry(self):
        parser=ImagesInPage('https://publisher.example/story')
        parser.feed('<img src="small.jpg" srcset="original.jpg 2400w, mid.jpg 1200w, tiny.jpg 300w">')
        self.assertEqual(parser.images[0],'https://publisher.example/original.jpg')

if __name__=='__main__':unittest.main()
