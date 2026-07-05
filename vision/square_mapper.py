from __future__ import annotations

from dataclasses import dataclass

from vision.board_detector import BoardDetection


FILES = "abcdefgh"
RANKS = "12345678"


@dataclass(slots=True)
class SquareBounds:
    square: str
    left: int
    top: int
    size: int


class SquareMapper:
    def __init__(self, detection: BoardDetection, flipped: bool = False) -> None:
        self.detection = detection
        self.flipped = flipped
        self.square_size = detection.size / 8.0

    def square_at(self, row: int, col: int) -> str:
        if not 0 <= row < 8 or not 0 <= col < 8:
            raise ValueError("row and col must be in 0..7")

        if self.flipped:
            file_index = 7 - col
            rank_index = row
        else:
            file_index = col
            rank_index = 7 - row
        return f"{FILES[file_index]}{RANKS[rank_index]}"

    def row_col_for_square(self, square: str) -> tuple[int, int]:
        file_index = FILES.index(square[0])
        rank_index = RANKS.index(square[1])
        if self.flipped:
            return rank_index, 7 - file_index
        return 7 - rank_index, file_index

    def bounds_for(self, row: int, col: int) -> SquareBounds:
        left = int(round(self.detection.left + col * self.square_size))
        top = int(round(self.detection.top + row * self.square_size))
        size = int(round(self.square_size))
        return SquareBounds(self.square_at(row, col), left, top, size)
