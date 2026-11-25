"""Dungeon navigator: reads on-screen text (macOS Vision) and decides what to tap outside battle.

Taps only text from an allowlist: the dungeon/floor names you give it, your helper's label, and a few
fixed buttons. Any screen showing a stop word halts the bot.
"""
import difflib
import re

STOP_WORDS = ("magic stone", "continue?", "purchase", "revive", "recover stamina", "not enough stamina",
              "insufficient")


def norm(s):
    # the game font reads "v" as "u" ("halues", "Uoids"), so fold them together everywhere
    return re.sub(r"[^a-z0-9 ]", "", s.lower()).replace("v", "u").strip()


def find(lines, label, exact=False, min_y=0):
    """Best OCR line matching label (fuzzy, OCR misreads letters). Returns its box or None."""
    want, best = norm(label), (0.0, None)
    for text, _, box in lines:
        if box[1] < min_y:
            continue
        t = norm(text)
        if exact:
            score = 1.0 if t == want else 0.0
        else:
            score = max(difflib.SequenceMatcher(None, want, t).ratio(),
                        1.0 if len(want) > 5 and want in t else 0.0)
        if score > best[0]:
            best = (score, box)
    return best[1] if best[0] >= 0.8 else None


def stop_word(lines):
    text = " ".join(norm(t) + ("?" if t.strip().endswith("?") else "") for t, _, _ in lines)
    return next((w for w in STOP_WORDS if norm(w) + ("?" if w.endswith("?") else "") in text), None)


CODE = re.compile(r"^\d+-\d+(-\d+)?$")  # "4-6" is a dungeon, "4-6-5" a floor


def uncleared(lines):
    """List entries (code, title, box) whose code has no "Clear!" badge on its row, top to bottom."""
    out = []
    for t, _, (x, y, w, h) in lines:
        code = t.strip()
        if not CODE.match(code):
            continue
        if any(norm(o) == "clear" and abs(b[1] - y) < 15 for o, _, b in lines):
            continue
        below = [(b[1], o, b) for o, _, b in lines
                 if y + 15 < b[1] < y + 70 and abs(b[0] - x) < 25 and norm(o) not in ("new", "clear")]
        if below:
            _, title, box = min(below)
            out.append((code, title, box))
    return out


def decide(lines, path, helper, height, new_only=False):
    """Returns (kind, label, box) for the next tap, or (kind, None, None) if nothing to tap.
    kind: results | tips | helper_popup | helper | enter | list | unknown
    ("list", None, None) = a list screen whose visible part lacks the target."""
    has = lambda label, exact=False: find(lines, label, exact)
    if has("Completion Reward"):
        return "results", "Completion Reward", has("Completion Reward")
    if has("TIPS", exact=True) and has("OK", exact=True):
        return "tips", "OK", has("OK", exact=True)
    if has("Select a Helper"):
        if has("Check Info") and has("Select", exact=True):
            return "helper_popup", "Select", has("Select", exact=True)
        return "helper", helper, has(helper, exact=True)
    if has("Enter Dungeon"):
        return "enter", "Enter", has("Enter", exact=True)
    if new_only:
        todo = uncleared(lines)
        if todo:
            code, title, box = todo[0]
            return "list", title, box
        floors = [t for t, _, _ in lines if CODE.match(t.strip()) and t.count("-") == 2]
        if floors:  # a floor list with every floor cleared: back out to the dungeon list
            return "list", "Back", find(lines, "Back", exact=True)
        if find(lines, "Back", exact=True) and any(CODE.match(t.strip()) for t, _, _ in lines):
            return "list", None, None  # dungeon list, nothing uncleared in view: scroll
        return "unknown", None, None
    for label in reversed(path):  # deepest name first: on a floor list the floor beats the dungeon header
        box = find(lines, label, min_y=0.27 * height)  # skip the title bar, which repeats the dungeon name
        if box:
            return "list", label, box
    if find(lines, "Back", exact=True) and find(lines, "Battles", exact=True):
        return "list", None, None  # a floor list without our target on it yet: scroll
    # shortcut: only floor lists (they show "Battles") scroll; teach dungeon-list markers when we see one
    return "unknown", None, None
