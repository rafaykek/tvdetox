---
name: restore
description: Undo tvkit changes on an Android or Google TV. Rolls back the last batch, everything tvkit ever changed, or the full package and setting state of any snapshot (including the factory baseline). Also the emergency playbook for when Home, inputs, the remote or Wi-Fi stop working after a debloat. Use when the user says something broke on the TV or wants to revert, undo or restore changes, or after a firmware update re-enabled things.
argument-hint: "[snapshot name, or 'all']"
---

# Restore and recover

`tvkit` below means `python3 "${CLAUDE_PLUGIN_ROOT}/bin/tvkit"`. Run it exactly like that.

## Choose the smallest fix
1. Run `tvkit journal`. It lists every change tvkit made, grouped in batches, with the before and after state.
2. Then pick the smallest fix that works:
   - The last batch: `tvkit undo`
   - A specific batch: `tvkit undo --batch <id>`
   - Everything tvkit ever changed: `tvkit undo --all`
   - Back to a snapshot (the default is the factory baseline): `tvkit snapshots`, then `tvkit restore <name>`
   - A single package: `tvkit enable <package>`

   Each one prints a plan first. Once the user agrees, run it again with `--yes`. Undo and restore re-check what's on the TV, so they're safe to repeat.
3. Ask the user to test again: Home, Inputs → HDMI, the remote's buttons, Wi-Fi, playback.

## Emergency playbook
- **The Home button does nothing, or the screen is blank**: `tvkit home` shows what Home opens. Re-enable the stock launcher (`tvkit enable com.google.android.apps.tv.launcherx`, or `com.google.android.tvlauncher` on Android TV), or run `tvkit undo --all`.
- **The Inputs / HDMI menu is gone**: `tvkit enable com.tcl.suspension com.tcl.tvinput com.tcl.tv`. tvkit never disables these, so something outside tvkit probably did.
- **The remote is dead**: drive the TV over ADB (`tvkit key HOME`, `tvkit key BACK`, ...) or with the Google TV phone app, then undo.
- **The TV lost Wi-Fi, so ADB is gone too**: plug in Ethernet if the TV has a port. ADB works over it once you find the new IP. Otherwise reconnect Wi-Fi with the remote. Then run `tvkit connect` and `tvkit undo --all`.
- **Boot loop, or stuck on the logo**: wait 10 minutes, because the first boot after changes can be slow. If it never boots, a factory reset from recovery mode is the last resort. The button combination varies by model (check TCL support), and it erases apps, logins and settings. Be honest that Wi-Fi ADB can't help while the TV can't boot.
- **After a firmware update**: updates can re-enable packages and reset settings. `tvkit audit` shows the current state. Re-apply with the debloat skill if the user wants.

If a problem traces back to a package tvkit allowed, tell the user. Suggest recording it (`tvkit learn <pkg> --tier protected ...`) or opening an issue, so the knowledge base protects the next person.
