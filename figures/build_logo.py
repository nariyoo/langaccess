"""Build the langaccess identity: mark, small variant, lockups, social, favicons.

    python build_logo.py                 # the whole set, then verify it

THE MARK. A page of English text whose lower corner is turned back, and what
the fold uncovers is not more of the same page but another layer, in the accent,
carrying its own line of writing. That is the subject the package is about: a
person who does not read English arriving at a public or nonprofit website, and
whether there is anything under the English for them. Chosen by Nari on
2026-07-29 from the G sheet, where it is variant G3.

THE SMALL VARIANT, and why there is one. The mark's reveal is a triangle, and a
triangle is a poor container: at 32 px the line of writing inside it disappears
and all that survives is a document with a coloured corner, which says nothing
about language. The fold cannot simply be opened up to fix this, because past
roughly half the page's diagonal it stops reading as a turned corner and becomes
a stroke drawn across a page, which is the universal prohibition sign and reads
as language access denied. Both jaws of that trap were measured on the G sheet.

So the favicon is not a reduction of the mark. It is a second drawing of the
same idea with the small size designed into it, the way an identity normally
carries a small variant: same page, same fold, same accent, but three body rules
cut to two, every stroke heavier, the fold opened from 48 to 57 per cent of the
diagonal (tested, still a corner), and the line of writing under the fold set at
exactly the weight of the body rules above it, so the eye reads it as another
line of text rather than as a label. Everything that makes the large mark
refined is what kills it small, and none of it is load-bearing.

THE REVEAL IS A KNOCKOUT, not a white bar. The line of writing under the fold is
a hole cut through the accent, so it takes the colour of whatever the logo is
placed on. That is what lets one geometry serve the light files, the reversed
files and the opaque social card without a white sliver appearing on a dark
background.

The register is inherited from build_system.py and is not negotiable: line-drawn
vector geometry in a 100-unit grid, ink and one accent, flat, square corners,
heavy strokes, matplotlib patches only. No gradients, shadows, glows, bevels,
icon fonts, images or emoji. The wordmark is Arial and a missing Arial is a hard
failure; it travels in the SVGs as outlines, never as a text element.

Geometry is written in a 100-unit grid, centred on its own bounding box, then
scaled into whatever figure is being written, so the favicon and the 1024 px
mark are the same drawing at two sizes rather than two drawings.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Rectangle, Polygon, PathPatch
from matplotlib.path import Path as MPath
from matplotlib.lines import Line2D
from matplotlib import font_manager as fm
from PIL import Image

HERE = Path(__file__).resolve().parent

INK = "#1B1F23"
ACCENT = "#2F3E75"
WHITE = "#FFFFFF"

# The reversed pair. Ink becomes a near-white; the accent is lightened only as
# far as it must be to hold contrast on a dark canvas. Unchanged, #2F3E75 sits
# at 1.9:1 on GitHub's dark ground and all but vanishes; #6F82C8 holds 5.1:1
# there while staying the same hue and well short of a pastel. Both ratios are
# recomputed and asserted at the end of every build.
INK_DARK = "#F2F3F5"
ACCENT_DARK = "#6F82C8"
DARK_CANVAS = "#0D1117"          # GitHub's dark ground, what the pair is for

WORD = "langaccess"
WORDFACE = "Franklin Gothic Demi"   # chosen 2026-08-08 from a 24-option sheet
CAP = 0.667          # the cap height of WORDFACE as a fraction of the em,
                     # MEASURED off the font file rather than assumed, for
                     # optical centring: the word is hung so its capital band,
                     # not its bounding box, is on the mark's centre line.
                     # Arial's is 0.716, so a face swap that skipped this
                     # would sit the word high by half a per cent of the em.


class Palette:
    def __init__(self, ink, accent, name):
        self.ink, self.accent, self.name = ink, accent, name


LIGHT = Palette(INK, ACCENT, "light")
DARK = Palette(INK_DARK, ACCENT_DARK, "dark")


# ------------------------------------------------------------------ scaffolding
def arial_or_die():
    """Register the wordmark face, or stop. A silent substitution ships a
    lockup in a typeface nobody chose, and the SVGs carry outlines, so the
    substitution would be invisible afterwards."""
    names = {f.name for f in fm.fontManager.ttflist}
    if WORDFACE not in names:
        raise FileNotFoundError(
            "%s is not registered with matplotlib; the wordmark cannot be set"
            % WORDFACE)
    plt.rcParams["font.family"] = WORDFACE
    plt.rcParams["svg.fonttype"] = "path"   # wordmark travels as outlines


def new_fig(w_in, h_in, xspan, dpi):
    """A figure whose axes fill it exactly. Returns (fig, ax, points-per-unit)."""
    fig = plt.figure(figsize=(w_in, h_in), dpi=dpi)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, xspan)
    ax.set_ylim(0, xspan * h_in / w_in)
    ax.set_aspect("equal")
    ax.axis("off")
    return fig, ax, w_in / xspan * 72.0


class Pen:
    """Draws the 100-unit mark geometry at a given centre, size and scale."""

    def __init__(self, ax, cx, cy, side, ppu, grid, pal=LIGHT):
        # `side` is the mark's long edge in data units; `grid` its long edge
        # in the 100-unit drawing space.
        self.ax = ax
        self.k = side / grid
        self.cx, self.cy = cx, cy
        self.pal = pal

    def X(self, x):
        return self.cx + x * self.k

    def Y(self, y):
        return self.cy + y * self.k

    def lw(self, w, ppu):
        return w * self.k * ppu


def line(pen, x0, y0, x1, y1, w, ppu, color=INK, z=5, cap="butt"):
    pen.ax.add_line(Line2D([pen.X(x0), pen.X(x1)], [pen.Y(y0), pen.Y(y1)],
                           lw=pen.lw(w, ppu), color=color, zorder=z,
                           solid_capstyle=cap))


def box(pen, x0, y0, w, h, lwid, ppu, ec=INK, fc="none", z=5):
    pen.ax.add_patch(Rectangle((pen.X(x0), pen.Y(y0)), w * pen.k, h * pen.k,
                               facecolor=fc,
                               edgecolor=("none" if ec is None else ec),
                               lw=(0 if ec is None else pen.lw(lwid, ppu)),
                               joinstyle="miter", zorder=z))


def _signed_area(pts):
    return 0.5 * sum(x0 * y1 - x1 * y0
                     for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]))


def holed(pen, outer, hole, color, z=3):
    """A filled polygon with a rectangle cut clean out of it.

    The inner ring is wound the opposite way round from the outer one, which
    makes the hole a hole under either fill rule, so it survives both the Agg
    raster and the SVG writer whatever either decides to apply. The winding is
    measured rather than assumed: reversing the inner ring blindly is what
    produced a solid triangle on the first build, because the rectangle helper
    already returns the opposite direction from the triangle.

    This is why the line of writing under the fold reads on white, on the dark
    pair and on the opaque social card without ever being painted a colour.
    """
    o = [(pen.X(x), pen.Y(y)) for x, y in outer]
    i = [(pen.X(x), pen.Y(y)) for x, y in hole]
    if (_signed_area(i) > 0) == (_signed_area(o) > 0):
        i = i[::-1]
    verts = o + [o[0]] + i + [i[0]]
    codes = ([MPath.MOVETO] + [MPath.LINETO] * (len(o) - 1) + [MPath.CLOSEPOLY]
             + [MPath.MOVETO] + [MPath.LINETO] * (len(i) - 1)
             + [MPath.CLOSEPOLY])
    pen.ax.add_patch(PathPatch(MPath(verts, codes), facecolor=color,
                               edgecolor="none", zorder=z))


def rect_pts(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


BORDER = 7.0          # the shared heavy outline weight


# ------------------------------------------------------------- the shipped mark
def mark_page(pen, ppu):
    """The mark: a page whose turned corner uncovers another language.

    Three body rules, the last one short the way a paragraph's last line is
    short. The fold runs at 45 degrees over 48 per cent of the page's diagonal,
    which is the largest setting that still reads as a turned corner. Under it,
    a line of writing knocked out of the accent.
    """
    pal = pen.pal
    holed(pen, [(40, -6), (40, -50), (-4, -50)],
          rect_pts(16, -44.5, 36, -31.5), pal.accent, z=3)
    box(pen, -40, -50, 80, 100, BORDER, ppu, ec=pal.ink, z=5)
    for y, x1 in ((32.0, 28.0), (14.0, 28.0), (-4.0, 10.0)):
        line(pen, -28, y, x1, y, 9.0, ppu, color=pal.ink, z=6)
    line(pen, 40, -6, -4, -50, BORDER, ppu, color=pal.ink, z=6)      # the fold


def mark_page_small(pen, ppu):
    """The same mark drawn for 32 px.

    Two body rules instead of three and every stroke heavier, so nothing is
    left that a reduction can turn to grey. The fold is opened from 48 to 57
    per cent of the diagonal, which buys the reveal half again its area and was
    checked to still read as a corner rather than as a stroke across the page.
    The line of writing under the fold is set at the body rules' own weight, so
    it reads as one more line of text on another layer instead of as a label.
    """
    pal = pen.pal
    holed(pen, [(40, 2), (40, -50), (-12, -50)],
          rect_pts(10, -42, 36, -30), pal.accent, z=3)
    box(pen, -40, -50, 80, 100, 8.0, ppu, ec=pal.ink, z=5)
    for y in (30.0, 10.0):
        line(pen, -28, y, 28, y, 12.0, ppu, color=pal.ink, z=6)
    line(pen, 40, 2, -12, -50, 8.0, ppu, color=pal.ink, z=6)         # the fold


# name -> (draw function, long edge, width of its geometry)
SHIPPED = {"mark": (mark_page, 100.0, 80.0),
           "small": (mark_page_small, 100.0, 80.0)}


def draw(ax, spec, cx, cy, side, ppu, pal=LIGHT):
    fn, grid, _ = spec
    fn(Pen(ax, cx, cy, side, ppu, grid, pal), ppu)


def aspect(spec):
    """Mark width as a fraction of its height."""
    _, grid, wide = spec
    return wide / grid


# ------------------------------------------------- round one, kept reproducible
def mark_diff(pen, ppu):
    """A: two page rectangles overlapping; the intersection is the accent."""
    pw, ph = 56.0, 72.0
    ax0, ay0 = -43.0, -20.0
    bx0, by0 = -13.0, -52.0
    ix0, iy0 = bx0, ay0
    ix1, iy1 = ax0 + pw, by0 + ph
    box(pen, ix0, iy0, ix1 - ix0, iy1 - iy0, 0, ppu, ec=None, fc=ACCENT, z=3)
    for x0, y0 in ((ax0, ay0), (bx0, by0)):
        box(pen, x0, y0, pw, ph, BORDER, ppu, z=5)
    line(pen, ax0 + 9, 40, ax0 + pw - 9, 40, 7.0, ppu)
    line(pen, bx0 + 9, -40, bx0 + pw - 9, -40, 7.0, ppu)


def mark_split(pen, ppu):
    """B: one page split down the middle, two writing systems."""
    w, h = 74.0, 96.0
    x0, y0 = -w / 2, -h / 2
    box(pen, x0 + w / 2, y0, w / 2, h, 0, ppu, ec=None, fc=ACCENT, z=3)
    box(pen, x0, y0, w, h, BORDER, ppu, z=6)
    line(pen, 0, y0, 0, y0 + h, BORDER, ppu, z=6)
    base = -15.0
    line(pen, -30, base, -6, base, 7.0, ppu, z=6)
    for x in (-27.5, -18.0, -8.5):
        line(pen, x, base, x, base + 30, 7.0, ppu, z=6)
    head = 15.0
    line(pen, 6, head, 30, head, 7.0, ppu, color=WHITE, z=6)
    for x in (8.5, 18.0, 27.5):
        line(pen, x, head, x, head - 30, 7.0, ppu, color=WHITE, z=6)


def mark_noteq(pen, ppu):
    """C: a page carrying a not-equal sign, the slash in the accent."""
    w, h = 76.0, 96.0
    x0, y0 = -w / 2, -h / 2
    box(pen, x0, y0, w, h, BORDER, ppu, z=5)
    for y in (16.0, -16.0):
        line(pen, -24, y, 24, y, 9.0, ppu, z=6)
    line(pen, -19, -34, 19, 34, 9.0, ppu, color=ACCENT, z=7)


MARKS = {"A": (mark_diff, "two readings of one page", 104.0, 86.0),
         "B": (mark_split, "one page, two writing systems", 96.0, 74.0),
         "C": (mark_noteq, "the two readings are not equal", 96.0, 76.0)}




# ------------------------------------------------------------------- outputs
def write_mark(spec, stem, pal=LIGHT, px=1024, pad=0.13, svg=True):
    """Square, transparent, the mark alone with even padding."""
    dpi = 200
    inches = px / dpi
    fig, ax, ppu = new_fig(inches, inches, 1.0, dpi)
    draw(ax, spec, 0.5, 0.5, 1.0 - 2 * pad, ppu, pal)
    made = [HERE / f"{stem}.png"]
    fig.savefig(made[0], dpi=dpi, transparent=True)
    if svg:
        made.append(HERE / f"{stem}.svg")
        fig.savefig(made[1], transparent=True)
    plt.close(fig)
    return made


def text_width_pt(s, fontsize, weight):
    fig = plt.figure(figsize=(12, 2), dpi=100)
    t = fig.text(0.05, 0.5, s, fontsize=fontsize, fontweight=weight)
    fig.canvas.draw()
    bb = t.get_window_extent(renderer=fig.canvas.get_renderer())
    plt.close(fig)
    return bb.width / 100.0 * 72.0


def lockup_layout(spec, mark_in, fontsize):
    """Lay the mark and the wordmark out on one line.

    One data unit is one mark height, so a size in points converts to units
    by dividing by the mark height in points.
    """
    ppu_pt = mark_in * 72.0
    tw = text_width_pt(WORD, fontsize, "bold") / ppu_pt
    mw = aspect(spec)
    gap = 0.30
    padx, pady = 0.14, 0.20
    xspan = padx + mw + gap + tw + padx
    h_units = 1.0 + 2 * pady
    return (xspan * mark_in, h_units * mark_in, xspan, padx + mw / 2,
            padx + mw + gap, h_units / 2)


def lockup(ax, spec, ppu, mark_in, fontsize, x, ycen, pal, unit_in=1.0):
    """Draw mark plus wordmark. `unit_in` is one data unit in inches."""
    mw = aspect(spec) * mark_in
    draw(ax, spec, x + mw / 2, ycen, mark_in, ppu, pal)
    base = ycen - 0.5 * CAP * fontsize / 72.0 / unit_in
    gap = 0.30 * mark_in
    ax.text(x + mw + gap, base, WORD, ha="left", va="baseline",
            fontsize=fontsize, fontweight="normal", color=pal.ink, zorder=6)
    return mw + gap + text_width_pt(WORD, fontsize, "bold") / 72.0 / unit_in


def write_lockup(spec, stem, pal=LIGHT, dpi=200):
    mark_in = 1.10
    fontsize = 62.0          # points, against a 1.10 in mark
    w_in, h_in, xspan, _, _, ycen = lockup_layout(spec, mark_in, fontsize)
    fig, ax, ppu = new_fig(w_in, h_in, xspan, dpi)
    lockup(ax, spec, ppu, 1.0, fontsize, 0.14, ycen, pal, unit_in=mark_in)
    png, svg = HERE / f"{stem}.png", HERE / f"{stem}.svg"
    fig.savefig(png, dpi=dpi, transparent=True)
    fig.savefig(svg, transparent=True)
    plt.close(fig)
    return [png, svg]


def write_social(spec, stem):
    dpi = 100
    w_in, h_in = 12.80, 6.40
    xspan = 12.80            # one unit == one inch
    fig, ax, ppu = new_fig(w_in, h_in, xspan, dpi)
    ax.add_patch(Rectangle((0, 0), xspan, xspan * h_in / w_in,
                           facecolor=WHITE, edgecolor="none", zorder=0))
    mark_in = 2.30
    fontsize = 118.0
    tw = text_width_pt(WORD, fontsize, "bold") / 72.0     # inches
    mw = aspect(spec) * mark_in
    total = mw + 0.30 * mark_in + tw
    lockup(ax, spec, ppu, mark_in, fontsize, (w_in - total) / 2, h_in / 2,
           LIGHT)
    png = HERE / f"{stem}.png"
    fig.savefig(png, dpi=dpi, facecolor=WHITE)
    plt.close(fig)
    return [png]


def write_favicons(spec, sizes=(32, 64)):
    """The small variant, rendered large and resampled down as a browser would."""
    made = []
    for s in sizes:
        dpi, big = 200, 1024
        inches = big / dpi
        fig, ax, ppu = new_fig(inches, inches, 1.0, dpi)
        draw(ax, spec, 0.5, 0.5, 1.0 - 2 * 0.05, ppu, LIGHT)   # tighter padding
        tmp = HERE / f"_favicon_src_{s}.png"
        fig.savefig(tmp, dpi=dpi, transparent=True)
        plt.close(fig)
        im = Image.open(tmp).convert("RGBA").resize((s, s), Image.LANCZOS)
        out = HERE / f"favicon_{s}.png"
        im.save(out)
        tmp.unlink()
        made.append(out)
    return made


# ------------------------------------------------------------- the whole sheet
def write_final():
    """One sheet showing the identity: mark, lockup, small variant at the sizes
    it exists for, and the reversed lockup on the ground it is for."""
    dpi = 200
    W, H = 13.5, 11.2
    fig, ax, ppu = new_fig(W, H, W, dpi)
    ax.add_patch(Rectangle((0, 0), W, H, facecolor=WHITE, edgecolor="none",
                           zorder=0))
    soft = "#666D74"

    def head(y, s, sub, color=INK):
        ax.text(0.55, y, s, ha="left", va="center", fontsize=13,
                fontweight="normal", color=color, zorder=6)
        ax.text(0.55, y - 0.30, sub, ha="left", va="center", fontsize=10,
                color=soft, zorder=6)

    def place(name, xin, ycen, win, label=None, ylab=None):
        """Show a DELIVERED file, not a redrawing of it. A contact sheet that
        re-renders the lockup can differ from the lockup that ships, which is
        exactly what happened when the wordmark face was chosen: the sheet
        showed a lighter word than the file did, and the sheet is what a person
        judges from."""
        im = Image.open(HERE / name)
        h_in = win * im.size[1] / im.size[0]
        a = fig.add_axes([xin / W, (ycen - h_in / 2) / H, win / W, h_in / H])
        a.imshow(im, interpolation="antialiased")
        a.set_xticks([]), a.set_yticks([])
        a.patch.set_alpha(0)
        for sp in a.spines.values():
            sp.set_visible(False)
        if label:
            ax.text(xin + win / 2, ylab, label, ha="center", va="center",
                    fontsize=9.5, color=soft, zorder=6)

    def raster(im, xin, ycen, win, label=None, ylab=None):
        a = fig.add_axes([xin / W, (ycen - win / 2) / H, win / W, win / H])
        a.imshow(im, interpolation="nearest")
        a.set_xticks([]), a.set_yticks([])
        for sp in a.spines.values():
            sp.set_visible(False)
        if label:
            ax.text(xin + win / 2, ylab, label, ha="center", va="center",
                    fontsize=9.5, color=soft, zorder=6)

    ax.text(0.55, H - 0.45, "langaccess", ha="left", va="center", fontsize=17,
            fontweight="normal", color=INK)
    ax.text(2.35, H - 0.45, "the identity", ha="left", va="center",
            fontsize=11, color=soft)

    # the mark and the lockup
    head(H - 1.30, "The mark",
         "a page whose turned corner uncovers another language")
    place("logo_mark.png", 2.05 - 1.05, H - 3.35, 2.10)
    place("logo_lockup.png", 4.55, H - 3.35, 5.30)

    # the small variant, at the sizes it exists for
    head(H - 5.15, "The small variant",
         "a separate drawing for icon sizes, not a reduction of the mark")
    ylab = H - 7.60
    place("logo_mark_small.png", 1.55 - 0.775, H - 6.60, 1.55)
    ax.text(1.55, ylab, "vector", ha="center", va="center", fontsize=9.5,
            color=soft)
    for s, xin, xblow in ((64, 3.10, 4.05), (32, 6.55, 7.30)):
        im = Image.open(HERE / f"favicon_{s}.png")
        raster(im, xin, H - 6.60, s / dpi, f"{s} px", ylab)
        raster(im.resize((320, 320), Image.NEAREST), xblow, H - 6.60, 1.60,
               f"{s} px, magnified", ylab)

    # the reversed pair, on the ground it is for
    ax.add_patch(Rectangle((0.55, 0.40), W - 1.10, 1.95, facecolor=DARK_CANVAS,
                           edgecolor="none", zorder=2))
    head(2.85, "Reversed, for dark backgrounds",
         "ink swapped for a near-white, the accent lightened to hold contrast")
    place("logo_lockup_dark.png", 1.15, 1.38, 4.60)
    place("logo_mark_dark.png", W - 1.80 - 0.575, 1.38, 1.15)

    out = HERE / "logo_final.png"
    fig.savefig(out, dpi=dpi, facecolor=WHITE)
    plt.close(fig)
    return out


# ------------------------------------------------------------------- verifying
def _lin(c):
    c = c / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def luminance(hexcolor):
    r, g, b = (int(hexcolor[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def contrast(a, b):
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def rgb(hexcolor):
    return np.array([int(hexcolor[i:i + 2], 16) for i in (1, 3, 5)], float)


def _blend_dist(p, a, b):
    """Distance from a colour to the straight line between two palette colours,
    which is every colour antialiasing is allowed to invent."""
    ab = b - a
    den = float(np.dot(ab, ab))
    t = 0.0 if den == 0 else float(np.clip(np.dot(p - a, ab) / den, 0, 1))
    return float(np.linalg.norm(p - (a + t * ab)))


def census(path, allowed, share=0.005, tol=26.0):
    """Every colour holding more than `share` of the opaque pixels has to be a
    palette colour or a blend of two of them. Catches a stray fill or a colour
    that drifted; tolerates the edge pixels a downscale must produce, which at
    32 px are a large share of the image and are all blends by construction."""
    a = np.array(Image.open(path).convert("RGBA"))
    op = a[..., 3] > 250
    if not op.any():
        raise AssertionError(f"{path.name}: no opaque pixels at all")
    cols, counts = np.unique(a[op][:, :3].reshape(-1, 3), axis=0,
                             return_counts=True)
    keep = counts >= share * counts.sum()
    pal = [rgb(h) for h in allowed]
    bad = []
    for c in cols[keep]:
        p = c.astype(float)
        d = min(_blend_dist(p, x, y) for x in pal for y in pal)
        if d > tol:
            bad.append(tuple(int(v) for v in c))
    if bad:
        raise AssertionError(f"{path.name}: unexpected colours {bad}, "
                             f"allowed {allowed}")
    return int(keep.sum())


def svg_check(path, allowed):
    """The wordmark must be outlines, the palette must be the palette, and the
    reveal must still be a hole in vector, not only in the raster."""
    s = path.read_text(encoding="utf-8", errors="ignore")
    for tag in ("<text", "<tspan", "font-family"):
        if tag in s:
            raise AssertionError(f"{path.name}: contains {tag}, the wordmark "
                                 "is not outlined")
    cols = {c.lower() for c in re.findall(r"#[0-9a-fA-F]{6}", s)}
    stray = cols - {h.lower() for h in allowed}
    if stray:
        raise AssertionError(f"{path.name}: colours outside the palette "
                             f"{sorted(stray)}")
    subpaths = [d.count("M ") for d in re.findall(r'<path d="([^"]+)"', s)]
    if max(subpaths, default=0) < 2:
        raise AssertionError(f"{path.name}: no compound path, the reveal was "
                             "filled in instead of knocked out")
    return len(subpaths), sorted(cols)


def verify(made):
    print("\nverify")
    for a, b, floor, what in (
            (INK, WHITE, 4.5, "ink on white"),
            (ACCENT, WHITE, 4.5, "accent on white"),
            (INK_DARK, DARK_CANVAS, 4.5, "reversed ink on dark"),
            (ACCENT_DARK, DARK_CANVAS, 3.0, "reversed accent on dark"),
            (ACCENT_DARK, INK_DARK, 2.0, "reversed accent vs reversed ink")):
        r = contrast(a, b)
        assert r >= floor, f"{what} is {r:.2f}:1, under {floor}:1"
        print(f"  contrast {what:<32} {r:5.2f}:1  (floor {floor})")
    print(f"  contrast {'accent unchanged on dark':<32} "
          f"{contrast(ACCENT, DARK_CANVAS):5.2f}:1  (why it is lightened)")

    light, dark = [INK, ACCENT, WHITE], [INK_DARK, ACCENT_DARK, DARK_CANVAS]
    checks = {"logo_mark.png": light, "logo_mark_small.png": light,
              "logo_lockup.png": light, "logo_social.png": light,
              "favicon_32.png": light, "favicon_64.png": light,
              "logo_mark_dark.png": dark, "logo_lockup_dark.png": dark,
              "logo_final.png": light + dark}
    for name, allowed in checks.items():
        n = census(HERE / name, allowed)
        print(f"  colours   {name:<32} {n} major, all in palette")

    for name, allowed in (("logo_mark.svg", [INK, ACCENT]),
                          ("logo_mark_small.svg", [INK, ACCENT]),
                          ("logo_lockup.svg", [INK, ACCENT]),
                          ("logo_mark_dark.svg", [INK_DARK, ACCENT_DARK]),
                          ("logo_lockup_dark.svg", [INK_DARK, ACCENT_DARK])):
        n, cols = svg_check(HERE / name, allowed)
        print(f"  vector    {name:<32} {n} paths, outlined, {cols}, hole kept")

    sizes = {"logo_mark.png": (1024, 1024), "logo_mark_dark.png": (1024, 1024),
             "logo_mark_small.png": (1024, 1024),
             "logo_social.png": (1280, 640), "favicon_32.png": (32, 32),
             "favicon_64.png": (64, 64)}
    for name, want in sizes.items():
        got = Image.open(HERE / name).size
        assert got == want, f"{name} is {got}, wanted {want}"
        print(f"  size      {name:<32} {got[0]}x{got[1]}")

    social = np.array(Image.open(HERE / "logo_social.png").convert("RGBA"))
    assert (social[..., 3] == 255).all(), "logo_social.png is not opaque"
    print(f"  alpha     {'logo_social.png':<32} fully opaque")
    for name in ("logo_mark.png", "logo_lockup.png", "logo_mark_dark.png",
                 "logo_lockup_dark.png", "favicon_32.png"):
        a = np.array(Image.open(HERE / name).convert("RGBA"))
        assert (a[..., 3] == 0).any(), f"{name} has no transparency"
        print(f"  alpha     {name:<32} transparent ground")

    # the reveal has to be a real hole, not a painted bar: sample the middle of
    # the line of writing under the fold in the 1024 px mark
    a = np.array(Image.open(HERE / "logo_mark.png").convert("RGBA"))
    k = (1.0 - 2 * 0.13) / 100.0
    px = int((0.5 + 26.0 * k) * 1024)
    py = int((1.0 - (0.5 + -38.0 * k)) * 1024)
    assert a[py, px, 3] == 0, ("the reveal is painted, not knocked out "
                               f"(alpha {a[py, px, 3]})")
    print(f"  knockout  {'logo_mark.png':<32} alpha 0 inside the reveal")


def main():
    argparse.ArgumentParser().parse_args()
    arial_or_die()

    mark, small = SHIPPED["mark"], SHIPPED["small"]
    made = []
    made += write_mark(mark, "logo_mark", LIGHT)
    made += write_mark(mark, "logo_mark_dark", DARK)
    made += write_mark(small, "logo_mark_small", LIGHT)
    made += write_lockup(mark, "logo_lockup", LIGHT)
    made += write_lockup(mark, "logo_lockup_dark", DARK)
    made += write_social(mark, "logo_social")
    made += write_favicons(small)
    made += [write_final()]

    for p in sorted(set(made), key=lambda q: q.name):
        if p.suffix == ".png":
            w, h = Image.open(p).size
            print(f"{p.name}: {w}x{h}")
        else:
            print(f"{p.name}: vector")
    verify(made)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
