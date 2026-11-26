#!/usr/bin/env python3
"""A tiny stand-in for `adb` that emulates one TCL Google TV, so tvkit can be tested without a TV.

State lives in the JSON file named by FAKE_ADB_STATE and persists between calls.
Only the commands tvkit actually sends are implemented.
"""
import json
import os
import re
import sys

STATE_FILE = os.environ["FAKE_ADB_STATE"]
PNG = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4"
       b"\x89\x00\x00\x00\rIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82")
STATE_NAMES = {0: "default", 1: "enabled", 2: "disabled", 3: "disabled-user", 4: "disabled-until-used"}
UI_XML = ('<?xml version="1.0" encoding="UTF-8"?><hierarchy rotation="0">'
          '<node text="" content-desc="YouTube" focused="true" bounds="[0,0][200,100]"/>'
          '<node text="Settings" content-desc="" focused="false" bounds="[200,0][400,100]"/></hierarchy>')


def load():
    with open(STATE_FILE) as f:
        return json.load(f)


def save(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=1)


def comp(pkg, activity):
    return f"{pkg}/{activity}"


def pm_list(state, args):
    pkgs = state["packages"]
    flags = set(a for a in args if a.startswith("-"))
    filt = next((a for a in args if not a.startswith("-") and a != "0"), None)
    lines = []
    for name, p in sorted(pkgs.items()):
        installed = not p.get("uninstalled")
        if not installed and "-u" not in flags:
            continue
        if "-s" in flags and not p["system"]:
            continue
        if "-3" in flags and p["system"]:
            continue
        if "-d" in flags and p["state"] not in (2, 3, 4):
            continue
        if "-e" in flags and p["state"] in (2, 3, 4):
            continue
        if filt and filt not in name:
            continue
        lines.append(f"package:{name}" + (f" uid:{p['uid']}" if "-U" in flags else ""))
    return "\n".join(lines)


def resolve_home(state):
    """Like Android: the highest HOME intent priority wins outright; the preferred Home only breaks ties."""
    pkgs = state["packages"]
    cands = [(p.get("home_priority", 0), name) for name, p in pkgs.items()
             if p.get("home") and p["state"] not in (2, 3, 4) and not p.get("uninstalled")]
    if not cands:
        return "android/com.android.internal.app.ResolverActivity"
    top = max(pr for pr, _ in cands)
    best = sorted(name for pr, name in cands if pr == top)
    preferred = state["home"].split("/")[0]
    name = preferred if preferred in best else best[0]
    return comp(name, pkgs[name]["home"])


def shell(state, cmd):
    pkgs = state["packages"]
    words = cmd.split()
    if not words:
        return ""
    if words[0] == "echo":
        return " ".join(words[1:])
    if words[0] == "getprop":
        if len(words) > 1:
            return state["props"].get(words[1], "")
        return "\n".join(f"[{k}]: [{v}]" for k, v in state["props"].items())
    if words[:2] == ["pm", "list"] and words[2] == "packages":
        return pm_list(state, words[3:])
    if words[:3] == ["pm", "list", "features"]:
        return "feature:android.software.leanback\nfeature:android.software.live_tv"
    if words[0] == "pm" and words[1] in ("disable-user", "enable", "default-state", "disable-until-used"):
        pkg = words[-1]
        if pkg not in pkgs:
            return f"Error: Unknown package: {pkg}"
        pkgs[pkg]["state"] = {"disable-user": 3, "enable": 1, "default-state": 0, "disable-until-used": 4}[words[1]]
        return f"Package {pkg} new state: {STATE_NAMES[pkgs[pkg]['state']]}"
    if words[:2] == ["pm", "trim-caches"]:
        state["df_avail_kb"] = state.get("df_avail_kb", 0) + 400000
        return ""
    if words[:3] == ["cmd", "package", "install-existing"]:
        pkgs[words[-1]]["uninstalled"] = False
        return f"Package {words[-1]} installed for user: 0"
    if words[:2] == ["dumpsys", "package"]:
        name = words[2]
        p = pkgs.get(name)
        if not p or p.get("uninstalled"):
            return ""
        flags = "SYSTEM HAS_CODE" if p["system"] else "HAS_CODE"
        if p.get("persistent"):
            flags += " PERSISTENT"
        user0 = ("    User 0: ceDataInode=1 installed=true hidden=false suspended=false stopped=false "
                 "notLaunched=false enabled={} instant=false virtual=false\n")
        # Updated system apps (like Google Assistant on a real TCL) have hundreds of permission lines and a
        # second, factory copy under "Hidden system packages:" whose User 0 state must not be read.
        perms = "".join(f"      android.permission.FAKE_{i}: granted=true\n" for i in range(400)) if p.get("big") else ""
        hidden = (f"\nHidden system packages:\n  Package [{name}] (9z9z9z):\n    userId={p['uid']}\n"
                  + user0.format(0)) if p.get("big") else ""
        return (f"Packages:\n  Package [{name}] (1a2b3c):\n    userId={p['uid']}\n    pkgFlags=[ {flags} ]\n"
                f"    runtime permissions:\n{perms}" + user0.format(p["state"]) + hidden)
    if words[:3] == ["dumpsys", "activity", "activities"]:
        return f"    mResumedActivity: ActivityRecord{{a1b2 u0 {resolve_home(state)} t1}}"
    if words[:2] == ["dumpsys", "meminfo"]:
        return "** MEMINFO in pid 1234 [x] **\n  TOTAL PSS:    93123            TOTAL RSS:   150000"
    if words[0] == "settings":
        op, ns = words[1], words[2]
        table = state["settings"].setdefault(ns, {})
        if op == "get":
            return table.get(words[3], "null")
        if op == "put":
            table[words[3]] = words[4]
            return ""
        if op == "delete":
            table.pop(words[3], None)
            return "Deleted 1 rows"
        if op == "list":
            return "\n".join(f"{k}={v}" for k, v in table.items())
    if words[:3] == ["cmd", "package", "resolve-activity"]:
        if "android.intent.category.HOME" in cmd:
            return "priority=0 preferredOrder=0 match=0x108000 specificIndex=-1 isDefault=true\n" + resolve_home(state)
        pkg = words[-1]
        p = pkgs.get(pkg)
        if p and p.get("launch") and p["state"] not in (2, 3, 4):
            return "priority=0 preferredOrder=0 match=0x108000 specificIndex=-1 isDefault=false\n" + comp(pkg, p["launch"])
        return "No activity found"
    if words[:3] == ["cmd", "package", "query-activities"]:
        key = "home" if "android.intent.category.HOME" in cmd else "launch"
        out = []
        for name, p in sorted(pkgs.items()):
            if p.get(key) and p["state"] not in (2, 3, 4) and not p.get("uninstalled"):
                out.append("priority=0 preferredOrder=0 match=0x108000 specificIndex=-1 isDefault=false")
                out.append("  " + comp(name, p[key]))
        return "\n".join(out)
    if words[:3] == ["cmd", "package", "set-home-activity"]:
        state["home"] = words[-1]
        return "Success"
    if words[:2] == ["wm", "size"]:
        return "Physical size: 1920x1080"
    if cmd == "cat /proc/meminfo":
        return "MemTotal:        2048000 kB\nMemFree:          100000 kB\nMemAvailable:     612000 kB"
    if words[:2] == ["df", "/data"]:
        total = 8000000
        avail = state.get("df_avail_kb", 1500000)
        return ("Filesystem       1K-blocks    Used Available Use% Mounted on\n"
                f"/dev/block/dm-5    {total} {total - avail}   {avail}  {100 * (total - avail) // total}% /data")
    if cmd == "cat /proc/uptime":
        return "1000000.00 2000000.00"
    if cmd == "head -1 /proc/stat":
        state["cpu_tick"] = state.get("cpu_tick", 0) + 1
        t = state["cpu_tick"]
        return f"cpu  {100 * t} 0 {50 * t} {1000 * t} {10 * t} 0 0 0 0 0"
    if words[0] in ("sleep", "mkdir", "rm", "input"):
        return ""
    if words[:2] == ["am", "force-stop"]:
        return ""
    if words[:2] == ["am", "start"]:
        target = words[-1]
        if "-W" in words:
            return (f"Starting: Intent {{ cmp={target} }}\nStatus: ok\nLaunchState: COLD\nActivity: {target}\n"
                    "TotalTime: 456\nWaitTime: 460\nComplete")
        return f"Starting: Intent {{ cmp={target} }}"
    if words[:2] == ["am", "broadcast"]:
        return "Broadcast completed: result=0"
    if words[0] == "uiautomator":
        return f"UI hierchary dumped to: {words[-1]}"
    sys.stderr.write(f"fake adb: unsupported shell command: {cmd}\n")
    return ""


def main():
    argv = sys.argv[1:]
    state = load()
    if argv[:1] == ["-s"]:
        argv = argv[2:]
    cmd = argv[0] if argv else ""
    if cmd == "version":
        print("Android Debug Bridge version 1.0.41 (fake)")
    elif cmd == "devices":
        print("List of devices attached")
        for serial, st in state["devices"].items():
            print(f"{serial}\t{st}")
    elif cmd == "connect":
        target = argv[1]
        if target in state["devices"]:
            print(f"already connected to {target}")
        else:
            state["devices"][target] = "device"
            print(f"connected to {target}")
    elif cmd == "disconnect":
        state["devices"].pop(argv[1], None)
        print(f"disconnected {argv[1]}")
    elif cmd == "mdns":
        print("List of discovered mdns services")
    elif cmd == "shell":
        outputs = [shell(state, part.strip()) for part in " ".join(argv[1:]).split("; ")]
        text = "\n".join(o for o in outputs)
        if text:
            print(text)
    elif cmd == "exec-out":
        if argv[1:3] == ["screencap", "-p"]:
            sys.stdout.buffer.write(PNG)
        elif argv[1] == "cat":
            sys.stdout.write(UI_XML)
    elif cmd == "push":
        print(f"{argv[1]}: 1 file pushed, 0 skipped.")
    elif cmd == "reboot":
        pass
    else:
        sys.stderr.write(f"fake adb: unsupported: {argv}\n")
        save(state)
        return 1
    save(state)
    return 0


if __name__ == "__main__":
    sys.exit(main())
