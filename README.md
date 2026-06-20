# PixSwap

A simple, cross-platform desktop tool to convert photos between formats **without losing detail**. Drag in your photos, pick a format, click Convert.

![platforms](https://img.shields.io/badge/platforms-Windows%20%7C%20macOS%20%7C%20Linux-blue)

Written by **LJ "HawaiizFynest" Eblacas** — [github.com/hawaiizfynest](https://github.com/hawaiizfynest)

## What it does

- Converts between **JPEG, PNG, WebP, TIFF, BMP, GIF, ICO, TGA, PPM, PDF, and HEIC**, and reads even more (including iPhone **HEIC/HEIF** photos).
- **Preserves all detail:** full resolution (never resized), EXIF metadata (camera, date, GPS), ICC colour profiles, and DPI.
- Batch convert whole folders at once.
- Quality slider for lossy formats; lossless option for WebP.
- Drag-and-drop, plus a progress log.

## Download (no Python needed)

Grab a prebuilt app from the [**Releases**](../../releases) page, or from the [**Actions**](../../actions) tab (click the latest run → *Artifacts*):

- **Windows:** `PixSwap-Windows.zip` → unzip → run `PixSwap.exe`
- **macOS:** `PixSwap-macOS.zip` → unzip → open `PixSwap.app`

> **macOS first launch:** since the app isn't code-signed, right-click `PixSwap.app` → **Open** → **Open** the first time (or go to *System Settings → Privacy & Security* and click *Open Anyway*). After that it opens normally.
>
> **Windows SmartScreen:** the first time, you may see "Windows protected your PC" → click **More info** → **Run anyway**. This appears because the build isn't code-signed.

## Run from source

Requires Python 3.9+.

```bash
pip install -r requirements.txt
python photo_converter.py
```

## Build it yourself

```bash
pip install -r requirements.txt pyinstaller
pyinstaller --noconfirm --clean PixSwap.spec
```

Output lands in `dist/` — a `PixSwap` folder (Windows/Linux) or `PixSwap.app` (macOS).

## Custom icon (optional)

Drop an `icon.ico` (Windows) and/or `icon.icns` (macOS) in the project root. The build picks them up automatically — no other changes needed.

## Optional extras

- **AVIF** read/write depends on your `pillow-heif` build shipping the AVIF codec.
- **RAW** camera files (CR2, NEF, ARW, DNG, …): uncomment the `rawpy` and `numpy` lines in `requirements.txt` and reinstall. The app auto-detects them and enables RAW reading.

## How releases work

Every push to `main` builds both apps and uploads them as Actions artifacts. To publish a downloadable **Release**, create a tag/release (e.g. `v1.0`) on GitHub — the workflow then attaches the Windows and macOS zips to it automatically.

---

© LJ "HawaiizFynest" Eblacas. Built with Python, Pillow, and PyInstaller.
