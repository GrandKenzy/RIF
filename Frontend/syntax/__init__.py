from gram import combinators as cmb
from gram import sessions


RIF_LANG_SESSION = sessions.Session("RIF_LANG_SESSION", "Many")
RIF_LANG_SESSION.clear_global()
RIF_LANG_SESSION.init()

from . import keywords
from .items.declarations import (
    CONSUMER,
    CALL,
    BREAK,
    DEFINE,
    ERROR,
    EBIT,
    EMMIT,
    EMITFR,
    EMITFREND,
    JMP,
    JMPIF,
    KW,
    LOAD,
    DLRES,
    GTRES,
    LDRES,
    PUT,
    RESERVE,
    RULE,
    SAVE,
    STORE,
    STACK,
    TABLE_MATCHER,
    TOKEN,
)
from .items.table import TABLE
from .items.values import CALL_VALUE, RESERVATION_ACCESS, TABLE_ACCESS, VALUE


VALUE.entrypoint = cmb.Alt(
    cmb.Ref(TABLE_ACCESS),
    cmb.Ref(RESERVATION_ACCESS),
    cmb.Ref(CALL_VALUE),
    cmb.MatchToken("NUMBER"),
    cmb.MatchToken("IDENT"),
    cmb.MatchToken("STRING"),
    cmb.MatchToken("BOOL"),
)


class ENTRYPOINT(cmb.RuleItem):
    entrypoint = cmb.Alt(
        cmb.Ref(TABLE),
        cmb.Ref(DEFINE),
        cmb.Ref(RULE),
        cmb.Ref(STACK),
    )


RIF_LANG_SESSION.entrypoint = ENTRYPOINT


RIF_LANG_SESSION.migrate()


__all__ = [
    "RIF_LANG_SESSION",
    "keywords",
    "TABLE",
    "DEFINE",
    "RULE",
    "TABLE_MATCHER",
    "CONSUMER",
    "STORE",
    "PUT",
    "EBIT",
    "EMMIT",
    "KW",
    "JMP",
    "SAVE",
    "LOAD",
    "STACK",
    "RESERVE",
    "LDRES",
    "DLRES",
    "GTRES",
    "JMPIF",
    "BREAK",
    "ERROR",
    "CALL",
    "EMITFR",
    "EMITFREND",
    "TOKEN",
    "TABLE_ACCESS",
    "RESERVATION_ACCESS",
    "CALL_VALUE",
    "ENTRYPOINT",
]
