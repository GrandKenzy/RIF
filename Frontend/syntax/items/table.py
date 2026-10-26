from gram import combinators as cmb

from .values import VALUE


class CELL(cmb.RuleItem):
    nodeable = True
    entrypoint = cmb.Seq(
        cmb.MatchToken("OR"),
        cmb.Ref(VALUE),
    )


class HEADER(cmb.RuleItem):
    nodeable = True
    entrypoint = cmb.Seq(
        cmb.Some(
            cmb.Seq(
                cmb.MatchToken("OR"),
                cmb.MatchToken("IDENT"),
            )
        ),
        cmb.MatchToken("OR"),
        cmb.MatchToken("NEWLINE"),
    )


class ROW(cmb.RuleItem):
    nodeable = True
    entrypoint = cmb.Seq(
        cmb.Some(cmb.Ref(CELL)),
        cmb.MatchToken("OR"),
        cmb.MatchToken("NEWLINE"),
    )


class SEPARATOR(cmb.RuleItem):
    nodeable = False
    entrypoint = cmb.Many(cmb.MatchSeqSymbol(pattern="_+"))


class COLUMNS(cmb.RuleItem):
    nodeable = False
    entrypoint = cmb.Seq(
        cmb.Ref(HEADER),
        cmb.Some(
            cmb.Seq(
                cmb.Ref(SEPARATOR),
                cmb.MatchToken("NEWLINE"),
                cmb.Ref(ROW),
            )
        ),
    )


class TABLE(cmb.RuleItem):
    nodeable = True
    entrypoint = cmb.Seq(
        cmb.MatchToken("AT"),
        cmb.MatchKeyword("table"),
        cmb.MatchToken("IDENT"),
        cmb.MatchToken("NEWLINE"),
        cmb.Ref(COLUMNS),
        cmb.MatchToken("AT"),
        cmb.MatchKeyword("end"),
    )


__all__ = ["TABLE"]
