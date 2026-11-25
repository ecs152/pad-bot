# pad-bot

Clears Puzzle & Dragons floors through the iPhone Mirroring window. It screenshots the window,
recognises the screen and the orb board, and sends mouse taps and drags. Nothing runs on the phone.

Automating the game breaks GungHo's terms of service (§5(o)). Use a spare account if you can.

## How it works
One loop (`padbot/run.py`) runs about twice a second:

1. **Look.** Screenshot the iPhone Mirroring window (`mac.py`, macOS `screencapture`).
2. **Classify.** Compare each of the 30 board cells to your own orb crops (`vision.py`). If the board
   reads cleanly, it's your turn. If the board is dimmed but the battle frame is there, it's
   animating, so wait. Anything else is a menu.
3. **Menus: navigator** (`nav.py`). Read the screen's text with macOS Vision (`ocr.py`) and decide
   the next tap: your dungeon/floor name (`--path`), or the first floor without a "Clear!" badge
   (`--uncleared`); then your "You" helper, Select, Enter, and the Completion Reward banner until
   the rewards screen leaves. Stop words ("Continue?", "Magic Stone", ...) halt immediately. The
   screen is re-read right before each tap, and a tap that doesn't change the screen halts too.
4. **Battle: team clearer** (`run.py` `battle_turn`, rules in `profiles/lugner.toml`). Look for
   enemy ability icons and fire their counter skill. If a counter isn't charged, stall with any
   match. Otherwise tap the first Lügner (slots 1, 2, 6) whose 3-turn cooldown is up; the bot
   tracks cooldowns and checks the board changed to know a skill fired.
5. **Battle: puzzle matcher** (`solver.py`). Search routes from 1 step upward and drag the shortest
   one that leaves a dark cross on the board, which keeps Lügner's cross if it's already there. If
   no cross is reachable within 15 steps, make any match. Matching follows PAD rules: 3+ in a line,
   touching same-colour groups merge, gravity cascades, no skyfall.

Every turn is logged to `logs/` as one JSON line. Tests in `tests/` cover the solver, the
navigator on real captures, and the loop's safety rules on synthetic frames.

## One-time setup

### 1. iPhone Mirroring
1. You need an iPhone on iOS 18 or later, signed in to the same Apple Account as this Mac, with
   two-factor authentication on.
2. Turn on Bluetooth and Wi-Fi on both devices. Keep the iPhone near the Mac, locked, and not
   sharing its connection through Personal Hotspot.
3. On the Mac, open **iPhone Mirroring** (in Applications) and follow the prompts. The iPhone asks
   you to confirm once.
4. Open Puzzle & Dragons in the mirrored window. Keep the window at its default size, because the
   reference images depend on it.

### 2. macOS permissions
The permissions belong to whichever app starts the bot. When Claude runs it, that's **Claude**.
When you run it yourself, it's **Terminal**.

In **System Settings → Privacy & Security**:
- **Screen & System Audio Recording:** turn on Claude (and Terminal if you run it yourself).
  Without it, captures come back blank and the bot stops with a message saying so.
- **Accessibility:** turn on the same app. This lets it send mouse clicks and drags.

Quit and reopen the app after changing these settings.

### 3. Orb skin
Reference orbs are captured from your own board. If your face-style skin turns out to be
unreliable, switching to the default skin fixes it.

## Commands
Run these from this folder. Nothing touches the phone without `--live`.

```bash
.venv/bin/python -m padbot shot floor_list            # save the window to shots/floor_list.png
.venv/bin/python -m padbot crop shots/x.png orbs D_plus X Y W H        # make a reference image
.venv/bin/python -m padbot board shots/battle.png     # read the board, draw the planned route
.venv/bin/python -m padbot testdrag 2 2 3 2 --live    # drag one orb (battle must be on screen)
.venv/bin/python -m padbot info --update              # download DadGuide fan data (NA, ~240 MB) to data/
.venv/bin/python -m padbot info                       # name the monster/dungeon on screen: skills, keywords, enemies
.venv/bin/python -m padbot run                        # dry run: recognise and plan, no clicks
.venv/bin/python -m padbot run --live --runs 3 --path "Aither Desert/Beyond the Desert"   # real run
.venv/bin/python -m unittest discover -s tests -t .   # self-tests, no phone
```

## Safety
- Outside battle the bot reads the screen's text and only taps your dungeon/floor names, your
  helper label, and the OK / Select / Enter / Completion Reward buttons. It re-reads the screen
  right before each tap and skips the tap if the screen changed.
- Text like "Continue?", "Magic Stone", "Purchase", "Revive" or "Recover stamina" stops it at once.
- Any image in `templates/stop/` (the Continue and Magic Stone dialogs) stops it immediately.
- It also stops on a screen it doesn't recognise for 10 seconds, a battle that stays busy, or a
  board it can't solve. Each stop sends a Mac notification and saves a screenshot to `logs/`.
- Moving the mouse to the top-left corner of the screen stops a live run.
- While it runs, it controls the Mac's mouse.

## Layout
- `config.toml`: board and portrait positions, thresholds, and the dungeon/floor to run (`[nav]`).
- `profiles/<team>.toml`: how a team plays: skills fired left to right with cooldowns, the default
  goal (keep or rebuild a dark cross), counters per enemy ability, and the stall match.
- `templates/`: reference images.
  - `screens/battle.png`: the battle screen's Menu button, so a dimmed board reads as "busy".
  - `icons/`: enemy ability icons for team profile rules. `stop/`: dialogs that halt the bot.
  - `orbs/`: `R B G L D H J P M`.
- `logs/`: one JSON line per turn, used to tune the profile.

## Mac app
`app/build.sh` builds `PAD Bot.app` and installs it in `/Applications` (`~/Applications` if that isn't writable) (Command Line Tools only, no
Xcode). It runs the same bot: pick uncleared floors or a dungeon/floor, the number of runs, and
whether it's a practice run, then Start. The menu bar icon shows status and has Stop. Grant Screen
Recording and Accessibility to **PAD Bot** (rebuilding resets them, since the app is signed locally).
Panels plug in through `app/Sources/Panels.swift`; the bot's event stream is in `docs/events.md`.
