# Bot architecture

The parts of the automation, what each does today, and what's missing. Issues are filed per gap.

| Part | Today | Gap |
|---|---|---|
| 1. Capture and input (`mac.py`) | Finds the iPhone Mirroring window, screenshots it, taps and drags; kill switch in the top-left corner | Doesn't notice a locked phone or a closed game (shows the wallpaper) |
| 2. Screen recognition (`nav.decide`) | An ordered list of OCR rules: title, notices, home, menu, lists, helper, enter, results | Rules are ad hoc and order-sensitive; screens have no saved fixtures, so a fix can break another screen |
| 3. Navigation loop (`run.py`) | Taps one step at a time, checks the screen changed, scrolls lists | No explicit states or transitions; stall timers are the only recovery |
| 4. Dungeon selection | Uncleared floors, a dungeon/floor path, a queue, a skip list | Always opens the top Stage tab; doesn't move on when a stage is fully cleared |
| 5. Team selection | Swipes the team carousel until the profile's leader skill shows | Starts by swiping back 10 times; doesn't remember which page the team is on |
| 6. Board reader and solver (`vision.py`, `solver.py`) | Reads the 6x5 board from orb templates; sparkle-tolerant; finds a cross or any match | No 7x6 or 5x4 boards; templates are tied to one orb skin |
| 7. Skill policy (`profile.py`, profiles) | One Lügner every turn when charged; counter skills per mechanic | In-battle mechanic icons aren't captured, so counters never fire (#12) |
| 8. Safety | Stop words, stall and no-change stops, kill switch, max runs | Stop dialogs are read by text only (#13) |
| 9. Recovery | Dismisses notices, falls back to the Dungeon tab | Can't restart the game or wait out a locked phone |
| 10. Logging | `logs/history.jsonl` per run, a screenshot at every stop, `@ev` events to the app | Stop screenshots aren't turned into test fixtures, so the same screen can fail again |
| 11. Data | DadGuide database; mechanics engine and Coverage tab | Live |
| 12. Mac app | Run, Queue, History, Teams, Coverage tabs; permissions popup | Live |

## Order
1. Screen fixtures and a screen registry (parts 2, 3, 10): every stop screenshot becomes a fixture with its expected screen, so each fix is tested against all known screens.
2. Dungeon selection across stage tabs (part 4).
3. Recovery from a locked phone or a closed game (parts 1, 9).
4. Board sizes and orb skins (part 6).
5. Mechanic icons and image-based stop dialogs (#12, #13).
6. Team page memory (part 5).
