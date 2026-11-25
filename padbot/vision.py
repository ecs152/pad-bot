"""Template matching for screens, buttons, status icons, stop dialogs, and orbs.

templates/
  screens/<screen>.png   a crop that identifies the screen (e.g. results banner)
  buttons/<button>.png   tappable buttons; only names listed in config.toml are ever tapped
  icons/<mechanic>.png   enemy/team status icons (combo_absorb, void, awoken_bind, ...)
  stop/<name>.png        Continue / Magic Stone dialogs: seeing any of these halts the bot at once
  orbs/<letter>[_x].png  crops of each orb type from your own board (R B G L D H J P M); the first
                         letter is the type, so D_plus.png is an enhanced dark orb
All crops come from captures of the same window size.
"""
from pathlib import Path

import cv2
import numpy as np

from .solver import COLS, ROWS

ROOT = Path(__file__).resolve().parent.parent / "templates"
ORB_SIZE = 24


def load(kind):
    d = ROOT / kind
    return {p.stem: cv2.imread(str(p)) for p in sorted(d.glob("*.png"))} if d.exists() else {}


def find(img, tmpl, thr):
    """Best match of tmpl in img. Returns (x, y, w, h) box in image pixels, or None."""
    if tmpl is None or tmpl.shape[0] > img.shape[0] or tmpl.shape[1] > img.shape[1]:
        return None
    res = cv2.matchTemplate(img, tmpl, cv2.TM_CCOEFF_NORMED)
    _, score, _, (x, y) = cv2.minMaxLoc(res)
    return (x, y, tmpl.shape[1], tmpl.shape[0]) if score >= thr else None


def first_match(img, templates, names, thr):
    for n in names:
        box = find(img, templates.get(n), thr)
        if box:
            return n, box
    return None


def board_cells(img, rect):
    """rect: board as fractions (x0, y0, x1, y1) of the image. Yields (r, c, crop, centre_px)."""
    h, w = img.shape[:2]
    x0, y0, x1, y1 = rect[0] * w, rect[1] * h, rect[2] * w, rect[3] * h
    cw, ch = (x1 - x0) / COLS, (y1 - y0) / ROWS
    for r in range(ROWS):
        for c in range(COLS):
            cx, cy = x0 + (c + 0.5) * cw, y0 + (r + 0.5) * ch
            # inner 70% of the cell avoids neighbours and the grid
            m = 0.35
            crop = img[int(cy - ch * m):int(cy + ch * m), int(cx - cw * m):int(cx + cw * m)]
            yield r, c, crop, (cx, cy)


def _norm(crop):
    return cv2.resize(crop, (ORB_SIZE, ORB_SIZE), interpolation=cv2.INTER_AREA).astype(np.float32)


def read_board(img, rect, orbs, max_dist, ready_median=15.0):
    """Returns (board as 5 strings, ok).
    A cell far from every reference orb (cloud, blind, effect) reads as '.', unknown.
    ok means the board as a whole looks live: median distance low. A dimmed board during
    animations is far from everything (median ~55), so it reads as not ok."""
    if not orbs:
        raise RuntimeError("No orb templates in templates/orbs/. Run `padbot crop` on a board screenshot first.")
    refs = {k: _norm(v) for k, v in orbs.items()}  # several crops per orb allowed: D.png, D_plus.png -> 'D'
    rows, dists = [[''] * COLS for _ in range(ROWS)], []
    for r, c, crop, _ in board_cells(img, rect):
        n = _norm(crop)
        k, d = min(((k, float(np.mean(np.abs(n - v)))) for k, v in refs.items()), key=lambda x: x[1])
        rows[r][c] = k[0] if d <= max_dist else '.'
        dists.append(d)
    return [''.join(r) for r in rows], float(np.median(dists)) <= ready_median


def cell_centre(img, rect, r, c):
    h, w = img.shape[:2]
    x0, y0, x1, y1 = rect[0] * w, rect[1] * h, rect[2] * w, rect[3] * h
    return x0 + (c + 0.5) * (x1 - x0) / COLS, y0 + (r + 0.5) * (y1 - y0) / ROWS
