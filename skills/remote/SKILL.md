---
name: remote
description: Control an Android or Google TV in plain language over ADB. Opens apps, navigates with the D-pad, types into search boxes, plays and pauses, changes the volume, switches inputs, and looks at the screen to decide what to press next. Use when the user asks Claude to do something on the TV, like "open YouTube", "search for lo-fi music", "go home", "pause" or "turn it down". It doesn't change settings or apps.
argument-hint: "<what to do on the TV>"
---

# TV remote

`tvkit` below means `python3 "${CLAUDE_PLUGIN_ROOT}/bin/tvkit"`. Run it exactly like that.

Work in a loop: **look → act → look**. Never press keys blind for more than two or three steps.
- **Look**: `tvkit screenshot now`, then Read the PNG. When you need the exact labels or the focused item, `tvkit ui-dump` prints the visible text and marks what's focused. It can fail while video plays; screenshots still work.
- **Open an app**: find the package with `tvkit apps --json`, then `tvkit launch <package>`.
- **Navigate**: `tvkit key UP|DOWN|LEFT|RIGHT|CENTER|BACK|HOME`. For several keys at once: `tvkit key DOWN DOWN RIGHT CENTER --delay 0.5`.
- **Media**: `tvkit key PLAY_PAUSE|PLAY|PAUSE|NEXT|PREVIOUS|REWIND|FAST_FORWARD`. Volume: `VOLUME_UP|VOLUME_DOWN|MUTE`. `INPUT` opens the input picker.
- **Type**: focus a search box first, then `tvkit text lo-fi beats` (letters, digits, spaces and basic punctuation).
- **Search inside YouTube**: launch it, find search (look at the screen), type the query, then press CENTER on a result.

## Rules
- Do what was asked, then stop and say what's on screen.
- Don't change settings, sign in or out, buy or rent anything, or accept terms or dialogs that cost money or share data. Stop and ask the user instead.
- `POWER` and `SLEEP` put the TV in standby, which usually drops Wi-Fi ADB. Warn the user first.
- Screenshots can show personal content such as profiles and watch history. They stay in ~/.tvkit on this computer; don't paste them anywhere else.
