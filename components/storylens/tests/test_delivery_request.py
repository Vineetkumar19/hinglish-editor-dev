import unittest
from hinglish_app.delivery_request import account_order,remaining_order,correction_text,destination_text
from hinglish_app.assistant_distribution import WORKFLOW
from hinglish_app.distribution_schedule import contract


class DeliveryRequestTests(unittest.TestCase):
    def test_account_quantities_are_additive_and_not_last_destination_wins(self):
        for text,expected in [
            ('upload 2 reels on cricket isnta page and 2 reel on gaming insta page',['cricket']*2+['gaming']*2),
            ('upload three videos on gaming and five reels on cricket',['gaming']*3+['cricket']*5),
            ('post 2 reels on each cricket and gaming account',['cricket']*2+['gaming']*2),
            ('post 6 saved reels alternating cricket and gaming',['cricket','gaming']*3)]:
            self.assertEqual(account_order(text,WORKFLOW),expected)

    def test_scope_repair_preserves_already_completed_gaming_deliveries(self):
        self.assertEqual(remaining_order(['cricket']*2+['gaming']*2,['gaming']*2),['cricket']*2)
        with self.assertRaises(ValueError):remaining_order(['cricket']*2,['gaming'])

    def test_post_now_answer_keeps_the_missing_cricket_destination(self):
        snapshot={'active_request_message_id':'new','messages':[
            {'id':'old','role':'user','text':'u only posted on gaming page, what about cricket paage'},
            {'id':'new','role':'user','text':'dont schedule .. post now'}]}
        text=correction_text(snapshot,'dont schedule .. post now',WORKFLOW)
        self.assertIn('what about cricket',text)
        self.assertEqual(destination_text(text),' cricket paage')
        self.assertTrue(contract(text,WORKFLOW)['immediate_all'])
