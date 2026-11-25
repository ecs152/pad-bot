# Mac app: window, Start/Stop, menu bar and safety settings
Labels: priority: high, enhancement

**Why:** the bot runs only from Terminal. A double-click app makes it usable, and gives the other panels a home.

**Scope:**
- `PAD Bot.app` (SwiftUI, built by `app/build.sh` with the Command Line Tools) that runs the existing bot.
- Run tab: uncleared floors or a dungeon/floor, runs count, practice run (default on), Start/Stop, status line, log.
- Event stream from the bot (`@ev` lines, docs/events.md) and a panel registry for other tracks.
- Menu bar icon with status, Stop, Open and Quit.
- Safety tab: always-on stone lock, extra stop words, max runs, alert when it stops.
- Out: board view, queue, history, team editing, companion data (their own issues).

**Done when:**
- The app opens from ~/Applications, runs a practice run and a live run, and Stop halts the bot at once.
- Other tracks can add a tab with one new file and one line in `Panels.swift`.
