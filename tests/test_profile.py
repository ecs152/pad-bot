"""Profile editing: the Teams tab saves through profile.save, so a save must keep every rule."""
import tempfile
import tomllib
import unittest
from pathlib import Path

from padbot import profile

ROOT = Path(__file__).resolve().parents[1]


class ProfileEditTest(unittest.TestCase):
    def test_every_profile_round_trips(self):
        for f in (ROOT / "profiles").glob("*.toml"):
            p = profile.load(f)
            self.assertEqual(profile.validate(p), [], f.name)
            self.assertEqual(tomllib.loads(profile.dumps(p)), p, f.name)

    def test_save_writes_and_rejects(self):
        p = profile.load(ROOT / "profiles" / "lugner.toml")
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "t.toml"
            self.assertEqual(profile.save(out, p), [])
            self.assertEqual(profile.load(out), p)
            bad = {**p, "cooldowns": {"7": 0}, "default": {"first_of": [1, 1], "goal": {"crosses": {"X": 1}, "avoid": ["D"]}}}
            errs = profile.save(out, bad)
            self.assertEqual(len(errs), 3, errs)
            self.assertEqual(profile.load(out), p)  # nothing written on error

    def test_odd_names_quote(self):
        p = {"name": 'Team "A"\nB', "on": {"attribute_absorb": {}}, "default": {"goal": {}}}
        self.assertEqual(tomllib.loads(profile.dumps(p)), p)
        self.assertTrue(profile.validate({"name": "x", "on": {"Bad Name": {}}}))


if __name__ == "__main__":
    unittest.main()
