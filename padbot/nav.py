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


def stop_word(lines, extra=()):
    """First stop word on screen. `extra` adds the user's own words (app Safety settings)."""
    text = " ".join(norm(t) + ("?" if t.strip().endswith("?") else "") for t, _, _ in lines)
    return next((w for w in STOP_WORDS + tuple(extra) if norm(w) + ("?" if w.endswith("?") else "") in text), None)


def title_start(lines):
    """START's box on the game's title screen, else None. Needs START plus the title screen's own text."""
    start = find(lines, "START", exact=True)
    if start and (find(lines, "GungHo Online") or (find(lines, "Data", exact=True) and find(lines, "Recou"))):
        return start
    return None


def banner_free(lines):
    """Lines minus the title screen's ad banner (below START), which advertises Magic Stone deals.
    Other screens are returned unchanged, so stop words still apply everywhere else."""
    start = title_start(lines)
    return [l for l in lines if l[2][1] <= start[1]] if start else lines


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


def back(lines):
    """Tap Back; if it can't be read, call the screen unknown (never ("list", None) — that would scroll)."""
    box = find(lines, "Back", exact=True)
    return ("list", "Back", box) if box else ("unknown", None, None)


def decide(lines, path, helper, height, new_only=False, skip=()):
    """Returns (kind, label, box) for the next tap, or (kind, None, None) if nothing to tap.
    skip: dungeon names uncleared mode never enters (and backs out of).
    kind: title | results | tips | helper_popup | helper | enter | list | unknown
    ("list", None, None) = a list screen whose visible part lacks the target."""
    has = lambda label, exact=False: find(lines, label, exact)
    if title_start(lines):
        return "title", "START", title_start(lines)
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
        floors = [t for t, _, _ in lines if CODE.match(t.strip()) and t.count("-") == 2]
        if floors and any(find(lines, name) for name in skip):  # inside a skipped dungeon: leave it
            return back(lines)
        todo = [e for e in uncleared(lines) if not any(find([(e[1], 1, e[2])], name) for name in skip)]
        if todo:
            code, title, box = todo[0]
            return "list", title, box
        if floors:  # a floor list with every floor cleared: back out to the dungeon list
            return back(lines)
        if find(lines, "Back", exact=True) and any(CODE.match(t.strip()) for t, _, _ in lines):
            return "list", None, None  # dungeon list, nothing uncleared in view: scroll
        return "unknown", None, None
    title = [l for l in lines if 0.2 * height < l[2][1] < 0.27 * height and norm(l[0]) != "back"]
    floor_codes = any(CODE.match(t.strip()) and t.count("-") == 2 for t, _, _ in lines)
    if len(path) > 1 and title and floor_codes and has("Back", exact=True) and not find(title, path[0]):
        return back(lines)  # another dungeon's floor list (a queue moved on): back out to the dungeon list
    for label in reversed(path):  # deepest name first: on a floor list the floor beats the dungeon header
        box = find(lines, label, min_y=0.27 * height)  # skip the title bar, which repeats the dungeon name
        if box:
            return "list", label, box
    if find(lines, "Back", exact=True) and find(lines, "Battles", exact=True):
        return "list", None, None  # a floor list without our target on it yet: scroll
    if find(lines, "Back", exact=True) and any(CODE.match(t.strip()) and t.count("-") == 1 for t, _, _ in lines):
        return "list", None, None  # dungeon list ("4-6" codes) without our dungeon in view: scroll
    # shortcut: lists only scroll down, so a dungeon above the visible part is never found; add scroll-up if that bites
    return "unknown", None, None
