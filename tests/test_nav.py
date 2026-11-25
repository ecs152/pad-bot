"""Navigator decisions on fake OCR lines, plus real OCR on saved captures when they exist."""
import unittest
from pathlib import Path

import cv2

from padbot import nav

SHOTS = Path(__file__).resolve().parent.parent / "shots"
PATH = ["Aither Desert", "Beyond the Desert"]


def lines(*items):
    return [(t, 1.0, (100, y, 200, 30)) for t, y in items]


TITLE = lines(("Dersion 23.4.0", 170), ("Data", 223), ("Recou.", 250), ("START", 1037),
              ("© GungHo Online Entertainment, Inc. All Rights Reserved.", 1224), ("100 MAGIC STONES &", 1258))


class Decide(unittest.TestCase):
    def test_title_screen_taps_start_and_ignores_its_banner(self):
        self.assertEqual(nav.decide(TITLE, PATH, "You", 1440)[:2], ("title", "START"))
        self.assertIsNone(nav.stop_word(nav.banner_free(TITLE)))

    def test_magic_stone_still_stops_off_the_title_screen(self):
        shop = lines(("START", 300), ("Buy 100 Magic Stones", 1258))  # START alone isn't the title screen
        self.assertEqual(nav.stop_word(nav.banner_free(shop)), "magic stone")

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


class Queue(unittest.TestCase):
    def test_other_dungeons_floor_list_backs_out(self):
        L = lines(("Back", 340), ("Sky Garden", 345), ("4-7-1", 400), ("Cloud Floor", 440), ("Battles", 480))
        self.assertEqual(nav.decide(L, PATH, "You", 1440)[:2], ("list", "Back"))

    def test_own_dungeons_floor_list_scrolls(self):
        L = lines(("Back", 340), ("Aither Desert", 345), ("4-6-5", 400), ("Genie of the Lamp", 440), ("Battles", 480))
        self.assertEqual(nav.decide(L, PATH, "You", 1440), ("list", None, None))

    def test_dungeon_list_without_target_scrolls(self):
        L = lines(("Back", 340), ("Stage 4", 345), ("4-7", 400), ("Sky Garden", 440))
        self.assertEqual(nav.decide(L, PATH, "You", 1440), ("list", None, None))

    def test_parse_queue(self):
        from padbot.__main__ import parse_queue
        from padbot.mac import Stop
        q = parse_queue('[{"path": "Aither Desert/Beyond the Desert", "runs": 2}, {"uncleared": true}]')
        self.assertEqual(q, [{"path": PATH, "uncleared": False, "runs": 2}, {"path": [], "uncleared": True, "runs": 1}])
        for bad in ('{}', '[]', '[{"path": "Aither Desert"}]', '[{"uncleared": true, "runs": 0}]', 'nope'):
            with self.assertRaises(Stop):
                parse_queue(bad)


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

    def test_skipped_dungeon_not_entered_and_left(self):
        D = self.rows(("Back", 31, 339), ("4-6", 123, 399), ("Aither Desert", 121, 445),
                      ("4-7", 123, 560), ("Sky Garden", 121, 606))
        self.assertEqual(nav.decide(D, [], "You", 1440, True, ("Aither Desert",))[:2], ("list", "Sky Garden"))
        F = self.rows(("Back", 33, 338), ("Aither Desert", 200, 338), ("4-6-5", 64, 397), ("Genie of the Lamp", 64, 432))
        self.assertEqual(nav.decide(F, [], "You", 1440, True, ("Aither Desert",))[:2], ("list", "Back"))

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
        img = cv2.imread(str(SHOTS / "r3.png"))  # Aither Desert floor list, skipped: back out
        self.assertEqual(nav.decide(read_text(img), [], "You", img.shape[0], True, ("Aither Desert",))[1], "Back")


if __name__ == "__main__":
    unittest.main()


class ExtraStopWords(unittest.TestCase):
    def test_user_words_stop(self):
        lines = [("Rank Up Bonus", 1, (0, 0, 10, 10))]
        self.assertIsNone(nav.stop_word(lines))
        self.assertEqual(nav.stop_word(lines, ("rank up",)), "rank up")


class Events(unittest.TestCase):
    def test_emit_is_one_json_line(self):
        import io, json, contextlib
        from padbot.events import PREFIX, emit
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            emit("cleared", count=1, runs=3)
        line = buf.getvalue()
        self.assertTrue(line.startswith(PREFIX) and line.count("\n") == 1)
        self.assertEqual(json.loads(line[len(PREFIX):])["count"], 1)
