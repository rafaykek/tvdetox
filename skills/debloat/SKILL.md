---
name: debloat
description: Safely disable bloatware, ads, promo apps and telemetry on an Android or Google TV, with a focus on TCL. Uses reversible `pm disable-user` through tvkit, in small tested batches, with a snapshot before every change, a protected list sourced from real breakage reports, live checks (current launcher, keyboard, system-user and persistent packages) and one-command undo. Use when the user wants to remove or disable preinstalled apps, bloatware, TCL junk, boot ads or tracking on their TV.
argument-hint: "[package ...]"
---

# Debloat, safely

`tvkit` below means `python3 "${CLAUDE_PLUGIN_ROOT}/bin/tvkit"`. Run it exactly like that.

## Ground rules (non-negotiable)
- Change packages only with `tvkit disable`. The guard hook blocks raw `pm uninstall`/`pm disable` anyway. tvkit disables and never uninstalls, so everything comes back with `tvkit undo`.
- At most 5 packages per batch, and the user tests with the real remote between batches.
- Never work around a tvkit refusal. Protected packages stay enabled, and so do live-protected ones: the current Home app, the keyboard, system-user packages and persistent packages.
- `caution` packages each remove a feature (voice, casting, mirroring, the launcher). Use `--allow-caution` only after the user says they don't use that feature.
- `unknown` packages: research them first (see the audit skill). Use `--allow-unknown` only with evidence and the user's OK.
- Never disable the firmware update service. Updates carry security fixes.
- The stock launcher is out of scope unless a replacement is installed, set as Home and verified by pressing Home on the real remote. Even then, prefer leaving it enabled (see the redesign skill).

Be honest with the user: debloating mostly buys fewer ads, less clutter and less background activity. In the one careful measurement so far (HWBusters, TCL 98C7K), app launch times barely moved. Fewer background apps helps more on low-RAM TVs (2 GB or less).

## Flow
1. **Preflight**: run `tvkit status`. `tvkit snapshots` should list a baseline; if it doesn't, run `tvkit snapshot --label baseline`.
2. **Ask what they use**, in one checklist-style message: streaming apps, the voice remote / Google Assistant, casting from a phone (Chromecast), screen mirroring, Alexa, videos from USB drives, antenna and recordings, TCL account features, screensaver / ambient mode.
3. **Plan**: run `tvkit audit --json`. Candidates are the `bloat_candidates`, plus `optional` apps the user never uses, plus `caution` items only for features they turned down. If `$ARGUMENTS` names packages, plan just those (tvkit still checks them). Show a table: package · what it is · why disable it · what they'd lose · source. Get a clear yes.
4. **Batch**: run `tvkit disable <up to 5 packages> --reason "<short why>"`. This prints the plan and any refusals and changes nothing (exit code 2). Explain any refusal plainly. Once the user agrees, run the same command with `--yes`.
5. **Test**: walk the user through the checklist tvkit prints: Home, Inputs → HDMI, volume, voice, Wi-Fi, playback. If anything misbehaves, run `tvkit undo` right away and carry on without that package.
6. Repeat steps 4–5 until the plan is done.
7. **Wrap up**: offer a restart test (`tvkit reboot --wait`, then `--yes` once they agree) and re-check with `tvkit audit`. Summarise from `tvkit journal`: what's disabled, why, and how to undo it (`tvkit undo`, `tvkit undo --all`, `tvkit restore baseline`). Remind them that a firmware update can re-enable packages, so they can re-run this skill after updates.

## Optional extras (offer, don't push)
- **Apps only mode** (Google TV, set by hand): Settings → Accounts & sign-in → profile → Apps only mode. Removes recommendation rows, but Assistant and search on Home go away too.
- **Network ad blocking with Private DNS** (experimental on TVs): `tvkit set global private_dns_mode hostname`, then `tvkit set global private_dns_specifier dns.adguard-dns.com`. This can cut ad and tracker traffic in some apps. It can't block YouTube ads and may break some apps. Undo with `tvkit undo`.
