"""pad-bot CLI. Nothing touches the phone without --live.

  shot NAME                      save the Mirroring window to shots/NAME.png
  crop PNG KIND NAME X Y W H     save a template crop (pixels) to templates/KIND/NAME.png
  board PNG                      read the board, solve the default goal, save PNG-route.png
  testdrag R1 C1 R2 C2 [--live]  drag one orb between board cells (needs a battle on screen)
  run [--live] [--runs N] [--path "Dungeon/Floor" | --uncleared] [--replay DIR]
"""
import argparse
import itertools
import sys
import time
import tomllib
from pathlib import Path

import cv2

from . import profile as prof
from . import vision
from .mac import Mouse, Stop, capture, find_window, to_point
from .run import Bot
from .solver import solve

ROOT = Path(__file__).resolve().parent.parent


def cfg():
    with open(ROOT / "config.toml", "rb") as f:
        return tomllib.load(f)


def draw_route(img, rect, path, out):
    pts = [tuple(int(v) for v in vision.cell_centre(img, rect, r, c)) for r, c in path]
    o = img.copy()
    for a, b in zip(pts, pts[1:]):
        cv2.line(o, a, b, (255, 255, 255), 8)
    cv2.circle(o, pts[0], 16, (0, 255, 0), -1)
    cv2.circle(o, pts[-1], 16, (0, 0, 255), -1)
    cv2.imwrite(str(out), o)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="padbot")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("shot"); s.add_argument("name")
    s = sub.add_parser("crop")
    for a in ("png", "kind", "name"):
        s.add_argument(a)
    for a in ("x", "y", "w", "h"):
        s.add_argument(a, type=int)
    s = sub.add_parser("board"); s.add_argument("png"); s.add_argument("--profile", default="profiles/lugner.toml")
    s = sub.add_parser("testdrag")
    for a in ("r1", "c1", "r2", "c2"):
        s.add_argument(a, type=int)
    s.add_argument("--live", action="store_true")
    s = sub.add_parser("run")
    s.add_argument("--live", action="store_true")
    s.add_argument("--runs", type=int, default=1, help="clears before stopping")
    s.add_argument("--path", help='names to tap through, e.g. "Aither Desert/Beyond the Desert"')
    s.add_argument("--uncleared", action="store_true", help="play floors without a Clear! badge, top to bottom")
    s.add_argument("--profile", default="profiles/lugner.toml")
    s.add_argument("--replay", help="folder of PNGs to loop through instead of the live window")
    a = ap.parse_args(argv)
    c = cfg()

    try:
        if a.cmd == "shot":
            img, bounds = capture()
            (ROOT / "shots").mkdir(exist_ok=True)
            p = ROOT / "shots" / f"{a.name}.png"
            cv2.imwrite(str(p), img)
            print(f"saved {p}  {img.shape[1]}x{img.shape[0]} px, window {bounds}")
        elif a.cmd == "crop":
            img = cv2.imread(a.png)
            d = ROOT / "templates" / a.kind
            d.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(str(d / f"{a.name}.png"), img[a.y:a.y + a.h, a.x:a.x + a.w])
            print(f"saved templates/{a.kind}/{a.name}.png")
        elif a.cmd == "board":
            img = cv2.imread(a.png)
            if not vision.load("orbs"):
                raise Stop("No orb templates in templates/orbs/ yet.")
            board, ok = vision.read_board(img, c["layout"]["board"], vision.load("orbs"), c["match"]["orb_max_dist"])
            print("\n".join(board), "\nconfident:", ok)
            p = prof.load(ROOT / a.profile)
            _, _, goal = prof.plan(p, [])
            path = solve(board, goal, max_steps=p.get("max_steps", 12))
            print("goal", goal, "route", path)
            if path:
                out = Path(a.png).with_name(Path(a.png).stem + "-route.png")
                draw_route(img, c["layout"]["board"], path, out)
                print("saved", out)
        elif a.cmd == "testdrag":
            img, bounds = capture()
            if not vision.load("orbs"):
                raise Stop("No orb templates in templates/orbs/ yet.")
            rect = c["layout"]["board"]
            board, ok = vision.read_board(img, rect, vision.load("orbs"), c["match"]["orb_max_dist"])
            if not ok:
                raise Stop("Board not read confidently: calibrate the board area and orbs first.")
            pts = [to_point(*vision.cell_centre(img, rect, r, cc), img.shape[1], bounds)
                   for r, cc in ((a.r1, a.c1), (a.r2, a.c2))]
            m = Mouse(a.live)
            m.focus()
            m.drag(pts)
        elif a.cmd == "run":
            grab = capture
            if a.replay:
                files = sorted(Path(a.replay).glob("*.png"))
                frames = itertools.cycle([cv2.imread(str(f)) for f in files])
                grab = lambda: (lambda im: (im, (0, 0, im.shape[1] / 2, im.shape[0] / 2)))(next(frames))
                if a.live:
                    sys.exit("--replay and --live can't be combined")
            if a.uncleared:
                c.setdefault("nav", {}).update(uncleared=True, path=[])
            if a.path:
                c.setdefault("nav", {})["path"] = [x.strip() for x in a.path.split("/")]
            bot = Bot(c, prof.load(ROOT / a.profile), Mouse(a.live), grab)
            bot.run(runs=a.runs,
                    max_iterations=(len(files) if a.replay else None))
    except Stop as e:
        print("STOPPED:", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
