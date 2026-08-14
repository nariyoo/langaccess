"""Build system.png, the README's pictogram pipeline figure.

    python build_system.py

A left-to-right pipeline of simple line-drawn vector pictograms, in the manner
of a hand-made engineering slide: a website address goes in, the same page is
read two ways, the difference between the two readings is taken, the codebook
rules judge it, and three outputs come out. All pictograms are drawn here as
matplotlib vector shapes; there are no icon fonts, no images and no emoji.
Labels are short phrases; the caption under the difference step is the longest
text in the figure.

This form was decided on 2026-08-07, replacing a tex/twemoji build whose boxed
prose read as machine-made. Writes figures/system.png at 300 dpi.
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import (Rectangle, Circle, Polygon, Arc,
                                FancyArrowPatch)
from matplotlib.lines import Line2D
from matplotlib import font_manager as fm

HERE = Path(__file__).resolve().parent
OUT = HERE / "system.png"
DPI = 300

INK = "#1B1F23"        # pictogram strokes, labels
SOFT = "#666D74"       # sublabels, caption
ACCENT = "#2F3E75"     # arrows only
WHITE = "#FFFFFF"

PLW = 3.0              # pictogram stroke width (pt)
LABEL_PT = 12
SUB_PT = 9.5

W, H = 15.6, 5.6       # inches; 300 dpi -> 4680 x 1680 px; widened for the class list sublabel


def arial_or_die():
    names = {f.name for f in fm.fontManager.ttflist}
    if "Arial" not in names:
        raise FileNotFoundError("Arial not registered with matplotlib")
    plt.rcParams["font.family"] = "Arial"


# ------------------------------------------------------------------ pictograms
def stroke(ax, xs, ys, lw=PLW, color=INK):
    ax.add_line(Line2D(xs, ys, lw=lw, color=color, solid_capstyle="round",
                       solid_joinstyle="round", zorder=5))


def p_address(ax, cx, cy):
    """Address-bar strip: a wide field with a small globe and a text line."""
    w, h = 2.0, 0.52
    ax.add_patch(Rectangle((cx - w / 2, cy - h / 2), w, h, fill=False,
                           edgecolor=INK, lw=PLW, zorder=5))
    g = (cx - w / 2 + 0.30, cy)
    r = 0.13
    ax.add_patch(Circle(g, r, fill=False, edgecolor=INK, lw=2.2, zorder=5))
    ax.add_patch(Arc(g, r * 1.1, r * 2, fill=False, edgecolor=INK, lw=1.6,
                     zorder=5))
    stroke(ax, [g[0] - r, g[0] + r], [g[1], g[1]], lw=1.6)
    stroke(ax, [cx - w / 2 + 0.56, cx + w / 2 - 0.22], [cy, cy], lw=2.6)


def p_browser(ax, cx, cy):
    """Browser window: title bar with three dots, a globe on a page inside."""
    w, h, bar = 1.70, 1.30, 0.30
    x0, y0 = cx - w / 2, cy - h / 2
    ax.add_patch(Rectangle((x0, y0), w, h, fill=False, edgecolor=INK,
                           lw=PLW, zorder=5))
    stroke(ax, [x0, x0 + w], [y0 + h - bar, y0 + h - bar], lw=2.4)
    for i in range(3):
        ax.add_patch(Circle((x0 + 0.17 + i * 0.20, y0 + h - bar / 2), 0.045,
                            facecolor=INK, edgecolor="none", zorder=5))
    g = (cx - 0.32, cy - bar / 2 + 0.02)
    r = 0.30
    ax.add_patch(Circle(g, r, fill=False, edgecolor=INK, lw=2.4, zorder=5))
    ax.add_patch(Arc(g, r * 0.95, r * 2, fill=False, edgecolor=INK, lw=1.7,
                     zorder=5))
    stroke(ax, [g[0] - r, g[0] + r], [g[1], g[1]], lw=1.7)
    for dy in (0.16, 0.0, -0.16):
        stroke(ax, [cx + 0.14, cx + 0.62], [g[1] + dy, g[1] + dy], lw=1.7)


def p_sheet(ax, cx, cy, w=1.00, h=1.26, fold=0.26, lines=4, lw=PLW):
    """Document sheet with a folded corner and ruled lines. Returns nothing."""
    x0, y0 = cx - w / 2, cy - h / 2
    xs = [x0, x0, x0 + w - fold, x0 + w, x0 + w, x0]
    ys = [y0, y0 + h, y0 + h, y0 + h - fold, y0, y0]
    ax.add_patch(Polygon(list(zip(xs, ys)), closed=True, facecolor=WHITE,
                         edgecolor=INK, lw=lw, joinstyle="round", zorder=5))
    stroke(ax, [x0 + w - fold, x0 + w - fold, x0 + w],
           [y0 + h, y0 + h - fold, y0 + h - fold], lw=lw * 0.72)
    top = y0 + h - fold - 0.14
    step = (top - y0 - 0.16) / max(lines - 1, 1)
    for i in range(lines):
        y = top - i * step
        stroke(ax, [x0 + 0.14, x0 + w - 0.14], [y, y], lw=1.7)


def p_diff(ax, cx, cy):
    """Two overlapping sheets, the front one carrying a highlighted band."""
    p_sheet(ax, cx + 0.13, cy + 0.13, w=0.96, h=1.22, lines=0, lw=2.2)
    p_sheet(ax, cx - 0.09, cy - 0.09, w=0.96, h=1.22, lines=0, lw=PLW)
    x0, y0 = cx - 0.09 - 0.48, cy - 0.09 - 0.61
    for y in (0.96, 0.78, 0.30, 0.12):
        stroke(ax, [x0 + 0.13, x0 + 0.83], [y0 + y, y0 + y], lw=1.7)
    ax.add_patch(Rectangle((x0 + 0.10, y0 + 0.44), 0.76, 0.22,
                           facecolor="#C9CED4", edgecolor=INK, lw=1.3,
                           zorder=6))


def p_checklist(ax, cx, cy):
    """A checklist sheet: three checked boxes with lines beside them."""
    w, h = 1.06, 1.30
    x0, y0 = cx - w / 2, cy - h / 2
    ax.add_patch(Rectangle((x0, y0), w, h, fill=False, edgecolor=INK,
                           lw=PLW, zorder=5))
    for i in range(3):
        by = y0 + h - 0.34 - i * 0.38
        ax.add_patch(Rectangle((x0 + 0.14, by), 0.20, 0.20, fill=False,
                               edgecolor=INK, lw=1.9, zorder=5))
        stroke(ax, [x0 + 0.18, x0 + 0.235, x0 + 0.32],
               [by + 0.09, by + 0.035, by + 0.17], lw=1.9)
        stroke(ax, [x0 + 0.44, x0 + w - 0.14], [by + 0.10, by + 0.10], lw=1.7)


def p_tag(ax, cx, cy, s=0.34):
    """A price-tag shape with a hole."""
    pts = [(-1.05, 0.55), (0.25, 0.55), (1.05, 0.0), (0.25, -0.55),
           (-1.05, -0.55)]
    ax.add_patch(Polygon([(cx + px * s, cy + py * s) for px, py in pts],
                         closed=True, fill=False, edgecolor=INK, lw=2.6,
                         joinstyle="round", zorder=5))
    ax.add_patch(Circle((cx - 0.62 * s, cy), 0.135 * s * 1.6, fill=False,
                        edgecolor=INK, lw=2.0, zorder=5))


def p_quote(ax, cx, cy, s=0.52):
    """Two solid quotation marks."""
    for dx in (-0.42, 0.42):
        x = cx + dx * s * 1.1
        y = cy + 0.18 * s
        ax.add_patch(Circle((x, y + 0.02 * s), 0.30 * s, facecolor=INK,
                            edgecolor="none", zorder=5))
        ax.add_patch(Polygon([(x - 0.30 * s, y + 0.06 * s),
                              (x + 0.10 * s, y + 0.06 * s),
                              (x - 0.16 * s, y - 0.62 * s)],
                             closed=True, facecolor=INK, edgecolor="none",
                             zorder=5))


def p_gauge(ax, cx, cy, r=0.40):
    """A half-dial with ticks and a needle."""
    ax.add_patch(Arc((cx, cy - 0.10), 2 * r, 2 * r, theta1=0, theta2=180,
                     edgecolor=INK, lw=2.6, zorder=5))
    stroke(ax, [cx - r, cx + r], [cy - 0.10, cy - 0.10], lw=2.6)
    for a in (30, 90, 150):
        t = np.radians(a)
        stroke(ax, [cx + np.cos(t) * r * 0.82, cx + np.cos(t) * r],
               [cy - 0.10 + np.sin(t) * r * 0.82, cy - 0.10 + np.sin(t) * r],
               lw=1.8)
    t = np.radians(55)
    stroke(ax, [cx, cx + np.cos(t) * r * 0.62],
           [cy - 0.10, cy - 0.10 + np.sin(t) * r * 0.62], lw=2.4)
    ax.add_patch(Circle((cx, cy - 0.10), 0.045, facecolor=INK,
                        edgecolor="none", zorder=5))


# --------------------------------------------------------------------- arrows
def arrow(ax, p0, p1, lw=6.0, scale=30):
    ax.add_patch(FancyArrowPatch(p0, p1, arrowstyle="-|>",
                                 mutation_scale=scale, lw=lw, color=ACCENT,
                                 shrinkA=0, shrinkB=0, capstyle="butt",
                                 zorder=4))


def label(ax, cx, y, main, sub=None, main_pt=LABEL_PT):
    ax.text(cx, y, main, ha="center", va="top", fontsize=main_pt,
            fontweight="bold", color=INK, zorder=6)
    if sub:
        ax.text(cx, y - 0.265, sub, ha="center", va="top", fontsize=SUB_PT,
                color=SOFT, zorder=6)


def main():
    arial_or_die()
    fig = plt.figure(figsize=(W, H), dpi=DPI)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, W)
    ax.set_ylim(0, H)
    ax.set_aspect("equal")
    ax.axis("off")

    mid = 2.95

    # the package frame, input node outside it
    fx0, fx1 = 2.45, 15.32
    ax.add_patch(Rectangle((fx0, 0.30), fx1 - fx0, H - 0.75, fill=False,
                           edgecolor=INK, lw=1.4, zorder=2))
    # The package's own lockup sits on the frame line, in place of the word set in Arial. The
    # wordmark is Franklin Gothic Demi and the mark is the turned-corner page, so setting the name
    # in the figure's body font printed a second, wrong version of it beside the real one.
    logo = plt.imread(str(HERE / "logo_lockup.png"))
    lg_h = 0.34                                        # inches of figure height
    lg_w = lg_h * logo.shape[1] / logo.shape[0]
    lg_cx = (fx0 + fx1) / 2
    ax.add_patch(Rectangle((lg_cx - lg_w / 2 - 0.16, H - 0.45 - lg_h / 2 - 0.06),
                           lg_w + 0.32, lg_h + 0.12, facecolor=WHITE, edgecolor="none",
                           zorder=3))
    ax.imshow(logo, extent=(lg_cx - lg_w / 2, lg_cx + lg_w / 2,
                            H - 0.45 - lg_h / 2, H - 0.45 + lg_h / 2),
              zorder=4, interpolation="antialiased")
    ax.set_xlim(0, W)                                  # imshow resets the limits; put them back
    ax.set_ylim(0, H)
    ax.set_aspect("equal")

    # input
    p_address(ax, 1.20, mid)
    label(ax, 1.20, mid - 0.48, "Website address", "robots.txt compliance")

    # two readings of the same page
    bx, by = 4.25, 4.10
    dx, dy = 4.25, 1.85
    p_browser(ax, bx, by)
    label(ax, bx, by - 0.87, "Rendered page", "headless Chromium")
    p_sheet(ax, dx, dy + 0.12)
    label(ax, dx, dy - 0.68, "Server document", "plain fetch")

    arrow(ax, (2.26, mid + 0.12), (3.28, by - 0.10))
    arrow(ax, (2.26, mid - 0.12), (3.28, dy + 0.10))

    # the difference
    cx, cy = 6.85, 3.30
    p_diff(ax, cx, cy)
    label(ax, cx, cy - 0.90, "Difference")
    ax.text(cx, cy - 1.20, "widget text absent from\n"
            "the server document", ha="center", va="top", fontsize=SUB_PT,
            color=SOFT, linespacing=1.3, zorder=6)

    arrow(ax, (5.16, by - 0.05), (6.10, cy + 0.28))
    arrow(ax, (4.88, dy + 0.10), (6.10, cy - 0.28))

    # the judgement
    rx, ry = 9.45, 3.30
    p_checklist(ax, rx, ry)
    label(ax, rx, ry - 0.87, "Codebook rules",
          "authorship and sufficiency\nper language")

    arrow(ax, (7.62, cy), (8.82, ry))

    # the outputs
    ox, olx = 11.30, 11.92
    rows = [(4.30, p_tag, "Classification",
             "true_multilingual / machine_translate /\n"
             "machine_translate_error / english_only / unreachable"),
            (2.95, p_quote, "Evidence",
             "URL and quoted text\n(e.g., /es/servicios, “Ayuda legal gratuita”)"),
            (1.60, p_gauge, "Read quality",
             "pages read and stop reason\n"
             "(e.g., 15 pages, deep enough for an absence claim)")]
    for oy, fn, main_, sub_ in rows:
        fn(ax, ox, oy)
        ax.text(olx, oy + (0.10 if sub_ else 0.0), main_, ha="left",
                va="center" if not sub_ else "bottom", fontsize=LABEL_PT,
                fontweight="bold", color=INK, zorder=6)
        if sub_:
            ax.text(olx, oy + 0.02, sub_, ha="left", va="top",
                    fontsize=SUB_PT, color=SOFT, zorder=6)

    # one arrow per output, so the judgement visibly produces all three
    for oy in (4.30, 2.95, 1.60):
        arrow(ax, (10.02, ry), (10.82, oy), lw=4.5, scale=24)

    fig.savefig(OUT, dpi=DPI, facecolor="white")
    from PIL import Image
    w, h = Image.open(OUT).size
    print(f"{OUT.name}: {w}x{h}px at {DPI} dpi")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
