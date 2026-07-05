from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from vision.board_detector import BoardDetection
from vision.fen_generator import FenGenerator
from vision.piece_detector import PieceOnSquare
from vision.square_mapper import SquareMapper


def main() -> int:
    mapper = SquareMapper(BoardDetection(0, 0, 800, 1.0), flipped=False)
    assert mapper.square_at(0, 0) == "a8"
    assert mapper.square_at(7, 7) == "h1"

    result = FenGenerator().generate(
        [
            PieceOnSquare("e1", "wk", 1.0),
            PieceOnSquare("e8", "bk", 1.0),
        ]
    )
    assert result.valid, result.errors
    print("Core validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
