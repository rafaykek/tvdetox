#!/usr/bin/env python3
"""tvkit guard: a Claude Code PreToolUse hook that blocks destructive ADB / fastboot commands.

Claude may run read-only adb commands freely (getprop, dumpsys, pm list, screencap, input, ...).
Anything that changes the TV must go through `tvkit`, which snapshots first, checks the protected
list and live device facts, and journals an exact undo. This hook enforces that at the tool-call
level, so a mistaken `pm uninstall`, `settings put global adb_enabled 0` or `fastboot` never
reaches the TV.

Contract: reads the PreToolUse JSON on stdin; exit 0 allows, exit 2 blocks (reason on stderr,
which Claude sees). Blocked commands are logged to ~/.tvkit/guard.log.
Only the user can switch it off: start Claude Code with TVKIT_GUARD=off.
"""
import datetime
import json
import os
import re
import shlex
import sys

STATE = os.path.expanduser(os.environ.get("TVKIT_HOME") or "~/.tvkit")
SAFE_RM_PREFIXES = ("/sdcard/tvkit", "/sdcard/Pictures/tvkit", "/storage/emulated/0/tvkit",
                    "/storage/emulated/0/Pictures/tvkit", "/data/local/tmp/tvkit")
SAFE_PUSH_PREFIXES = ("/sdcard/", "/storage/", "/data/local/tmp/")
ADB_NAMES = ("adb", "adb.exe")
GLOBAL_OPTS_WITH_VALUE = {"-s", "-t", "-H", "-P", "-L"}
PUNCT = set("();<>|&")

# Checked against the whole command whenever it mentions adb or fastboot. These strings have no
# business in a local command next to adb, so scanning everything errs on the safe side.
RULES = [
    (r"\bfastboot\b",
     "fastboot flashes or erases partitions; one wrong command can brick the TV."),
    (r"\breboot(?:-bootloader\b|\s+(?:bootloader|recovery|fastboot|sideload(?:-auto-reboot)?|edl|download|safemode)\b)",
     "rebooting into bootloader/recovery/fastboot is outside tvkit's safe scope. A normal restart is fine: `tvkit reboot`."),
    (r"\b(?:pm|cmd\s+package)\s+uninstall\b",
     "uninstalling can't be undone the way disabling can. Use `tvkit disable <package>` (snapshot + undo)."),
    (r"\b(?:pm|cmd\s+package)\s+(?:disable(?:-user|-until-used)?|hide|suspend)\b",
     "package changes must go through `tvkit disable`, which checks the protected list and live device facts and journals an exact undo."),
    (r"\b(?:pm|cmd\s+package)\s+clear\b(?![^;&|\n]*--cache-only)",
     "`pm clear` wipes the app's data and logins. To free space, use `tvkit cache`."),
    (r"\b(?:pm|cmd\s+package)\s+uninstall-system-updates\b",
     "this rolls apps back to factory versions; it isn't journaled by tvkit."),
    (r"\bsettings\s+(?:put|delete|reset)\b",
     "settings changes must go through `tvkit set` / `tvkit unset` / `tvkit animations`, so the old value is journaled and undoable."),
    (r"\bcmd\s+role\s+(?:add|remove|clear)-role-holder\b|\b(?:pm|cmd\s+package)\s+set-home-activity\b",
     "launcher changes must go through `tvkit home set` (journaled and verified)."),
    (r"\bsvc\s+(?:wifi|data|ethernet)\s+disable\b|\bcmd\s+wifi\s+set-wifi-enabled\s+disabled\b"
     r"|\bifconfig\s+\S+\s+down\b|\bip\s+link\s+set\s+\S+\s+down\b|\bcmd\s+connectivity\s+airplane-mode\s+enable\b",
     "this would cut the TV's network, and this ADB connection with it; getting back needs the physical remote."),
    (r"MASTER_CLEAR|FACTORY_RESET|--wipe_data|\bwipe\s+data\b|\brecovery\s+--wipe",
     "factory-reset commands are never run here; they erase every app, login and setting."),
    (r"(?:^|[\s;&|'\"(])(?:dd|mkfs(?:\.\w+)?|mke2fs|make_ext4fs|flash_image|blkdiscard|sgdisk|parted)\s",
     "raw disk/partition tools can brick the TV."),
    (r"\bsetprop\b",
     "setprop changes system properties, and some persist across reboots."),
    (r"\bcontent\s+(?:insert|update|delete)\b",
     "writing to content providers bypasses tvkit's journal."),
    (r"\bcmd\s+overlay\s+(?:enable|disable)\b",
     "toggling system overlays can break the TV's UI."),
]

# Used only when the command can't be parsed (unbalanced quotes etc.).
FALLBACK_RULES = [
    (r"\badb(?:\.exe)?\b[^;&|\n]*\s(?:uninstall|sideload|disable-verity|enable-verity|remount|root|unroot)\b",
     "this adb subcommand is outside tvkit's safe scope."),
    (r"\badb(?:\.exe)?\b[^\n]*\brm\s",
     "deleting files on the TV is blocked unless it is clearly one of tvkit's own temp files."),
]


def block(reason, command):
    try:
        os.makedirs(STATE, exist_ok=True)
        with open(os.path.join(STATE, "guard.log"), "a") as f:
            f.write(json.dumps({"ts": datetime.datetime.now().isoformat(timespec="seconds"),
                                "reason": reason, "command": command[:500]}) + "\n")
    except OSError:
        pass
    shown = command if len(command) <= 300 else command[:297] + "..."
    sys.stderr.write(
        "tvkit guard blocked this command.\n"
        f"Reason: {reason}\n"
        f"Command: {shown}\n"
        "Make TV changes with tvkit (it snapshots, checks safety rules and journals an undo). Run read-only "
        "adb commands one at a time. Only the user can turn this guard off (TVKIT_GUARD=off when starting "
        "Claude Code); don't try to work around it.\n")
    sys.exit(2)


def tokenize(command):
    lex = shlex.shlex(command.replace("\n", " ; "), posix=True, punctuation_chars=True)
    lex.whitespace_split = True
    lex.commenters = ""
    return list(lex)


def is_operator(token):
    return bool(token) and all(c in PUNCT for c in token)


def adb_invocations(tokens):
    """Yield (args, token_before, token_after) for every adb call in the token stream."""
    i = 0
    while i < len(tokens):
        if os.path.basename(tokens[i]).lower() in ADB_NAMES:
            j = i + 1
            while j < len(tokens) and not is_operator(tokens[j]):
                j += 1
            yield tokens[i + 1:j], (tokens[i - 1] if i else None), (tokens[j] if j < len(tokens) else None)
            i = j
        else:
            i += 1


def strip_global_opts(args):
    args = list(args)
    while args and args[0].startswith("-"):
        args = args[2:] if args[0] in GLOBAL_OPTS_WITH_VALUE else args[1:]
    return args


def check_device_command(device_cmd, command):
    for m in re.finditer(r"(?:^|[\s;&|(])rm\s+([^;&|\n]*)", device_cmd):
        paths = [t for t in m.group(1).split() if not t.startswith("-")]
        bad = [p for p in paths if not p.strip("'\"").startswith(SAFE_RM_PREFIXES)]
        if bad:
            block(f"deleting files on the TV ({', '.join(bad)}) is blocked; only tvkit's own temp files "
                  "may be removed.", command)
    if re.match(r"\s*(?:sh|bash|mksh|ash)\s+(?!-c\b)\S", device_cmd):
        block("running a script file on the TV hides what it does; run commands one at a time.", command)
    if re.search(r"(?:^|[\s;&|(])su(?:\s|$)", device_cmd):
        block("root shells are outside tvkit's scope.", command)


def check_invocation(args, before, after, command):
    rest = strip_global_opts(args)
    if not rest:
        return
    sub, params = rest[0], rest[1:]
    if sub in ("uninstall",):
        block("uninstalling can't be undone the way disabling can. Use `tvkit disable <package>`.", command)
    if sub in ("sideload", "disable-verity", "enable-verity", "remount", "root", "unroot", "reboot-bootloader"):
        block(f"`adb {sub}` is outside tvkit's safe scope.", command)
    if sub == "logcat" and not any(p in ("-d", "-c", "--clear") or p.startswith(("-t", "-d")) for p in params):
        block("`adb logcat` without -d streams forever and would hang this session. Use `adb logcat -d | tail -n 200`.",
              command)
    if sub == "push" and params:
        dest = params[-1].strip("'\"")
        if not dest.startswith(SAFE_PUSH_PREFIXES):
            block(f"pushing files to {dest} is blocked; use /sdcard/ (e.g. `tvkit push-wallpaper`).", command)
    if sub in ("shell", "exec-out"):
        i = 0
        while i < len(params) and re.fullmatch(r"-[tTnxe]", params[i]):
            i += 1
        device_args = params[i:]
        if not device_args:
            if before == "|" or (after or "").startswith("<"):
                block("feeding commands to `adb shell` through stdin hides them from safety checks; pass each "
                      "command as an argument instead.", command)
            block("an interactive `adb shell` would hang this session; pass the command, e.g. "
                  "`adb shell getprop ro.product.model`.", command)
        check_device_command(" ".join(device_args), command)


def main():
    if os.environ.get("TVKIT_GUARD", "").lower() in ("off", "0", "false"):
        return 0
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0
    if event.get("tool_name") != "Bash":
        return 0
    command = (event.get("tool_input") or {}).get("command") or ""
    if not re.search(r"\b(?:adb|fastboot)\b", command, re.I):
        return 0
    # Also scan a copy with quotes, commas and brackets flattened, so argv-style lists such as
    # subprocess.run(['adb', 'shell', 'pm', 'uninstall', ...]) read like the shell command they become.
    flattened = re.sub(r"[\"'`,\[\]{}()]+", " ", command)
    for text in (command, flattened):
        for pattern, reason in RULES:
            if re.search(pattern, text):
                block(reason, command)
    try:
        tokens = tokenize(command)
    except ValueError:
        for pattern, reason in FALLBACK_RULES:
            if re.search(pattern, command):
                block(reason + " (The command also couldn't be parsed; simplify the quoting.)", command)
        return 0
    for args, before, after in adb_invocations(tokens):
        check_invocation(args, before, after, command)
    return 0


if __name__ == "__main__":
    sys.exit(main())
