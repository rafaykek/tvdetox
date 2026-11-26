# tvkit safety model

tvkit lets an AI agent change a TV over the network. These are the layers that keep that from going wrong, from the outside in.

## What we're protecting against

| Risk | Example | Why it matters |
|---|---|---|
| Disabling a core package | `com.tcl.suspension` kills the Inputs button | You lose HDMI until it's re-enabled |
| Cutting the connection | Disabling Wi-Fi, `adb_enabled 0` | Fixing it needs the physical remote |
| Boot loop | `com.android.location.fused` (reported) | Wi-Fi ADB is gone while the TV can't boot; a factory reset is the last resort |
| Irreversible actions | `pm uninstall`, `pm clear`, factory reset, `fastboot` | Data and logins lost; possible brick |
| Session hangs | An interactive `adb shell`, a streaming `adb logcat` | The agent stalls |
| Network exposure | Debugging left on, on a shared network | Someone else could control the TV |

## The layers

1. **Plan, then change.** Commands that change the TV (`disable`, `enable`, `undo`, `restore`, `set`, `animations`, `cache`, `home set`, `reboot`, `bench`, `lock`) print a plan and exit with code `2` until they're re-run with `--yes`. In an interactive terminal they ask instead. The skills show the plan to you and only add `--yes` after you agree.
2. **Snapshot before every change.** Every package with its uid, the system and disabled package lists, every global/secure/system setting, `getprop` and the Home activity, saved to `~/.tvkit/devices/<tv>/snapshots/`. The first connect saves a `baseline`.
3. **Knowledge base with sources.** [`data/packages.json`](../data/packages.json) rates packages as `protected`, `caution`, `bloat` or `optional`, and every entry cites where the claim came from. On top of the list:
   - whole namespaces are protected (`android.*`, `com.android.providers.*`, chipset vendors like `com.mediatek.*`, Play Services, …);
   - unknown *system* packages whose names suggest a core job (input, hdmi, remote, bt, wifi, network, setup, update, ota, factory, keyboard, provider, framework, service, …) are treated as protected;
   - other unknown system packages need research and `--allow-unknown`;
   - `caution` packages each remove a feature (voice, casting, launcher) and need `--allow-caution` plus your OK;
   - local notes (`tvkit learn`) can add knowledge but never unprotect anything.
4. **Live checks on the TV.** These come from the device and override everything above:
   - the package that currently resolves as **Home**;
   - the active **keyboard**;
   - active **accessibility services**;
   - packages that run as a **system user** (uid < 10000): over Wi-Fi ADB a boot loop would take ADB away too, so tvkit never touches these;
   - **persistent** packages (Android keeps them running permanently).
5. **Reversible operations only.** `pm disable-user --user 0` (app data kept), settings with their old value logged, the Home app with the old one logged. No uninstall, no data clearing, no root.
6. **Exact undo.** `~/.tvkit/devices/<tv>/journal.jsonl` records each change's previous state. `undo` puts that state back, using `pm default-state` rather than a blanket `pm enable`, so packages that were disabled before tvkit started stay disabled. `restore` compares a snapshot with the live TV and only touches differences tvkit can manage.
7. **Small batches.** At most 5 packages per batch (hard cap 10), and after each batch the checklist: Home, Inputs → HDMI, volume, voice, Wi-Fi, playback. If the connection drops right after a change, tvkit stops immediately and tells you how to recover.
8. **The guard hook.** [`hooks/adb_guard.py`](../hooks/adb_guard.py) runs before every Bash command Claude issues. If the command involves `adb` or `fastboot` and matches a destructive pattern, it is blocked (exit 2) and logged to `~/.tvkit/guard.log`. The checks below appear in that guard log, so you can see what was stopped.

## What the guard blocks

| Pattern | Why | Use instead |
|---|---|---|
| `fastboot …`, `adb reboot bootloader/recovery/sideload`, `adb root/remount/disable-verity` | Partition writes and recovery modes can brick the TV | `tvkit reboot` for a normal restart |
| `pm uninstall`, `adb uninstall`, `pm uninstall-system-updates` | Not reversible the way disabling is | `tvkit disable` |
| `pm disable*`, `pm hide`, `pm suspend` (raw) | Skips the protected list, live checks and journal | `tvkit disable` |
| `pm clear` (without `--cache-only`) | Wipes app data and logins | `tvkit cache` |
| `settings put/delete/reset` (raw) | Not journaled; some keys cut the connection | `tvkit set` / `unset` / `animations` |
| `cmd role …-role-holder`, `set-home-activity` (raw) | Launcher changes need verification | `tvkit home set` |
| Wi-Fi / network off, airplane mode | Cuts the ADB connection | — |
| `MASTER_CLEAR`, `FACTORY_RESET`, `--wipe_data` | Erases everything | — |
| `dd`, `mkfs`, `setprop`, `content insert/update/delete`, `cmd overlay` | Low-level writes | — |
| `rm` outside `/sdcard/tvkit*` and `/data/local/tmp/tvkit*` | Deletes your files | — |
| `adb push` outside `/sdcard`, `/storage`, `/data/local/tmp` | System paths | `tvkit push-wallpaper` |
| Interactive `adb shell`, `… \| adb shell`, `adb shell < file`, `adb shell sh script.sh` | Hides commands from these checks, or hangs | Pass each command as an argument |
| `adb logcat` without `-d` | Streams forever | `adb logcat -d \| tail -n 200` |

Read-only commands (`getprop`, `dumpsys`, `pm list`, `settings get/list`, `screencap`, `input`, `am start`, …) pass through. Only **you** can turn the guard off, by starting Claude Code with `TVKIT_GUARD=off`. Claude is told not to try to work around it.

## Network ADB

ADB over Wi-Fi gives full shell access to anyone on your network who gets past the TV's **Allow debugging?** prompt. So:
- only approve prompts you triggered yourself;
- don't enable debugging on public or shared networks;
- turn it off when you're done: `tvkit lock`, or Developer options → USB debugging.

## When something still goes wrong

See [`skills/restore/SKILL.md`](../skills/restore/SKILL.md) for the playbook: lost Home screen, missing Inputs menu, dead remote, lost Wi-Fi, boot loop, and what a firmware update does to your changes.
