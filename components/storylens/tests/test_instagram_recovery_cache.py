import unittest
from unittest.mock import patch
from hinglish_publish.prepare_post_source import recover_instagram

class RecoveryFeedback(unittest.TestCase):
    def test_failed_response_is_rejected_and_supplied_to_next_attempt(self):
        bad={'caption_words':['Kolkata','sets','records.'],'instagram_hashtags':['Kolkata','Cricket','Batting']}
        good={'caption_words':['Explore',"Kolkata's",'batting','performance.'],'instagram_hashtags':['Kolkata','Cricket','Batting']}
        class Brain:
            def __init__(self):self.calls=[];self.rejected=[]
            def json(self,system,data,schema,**kwargs):
                self.calls.append(dict(data));return bad if len(self.calls)==1 else good
            def reject_result(self,value,error):self.rejected.append((value,error))
        brain=Brain()
        with patch('hinglish_publish.metadata.review_grounding'),patch('hinglish_publish.metadata.validate_source_copy'):
            result=recover_instagram(brain,{'title':'Kolkata batting'},'Kolkata batting performance',{}, {},lambda _:None)
        self.assertEqual(len(brain.rejected),1)
        self.assertIs(brain.rejected[0][0],bad)
        self.assertEqual(brain.calls[1]['rejected_draft'],bad)
        self.assertIn('record',brain.calls[1]['correction'])
        self.assertIn('batting performance',result['instagram_caption'])

    def test_exhaustion_rejects_both_answers(self):
        class Brain:
            def __init__(self):self.rejected=[]
            def json(self,*args,**kwargs):return {'caption_words':['too many words in one item'],'instagram_hashtags':['Cricket','Batting','Kolkata']}
            def reject_result(self,value,error):self.rejected.append(error)
        brain=Brain()
        with self.assertRaisesRegex(ValueError,'could not finish reliable'):
            recover_instagram(brain,{},'Kolkata batting',{}, {},lambda _:None)
        self.assertEqual(len(brain.rejected),2)

if __name__=='__main__':unittest.main()
