"""Tests for the PreToolUse guard hook that blocks destructive ADB commands before they reach the TV.

Run: python3 -m unittest discover -s tests -v
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

GUARD = Path(__file__).resolve().parent.parent / "hooks" / "adb_guard.py"


class Guard(unittest.TestCase):
    ALLOWED = [
        "ls -la",
        "echo 'pm uninstall' > notes.txt",
        "python3 bin/tvkit disable com.tcl.browser --yes",
        "adb devices",
        "adb connect 192.168.1.50:5555",
        "adb -s 192.168.1.50:5555 shell getprop ro.product.model",
        "adb shell pm list packages -s | grep tcl",
        "adb shell 'dumpsys package com.tcl.tv | grep -i enabled'",
        "adb exec-out screencap -p > shot.png",
        "adb shell input keyevent KEYCODE_HOME",
        "adb shell settings get global window_animation_scale",
        "adb shell pm enable --user 0 com.tcl.browser",
        "adb shell cmd package install-existing com.tcl.browser",
        "adb reboot",
        "adb shell rm -f /sdcard/tvkit-ui.xml",
        "adb pull /sdcard/x.png . && rm x.png",
        "adb logcat -d | tail -n 50",
        "adb install FLauncher.apk",
        "adb push wall.png /sdcard/Pictures/tvkit/wall.png",
        "adb shell pm clear --cache-only com.netflix.ninja",
    ]
    BLOCKED = [
        "adb shell pm uninstall com.tcl.browser",
        "adb shell pm uninstall -k --user 0 com.tcl.browser",
        "adb uninstall com.example.app",
        "adb -s 1.2.3.4:5555 shell \"pm disable-user --user 0 com.tcl.suspension\"",
        "adb shell cmd package disable-user com.x",
        "adb shell pm clear com.netflix.ninja",
        "adb shell settings put global adb_enabled 0",
        "adb shell settings put global window_animation_scale 0.5",
        "adb reboot bootloader",
        "adb reboot recovery",
        "fastboot flash boot boot.img",
        "adb shell rm -rf /data/local/tmp/*",
        "adb shell 'rm -rf /sdcard/Movies'",
        "adb shell svc wifi disable",
        "adb shell am broadcast -a android.intent.action.MASTER_CLEAR",
        "adb shell setprop persist.sys.foo 1",
        "adb shell",
        "echo 'getprop' | adb shell",
        "adb shell < script.sh",
        "adb logcat",
        "adb push evil.so /system/lib/",
        "adb shell sh /sdcard/do_everything.sh",
        "adb shell cmd package set-home-activity com.x/.Main",
        "adb root",
        "adb remount",
        "ADB=adb; $ADB shell pm uninstall x",
        "python3 -c \"import subprocess; subprocess.run(['adb','shell','pm','uninstall','x'])\"",
        "adb shell 'true; pm uninstall com.x'",
        "adb shell dd if=/dev/zero of=/dev/block/mmcblk0",
    ]

    def guard(self, command, env=None):
        event = {"tool_name": "Bash", "tool_input": {"command": command}, "hook_event_name": "PreToolUse"}
        with tempfile.TemporaryDirectory() as home:
            e = dict(os.environ, TVKIT_HOME=home, **(env or {}))
            e.pop("TVKIT_GUARD", None) if not env else None
            return subprocess.run([sys.executable, str(GUARD)], input=json.dumps(event), capture_output=True,
                                  text=True, env=e, timeout=10)

    def test_allowed(self):
        for command in self.ALLOWED:
            with self.subTest(command=command):
                res = self.guard(command)
                self.assertEqual(res.returncode, 0, res.stderr)

    def test_blocked(self):
        for command in self.BLOCKED:
            with self.subTest(command=command):
                res = self.guard(command)
                self.assertEqual(res.returncode, 2, f"not blocked: {command}")
                self.assertIn("tvkit guard blocked", res.stderr)

    def test_user_can_switch_off(self):
        self.assertEqual(self.guard("adb shell pm uninstall x", env={"TVKIT_GUARD": "off"}).returncode, 0)

    def test_other_tools_ignored(self):
        event = {"tool_name": "Read", "tool_input": {"file_path": "/x"}}
        res = subprocess.run([sys.executable, str(GUARD)], input=json.dumps(event), capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)


if __name__ == "__main__":
    unittest.main()
