"""Mechanics engine: which enemy mechanics a dungeon uses, which of them a team counters, and how.

Detection and counters are regexes over DadGuide NA text (enemy skill text, active skill text) plus
awakening names, so they follow the game's own wording. The catalogue and its sources are in
docs/mechanics.md. Keys match team-profile rules ([on.<key>]) and enemy icon templates.
"""
import re

# key: (label, enemy-skill regex, counters, how to deal with it when no skill covers it)
# counters: ("active", regex on active skill text) | ("awakening", name, share) where share is how much
# one awakening covers (1.0 = fully on its own, 0.2 = five needed); per-card resists use "card".
CATALOGUE = {
    "awoken_bind": ("Awoken bind", r"bind awoken skills",
                    [("active", r"awoken skill binds")], "Clear it with an active; nothing resists it."),
    "bind": ("Bind", r"\bbind \d+(~\d+)? random (cards?|subs?)|bind (the )?(leader|helper|subs)",
             [("active", r"remove all binds|reduce binds"), ("awakening", "Resistance-Bind+", "card"),
              ("awakening", "Resistance-Bind", "card"), ("awakening", "Recover Bind", "card"),
              ("awakening", "Recover Bind+", "card")], "Bind resists per card, or an active that clears binds."),
    "skill_bind": ("Skill bind", r"bind active skills",
                   [("awakening", "Resistance-Skill Bind", "card")], "Skill bind resist awakenings."),
    "skill_delay": ("Skill delay", r"delay active skills",
                    [("awakening", "Skill Delay Resist", "card")], "Skill delay resist, or spare cooldown."),
    "damage_void": ("Damage void", r"void damage >=",
                    [("active", r"bypass void damage"), ("awakening", "Damage Void Piercer", "partial"),
                     ("awakening", "Damage Void Piercer+", "partial")],
                    "A void-pierce active, or Damage Void Piercer with a 3x3 box match."),
    "damage_absorb": ("Damage absorb", r"absorb damage when damage >=",
                      [("active", r"bypass (att\. absorb and )?damage absorb")],
                      "A damage-absorb void active, or hit for less than the threshold."),
    "attribute_absorb": ("Attribute absorb", r"absorb (fire|water|wood|light|dark)\b[^;]*?damage",
                         [("active", r"bypass att\. absorb")],
                         "An attribute-absorb void active, or don't attack with that colour."),
    "combo_absorb": ("Combo absorb", r"absorb damage when combos? <=",
                     [("active", r"bypass combo absorb")], "A combo-absorb void active, or make more combos."),
    "locks": ("Locked orbs", r"\block (all|\d+)|locked\b",
              [("active", r"unlock all orbs")], "An unlock active; locked orbs can still be matched."),
    "blind": ("Blind", r"\bblind (all|random|orbs)",
              [("awakening", "Resistance-Blind+", 1.0), ("awakening", "Resistance-Blind", 0.2)],
              "Blind resist (100% team total)."),
    "clouds": ("Clouds", r"clouds? appears?|\bclouds\b",
               [("awakening", "Resistance-Clouds", 1.0)], "One cloud-resist awakening."),
    "tape": ("Tape (sealed row/column)", r"\bseal the",
             [("awakening", "Resistance-Immobility", 1.0)], "One tape-resist awakening."),
    "unmatchable": ("Unmatchable orbs", r"unable to match", [],
                    "Match other colours, or change the unmatchable orbs away."),
    "poison": ("Poison orbs", r"poison orbs?",
               [("awakening", "Resistance-Poison+", 1.0), ("awakening", "Resistance-Poison", 0.2)],
               "Poison resist (100% team total), or don't match them."),
    "jammer": ("Jammer orbs", r"jammer orbs?",
               [("awakening", "Resistance-Jammers+", 1.0), ("awakening", "Resistance-Jammers", 0.2)],
               "Jammer resist (100% team total)."),
    "bomb": ("Bomb orbs", r"bomb orbs?", [], "Match or change them before they go off."),
    "roulette": ("Roulette / spinners", r"orbs change every", [], "Avoid or change those orbs."),
    "fixed_start": ("Fixed starting orb", r"fix orb movement starting point", [],
                    "Plan the move from that cell (the bot's solver must start there)."),
    "move_time": ("Move-time debuff", r"movetime",
                  [("awakening", "Move Time Change Resist", "card"), ("active", r"orb move time")],
                  "Short moves; the bot's one-step drags rarely care."),
    "leader_swap": ("Leader swap", r"leader changes to", [], "Wait it out; the leader skill changes meanwhile."),
    "no_skyfall": ("No skyfall", r"no skyfall", [], "Plan without new orbs."),
    "combo_negate": ("Combo reduction", r"negate \d+ combos?", [], "Make extra combos."),
    "resolve": ("Resolve / damage cut-off", r"survive attacks with|is nullified",
                [("active", r"set damage cap")], "Two hits, true damage, or a higher damage cap."),
    "status_void": ("Status shield", r"voids status ailments", [],
                    "Delays, poison and debuffs from the team don't land."),
}


def detect(text):
    """Mechanic keys an enemy skill's text describes."""
    return [k for k, (_, rx, _, _) in CATALOGUE.items() if re.search(rx, text or "", re.I)]


def counters(active_text, awakenings):
    """{key: [(how, detail, share)]} that one card provides: its active skill and awakenings."""
    out = {}
    for k, (_, _, cs, _) in CATALOGUE.items():
        for c in cs:
            if c[0] == "active" and re.search(c[1], active_text or "", re.I):
                out.setdefault(k, []).append(("active", re.search(c[1], active_text, re.I)[0], 1.0))
            elif c[0] == "awakening":
                n = sum(a == c[1] for a in awakenings)
                if n:
                    out.setdefault(k, []).append(("awakening", f"{c[1]} x{n}", c[2] if isinstance(c[2], str) else c[2] * n))
    return out


def team(cards):
    """cards: [(slot, name, active_text, awakenings)]. Returns {key: {"level": full|partial, "by": [...]}}.
    Actives cover fully; team-total resists need 100%; per-card resists and VDP count as partial."""
    cov = {}
    for slot, name, act, awk in cards:
        for k, items in counters(act, awk).items():
            cov.setdefault(k, []).extend({"slot": slot, "name": name, "how": h, "detail": d, "share": s}
                                         for h, d, s in items)
    out = {}
    for k, by in cov.items():
        total = sum(b["share"] for b in by if isinstance(b["share"], float))
        full = any(b["how"] == "active" for b in by) or total >= 1.0 - 1e-9
        out[k] = {"level": "full" if full else "partial", "by": by}
    return out


def report(team_cov, dungeon_mech):
    """dungeon_mech: {key: [{"enemy", "skill", "preempt"}]}. Splits into covered / partial / gaps."""
    rows = []
    for k, seen in dungeon_mech.items():
        label, _, cs, how = CATALOGUE[k]
        c = team_cov.get(k)
        status = c["level"] if c else ("gap" if cs else "manage")
        rows.append({"key": k, "label": label, "status": status, "by": c["by"] if c else [], "how": how,
                     "preempt": any(s["preempt"] for s in seen), "seen": seen[:5]})
    order = {"gap": 0, "partial": 1, "manage": 2, "full": 3}
    return sorted(rows, key=lambda r: (order[r["status"]], not r["preempt"], r["label"]))


def rules(team_cov):
    """Suggested profile rules: [on.<key>] skills = slots whose active counters it."""
    return {k: sorted({b["slot"] for b in v["by"] if b["how"] == "active"})
            for k, v in team_cov.items() if any(b["how"] == "active" for b in v["by"])}


# --- DadGuide enemy behaviour (protobuf, schema: TsubakiBotPad/pad-data-pipeline proto/enemy_skills.proto) ---
def _fields(buf):
    i = 0
    while i < len(buf):
        key, i = _varint(buf, i)
        f, wt = key >> 3, key & 7
        if wt == 0:
            v, i = _varint(buf, i)
        elif wt == 2:
            n, i = _varint(buf, i)
            v, i = buf[i:i + n], i + n
        elif wt == 5:
            v, i = buf[i:i + 4], i + 4
        elif wt == 1:
            v, i = buf[i:i + 8], i + 8
        else:
            raise ValueError(f"wire type {wt}")
        yield f, v


def _varint(buf, i):
    out = shift = 0
    while True:
        b = buf[i]
        out |= (b & 0x7F) << shift
        i, shift = i + 1, shift + 7
        if b < 0x80:
            return out, i


def skill_ids(blob):
    """[(enemy_skill_id, preempt)] in a MonsterBehavior blob, all levels."""
    out = []

    def group(buf, preempt=False):
        gtype = next((v for f, v in _fields(buf) if f == 1), 0)
        for f, v in _fields(buf):
            if f == 3:  # BehaviorItem
                for f2, v2 in _fields(v):
                    if f2 == 2:
                        group(v2, preempt or gtype == 2)
                    elif f2 == 3:  # Behavior: enemy_skill_id = 2
                        sid = next((x for f3, x in _fields(v2) if f3 == 2), None)
                        if sid and sid < 2 ** 31:
                            out.append((sid, preempt or gtype == 2))

    for f, v in _fields(bytes(blob)):
        if f == 2:  # LevelBehavior
            for f2, v2 in _fields(v):
                if f2 == 2:
                    group(v2)
    return out


# --- glue to the fan data (padbot.info.Info) ---
def team_cards(info, profile):
    """Profile slot names -> DadGuide cards. Text in brackets is ignored ("Lügner (leader)" -> Lügner).
    Returns (cards, unknown slot names)."""
    from .info import norm
    cards, unknown = [], []
    for slot, name in sorted(profile.get("slots", {}).items()):
        no = info.monsters.get(norm(re.sub(r"\(.*?\)", "", name)))
        m = info.monster(no) if no else None
        if not m:
            unknown.append(f"{slot}: {name}")
            continue
        cards.append((int(slot), m["name"], (m["active"] or {}).get("text", ""), m["awakenings"]))
    return cards, unknown


def dungeon(info, name, floor=None):
    """{key: [{"enemy", "skill", "preempt"}]} for a dungeon (newest one with that name), optionally one floor."""
    from .info import norm
    ids = info.dungeons.get(norm(name))
    if not ids:
        return None
    q = info.db.execute
    subs = [r["sub_dungeon_id"] for r in q("select sub_dungeon_id, name_en from sub_dungeons_na where dungeon_id=?",
                                           (ids[-1],)) if floor is None or norm(r["name_en"]) == norm(floor)]
    found = {}
    rows = q(f"select distinct m.name_en, d.behavior from encounters e join enemy_data_na d using(enemy_id) "
             f"join monsters_na m on m.monster_id = e.monster_id "
             f"where e.sub_dungeon_id in ({','.join('?' * len(subs))})", subs).fetchall() if subs else []
    for enemy, blob in rows:
        try:
            ids_ = skill_ids(blob)
        except (ValueError, IndexError):  # a malformed blob loses that enemy's mechanics, not the dungeon
            continue
        for sid, pre in ids_:
            s = q("select name_en, desc_en from enemy_skills_na where enemy_skill_id=?", (sid,)).fetchone()
            for k in detect(s["desc_en"]) if s else []:
                hit = {"enemy": enemy, "skill": s["name_en"], "preempt": pre}
                if hit not in found.setdefault(k, []):
                    found[k].append(hit)
    return found
