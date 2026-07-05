from __future__ import annotations

from vision.board_detector import BoardDetection
from vision.square_mapper import SquareMapper


def test_white_orientation_mapping() -> None:
    mapper = SquareMapper(BoardDetection(0, 0, 800, 1.0), flipped=False)

    assert mapper.square_at(0, 0) == "a8"
    assert mapper.square_at(7, 7) == "h1"
    assert mapper.row_col_for_square("e4") == (4, 4)


def test_black_orientation_mapping() -> None:
    mapper = SquareMapper(BoardDetection(0, 0, 800, 1.0), flipped=True)

    assert mapper.square_at(0, 0) == "h1"
    assert mapper.square_at(7, 7) == "a8"
    assert mapper.row_col_for_square("e4") == (3, 3)
