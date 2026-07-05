from __future__ import annotations

from dataclasses import dataclass

import chess

from vision.piece_detector import PieceOnSquare


PIECE_TO_FEN = {
    "wp": "P",
    "wn": "N",
    "wb": "B",
    "wr": "R",
    "wq": "Q",
    "wk": "K",
    "bp": "p",
    "bn": "n",
    "bb": "b",
    "br": "r",
    "bq": "q",
    "bk": "k",
}


@dataclass(frozen=True, slots=True)
class FenResult:
    fen: str
    valid: bool
    errors: tuple[str, ...]


class FenGenerator:
    def generate(
        self,
        pieces: list[PieceOnSquare],
        side_to_move: chess.Color = chess.WHITE,
        castling: str = "-",
        en_passant: str = "-",
        halfmove_clock: int = 0,
        fullmove_number: int = 1,
    ) -> FenResult:
        board_map: dict[str, str] = {}
        errors: list[str] = []

        for piece in pieces:
            fen_piece = PIECE_TO_FEN.get(piece.piece_code)
            if fen_piece is None:
                errors.append(f"Unknown piece code {piece.piece_code!r}")
                continue
            if piece.square in board_map:
                errors.append(f"Duplicate square {piece.square}")
            board_map[piece.square] = fen_piece

        placement_parts: list[str] = []
        for rank in range(8, 0, -1):
            empty = 0
            rank_part = ""
            for file in "abcdefgh":
                piece = board_map.get(f"{file}{rank}")
                if piece is None:
                    empty += 1
                else:
                    if empty:
                        rank_part += str(empty)
                        empty = 0
                    rank_part += piece
            if empty:
                rank_part += str(empty)
            placement_parts.append(rank_part)

        turn = "w" if side_to_move == chess.WHITE else "b"
        fen = (
            f"{'/'.join(placement_parts)} {turn} {castling} {en_passant} "
            f"{halfmove_clock} {fullmove_number}"
        )

        white_kings = sum(1 for value in board_map.values() if value == "K")
        black_kings = sum(1 for value in board_map.values() if value == "k")
        if white_kings != 1:
            errors.append(f"Expected one white king, found {white_kings}")
        if black_kings != 1:
            errors.append(f"Expected one black king, found {black_kings}")

        try:
            chess.Board(fen)
        except ValueError as exc:
            errors.append(str(exc))

        return FenResult(fen=fen, valid=not errors, errors=tuple(errors))
