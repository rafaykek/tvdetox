"""End-to-end tests for the tvkit CLI, against a fake TCL Google TV.

Run: python3 -m unittest discover -s tests -v
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TVKIT = ROOT / "bin" / "tvkit"
FAKE_ADB = Path(__file__).resolve().parent / "fake_adb.py"
SERIAL = "192.168.1.50:5555"


def fake_tv():
    def pkg(uid, system=True, state=0, **extra):
        return dict(uid=uid, system=system, state=state, **extra)
    return {
        "devices": {},
        "props": {"ro.product.model": "55C645", "ro.product.brand": "TCL", "ro.product.manufacturer": "TCL",
                  "ro.build.version.release": "12", "ro.build.version.sdk": "31",
                  "ro.build.fingerprint": "TCL/55C645/fake:12/userbuild", "ro.serialno": "FAKE123",
                  "ro.build.version.security_patch": "2025-12-05"},
        "home": "com.google.android.apps.tv.launcherx/.home.HomeActivity",
        "settings": {"global": {"window_animation_scale": "1.0", "transition_animation_scale": "1.0"},
                     "secure": {"default_input_method":
                                "com.google.android.inputmethod.latin/com.android.inputmethod.latin.LatinIME"},
                     "system": {}},
        "packages": {
            "com.google.android.apps.tv.launcherx": pkg(10050, home=".home.HomeActivity"),
            "com.google.android.inputmethod.latin": pkg(10051),
            "com.google.android.katniss": pkg(10052, big=True),
            "com.tcl.suspension": pkg(10060),
            "com.tcl.browser": pkg(10061, launch=".MainActivity"),
            "com.tcl.bootadservice": pkg(10062),
            "com.tcl.smartalexa": pkg(10063),
            "com.tcl.gallery": pkg(1000, launch=".Gallery"),
            "com.tcl.mystery": pkg(10064),
            "com.tcl.inputhelper": pkg(10065),
            "com.tcl.persist": pkg(10066, persistent=True),
            "com.netflix.ninja": pkg(10080, launch=".MainActivity"),
            "com.google.android.youtube.tv": pkg(10081, launch="com.google.android.apps.youtube.tv.activity.ShellActivity"),
            "com.android.tv.settings": pkg(1000, home=".FallbackHome", home_priority=-1000),
            "com.spocky.projengmenu": pkg(10101, system=False, launch=".ui.home.MainActivity",
                                          home=".ui.home.MainActivity"),
            "com.example.userapp": pkg(10102, system=False, launch=".Main"),
        },
    }


class TvkitTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        tmp = Path(self.tmp.name)
        self.state_file = tmp / "fake-tv.json"
        self.state_file.write_text(json.dumps(fake_tv()))
        adb_wrapper = tmp / "adb"
        adb_wrapper.write_text(f"#!/bin/sh\nexec \"{sys.executable}\" \"{FAKE_ADB}\" \"$@\"\n")
        adb_wrapper.chmod(0o755)
        self.env = dict(os.environ, TVKIT_ADB=str(adb_wrapper), TVKIT_HOME=str(tmp / "home"),
                        FAKE_ADB_STATE=str(self.state_file), TVKIT_SLEEP_SCALE="0")
        self.env.pop("TVKIT_DEVICE", None)
        out = self.tvkit("connect", "192.168.1.50")
        self.assertEqual(out.returncode, 0, out.stderr)

    def tearDown(self):
        self.tmp.cleanup()

    def tvkit(self, *args):
        return subprocess.run([sys.executable, str(TVKIT), *args], env=self.env, capture_output=True, text=True,
                              timeout=60)

    def tv(self):
        return json.loads(self.state_file.read_text())

    def pkg_state(self, pkg):
        return self.tv()["packages"][pkg]["state"]


class ConnectAndRead(TvkitTestCase):
    def test_connect_saves_device_and_baseline(self):
        home = Path(self.env["TVKIT_HOME"])
        self.assertEqual(json.loads((home / "config.json").read_text())["device"], SERIAL)
        snaps = list(home.glob("devices/*/snapshots/*-baseline"))
        self.assertEqual(len(snaps), 1)
        self.assertIn("com.tcl.browser", (snaps[0] / "packages.txt").read_text())

    def test_info_json(self):
        info = json.loads(self.tvkit("info", "--json").stdout)
        self.assertEqual(info["model"], "55C645")
        self.assertTrue(info["google_tv"])
        self.assertEqual(info["home_package"], "com.google.android.apps.tv.launcherx")
        self.assertAlmostEqual(info["storage_free_gb"], 1.43, places=2)
        self.assertEqual(info["keyboard"], "com.google.android.inputmethod.latin")

    def test_audit_classifies(self):
        report = json.loads(self.tvkit("audit", "--json").stdout)
        tiers = {r["package"]: (r["tier"], r["live_protection"]) for r in report["packages"]}
        self.assertEqual(tiers["com.tcl.suspension"][0], "protected")
        self.assertEqual(tiers["com.tcl.inputhelper"][0], "protected")     # keyword rule
        self.assertEqual(tiers["com.tcl.mystery"][0], "unknown")
        self.assertEqual(tiers["com.example.userapp"][0], "user-app")
        self.assertEqual(tiers["com.tcl.gallery"][1], "system user (uid 1000)")
        self.assertEqual(tiers["com.google.android.apps.tv.launcherx"][1], "current Home app")
        bloat = {r["package"] for r in report["bloat_candidates"]}
        self.assertEqual(bloat, {"com.tcl.browser", "com.tcl.bootadservice", "com.tcl.smartalexa"})
        self.assertTrue(any(f["level"] == "high" for f in report["findings"]))  # low storage

    def test_apps_json_contract(self):
        apps = json.loads(self.tvkit("apps", "--launchable", "--json").stdout)
        netflix = next(a for a in apps if a["package"] == "com.netflix.ninja")
        self.assertEqual(netflix["label"], "Netflix")
        self.assertEqual(set(netflix), {"package", "label", "activity", "system", "enabled", "tier"})

    def test_key_and_long_press(self):
        self.assertEqual(self.tvkit("key", "HOME", "DOWN").returncode, 0)
        self.assertEqual(self.tvkit("key", "CENTER", "--long").returncode, 0)
        self.assertEqual(self.tvkit("key", "NOT_A_KEY").returncode, 1)

    def test_screenshot_and_ui_dump(self):
        shot = self.tvkit("screenshot", "home")
        self.assertEqual(shot.returncode, 0, shot.stderr)
        path = Path(shot.stdout.strip().splitlines()[-1])
        self.assertTrue(path.read_bytes().startswith(b"\x89PNG"))
        dump = self.tvkit("ui-dump")
        self.assertEqual(dump.returncode, 0, dump.stderr)
        self.assertIn("YouTube", dump.stdout)


class DisableSafety(TvkitTestCase):
    def test_plan_only_without_yes(self):
        out = self.tvkit("disable", "com.tcl.browser")
        self.assertEqual(out.returncode, 2)
        self.assertIn("Plan only", out.stdout)
        self.assertEqual(self.pkg_state("com.tcl.browser"), 0)

    def test_disable_then_undo_restores_exact_state(self):
        out = self.tvkit("disable", "com.tcl.browser", "com.tcl.bootadservice", "--yes")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertEqual(self.pkg_state("com.tcl.browser"), 3)
        self.assertEqual(self.pkg_state("com.tcl.bootadservice"), 3)
        undo = self.tvkit("undo", "--yes")
        self.assertEqual(undo.returncode, 0, undo.stdout + undo.stderr)
        self.assertEqual(self.pkg_state("com.tcl.browser"), 0)
        self.assertEqual(self.pkg_state("com.tcl.bootadservice"), 0)
        self.assertIn("Nothing to undo", self.tvkit("undo", "--yes").stdout)

    def test_protected_from_breakage_reports(self):
        out = self.tvkit("disable", "com.tcl.suspension", "--yes", "--allow-caution", "--allow-unknown")
        self.assertEqual(out.returncode, 3)
        self.assertIn("Inputs", out.stdout)
        self.assertEqual(self.pkg_state("com.tcl.suspension"), 0)

    def test_current_home_is_untouchable(self):
        out = self.tvkit("disable", "com.google.android.apps.tv.launcherx", "--yes", "--allow-caution")
        self.assertEqual(out.returncode, 3)
        self.assertIn("current Home app", out.stdout)

    def test_active_keyboard_is_untouchable(self):
        out = self.tvkit("disable", "com.google.android.inputmethod.latin", "--yes", "--allow-caution")
        self.assertEqual(out.returncode, 3)

    def test_system_uid_is_untouchable(self):
        out = self.tvkit("disable", "com.tcl.gallery", "--yes", "--allow-caution")
        self.assertEqual(out.returncode, 3)
        self.assertIn("uid 1000", out.stdout)

    def test_persistent_is_untouchable(self):
        out = self.tvkit("disable", "com.tcl.persist", "--yes", "--allow-unknown")
        self.assertEqual(out.returncode, 3)
        self.assertIn("persistent", out.stdout)

    def test_keyword_protected_even_with_allow_unknown(self):
        out = self.tvkit("disable", "com.tcl.inputhelper", "--yes", "--allow-unknown")
        self.assertEqual(out.returncode, 3)

    def test_unknown_and_caution_need_flags(self):
        self.assertEqual(self.tvkit("disable", "com.tcl.mystery", "--yes").returncode, 3)
        self.assertEqual(self.tvkit("disable", "com.tcl.mystery", "--yes", "--allow-unknown").returncode, 0)
        self.assertEqual(self.pkg_state("com.tcl.mystery"), 3)
        self.assertEqual(self.tvkit("disable", "com.google.android.katniss", "--yes").returncode, 3)
        self.assertEqual(self.tvkit("disable", "com.google.android.katniss", "--yes", "--allow-caution").returncode, 0)

    def test_long_dumpsys_block_is_verified(self):
        # Regression: on a real TCL (Android 9) Google Assistant's dumpsys block is >8 KB and is followed by a
        # "Hidden system packages" copy with enabled=0. Verification must read the live copy's state.
        out = self.tvkit("disable", "com.google.android.katniss", "--allow-caution", "--yes")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertIn("ok      com.google.android.katniss", out.stdout)
        explain = json.loads(self.tvkit("explain", "com.google.android.katniss", "--json").stdout)
        self.assertEqual(explain["device"]["enabled_state"], 3)
        undo = self.tvkit("undo", "--yes")
        self.assertIn("ok      com.google.android.katniss", undo.stdout)
        self.assertEqual(self.pkg_state("com.google.android.katniss"), 0)

    def test_batch_limit(self):
        out = self.tvkit("disable", "a.b1", "a.b2", "a.b3", "a.b4", "a.b5", "a.b6", "--yes")
        self.assertEqual(out.returncode, 3)

    def test_learn_cannot_unprotect(self):
        self.assertEqual(self.tvkit("learn", "com.tcl.suspension", "--tier", "bloat", "--label", "x", "--why", "x",
                                    "--source", "x").returncode, 3)
        self.assertEqual(self.tvkit("learn", "com.mediatek.foo", "--tier", "bloat", "--label", "x", "--why", "x",
                                    "--source", "x").returncode, 3)
        self.assertEqual(self.tvkit("learn", "com.tcl.mystery", "--tier", "bloat", "--label", "Mystery",
                                    "--why", "promo app", "--source", "https://example.com").returncode, 0)
        self.assertEqual(self.tvkit("disable", "com.tcl.mystery", "--yes").returncode, 0)

    def test_restore_baseline(self):
        self.tvkit("disable", "com.tcl.browser", "--yes")
        self.tvkit("disable", "com.tcl.smartalexa", "--yes")
        self.tvkit("animations", "0.5", "--yes")
        out = self.tvkit("restore", "baseline", "--yes")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertEqual(self.pkg_state("com.tcl.browser"), 0)
        self.assertEqual(self.pkg_state("com.tcl.smartalexa"), 0)
        self.assertEqual(self.tv()["settings"]["global"]["window_animation_scale"], "1.0")
        self.assertNotIn("animator_duration_scale", self.tv()["settings"]["global"])


class SettingsAndTools(TvkitTestCase):
    def test_animations_and_undo(self):
        out = self.tvkit("animations", "0.5", "--yes")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        g = self.tv()["settings"]["global"]
        self.assertEqual((g["window_animation_scale"], g["animator_duration_scale"]), ("0.5", "0.5"))
        self.assertEqual(self.tvkit("undo", "--yes").returncode, 0)
        g = self.tv()["settings"]["global"]
        self.assertEqual(g["window_animation_scale"], "1.0")
        self.assertNotIn("animator_duration_scale", g)   # was absent before, so it is deleted again

    def test_dangerous_settings_refused(self):
        for key in ("adb_enabled", "wifi_on", "device_provisioned"):
            self.assertEqual(self.tvkit("set", "global", key, "0", "--yes").returncode, 3, key)

    def test_cache_only_when_tight(self):
        self.assertEqual(self.tvkit("cache").returncode, 2)          # storage is tight in the fake TV: plan
        out = self.tvkit("cache", "--yes")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("GB free", out.stdout)

    def test_home_set_and_undo(self):
        home = json.loads(self.tvkit("home", "--json").stdout)
        self.assertNotIn("FallbackHome", " ".join(home["candidates"]))
        out = self.tvkit("home", "set", "com.spocky.projengmenu", "--yes")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertTrue(self.tv()["home"].startswith("com.spocky.projengmenu/"))
        self.assertEqual(self.tvkit("undo", "--yes").returncode, 0)
        self.assertTrue(self.tv()["home"].startswith("com.google.android.apps.tv.launcherx/"))

    def outrank_stock_launcher(self, **extra_packages):
        tv = self.tv()
        tv["packages"]["com.google.android.apps.tv.launcherx"]["home_priority"] = 2   # like the real TCL
        tv["packages"].update(extra_packages)
        self.state_file.write_text(json.dumps(tv))

    def test_home_set_is_ignored_when_stock_outranks(self):
        self.outrank_stock_launcher()
        out = self.tvkit("home", "set", "com.spocky.projengmenu", "--yes")
        self.assertIn("resolves to com.google.android.apps.tv.launcherx", out.stdout)

    def test_home_swap_and_undo(self):
        self.outrank_stock_launcher()
        self.assertEqual(self.tvkit("home", "swap", "com.spocky.projengmenu").returncode, 2)   # plan only
        out = self.tvkit("home", "swap", "com.spocky.projengmenu", "--yes")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertEqual(self.pkg_state("com.google.android.apps.tv.launcherx"), 3)
        self.assertTrue(json.loads(self.tvkit("home", "--json").stdout)["current"].startswith("com.spocky.projengmenu/"))
        self.assertEqual(self.tvkit("undo", "--yes").returncode, 0)
        self.assertEqual(self.pkg_state("com.google.android.apps.tv.launcherx"), 0)

    def test_home_swap_rolls_back_when_setup_takes_home(self):
        # The documented trap: with the stock launcher off, Google's setup app can grab Home instead.
        self.outrank_stock_launcher(**{"com.google.android.tungsten.setupwraith": {
            "uid": 10400, "system": True, "state": 0, "home": ".MainActivity", "home_priority": 1}})
        out = self.tvkit("home", "swap", "com.spocky.projengmenu", "--yes")
        self.assertEqual(out.returncode, 1)
        self.assertIn("switched back on", out.stderr)
        self.assertEqual(self.pkg_state("com.google.android.apps.tv.launcherx"), 0)
        self.assertIn("Nothing to undo", self.tvkit("undo", "--yes").stdout)

    def test_bench_and_compare(self):
        for label in ("before", "after"):
            out = self.tvkit("bench", "--label", label, "--runs", "2", "--yes")
            self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        cmp = self.tvkit("bench-compare", "before", "after", "--json")
        data = json.loads(cmp.stdout)
        self.assertTrue(data["apps"])
        self.assertTrue(all(a["verdict"].startswith("no real change") for a in data["apps"]))

    def test_journal_lists_changes(self):
        self.tvkit("disable", "com.tcl.browser", "--yes")
        rows = json.loads(self.tvkit("journal", "--json").stdout)
        self.assertEqual([(r["target"], r["active"]) for r in rows], [("com.tcl.browser", True)])


class Discovery(unittest.TestCase):
    def setUp(self):
        import importlib.machinery
        import importlib.util
        loader = importlib.machinery.SourceFileLoader("tvkit_module", str(TVKIT))
        spec = importlib.util.spec_from_loader("tvkit_module", loader)
        self.tvkit = importlib.util.module_from_spec(spec)
        loader.exec_module(self.tvkit)

    def test_tcp_scan_reports_only_open_ports(self):
        import socket
        server = socket.socket()
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        port = server.getsockname()[1]
        try:
            found = self.tvkit.tcp_scan(["127.0.0.1"], [port, 1], timeout=0.5)
        finally:
            server.close()
        self.assertEqual(found, {"127.0.0.1": {port}})

    def test_status_labels(self):
        status = self.tvkit.discover_status
        self.assertEqual(status({"adb_port": 5555, "services": ["adb:5555"]}), "ADB ready")
        self.assertTrue(status({"services": ["android-tv-remote:6466", "cast:8009"]}).startswith("Android"))
        self.assertTrue(status({"services": ["cast:8009"]}).startswith("Cast"))


if __name__ == "__main__":
    unittest.main()
