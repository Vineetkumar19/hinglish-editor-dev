import unittest
from hinglish_broll import report


class EmptyReportTests(unittest.TestCase):
    def test_rejected_video_checks_are_not_reported_as_stock_unavailability(self):
        slot={'checks':[{'id':'one','producer_stage':'original'},{'id':'one','producer_stage':'prepared'},
                        {'id':'two','producer_stage':'original'}],
              'attempted':[{'id':'one'},{'id':'two'},{'id':'download-failed'}]}
        message=report.empty_bank_status(slot)
        self.assertIn('2 videos checked',message)
        self.assertIn('checks',message)
        self.assertNotIn('No downloadable',message)

    def test_download_attempts_and_no_attempts_are_distinct(self):
        tried=report.empty_bank_status({'attempted':[{'id':'one'},{'id':'two'}]})
        empty=report.empty_bank_status({})
        self.assertIn('2 sources tried',tried)
        self.assertNotEqual(tried,empty)


if __name__=='__main__':unittest.main()
