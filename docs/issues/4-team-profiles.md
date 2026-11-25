# Edit team profiles in the app
Labels: priority: medium, enhancement

**Why:** team rules live in `profiles/*.toml`; switching or tuning a team means editing a file.

**Scope:**
- Team picker on the Run tab (one entry per `profiles/*.toml`), passed to the bot with `--profile`.
- Teams tab: edit a profile's skill order, cooldowns, default goal and counters per enemy ability in a
  form, saved back to TOML.
- Out: learning rules automatically from runs.

**Done when:** a new team can be created and run from the app without opening a file, and the Lügner
profile round-trips unchanged.
