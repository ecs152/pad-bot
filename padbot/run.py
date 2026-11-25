"""Main loop: navigator (outside battle), team clearer and puzzle matcher (in battle).

Every tap is decided on a fresh capture: navigation re-reads the screen right before tapping, battle
re-reads the board right before dragging. Stop dialogs (templates/stop or stop words) halt at once."""
import json
import re
import time
from pathlib import Path

import cv2

from . import nav
from .events import emit
from . import profile as prof
from . import vision
from .mac import Stop, capture, notify, to_point
from .ocr import read_text
from .solver import solve

LOGS = Path(__file__).resolve().parent.parent / "logs"


class Bot:
    def __init__(self, cfg, profile, mouse, grab=capture, ocr=read_text):
        self.cfg, self.profile, self.mouse, self.grab, self.ocr = cfg, profile, mouse, grab, ocr
        self.t = {k: vision.load(k) for k in ("screens", "buttons", "icons", "stop", "orbs")}
        n = cfg.get("nav", {})
        self.helper = n.get("helper", "You")
        self.skip = tuple(n.get("skip", []))
        self.extra_stop = tuple(w.lower() for w in cfg.get("safety", {}).get("stop_words", []))
        self.set_target(n.get("path", []), n.get("uncleared", False))
        self.turn, self.ready_at = 0, {}
        self.stamina, self.coins, self.drops, self.floor = None, None, None, None
        self.team_swipes = 0
        self.run_t0 = time.time()
        self.done_before, self.total_runs = 0, None  # queue progress, for the `cleared` event
        LOGS.mkdir(exist_ok=True)
        self.log_path = LOGS / time.strftime("run-%Y%m%d-%H%M%S.jsonl")

    def set_target(self, path, uncleared=False):
        """What to play next: names to tap through, or uncleared floors. Refuses labels with stop words."""
        path = list(path)
        bad = [x for x in path + [self.helper] if nav.stop_word([(x + "?", 1, (0, 0, 0, 0))], self.extra_stop)]
        if bad:
            raise Stop(f"Refusing to tap labels containing stop words: {bad}")
        self.path, self.new_only = path, bool(uncleared)

    @property
    def target(self):
        return "/".join(self.path) if self.path else f"uncleared: {self.floor or '?'}"

    def record(self, result, reason=None):
        """One run in logs/history.jsonl (the app's History tab) and a `run` event."""
        rec = {"t": round(time.time(), 3), "target": self.target, "result": result,
               "seconds": round(time.time() - self.run_t0, 1),
               "stamina": list(self.stamina) if self.stamina else None, "coins": self.coins, "drops": self.drops}
        if reason:
            rec["reason"] = reason
        LOGS.mkdir(exist_ok=True)
        with open(LOGS / "history.jsonl", "a") as f:
            f.write(json.dumps(rec) + "\n")
        emit("run", **{k: v for k, v in rec.items() if k != "t"})
        self.coins, self.drops, self.run_t0 = None, None, time.time()

    # --- perception -------------------------------------------------------
    def frame(self):
        img, bounds = self.grab()
        hit = vision.first_match(img, self.t["stop"], list(self.t["stop"]), self.cfg["match"]["stop"])
        if hit:
            self.fail(img, f"Stop dialog on screen: {hit[0]}")
        return img, bounds

    def classify(self, img):
        """battle_ready (with board) | battle_busy | None (not battle: ask the navigator)."""
        m = self.cfg["match"]
        if not self.t["orbs"]:
            raise Stop("No orb templates in templates/orbs/ yet (calibration step).")
        board, ok = vision.read_board(img, self.cfg["layout"]["board"], self.t["orbs"], m["orb_max_dist"])
        if ok:
            return "battle_ready", board
        if vision.find(img, self.t["screens"].get("battle"), m["screen"]):
            return "battle_busy", None
        return None, None

    def read(self, img):
        lines = self.ocr(img)
        w = nav.stop_word(nav.banner_free(lines), self.extra_stop)
        if w:
            self.fail(img, f"Stop word on screen: '{w}'")
        st = stamina(lines, img.shape[0])
        if st and st != self.stamina:
            self.stamina = st
            emit("stamina", now=st[0], max=st[1])
        if nav.find(lines, "Completion Reward"):
            coins, drops = rewards(lines)
            self.coins = coins if coins is not None else self.coins  # coins count up: keep the last reading
            self.drops = drops if drops is not None else self.drops
        return lines

    def fail(self, img, msg):
        LOGS.mkdir(exist_ok=True)
        p = LOGS / time.strftime("stop-%Y%m%d-%H%M%S.png")
        cv2.imwrite(str(p), img)
        notify(msg)
        raise Stop(f"{msg} (screenshot: {p})")

    # --- actions ----------------------------------------------------------
    def tap_px(self, img, bounds, px, py):
        self.mouse.tap(*to_point(px, py, img.shape[1], bounds))
        self.last_progress = time.time()

    def kind(self, img):
        """Screen kind on one frame: battle_ready / battle_busy, else the navigator's reading."""
        screen, _ = self.classify(img)
        if screen:
            return screen, None, None
        return nav.decide(self.read(img), self.path, self.helper, img.shape[0], self.new_only, self.skip)

    def navigate(self, img):
        """One navigation step on a non-battle screen. Returns (kind, tapped)."""
        lines = self.read(img)
        kind, label, _ = nav.decide(lines, self.path, self.helper, img.shape[0], self.new_only, self.skip)
        if kind == "enter" and not self.team_ok(lines, img.shape[0]):
            return kind, self.next_team(img)
        if label is None:
            return kind, False
        # decided on one frame, tap on a fresh one that still agrees
        img, bounds = self.frame()
        kind2, label2, box = self.kind(img)
        if (kind2, label2) != (kind, label) or box is None:
            print(f"  screen changed ({kind}->{kind2}): not tapping")
            return kind2, False
        x, y, w, h = box
        print(f"  {kind}: tap '{label}'")
        if kind == "list" and self.new_only and label != "Back":
            self.floor = label
        self.tap_px(img, bounds, x + w / 2, y + h / 2)
        if kind == "results":
            time.sleep(1.5)  # rewards fill in over several taps on the same screen; the loop caps re-taps
        else:
            self.wait_change(kind, label, box)
        return kind, True

    def team_ok(self, lines, height):
        """Enter screen: is the profile's team selected? Its leader skill name shows above the helper's."""
        want = self.profile.get("leader_skill")
        if not want:
            return True
        own = [l for l in lines if l[2][1] < 0.62 * height]  # the helper's leader skill sits lower, at ~0.69
        if nav.find(own, want):
            self.team_swipes = 0
            return True
        return False

    def next_team(self, img):
        """Swipe the team carousel: back towards team 1 first, then forward through every team."""
        self.team_swipes += 1
        back, total = 10, 40
        if self.team_swipes > total:
            self.fail(img, f"No team with leader skill '{self.profile['leader_skill']}' after {total} swipes")
        img, bounds = self.frame()
        h, w = img.shape[:2]
        xs = (0.2, 0.4, 0.6, 0.8) if self.team_swipes <= back else (0.8, 0.6, 0.4, 0.2)
        print(f"  team: swipe {'back' if self.team_swipes <= back else 'forward'} ({self.team_swipes})")
        self.mouse.drag([to_point(w * x, h * 0.65, w, bounds) for x in xs], step_s=0.08)
        self.last_progress = time.time()
        time.sleep(0.8)
        return True

    def wait_change(self, kind, label, box0=None):
        """After a tap the screen must move on. If it doesn't, something we can't read (a stamina or
        stone prompt) may be in the way, so stop instead of tapping the same spot again."""
        t0 = time.time()
        while time.time() - t0 < self.cfg.get("tap_change_seconds", 10):
            time.sleep(0.6)
            img, _ = self.frame()
            k, l, box = self.kind(img)
            # a new popup with its OK somewhere else counts as a change (notices come one after another)
            moved = box is not None and box0 is not None and abs(box[1] - box0[1]) > 20
            if (k, l) != (kind, label) or moved:
                return
        self.fail(img, f"Tapped '{label}' but the screen didn't change")

    def scroll(self, img, bounds, up=False):
        h, w = img.shape[:2]
        fs = (0.75, 0.6, 0.45, 0.4)
        pts = [to_point(w / 2, h * f, w, bounds) for f in (fs[::-1] if up else fs)]
        print("  scroll up" if up else "  scroll")
        self.mouse.drag(pts, step_s=0.15)
        self.last_progress = time.time()

    def battle_ready_frame(self):
        img, bounds = self.frame()
        screen, board = self.classify(img)
        return (img, bounds, board) if screen == "battle_ready" else (None, None, None)

    def use_skill(self, slot):
        """Tap a portrait if its tracked cooldown allows. Returns True if the skill fired."""
        if self.ready_at.get(slot, 0) > self.turn:
            return False
        img, bounds, before = self.stable_board()
        if img is None:
            return False
        fx, fy = self.cfg["layout"]["portraits"][slot - 1]
        h, w = img.shape[:2]
        print(f"  skill slot {slot}")
        self.tap_px(img, bounds, fx * w, fy * h)  # one-tap skills: the tap fires it; uncharged does nothing
        fired = self.settled_change(before)
        emit("skill", slot=slot, fired=fired, turn=self.turn)
        cd = int(self.profile.get("cooldowns", {}).get(str(slot), 1))
        self.ready_at[slot] = self.turn + (cd if fired else 1)
        return fired

    def stable_board(self, timeout_s=6.0):
        """Board read twice in a row the same: cascades and skill animations have finished."""
        t0, last = time.time(), None
        while time.time() - t0 < timeout_s:
            img, bounds, board = self.battle_ready_frame()
            if board is not None and board == last:
                return img, bounds, board
            last = board
            time.sleep(0.4)
        return None, None, None

    def settled_change(self, before, window_s=4.0):
        """Watch for the board to change after a skill tap, then wait for it to settle.
        shortcut: "fired" = board changed; fine for orb-changing skills, upgrade for buff-only ones."""
        t0, changed, last = time.time(), False, None
        while time.time() - t0 < (window_s if not changed else self.cfg["busy_stop_seconds"]):
            _, _, board = self.battle_ready_frame()
            if board is not None and board != before:
                if changed and board == last:
                    return True  # same changed board twice in a row: animation done
                changed, last = True, board
            time.sleep(0.4)
        return changed

    def battle_turn(self, img):
        """Team clearer: counter enemy abilities, else fire the first ready Lügner (left to right),
        then keep or rebuild the cross; stall with any match when a needed counter isn't ready."""
        m = self.cfg["match"]
        img, _, _ = self.stable_board()  # let the last move's cascade finish before judging the board
        if img is None:
            return
        mech = [n for n, t in self.t["icons"].items() if vision.find(img, t, m["icon"])]
        counters, first_of, goal = prof.plan(self.profile, mech)
        fallback = self.profile.get("default", {}).get("fallback_goal", {"min_combos": 1})
        print(f"turn {self.turn}: mechanics={mech} counters={counters}")
        if counters and not any([self.use_skill(s) for s in counters]):
            print("  counter not ready: skipping Lügner, stalling")
            goal = fallback
        else:
            next((s for s in first_of if self.use_skill(s)), None)
        img, bounds, board = self.stable_board()
        if img is None:
            return
        steps = self.profile.get("max_steps", 12)
        path = solve(board, goal, max_steps=steps)
        if path is None and goal != fallback:
            print("  cross out of reach, any match instead")
            path = solve(board, fallback, max_steps=steps)
        if path is None:
            self.fail(img, f"No route for goal {goal} on board {board}")
        print("  board " + " / ".join(board) + f"  route {path}")
        rect = self.cfg["layout"]["board"]
        pts = [to_point(*vision.cell_centre(img, rect, r, c), img.shape[1], bounds) for r, c in path]
        _, _, board2 = self.battle_ready_frame()  # fresh frame right before the drag
        if board2 != board:
            print("  board changed before drag, retrying")
            return
        self.mouse.drag(pts)
        self.turn += 1
        self.last_progress = time.time()
        emit("turn", turn=self.turn, board=board, route=path, goal=goal, mechanics=mech)
        with open(self.log_path, "a") as f:
            f.write(json.dumps({"t": time.time(), "turn": self.turn, "mechanics": mech, "goal": goal,
                                "board": board, "route": path}) + "\n")
        time.sleep(1.0)

    # --- loop -------------------------------------------------------------
    def run(self, runs=1, max_iterations=None):
        self.mouse.focus()
        last_known, cleared, scrolls, i, result_taps = time.time(), 0, 0, 0, 0
        self.last_progress = time.time()
        while max_iterations is None or i < max_iterations:
            i += 1
            img, bounds = self.frame()
            screen, board = self.classify(img)
            tapped = False
            if screen is None and result_taps and nav.decide(self.read(img), self.path, self.helper, img.shape[0],
                                                             self.new_only, self.skip)[0] not in ("results", "unknown"):
                result_taps, cleared = 0, cleared + 1  # rewards screen left: count before tapping anything else
                print(f"cleared {cleared}/{runs}")
                self.record("cleared")
                emit("cleared", count=self.done_before + cleared, runs=self.total_runs or runs)
                if cleared >= runs:
                    return cleared
            if screen is None:
                screen, tapped = self.navigate(img)
            print(f"screen: {screen}")
            emit("screen", name=screen)
            if screen == "unknown":  # loading screens land here too: wait, never swipe
                if time.time() - last_known > self.cfg["unknown_stop_seconds"]:
                    self.fail(img, "Unrecognised screen")
            else:
                last_known = time.time()
            if screen == "list" and not tapped:
                n = self.cfg.get("nav", {}).get("max_scrolls", 6)
                if scrolls >= 3 * n:  # n down to the bottom, then 2n up past where we started
                    self.fail(img, f"Couldn't find {self.path} after {scrolls} scrolls")
                scrolls += 1
                self.scroll(img, bounds, up=scrolls > n)
            elif tapped:
                scrolls = 0
            if time.time() - self.last_progress > self.cfg["stall_stop_seconds"]:
                self.fail(img, f"No tap or drag for {self.cfg['stall_stop_seconds']}s (screen: {screen})")
            if screen == "battle_ready":
                self.battle_turn(img)
            elif screen == "enter" and tapped:
                self.turn, self.ready_at = 0, {}  # new dungeon run: skills start fresh
                self.run_t0 = time.time()
            if screen == "results" and tapped:
                result_taps += 1
                if result_taps > 8:
                    self.fail(img, "Rewards screen won't go away after 8 taps")

            time.sleep(self.cfg["poll_seconds"])
        return cleared


STAMINA = re.compile(r"(\d{1,4})\s*/\s*(\d{1,4})\s*$")


def stamina(lines, height):
    """(now, max) from the top bar's "578/585" next to STA, or None. Other "a/b" text sits lower."""
    for t, _, (x, y, w, h) in lines:
        m = STAMINA.search(t)
        if m and 0.15 * height < y < 0.22 * height and int(m[1]) <= int(m[2]) * 3:  # stamina can overfill
            return int(m[1]), int(m[2])
    return None


def rewards(lines):
    """(coins, drops) from the Completion Reward screen. drops: [] when it reads "None", else None
    (monster drops are icons, not text). shortcut: no drop names; add icon matching if wanted."""
    coins = drops = None
    for t, _, (x, y, w, h) in lines:
        if nav.norm(t) == "coins acquired":
            row = [o for o, _, b in lines if abs(b[1] - y) < 15 and re.fullmatch(r"[\d,]+", o.strip())]
            coins = int(row[0].replace(",", "")) if row else coins
        if nav.norm(t).startswith("monsters acquired"):
            if any(nav.norm(o) == "none" and b[1] > y for o, _, b in lines):
                drops = []
    return coins, drops
