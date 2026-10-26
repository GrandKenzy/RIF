from gram import config
from gram import lexer

config.LEXER_COMMENT_TOKEN = ";"
config.LEXER_IGNORE_NEWLINES = False
config.SUPPORT_INDENT = False

word = lexer.words
word.add_group("keywords")
word.add_keyword("table", group="keywords")
word.add_keyword("end", group="keywords")
word.add_keyword("define", group="keywords")
word.add_keyword("rule", group="keywords")
word.add_keyword("put", group="keywords")
word.add_keyword("ebit", group="keywords")
word.add_keyword("emmit", group="keywords")
word.add_keyword("KW", group="keywords")
word.add_keyword("JMP", group="keywords")
word.add_keyword("stack", group="keywords")
word.add_keyword("save", group="keywords")
word.add_keyword("load", group="keywords")
word.add_keyword("reserve", group="keywords")
word.add_keyword("ldres", group="keywords")
word.add_keyword("dlres", group="keywords")
word.add_keyword("gtres", group="keywords")
word.add_keyword("jmpif", group="keywords")
word.add_keyword("call", group="keywords")
word.add_keyword("CALL", group="keywords")
word.add_keyword("break", group="keywords")
word.add_keyword("error", group="keywords")
word.add_keyword("emitfr", group="keywords")
word.add_keyword("emitfrend", group="keywords")

word.add_group("token_names")
for token in lexer.Token:
    word.add_keyword(token.name, group="token_names")
