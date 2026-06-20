#!/usr/bin/env python3
"""
PixSwap
=======

A simple cross-platform (Windows / macOS / Linux) GUI tool that converts images
between formats while preserving as much detail as possible:

  * full pixel resolution (images are never resized)
  * EXIF metadata (camera, date, GPS, orientation, ...)
  * ICC colour profiles
  * DPI / print resolution

Just run it, drag in some photos (or click "Add Files"), pick a target format,
and hit Convert.

Written by LJ "HawaiizFynest" Eblacas — https://github.com/hawaiizfynest
"""

import os
import sys
import threading
import queue
import traceback
import webbrowser

# --------------------------------------------------------------------------- #
#  Image backend (Pillow) + optional plugins
# --------------------------------------------------------------------------- #
try:
    from PIL import Image
except ImportError:
    print("Pillow is not installed.\n\nRun:  pip install -r requirements.txt")
    sys.exit(1)

# Allow very large images without the "decompression bomb" warning blocking us.
Image.MAX_IMAGE_PIXELS = None

# Optional HEIC / HEIF / AVIF support (iPhone photos, modern web formats).
HEIF_OK = False
AVIF_OK = False
try:
    import pillow_heif

    pillow_heif.register_heif_opener()
    HEIF_OK = True
    try:
        pillow_heif.register_avif_opener()
        AVIF_OK = True
    except Exception:
        AVIF_OK = False
except Exception:
    HEIF_OK = False

# Optional RAW camera support (CR2, NEF, ARW, DNG, ...).
RAW_OK = False
try:
    import rawpy  # noqa: F401

    RAW_OK = True
except Exception:
    RAW_OK = False

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

# Optional drag-and-drop (makes the app nicer; degrades gracefully if missing).
DND_OK = False
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD

    DND_OK = True
except Exception:
    DND_OK = False


# --------------------------------------------------------------------------- #
#  Format tables
# --------------------------------------------------------------------------- #
RAW_EXTS = {
    ".cr2", ".cr3", ".nef", ".arw", ".dng", ".raf", ".rw2",
    ".orf", ".srw", ".pef", ".raw", ".3fr", ".erf", ".kdc",
}

READ_EXTS = {
    ".jpg", ".jpeg", ".jpe", ".jfif", ".png", ".gif", ".bmp", ".dib",
    ".tif", ".tiff", ".webp", ".ico", ".ppm", ".pgm", ".pbm", ".pnm",
    ".tga", ".dds", ".jp2", ".j2k", ".jpf", ".jpx", ".eps", ".im",
    ".pcx", ".sgi", ".xbm", ".icns", ".blp", ".ftex",
}
if HEIF_OK:
    READ_EXTS |= {".heic", ".heif", ".hif"}
if AVIF_OK:
    READ_EXTS |= {".avif"}
if RAW_OK:
    READ_EXTS |= RAW_EXTS

# (label shown in dropdown, Pillow format name, default extension)
WRITE_FORMATS = [
    ("JPEG  (.jpg)", "JPEG", ".jpg"),
    ("PNG   (.png)", "PNG", ".png"),
    ("WebP  (.webp)", "WEBP", ".webp"),
    ("TIFF  (.tiff)", "TIFF", ".tiff"),
    ("BMP   (.bmp)", "BMP", ".bmp"),
    ("GIF   (.gif)", "GIF", ".gif"),
    ("ICO   (.ico)", "ICO", ".ico"),
    ("TGA   (.tga)", "TGA", ".tga"),
    ("PPM   (.ppm)", "PPM", ".ppm"),
    ("PDF   (.pdf)", "PDF", ".pdf"),
]
if HEIF_OK:
    WRITE_FORMATS.append(("HEIC  (.heic)", "HEIF", ".heic"))
if AVIF_OK:
    WRITE_FORMATS.append(("AVIF  (.avif)", "AVIF", ".avif"))

QUALITY_FORMATS = {"JPEG", "WEBP", "HEIF", "AVIF"}

# --------------------------------------------------------------------------- #
#  App identity
# --------------------------------------------------------------------------- #
APP_NAME = "PixSwap"
AUTHOR = 'LJ "HawaiizFynest" Eblacas'
GITHUB_URL = "https://github.com/hawaiizfynest"
GITHUB_REPO = "https://github.com/hawaiizfynest/PixSwap"


# --------------------------------------------------------------------------- #
#  Conversion core
# --------------------------------------------------------------------------- #
def load_image(path):
    """Open any supported file as a Pillow image (handles RAW via rawpy)."""
    ext = os.path.splitext(path)[1].lower()
    if RAW_OK and ext in RAW_EXTS:
        with rawpy.imread(path) as raw:
            rgb = raw.postprocess(use_camera_wb=True, no_auto_bright=True, output_bps=8)
        return Image.fromarray(rgb)
    img = Image.open(path)
    img.load()
    return img


def _flatten_alpha(img, bg=(255, 255, 255)):
    """Composite an image with transparency onto a solid background."""
    base = img.convert("RGBA")
    canvas = Image.new("RGBA", base.size, bg + (255,))
    canvas.paste(base, mask=base.split()[-1])
    return canvas.convert("RGB")


def prepare_for_format(img, fmt):
    """Convert the image to a pixel mode the target format can actually store."""
    f = fmt.upper()
    has_alpha = img.mode in ("RGBA", "LA", "PA") or (
        img.mode == "P" and "transparency" in img.info
    )

    # High-bit-depth / float modes only survive in PNG and TIFF.
    if img.mode in ("I", "I;16", "I;16B", "F") and f not in ("PNG", "TIFF"):
        img = img.convert("L")

    if f == "JPEG":
        if has_alpha or img.mode in ("P", "RGBA", "LA", "PA"):
            img = _flatten_alpha(img)
        elif img.mode not in ("RGB", "L", "CMYK"):
            img = img.convert("RGB")

    elif f in ("BMP", "PPM", "TGA"):
        if has_alpha:
            img = _flatten_alpha(img)
        elif img.mode not in ("RGB", "L", "1", "RGBA"):
            img = img.convert("RGB")

    elif f == "PDF":
        if has_alpha:
            img = _flatten_alpha(img)
        if img.mode not in ("RGB", "L", "CMYK"):
            img = img.convert("RGB")

    elif f == "GIF":
        if img.mode != "P":
            img = img.convert("P", palette=Image.ADAPTIVE, colors=256)

    elif f == "ICO":
        img = img.convert("RGBA")

    elif f in ("PNG", "WEBP", "TIFF", "HEIF", "AVIF"):
        if img.mode == "P":
            img = img.convert("RGBA" if has_alpha else "RGB")
        if img.mode == "CMYK" and f in ("WEBP", "HEIF", "AVIF"):
            img = img.convert("RGB")

    return img


def build_save_kwargs(fmt, quality, lossless):
    """Encoder options (quality, compression, etc.) for the target format."""
    f = fmt.upper()
    kw = {}
    if f in QUALITY_FORMATS:
        kw["quality"] = int(quality)
    if f == "JPEG":
        kw.update(optimize=True, progressive=True,
                  subsampling=0 if quality >= 90 else 2)
    elif f == "WEBP":
        if lossless:
            kw["lossless"] = True
            kw["quality"] = 100
        else:
            kw["method"] = 6
    elif f == "PNG":
        kw["optimize"] = True
    elif f == "TIFF":
        kw["compression"] = "tiff_lzw"  # lossless
    return kw


def safe_save(img, dst, fmt, save_kwargs, meta):
    """
    Save the image, trying hard to keep metadata. If a particular format/Pillow
    build rejects some metadata kwarg, progressively drop the optional bits
    rather than failing the whole conversion.

    Returns a short note describing what (if anything) was dropped.
    """
    f = fmt.upper()
    icc = {"icc_profile": meta["icc_profile"]} if meta.get("icc_profile") else {}
    exif = {"exif": meta["exif"]} if meta.get("exif") else {}
    dpi = {"dpi": meta["dpi"]} if meta.get("dpi") else {}

    trials = [
        ({**save_kwargs, **exif, **icc, **dpi}, ""),
        ({**save_kwargs, **exif, **icc}, "DPI not embedded"),
        ({**save_kwargs, **icc}, "EXIF not embedded"),
        ({**save_kwargs, **exif}, "ICC profile not embedded"),
        ({**save_kwargs}, "metadata not embedded for this format"),
        ({}, "saved with default options"),
    ]

    last_err = None
    for kwargs, note in trials:
        try:
            img.save(dst, format=f, **kwargs)
            return note
        except Exception as e:  # noqa: BLE001  (we want to try the next fallback)
            last_err = e
    raise last_err


def convert_one(src, out_dir, fmt, ext, quality, lossless, preserve_meta):
    """Convert a single file. Returns (dst_path, note)."""
    img = load_image(src)
    try:
        info = img.info
        meta = {}
        if preserve_meta:
            if info.get("exif"):
                meta["exif"] = info["exif"]
            elif hasattr(img, "getexif"):
                ex = img.getexif()
                if ex:
                    meta["exif"] = ex.tobytes()
            if info.get("icc_profile"):
                meta["icc_profile"] = info["icc_profile"]
            if info.get("dpi"):
                meta["dpi"] = info["dpi"]

        out_img = prepare_for_format(img, fmt)
        save_kwargs = build_save_kwargs(fmt, quality, lossless)

        base = os.path.splitext(os.path.basename(src))[0]
        dst = os.path.join(out_dir, base + ext)

        # Never silently overwrite the source file with itself.
        if os.path.abspath(dst) == os.path.abspath(src):
            dst = os.path.join(out_dir, base + "_converted" + ext)
        # Avoid clobbering an already-converted file from this batch.
        n = 1
        while os.path.exists(dst) and os.path.abspath(dst) != os.path.abspath(src):
            dst = os.path.join(out_dir, f"{base} ({n}){ext}")
            n += 1

        note = safe_save(out_img, dst, fmt, save_kwargs, meta)
        return dst, note
    finally:
        img.close()


# --------------------------------------------------------------------------- #
#  GUI
# --------------------------------------------------------------------------- #
class App:
    PAD = 8

    def __init__(self, root):
        self.root = root
        self.files = []                 # full source paths
        self.msg_q = queue.Queue()      # worker -> UI messages
        self.worker = None

        root.title(APP_NAME)
        root.minsize(640, 540)
        self._set_window_icon()
        try:
            ttk.Style().theme_use("clam")
        except Exception:
            pass

        self._build_ui()
        self.root.after(100, self._drain_queue)

    def _set_window_icon(self):
        """Set the titlebar/taskbar icon (from source or a PyInstaller bundle)."""
        base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
        # Prefer .ico on Windows (iconbitmap), fall back to PNG iconphoto.
        try:
            if sys.platform.startswith("win"):
                ico = os.path.join(base, "icon.ico")
                if os.path.exists(ico):
                    self.root.iconbitmap(ico)
                    return
            png = os.path.join(base, "icon.png")
            if os.path.exists(png):
                self._icon_img = tk.PhotoImage(file=png)
                self.root.iconphoto(True, self._icon_img)
        except Exception:
            pass  # a missing/odd icon should never stop the app from opening

    # -- layout ------------------------------------------------------------- #
    def _build_ui(self):
        P = self.PAD
        root = self.root

        # --- file list ---
        files_frame = ttk.LabelFrame(root, text="Photos to convert")
        files_frame.pack(fill="both", expand=True, padx=P, pady=(P, 0))

        list_wrap = ttk.Frame(files_frame)
        list_wrap.pack(fill="both", expand=True, padx=P, pady=P)

        self.listbox = tk.Listbox(list_wrap, selectmode="extended",
                                  activestyle="none", height=8)
        self.listbox.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(list_wrap, orient="vertical",
                           command=self.listbox.yview)
        sb.pack(side="right", fill="y")
        self.listbox.config(yscrollcommand=sb.set)

        if DND_OK:
            self.listbox.drop_target_register(DND_FILES)
            self.listbox.dnd_bind("<<Drop>>", self._on_drop)

        btns = ttk.Frame(files_frame)
        btns.pack(fill="x", padx=P, pady=(0, P))
        ttk.Button(btns, text="Add Files…",
                   command=self.add_files).pack(side="left")
        ttk.Button(btns, text="Add Folder…",
                   command=self.add_folder).pack(side="left", padx=(P, 0))
        ttk.Button(btns, text="Remove Selected",
                   command=self.remove_selected).pack(side="left", padx=(P, 0))
        ttk.Button(btns, text="Clear",
                   command=self.clear_files).pack(side="left", padx=(P, 0))

        hint = ("Drag & drop photos here, or use the buttons."
                if DND_OK else "Use the buttons above to add photos.")
        ttk.Label(files_frame, text=hint, foreground="#666").pack(
            anchor="w", padx=P, pady=(0, P))

        # --- options ---
        opt = ttk.LabelFrame(root, text="Options")
        opt.pack(fill="x", padx=P, pady=(P, 0))
        opt.columnconfigure(1, weight=1)

        ttk.Label(opt, text="Convert to:").grid(
            row=0, column=0, sticky="w", padx=P, pady=P)
        self.fmt_var = tk.StringVar(value=WRITE_FORMATS[0][0])
        self.fmt_box = ttk.Combobox(
            opt, textvariable=self.fmt_var, state="readonly",
            values=[f[0] for f in WRITE_FORMATS], width=18)
        self.fmt_box.grid(row=0, column=1, sticky="w", padx=P, pady=P)
        self.fmt_box.bind("<<ComboboxSelected>>", lambda e: self._sync_quality())

        # Quality
        self.quality_var = tk.IntVar(value=95)
        self.q_label = ttk.Label(opt, text="Quality:")
        self.q_label.grid(row=1, column=0, sticky="w", padx=P, pady=P)
        qrow = ttk.Frame(opt)
        qrow.grid(row=1, column=1, sticky="we", padx=P, pady=P)
        self.q_scale = ttk.Scale(qrow, from_=1, to=100, orient="horizontal",
                                 command=self._on_quality)
        self.q_scale.set(95)
        self.q_scale.pack(side="left", fill="x", expand=True)
        self.q_value = ttk.Label(qrow, text="95", width=4)
        self.q_value.pack(side="left", padx=(P, 0))

        self.lossless_var = tk.BooleanVar(value=False)
        self.lossless_chk = ttk.Checkbutton(
            opt, text="Lossless (WebP only)", variable=self.lossless_var)
        self.lossless_chk.grid(row=2, column=1, sticky="w", padx=P)

        self.meta_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            opt, text="Preserve metadata (EXIF, colour profile, DPI)",
            variable=self.meta_var).grid(row=3, column=1, sticky="w",
                                         padx=P, pady=(0, P))

        # Output folder
        ttk.Label(opt, text="Save to:").grid(
            row=4, column=0, sticky="w", padx=P, pady=P)
        orow = ttk.Frame(opt)
        orow.grid(row=4, column=1, sticky="we", padx=P, pady=P)
        self.out_var = tk.StringVar(value="")
        self.out_entry = ttk.Entry(orow, textvariable=self.out_var)
        self.out_entry.pack(side="left", fill="x", expand=True)
        ttk.Button(orow, text="Browse…",
                   command=self.choose_out).pack(side="left", padx=(P, 0))
        ttk.Label(opt, text="(leave blank to save into a 'converted' "
                            "subfolder next to each photo)",
                  foreground="#666").grid(row=5, column=1, sticky="w",
                                          padx=P, pady=(0, P))

        # --- action / progress ---
        action = ttk.Frame(root)
        action.pack(fill="x", padx=P, pady=P)
        self.convert_btn = ttk.Button(action, text="Convert",
                                      command=self.start_convert)
        self.convert_btn.pack(side="left")
        self.progress = ttk.Progressbar(action, mode="determinate")
        self.progress.pack(side="left", fill="x", expand=True, padx=(P, 0))

        # --- log ---
        log_frame = ttk.LabelFrame(root, text="Log")
        log_frame.pack(fill="both", expand=True, padx=P, pady=(0, P))
        self.log = tk.Text(log_frame, height=7, wrap="word", state="disabled")
        self.log.pack(side="left", fill="both", expand=True, padx=(P, 0), pady=P)
        lsb = ttk.Scrollbar(log_frame, orient="vertical", command=self.log.yview)
        lsb.pack(side="right", fill="y", pady=P)
        self.log.config(yscrollcommand=lsb.set)

        # --- credit footer ---
        footer = ttk.Frame(root)
        footer.pack(fill="x", padx=P, pady=(0, P))
        ttk.Label(footer, text=f"{APP_NAME} — Written by {AUTHOR}",
                  foreground="#666").pack(side="left")
        link = tk.Label(footer, text=GITHUB_URL, fg="#1a73e8",
                        cursor="hand2")
        f = link.cget("font")
        link.config(font=(f if isinstance(f, str) else "TkDefaultFont"))
        link.pack(side="right")
        link.bind("<Button-1>",
                  lambda e: webbrowser.open_new(GITHUB_REPO))

        self._sync_quality()
        caps = []
        caps.append("HEIC/HEIF " + ("on" if HEIF_OK else "off"))
        caps.append("AVIF " + ("on" if AVIF_OK else "off"))
        caps.append("RAW " + ("on" if RAW_OK else "off"))
        self._log("Ready. Capabilities: " + ", ".join(caps) + ".")

    # -- option helpers ----------------------------------------------------- #
    def _on_quality(self, _evt=None):
        v = int(round(float(self.q_scale.get())))
        self.quality_var.set(v)
        self.q_value.config(text=str(v))

    def _current_fmt(self):
        label = self.fmt_var.get()
        for lbl, fmt, ext in WRITE_FORMATS:
            if lbl == label:
                return fmt, ext
        return WRITE_FORMATS[0][1], WRITE_FORMATS[0][2]

    def _sync_quality(self):
        fmt, _ = self._current_fmt()
        uses_q = fmt in QUALITY_FORMATS
        state = "normal" if uses_q else "disabled"
        self.q_scale.config(state=state)
        self.q_label.config(state=state)
        self.q_value.config(state=state)
        self.lossless_chk.config(
            state="normal" if fmt == "WEBP" else "disabled")

    # -- file management ---------------------------------------------------- #
    def _add_paths(self, paths):
        added = 0
        for p in paths:
            p = os.path.abspath(p)
            if os.path.isdir(p):
                for name in sorted(os.listdir(p)):
                    fp = os.path.join(p, name)
                    if os.path.isfile(fp) and self._is_image(fp):
                        if fp not in self.files:
                            self.files.append(fp)
                            self.listbox.insert("end", os.path.basename(fp))
                            added += 1
            elif os.path.isfile(p) and self._is_image(p):
                if p not in self.files:
                    self.files.append(p)
                    self.listbox.insert("end", os.path.basename(p))
                    added += 1
        if added:
            self._log(f"Added {added} file(s). Total: {len(self.files)}.")

    @staticmethod
    def _is_image(path):
        return os.path.splitext(path)[1].lower() in READ_EXTS

    def add_files(self):
        exts = " ".join("*" + e for e in sorted(READ_EXTS))
        paths = filedialog.askopenfilenames(
            title="Select photos",
            filetypes=[("Images", exts), ("All files", "*.*")])
        if paths:
            self._add_paths(paths)

    def add_folder(self):
        d = filedialog.askdirectory(title="Select a folder of photos")
        if d:
            self._add_paths([d])

    def remove_selected(self):
        for i in reversed(self.listbox.curselection()):
            self.listbox.delete(i)
            del self.files[i]

    def clear_files(self):
        self.listbox.delete(0, "end")
        self.files.clear()

    def choose_out(self):
        d = filedialog.askdirectory(title="Choose output folder")
        if d:
            self.out_var.set(d)

    def _on_drop(self, event):
        # tkinterdnd2 returns a brace/space delimited string of paths.
        paths = self.root.tk.splitlist(event.data)
        self._add_paths(paths)

    # -- conversion --------------------------------------------------------- #
    def start_convert(self):
        if self.worker and self.worker.is_alive():
            return
        if not self.files:
            messagebox.showinfo("Nothing to do", "Add some photos first.")
            return

        fmt, ext = self._current_fmt()
        quality = self.quality_var.get()
        lossless = self.lossless_var.get() and fmt == "WEBP"
        preserve = self.meta_var.get()
        out_dir = self.out_var.get().strip() or None
        files = list(self.files)

        self.convert_btn.config(state="disabled")
        self.progress.config(maximum=len(files), value=0)
        self._log(f"\nConverting {len(files)} file(s) to {fmt}…")

        self.worker = threading.Thread(
            target=self._worker, daemon=True,
            args=(files, out_dir, fmt, ext, quality, lossless, preserve))
        self.worker.start()

    def _worker(self, files, out_dir, fmt, ext, quality, lossless, preserve):
        ok = fail = 0
        last_dir = None
        for i, src in enumerate(files, 1):
            try:
                target = out_dir or os.path.join(os.path.dirname(src), "converted")
                os.makedirs(target, exist_ok=True)
                dst, note = convert_one(
                    src, target, fmt, ext, quality, lossless, preserve)
                last_dir = target
                ok += 1
                suffix = f"  [{note}]" if note else ""
                self.msg_q.put(("log",
                    f"  ✓ {os.path.basename(src)} → {os.path.basename(dst)}{suffix}"))
            except Exception as e:  # noqa: BLE001
                fail += 1
                self.msg_q.put(("log",
                    f"  ✗ {os.path.basename(src)} — {e}"))
                self.msg_q.put(("trace", traceback.format_exc()))
            self.msg_q.put(("progress", i))
        self.msg_q.put(("done", (ok, fail, last_dir)))

    # -- UI message pump ---------------------------------------------------- #
    def _drain_queue(self):
        try:
            while True:
                kind, payload = self.msg_q.get_nowait()
                if kind == "log":
                    self._log(payload)
                elif kind == "trace":
                    # Keep tracebacks out of the main log; print to stderr.
                    print(payload, file=sys.stderr)
                elif kind == "progress":
                    self.progress.config(value=payload)
                elif kind == "done":
                    ok, fail, last_dir = payload
                    self._log(f"Done. {ok} converted, {fail} failed.")
                    self.convert_btn.config(state="normal")
                    if ok and last_dir:
                        if messagebox.askyesno(
                                "Conversion complete",
                                f"{ok} file(s) converted"
                                + (f", {fail} failed." if fail else ".")
                                + "\n\nOpen the output folder?"):
                            self._open_folder(last_dir)
                    elif fail:
                        messagebox.showwarning(
                            "Conversion finished",
                            f"All {fail} file(s) failed. See the log.")
        except queue.Empty:
            pass
        self.root.after(100, self._drain_queue)

    def _log(self, text):
        self.log.config(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.config(state="disabled")

    @staticmethod
    def _open_folder(path):
        try:
            if sys.platform.startswith("win"):
                os.startfile(path)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                import subprocess
                subprocess.Popen(["open", path])
            else:
                import subprocess
                subprocess.Popen(["xdg-open", path])
        except Exception:
            pass


def main():
    root = TkinterDnD.Tk() if DND_OK else tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
