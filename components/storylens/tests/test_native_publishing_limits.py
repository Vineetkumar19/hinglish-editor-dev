"""Boundary checks for the production native decoder, not model-quality claims."""
import unittest
from hinglish_cut.native_schema import schema_parser
from jsonschema import validate,ValidationError

SCHEMA={'type':'object','additionalProperties':False,
        'properties':{'sentence_ids':{'type':'array','minItems':1,'maxItems':6,
                     'uniqueItems':True,'items':{'type':'integer','enum':list(range(79))}}},
        'required':['sentence_ids']}

def accepts(text,schema=SCHEMA):
    parser=schema_parser(schema)
    for char in text:
        if char not in parser.get_allowed_characters():return False
        parser=parser.add_character(char)
    return parser.can_end()

class NativeOutputLimits(unittest.TestCase):
    def test_six_complete_choices_can_finish(self):
        self.assertTrue(accepts('{"sentence_ids":[0,3,4,5,6,7]}'))
    def test_seventh_choice_cannot_be_generated(self):
        self.assertFalse(accepts('{"sentence_ids":[0,1,2,3,4,5,6]}'))
    def test_empty_selection_is_blocked(self):
        self.assertFalse(accepts('{"sentence_ids":[]}'))
    def test_nonexistent_source_id_is_blocked(self):
        self.assertFalse(accepts('{"sentence_ids":[99]}'))
    def test_unexpected_background_field_is_blocked(self):
        self.assertFalse(accepts('{"sentence_ids":[0],"documentary_style":"x"}'))
    def test_duplicate_choices_are_rejected_by_final_validator(self):
        with self.assertRaises(ValidationError):validate({'sentence_ids':[0,0]},SCHEMA)
    def test_fully_terminated_multi_digit_enums_are_counted_once(self):
        self.assertTrue(accepts('{"sentence_ids":[10,11,12,13,14,15]}'))
        self.assertFalse(accepts('{"sentence_ids":[10,11,12,13,14,15,16]}'))
    def test_nested_objects_and_quoted_commas_keep_their_own_counts(self):
        schema={'type':'array','minItems':5,'maxItems':5,'items':{'type':'object','properties':{'words':{'type':'array','minItems':2,'maxItems':2,'items':{'type':'string'}}},'required':['words'],'additionalProperties':False}}
        import json
        for count in (4,5,6):
            text=json.dumps([{'words':['hello, friend','another']}]*count,separators=(',',':'))
            self.assertEqual(accepts(text,schema),count==5)
    def test_short_explanations_are_bounded_and_cannot_repeat_newlines(self):
        import json
        from hinglish_shorts.find import pick_schema
        schema=pick_schema(3,[0,1,2,3,4])
        def answer(why='A complete hook with a payoff.',score=7,pieces=None):
            return json.dumps({'shorts':[{'why':why,'title':'A useful moment','pieces':pieces or [[0,3]],'score':score}]},separators=(',',':'))
        self.assertTrue(accepts(answer(),schema))
        self.assertFalse(accepts(answer('Repeat\n\n\n'),schema))
        self.assertFalse(accepts(answer('x'*241),schema))
        self.assertFalse(accepts(answer(score=11),schema))
        self.assertFalse(accepts(answer(pieces=[[0,99]]),schema))

if __name__=='__main__':unittest.main()
