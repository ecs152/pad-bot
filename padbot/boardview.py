"""Live board view: draws the bot's read of the 30 orbs and its planned drag.

render() is a pure function the app shell can embed. watch() follows the newest logs/run-*.jsonl
(one line per turn: board, route, goal) and shows the drawing beside the iPhone Mirroring window.
Read-only: never captures, clicks or drags."""
import json
from pathlib import Path

import cv2
import numpy as np

from .solver import COLS, ROWS

LOGS = Path(__file__).resolve().parent.parent / "logs"
# BGR fill per orb letter (solver.py legend); '.' = unread
COLOURS = {"R": (60, 60, 230), "B": (230, 140, 40), "G": (70, 190, 70), "L": (60, 220, 240),
           "D": (170, 60, 150), "H": (190, 120, 245), "J": (150, 150, 150), "P": (120, 50, 90),
           "M": (60, 20, 50), ".": (70, 70, 70)}


NAMES = {"R": "fire", "B": "water", "G": "wood", "L": "light", "D": "dark", "H": "heal"}


def goal_text(goal):
    """{"crosses": {"D": 1}, "min_combos": 3} -> 'dark cross x1, 3+ combos'."""
    n = lambda k: NAMES.get(k, k)
    parts = [f"{n(k)} cross x{v}" for k, v in goal.get("crosses", {}).items()]
    parts += [f"{v}+ {n(k)} linked" for k, v in goal.get("link", {}).items()]
    parts += [f"{goal['min_combos']}+ combos"] if goal.get("min_combos") else []
    parts += [f"avoid {', '.join(n(k) for k in goal.get('avoid', []))}"] if goal.get("avoid") else []
    return ", ".join(parts) or "any match"


def caption(ev):
    steps = max(len(ev.get("route") or []) - 1, 0)
    return [f"Turn {ev.get('turn', '?')}  -  {steps} step{'s' * (steps != 1)}",
            f"Goal: {goal_text(ev.get('goal') or {})}",
            f"Enemy icons: {', '.join(ev.get('mechanics') or []) or 'none'}"]


def render(board, route=None, lines=(), cell=64):
    """board: 5 strings of 6 orb letters. route: [(r, c), ...] drag path. Returns a BGR image."""
    pad, head = cell // 4, 24 * len(lines) + (cell // 4 if lines else 0)
    img = np.full((head + ROWS * cell + 2 * pad, COLS * cell + 2 * pad, 3), 32, np.uint8)
    for i, t in enumerate(lines):
        cv2.putText(img, t, (pad, pad + 16 + 24 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                    (235, 235, 235), 1, cv2.LINE_AA)
    centre = lambda r, c: (pad + c * cell + cell // 2, head + pad + r * cell + cell // 2)
    for r in range(ROWS):
        for c in range(COLS):
            k = board[r][c] if r < len(board) and c < len(board[r]) else "."
            x, y = centre(r, c)
            cv2.rectangle(img, (x - cell // 2, y - cell // 2), (x + cell // 2 - 1, y + cell // 2 - 1),
                          (48, 48, 48) if (r + c) % 2 else (40, 40, 40), -1)
            cv2.circle(img, (x, y), int(cell * 0.4), COLOURS.get(k, COLOURS["."]), -1, cv2.LINE_AA)
            label = "?" if k == "." else k
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
            cv2.putText(img, label, (x - tw // 2, y + th // 2), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2,
                        cv2.LINE_AA)
    if route:
        pts = [centre(r, c) for r, c in route]
        for a, b in zip(pts, pts[1:]):
            cv2.line(img, a, b, (20, 20, 20), 9, cv2.LINE_AA)  # dark outline keeps the path visible on light orbs
            cv2.line(img, a, b, (255, 255, 255), 5, cv2.LINE_AA)
        for i, p in enumerate(pts[1:-1], 1):  # step numbers where the finger turns or passes
            cv2.putText(img, str(i), (p[0] + 8, p[1] - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1,
                        cv2.LINE_AA)
        cv2.circle(img, pts[0], cell // 7, (60, 200, 60), -1, cv2.LINE_AA)
        cv2.circle(img, pts[0], cell // 7, (255, 255, 255), 2, cv2.LINE_AA)
        cv2.circle(img, pts[-1], cell // 7, (50, 50, 220), -1, cv2.LINE_AA)
        cv2.circle(img, pts[-1], cell // 7, (255, 255, 255), 2, cv2.LINE_AA)
    return img


def last_event(logs=LOGS):
    """Newest turn from the newest run log, or None."""
    files = sorted(logs.glob("run-*.jsonl"), key=lambda p: p.stat().st_mtime)
    for p in reversed(files):
        lines = [ln for ln in p.read_text().splitlines() if ln.strip()]
        if lines:
            return json.loads(lines[-1])
    return None


def beside_mirroring():
    """Global point just right of the iPhone Mirroring window, or None if it isn't open."""
    try:
        from .mac import find_window
        _, (x, y, w, _) = find_window(retry=False)  # no retry: retry would bring Mirroring to the front
        return int(x + w + 8), int(y)
    except Exception:
        return None


def watch(poll_s=0.3):
    name = "pad-bot board"
    cv2.namedWindow(name, cv2.WINDOW_AUTOSIZE)
    seen, placed = None, False
    while True:
        try:
            ev = last_event()
        except (OSError, ValueError):  # log line half-written: try again next poll
            ev = seen
        if ev != seen or seen is None:
            seen = ev
            img = (render(ev["board"], ev.get("route"), caption(ev)) if ev
                   else render(["." * COLS] * ROWS, None, ["Waiting for the bot's first turn..."]))
            cv2.imshow(name, img)
            if not placed:
                pos = beside_mirroring()
                if pos:
                    cv2.moveWindow(name, *pos)
                placed = True
        if cv2.waitKey(int(poll_s * 1000)) in (27, ord("q")) or \
                cv2.getWindowProperty(name, cv2.WND_PROP_VISIBLE) < 1:
            break
    cv2.destroyAllWindows()
