"""End-to-end on synthetic frames: board reading, coordinate mapping, profile merge, and the loop's
safety rules. No real window, no real mouse events."""
import itertools
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from padbot import mac, profile, run, vision
from padbot.mac import Stop, to_pixel, to_point
from padbot.solver import COLS, ROWS

W, H = 400, 800
RECT = [0.0, 0.5, 1.0, 0.9]
COLORS = {"R": (40, 40, 220), "B": (220, 120, 30), "G": (40, 180, 40), "L": (60, 220, 240),
          "D": (160, 40, 140), "H": (180, 120, 240)}


def make_frame(board=None, dim=False, banner=None):
    img = np.full((H, W, 3), 30, np.uint8)
    cv2.putText(img, "BATTLE", (20, 60), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255, 255, 255), 3)
    if board:
        for r in range(ROWS):
            for c in range(COLS):
                x, y = vision.cell_centre(img, RECT, r, c)
                cv2.circle(img, (int(x), int(y)), 22, COLORS[board[r][c]], -1)
                cv2.circle(img, (int(x - 6), int(y - 6)), 5, (255, 255, 255), -1)  # a "face"
    if dim:
        img = (img * 0.4).astype(np.uint8)
    if banner:
        img[:] = 30
        cv2.putText(img, banner, (20, 300), cv2.FONT_HERSHEY_SIMPLEX, 1.4, (255, 255, 255), 3)
        cv2.rectangle(img, (120, 600), (280, 660), (0, 160, 255), -1)
        cv2.putText(img, "OK", (175, 643), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (0, 0, 0), 3)
    return img


BOARD = ["RBGRBG", "BGDGRB", "GDLDBR", "RBDRGB", "BGDBRG"]
CFG = {"poll_seconds": 0, "tap_change_seconds": 0.7, "unknown_stop_seconds": 0, "stall_stop_seconds": 60, "busy_stop_seconds": 0.2,
       "match": {"screen": 0.88, "button": 0.9, "icon": 0.85, "stop": 0.8, "orb_max_dist": 25},
       "layout": {"board": RECT, "portraits": [[0.1, 0.45]] * 6},
       "nav": {"path": [], "helper": "You"}}
TEXT = {}  # fake OCR: frame id -> lines


def screen(*labels):
    """A non-battle frame whose 'OCR' reads labels, stacked top to bottom from y=300."""
    img = np.full((H, W, 3), 60, np.uint8)
    TEXT[id(img)] = [(t, 1.0, (100, 300 + 40 * i, 200, 30)) for i, t in enumerate(labels)]
    FRAMES.append(img)  # keep alive so ids stay unique
    return img


FRAMES = []
PROFILE = {"max_steps": 12, "default": {"skills": [], "goal": {"crosses": {"D": 1}}}}


class RecMouse(mac.Mouse):
    def __init__(self):
        super().__init__(live=False)
        self.taps, self.drags = [], []

    def tap(self, x, y):
        self.taps.append((x, y))

    def drag(self, pts, **kw):
        self.drags.append(pts)


class Pipeline(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self._root, self._logs, self._notify = vision.ROOT, run.LOGS, run.notify
        vision.ROOT, run.LOGS, run.notify = self.tmp / "templates", self.tmp / "logs", lambda m: None
        # orb references cropped from a synthetic board, like `padbot crop` does on a real one
        img = make_frame(BOARD)
        (vision.ROOT / "orbs").mkdir(parents=True)
        done = set()
        for r, c, crop, _ in vision.board_cells(img, RECT):
            if BOARD[r][c] not in done:
                cv2.imwrite(str(vision.ROOT / "orbs" / f"{BOARD[r][c]}.png"), crop)
                done.add(BOARD[r][c])
        for k in ("screens", "buttons", "stop"):
            (vision.ROOT / k).mkdir()
        cv2.imwrite(str(vision.ROOT / "screens" / "battle.png"), make_frame(BOARD)[30:75, 15:200])
        res = make_frame(banner="RESULTS")
        cv2.imwrite(str(vision.ROOT / "screens" / "results.png"), res[260:315, 15:220])
        cv2.imwrite(str(vision.ROOT / "buttons" / "results_ok.png"), res[600:660, 120:280])
        cv2.imwrite(str(vision.ROOT / "stop" / "continue.png"), make_frame(banner="CONTINUE?")[260:315, 15:260])

    def tearDown(self):
        vision.ROOT, run.LOGS, run.notify = self._root, self._logs, self._notify

    def bot(self, frames, mouse):
        it = iter(frames)
        return run.Bot(CFG, PROFILE, mouse, lambda: (next(it), (100, 50, W / 2, H / 2)),
                       ocr=lambda img: TEXT.get(id(img), []))

    def test_read_board(self):
        board, ok = vision.read_board(make_frame(BOARD), RECT, vision.load("orbs"), 25)
        self.assertEqual(board, BOARD)
        self.assertTrue(ok)
        _, ok = vision.read_board(make_frame(BOARD, dim=True), RECT, vision.load("orbs"), 25)
        self.assertFalse(ok, "dimmed board must not read as ready")

    def test_unknown_cell_reads_as_dot(self):
        img = make_frame(BOARD)
        x, y = vision.cell_centre(img, RECT, 1, 0)
        cv2.rectangle(img, (int(x - 30), int(y - 30)), (int(x + 30), int(y + 30)), (230, 230, 230), -1)  # a "cloud"
        board, ok = vision.read_board(img, RECT, vision.load("orbs"), 25)
        self.assertTrue(ok)
        self.assertEqual(board[1][0], '.')

    def test_mapping_round_trip(self):
        bounds = (100, 50, 200, 400)  # points; image is 2x (Retina)
        gx, gy = to_point(40, 80, 400, bounds)
        self.assertEqual((gx, gy), (120, 90))
        self.assertEqual(to_pixel(gx, gy, 400, bounds), (40, 80))

    def test_profile_merge(self):
        p = {"default": {"skills": [1], "goal": {"crosses": {"D": 1}}},
             "on": {"combo_absorb": {"goal": {"min_combos": 7}}, "absorb_red": {"skills": [5], "goal": {"avoid": ["R"]}},
                    "awoken_bind": {"skills": [3, 1]}}}
        self.assertEqual(profile.plan(p, []), ([1], [], {"crosses": {"D": 1}}))
        self.assertEqual(profile.plan(p, ["awoken_bind"]), ([1, 3], [], {"crosses": {"D": 1}}))
        skills, _, goal = profile.plan(p, ["absorb_red", "combo_absorb"])
        self.assertEqual(skills, [1, 5])
        self.assertEqual(goal, {"min_combos": 7, "avoid": ["R"]})

    def test_battle_turn_drags_shortest_cross(self):
        m = RecMouse()
        f = make_frame(BOARD)
        self.bot(itertools.repeat(f), m).run(max_iterations=1)
        self.assertEqual(len(m.drags), 1)
        pts = m.drags[0]
        self.assertEqual(len(pts), 3)  # 2-step route
        # route starts on the light orb at row 2, col 2 -> global points
        x, y = vision.cell_centre(f, RECT, 2, 2)
        self.assertEqual(pts[0], to_point(x, y, W, (100, 50, W / 2, H / 2)))

    def test_turn_and_cleared_events(self):
        import contextlib, io, json
        from padbot.events import PREFIX
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.bot(itertools.repeat(make_frame(BOARD)), RecMouse()).run(max_iterations=1)
            r = screen("Completion Reward", "Beyond the Desert")
            self.bot([r, r, screen("Back", "Genie of the Lamp", "Battles")], RecMouse()).run(runs=1, max_iterations=2)
        ev = [json.loads(l[len(PREFIX):]) for l in buf.getvalue().splitlines() if l.startswith(PREFIX)]
        turn = next(e for e in ev if e["type"] == "turn")
        self.assertEqual((turn["turn"], turn["board"], len(turn["route"])), (1, BOARD, 3))
        self.assertIn({"type": "cleared", "count": 1, "runs": 1}, [{k: v for k, v in e.items() if k != "t"} for e in ev])
        rec = next(e for e in ev if e["type"] == "run")
        self.assertEqual((rec["result"], rec["target"]), ("cleared", "uncleared: ?"))
        hist = [json.loads(l) for l in (run.LOGS / "history.jsonl").read_text().splitlines()]
        self.assertEqual([h["result"] for h in hist], ["cleared"])

    def test_queue_moves_to_another_dungeon(self):
        """Item 1 cleared on Aither Desert's floor list; item 2 is in Sky Garden: Back, then the dungeon."""
        m = RecMouse()
        def floors(title, *rows):  # title bar at y=180 (0.2-0.27 of H=800), floors below
            img = np.full((H, W, 3), 60, np.uint8)
            TEXT[id(img)] = [("Back", 1.0, (10, 180, 60, 30)), (title, 1.0, (100, 180, 200, 30))] + [
                (t, 1.0, (100, 300 + 40 * i, 200, 30)) for i, t in enumerate(rows)]
            FRAMES.append(img)
            return img
        a = floors("Aither Desert", "4-6-2", "Beyond the Desert", "Battles")
        d = floors("Stage 4", "4-6", "Aither Desert", "4-7", "Sky Garden")
        bot = self.bot([a, a, d, d, d, floors("Sky Garden", "4-7-1", "Cloud Floor", "Battles")], m)
        bot.set_target(["Sky Garden", "Cloud Floor"])
        bot.run(runs=1, max_iterations=2)
        self.assertEqual(len(m.taps), 2, "Back on the old floor list, then Sky Garden")
        self.assertEqual(m.taps[1], to_point(200, 300 + 40 * 3 + 15, W, (100, 50, W / 2, H / 2)))

    def test_queue_labels_checked_before_any_tap(self):
        bot = self.bot([], RecMouse())
        with self.assertRaises(Stop):
            bot.set_target(["Shop", "Buy Magic Stone"])

    def test_stamina_and_rewards_read(self):
        top = [("578/585", 1, (300, 275, 80, 20)), ("STA", 1, (250, 275, 40, 20)), ("swipe 5/22", 1, (0, 550, 80, 20))]
        self.assertEqual(run.stamina(top, 1440), (578, 585))
        self.assertIsNone(run.stamina(top[2:], 1440))
        res = [("Coins Acquired", 1, (60, 490, 150, 20)), ("6,304", 1, (400, 492, 60, 20)),
               ("Monster(s) Acquired", 1, (60, 690, 150, 20)), ("None", 1, (300, 780, 50, 20))]
        self.assertEqual(run.rewards(res), (6304, []))
        self.assertEqual(run.rewards(res[:3]), (6304, None))

    def test_no_drag_if_board_changed(self):
        m = RecMouse()
        other = ["RBGRBG", "BGDGRB", "GDLDBR", "RBDRGB", "BGDBRB"]
        # loop frame, 2 stable reads before judging, 2 before solving, then the pre-drag check sees a new board
        self.bot([make_frame(BOARD)] * 5 + [make_frame(other)], m).run(max_iterations=1)
        self.assertEqual(m.drags, [])

    def test_results_tapped_from_fresh_frame(self):
        m = RecMouse()
        r = screen("Completion Reward", "Beyond the Desert")
        self.assertEqual(self.bot([r, r, screen("Back", "Genie of the Lamp", "Battles")], m).run(runs=1, max_iterations=2), 1)
        self.assertEqual(m.taps, [to_point(200, 315, W, (100, 50, W / 2, H / 2))])

    def test_rewards_retapped_until_gone_counted_once(self):
        m = RecMouse()
        CFG["nav"]["path"] = ["Beyond the Desert"]
        self.addCleanup(lambda: CFG["nav"].update(path=[]))
        r = screen("Completion Reward")
        frames = [r] * 6 + [screen("Back", "Beyond the Desert", "Battles")]
        self.assertEqual(self.bot(frames, m).run(runs=1, max_iterations=4), 1)
        self.assertEqual(len(m.taps), 3, "done before tapping anything on the floor list")

    def test_stop_word_halts_without_tapping(self):
        m = RecMouse()
        with self.assertRaises(Stop):
            self.bot([screen("Continue?", "Use 1 Magic Stone")], m).run(max_iterations=1)
        self.assertEqual((m.taps, m.drags), ([], []))

    def test_dialog_appearing_before_tap_halts(self):
        m = RecMouse()
        with self.assertRaises(Stop):
            self.bot([screen("Completion Reward"), screen("Recover stamina?", "OK")], m).run(max_iterations=1)
        self.assertEqual(m.taps, [])

    def test_screen_changed_before_tap_not_tapped(self):
        m = RecMouse()
        with self.assertRaises(Stop):  # the new screen is unknown, so it also stops
            self.bot([screen("TIPS", "OK"), screen("Not sure what this is")], m).run(max_iterations=1)
        self.assertEqual(m.taps, [])

    def test_tap_with_no_effect_stops(self):
        # e.g. a stamina prompt we can't read covers the screen: never tap the same spot again
        m = RecMouse()
        e = screen("Enter Dungeon", "Beyond the Desert", "Enter")
        with self.assertRaises(Stop):
            self.bot(itertools.repeat(e), m).run(max_iterations=3)
        self.assertEqual(len(m.taps), 1)

    def test_unknown_screen_never_swipes(self):
        m = RecMouse()
        cfg = dict(CFG, unknown_stop_seconds=60, nav={"path": ["Aither Desert"], "helper": "You"})
        it = itertools.repeat(screen("Now Loading"))
        run.Bot(cfg, PROFILE, m, lambda: (next(it), (100, 50, W / 2, H / 2)),
                ocr=lambda img: TEXT.get(id(img), [])).run(max_iterations=3)
        self.assertEqual((m.taps, m.drags), ([], []))

    def test_list_without_target_scrolls(self):
        m = RecMouse()
        cfg = dict(CFG, nav={"path": ["Aither Desert"], "helper": "You"})
        it = itertools.repeat(screen("Back", "Genie of the Lamp", "Battles"))
        run.Bot(cfg, PROFILE, m, lambda: (next(it), (100, 50, W / 2, H / 2)),
                ocr=lambda img: TEXT.get(id(img), [])).run(max_iterations=2)
        self.assertEqual(len(m.drags), 2)

    def test_list_scrolls_down_then_up_then_stops(self):
        m = RecMouse()
        cfg = dict(CFG, nav={"path": ["Aither Desert"], "helper": "You", "max_scrolls": 2})
        it = itertools.repeat(screen("Back", "Genie of the Lamp", "Battles"))
        bot = run.Bot(cfg, PROFILE, m, lambda: (next(it), (100, 50, W / 2, H / 2)),
                      ocr=lambda img: TEXT.get(id(img), []))
        with self.assertRaises(Stop):
            bot.run(max_iterations=20)
        dirs = ["down" if d[0][1] > d[-1][1] else "up" for d in m.drags]  # finger moves up = list scrolls down
        self.assertEqual(dirs, ["down", "down", "up", "up", "up", "up"])

    def test_stall_stops(self):
        m = RecMouse()
        cfg = dict(CFG, stall_stop_seconds=-1)
        it = itertools.repeat(screen("TIPS", "OK"))
        with self.assertRaises(Stop):
            run.Bot(cfg, PROFILE, m, lambda: (next(it), (100, 50, W / 2, H / 2)),
                    ocr=lambda img: TEXT.get(id(img), [])).run(max_iterations=1)

    def test_skill_fire_detected_after_animation(self):
        other = ["DDDRBG", "BGDGRB", "GDLDBR", "RBDRGB", "BGDBRG"]
        f, g, dim = make_frame(BOARD), make_frame(other), make_frame(BOARD, dim=True)
        bot = self.bot([dim, f, g, g], RecMouse())
        self.assertTrue(bot.settled_change(BOARD, window_s=5))
        bot = self.bot(itertools.repeat(f), RecMouse())
        self.assertFalse(bot.settled_change(BOARD, window_s=0.5))

    def test_unknown_screen_stops(self):
        m = RecMouse()
        with self.assertRaises(Stop):
            self.bot([screen()], m).run(max_iterations=1)

    def test_stop_word_in_target_rejected(self):
        cfg = dict(CFG, nav={"path": ["Buy Magic Stone"], "helper": "You"})
        with self.assertRaises(Stop):
            run.Bot(cfg, PROFILE, RecMouse(), lambda: None)

    def test_cooldown_skips_portrait_tap(self):
        m = RecMouse()
        bot = self.bot(itertools.repeat(make_frame(BOARD)), m)
        bot.ready_at[1] = 3
        self.assertFalse(bot.use_skill(1))
        self.assertEqual(m.taps, [])

    def test_counter_not_ready_skips_lugner_and_stalls(self):
        m = RecMouse()
        f = make_frame(BOARD)
        prof = {"max_steps": 12, "cooldowns": {"1": 3},
                "default": {"first_of": [1], "goal": {"crosses": {"D": 1}}, "fallback_goal": {"min_combos": 1}},
                "on": {"absorb": {"skills": [5]}}}
        bot = run.Bot(CFG, prof, m, lambda: (f, (100, 50, W / 2, H / 2)), ocr=lambda img: [])
        bot.t["icons"] = {"absorb": f[30:75, 15:200]}  # the icon is "on screen"
        bot.battle_turn(f)
        self.assertEqual(len(m.taps), 1, "only the counter (slot 5) is tapped, Lügner is saved")
        self.assertEqual(bot.ready_at, {5: 1})
        self.assertEqual(len(m.drags), 1)


if __name__ == "__main__":
    unittest.main()
