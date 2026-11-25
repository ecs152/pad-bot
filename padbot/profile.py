import json
import os
import sys
import tomllib
from pathlib import Path


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


# --- editing (the app's Teams tab talks to this as JSON: python -m padbot.profile show|save PATH) ---
COLOURS = set("RBGLDH")
SLOTS = range(1, 7)
GOAL_KEYS = {"crosses", "link", "min_combos", "avoid"}


def _is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _check_slots(v, where, errs):
    if not isinstance(v, list) or not all(_is_int(s) and s in SLOTS for s in v):
        errs.append(f"{where}: slots must be numbers 1-6")
    elif len(set(v)) != len(v):
        errs.append(f"{where}: a slot is listed twice")


def _check_goal(g, where, errs):
    if not isinstance(g, dict):
        return errs.append(f"{where}: must be a table")
    for k in set(g) - GOAL_KEYS:
        errs.append(f"{where}: unknown key '{k}'")
    for k in ("crosses", "link"):
        for c, n in g.get(k, {}).items():
            if c not in COLOURS or not _is_int(n) or n < 1:
                errs.append(f"{where}.{k}: need an orb (R B G L D H) and a count of 1 or more")
    if "min_combos" in g and not (_is_int(g["min_combos"]) and 0 <= g["min_combos"] <= 10):
        errs.append(f"{where}.min_combos: must be 0-10")
    if not set(g.get("avoid", [])) <= COLOURS:
        errs.append(f"{where}.avoid: orbs must be R B G L D H")
    if set(g.get("avoid", [])) & (set(g.get("crosses", {})) | set(g.get("link", {}))):
        errs.append(f"{where}: an orb can't be both wanted and avoided")


def validate(p):
    """Problems that would make the bot misbehave, as readable strings. Empty list = OK to save."""
    errs = []
    for k in set(p) - {"name", "notes", "max_steps", "leader_skill", "slots", "default", "cooldowns", "on"}:
        errs.append(f"unknown setting '{k}'")
    if not str(p.get("name", "")).strip():
        errs.append("name: required")
    if not (_is_int(p.get("max_steps", 12)) and 1 <= p.get("max_steps", 12) <= 30):
        errs.append("max_steps: must be 1-30")
    for s, n in p.get("slots", {}).items():
        if s not in {str(i) for i in SLOTS} or not isinstance(n, str):
            errs.append(f"slots: '{s}' must be a slot 1-6 with a name")
    d = p.get("default", {})
    for k in set(d) - {"first_of", "skills", "goal", "fallback_goal"}:
        errs.append(f"default: unknown key '{k}'")
    for k in ("first_of", "skills"):
        _check_slots(d.get(k, []), f"default.{k}", errs)
    for k in ("goal", "fallback_goal"):
        if k in d:
            _check_goal(d[k], f"default.{k}", errs)
    for s, n in p.get("cooldowns", {}).items():
        if s not in {str(i) for i in SLOTS} or not _is_int(n) or not 1 <= n <= 99:
            errs.append(f"cooldowns: slot {s} needs a whole number of turns, 1-99")
    for name, rule in p.get("on", {}).items():
        if not name.replace("_", "").isalnum() or not name.islower():
            errs.append(f"on.{name}: ability names are lowercase letters, digits and _")
        for k in set(rule) - {"skills", "first_of", "goal"}:
            errs.append(f"on.{name}: unknown key '{k}'")
        for k in ("skills", "first_of"):
            if k in rule:
                _check_slots(rule[k], f"on.{name}.{k}", errs)
        if "goal" in rule:
            _check_goal(rule["goal"], f"on.{name}.goal", errs)
    return errs


def _key(k):
    return k if k.replace("_", "").replace("-", "").isalnum() and k.isascii() else json.dumps(k, ensure_ascii=False)


def _val(v):
    if isinstance(v, dict):
        return "{ " + ", ".join(f"{_key(k)} = {_val(x)}" for k, x in v.items()) + " }" if v else "{}"
    if isinstance(v, list):
        return "[" + ", ".join(_val(x) for x in v) + "]"
    if isinstance(v, bool):
        return str(v).lower()
    return json.dumps(v, ensure_ascii=False) if isinstance(v, str) else str(v)


def dumps(p):
    """TOML for a validated profile. Comments aren't kept: put notes in `notes` and slot names in [slots]."""
    out = [f"{_key(k)} = {_val(p[k])}" for k in ("name", "notes", "max_steps", "leader_skill") if k in p]
    for t in ("slots", "default", "cooldowns"):
        if t in p:
            out += ["", f"[{t}]"] + [f"{json.dumps(k) if t != 'default' else k} = {_val(v)}" for k, v in p[t].items()]
    for name, rule in p.get("on", {}).items():
        out += ["", f"[on.{name}]"] + [f"{k} = {_val(v)}" for k, v in rule.items()]
    return "\n".join(out) + "\n"


def save(path, p):
    """Validate, then write atomically. Returns the list of problems (nothing written if any)."""
    errs = validate(p)
    if not errs:
        if tomllib.loads(dumps(p)) != p:
            return ["internal: profile didn't survive a save round trip; nothing written"]
        tmp = Path(path).with_suffix(".toml.tmp")
        tmp.write_text(dumps(p), encoding="utf-8")
        os.replace(tmp, path)
    return errs


if __name__ == "__main__":
    cmd, path = sys.argv[1], sys.argv[2]
    try:
        if cmd == "show":
            p = load(path)
            print(json.dumps({"profile": p, "errors": validate(p)}, ensure_ascii=False))
        elif cmd == "save":
            errs = save(path, json.load(sys.stdin))
            print(json.dumps({"errors": errs}, ensure_ascii=False))
    except (OSError, ValueError) as e:  # ValueError covers TOML and JSON decode errors
        print(json.dumps({"errors": [str(e)]}))
