# Bot events (app contract)

`python -u -m padbot run ...` prints one line per event to stdout:

```
@ev {"type": "turn", "t": 1795577912.2, "turn": 2, "board": ["RBGRBG", ...], "route": [[2, 2], [3, 2]], ...}
```

The Mac app (`app/Sources/BotRunner.swift`) parses these into `BotRunner.events` and shows every
other line in the log. Emit new events with `padbot.events.emit(type, **fields)` and list them here.

| type | fields | when |
|---|---|---|
| `start` | `live`, `runs`, `path` (list), `uncleared` | before the loop starts |
| `screen` | `name`: battle_ready, battle_busy, list, helper, helper_popup, enter, tips, results, unknown | every loop pass |
| `skill` | `slot` (1-6), `fired`, `turn` | after each skill tap |
| `turn` | `turn`, `board` (5 strings of 6 orbs: R B G L D H, `.` unknown), `route` (list of [row, col]), `goal`, `mechanics` | right after each drag (same dict as `logs/run-*.jsonl`) |
| `cleared` | `count`, `runs` | when a rewards screen is left |
| `done` | `cleared` | runs reached |
| `stop` | `reason` | any stop: safety, error, or the Stop button (SIGINT) |

Every event also has `t` (Unix time).

## Adding a panel
1. Write a SwiftUI view in `app/Sources/<Name>Panel.swift`. Read state from
   `@EnvironmentObject var bot: BotRunner` (`events`, `lastTurn`, `running`, `cleared`, ...).
2. Append one line to `panels` in `app/Sources/Panels.swift`.
3. `app/build.sh --no-install`, then `"build/PAD Bot.app/Contents/MacOS/PADBot" --snapshot /tmp/snap`
   renders every panel to PNG without opening a window.
