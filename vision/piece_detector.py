from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import cv2
import numpy as np

from vision.board_detector import BoardDetection
from vision.square_mapper import SquareMapper

LOGGER = logging.getLogger(__name__)

PIECE_CODES = ("wp", "wn", "wb", "wr", "wq", "wk", "bp", "bn", "bb", "br", "bq", "bk")


@dataclass(frozen=True, slots=True)
class PieceOnSquare:
    square: str
    piece_code: str
    confidence: float


@dataclass(frozen=True, slots=True)
class PieceTemplate:
    code: str
    rgb_image: np.ndarray
    edge_image: np.ndarray
    alpha_mask: np.ndarray | None = None


class PieceDetector(Protocol):
    def detect(self, image: np.ndarray, board: BoardDetection) -> list[PieceOnSquare]:
        ...


class TemplatePieceDetector:
    def __init__(self, template_dir: Path, threshold: float = 0.62) -> None:
        self.template_dir = template_dir
        self.threshold = threshold
        self._templates = self._load_templates()

    @property
    def has_templates(self) -> bool:
        return bool(self._templates)

    def detect(self, image: np.ndarray, board: BoardDetection) -> list[PieceOnSquare]:
        return self.map_cells(self.detect_cells(image, board), board)

    def detect_cells(
        self, image: np.ndarray, board: BoardDetection
    ) -> list[tuple[int, int, str, float]]:
        """Raw grid detections as (row, col, code, confidence).

        Row/col are screen positions (row 0 = top), independent of orientation,
        so the caller can decide board orientation before mapping to squares.
        """
        if not self._templates:
            LOGGER.warning("No piece templates found in %s", self.template_dir)
            return []

        board_image = image[board.top : board.bottom, board.left : board.right]
        square_size = board.size // 8
        cells: list[tuple[int, int, str, float]] = []

        for row in range(8):
            for col in range(8):
                tile = board_image[
                    row * square_size : (row + 1) * square_size,
                    col * square_size : (col + 1) * square_size,
                ]
                match = self._classify_tile(tile)
                if match is not None:
                    code, confidence = match
                    cells.append((row, col, code, confidence))
        return cells

    def map_cells(
        self, cells: list[tuple[int, int, str, float]], board: BoardDetection
    ) -> list[PieceOnSquare]:
        mapper = SquareMapper(board, board.flipped)
        return [
            PieceOnSquare(mapper.square_at(row, col), code, confidence)
            for row, col, code, confidence in cells
        ]

    def _load_templates(self) -> dict[str, PieceTemplate]:
        templates: dict[str, PieceTemplate] = {}
        for code in PIECE_CODES:
            path = self.template_dir / f"{code}.png"
            if not path.exists():
                continue
            image = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
            if image is None:
                continue
            rgb = cv2.cvtColor(image[:, :, :3], cv2.COLOR_BGR2RGB)
            if image.shape[2] == 4:
                alpha = image[:, :, 3]
                gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
                edge_image = cv2.Canny(gray, 40, 120)
                alpha_mask = alpha
            else:
                gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
                edge_image = cv2.Canny(gray, 40, 120)
                alpha_mask = None
            templates[code] = PieceTemplate(
                code=code,
                rgb_image=rgb,
                edge_image=edge_image,
                alpha_mask=alpha_mask,
            )
        return templates

    def _classify_tile(self, tile: np.ndarray) -> tuple[str, float] | None:
        if tile.size == 0:
            return None

        best_code = ""
        best_score = -1.0
        tile_gray = cv2.cvtColor(tile, cv2.COLOR_RGB2GRAY)
        tile_edges = cv2.Canny(tile_gray, 40, 120)
        if float(np.count_nonzero(tile_edges)) / tile_edges.size < 0.025:
            return None

        for code, template in self._templates.items():
            template_edges = cv2.resize(
                template.edge_image,
                (tile.shape[1], tile.shape[0]),
                interpolation=cv2.INTER_AREA,
            )
            edge_score = float(cv2.matchTemplate(tile_edges, template_edges, cv2.TM_CCOEFF_NORMED).max())
            color_score = self._color_similarity(tile, template)
            score = 0.62 * edge_score + 0.38 * color_score
            if score > best_score:
                best_code = code
                best_score = score

        if best_score < self.threshold:
            return None
        return best_code, best_score

    def _color_similarity(self, tile: np.ndarray, template: PieceTemplate) -> float:
        template_rgb = cv2.resize(
            template.rgb_image,
            (tile.shape[1], tile.shape[0]),
            interpolation=cv2.INTER_AREA,
        )
        if template.alpha_mask is not None:
            mask = cv2.resize(
                template.alpha_mask,
                (tile.shape[1], tile.shape[0]),
                interpolation=cv2.INTER_AREA,
            ) > 25
        else:
            mask = np.ones(tile.shape[:2], dtype=bool)

        if int(np.count_nonzero(mask)) < 20:
            return 0.0
        diff = np.abs(tile.astype(np.int16) - template_rgb.astype(np.int16))
        mean_diff = float(diff[mask].mean())
        return max(0.0, 1.0 - mean_diff / 255.0)
