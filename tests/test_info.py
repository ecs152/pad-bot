"""Monster/dungeon lookup. Pure helpers always run; lookups need the fan data (padbot info --update)."""
import unittest

from padbot import info


class Helpers(unittest.TestCase):
    def test_norm_folds_accents_punctuation_and_v(self):
        self.assertEqual(info.norm("- Lügner's Envoy -"), info.norm("Lugner s Enuoy"))

    def test_keywords(self):
        self.assertEqual(info.keywords("Unlock all orbs; bypass void damage shield"), ["Damage void", "Lock"])
        self.assertEqual(info.keywords(""), [])


@unittest.skipUnless(info.DB.exists(), "no fan data in data/ (run padbot info --update)")
class Lookup(unittest.TestCase):
    db = info.Info() if info.DB.exists() else None

    def test_card_number(self):
        m = self.db.lookup(["Back", "No.13442", "Lügner"])["monster"]
        self.assertEqual((m["no"], m["name"]), (13442, "Lügner"))
        self.assertIn("Dark orbs", m["active"]["text"])
        self.assertNotIn("{{", m["leader"]["text"])  # awakening placeholders filled in

    def test_misread_card_number_loses_to_the_name(self):
        self.assertEqual(self.db.lookup(["No.17458", "Linie"])["monster"]["name"], "Linie")

    def test_number_inside_a_skill_name_is_ignored(self):
        self.assertIsNone(self.db.lookup(["Gunsword Technique No. 1: Eruption Slash"])["monster"])

    def test_leader_skill_name_with_ocr_typo(self):
        self.assertEqual(self.db.lookup(["Leader Skill: False Enuoy of Peace"])["monster"]["name"], "Lügner")

    def test_floor_picks_the_dungeon_with_enemy_data(self):
        d = self.db.lookup(["- Aither Desert", "Genie of the Lamp"])["dungeon"]
        self.assertEqual((d["name"], d["floor"]["name"], d["floor"]["battles"]), ("Aither Desert", "Genie of the Lamp", 5))
        self.assertIn("Genie", [e["name"] for e in d["floor"]["enemies"]])


if __name__ == "__main__":
    unittest.main()
