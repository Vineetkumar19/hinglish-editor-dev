import unittest
from unittest.mock import Mock, patch
from hinglish_app.assistant_upload_workflow import supervise


class BufferedDeliveryStartup(unittest.TestCase):
    def test_restore_buffer_without_active_chats_or_page_visits(self):
        assistant=Mock();assistant.folder.glob.return_value=[]
        stop=Mock();stop.wait.side_effect=[False,True]
        with patch('hinglish_app.prepare_post_http.service') as service:
            supervise(assistant,stop)
        service.assert_called_once_with(assistant.state,recover_delivery=True)
        assistant.snapshot.assert_not_called()

    def test_buffer_recovery_error_does_not_resume_or_reauthorize_anything(self):
        assistant=Mock();assistant.folder.glob.return_value=[]
        stop=Mock();stop.wait.side_effect=[False,True]
        with patch('hinglish_app.prepare_post_http.service',side_effect=RuntimeError('fixture offline')), \
             patch('logging.Logger.exception') as log:
            supervise(assistant,stop)
        log.assert_called_once()
        assistant.snapshot.assert_not_called()


if __name__=='__main__':unittest.main()
