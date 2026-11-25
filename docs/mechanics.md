# Enemy mechanics and their counters

This file backs `padbot/mechanics.py`. The engine reads enemy skills from DadGuide's NA data to find
which mechanics a dungeon uses. It checks each team card's active skill and awakenings against the
counters listed here.

`padbot coverage --dungeon NAME` and the app's Coverage tab show the result in one of four statuses:
- **full:** an active, or enough resists, covers it.
- **partial:** some resist is there, but not enough.
- **gap:** a counter exists but the team has none.
- **manage:** no skill counters it, so the team has to play around it.

## How detection works
- **Dungeon side:** `encounters` → `enemy_data_na.behavior` (a protobuf with the
  [pad-data-pipeline schema](https://github.com/TsubakiBotPad/pad-data-pipeline/blob/master/proto/enemy_skills.proto))
  → enemy skill ids → `enemy_skills_na.desc_en` → the regexes in `CATALOGUE`. Skills in a PREEMPT group are
  marked "pre-emptive".
- **Team side:** profile slot names → DadGuide cards (text in brackets is ignored) → active skill text and
  awakening names. A slot whose name isn't a real card name is reported, not guessed.
- **Wording:** the regexes match DadGuide's generated English, not the in-game NA text. The local
  DadGuide file (downloaded by the Info tab) is current and includes 2024+ effects such as
  "pierce damage void" and damage caps.

## Catalogue (key: what it does; counters; timing)
Timing is either:
- **Pre-emptive:** it must be on the team or ready before the floor.
- **Reactive:** use it when the mechanic appears.

### Shields
- **damage_absorb:** a hit at or above a threshold heals the enemy.
  - Counters: the active "bypass damage absorb", hitting under the threshold, or the Damage Absorption Piercer latent.
  - Timing: reactive.
- **attribute_absorb:** damage of the listed colours heals the enemy.
  - Counters: the active "bypass att. absorb", or don't attack with those colours.
  - The Att. Absorption Piercer latent needs either 2+ or 3+ attributes; sources conflict.
  - Timing: reactive.
- **combo_absorb:** making N or fewer combos heals the enemy.
  - Counters: make more combos, the active "bypass combo absorb", add-combo actives or leader skills, or the Create Combo Orbs awakening.
  - Timing: reactive.
- **damage_void:** a hit at or above a threshold deals 0.
  - Counters: the active "bypass void damage", the Damage Void Piercer(+) awakening (only a 3x3 box match pierces), or the VDP latent.
  - Timing: actives are reactive; awakenings and latents are team building.
- **resolve:** the enemy survives a lethal hit while above X% HP. Super resolve cancels damage from above X% to below Y%.
  - Counters: a second hit (Bonus Attack, multi-hit), chipping its HP first, or damage-cap actives.
- **damage_immunity:** the enemy takes no damage until other enemies die.
- **status_void:** delays, poison and DEF-down don't land.
- **buff_dispel:** removes the team's buffs.

### Binds
- **bind:** the bound card's stats, awakenings and active are off.
  - Counters: Resistance-Bind (50%) or Resistance-Bind+ (100%) on each card, Recover Bind(+) on a heart row, or actives that "remove all binds" / "reduce binds".
  - Timing: resists are pre-emptive.
- **awoken_bind:** all awakenings are off.
  - Counters: actives that clear awoken skill binds. No resist exists.
  - Timing: reactive, but the active must be charged.
- **skill_bind:** actives can't be used.
  - Counters: Resistance-Skill Bind, 20% each, added up across the team.
  - Timing: pre-emptive.
- **assist_void:** assists are off, or actives are disabled.
  - Counters: the Assist Void Resistance awakening.
- **skill_delay:** adds turns to cooldowns.
  - Counters: Skill Delay Resistance (awakening or latent), or a spare charge.
- **leader_swap:** the leader is swapped with a sub.
  - Counters: the Leader Change Resist latent, or wait it out.

### Board
- **locks:**
  - Counters: the active "unlock all orbs", or L-shape matches with the [L] Increased Attack awakening.
- **clouds:**
  - Counters: Resistance-Clouds.
- **tape** (sealed row/column):
  - Counters: Resistance-Immobility.
- **unmatchable:** a colour can't be matched.
  - Counters: recovery actives, or the Unmatchable Orb Recovery latent.
- **roulette:** orbs keep changing during the move.
  - Counters: the Roulette Orb Recovery latent, or avoid those orbs.
- **blind:** blinded orbs are hidden.
  - Counters: Resistance-Blind (20%) or Resistance-Blind+ (100%).
  - Sticky and super blind: Cross Attack(+) recovers super blind. Whether resists apply to them is unconfirmed.
- **poison / jammer / bomb:** spawned orbs.
  - Counters: Resistance-Poison(+) and Resistance-Jammers(+) (20% / 100% each), or Surge Resist latents.
- **barbed:** touching these orbs during a move hurts.
  - Counters: route around them (the solver must avoid them).
- **fixed_start:** the move must start from a fixed cell (the solver must start there).
- **no_skyfall:** no new orbs fall.
- **board_size:** the board changes to 5x4 or 7x6.
- **combo_negate:** some of your combos don't count.

### Player debuffs
- **move_time:** less time to move orbs.
  - Counters: Move Time Change Resist, or move-time actives.
- **Not tracked:** gravity, ATK/RCV debuffs and HP changes. They are damage to survive, not counters to bring.

### Dungeon-wide (not detected per enemy)
Super Gravity (counter: Levitation), Super Altitude, Incalescence, Viridescence, Riptide, and dungeon-wide
Awoken Bind, Leader Skill Invalid or Assist Void.

## Sources
- DadGuide / Tsubaki pipeline: https://github.com/TsubakiBotPad/pad-data-pipeline (enemy and active skill text
  templates, behaviour proto).
- Sanbon (team builder): https://sanbon.me/na. Its awakening and latent pages and its skill filter labels
  ("AS - Void Damage Absorb", "AS - Pierce Damage Void", "AS - Awoken Bind Recovery", ...) were used as a
  cross-check. Sanbon has no API or export, and its robots.txt disallows crawling, so it is **not** used as a
  data source.
- Official guide to recent mechanics (shields, barbed orbs, part break):
  https://www.puzzleanddragons.us/single-post/perfect-for-returning-new-players-a-guide-to-recent-major-updates-2602
- Latent glossary: https://pad.protic.site/glossary/latent/
- Damage Void Piercer latent: https://laggygaming.com/puzzles-and-dragons/latents/damage-void-piercer/

## Open questions
- **VDP multiplier:** sources give 3.5x and 2.5x.
- **Att. Absorption Piercer:** sources say it needs 2+ or 3+ attributes.
- **Super blind:** how it works exactly.
- **Recover Bind and awoken bind:** whether Recover Bind clears awoken bind.
- **Wording:** the in-game NA text for each counter. The engine relies on DadGuide's text, so this only matters for reading the screen.
