# Configuration Guide

Settings live in `config/settings.json`. The file is created automatically on first run.

## Engine

```json
{
  "engine": {
    "stockfish_path": "stockfish",
    "depth": 14,
    "skill_level": 20,
    "threads": 2,
    "hash_mb": 256,
    "analysis_time_ms": 700,
    "multipv": 3
  }
}
```

- `stockfish_path`: executable path or a command available on `PATH`.
- `depth`: maximum engine depth.
- `skill_level`: Stockfish skill level from 0 to 20.
- `threads`: CPU threads used by Stockfish.
- `hash_mb`: engine hash memory in MB.
- `analysis_time_ms`: per-position analysis budget.
- `multipv`: number of candidate moves to return.

## Capture

```json
{
  "capture": {
    "fps": 30,
    "use_dxcam": false,
    "selected_window_title": "",
    "manual_region": null
  }
}
```

Use `manual_region` when automatic window selection is not enough:

```json
"manual_region": {
  "left": 100,
  "top": 100,
  "width": 900,
  "height": 900
}
```

## Overlay

The overlay is transparent, always on top, and click-through. When analysis is running, it highlights the source square, highlights the destination square, and draws an arrow on the live board so you do not need to read chess notation.

## Gameplay

```json
{
  "gameplay": {
    "player_color": "white",
    "recognition_interval_ms": 250
  }
}
```

- `player_color`: your side, `white` or `black`.
- `recognition_interval_ms`: how often the app performs full board and piece recognition. Lower values react faster; higher values use less CPU.

## Piece templates

Place templates in `assets/pieces/chesscom/`. The detector expects files named `wp.png`, `wn.png`, `wb.png`, `wr.png`, `wq.png`, `wk.png`, `bp.png`, `bn.png`, `bb.png`, `br.png`, `bq.png`, and `bk.png`.
