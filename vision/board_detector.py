from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(slots=True)
class BoardDetection:
    left: int
    top: int
    size: int
    confidence: float
    flipped: bool = False

    @property
    def right(self) -> int:
        return self.left + self.size

    @property
    def bottom(self) -> int:
        return self.top + self.size


class BoardDetector:
    def detect(self, image: np.ndarray) -> BoardDetection | None:
        if image.size == 0:
            return None

        color_detection = self._detect_by_chesscom_colors(image)
        if color_detection is not None:
            return color_detection

        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 40, 120)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        height, width = gray.shape
        min_size = int(min(width, height) * 0.25)
        candidates: list[tuple[float, BoardDetection]] = []

        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            size = min(w, h)
            if size < min_size:
                continue
            aspect = w / max(h, 1)
            if not 0.85 <= aspect <= 1.15:
                continue

            square = self._snap_to_square(image, x, y, size)
            score = self._score_grid(image, square)
            if score > 0.25:
                candidates.append((score, square))

        if candidates:
            candidates.sort(key=lambda item: item[0], reverse=True)
            return candidates[0][1]

        return self._scan_for_board(image)

    def _snap_to_square(
        self, image: np.ndarray, left: int, top: int, size: int
    ) -> BoardDetection:
        height, width = image.shape[:2]
        size = max(8, min(size, width - left, height - top))
        left = max(0, min(left, width - size))
        top = max(0, min(top, height - size))
        confidence = self._grid_confidence(image[top : top + size, left : left + size])
        return BoardDetection(left=left, top=top, size=size, confidence=confidence)

    def _scan_for_board(self, image: np.ndarray) -> BoardDetection | None:
        height, width = image.shape[:2]
        limit = min(width, height)
        best: BoardDetection | None = None
        best_score = 0.0

        for size in range(limit, max(120, limit // 3), -max(16, limit // 16)):
            step = max(16, size // 12)
            for top in range(0, max(1, height - size + 1), step):
                for left in range(0, max(1, width - size + 1), step):
                    detection = BoardDetection(left, top, size, 0.0)
                    score = self._score_grid(image, detection)
                    if score > best_score:
                        best_score = score
                        best = BoardDetection(left, top, size, score)

        return best if best and best.confidence >= 0.35 else None

    def _detect_by_chesscom_colors(self, image: np.ndarray) -> BoardDetection | None:
        expected = np.array(
            [[118, 150, 86], [238, 238, 210], [186, 204, 55]],
            dtype=np.int16,
        )
        distances = np.min(
            np.linalg.norm(
                image[:, :, None, :].astype(np.int16) - expected[None, None, :, :],
                axis=3,
            ),
            axis=2,
        )
        mask = distances < 25
        height, width = mask.shape

        x_run = self._largest_axis_run(mask, axis=1)
        y_run = self._largest_axis_run(mask, axis=0)
        if x_run is None or y_run is None:
            return None

        left, right = x_run
        top, bottom = y_run
        size = min(right - left + 1, bottom - top + 1)
        size -= size % 8
        if size < min(width, height) * 0.45:
            return None

        confidence = self._grid_confidence(image[top : top + size, left : left + size])
        if confidence < 0.35:
            return None
        return BoardDetection(left=left, top=top, size=size, confidence=confidence)

    def _largest_axis_run(self, mask: np.ndarray, axis: int) -> tuple[int, int] | None:
        best: tuple[int, int] | None = None
        best_length = 0
        lines = mask if axis == 1 else mask.T
        for line in lines:
            padded = np.concatenate(([False], line, [False]))
            changes = np.flatnonzero(padded[1:] != padded[:-1])
            for start, end in zip(changes[0::2], changes[1::2]):
                length = int(end - start)
                if length > best_length:
                    best_length = length
                    best = (int(start), int(end - 1))
        return best

    def _score_grid(self, image: np.ndarray, detection: BoardDetection) -> float:
        board = image[
            detection.top : detection.bottom,
            detection.left : detection.right,
        ]
        return self._grid_confidence(board)

    def _grid_confidence(self, board: np.ndarray) -> float:
        if board.shape[0] < 80 or board.shape[1] < 80:
            return 0.0

        resized = cv2.resize(board, (160, 160), interpolation=cv2.INTER_AREA)
        lab = cv2.cvtColor(resized, cv2.COLOR_RGB2LAB)
        samples = []
        for rank in range(8):
            for file in range(8):
                tile = lab[rank * 20 + 5 : rank * 20 + 15, file * 20 + 5 : file * 20 + 15]
                samples.append(tile.reshape(-1, 3).mean(axis=0))
        sample_array = np.asarray(samples)
        even = sample_array[[idx for idx in range(64) if (idx // 8 + idx % 8) % 2 == 0]]
        odd = sample_array[[idx for idx in range(64) if (idx // 8 + idx % 8) % 2 == 1]]
        color_distance = float(np.linalg.norm(even.mean(axis=0) - odd.mean(axis=0)))
        even_noise = float(even.std(axis=0).mean())
        odd_noise = float(odd.std(axis=0).mean())
        regularity = 1.0 / (1.0 + (even_noise + odd_noise) / 50.0)
        contrast = min(color_distance / 55.0, 1.0)
        return max(0.0, min(1.0, contrast * regularity))
