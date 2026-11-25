# Show the bot's board read and planned drag live
Labels: priority: medium, enhancement

**Why:** when a move looks wrong, there's no way to see what the bot read or what it planned.

**Scope:**
- A "Board" tab: the 5x6 board from the latest `turn` event, coloured by orb, with the route drawn
  (start and end marked).
- Turn number, goal and detected mechanics under it.
- `padbot watch` for the CLI (tails the newest log).
- Out: editing the board or replaying old runs.

**Done when:** during a run the Board tab updates every turn and matches the board on the phone.
