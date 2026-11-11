"""CPU-only vocabulary filtering checks; never loads model weights."""
import json
import unittest

from hinglish_cut.native_schema import schema_parser


class SingleLineDecoder(unittest.TestCase):
    def setUp(self):
        from lmformatenforcer.tokenenforcer import TokenEnforcer,TokenEnforcerTokenizerData
        self.schema={'type':'object','properties':{'text':{'type':'string','pattern':r'^[^\r\n]{1,4}$'}},
                     'required':['text'],'additionalProperties':False}
        self.values=['a','ab','abcd','abcde','"','a"','a",','"}', '\\n','\n','\r','b','{','}',' ',':',',']
        data=TokenEnforcerTokenizerData([(i,s,False) for i,s in enumerate(self.values)],
                                       lambda ids:''.join(self.values[i] for i in ids),99,False,100)
        self.enforcer=TokenEnforcer(data,schema_parser(self.schema))

    def allowed(self,prefix):
        from lmformatenforcer.tokenlist import TokenList
        parser=schema_parser(self.schema)
        for char in prefix:
            self.assertIn(char,parser.get_allowed_characters())
            parser=parser.add_character(char)
        tokens=TokenList(False,100)
        self.enforcer._collect_allowed_tokens(parser,self.enforcer.tokenizer_tree.root,tokens,None)
        return {self.values[i] for i in tokens.allowed_tokens}

    def test_content_and_quote_lengths_and_single_line_boundaries(self):
        before=self.allowed('{"text":"')
        self.assertTrue({'a','ab','abcd','a"'}<=before)
        self.assertFalse({'abcde','"','\\n','\n','\r'} & before)
        end=self.allowed('{"text":"abcd')
        self.assertIn('"',end);self.assertIn('"}',end)
        self.assertFalse({'a','ab','abcd','a"','\\n','\n'} & end)

    def test_every_cached_token_is_accepted_by_original_parser(self):
        for prefix in ['{"text":"','{"text":"a','{"text":"abc','{"text":"abcd']:
            for token in self.allowed(prefix):
                parser=schema_parser(self.schema)
                for char in prefix+token:
                    self.assertIn(char,parser.get_allowed_characters(),(prefix,token,char))
                    parser=parser.add_character(char)

    def test_other_patterns_keep_the_original_rules(self):
        schema={'type':'string','pattern':'^[A-Z]{2}$'}
        parser=schema_parser(schema)
        for char in '"AB"':
            self.assertIn(char,parser.get_allowed_characters());parser=parser.add_character(char)
        self.assertTrue(parser.can_end())


if __name__=='__main__':unittest.main()
