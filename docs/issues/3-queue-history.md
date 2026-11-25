# Farm a queue of dungeons and keep a run history
Labels: priority: medium, enhancement

**Why:** the bot runs one dungeon or "uncleared" mode per start, and nothing records what happened.

**Scope:**
- Queue tab: an ordered list of dungeon/floor entries with runs each and an "uncleared first" toggle;
  the bot works through it in order.
- Stamina shown when the game displays it (read from screen).
- History tab: each run's dungeon, clear time, turns, and why it stopped, kept across app restarts.
- Out: drop tracking (needs reward-screen reading; separate issue if wanted).

**Done when:** a queue of two dungeons runs end to end without input, and both runs appear in History
after relaunching the app.
