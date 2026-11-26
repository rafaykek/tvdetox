---
name: connect
description: Connect Claude Code to an Android TV or Google TV (TCL, Hisense, Sony, Philips, Xiaomi, Chromecast with Google TV) over Wi-Fi ADB. Finds the TV on the network, walks the user through Developer options and debugging, handles Android 11+ pairing codes and the "Allow debugging?" prompt, then saves a read-only baseline snapshot. Use when the user wants to connect, pair, set up or reconnect their TV, or when another tvkit skill reports that no TV is connected.
argument-hint: "[tv-ip or ip:port]"
---

# Connect a TV

`tvkit` below means `python3 "${CLAUDE_PLUGIN_ROOT}/bin/tvkit"`. Run it exactly like that.
Give the user TV-side steps one at a time, in plain words. They're holding a remote, not reading a manual.

## 1. Check this computer
Run `tvkit doctor`.
- adb missing: offer to install it (macOS `brew install --cask android-platform-tools`, Linux `sudo apt install adb`, Windows: Google's platform-tools zip). Ask before installing anything.
- Already connected (✓ ADB session): skip to step 5.

## 2. Make sure this TV can do ADB
ADB exists only on Android TV and Google TV. TCL also sells Roku TV models and older sets that run TCL's own OS. Samsung (Tizen) and LG (webOS) don't have ADB either. If the user isn't sure, ask them to open Settings. A Roku menu, or no "Android TV OS build" under About, means stop and explain that tvkit can't help with that TV.

## 3. Turn on debugging (on the TV)
1. Settings → System → About → highlight **Android TV OS build** and press OK 7 times, until it says "You are now a developer". On some TCL menus About is under Settings → Device Preferences.
2. Back to Settings → System → **Developer options** → turn on **USB debugging**. Despite the name, this is what allows Wi-Fi ADB on most TVs.
3. If Developer options also has **Wireless debugging** (Android 11+), turn it on and open it. It shows an "IP address & Port" and a "Pair device with pairing code" option.

## 4. Find the TV and connect
- If the user gave an IP in `$ARGUMENTS`, use it. Otherwise run `tvkit discover`. Many TVs don't announce themselves, so if nothing shows up run `tvkit discover --scan`. It probes the local network for TV ports (5555 ADB, 6466 Android TV remote, 8009 Cast) with plain TCP connects, so no prompt appears on any device. "Android/Google TV, debugging off" means the TV was found but step 3 isn't done yet. If the scan finds nothing either, ask for the IP from Settings → Network & Internet → (their network).
- Classic debugging: `tvkit connect <ip>` (port 5555).
- Wireless debugging: `tvkit pair <ip>:<pairing-port> <6-digit-code>`, then `tvkit connect <ip>:<port shown under "IP address & Port">`. The two ports differ, and both change whenever debugging is switched off and on.
- Before running connect, tell the user: "Your TV will ask **Allow debugging?** Tick **Always allow from this computer**, then choose **Allow**." tvkit waits 60 seconds for it.

## 5. Confirm and hand over
Run `tvkit status` and `tvkit info`. Summarise in one short paragraph: model, Android version, Google TV or Android TV, RAM, free storage, uptime. On first connect tvkit saves a **baseline snapshot** of the TV's current state. Tell the user that's the safety net for everything after.

Suggest what's next: `/tvkit:audit` (see what's on the TV; changes nothing), then `/tvkit:speedup`, `/tvkit:debloat` or `/tvkit:redesign`.

## Troubleshooting
| Symptom | Fix |
|---|---|
| `Connection refused` | Debugging is off, or Wireless debugging uses a different port. Re-check step 3 and use the IP:port the TV shows. |
| `No route to host` | Wrong IP, or a different network (guest Wi-Fi, VPN). On macOS, also allow the terminal / VS Code under System Settings → Privacy & Security → Local Network. |
| Times out | The TV is in standby. Wake it up. A DHCP reservation in the router stops the IP from changing. |
| Stuck on `unauthorized`, no prompt on the TV | Turn USB debugging off and on, run `adb kill-server`, then connect again. |
| Worked yesterday, not today | The IP or the wireless-debugging port changed. Run `tvkit discover`, then `tvkit connect`. |
| USB drives stop working while debugging is on | A known quirk on some TVs. Turn debugging off when you're done. |

## Security
While debugging is on, anyone on the local network who gets past the TV's Allow prompt can control it. Never approve a prompt you didn't trigger, never enable debugging on public networks, and turn it off when you're done: `tvkit lock` (ends access) or the toggle in Developer options.
