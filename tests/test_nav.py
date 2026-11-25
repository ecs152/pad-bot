"""Navigator decisions on fake OCR lines, plus real OCR on saved captures when they exist."""
import unittest
from pathlib import Path

import cv2

from padbot import nav

SHOTS = Path(__file__).resolve().parent.parent / "shots"
PATH = ["Aither Desert", "Beyond the Desert"]


def lines(*items):
    return [(t, 1.0, (100, y, 200, 30)) for t, y in items]


class Decide(unittest.TestCase):
    def test_floor_list_taps_floor_not_header(self):
        k, label, _ = nav.decide(lines(("Aither Desert", 350), ("Beyond the Desert", 940)), PATH, "You", 1440)
        self.assertEqual((k, label), ("list", "Beyond the Desert"))

    def test_header_alone_is_not_a_target(self):
        k, _, _ = nav.decide(lines(("Back Aither Desert", 350), ("Genie of the Lamp", 440), ("Battles", 480)), PATH, "You", 1440)
        self.assertEqual(k, "unknown")

    def test_dungeon_list_taps_dungeon(self):
        k, label, _ = nav.decide(lines(("Normal Dungeons", 350), ("Aither Desert", 700)), PATH, "You", 1440)
        self.assertEqual((k, label), ("list", "Aither Desert"))

    def test_helper_flow(self):
        self.assertEqual(nav.decide(lines(("Select a Helper", 350), ("You", 465)), PATH, "You", 1440)[0], "helper")
        k, label, _ = nav.decide(lines(("Select a Helper", 350), ("Select", 860), ("Check Info", 960)), PATH, "You", 1440)
        self.assertEqual((k, label), ("helper_popup", "Select"))

    def test_enter_beats_floor_name(self):
        k, label, _ = nav.decide(lines(("Enter Dungeon", 350), ("Beyond the Desert", 600), ("Enter", 1145)),
                                 PATH, "You", 1440)
        self.assertEqual((k, label), ("enter", "Enter"))

    def test_fuzzy_match_survives_ocr_misreads(self):
        self.assertIsNotNone(nav.find(lines(("Bevond the Desert", 900)), "Beyond the Desert"))
        self.assertIsNone(nav.find(lines(("Temple Under the Desert", 900)), "Beyond the Desert"))

    def test_list_without_target_scrolls(self):
        self.assertEqual(nav.decide(lines(("Back", 340), ("Genie of the Lamp", 440), ("Battles", 480)), PATH, "You", 1440),
                         ("list", None, None))

    def test_stop_words(self):
        self.assertTrue(nav.stop_word(lines(("Reuiue?", 500))))  # "Revive?" as the game font reads it
        self.assertTrue(nav.stop_word(lines(("Continue?", 500))))
        self.assertTrue(nav.stop_word(lines(("Use 1 Magic Stone to recover", 500))))
        self.assertFalse(nav.stop_word(lines(("Beyond the Desert", 500))))


class Uncleared(unittest.TestCase):
    def rows(self, *items):
        return [(t, 1.0, (x, y, 100, 25)) for t, x, y in items]

    def test_picks_first_floor_without_clear_badge(self):
        L = self.rows(("Back", 33, 338), ("4-6-5", 64, 397), ("new", 188, 401), ("Genie of the Lamp", 64, 432),
                      ("4-6-4", 64, 562), ("Clear!", 179, 567), ("Guards of the Light", 64, 598))
        self.assertEqual(nav.decide(L, [], "You", 1440, new_only=True)[:2], ("list", "Genie of the Lamp"))

    def test_all_floors_cleared_goes_back(self):
        L = self.rows(("Back", 33, 338), ("4-6-4", 64, 562), ("Clear!", 179, 567), ("Guards of the Light", 64, 598))
        self.assertEqual(nav.decide(L, [], "You", 1440, new_only=True)[:2], ("list", "Back"))

    def test_dungeon_list_all_cleared_scrolls(self):
        L = self.rows(("Back", 31, 339), ("4-10", 123, 399), ("Clear!", 238, 399), ("Paradise", 121, 445))
        self.assertEqual(nav.decide(L, [], "You", 1440, new_only=True), ("list", None, None))


@unittest.skipUnless((SHOTS / "r3.png").exists(), "real captures not present")
class RealScreens(unittest.TestCase):
    def kind(self, name):
        from padbot.ocr import read_text
        img = cv2.imread(str(SHOTS / name))
        return nav.decide(read_text(img), PATH, "You", img.shape[0])[:2]

    def test_real(self):
        self.assertEqual(self.kind("r3.png"), ("list", "Beyond the Desert"))   # Aither Desert floor list
        self.assertEqual(self.kind("t2.png"), ("enter", "Enter"))              # Enter Dungeon
        self.assertEqual(self.kind("t1.png"), ("helper_popup", "Select"))      # helper popup
        img = cv2.imread(str(SHOTS / "c2.png"))
        from padbot.ocr import read_text
        k, label, box = nav.decide(read_text(img), PATH, "You", img.shape[0])
        self.assertEqual((k, label), ("helper", "You"))                         # helper list
        self.assertTrue(400 < box[1] < 500, box)                                # your own row, at the top
        self.assertEqual(self.kind("r2.png")[0], "results")                    # Completion Reward
        self.assertEqual(self.kind("r0.png"), ("tips", "OK"))                  # CLEAR! + tips
        from padbot.ocr import read_text
        for f, want in (("r3.png", "Genie of the Lamp"), ("n4.png", None)):
            img = cv2.imread(str(SHOTS / f))
            self.assertEqual(nav.decide(read_text(img), [], "You", img.shape[0], new_only=True)[1], want)


if __name__ == "__main__":
    unittest.main()
