# Installation Guide

## 1. Install Python

Install Python 3.11 or newer for Windows from [python.org](https://www.python.org/downloads/windows/). During setup, enable **Add python.exe to PATH**.

## 2. Create a virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

## 3. Install Python packages

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Python 3.13 currently skips the optional YOLO and ONNX packages in `requirements.txt` because those ecosystems can lag the newest Python release. The main app still runs without them.

## 4. Install Stockfish

Download Stockfish for Windows from [stockfishchess.org](https://stockfishchess.org/download/). Save the executable somewhere stable, such as:

```text
C:\Tools\Stockfish\stockfish-windows-x86-64-avx2.exe
```

Set that path in the app under **Engine Settings**.

## 5. Run the app

```powershell
python main.py
```

Open a Chess.com board in your browser, then use **Refresh Detection** if the app does not select it automatically.
