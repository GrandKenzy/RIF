from gram import config
from gram import lexer

config.LEXER_COMMENT_TOKEN = ";"
config.LEXER_IGNORE_NEWLINES = False
config.SUPPORT_INDENT = False

word = lexer.words
word.add_group("keywords")
INSTRUCTION_OPCODES = {
    name: name
    for name in (
        "put", "ebit", "emmit", "save", "load", "reserve", "ldres",
        "dlres", "gtres", "jmpif", "break", "error", "emitfr",
        "padding", "alignement", "fits", "iffits", "ifnfits",
        "vpadding", "vreserve", "dsave", "dload", "dpop",
        "emitbits", "readbits", "patchbits", "valignement",
    )
}
INSTRUCTION_OPCODES.update({"KW": "kw", "JMP": "jmp", "CALL": "call"})
for keyword in (
    "table", "end", "define", "rule", "stack", "call", "emitfrend",
    "insert", "before",
    "dpeek", "reswidth", "vreswidth", "DDEPTH", "dist", "vdist",
    "resdir", "resvdir", "resdist", "resvdist", "SIZE", "VSIZE",
    "ALIGNMENT", "config", "configend", "linker", "linkerend", "LOAD",
    *INSTRUCTION_OPCODES,
):
    word.add_keyword(keyword, group="keywords")
word.add_group("variant_keywords")
word.add_keyword("SUPPORTS", group="variant_keywords")
word.add_keyword("ASMVARIANT", group="variant_keywords")
word.add_keyword("END", group="variant_keywords")
word.add_keyword("MODE", group="variant_keywords")
word.add_keyword("SWITCH", group="variant_keywords")
word.add_keyword("ENCAPSULATE", group="variant_keywords")
word.add_keyword("ENTER", group="variant_keywords")
word.add_keyword("EXIT", group="variant_keywords")

word.add_group("token_names")
for token in lexer.Token:
    word.add_keyword(token.name, group="token_names")
