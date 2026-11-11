import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from hinglish_eval.specs import Check, evaluate


class ScriptQualityTests(unittest.TestCase):
    def test_valid_xml_cannot_make_an_incomplete_script_pass(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'EDITED_SEQUENCE.xml').touch()
            for complete in (False,True):
                (root/'report.json').write_text(json.dumps({'kind':'assemble','errors':[],
                    'rows':[{'selected':{'span':{}}},{'selected':{'span':{}} if complete else None}]}))
                with patch('hinglish_eval.specs.check_xml',return_value=[Check('xml.valid','Valid XML',True)]):
                    result=evaluate(root)
                self.assertEqual(result[0].feature,'script')
                self.assertEqual(result[0].passed,complete)
                if not complete:self.assertLess(result[0].score,100)


if __name__=='__main__':unittest.main()
