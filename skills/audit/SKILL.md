---
name: audit
description: Read-only health check of a connected Android or Google TV. Reports model, storage, memory, uptime and what is actually slowing it down, and classifies every installed package as protected / caution / bloat / optional / unknown, with plain-English explanations and sources. Use when the user asks what's on their TV, why it's slow, what bloatware or ads it has, or before any debloat, speed-up or redesign work. Changes nothing on the TV.
---

# TV audit (read-only)

`tvkit` below means `python3 "${CLAUDE_PLUGIN_ROOT}/bin/tvkit"`. Run it exactly like that. Nothing in this skill changes the TV.

1. Run `tvkit status`. If no TV is connected, use the connect skill first.
2. Run `tvkit audit --json` for the data. The output is long, so focus on `info`, `findings`, `counts_enabled`, `bloat_candidates`, `optional`, `caution`, `unknown` and `already_disabled`. Plain `tvkit audit` gives a readable version.
3. Run `tvkit key HOME`, then `tvkit screenshot home`, and Read the PNG. Note the ad and promo rows, sponsored tiles, and how many presses it takes to reach the apps.
4. Some enabled system packages from the TV maker (e.g. `com.tcl.*`) will be `unknown`. Look a few up on the web when their names suggest ads, promos, stores, cloud or analytics. Record a finding only when you have real evidence: `tvkit learn <pkg> --tier bloat|optional|caution|protected --label "..." --why "..." --source <url>`. Never guess: if you find nothing, the package stays unknown.

## Report to the user
Keep it short and concrete:
1. **Your TV**: model, Android version, Google TV or Android TV, RAM, storage, uptime, security patch.
2. **What actually affects speed on this TV**: the `findings`, ranked by impact, with numbers. Nearly full storage and a long uptime matter far more than any list of apps.
3. **Bloat you could disable**: a table with package · what it is · why. Name the source when it came from a measured test (HWBusters).
4. **Leave alone**: one line on what's protected (inputs, remote, Wi-Fi, updates, the current Home app, the keyboard, system-user apps), so the user can see the guardrails.
5. **Privacy settings to check by hand** (menu names vary by model):
   - Settings → Privacy → Usage & diagnostics: off.
   - Ads → Ads personalization: off, and reset the advertising ID.
   - TCL "Viewing information", "Smart TV experience" or "User Experience Improvement Program": off. This is the ACR feature that collects viewing data.
   - Google TV **Apps only mode** (Settings → Accounts & sign-in → profile) removes recommendation rows, but it also turns off Assistant and search on Home.
6. **Next steps**: `/tvkit:speedup` (it measures first), `/tvkit:debloat`, `/tvkit:redesign`.

If an Artifact tool is available and the user wants something shareable, offer to turn the report into a one-page "TV health report". Follow that tool's rules, and never include the TV's serial number or IP address.
