import json
import tempfile
import unittest
from pathlib import Path

from padbot.boardview import caption, last_event, render

BOARD = ["LDHGRR", "DDDHGB", "GDDHLD", "HBRBBD", "RGBBG."]


class BoardViewTests(unittest.TestCase):
    def test_render_draws_route_endpoints(self):
        img = render(BOARD, [(0, 2), (0, 3), (1, 3)], cell=64)
        pad = 16
        start, end = img[pad + 32, pad + 2 * 64 + 32], img[pad + 64 + 32, pad + 3 * 64 + 32]
        self.assertEqual(tuple(start), (60, 200, 60))  # green start dot
        self.assertEqual(tuple(end), (50, 50, 220))    # red end dot
        self.assertEqual(img.shape[:2], (5 * 64 + 2 * pad, 6 * 64 + 2 * pad))

    def test_last_event_reads_newest_log(self):
        with tempfile.TemporaryDirectory() as d:
            ev = {"turn": 3, "goal": {"crosses": {"D": 1}}, "mechanics": [], "board": BOARD, "route": [[3, 0], [3, 1]]}
            Path(d, "run-1.jsonl").write_text(json.dumps({"turn": 1}) + "\n" + json.dumps(ev) + "\n")
            self.assertEqual(last_event(Path(d)), ev)
            self.assertEqual(caption(ev)[:2], ["Turn 3  -  1 step", "Goal: dark cross x1"])
            self.assertIsNone(last_event(Path(d, "none")))


class Merge(unittest.TestCase):
    def test_sparkling_cells_fill_in(self):
        from padbot.vision import merge
        a, b = ["DG.BLH", ".GGGGG"], ["DGBBLH", "GGGGGG"]
        self.assertEqual(merge(a, b), ["DGBBLH", "GGGGGG"])
        self.assertIsNone(merge(a, ["DGBRLH", "GGGGGG"]))  # a real change is still a change
