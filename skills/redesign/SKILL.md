---
name: redesign
description: Redesign, modernize or personalize an Android TV / Google TV home screen (launcher). Captures the TV's current home screen over ADB, asks about the user's apps and taste, and builds an interactive mockup (Samsung-style ribbon, Apple-TV-style shelf, or minimal) that you drive with the arrow keys like a remote, with a before/after view and a matching 1920x1080 wallpaper, as a local page (published as a shareable link only if the user asks). Then gives an honest plan to make it real with built-in settings or an alternative launcher (Projectivy, FLauncher). Use when the user wants a better, cleaner, more modern or more personal TV interface, a Samsung- or Apple-TV-like home screen, a new launcher or wallpaper, or a TV UI design to show on LinkedIn or GitHub.
argument-hint: "[ribbon|shelf|minimal] [what to change, e.g. 'warmer colours, Netflix first']"
---

# Redesign the TV home screen

Turn the TV's current home screen into a calmer, personal design: an interactive mockup the user can drive with the arrow keys and share, plus an honest plan for getting as close to it as their TV allows.

**What this skill changes on the TV: nothing**, apart from pushing a wallpaper image if the user asks for one. It reads screenshots and the app list. It never disables, hides or replaces the stock launcher. That belongs to `/tvkit:debloat`, and only after a replacement launcher has been verified working.

In the commands below, `tvkit` means `python3 "${CLAUDE_PLUGIN_ROOT}/bin/tvkit"`. Write the full command every time.

## 1. Check the connection

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/bin/tvkit" status
```

If it fails, stop and run `/tvkit:connect` first.

## 2. Capture what is there today

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/bin/tvkit" key HOME --delay 2
python3 "${CLAUDE_PLUGIN_ROOT}/bin/tvkit" screenshot home          # last line = PNG path
python3 "${CLAUDE_PLUGIN_ROOT}/bin/tvkit" apps --launchable --json  # apps with a TV launcher icon
python3 "${CLAUDE_PLUGIN_ROOT}/bin/tvkit" info --json               # model, resolution, home launcher, google_tv
```

- **Read the screenshot PNG** so you can see the screen. If the home screen continues below, capture one more after `tvkit key DOWN DOWN --delay 1` (`tvkit screenshot home-2`), then press `HOME` again so the TV is left where it was.
- `tvkit ui-dump` (optional, best effort) gives the visible text when the screenshot is hard to read.
- A black screenshot usually means protected (DRM) video was on screen. Go Home and retry.
- App labels from `apps --launchable` can be derived from package names. Correct them to the names people know.

**Real app logos (recommended).** The TV's own Apps screen shows each installed app's official banner. Capture them so the mockup shows logos instead of letters:
1. Open the Apps screen with keys, looking after each step. On Android TV 9+ that's usually `tvkit key HOME`, `UP`, `RIGHT` to the Apps tab, `CENTER`, then `DOWN` into the grid. On Google TV it's the Apps tab or "Your apps → See all".
2. On a still screen: `tvkit ui-dump` (its last line is the XML path; retry if it fails while something animates) and `tvkit screenshot apps`. Unfocused rows are dimmed, so move focus into a row (`tvkit key DOWN`) before capturing it.
3. Crop by tile label: `python3 "${CLAUDE_SKILL_DIR}/scripts/crop_tiles.py" <apps.png> <ui.xml> <dir>/logos "Netflix=netflix" "YouTube=youtube" ...`
4. Add `"logo": "<dir>/logos/netflix.png"` to each app in the config. The build embeds the logos, so the page still works offline.
5. Press `HOME` to leave the TV where it was.

These banners come from the user's own TV. They stay in `~/.tvkit` and must never be committed to a repository; the repo's sample images use letters on purpose.

## 3. Ask briefly

Skip anything the user already said. With `AskUserQuestion`, ask at most four things at once:

1. **Favourites, in order.** Offer the detected apps and keep it to 4–8.
2. **Layout**, using these previews:
   ```
   ribbon                          shelf                           minimal
   ┌──────────────────────────┐    ┌──────────────────────────┐    ┌──────────────────────────┐
   │ Good evening   (o)(o) 21:40│    │ Good evening   (o)(o) 21:40│    │ 21:40               (o)(o)│
   │ FAVOURITE · 2 OF 5        │    │ NETFLIX           ░░ N ░░ │    │ Wednesday 25 November     │
   │ Netflix                   │    │ [Continue] [My List]      │    │                           │
   │ [Continue] [My List]      │    │ FAVOURITES                │    │ FAVOURITES                │
   │                           │    │ [YT] [N] [PV] [S] [PX]    │    │ (YouTube) (Netflix) (Plex)│
   │ [YT][N][PV][S] | [H1][H2] │    │ INPUTS  [HDMI 1] [HDMI 2] │    │ INPUTS (HDMI 1 · PS5)     │
   └──────────────────────────┘    └──────────────────────────┘    └──────────────────────────┘
   ```
3. **Mood**: Tungsten (warm, the default), Aurora, Midnight, Graphite or Coral, or an accent colour of their own.
4. **What bothers them today**: ad or sponsored rows, too many presses to reach apps, clutter, a slow feel. Also ask **which inputs they use** and what is plugged in, e.g. HDMI 1 = PlayStation 5.

Also ask whether the "before" screenshot may go into a page that could be shared. It can show profile names, watch history and thumbnails. If unsure, keep it in the local file only.

## 4. Critique the current screen

Be specific and countable, never generic:

- Count the rows, and how many are ads, sponsored or recommendations.
- Count the D-pad presses from Home to each favourite and to the Inputs menu.
- Note small text, crowded rows, autoplaying trailer areas and anything that hides the apps.

These observations become `before.issues`. The improvements become `changes`, e.g. "Netflix: 6 presses → 1". Every claim in `changes` must be true of the mockup. Count presses from the layout you are building (in the ribbon, favourite *n* is *n−1* presses right of the first tile).

Do not promise speed. The redesign is about fewer steps and less clutter. Measured debloats barely change app launch times (0.5–1.5% on a TCL 98C7K in HWBusters' tests), and that is the `/tvkit:speedup` skill's subject.

## 5. Build the mockup

Write the config as JSON (schema below), then build:

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/build.py" \
  --config "<dir>/config.json" \
  --before "<home.png from step 2>" \
  --out "<dir>" --renders
```

It writes into `<dir>`. Without `--out` it uses `~/.tvkit/redesign/<timestamp>/`.

| File | What it is |
|---|---|
| `tv-redesign.html` | standalone page; open it locally |
| `tv-redesign.artifact.html` | the same page without the html/head/body skeleton, ready for the Artifact tool |
| `tv-redesign-wallpaper.png` | 1920×1080 wallpaper exported with headless Chrome/Chromium/Edge/Brave (skipped if none is installed) |
| `tv-redesign-{ribbon,shelf,minimal,before}.png` | full-screen renders for posts and READMEs (`--renders`) |

Other flags: `--wallpaper-photo PHOTO.jpg` uses the user's own photo as the wallpaper. `--no-wallpaper` skips the PNG. `--name` changes the file prefix.

Customize through the config. Edit `${CLAUDE_SKILL_DIR}/templates/tv-home.html` only for something the config can't express. The template already meets the Artifact page rules: no html/head/body skeleton, its own `<title>`, a theme-aware page, no external requests.

### Config schema

```json
{
  "title": "Alex's Living Room TV",
  "subtitle": "Favourites first, the console one press away, no promoted rows.",
  "sample": false,
  "owner": "Alex",
  "greeting": "auto",
  "preset": "ribbon",
  "theme": "tungsten",
  "accent": null,
  "clock": "24h",
  "wallpaper": { "mood": "horizon", "seed": 11 },
  "device": { "model": "TCL 55C645", "resolution": "1920x1080" },
  "favorites": [
    { "label": "Netflix", "color": "#B20710", "glyph": "N", "package": "com.netflix.ninja",
      "note": "Pick up where you left off", "actions": ["Continue watching", "My List", "Search"] }
  ],
  "inputs": [ { "label": "HDMI 1", "name": "PlayStation 5", "note": "HDMI 1 · switch without the Inputs menu" } ],
  "apps": [ { "label": "VLC", "color": "#F47216", "glyph": "VLC", "package": "org.videolan.vlc" } ],
  "before": { "caption": "Stock Google TV home, captured 25 Nov 2026",
              "issues": [ { "title": "Two sponsored rows", "detail": "Rows 2 and 3 promote shows from apps you don't use." } ] },
  "changes": [ { "title": "Netflix: 6 presses → 1", "detail": "It is the first tile on the ribbon." } ]
}
```

| Key | Values and rules |
|---|---|
| `title` | Page and artifact name: a short noun phrase, no explanation after a dash. |
| `preset` | `ribbon` · `shelf` · `minimal` |
| `theme` | `tungsten` · `aurora` · `midnight` · `graphite` · `coral`. `accent` optionally overrides the focus colour (`#RRGGBB`). |
| `wallpaper.mood` | `horizon` · `aurora` · `midnight` · `solid` (`photo` is set by `--wallpaper-photo`). `seed` varies the generated scene. |
| `owner`, `greeting`, `clock` | Greeting name (optional) · `"auto"` or fixed text · `"24h"` / `"12h"` |
| `favorites`, `apps` | `label` (required), `color` (brand-like hex), `glyph` (1–3 letters, used when there's no logo), `logo` (optional path to a banner captured from the user's TV; embedded at build time), `package`, `note` (one line), `actions` (up to 4 short labels). |
| `inputs` | `label` ("HDMI 1"), `name` (what is plugged in), optional `note` and `actions`. |
| `before.issues`, `changes` | Lists of `{title, detail}`. Shown under the TV. Facts only. |
| `before.image` | Filled by `--before`. Never write a data URI by hand. |
| `sample` | `true` only for demo data; it shows a "Sample data" chip. |

## 6. Show it

- **Default: open the local page.** `open "<dir>/tv-redesign.html"` (macOS), `xdg-open` (Linux) or `start` (Windows). It works offline and nothing leaves the computer.
- **Publish only if the user asks for a shareable link.** Ask first; many people don't want anything published. If they say yes and an Artifact tool is available, call it with `action: "quickstart"` and `intent: "other"`. This is an interactive prototype the viewer drives with arrow keys: a plain page, not a Design-canvas document. Follow what the quickstart says, then publish `tv-redesign.artifact.html` as `file_path` with a one-sentence `description` and `icon: "tv"`. The Artifact tool only sends files from the working folder or your scratchpad, so build with `--out` inside your scratchpad. Never publish a build made with `--before` unless the user agreed to share their screenshot. Tell the user the page is private until they share it.

In the page: arrow keys move, Enter "opens". The remote's colour keys work too: **R** toggles before/after, **G** changes the layout, **Y** cycles the wallpaper, **B** changes the theme. The rail switches layout, theme and wallpaper live, and **Export wallpaper PNG** works in the local file. Inside a shared artifact, downloads are blocked, so use the PNG the build script wrote.

## 7. Make it real (be honest about each tier)

**Tier 1: built-in settings. No ADB changes, fully reversible.**
- Google TV **Apps only mode**: Settings → Accounts & Sign In → your profile → Apps only mode. It hides personalised recommendations. Google Assistant and some content features stop working, and some promoted content can remain.
- Reorder favourites: in the apps row, highlight an app, long-press OK, then Move. Remove unused apps from favourites the same way.
- Rename inputs (usually Settings → Channels & Inputs → Inputs) so "HDMI 1" reads "PlayStation 5" everywhere. Menu names vary by model and firmware, so say "usually".

**Tier 2: an alternative launcher. Installed alongside the stock one; nothing gets disabled.**
- Install **Projectivy Launcher** (the most customisable: themes, wallpapers, row layout, hiding ad slots) or **FLauncher** (open source, lightweight: gitlab.com/flauncher/flauncher) from the Play Store on the TV.
- Wallpaper: `python3 "${CLAUDE_PLUGIN_ROOT}/bin/tvkit" push-wallpaper "<dir>/tv-redesign-wallpaper.png"` copies it to `/sdcard/Pictures/tvkit/`. Pick that image in the launcher's wallpaper settings. Then match the favourites order and accent colour to the mockup.
- Home button: `tvkit home` shows the current home app and the installed home-capable apps. Set expectations plainly:
  - Projectivy's "Override current launcher" takes over Home through an accessibility service. Android warns such services can read typed text, and HWBusters left it off for that reason.
  - In 2026, a Google TV update stopped Projectivy's override from working on some devices (Android Authority). TCL owners report the accessibility toggle getting switched off, after which Home goes back to the stock launcher.
  - On a TCL 98C7K, `cmd package set-home-activity` printed "Success" but the Home key still opened Google TV (HWBusters). The user may end up opening the launcher from the apps row.
- Cost: HWBusters measured Projectivy 4.72 on that TCL. Idle CPU was **20.47% vs 3.76%** for stock Google TV Home (17.03% with the wallpaper set to None), and app launches were about 4–5% slower. A prettier launcher is not a faster one; say so.
- Never disable the stock launcher from this skill. If the user wants that, hand off to `/tvkit:debloat`. It does it only after the replacement is verified, and warns that disabling the Google TV launcher can break casting on some devices.

**Tier 3: tvkit Home, the mockup as the real home screen (exact look).** `launcher/` holds a tiny Android TV launcher (about 200 KB): a full-screen WebView that shows the built page at `#launcher` and a 5-method bridge (`launch`, `openInput`, `openSettings`, `search`, `apps`). It never loads anything from the network. Inside it, the page adds every other installed TV app, with the banner the TV uses, to "More apps", so nothing becomes unreachable. Tested on a TCL Android TV 9.
1. Ask first. This installs about 600 MB of build tools on the computer (`brew install openjdk@17`, `brew install --cask android-commandlinetools`, `sdkmanager "build-tools;34.0.0" "platforms;android-28"`, which accepts Google's SDK licence) and one app on the TV.
2. Build the page without `--before`, then `"${CLAUDE_PLUGIN_ROOT}/launcher/build.sh" <dir>/tv-redesign.html <dir>/tv-redesign-wallpaper.png` → `~/.tvkit/launcher/tvkit-home.apk`. The signing key is created once in `~/.tvkit/keystore/` so updates install over it.
3. `adb install -r ~/.tvkit/launcher/tvkit-home.apk`, then `tvkit launch dev.tvkit.home` to check it on the TV. A cold start shows black for about 2 seconds while the WebView starts (measured on a TCL Android TV 9). Start-up timings are logged: `adb logcat -s tvkitHome`.
4. Home button: stock launchers often register Home at intent priority 2, and installed apps are capped at 0, so `tvkit home set` reports Success but changes nothing (seen on this TCL). `tvkit home swap dev.tvkit.home` switches off the stock launcher only after the user agrees. It then verifies that Home resolves to, and opens, tvkit Home, and switches the stock launcher back on by itself if not. Undo: `tvkit undo`.

Prior art: Mihir Gupta's Apple-TV-style launcher for a TCL Google TV (github.com/mihirgupta0900/tv-home).

## 8. Wrap up

- Leave the TV on its Home screen.
- Give the user the artifact link or the local file, the wallpaper PNG path, the renders (handy for a LinkedIn post or README), and the tier they chose with its next step.
- Saved outputs live in `<dir>`. Keep personal screenshots out of git repositories.
