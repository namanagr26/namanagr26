#!/usr/bin/env python3
"""
Generates portrait.svg — a self-typing ASCII portrait rendered entirely as
inline SVG (SMIL animation, embedded font, no scripts, no external assets).

Pipeline (see SETUP.md for photo requirements):
  1. rembg cut-out              -- forces background to white so it maps to
                                    the blank end of the ramp
  2. bilateral filter           -- smooths skin, keeps edges
  3. CLAHE, clip ~3.0           -- local contrast per tile
  4. darkening curve (v/255)^1.7 -- keeps glasses/brows/lips from washing out
  5. map to ramp                -- leading space clears the background

Usage:
    python3 generate_portrait.py <path-to-photo.jpg>

Writes portrait.svg into the repo root.
"""
import base64
import os
import sys
import textwrap

import cv2
import numpy as np
from PIL import Image
from rembg import remove, new_session

_REMBG_SESSION = new_session("u2net")  # ~176 MB; much lighter than the default model

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = os.path.join(HERE, "fonts")

# ---------------------------------------------------------------------------
# Tunables (see the guide for why these specific values)
# ---------------------------------------------------------------------------
RAMP = " .`:-=+*cs#%@"      # 13 levels, low -> high density
COLS = 90                   # below ~88 the face muddies; much above, it dominates
CHAR_W = 7.74                # advance width in px at FONT_SIZE, JetBrains Mono
FONT_SIZE = 12.9
ROW_SCALE = 0.48             # rows = cols * (h/w) * 0.48  (monospace cells ~2:1 tall:wide)
DARKEN_GAMMA = 1.7
CLAHE_CLIP = 3.0
BG = "#0d1117"
FG = "#58a6ff"


def load_font_b64(name):
    with open(os.path.join(FONT_DIR, name), "rb") as fh:
        return base64.b64encode(fh.read()).decode()


def cutout_to_white_bg(image_path):
    """rembg cut-out; everything outside the subject forced to white so it
    maps to the blank end of the ramp instead of drowning the portrait in @."""
    with open(image_path, "rb") as f:
        input_bytes = f.read()
    result = remove(input_bytes, session=_REMBG_SESSION)  # RGBA
    img = Image.open(__import__("io").BytesIO(result)).convert("RGBA")
    bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
    composited = Image.alpha_composite(bg, img).convert("RGB")
    return np.array(composited)[:, :, ::-1]  # RGB -> BGR for opencv


def process_image(bgr):
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)

    # bilateral filter: smooth skin, keep edges
    smoothed = cv2.bilateralFilter(gray, d=9, sigmaColor=75, sigmaSpace=75)

    # CLAHE: local contrast per tile, not a global autocontrast
    clahe = cv2.createCLAHE(clipLimit=CLAHE_CLIP, tileGridSize=(8, 8))
    contrasted = clahe.apply(smoothed)

    # darkening curve -- keeps thin dark features (glasses, brows, lips) from
    # washing out to a uniform mid-tone
    normalized = contrasted.astype(np.float64) / 255.0
    darkened = np.power(normalized, DARKEN_GAMMA) * 255.0
    return darkened.astype(np.uint8)


def to_ascii_grid(processed, cols=COLS):
    h, w = processed.shape
    rows = max(1, round(cols * (h / w) * ROW_SCALE))
    resized = cv2.resize(processed, (cols, rows), interpolation=cv2.INTER_AREA)

    ramp_len = len(RAMP)
    grid = []
    for r in range(rows):
        line = []
        for c in range(cols):
            v = resized[r, c]
            # bright (white background, highlights) -> blank end of ramp;
            # dark (shadow, features) -> dense end. Inverting v does this.
            idx = min(ramp_len - 1, int(((255.0 - v) / 255.0) * (ramp_len - 1)))
            line.append(RAMP[idx])
        grid.append("".join(line))
    return grid


def esc(ch):
    return {"&": "&amp;", "<": "&lt;", ">": "&gt;"}.get(ch, ch)


def build_svg(grid):
    cols = len(grid[0])
    rows = len(grid)
    width = cols * CHAR_W
    height = rows * (CHAR_W * 2 * ROW_SCALE / 0.48)  # keep aspect from the grid math
    row_h = height / rows

    reg_b64 = load_font_b64("text-regular.woff2")

    style = f"""
      @font-face {{
        font-family: 'JBM';
        src: url(data:font/woff2;base64,{reg_b64}) format('woff2');
        font-weight: 400;
      }}
      text {{ font-family: 'JBM', monospace; fill: {FG}; white-space: pre; }}
    """

    parts = [textwrap.dedent(f"""\
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:.1f} {height:.1f}"
             width="{width:.1f}" height="{height:.1f}" role="img" aria-label="ASCII portrait">
          <title>ASCII portrait</title>
          <style>{style}</style>
          <rect width="{width:.1f}" height="{height:.1f}" fill="{BG}"/>
    """)]

    # each row sits in a clipPath whose rect animates width from 0 to full,
    # staggered top to bottom, fill="freeze" so it prints once and stops
    for i, line in enumerate(grid):
        y = i * row_h
        clip_id = f"clip{i}"
        escaped = "".join(esc(c) for c in line)
        parts.append(
            f'<clipPath id="{clip_id}">'
            f'<rect x="0" y="{y:.2f}" width="0" height="{row_h:.2f}">'
            f'<animate attributeName="width" from="0" to="{width:.1f}" '
            f'dur="0.12s" begin="{i*0.09:.2f}s" fill="freeze"/>'
            f'</rect></clipPath>'
        )
        parts.append(
            f'<g clip-path="url(#{clip_id})">'
            f'<text x="0" y="{y + row_h*0.8:.2f}" font-size="{FONT_SIZE}" '
            f'xml:space="preserve">{escaped}</text></g>'
        )

    parts.append("</svg>\n")
    return "".join(parts)


def main():
    if len(sys.argv) != 2:
        print("usage: generate_portrait.py <photo.jpg>", file=sys.stderr)
        sys.exit(1)

    photo_path = sys.argv[1]
    bgr = cutout_to_white_bg(photo_path)
    processed = process_image(bgr)
    grid = to_ascii_grid(processed)
    svg = build_svg(grid)

    out_path = os.path.join(HERE, "..", "portrait.svg")
    with open(out_path, "w") as f:
        f.write(svg)
    print(f"wrote {out_path} ({len(svg)} bytes, {len(grid)} rows x {len(grid[0])} cols)")


if __name__ == "__main__":
    main()
