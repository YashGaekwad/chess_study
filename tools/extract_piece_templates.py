from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import cv2
import numpy as np

from config import ASSETS_DIR


DEFAULT_MAPPING = {
    "br": "h8",
    "bn": "b8",
    "bb": "c8",
    "bq": "d8",
    "bk": "e8",
    "bp": "e5",
    "wr": "h1",
    "wn": "b1",
    "wb": "c1",
    "wq": "d1",
    "wk": "e1",
    "wp": "e4",
}


def square_to_row_col(square: str) -> tuple[int, int]:
    file_index = "abcdefgh".index(square[0])
    rank_index = int(square[1])
    return 8 - rank_index, file_index


def infer_board(image: np.ndarray) -> tuple[int, int, int]:
    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    expected = np.array([[118, 150, 86], [238, 238, 210], [186, 204, 55]], dtype=np.int16)
    distances = np.min(
        np.linalg.norm(rgb[:, :, None, :].astype(np.int16) - expected[None, None, :, :], axis=3),
        axis=2,
    )
    mask = distances < 25
    x_run = largest_run(mask, axis=1)
    y_run = largest_run(mask, axis=0)
    if x_run is None or y_run is None:
        raise RuntimeError("Could not detect board area")

    x, right = x_run
    y, bottom = y_run
    size = min(right - x + 1, bottom - y + 1)
    size -= size % 8
    return x, y, size


def largest_run(mask: np.ndarray, axis: int) -> tuple[int, int] | None:
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


def piece_alpha(tile: np.ndarray) -> np.ndarray:
    height, width = tile.shape[:2]
    samples = np.concatenate(
        [
            tile[0:8, :, :].reshape(-1, 3),
            tile[-8:, :, :].reshape(-1, 3),
            tile[:, 0:8, :].reshape(-1, 3),
            tile[:, -8:, :].reshape(-1, 3),
        ],
        axis=0,
    )
    background = np.median(samples, axis=0)
    distance = np.linalg.norm(tile.astype(np.float32) - background.astype(np.float32), axis=2)
    mask = (distance > 26).astype(np.uint8) * 255

    # Remove square coordinates and tiny artifacts, then keep central components.
    kernel = np.ones((3, 3), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    component_count, labels, stats, centroids = cv2.connectedComponentsWithStats(mask, 8)
    kept = np.zeros((height, width), dtype=np.uint8)
    center = np.array([width / 2, height / 2])
    for index in range(1, component_count):
        area = stats[index, cv2.CC_STAT_AREA]
        if area < 80:
            continue
        centroid = centroids[index]
        if np.linalg.norm(centroid - center) > width * 0.48 and area < 500:
            continue
        kept[labels == index] = 255

    kept = cv2.dilate(kept, np.ones((2, 2), np.uint8), iterations=1)
    return cv2.GaussianBlur(kept, (3, 3), 0)


def extract_templates(source: Path, output_dir: Path) -> None:
    image = cv2.imread(str(source), cv2.IMREAD_COLOR)
    if image is None:
        raise RuntimeError(f"Could not read {source}")

    left, top, size = infer_board(image)
    square_size = size // 8
    output_dir.mkdir(parents=True, exist_ok=True)

    for code, square in DEFAULT_MAPPING.items():
        row, col = square_to_row_col(square)
        tile = image[
            top + row * square_size : top + (row + 1) * square_size,
            left + col * square_size : left + (col + 1) * square_size,
        ]
        alpha = piece_alpha(tile)
        rgba = cv2.cvtColor(tile, cv2.COLOR_BGR2BGRA)
        rgba[:, :, 3] = alpha
        cv2.imwrite(str(output_dir / f"{code}.png"), rgba)

    print(f"Wrote templates to {output_dir}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract Chess.com piece templates from a screenshot.")
    parser.add_argument("source", type=Path, help="Screenshot containing a Chess.com board")
    parser.add_argument(
        "--output",
        type=Path,
        default=ASSETS_DIR / "pieces" / "chesscom",
        help="Output directory for wp.png, bk.png, etc.",
    )
    args = parser.parse_args()
    extract_templates(args.source, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
