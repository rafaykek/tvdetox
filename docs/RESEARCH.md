# Research notes: AI agents, ADB and smart TVs (as of November 2026)

What people did, what they measured, and what broke. These findings shaped tvkit's design. Claims are labelled as *reported* where nobody measured them.

## TL;DR

- **The recipe is the same everywhere.** Turn on Developer options and USB / Wireless debugging. `adb connect` over Wi-Fi. Back up the package list. Disable (don't uninstall) preinstalled packages with `pm disable-user --user 0`. Optionally swap the launcher and shorten animations.
- **It removes ads and clutter. It doesn't make TVs "10x faster."** The only controlled before/after test (HWBusters, TCL 98C7K) found app launch times changed by 0.5–1.5%, which is noise. Available RAM rose by 3 MiB.
- **Breakage is real and specific.** A handful of TCL packages kill HDMI inputs, Wi-Fi or the remote when disabled. One location package reportedly boot-loops the TV. Over Wi-Fi ADB, a TV that can't boot can't be fixed remotely.
- **Replacing the Google TV home screen is fragile in 2026.** Projectivy's override depends on an accessibility service that recent updates and TCL firmware interfere with. `set-home-activity` can report success while the Home button still opens Google TV.
- **Privacy is a stronger reason than speed.** TCL's viewing-data (ACR) settings, Google's usage and ads settings, and promo services are the things worth switching off.

## Timeline

| When | Who | What |
|---|---|---|
| Sep 2026 | Mert Cobanov ([prompt](https://tv.cobanov.dev/en/prompt.txt)) | Used Claude Code on an older Android TV: FLauncher, shorter animations. Published a prompt with a "known traps" list of TCL packages. |
| mid-Oct 2026 | Gathin T. ([tv-vibehack](https://github.com/Gathin23/tv-vibehack), [CleanYourTV](https://github.com/Gathin23/cleanyourtv)) | Started with his parents' Xiaomi Mi TV, which showed an ad before Netflix. The project is a prompt plus scripts: backup, disable in batches with screenshots, a restore script, a clean launcher. Widely covered. Reported star counts vary a lot by date and source. |
| 20 Oct 2026 | Mihir Gupta, via [TweakTown](https://www.tweaktown.com/news/114177/tcl-google-tv-owner-hands-the-remote-to-claude-code-and-the-ads-dont-survive/index.html) | TCL Google TV with 2 GB RAM. Claude Code over Wi-Fi ADB disabled 25 preinstalled apps, then built an Apple TV-style launcher ([tv-home](https://github.com/mihirgupta0900/tv-home)). The README *reports* home-screen memory falling from 192 MB to 83 MB (not independently verified). |
| 21–23 Oct 2026 | [HWBusters](https://hwbusters.com/software/ai-tv-debloating-tcl-98c7k-benchmarks/) | A controlled benchmark on a TCL 98C7K (Android TV 14). Details below. |
| Oct–Nov 2026 | [ItsFOSS](https://itsfoss.com/news/debloat-smart-tv/), [DevDigest](https://www.developersdigest.tech/blog/cleanyourtv-claude-code-debloat-android-tv-safe-guide-2026), [ExplainX](https://www.explainx.ai/blog/tv-vibehack-debloat-android-tv-claude-code-adb-launcher-guide-2026) and others | Wide coverage. Reports of refusals for bare "hack my TV" requests, one TV bricked, and a Mi TV Stick that never booted after a list disabled six system packages (reported second-hand). |
| Nov 2026 | Android Authority | A Google TV update reportedly blocks Projectivy's launcher override. |

## What HWBusters actually measured (TCL 98C7K)

The baseline was rebuilt from saved package states. The tune-up disabled six apps (iQIYI, BrowseHere `com.tcl.browser`, Play Games, YouTube Music, TCL Alexa `com.tcl.smartalexa`, MagiConnect `com.tcl.magiconnectfree`) and set animations to 0.5x.

| Metric | Before | After | Notes |
|---|---|---|---|
| YouTube cold launch, median | 446.0 ms | 443.5 ms | 8 runs per configuration, `am start -W` |
| Plex cold launch, median | 500.0 ms | 497.5 ms | |
| VLC cold launch, median | 408.5 ms | 402.5 ms | Direction varied between blocks |
| Home navigation p95 frame time | 22 ms | 22 ms | 5,653 frames from HWUI counters |
| Idle CPU | 4.18% | 2.80% | Short `/proc/stat` samples |
| Available RAM | 902.3 MiB | 905.4 MiB | Ranges overlap |

Their Projectivy 4.72 trial, compared with the stock Google TV Home: launches were 4–5% *slower*, and idle CPU was 20.47% vs 3.76% (17% even with the wallpaper off). Their verdict: *"I wouldn't bother with this tune-up just to get these apps to start faster."*

tvkit's `bench` command copies this method: cold launches via `am start -W` with a force-stop first, medians and ranges, idle CPU from `/proc/stat` deltas, MemAvailable, and the Home app's PSS.

## The common recipe, and where it bites

| Step | Common practice | Trap |
|---|---|---|
| Connect | Developer options (press OK on "Android TV OS build" 7×), USB debugging, `adb connect IP:5555`. Android 11+ uses Wireless debugging with `adb pair`. | macOS Local Network privacy can block adb ("No route to host"). Ports change when debugging is toggled. Some TVs cut USB power while debugging is on. |
| Backup | `pm list packages -s/-d`, `settings list`, `getprop` | Restoring by "enable everything" re-enables things that were disabled before you started. tvkit restores exact previous states. |
| Debloat | `pm disable-user --user 0`, in batches, with screenshots between | Uninstalling isn't easily undone. Chained `pm` commands can stop silently after the first one, so run them one per call. |
| Launcher | Install Projectivy or FLauncher. Some disable the stock launcher. | Disabling the stock launcher before the new one is set leaves no Home screen. `setupwraith` can take Home back. Casting reportedly breaks on some Google TV devices without the stock launcher. |
| Speed | 0.5x animations | The difference is felt rather than measured. |
| Safety net | Restore script | A factory reset is the real last resort, and it wipes everything. |

## Reported breakage (TCL and Google TV)

From [Mert Cobanov's prompt](https://tv.cobanov.dev/en/prompt.txt) unless noted. These are author reports, not lab results.

| Package | Reported effect when disabled |
|---|---|
| `com.tcl.suspension` | The Inputs/Source button dies; you can't switch to HDMI |
| `com.tcl.tvinput`, `com.tcl.tv` | HDMI and antenna inputs stop working |
| `com.tcl.providers.config`, `com.tcl.initsetup` | Wi-Fi drops |
| `com.tcl.tcl_bt_rcu_service`, `com.tcl.autopair`, `com.google.android.tv.remote.service` | The remote stops working |
| `com.tcl.ttvs` | The system update menu silently stops working |
| `com.android.location.fused` | Boot loop |
| Stock launcher, disabled before a replacement | No Home screen |
| Gallery (system UID) | Not a breakage: HWBusters left it alone because it shares the Android system UID. tvkit generalises this into a rule. |

## Customising the home screen in 2026

- **Built in:** Google TV **Apps only mode** (Settings → Accounts & sign-in → profile). It hides personalised recommendations, but Assistant and search on Home go away too, and some ads remain.
- **Projectivy Launcher:** the most customisable option (themes, wallpaper plugins, which apps may recommend content, hiding ad slots). The override uses an accessibility service, which Android warns can read typed text. TCL users report the override switching itself off, a recent Google TV update reportedly blocks it, and it was the heaviest launcher HWBusters measured.
- **FLauncher** (open source, lightweight) and its fork **Arc**; **Dispatch** and **AT4K** (commercial).
- **Build your own:** Mihir Gupta's tv-home is the proof of concept.
- **ADB home switch:** `cmd package set-home-activity` printed "Success" on a TCL 98C7K, but the Home key still opened Google TV.

tvkit's `/tvkit:redesign` designs the home screen with you first (as an interactive mockup), then maps the design to the least fragile way to get there.

## Privacy (ACR)

Google says the Google TV platform itself doesn't use ACR (automatic content recognition) to capture what you watch. TV makers can, through their own terms. Texas's attorney general has sued several TV makers, including TCL, over ACR (an allegation, not a finding). RTINGS couldn't isolate an ACR data flow on a TCL QM8K. What to check: Settings → Privacy → Usage & diagnostics, Ads personalisation, and TCL's "Viewing information", "Smart TV experience" and "User Experience Improvement Program" toggles. Names vary by model.

## Existing tools

| Project | Form | Notes |
|---|---|---|
| CleanYourTV / tv-vibehack | Prompt + shell scripts + a pure-Python ADB client | Huge reach; restore script; per-TV example lists |
| tv-home | Custom launcher | Apple TV-style home for a TCL Google TV |
| TV Box Tools (smartago) | Claude Code plugin + MCP server (Node 22) | No raw shell; refuses system apps; focused on launcher setup |
| adb-tv-mcp, MCP-ADB, clawtv, TVWizard | MCP servers / CLIs | General ADB control for agents |
| android-tv-debloat-toolkit (seun-novodev) | Windows tool | Safe/Caution/Critical lists; not actively maintained |

**Where tvkit differs:** it pairs a raw-ADB-capable agent with a guard hook (instead of removing the shell), checks live device facts, keeps an exact-state undo journal, benchmarks before and after, and closes the loop from design to device.

## Sources

- TweakTown, *TCL Google TV owner hands the remote to Claude Code and the ads don't survive* — https://www.tweaktown.com/news/114177/tcl-google-tv-owner-hands-the-remote-to-claude-code-and-the-ads-dont-survive/index.html
- HWBusters, *AI TV debloating: TCL 98C7K benchmarks* — https://hwbusters.com/software/ai-tv-debloating-tcl-98c7k-benchmarks/
- Mert Cobanov, Android TV prompt — https://tv.cobanov.dev/en/prompt.txt
- DevDigest, *CleanYourTV: Debloat Your TV With Claude Code, Safely* — https://www.developersdigest.tech/blog/cleanyourtv-claude-code-debloat-android-tv-safe-guide-2026
- ExplainX, *tv-vibehack guide* — https://www.explainx.ai/blog/tv-vibehack-debloat-android-tv-claude-code-adb-launcher-guide-2026
- ItsFOSS, *People Are Using AI to Get Rid of Smart TV Ads* — https://itsfoss.com/news/debloat-smart-tv/
- Android Authority, *Install a Google TV launcher alternative* — https://www.androidauthority.com/install-google-tv-launcher-alternative-3663642/
- Android Authority, *Google TV update blocks Projectivy override* — https://www.androidauthority.com/google-tv-update-blocks-projectivy-override-3649445
- seun-novodev, android-tv-debloat-toolkit — https://github.com/seun-novodev/android-tv-debloat-toolkit
- Bayton system app database (com.tcl) — https://sysapps.bayton.org/packages/com.tcl
- Malwarebytes, *Samsung TVs stop spying on viewers in Texas* (ACR) — https://www.malwarebytes.com/blog/news/2026/03/samsung-tvs-stop-spying-on-viewers-in-texas-heres-how-to-disable-acr-anywhere
- RTINGS, *Testing smart TV tracking* — https://www.rtings.com/tv/learn/research/smart-tv-tracking
- TV Box Tools — https://mcpservers.org/servers/smartago/tvboxtools-plugin
