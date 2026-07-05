from __future__ import annotations

from vision.fen_generator import FenGenerator
from vision.piece_detector import PieceOnSquare


def test_generate_starting_position_piece_placement() -> None:
    pieces = [
        PieceOnSquare("e1", "wk", 1.0),
        PieceOnSquare("e8", "bk", 1.0),
        PieceOnSquare("a1", "wr", 1.0),
        PieceOnSquare("h8", "br", 1.0),
    ]

    result = FenGenerator().generate(pieces)

    assert result.valid
    assert result.fen.startswith("4k2r/8/8/8/8/8/8/R3K3 w - - 0 1")


def test_requires_both_kings() -> None:
    result = FenGenerator().generate([PieceOnSquare("e1", "wk", 1.0)])

    assert not result.valid
    assert "Expected one black king" in "; ".join(result.errors)
