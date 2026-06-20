# PixSwap — Project Handoff

Snapshot for picking this project up in a fresh session.

## What this is

**PixSwap** — a cross-platform (Windows / macOS / Linux) desktop GUI tool that converts
photos between formats **without losing detail** (full resolution, EXIF, ICC colour
profile, and DPI are all preserved). Drag photos in, pick a format, click Convert.

- **Author / credit shown in app + README:** `LJ "HawaiizFynest" Eblacas`
- **GitHub:** https://github.com/hawaiizfynest  (repo: https://github.com/hawaiizfynest/PixSwap)
- **Local folder:** `F:\GitHub\Repos\PixSwap`  (renamed from `photo-converter`)

## Current status — DONE and verified

- App fully built and working. The Windows `.exe` was built with PyInstaller and
  launch-tested successfully multiple times (it opens, runs, closes cleanly).
- Conversion engine smoke-tested: every output format works, resolution is preserved,
  and EXIF/DPI survive a JPEG round-trip. Alpha→JPEG flattening works.
- Custom app icon generated (blue→violet gradient, two photo tiles + swap arrows) and
  embedded into the exe + bundled for the window titlebar.
- GitHub Actions workflow auto-builds **both** the Windows `.exe` and macOS `.app` on
  every push to `main`/`master`, uploads them as artifacts, and attaches them to a
  GitHub Release when you publish a tag (e.g. `v1.0`).

> ⚠️ The macOS `.app` has only been built/verified by CI design, not run on a real Mac
> (development happened on Windows). PyInstaller's macOS path is standard and the spec
> handles `.app` bundling correctly, but the very first Mac build is the real test — if
> it hiccups, grab the Actions log and debug from there.

## Files in the repo

| File | Purpose |
|------|---------|
| `photo_converter.py` | The app (GUI + conversion engine). Script name is internal; the app/exe/.app are all "PixSwap". |
| `requirements.txt` | Deps: Pillow, pillow-heif, tkinterdnd2 (rawpy/numpy commented out = optional RAW support). |
| `PixSwap.spec` | PyInstaller build recipe. Auto-detects `icon.ico`/`icon.icns`, bundles tkinterdnd2 + pillow-heif binaries. |
| `make_icons.py` | Regenerates the icons. Run `python make_icons.py` to rebuild them after tweaking. Safe to delete if you don't want it public. |
| `icon.ico` / `icon.icns` / `icon.png` | App icons (Windows / macOS / master+window). |
| `README.md` | User-facing docs + author credit + download instructions. |
| `.github/workflows/build.yml` | CI that builds both apps. |
| `.gitignore` | Keeps `build/`, `dist/`, `__pycache__/` out of git. |

## How to build locally (Windows)

```bash
pip install -r requirements.txt pyinstaller
python -m PyInstaller --noconfirm --clean PixSwap.spec
```
Output: `dist/PixSwap/PixSwap.exe` (one-folder build).

## How to run from source

```bash
pip install -r requirements.txt
python photo_converter.py
```

## Capabilities on the dev machine (Windows, Python 3.14)

- HEIC/HEIF read+write: **ON** (pillow-heif)
- AVIF: **OFF** (this pillow-heif build didn't ship the AVIF codec)
- RAW (CR2/NEF/ARW/DNG): **OFF** (uncomment `rawpy`+`numpy` in requirements.txt to enable)
- Drag-and-drop: **ON** (tkinterdnd2)

## Formats

- **Write:** JPEG, PNG, WebP, TIFF, BMP, GIF, ICO, TGA, PPM, PDF, HEIC
- **Read:** all of the above plus JP2, EPS, HEIC/HEIF, and more (33 extensions total)

## Publishing checklist (next steps for the user)

1. Create a GitHub repo named **PixSwap** under `hawaiizfynest`.
2. In GitHub Desktop, add `F:\GitHub\Repos\PixSwap` as a local repo and publish it.
3. First push to `main` → Actions builds both apps automatically (Actions tab → latest
   run → Artifacts: `PixSwap-Windows.zip`, `PixSwap-macOS.zip`).
4. For permanent download links, create a Release tagged `v1.0` — zips attach to it.

## Possible future work / open ideas

- Enable AVIF (needs a pillow-heif build with the AVIF codec, or libheif w/ aom/dav1d).
- Code-signing to remove the Windows SmartScreen / macOS Gatekeeper warnings (costs $).
- Add a custom-icon-driven GitHub social preview image.
- Optional: rename `photo_converter.py` → `pixswap.py` (would require updating the
  README run command and the `Analysis([...])` entry in `PixSwap.spec`). Left as-is
  because the filename is not user-facing.
