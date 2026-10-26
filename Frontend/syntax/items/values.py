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


class SIZE_VALUE(cmb.RuleItem):
    nodeable = True
    description = "Posición física actual del buffer en bits."
    entrypoint = cmb.Seq(
        cmb.MatchToken("COLON"),
        cmb.MatchToken("COLON"),
        cmb.MatchKeyword("SIZE"),
    )


class VSIZE_VALUE(cmb.RuleItem):
    nodeable = True
    description = "Posición virtual actual del buffer en bits."
    entrypoint = cmb.Seq(
        cmb.MatchToken("COLON"),
        cmb.MatchToken("COLON"),
        cmb.MatchKeyword("VSIZE"),
    )


class ALIGNMENT_VALUE(cmb.RuleItem):
    nodeable = True
    description = "Alineamiento configurado para la sección actual."
    entrypoint = cmb.Seq(
        cmb.MatchToken("COLON"),
        cmb.MatchToken("COLON"),
        cmb.MatchKeyword("ALIGNMENT"),
    )


def _reservation_value(name: str):
    return cmb.Seq(
        cmb.MatchKeyword(name),
        cmb.MatchToken("STRING"),
    )


class DIST_VALUE(cmb.RuleItem):
    nodeable = True
    description = "Distancia física desde una etiqueta hasta la posición actual."
    entrypoint = _reservation_value("dist")


class VDIST_VALUE(cmb.RuleItem):
    nodeable = True
    description = "Distancia virtual desde una etiqueta hasta la posición actual."
    entrypoint = _reservation_value("vdist")


class RESDIR_VALUE(cmb.RuleItem):
    nodeable = True
    description = "Dirección física de una reserva."
    entrypoint = _reservation_value("resdir")


class RESVDIR_VALUE(cmb.RuleItem):
    nodeable = True
    description = "Dirección virtual de una reserva."
    entrypoint = _reservation_value("resvdir")


class RESDIST_VALUE(cmb.RuleItem):
    nodeable = True
    description = "Distancia física hasta una reserva."
    entrypoint = _reservation_value("resdist")


class RESVDIST_VALUE(cmb.RuleItem):
    nodeable = True
    description = "Distancia virtual hasta una reserva."
    entrypoint = _reservation_value("resvdist")


class VALUE(cmb.RuleItem):
    nodeable = True


__all__ = [
    "TABLE_ACCESS",
    "RESERVATION_ACCESS",
    "CALL_VALUE",
    "SIZE_VALUE",
    "VSIZE_VALUE",
    "ALIGNMENT_VALUE",
    "DIST_VALUE",
    "VDIST_VALUE",
    "RESDIR_VALUE",
    "RESVDIR_VALUE",
    "RESDIST_VALUE",
    "RESVDIST_VALUE",
    "VALUE",
]
