from gram import combinators as cmb
from gram import lexer

from .values import CALL_VALUE, TABLE_ACCESS, VALUE
from .instructions import INSTRUCTION


def _directive(name: str):
    """Match a dotted config/linker directive without reserving its name globally."""
    return cmb.Req("IDENT").equal(name)


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


class PADDING(cmb.RuleItem):
    nodeable = True
    description = "Inserta una cantidad explícita de ceros y la registra como padding."
    entrypoint = cmb.Seq(
        cmb.MatchToken("ARROW"),
        cmb.MatchKeyword("padding"),
        cmb.MatchToken("NUMBER"),
        cmb.MatchToken("NEWLINE"),
    )


class ALIGNEMENT(cmb.RuleItem):
    nodeable = True
    description = "Alinea la posición actual insertando el padding necesario."
    entrypoint = cmb.Seq(
        cmb.MatchToken("ARROW"),
        cmb.MatchKeyword("alignement"),
        cmb.MatchToken("NUMBER"),
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
        cmb.Many(cmb.Ref(INSTRUCTION)),
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


class SECTIONDEF(cmb.RuleItem):
    nodeable = True
    description = "Define la directiva que abre una sección del ensamblador."
    entrypoint = cmb.Seq(
        cmb.MatchToken("DOT"),
        _directive("sectiondef"),
        cmb.MatchToken("STRING"),
        cmb.MatchToken("NEWLINE"),
    )


class MAKE_SECTION(cmb.RuleItem):
    nodeable = True
    description = "Declara una sección válida del ensamblador."
    entrypoint = cmb.Seq(
        cmb.MatchToken("DOT"),
        _directive("make"),
        _directive("section"),
        cmb.MatchToken("STRING"),
        cmb.MatchToken("NEWLINE"),
    )


class SECTIONEND(cmb.RuleItem):
    nodeable = True
    description = "Define el terminador de una cabecera de sección."
    entrypoint = cmb.Seq(
        cmb.MatchToken("DOT"),
        _directive("sectionend"),
        cmb.MatchToken("STRING"),
        cmb.MatchToken("NEWLINE"),
    )


class ENTRYSECTION(cmb.RuleItem):
    nodeable = True
    description = "Selecciona la sección de entrada del programa."
    entrypoint = cmb.Seq(
        cmb.MatchToken("DOT"),
        _directive("entrysection"),
        cmb.MatchToken("STRING"),
        cmb.MatchToken("NEWLINE"),
    )


class ENTRYLABEL(cmb.RuleItem):
    nodeable = True
    description = "Define el label de entrada del programa."
    entrypoint = cmb.Seq(
        cmb.MatchToken("DOT"),
        _directive("entrylabel"),
        cmb.MatchToken("STRING"),
        cmb.MatchToken("NEWLINE"),
    )


class COMMENT(cmb.RuleItem):
    nodeable = True
    description = "Configura el delimitador de comentarios del ensamblador."
    entrypoint = cmb.Seq(
        cmb.MatchToken("DOT"),
        _directive("comment"),
        cmb.MatchToken("STRING"),
        cmb.MatchToken("NEWLINE"),
    )


class LABELEND(cmb.RuleItem):
    nodeable = True
    description = "Define el terminador de labels del ensamblador."
    entrypoint = cmb.Seq(
        cmb.MatchToken("DOT"),
        _directive("labelend"),
        cmb.MatchToken("STRING"),
        cmb.MatchToken("NEWLINE"),
    )


class DATASECTION(cmb.RuleItem):
    nodeable = True
    description = "Selecciona la sección donde se buscarán símbolos de datos."
    entrypoint = cmb.Seq(
        cmb.MatchToken("DOT"),
        _directive("datasection"),
        cmb.MatchToken("STRING"),
        cmb.MatchToken("NEWLINE"),
    )


class DEFAULTSECTION(cmb.RuleItem):
    nodeable = True
    description = "Define la sección usada por defecto."
    entrypoint = cmb.Seq(
        cmb.MatchToken("DOT"),
        _directive("defaultsection"),
        cmb.MatchToken("STRING"),
        cmb.MatchToken("NEWLINE"),
    )


class SECTIONFLAGS(cmb.RuleItem):
    nodeable = True
    description = "Define los permisos de una sección."
    entrypoint = cmb.Seq(
        cmb.MatchToken("DOT"),
        _directive("sectionflags"),
        cmb.MatchToken("STRING"),
        cmb.MatchToken("STRING"),
        cmb.MatchToken("NEWLINE"),
    )


class SECTIONALIGN(cmb.RuleItem):
    nodeable = True
    description = "Define la alineación mínima de una sección."
    entrypoint = cmb.Seq(
        cmb.MatchToken("DOT"),
        _directive("sectionalign"),
        cmb.MatchToken("STRING"),
        cmb.MatchToken("NUMBER"),
        cmb.MatchToken("NEWLINE"),
    )


class WORDSIZE(cmb.RuleItem):
    nodeable = True
    description = "Define el tamaño natural de palabra."
    entrypoint = cmb.Seq(
        cmb.MatchToken("DOT"),
        _directive("wordsize"),
        cmb.MatchToken("NUMBER"),
        cmb.MatchToken("NEWLINE"),
    )


class ADDRESSSIZE(cmb.RuleItem):
    nodeable = True
    description = "Define el tamaño de las direcciones."
    entrypoint = cmb.Seq(
        cmb.MatchToken("DOT"),
        _directive("addresssize"),
        cmb.MatchToken("NUMBER"),
        cmb.MatchToken("NEWLINE"),
    )


class ENDIANESS(cmb.RuleItem):
    nodeable = True
    description = "Define el orden de bytes de la arquitectura."
    entrypoint = cmb.Seq(
        cmb.MatchToken("DOT"),
        cmb.Alt(
            _directive("endianess"),
            _directive("endianness"),
        ),
        cmb.MatchToken("STRING"),
        cmb.MatchToken("NEWLINE"),
    )


class CASESENSITIVE(cmb.RuleItem):
    nodeable = True
    description = "Define si los nombres distinguen mayúsculas y minúsculas."
    entrypoint = cmb.Seq(
        cmb.MatchToken("DOT"),
        _directive("casesensitive"),
        cmb.MatchToken("BOOL"),
        cmb.MatchToken("NEWLINE"),
    )


class SYMBOLPREFIX(cmb.RuleItem):
    nodeable = True
    description = "Define el prefijo de símbolos globales."
    entrypoint = cmb.Seq(
        cmb.MatchToken("DOT"),
        _directive("symbolprefix"),
        cmb.MatchToken("STRING"),
        cmb.MatchToken("NEWLINE"),
    )


class LOCALPREFIX(cmb.RuleItem):
    nodeable = True
    description = "Define el prefijo de símbolos locales."
    entrypoint = cmb.Seq(
        cmb.MatchToken("DOT"),
        _directive("localprefix"),
        cmb.MatchToken("STRING"),
        cmb.MatchToken("NEWLINE"),
    )


class UNDEFINEDSYMBOLS(cmb.RuleItem):
    nodeable = True
    description = "Define la política para símbolos no encontrados."
    entrypoint = cmb.Seq(
        cmb.MatchToken("DOT"),
        _directive("undefinedsymbols"),
        cmb.MatchToken("STRING"),
        cmb.MatchToken("NEWLINE"),
    )


class DUPLICATESYMBOLS(cmb.RuleItem):
    nodeable = True
    description = "Define la política para símbolos duplicados."
    entrypoint = cmb.Seq(
        cmb.MatchToken("DOT"),
        cmb.Alt(
            _directive("duplicateSymbols"),
            _directive("duplicatesymbols"),
        ),
        cmb.MatchToken("STRING"),
        cmb.MatchToken("NEWLINE"),
    )


class STRICT(cmb.RuleItem):
    nodeable = True
    description = "Activa o desactiva el modo estricto."
    entrypoint = cmb.Seq(
        cmb.MatchToken("DOT"),
        _directive("strict"),
        cmb.MatchToken("BOOL"),
        cmb.MatchToken("NEWLINE"),
    )


class ALLOWEMPTYSECTIONS(cmb.RuleItem):
    nodeable = True
    description = "Permite o prohíbe secciones vacías."
    entrypoint = cmb.Seq(
        cmb.MatchToken("DOT"),
        _directive("allowemptysections"),
        cmb.MatchToken("BOOL"),
        cmb.MatchToken("NEWLINE"),
    )


class BITORDER(cmb.RuleItem):
    nodeable = True
    description = "Define el orden de los bits dentro de cada byte."
    entrypoint = cmb.Seq(
        cmb.MatchToken("DOT"),
        _directive("bitorder"),
        cmb.MatchToken("STRING"),
        cmb.MatchToken("NEWLINE"),
    )


class CONFIG(cmb.RuleItem):
    nodeable = True
    description = "Declara la configuración del formato ensamblador objetivo."
    entrypoint = cmb.Seq(
        cmb.MatchToken("AT"),
        cmb.MatchKeyword("config"),
        cmb.MatchToken("COLON"),
        cmb.MatchToken("NEWLINE"),
        cmb.Many(
            cmb.Alt(
                cmb.Ref(SECTIONDEF),
                cmb.Ref(MAKE_SECTION),
                cmb.Ref(SECTIONEND),
                cmb.Ref(ENTRYSECTION),
                cmb.Ref(ENTRYLABEL),
                cmb.Ref(COMMENT),
                cmb.Ref(LABELEND),
                cmb.Ref(DATASECTION),
                cmb.Ref(DEFAULTSECTION),
                cmb.Ref(SECTIONFLAGS),
                cmb.Ref(SECTIONALIGN),
                cmb.Ref(WORDSIZE),
                cmb.Ref(ADDRESSSIZE),
                cmb.Ref(ENDIANESS),
                cmb.Ref(CASESENSITIVE),
                cmb.Ref(SYMBOLPREFIX),
                cmb.Ref(LOCALPREFIX),
                cmb.Ref(UNDEFINEDSYMBOLS),
                cmb.Ref(DUPLICATESYMBOLS),
                cmb.Ref(STRICT),
                cmb.Ref(ALLOWEMPTYSECTIONS),
                cmb.Ref(BITORDER),
            )
        ),
        cmb.MatchToken("AT"),
        cmb.MatchKeyword("configend"),
    )


class EXT(cmb.RuleItem):
    nodeable = True
    description = "Define la extensión de los archivos fuente del linker."
    entrypoint = cmb.Seq(
        cmb.MatchToken("DOT"),
        _directive("ext"),
        cmb.MatchToken("STRING"),
        cmb.MatchToken("NEWLINE"),
    )


class NAME(cmb.RuleItem):
    nodeable = True
    description = "Define el nombre base del archivo principal."
    entrypoint = cmb.Seq(
        cmb.MatchToken("DOT"),
        _directive("name"),
        cmb.MatchToken("STRING"),
        cmb.MatchToken("NEWLINE"),
    )


class SEARCHING(cmb.RuleItem):
    nodeable = True
    description = "Define dónde buscar archivos de secciones adicionales."
    entrypoint = cmb.Seq(
        cmb.MatchToken("DOT"),
        _directive("searching"),
        cmb.Alt(
            cmb.MatchToken("STRING"),
            cmb.MatchToken("BOOL"),
        ),
        cmb.MatchToken("NEWLINE"),
    )


class LINKER(cmb.RuleItem):
    nodeable = True
    description = "Declara la configuración del linker de RIF."
    entrypoint = cmb.Seq(
        cmb.MatchToken("AT"),
        cmb.MatchKeyword("linker"),
        cmb.MatchToken("COLON"),
        cmb.MatchToken("NEWLINE"),
        cmb.Many(
            cmb.Alt(
                cmb.Ref(EXT),
                cmb.Ref(NAME),
                cmb.Ref(SEARCHING),
            )
        ),
        cmb.MatchToken("AT"),
        cmb.MatchKeyword("linkerend"),
    )


class SUPPORTS(cmb.RuleItem):
    nodeable = True
    description = "Declara una variante ISA disponible para delegación."
    entrypoint = cmb.Seq(
        cmb.MatchToken("AT"),
        cmb.MatchKeyword("SUPPORTS"),
        cmb.MatchToken("IDENT"),
        cmb.MatchToken("NEWLINE"),
    )


class VARIANT_MODE(cmb.RuleItem):
    nodeable = True
    description = "Define el modo de delegación de una variante ISA."
    entrypoint = cmb.Seq(
        cmb.MatchToken("DOT"),
        cmb.MatchKeyword("MODE"),
        cmb.Alt(
            cmb.MatchKeyword("SWITCH"),
            cmb.MatchKeyword("ENCAPSULATE"),
        ),
        cmb.MatchToken("NEWLINE"),
    )


class VARIANT_ENTER(cmb.RuleItem):
    nodeable = True
    description = "Referencia la Rule que activa una variante."
    entrypoint = cmb.Seq(
        cmb.MatchToken("DOT"),
        cmb.MatchKeyword("ENTER"),
        cmb.MatchToken("STRING"),
        cmb.MatchToken("NEWLINE"),
    )


class VARIANT_EXIT(cmb.RuleItem):
    nodeable = True
    description = "Referencia la Rule que devuelve al contexto padre."
    entrypoint = cmb.Seq(
        cmb.MatchToken("DOT"),
        cmb.MatchKeyword("EXIT"),
        cmb.MatchToken("STRING"),
        cmb.MatchToken("NEWLINE"),
    )


class ASMVARIANT(cmb.RuleItem):
    nodeable = True
    description = "Configura la delegación sintáctica a otra variante ISA."
    entrypoint = cmb.Seq(
        cmb.MatchToken("AT"),
        cmb.MatchKeyword("ASMVARIANT"),
        cmb.MatchToken("IDENT"),
        cmb.MatchToken("COLON"),
        cmb.MatchToken("NEWLINE"),
        cmb.Many(
            cmb.Alt(
                cmb.Ref(VARIANT_MODE),
                cmb.Ref(VARIANT_ENTER),
                cmb.Ref(VARIANT_EXIT),
            )
        ),
        cmb.MatchToken("AT"),
        cmb.MatchKeyword("END"),
    )


class LOAD_FILE(cmb.RuleItem):
    nodeable = True
    description = "Carga declaraciones desde otro archivo RIF en esta posición."
    entrypoint = cmb.Seq(
        cmb.MatchToken("AT"),
        cmb.MatchKeyword("LOAD"),
        cmb.MatchToken("STRING"),
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
    "CONFIG",
    "SECTIONDEF",
    "MAKE_SECTION",
    "SECTIONEND",
    "ENTRYSECTION",
    "ENTRYLABEL",
    "COMMENT",
    "LABELEND",
    "DATASECTION",
    "DEFAULTSECTION",
    "SECTIONFLAGS",
    "SECTIONALIGN",
    "WORDSIZE",
    "ADDRESSSIZE",
    "ENDIANESS",
    "CASESENSITIVE",
    "SYMBOLPREFIX",
    "LOCALPREFIX",
    "UNDEFINEDSYMBOLS",
    "DUPLICATESYMBOLS",
    "STRICT",
    "ALLOWEMPTYSECTIONS",
    "BITORDER",
    "EXT",
    "NAME",
    "SEARCHING",
    "LINKER",
    "SUPPORTS",
    "VARIANT_MODE",
    "VARIANT_ENTER",
    "VARIANT_EXIT",
    "ASMVARIANT",
    "LOAD_FILE",
    "INSTRUCTION",
]
