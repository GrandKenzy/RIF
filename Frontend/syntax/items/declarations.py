from gram import combinators as cmb
from gram import lexer

from .values import CALL_VALUE, TABLE_ACCESS, VALUE


class TOKEN(cmb.RuleItem):
    nodeable = True
    description = "Referencia sintáctica a un token por nombre o número."
    entrypoint = cmb.Alt(
        cmb.MatchGroup("token_names"),
        cmb.MatchToken("NUMBER"),
    )


class TABLE_MATCHER(cmb.RuleItem):
    nodeable = True
    description = "Relaciona una columna de tabla con un token esperado."
    entrypoint = cmb.Seq(
        cmb.MatchToken("ARROW"),
        cmb.Ref(TABLE_ACCESS),
        cmb.MatchToken("COMMA"),
        cmb.Ref(TOKEN),
        cmb.MatchToken("NEWLINE"),
    )


class CONSUMER(cmb.RuleItem):
    nodeable = False
    description = "Consume un token declarado por nombre o número."
    entrypoint = cmb.Seq(
        cmb.MatchToken("ARROW"),
        cmb.Ref(TOKEN),
        cmb.MatchToken("NEWLINE"),
    )


class STORE(cmb.RuleItem):
    nodeable = True
    description = "Declara una lista de tokens candidatos para almacenar."
    entrypoint = cmb.Seq(
        cmb.MatchToken("ARROW"),
        cmb.Enclosed(
            open=lexer.Token.LBRACKET,
            content=cmb.Separator(
                values=[cmb.Ref(TOKEN)],
                sep=lexer.Token.COMMA,
                min=1,
                allow_trailing=False,
            ),
            close=lexer.Token.RBRACKET,
            allow_empty=False,
        ),
        cmb.MatchToken("NEWLINE"),
    )


class PUT(cmb.RuleItem):
    nodeable = True
    description = "Declara dos valores consecutivos para una operación put."
    entrypoint = cmb.Seq(
        cmb.MatchToken("ARROW"),
        cmb.MatchKeyword("put"),
        cmb.Ref(VALUE),
        cmb.Ref(VALUE),
        cmb.MatchToken("NEWLINE"),
    )


class EBIT(cmb.RuleItem):
    nodeable = True
    entrypoint = cmb.Seq(
        cmb.MatchToken("ARROW"),
        cmb.MatchKeyword("ebit"),
        cmb.Ref(VALUE),
        cmb.Ref(VALUE),
        cmb.Ref(VALUE),
        cmb.Ref(VALUE),
        cmb.Ref(VALUE),
        cmb.Ref(VALUE),
        cmb.Ref(VALUE),
        cmb.Ref(VALUE),
        cmb.MatchToken("NEWLINE"),
    )


class EMMIT(cmb.RuleItem):
    nodeable = True
    description = "Emite un único valor."
    entrypoint = cmb.Seq(
        cmb.MatchToken("ARROW"),
        cmb.MatchKeyword("emmit"),
        cmb.Ref(VALUE),
        cmb.MatchToken("NEWLINE"),
    )


class DEFINE(cmb.RuleItem):
    nodeable = True
    description = "Declara un nombre reutilizable del lenguaje."
    entrypoint = cmb.Seq(
        cmb.MatchToken("AT"),
        cmb.MatchKeyword("define"),
        cmb.MatchToken("IDENT"),
        cmb.MatchToken("NEWLINE"),
    )


class KW(cmb.RuleItem):
    nodeable = True
    description = "Declara un keyword literal que debe coincidir exactamente."
    entrypoint = cmb.Seq(
        cmb.MatchToken("ARROW"),
        cmb.MatchKeyword("KW"),
        cmb.MatchToken("STRING"),
        cmb.MatchToken("NEWLINE"),
    )


class JMP(cmb.RuleItem):
    nodeable = True
    description = "Salta sintácticamente a otra regla por nombre."
    entrypoint = cmb.Seq(
        cmb.MatchToken("ARROW"),
        cmb.MatchKeyword("JMP"),
        cmb.MatchToken("IDENT"),
        cmb.MatchToken("NEWLINE"),
    )


class SAVE(cmb.RuleItem):
    nodeable = True
    description = "Guarda sintácticamente el token actual bajo una etiqueta."
    entrypoint = cmb.Seq(
        cmb.MatchToken("ARROW"),
        cmb.MatchKeyword("save"),
        cmb.MatchToken("STRING"),
        cmb.MatchToken("NEWLINE"),
    )


class LOAD(cmb.RuleItem):
    nodeable = True
    description = "Carga sintácticamente un token identificado por etiqueta."
    entrypoint = cmb.Seq(
        cmb.MatchToken("ARROW"),
        cmb.MatchKeyword("load"),
        cmb.MatchToken("STRING"),
        cmb.MatchToken("NEWLINE"),
    )


class RESERVE(cmb.RuleItem):
    nodeable = True
    description = "Reserva un espacio etiquetado con un tamaño declarado."
    entrypoint = cmb.Seq(
        cmb.MatchToken("ARROW"),
        cmb.MatchKeyword("reserve"),
        cmb.MatchToken("STRING"),
        cmb.MatchToken("NUMBER"),
        cmb.MatchToken("NEWLINE"),
    )


class LDRES(cmb.RuleItem):
    nodeable = True
    description = "Carga un valor en una reserva etiquetada."
    entrypoint = cmb.Seq(
        cmb.MatchToken("ARROW"),
        cmb.MatchKeyword("ldres"),
        cmb.MatchToken("STRING"),
        cmb.Ref(VALUE),
        cmb.MatchToken("NEWLINE"),
    )


class DLRES(cmb.RuleItem):
    nodeable = True
    description = "Elimina una reserva del espacio de nombres."
    entrypoint = cmb.Seq(
        cmb.MatchToken("ARROW"),
        cmb.MatchKeyword("dlres"),
        cmb.MatchToken("STRING"),
        cmb.MatchToken("NEWLINE"),
    )


class GTRES(cmb.RuleItem):
    nodeable = True
    description = "Inserta una reserva etiquetada en el flujo actual."
    entrypoint = cmb.Seq(
        cmb.MatchToken("ARROW"),
        cmb.MatchKeyword("gtres"),
        cmb.MatchToken("STRING"),
        cmb.MatchToken("NEWLINE"),
    )


class JMPIF(cmb.RuleItem):
    nodeable = True
    description = "Salta a una regla cuando una condición booleana o externa es verdadera."
    entrypoint = cmb.Seq(
        cmb.MatchToken("ARROW"),
        cmb.MatchKeyword("jmpif"),
        cmb.MatchToken("IDENT"),
        cmb.MatchToken("COMMA"),
        cmb.Alt(
            cmb.MatchToken("BOOL"),
            cmb.Ref(CALL_VALUE),
        ),
        cmb.MatchToken("NEWLINE"),
    )


class BREAK(cmb.RuleItem):
    nodeable = True
    description = "Rompe el flujo actual y retorna al contexto de salto."
    entrypoint = cmb.Seq(
        cmb.MatchToken("ARROW"),
        cmb.MatchKeyword("break"),
        cmb.MatchToken("NEWLINE"),
    )


class ERROR(cmb.RuleItem):
    nodeable = True
    description = "Declara un mensaje de error literal."
    entrypoint = cmb.Seq(
        cmb.MatchToken("ARROW"),
        cmb.MatchKeyword("error"),
        cmb.MatchToken("COMMA"),
        cmb.MatchToken("STRING"),
        cmb.MatchToken("NEWLINE"),
    )


class CALL(cmb.RuleItem):
    nodeable = True
    description = "Ejecuta una llamada externa dentro del flujo."
    entrypoint = cmb.Seq(
        cmb.MatchToken("ARROW"),
        cmb.MatchKeyword("CALL"),
        cmb.Ref(CALL_VALUE),
        cmb.MatchToken("NEWLINE"),
    )


class EMITFR_LINE(cmb.RuleItem):
    nodeable = False
    description = "Línea de valores de un frame de emisión."
    entrypoint = cmb.Seq(
        cmb.Some(cmb.Ref(VALUE)),
        cmb.MatchToken("NEWLINE"),
    )


class EMITFREND(cmb.RuleItem):
    nodeable = False
    description = "Cierre sintáctico de un frame de emisión."
    entrypoint = cmb.Seq(
        cmb.MatchToken("ARROW"),
        cmb.MatchKeyword("emitfrend"),
        cmb.MatchToken("NEWLINE"),
    )


class EMITFR(cmb.RuleItem):
    nodeable = True
    description = "Emite un frame multilinea delimitado de valores."
    entrypoint = cmb.Seq(
        cmb.MatchToken("ARROW"),
        cmb.MatchKeyword("emitfr"),
        cmb.Some(cmb.Ref(VALUE)),
        cmb.MatchToken("NEWLINE"),
        cmb.Many(cmb.Ref(EMITFR_LINE)),
        cmb.Ref(EMITFREND),
    )


class RULE(cmb.RuleItem):
    nodeable = True
    description = "Declara una regla con operaciones delimitadas por líneas."
    entrypoint = cmb.Seq(
        cmb.MatchToken("AT"),
        cmb.MatchKeyword("rule"),
        cmb.MatchToken("IDENT"),
        cmb.MatchToken("COLON"),
        cmb.MatchToken("NEWLINE"),
        cmb.Many(
            cmb.Alt(
                cmb.Ref(TABLE_MATCHER),
                cmb.Ref(CONSUMER),
                cmb.Ref(STORE),
                cmb.Ref(PUT),
                cmb.Ref(EBIT),
                cmb.Ref(EMMIT),
                cmb.Ref(KW),
                cmb.Ref(JMP),
                cmb.Ref(SAVE),
                cmb.Ref(LOAD),
                cmb.Ref(RESERVE),
                cmb.Ref(LDRES),
                cmb.Ref(DLRES),
                cmb.Ref(GTRES),
                cmb.Ref(JMPIF),
                cmb.Ref(BREAK),
                cmb.Ref(ERROR),
                cmb.Ref(CALL),
                cmb.Ref(EMITFR),
            )
        ),
    )


class STACK(cmb.RuleItem):
    nodeable = True
    description = "Declara sintácticamente el tamaño del array de slots."
    entrypoint = cmb.Seq(
        cmb.MatchToken("AT"),
        cmb.MatchKeyword("stack"),
        cmb.Alt(
            cmb.MatchToken("NUMBER"),
            cmb.Seq(
                cmb.MatchToken("MINUS"),
                cmb.MatchToken("NUMBER"),
            ),
        ),
        cmb.MatchToken("NEWLINE"),
    )


__all__ = [
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
]
