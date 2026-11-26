---
name: speedup
description: Make an Android or Google TV feel faster with measured, reversible tweaks. Benchmarks first (cold app-launch times, idle CPU, free RAM, storage), applies only the levers this TV's numbers point to (a restart after long uptime, freeing storage when it's nearly full, 0.5x animations, a lighter home screen, fewer background apps), then re-measures and reports honestly. Use when the user says their TV is slow, laggy or sluggish, or wants it faster. No "10x faster" claims.
---

# Speed up, with receipts

`tvkit` below means `python3 "${CLAUDE_PLUGIN_ROOT}/bin/tvkit"`. Run it exactly like that.

**Set expectations first.** Viral posts promise "10x faster". The one careful test so far (HWBusters, TCL 98C7K, October 2026) found that debloating plus 0.5x animations changed app launch times by 0.5–1.5%, which is within noise. What really slows Android TVs is nearly full storage, weeks without a restart, too little RAM for the apps running in the background, and a heavy, ad-filled home screen. Measure, change one thing at a time, and measure again.

## Flow
1. Run `tvkit status`, then `tvkit info`. Note RAM, free storage, uptime, the animation scales and the health hints.
2. **Baseline.** Ask first: for a few minutes the TV opens and closes apps on screen, and nobody should touch the remote. `tvkit bench --label before` prints the plan; run it again with `--yes`. Pick apps the user actually uses with `--apps pkg1,pkg2` (see `tvkit apps`).
3. **Apply only what the numbers justify.** Explain each lever before applying it:

   | Signal | Lever | Command |
   |---|---|---|
   | Uptime over 7 days | Restart. TCL "instant power on" rarely truly reboots. | `tvkit reboot --wait` |
   | Free storage under 2 GB or under 15% | Trim app caches, and uninstall apps they never use (from TV Settings) | `tvkit cache` (it refuses when storage is fine, which is right) |
   | Animations at 1x | 0.5x makes menus feel snappier. Cosmetic, but you notice it. | `tvkit animations 0.5` |
   | Ad-heavy Google TV home screen | Apps only mode (set by hand), or a lighter launcher via the redesign skill | — |
   | Less than 400 MB RAM available | Fewer background apps | the debloat skill |

   Every command prints a plan first (exit code 2). Run it with `--yes` once the user agrees. `tvkit undo` reverts any change.
4. **Re-measure** under the same conditions: `tvkit bench --label after --yes` with the same `--apps`, then `tvkit bench-compare before after`.
5. **Report honestly.** Show a before/after table, then explain it in plain words. If a change is within noise, say so. Keep *measured* results (launch ms, idle CPU, RAM) apart from *felt* ones (animations, fewer ads). These numbers are the user's receipts if they post about it.

## Don't
- Install "booster" or "RAM cleaner" apps, set background process limits, or force-stop system services. They make things worse or don't stick.
- Change GPU or renderer properties, or anything via `setprop` (the guard blocks it).
- Clear caches when storage is fine. It slows the next app launches.
- Claim a speed-up the benchmark doesn't show.
