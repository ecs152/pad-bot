"""Board matching and shortest-route search.

Board: 5 strings of 6 chars. Orbs: R fire, B water, G wood, L light, D dark, H heal,
J jammer, P poison, M mortal poison, '.' empty/unknown.
Goal (from the team profile): {"crosses": {"D": 1}, "link": {"D": 5}, "min_combos": 0, "avoid": ["R"]}.
link = at least one matched group of that colour with N+ orbs.
"""
ROWS, COLS = 5, 6
DIRS = [(-1, 0), (1, 0), (0, -1), (0, 1)]  # shortcut: no diagonals; add if routes get too long


def _groups(cells):
    """cells: flat list of 30. Returns list of (color, set_of_indices) matched groups."""
    marked = set()
    for r in range(ROWS):
        for c in range(COLS):
            o = cells[r * COLS + c]
            if o == '.':
                continue
            if c + 2 < COLS and cells[r * COLS + c + 1] == o == cells[r * COLS + c + 2]:
                marked |= {r * COLS + c, r * COLS + c + 1, r * COLS + c + 2}
            if r + 2 < ROWS and cells[(r + 1) * COLS + c] == o == cells[(r + 2) * COLS + c]:
                marked |= {r * COLS + c, (r + 1) * COLS + c, (r + 2) * COLS + c}
    groups, seen = [], set()
    for i in marked:
        if i in seen:
            continue
        color, stack, g = cells[i], [i], set()
        while stack:
            j = stack.pop()
            if j in g:
                continue
            g.add(j)
            r, c = divmod(j, COLS)
            for dr, dc in DIRS:
                rr, cc = r + dr, c + dc
                k = rr * COLS + cc
                if 0 <= rr < ROWS and 0 <= cc < COLS and k in marked and k not in g and cells[k] == color:
                    stack.append(k)
        seen |= g
        groups.append((color, g))
    return groups


def is_cross(g):
    if len(g) != 5:
        return False
    rc = [divmod(i, COLS) for i in g]
    rs, cs = sorted(r for r, _ in rc), sorted(c for _, c in rc)
    mr, mc = rs[2], cs[2]
    return set(rc) == {(mr, mc), (mr - 1, mc), (mr + 1, mc), (mr, mc - 1), (mr, mc + 1)}


def resolve(cells):
    """Clear matches with gravity (no skyfall, unknown orbs). Returns list of (color, group) over all cascades."""
    cells, out = list(cells), []
    while True:
        gs = _groups(cells)
        if not gs:
            return out
        out += gs
        for _, g in gs:
            for i in g:
                cells[i] = '.'
        for c in range(COLS):
            col = [cells[r * COLS + c] for r in range(ROWS) if cells[r * COLS + c] != '.']
            col = ['.'] * (ROWS - len(col)) + col
            for r in range(ROWS):
                cells[r * COLS + c] = col[r]


def evaluate(cells, goal):
    """Returns (goal_met, score)."""
    gs = resolve(cells)
    crosses = {}
    for color, g in gs:
        if is_cross(g):
            crosses[color] = crosses.get(color, 0) + 1
    avoided = sum(1 for color, _ in gs if color in goal.get('avoid', ()))
    need = goal.get('crosses', {})
    link = goal.get('link', {})
    biggest = {}
    for color, g in gs:
        biggest[color] = max(biggest.get(color, 0), len(g))
    met = (len(gs) >= goal.get('min_combos', 0)
           and all(biggest.get(k, 0) >= n for k, n in link.items())
           and all(crosses.get(k, 0) >= n for k, n in need.items())
           and avoided == 0
           and (len(gs) > 0))
    score = (len(gs) * 10 + sum(min(crosses.get(k, 0), n) for k, n in need.items()) * 100
             + sum(min(biggest.get(k, 0), n) for k, n in link.items()) * 30 - avoided * 1000)
    return met, score


def solve(board, goal, max_steps=25, beam=5000):
    """Shortest route meeting goal. Returns (start_rc, [rc, ...] path incl. start) or None.

    Depth-by-depth beam search: depths whose state count fits in the beam (~5 steps) are exhaustive,
    so short answers are truly shortest; deeper ones are best-effort.
    """
    cells = ''.join(board)
    assert len(cells) == ROWS * COLS, board
    states = [(cells, i, -1, (i,)) for i in range(ROWS * COLS) if cells[i] != '.']
    best = None
    for _ in range(max_steps):
        nxt = []
        for cur, pos, prev, path in states:
            r, c = divmod(pos, COLS)
            for dr, dc in DIRS:
                rr, cc = r + dr, c + dc
                if not (0 <= rr < ROWS and 0 <= cc < COLS):
                    continue
                k = rr * COLS + cc
                if k == prev:
                    continue
                l = list(cur)
                l[pos], l[k] = l[k], l[pos]
                s = ''.join(l)
                met, score = evaluate(s, goal)
                st = (s, k, pos, path + (k,))
                if met and (best is None or score > best[0]):
                    best = (score, st)
                nxt.append((score, st))
        if best:
            return [divmod(i, COLS) for i in best[1][3]]
        nxt.sort(key=lambda x: -x[0])
        states = [st for _, st in nxt[:beam]]
    return None


def apply_path(board, path):
    l = list(''.join(board))
    for (r1, c1), (r2, c2) in zip(path, path[1:]):
        a, b = r1 * COLS + c1, r2 * COLS + c2
        l[a], l[b] = l[b], l[a]
    return [''.join(l[r * COLS:(r + 1) * COLS]) for r in range(ROWS)]
