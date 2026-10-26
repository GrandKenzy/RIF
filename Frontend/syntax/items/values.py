from gram import combinators as cmb


class TABLE_ACCESS(cmb.RuleItem):
    nodeable = True
    description = "Acceso sintáctico a una columna de tabla."
    entrypoint = cmb.Seq(
        cmb.MatchToken("DOLLAR"),
        cmb.MatchToken("IDENT"),
        cmb.MatchToken("DOT"),
        cmb.MatchToken("IDENT"),
    )


class RESERVATION_ACCESS(cmb.RuleItem):
    nodeable = True
    description = "Acceso sintáctico a una reserva por etiqueta."
    entrypoint = cmb.Seq(
        cmb.MatchToken("AND"),
        cmb.MatchToken("IDENT"),
    )


class CALL_VALUE(cmb.RuleItem):
    nodeable = True
    description = "Llamada sintáctica a una función externa."
    entrypoint = cmb.Seq(
        cmb.MatchToken("HASH"),
        cmb.MatchKeyword("call"),
        cmb.MatchToken("LBRACKET"),
        cmb.MatchToken("IDENT"),
        cmb.MatchToken("RBRACKET"),
    )


class VALUE(cmb.RuleItem):
    nodeable = True


__all__ = ["TABLE_ACCESS", "RESERVATION_ACCESS", "CALL_VALUE", "VALUE"]
