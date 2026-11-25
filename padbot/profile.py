import tomllib


def load(path):
    with open(path, "rb") as f:
        return tomllib.load(f)


def plan(profile, mechanics):
    """Merge [default] with [on.<mechanic>] rules in detection order. Returns (skills, first_of, goal)."""
    d = profile.get("default", {})
    skills, goal = list(d.get("skills", [])), dict(d.get("goal", {}))
    first_of = list(d.get("first_of", []))
    for m in mechanics:
        rule = profile.get("on", {}).get(m)
        if not rule:
            continue
        skills += [s for s in rule.get("skills", []) if s not in skills]
        first_of = rule.get("first_of", first_of)
        g = rule.get("goal")
        if g:
            avoid = set(goal.get("avoid", [])) | set(g.get("avoid", []))
            goal = dict(g)  # a mechanic's goal replaces the default shape...
            if avoid:
                goal["avoid"] = sorted(avoid)  # ...but avoided colours always accumulate
    return skills, first_of, goal
