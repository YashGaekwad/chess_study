# Chess Study Assistant

A Windows desktop study tool that watches a Chess.com board on your monitor, reconstructs the current position, analyzes it with Stockfish, and displays the result in a PySide6 interface with an optional transparent overlay.

## Current capabilities

- Detects Chess.com browser windows by title and supports manual capture regions.
- Captures the selected window or monitor region with `mss`.
- Locates an 8x8 board using OpenCV geometry and color consistency heuristics.
- Maps board pixels to chess squares for white or black orientation.
- Generates and validates FEN from detected pieces.
- Runs Stockfish through `python-chess`, including top candidate lines, centipawn or mate score, and principal variations.
- Provides a responsive PySide6 UI with start, stop, pause, resume, settings, logs, FEN, board preview, performance stats, and dark mode.
- Provides an always-on-top transparent overlay that draws the best-move arrow directly on the detected board.

## Important limitation

Chess.com piece recognition is theme-dependent. This project includes a production template-matching detector, but it needs piece template images in `assets/pieces/<theme>/` to classify pieces reliably. Without templates, the app can still detect and preview the board, but FEN generation will report an incomplete position.

Expected template filenames:

```text
assets/pieces/chesscom/wp.png
assets/pieces/chesscom/wn.png
assets/pieces/chesscom/wb.png
assets/pieces/chesscom/wr.png
assets/pieces/chesscom/wq.png
assets/pieces/chesscom/wk.png
assets/pieces/chesscom/bp.png
assets/pieces/chesscom/bn.png
assets/pieces/chesscom/bb.png
assets/pieces/chesscom/br.png
assets/pieces/chesscom/bq.png
assets/pieces/chesscom/bk.png
```

Use transparent PNG templates cropped tightly around the piece. Additional AI detectors can be added behind the `PieceDetector` protocol in `vision/piece_detector.py`.

## Installation

1. Install Python 3.11 or newer.
2. Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

3. Download Stockfish from [stockfishchess.org](https://stockfishchess.org/download/) and set its path in `config/settings.json` or in the Engine Settings dialog.
4. Run the app:

```powershell
python main.py
```

## Configuration

Settings are stored in `config/settings.json` after first launch. The main options are:

- `engine.stockfish_path`: path to `stockfish.exe`
- `engine.depth`: search depth for quick analysis
- `engine.analysis_time_ms`: time budget per position
- `engine.threads`: Stockfish thread count
- `engine.hash_mb`: Stockfish hash memory
- `capture.fps`: capture target FPS
- `capture.manual_region`: optional region `{left, top, width, height}`
- `overlay.opacity`: transparent overlay opacity

## Keyboard shortcuts

- `F1`: Start analysis
- `F2`: Pause
- `F3`: Resume
- `F4`: Hide or show overlay
- `F5`: Refresh board detection
- `F6`: Engine settings
- `Esc`: Exit

Set the toolbar color selector to your side before pressing **Start Analysis**. The app will show an arrow when it believes it is your turn, then wait after your move until the opponent moves.

## Architecture

```text
main.py                 application entry point
app.py                  PySide6 bootstrap
config.py               JSON-backed settings dataclasses
logger.py               rotating application logging
capture/                screen capture and window detection
vision/                 board detection, square mapping, piece detection, FEN
engine/                 Stockfish wrapper and analysis data models
overlay/                transparent overlay window and painting helpers
ui/                     main window and settings dialog
assets/                 piece templates and visual assets
models/                 optional YOLO/ONNX models
logs/                   runtime logs
tests/                  focused unit tests
```

The UI owns worker threads; capture, vision, and engine modules are independent and testable.

## Development

Run tests:

```powershell
python -m pytest
```

The most useful extension points are:

- Add a YOLO/ONNX implementation of `PieceDetector`.
- Persist calibrated board regions per Chess.com window.
- Add side-to-move inference from clock highlights or Chess.com move list.

## License

This project is open source under the MIT License. See `LICENSE` for details.
