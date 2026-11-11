import unittest
from tools.template_font_audit import extract_aep_fonts, decode_literal


class TemplateFontAuditTests(unittest.TestCase):
    def test_malformed_reference_does_not_abort_valid_fonts_or_the_library_scan(self):
        errors=[]
        bad=b'/CoolTypeFont /0 << /0 (\xfe\xffA)'
        good=b'/CoolTypeFont /0 << /0 (Roboto-Bold)'
        self.assertEqual(extract_aep_fonts(bad+good,errors),['Roboto-Bold'])
        self.assertEqual(len(errors),1)

    def test_utf16_postscript_names_and_internal_font_exclusion(self):
        def entry(name):
            return b'/99 /CoolTypeFont /0 << /0 (' + b'\xfe\xff' + name.encode('utf-16-be') + b') /2 0 >>'
        data = entry('Oswald-Bold') + entry('AdobeInvisFont') + entry('Oswald-Bold')
        self.assertEqual(extract_aep_fonts(data), ['Oswald-Bold'])

    def test_postscript_literal_escaped_parentheses_and_backslash(self):
        self.assertEqual(decode_literal(br'A\(B\)\\C\040D'), b'A(B)\\C D')

    def test_empty_or_non_project_does_not_invent_fonts(self):
        self.assertEqual(extract_aep_fonts(b'Font instructions: Arial'), [])
