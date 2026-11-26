# tvkit: notes for Claude

A Claude Code plugin for safe, reversible, measured Android TV / Google TV tune-ups over ADB.

## Layout
- `bin/tvkit`: the CLI (Python 3.8+, stdlib only). Every TV change goes through it.
- `hooks/adb_guard.py` + `hooks/hooks.json`: PreToolUse guard that blocks destructive adb/fastboot commands.
- `data/packages.json`: package knowledge base (tiers + sources).
- `skills/<name>/SKILL.md`: connect, audit, debloat, speedup, redesign, remote, restore. They call `python3 "${CLAUDE_PLUGIN_ROOT}/bin/tvkit"`.
- `launcher/`: tvkit Home, an Android TV launcher (WebView + bridge) that runs the redesign page as the real home screen. Built by `launcher/build.sh` without Gradle; output and signing key live in `~/.tvkit/`, never in git.
- `tests/`: unittest suite against `tests/fake_adb.py` (a fake TCL Google TV). No hardware needed.
- `docs/`: RESEARCH.md (sources), SAFETY.md (safety model).

## Rules when working on a real TV
- Change the TV only through `bin/tvkit`. Read-only `adb shell` commands are fine; raw writes are blocked by the guard, and that's by design. Never work around the guard or a tvkit refusal.
- Run a changing command without `--yes` first, show the user the plan, and add `--yes` only after they agree.
- Batches of 5 or fewer packages; the user tests with the real remote between batches.
- Never disable the firmware update service, the current Home app, the keyboard, input/HDMI, remote, Wi-Fi or system-user packages.
- Report benchmark results honestly; no speed-up claims that `tvkit bench-compare` doesn't show.
- Screenshots, serial numbers and IPs stay in `~/.tvkit/`. Don't commit or publish them.

## Changing the code
- Keep `bin/tvkit` stdlib-only and a single file. Keep the exit codes (0 ok, 1 error, 2 plan only, 3 refused).
- Every new package entry in `data/packages.json` needs `src` pointing at a breakage report, a measured test or official docs. When in doubt, use a stricter tier.
- New tvkit commands that change state must: print a plan + `confirm()`, `take_snapshot()`, and log through `Batch.log()` with the previous state so `undo` works.
- Run `python3 -m unittest discover -s tests` and `claude plugin validate .` before committing. Extend `tests/fake_adb.py` when you add device commands.
