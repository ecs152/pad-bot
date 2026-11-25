import unittest

from padbot import mechanics as M

SAMPLE = bytes.fromhex("08041215080112110806120208181A091A070A02104610C401")  # DadGuide enemy 4: skill 196


class Detect(unittest.TestCase):
    def test_enemy_text(self):
        cases = {
            "Absorb damage when combos <= 5 for 999 turns": ["combo_absorb"],
            "Absorb damage when damage >= 500,000,000 for 3 turns": ["damage_absorb"],
            "Absorb Fire and Dark damage for 5 turns": ["attribute_absorb"],
            "Void damage >= 2,000,000,000 for 10 turns": ["damage_void"],
            "Bind awoken skills for 3 turns": ["awoken_bind"],
            "Bind 2 random subs for 3 turns, Deal 100% damage": ["bind"],
            "Bind active skills for 5 turns": ["skill_bind"],
            "Seal the 1st row for 2 turn, Deal 100% damage": ["tape"],
            "Random 3 orbs change every 1.0s for 1 turn": ["roulette"],
            "Deal 4,000% damage": [],
        }
        for text, want in cases.items():
            self.assertEqual(M.detect(text), want, text)

    def test_counters_from_active_and_awakenings(self):
        lug = "Unlock all orbs; For 1 turn, bypass void damage shield effects; For 1 turn, bypass combo absorb shield effects"
        c = M.counters(lug, ["Resistance-Bind+", "Resistance-Blind", "Resistance-Blind"])
        self.assertEqual(set(c), {"locks", "damage_void", "combo_absorb", "bind", "blind"})
        self.assertAlmostEqual(c["blind"][0][2], 0.4)  # two 20% blind resists

    def test_team_levels(self):
        cov = M.team([(1, "A", "For 2 turns, bypass att. absorb and damage absorb shield effects", ["Resistance-Blind+"]),
                      (2, "B", "", ["Resistance-Poison"] * 3, )])
        self.assertEqual(cov["damage_absorb"]["level"], "full")
        self.assertEqual(cov["attribute_absorb"]["level"], "full")
        self.assertEqual(cov["blind"]["level"], "full")      # one + resist = 100%
        self.assertEqual(cov["poison"]["level"], "partial")  # 3 x 20%
        self.assertEqual(M.rules(cov), {"damage_absorb": [1], "attribute_absorb": [1]})

    def test_report_puts_gaps_first(self):
        cov = M.team([(5, "Voider", "For 2 turns, bypass damage absorb shield effects", [])])
        seen = {"damage_absorb": [{"enemy": "X", "skill": "s", "preempt": False}],
                "awoken_bind": [{"enemy": "Y", "skill": "t", "preempt": True}],
                "roulette": [{"enemy": "Z", "skill": "u", "preempt": False}]}
        self.assertEqual([(r["key"], r["status"]) for r in M.report(cov, seen)],
                         [("awoken_bind", "gap"), ("roulette", "manage"), ("damage_absorb", "full")])


class Behaviour(unittest.TestCase):
    def test_skill_ids(self):
        self.assertEqual(M.skill_ids(SAMPLE), [(196, False)])
        pre = bytearray(SAMPLE)
        pre[pre.index(bytes.fromhex("0806"))+1] = 2  # same group as PREEMPT
        self.assertEqual(M.skill_ids(bytes(pre)), [(196, True)])


if __name__ == "__main__":
    unittest.main()
