"""Pinned LMFE compatibility for arrays whose enum items finish immediately."""
import re


def _single_line_shortcut():
    """Cache bounded single-line vocabulary instead of traversing it per token.

    LMFE's ordinary JSON free-text shortcut explicitly excludes regex strings.
    Our exact [^CRLF]{min,max} fields otherwise walk the entire 150k vocabulary
    at each character count. Keep the original strict parser for all boundaries
    and other regexes; cache only tokens that remain inside this one string.
    """
    from lmformatenforcer import JsonSchemaParser
    from lmformatenforcer.jsonschemaparser import StringParsingState
    from lmformatenforcer.tokenenforcer import TokenEnforcer
    from lmformatenforcer.tokenizerprefixtree import JsonFreetextTokenCache
    if getattr(TokenEnforcer,'_storylens_single_line_fix',False):
        return
    original=TokenEnforcer._collect_allowed_tokens

    def collect(self,parser,node,allowed,shortcut):
        current=parser.object_stack[-1] if isinstance(parser,JsonSchemaParser) and parser.object_stack else None
        match=(re.fullmatch(r'\[\^\\r\\n\]\{(\d+),(\d+)\}',current.pattern or '')
               if isinstance(current,StringParsingState) and current.seen_opening_quote
               and not current.seen_closing_quote else None)
        if node is not self.tokenizer_tree.root or not match:
            return original(self,parser,node,allowed,shortcut)
        cache=getattr(self.tokenizer_tree,'_storylens_single_line_tokens',None)
        if cache is None:
            cache=JsonFreetextTokenCache(self.use_bitmask,self.vocab_size)
            for number,value in self.tokenizer_tree.tokens_to_strs.items():
                # Escapes and interior quotes need full structural parsing, so
                # they are deliberately absent from the cached inner-string set.
                if value and not any(c in value for c in '\r\n\\') and '"' not in value[:-1]:
                    cache.add_token(value,number)
            cache.freeze()
            self.tokenizer_tree._storylens_single_line_tokens=cache
        minimum,maximum=map(int,match.groups());length=len(current.parsed_string)
        allowed.extend(cache.lookup_allowed_tokens(max(0,minimum-length),max(0,maximum-length)).allowed_tokens)
        # A token beginning with the closing quote may also contain a comma,
        # brace or the next field. Let the original parser validate all of it.
        if '"' in parser.get_allowed_characters() and '"' in node.children:
            original(self,parser.add_character('"'),node.children['"'],allowed,None)
    TokenEnforcer._collect_allowed_tokens=collect
    TokenEnforcer._storylens_single_line_fix=True

def schema_parser(schema):
    _single_line_shortcut()
    from lmformatenforcer import JsonSchemaParser
    from lmformatenforcer.jsonschemaparser import ListParsingState
    if not getattr(ListParsingState,'_storylens_count_fix',False):
        original=ListParsingState.add_character
        def add_character(self,char):
            result=original(self,char)
            if char==',' and not self.seen_list_closer:
                # LMFE 0.11.3 counts a completed enum both when its parser is
                # popped and at the following comma. At a delimiter the number
                # of completed entries equals this list's own comma count.
                # Nested/string commas are handled by their own parsers.
                result.num_items_seen=result.parsed_string.count(',')
            return result
        ListParsingState.add_character=add_character
        ListParsingState._storylens_count_fix=True
    return JsonSchemaParser(schema)
