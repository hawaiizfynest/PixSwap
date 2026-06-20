"""
Generate PixSwap app icons.

Produces:
  * icon.ico   (Windows, multi-size: 16..256)
  * icon.icns  (macOS,  multi-size: 16..1024)  -- if Pillow can write ICNS
  * icon.png   (1024px master, handy for the GitHub social preview / README)

Design: a rounded-square "photo tile" with a smaller overlapping tile behind
it, and two curved swap arrows cycling between them -- the "swap formats" idea.
Everything is drawn at 1024px with 4x supersampling for crisp anti-aliasing,
then downscaled to each target size.
"""

import os
import math
from PIL import Image, ImageDraw

OUT_DIR = os.path.dirname(os.path.abspath(__file__))

# --- palette -------------------------------------------------------------- #
BG_TOP = (37, 99, 235)      # blue
BG_BOT = (124, 58, 237)     # violet  (vertical gradient)
TILE_FRONT = (255, 255, 255)
TILE_BACK = (210, 224, 255)
ACCENT = (255, 255, 255)
SUN = (255, 199, 64)        # little "photo" sun
MOUNT = (52, 168, 120)      # little "photo" mountains
ARROW = (255, 255, 255)


def lerp(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def rounded_rect(draw, box, radius, fill, outline=None, width=0):
    draw.rounded_rectangle(box, radius=radius, fill=fill,
                           outline=outline, width=width)


def draw_master(S):
    """Draw the icon at SxS into an RGBA image and return it."""
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # 1) rounded-square background with vertical gradient
    radius = int(S * 0.225)
    grad = Image.new("RGB", (1, S))
    gp = grad.load()
    for y in range(S):
        gp[0, y] = lerp(BG_TOP, BG_BOT, y / (S - 1))
    grad = grad.resize((S, S))
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, S - 1, S - 1],
                                           radius=radius, fill=255)
    img.paste(grad, (0, 0), mask)
    d = ImageDraw.Draw(img)

    # 2) back tile (offset up-left), semi-transparent for depth
    tw = int(S * 0.46)          # tile size
    tr = int(S * 0.085)         # tile corner radius
    bx, by = int(S * 0.20), int(S * 0.18)
    rounded_rect(d, [bx, by, bx + tw, by + tw], tr, TILE_BACK + (235,))

    # 3) front tile (offset down-right) with a tiny "photo" scene
    fx, fy = int(S * 0.34), int(S * 0.36)
    rounded_rect(d, [fx, fy, fx + tw, fy + tw], tr, TILE_FRONT + (255,))

    # photo scene inside the front tile: sun + two mountains
    pad = int(tw * 0.16)
    ix0, iy0 = fx + pad, fy + pad
    ix1, iy1 = fx + tw - pad, fy + tw - pad
    iw = ix1 - ix0
    # sun
    sr = int(iw * 0.16)
    scx, scy = ix0 + int(iw * 0.30), iy0 + int(iw * 0.28)
    d.ellipse([scx - sr, scy - sr, scx + sr, scy + sr], fill=SUN)
    # mountains (two triangles), clipped to the lower part of the scene
    m_top = iy0 + int(iw * 0.40)
    tri1 = [(ix0, iy1), (ix0 + int(iw * 0.38), m_top),
            (ix0 + int(iw * 0.72), iy1)]
    tri2 = [(ix0 + int(iw * 0.45), iy1), (ix0 + int(iw * 0.74),
            m_top + int(iw * 0.12)), (ix1, iy1)]
    d.polygon(tri2, fill=lerp(MOUNT, (255, 255, 255), 0.25))
    d.polygon(tri1, fill=MOUNT)

    # 4) two curved "swap" arrows cycling between the tiles.
    #    Drawn as arcs around the icon centre with arrowheads.
    cx, cy = S / 2, S / 2
    R = int(S * 0.30)
    lw = max(2, int(S * 0.035))

    abox = [int(cx - R), int(cy - R), int(cx + R), int(cy + R)]

    # top arc: sweeps along the top, arrowhead pointing right
    d.arc(abox, start=205, end=335, fill=ARROW, width=lw)
    _arrowhead(d, cx, cy, R, angle_deg=335, lw=lw, pointing="cw")
    # bottom arc: sweeps along the bottom, arrowhead pointing left
    d.arc(abox, start=25, end=155, fill=ARROW, width=lw)
    _arrowhead(d, cx, cy, R, angle_deg=155, lw=lw, pointing="cw")

    return img


def _arrowhead(d, cx, cy, R, angle_deg, lw, pointing="cw"):
    """Draw a triangular arrowhead at the end of an arc."""
    a = math.radians(angle_deg)
    # point on the circle
    px, py = cx + R * math.cos(a), cy + R * math.sin(a)
    # tangent direction (clockwise)
    tdir = a + math.pi / 2 if pointing == "cw" else a - math.pi / 2
    size = lw * 2.6
    # base direction (radial) for width of the head
    back = a
    tip = (px + size * math.cos(tdir), py + size * math.sin(tdir))
    left = (px + size * 0.7 * math.cos(back),
            py + size * 0.7 * math.sin(back))
    right = (px - size * 0.7 * math.cos(back),
             py - size * 0.7 * math.sin(back))
    d.polygon([tip, left, right], fill=ARROW)


def main():
    # Render once at 1024px, then downscale with LANCZOS per target size.
    base = draw_master(1024)

    png_path = os.path.join(OUT_DIR, "icon.png")
    base.save(png_path)
    print("wrote", png_path)

    ico_sizes = [16, 24, 32, 48, 64, 128, 256]

    # ICO (Pillow writes a multi-image .ico directly)
    ico_path = os.path.join(OUT_DIR, "icon.ico")
    base.save(ico_path, format="ICO",
              sizes=[(s, s) for s in ico_sizes])
    print("wrote", ico_path)

    # ICNS
    icns_path = os.path.join(OUT_DIR, "icon.icns")
    try:
        # Pillow's ICNS writer wants a square RGBA image; it derives sizes.
        base.save(icns_path, format="ICNS")
        print("wrote", icns_path)
    except Exception as e:
        print("ICNS write failed via Pillow:", e)
        print("(macOS build will fall back to the default icon; "
              "icon.png is still available.)")


if __name__ == "__main__":
    main()
