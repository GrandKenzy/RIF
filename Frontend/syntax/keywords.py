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
        "nibbles", "emit", "eword", "save", "load", "reserve", "write_res",
        "drop_res", "emit_res", "frame",
        "pad", "align", "fit", "fit_exact", "fit_not",
        "fit_signed", "fit_signed_exact", "fit_signed_not",
        "vpad", "vreserve", "dpush", "dget", "dpop",
        "bits", "read_bits", "patch_bits", "valign", "mark", "fixup",
        "arm_imm8", "arm_imm_rotate",
    )
}
INSTRUCTION_OPCODES.update({"KW": "kw", "JUMP": "jump"})
INSTRUCTION_OPCODES.update({"JUMPIF": "jumpif", "BREAK": "break", "ERROR": "error"})
KEYWORD_NAMES = (
    "table", "end", "block", "define", "rule", "stack", "call",
    "insert", "before",
    "reswidth", "vreswidth", "dist", "vdist",
    "resdir", "resvdir", "resdist", "resvdist", "SIZE", "VSIZE",
    "ALIGNMENT", "LOAD", "LIBRARY",
)
for keyword in KEYWORD_NAMES:
    word.add_keyword(keyword, group="keywords")
word.add_group("variant_keywords")
VARIANT_KEYWORD_NAMES = (
    "SUPPORTS", "ASMVARIANT", "END", "MODE", "SWITCH", "ENCAPSULATE",
    "ENTER", "EXIT",
)
for keyword in VARIANT_KEYWORD_NAMES:
    word.add_keyword(keyword, group="variant_keywords")

word.add_group("token_names")
for token in lexer.Token:
    word.add_keyword(token.name, group="token_names")


# These names are part of RIF's own language, not target vocabulary.  Keep
# them in one registry so a target cannot shadow an opcode or grammar keyword
# with a Rule, table, block, define, or variant name.  ``frameend`` is a
# syntax-level operation selected by a dedicated parser item rather than the
# public opcode map.
RIF_RESERVED_NAMES = frozenset(
    name.casefold()
    for name in (
        *INSTRUCTION_OPCODES.keys(),
        *INSTRUCTION_OPCODES.values(),
        *KEYWORD_NAMES,
        *VARIANT_KEYWORD_NAMES,
        *(token.name for token in lexer.Token),
        "dpeek",
        "ddepth",
        "frameend",
    )
)


def validate_user_name(name: str, declaration: str) -> None:
    """Reject declarations that would shadow RIF syntax or opcodes."""

    if name.casefold() in RIF_RESERVED_NAMES:
        raise RuntimeError(
            f"El nombre de {declaration} '{name}' está reservado por RIF."
        )


__all__ = [
    "INSTRUCTION_OPCODES",
    "KEYWORD_NAMES",
    "VARIANT_KEYWORD_NAMES",
    "RIF_RESERVED_NAMES",
    "validate_user_name",
]
