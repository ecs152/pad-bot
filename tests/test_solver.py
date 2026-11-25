import time
import unittest

from padbot.solver import apply_path, evaluate, is_cross, resolve, solve, COLS


def combos(board):
    return len(resolve(''.join(board)))


class SolverTests(unittest.TestCase):
    def test_cross_detection(self):
        b = ["RBGRBG",
             "BGDGRB",
             "GDDDBR",
             "RBDRGB",
             "BGRBRG"]
        gs = resolve(''.join(b))
        self.assertTrue(any(c == 'D' and is_cross(g) for c, g in gs))

    def test_shortest_dark_cross(self):
        # Cross missing its centre: drag the light orb down two cells.
        b = ["RBGRBG",
             "BGDGRB",
             "GDLDBR",
             "RBDRGB",
             "BGDBRG"]
        self.assertEqual(combos(b), 0)
        path = solve(b, {"crosses": {"D": 1}})
        self.assertEqual(len(path) - 1, 2, path)
        met, _ = evaluate(''.join(apply_path(b, path)), {"crosses": {"D": 1}})
        self.assertTrue(met)

    def test_avoid_color(self):
        # Moving fire would be shortest; the goal forbids matching fire.
        b = ["RRBRGL",
             "GBGLDH",
             "LHDGBL",
             "BLGHDG",
             "HGLBHD"]
        path = solve(b, {"min_combos": 1, "avoid": ["R"]})
        self.assertIsNotNone(path)
        gs = resolve(''.join(apply_path(b, path)))
        self.assertTrue(gs and all(c != 'R' for c, _ in gs))

    def test_combo_goal_on_random_board(self):
        import random
        rnd = random.Random(7)
        while True:
            b = [''.join(rnd.choice("RBGLDH") for _ in range(COLS)) for _ in range(5)]
            if combos(b) == 0:
                break
        t = time.time()
        path = solve(b, {"min_combos": 4}, beam=1500)
        took = time.time() - t
        self.assertIsNotNone(path)
        self.assertGreaterEqual(combos(apply_path(b, path)), 4)
        self.assertLess(took, 20, f"solver too slow: {took:.1f}s")
        print(f"\n4-combo route: {len(path) - 1} steps in {took:.2f}s")

    def test_existing_cross_kept_with_one_step(self):
        # Lügner's active already made the cross: any 1-step move that keeps it is the answer.
        b = ["RBGRBG",
             "BGDGRB",
             "GDDDBR",
             "RBDRGB",
             "BGRBRG"]
        path = solve(b, {"crosses": {"D": 1}})
        self.assertEqual(len(path) - 1, 1, path)
        self.assertTrue(evaluate(''.join(apply_path(b, path)), {"crosses": {"D": 1}})[0])

    def test_combo_absorb_timing(self):
        import random
        for target in (6, 7):
            for seed in range(3):
                rnd = random.Random(seed)
                b = [''.join(rnd.choice("RBGLDH") for _ in range(COLS)) for _ in range(5)]
                t = time.time()
                path = solve(b, {"min_combos": target}, max_steps=25)
                took = time.time() - t
                got = combos(apply_path(b, path)) if path else 0
                print(f"\n{target}-combo seed {seed}: {len(path) - 1 if path else None} steps, {got} combos, {took:.1f}s")
                self.assertIsNotNone(path)
                self.assertLess(took, 30)

    def test_link_five_dark(self):
        b = ["RBGRBG",
             "BGDGRB",
             "GDLDBR",
             "RBDRGB",
             "BGDBRG"]
        path = solve(b, {"link": {"D": 5}})
        gs = resolve(''.join(apply_path(b, path)))
        self.assertTrue(any(c == 'D' and len(g) >= 5 for c, g in gs))
        self.assertLessEqual(len(path) - 1, 2)

    def test_path_is_adjacent_steps(self):
        b = ["RBGRBG", "BGDGRB", "GDLDBR", "RBDRGB", "BGDBRG"]
        path = solve(b, {"crosses": {"D": 1}})
        for (a, b2), (c, d) in zip(path, path[1:]):
            self.assertEqual(abs(a - c) + abs(b2 - d), 1)


if __name__ == "__main__":
    unittest.main()
