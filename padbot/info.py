"""Read-only lookup: what monster or dungeon is on screen, from public fan data (DadGuide, NA server).

The data is one SQLite file DadGuide publishes; `padbot info --update` downloads it to data/ (git-ignored).
Nothing here taps the phone or touches the game: it only reads screen text.
"""
import re
import sqlite3
import unicodedata
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "dadguide.sqlite"
URL = "https://d30r6ivozz8w2a.cloudfront.net/db/dadguide.sqlite"

# Mechanics worth calling out, matched in skill text (case-insensitive).
KEYWORDS = {
    "Bind": r"\bbind", "Unbind": r"unbind|bind recovery|recover.{0,20}bind", "Awoken bind": r"awoken.{0,10}(bind|invalid)",
    "Absorb": r"absorb", "Damage void": r"void|damage shield", "Unmatchable": r"unmatchable",
    "Jammer": r"jammer", "Poison": r"poison", "Bomb": r"\bbomb", "Skyfall": r"skyfall",
    "Lock": r"\block|unlock", "Cloud": r"cloud", "Tape": r"\btape|seal", "Blind": r"blind",
    "Gravity": r"gravity|% of (enemy|current) hp", "Delay": r"\bdelay", "Leader swap": r"leader swap|swap.{0,10}leader",
    "Orb change": r"\bchange.{0,30}orbs|create .{0,40}orbs|orbs? (to|into)", "Enhance orbs": r"enhance.{0,15}orbs",
    "Time extend": r"extend.{0,20}time|time.{0,10}extend|orb movement time", "Reduce damage": r"reduce damage|halves damage|damage taken",
    "Combos": r"combo", "True damage": r"true damage|fixed damage", "Counter": r"counter",
    "Heal": r"\brecover \d|\bheal", "Status shield": r"status shield|resistance",
}


def keywords(text):
    return [k for k, rx in KEYWORDS.items() if re.search(rx, text or "", re.I)]


def norm(s):
    """Fold accents, case and punctuation; OCR reads v as u in this font, so treat them as one letter."""
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower().replace("v", "u")
    return " ".join(re.sub(r"[^a-z0-9]+", " ", s).split())


def update(url=URL, dest=DB):
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(".part")
    with urllib.request.urlopen(url, timeout=60) as r, open(tmp, "wb") as f:
        while chunk := r.read(1 << 20):
            f.write(chunk)
    sqlite3.connect(tmp).execute("select count(*) from monsters_na").fetchone()  # fail before replacing a good copy
    tmp.replace(dest)


class Info:
    def __init__(self, path=DB):
        if not Path(path).exists():
            raise FileNotFoundError("No fan data yet. Download it first (padbot info --update).")
        self.db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        self.db.row_factory = sqlite3.Row
        q = self.db.execute
        # Names -> ids. Several cards can share a name; keep the newest NA one.
        self.monsters = {norm(r[0]): r[1] for r in q(
            "select name_en, monster_no_na from monsters_na where on_na=1 order by monster_no_na")}
        self.leaders = {norm(r[0]): r[1] for r in q(
            "select l.name_en, m.monster_no_na from monsters_na m join leader_skills_na l using(leader_skill_id) "
            "where m.on_na=1 and l.name_en!='' order by m.monster_no_na")}
        self.dungeons = {}  # several dungeons share a name (event re-runs): keep all ids
        for name, did in q("select name_en, dungeon_id from dungeons_na where name_en!='' order by dungeon_id"):
            self.dungeons.setdefault(norm(name), []).append(did)
        self.awoken = {r[0]: r[1] for r in q("select awoken_skill_id, name_en from awoken_skills")}
        self.updated = q("select max(tstamp) from monsters_na").fetchone()[0]

    def lookup(self, lines):
        """lines: OCR strings, top to bottom. Returns {'monster': {...} | None, 'dungeon': {...} | None}."""
        names = [norm(re.sub(r"^\W*leader skill\W*", "", l, flags=re.I)) for l in lines]
        names = [n for n in names if len(n) >= 4]
        by_name = next((self.monsters.get(n) or self.leaders.get(n) for n in names
                        if self.monsters.get(n) or self.leaders.get(n)), None)
        # The card number on a monster's detail screen ("No.13442" alone on its line) wins, unless OCR
        # misread a digit: then the name on screen disagrees and the name wins.
        nos = [int(m.group(1)) for l in lines if (m := re.fullmatch(r"\s*No\.\s*(\d{1,5})\s*", l))]
        no = nos[0] if nos and (by_name is None or by_name == nos[0] or norm(self.name(nos[0])) in names) else by_name
        mon = self.monster(no) if no else None
        found = [self.dungeon(did, names) for n in names for did in self.dungeons.get(n, [])]
        # Prefer the dungeon whose floor is on screen too and has enemy data, then the topmost on screen.
        dungeon = max(found, key=lambda d: (d["floor"] is not None, bool(d["floor"] and d["floor"]["enemies"])),
                      default=None)
        return {"monster": mon, "dungeon": dungeon}

    def text(self, s):
        s = re.sub(r"\{\{\s*awoskills\.id(\d+)[^}]*\}\}", lambda m: f"[{self.awoken.get(int(m.group(1)), '?')}]", s or "")
        return s

    def name(self, no):
        r = self.db.execute("select name_en from monsters_na where monster_no_na=? and on_na=1", (no,)).fetchone()
        return r[0] if r else ""

    def monster(self, no):
        q = self.db.execute
        m = q("select * from monsters_na where monster_no_na=? and on_na=1", (no,)).fetchone()
        if not m:
            return None
        ls = q("select * from leader_skills_na where leader_skill_id=?", (m["leader_skill_id"],)).fetchone()
        a = q("select * from active_skills_na where active_skill_id=?", (m["active_skill_id"],)).fetchone()
        awk = [self.awoken.get(r[0], "?") for r in q(
            "select awoken_skill_id from awakenings_na where monster_id=? and is_super=0 order by order_idx",
            (m["monster_id"],))]
        leader = {"name": ls["name_en"], "text": self.text(ls["desc_en"])} if ls else None
        active = {"name": a["name_en"], "text": self.text(a["desc_en"]),
                  "turns": [a["cooldown_turns_max"], a["cooldown_turns_min"]]} if a else None
        return {"no": no, "name": m["name_en"], "leader": leader, "active": active, "awakenings": awk,
                "keywords": keywords(" ".join(x["text"] for x in (leader, active) if x))}

    def dungeon(self, dungeon_id, names):
        q = self.db.execute
        d = q("select name_en from dungeons_na where dungeon_id=?", (dungeon_id,)).fetchone()
        floors = q("select * from sub_dungeons_na where dungeon_id=? order by sub_dungeon_id", (dungeon_id,)).fetchall()
        # A floor counts only inside its own dungeon, so a short floor name can't match a stray word elsewhere.
        f = next((f for n in names for f in floors if norm(f["name_en"]) == n), None)
        out = {"id": dungeon_id, "name": d["name_en"], "floors": [x["name_en"] for x in floors], "floor": None}
        if f:
            enemies = q("select m.name_en name, max(e.hp) hp, max(e.turns) turns from encounters e "
                        "join monsters_na m using(monster_id) where e.sub_dungeon_id=? "
                        "group by m.name_en order by min(e.stage), min(e.order_idx)", (f["sub_dungeon_id"],)).fetchall()
            out["floor"] = {"name": f["name_en"], "stamina": f["stamina"], "battles": f["floors"],
                            "mult": [f["hp_mult"], f["atk_mult"], f["def_mult"]], "reward": f["reward_na"] or "",
                            "enemies": [dict(e) for e in enemies]}
        return out
