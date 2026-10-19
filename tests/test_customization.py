"""Real pinned Packwiz + Java protection E2E in disposable Minecraft fixtures.

No Minecraft/Prism installation is searched, launched, or modified. HTTP serves
only generated fixture data over loopback. Set COZY_REQUIRE_E2E=1 in CI, and
PACKWIZ_INSTALLER_JAR to the SHA-256-pinned v0.5.14 JAR. COZY_TEST_JAR can select
an already-built protection JAR. ACA_TEST_REPORT writes hash inventories/logs.
"""
from __future__ import annotations

import functools
import hashlib
import http.server
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import tomllib
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_prism
import build_serverpack

EVIDENCE = []
TEST_RESULTS = []


def sha(data):
    return hashlib.sha256(data).hexdigest()


def inventory(root):
    """Hash every regular fixture file; do not follow a hostile symlink."""
    result = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            result[relative] = {"symlink": str(path.readlink())}
        elif path.is_file():
            raw = path.read_bytes()
            result[relative] = {"bytes": len(raw), "sha256": sha(raw)}
    return result


def gameplay(files):
    return {name: value for name, value in files.items() if not name.startswith(".cozy/")}


class Fixture:
    def __init__(self, testcase, label):
        self.testcase, self.label = testcase, label
        self.temporary = tempfile.TemporaryDirectory(prefix="cozy-isolated-e2e-")
        testcase.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.source = self.base / "source"
        self.minecraft = self.base / "Prism Instance with spaces" / "minecraft"
        self.source.mkdir()
        self.minecraft.mkdir(parents=True)
        (self.minecraft.parent / "mmc-pack.json").write_text(json.dumps({"formatVersion": 1, "components": [
            {"uid": "net.minecraft", "version": "26.3"},
            {"uid": "net.fabricmc.fabric-loader", "version": "0.19.5"}]}), encoding="utf-8")
        self.faults = {}
        self.requests = []
        self.block = threading.Event()
        self.release = threading.Event()
        fixture = self

        class Handler(http.server.SimpleHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def do_GET(self):
                fixture.requests.append(self.path)
                mode = fixture.faults.get(self.path)
                if mode in ("block", "block-once"):
                    if mode == "block-once":
                        fixture.faults.pop(self.path, None)
                    fixture.block.set()
                    fixture.release.wait(20)
                elif mode == "truncate":
                    data = (fixture.source / self.path.lstrip("/")).read_bytes()
                    self.send_response(200)
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data[:max(1, len(data) // 2)])
                    self.wfile.flush()
                    self.close_connection = True
                    return
                try:
                    super().do_GET()
                except (ConnectionError, BrokenPipeError):
                    pass

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0),
            functools.partial(Handler, directory=str(self.source)))
        self.server.daemon_threads = True
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        testcase.addCleanup(self.close)
        self.jar = testcase.jar
        self.revision = 0
        self.pack_version = None
        self.specs = self.defaults()
        self.publish()

    def close(self):
        self.release.set()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    @staticmethod
    def defaults():
        return {
            "mods/gameplay.pw.toml": {"filename": "gameplay.jar", "name": "Gameplay", "data": b"required-v1"},
            "mods/colorlight.pw.toml": {"filename": "colorlight.jar", "name": "ColorLight", "data": b"colorlight-v1", "optional": True},
            "resourcepacks/cozy.pw.toml": {"filename": "cozy.zip", "name": "Cozy Resources", "data": b"official-resources-v1", "optional": True},
            "config/cozy.json": {"data": b'{"seed":1}\n'},
        }

    def write(self, relative, data):
        target = self.minecraft / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data if isinstance(data, bytes) else data.encode())
        return target

    def read(self, relative):
        return (self.minecraft / relative).read_bytes()

    def state(self):
        return json.loads(self.read(".cozy/state.json"))

    def publish(self):
        self.revision += 1
        files = []
        for identifier, spec in sorted(self.specs.items()):
            target = self.source / identifier
            target.parent.mkdir(parents=True, exist_ok=True)
            metafile = identifier.endswith(".pw.toml")
            if metafile:
                payload = self.source / "downloads" / spec["filename"]
                payload.parent.mkdir(exist_ok=True)
                payload.write_bytes(spec["data"])
                side = "client" if spec.get("optional") or identifier.startswith("resourcepacks/") else "both"
                raw = (f'name = {json.dumps(spec["name"])}\nfilename = {json.dumps(spec["filename"])}\nside = "{side}"\n'
                       f'[download]\nurl = "{self.url}/downloads/{spec["filename"]}"\nhash-format = "sha256"\nhash = "{sha(spec["data"])}"\n')
                if spec.get("optional"):
                    raw += '[option]\noptional = true\ndefault = true\ndescription = "Fixture option"\n'
                raw = raw.encode()
            else:
                raw = spec["data"]
            target.write_bytes(raw)
            files.append(f'[[files]]\nfile = {json.dumps(identifier)}\nhash = "{sha(raw)}"\n' + ('metafile = true\n' if metafile else ''))
        index = ('hash-format = "sha256"\n\n' + '\n'.join(files)).encode()
        (self.source / "index.toml").write_bytes(index)
        pack = (f'name = "A Cozy Adventure Test Fixture"\nauthor = "E2E"\nversion = "0.0.{self.revision}"\npack-format = "packwiz:1.1.0"\n'
                f'[index]\nfile = "index.toml"\nhash-format = "sha256"\nhash = "{sha(index)}"\n'
                '[versions]\nminecraft = "26.3"\nfabric = "0.19.5"\n').encode()
        if self.pack_version:
            pack = pack.replace(f'version = "0.0.{self.revision}"'.encode(), f'version = "{self.pack_version}"'.encode())
        (self.source / "pack.toml").write_bytes(pack)

    def command(self):
        return ["java", "-Djava.awt.headless=true", "-jar", str(self.jar), "--pack", self.url + "/pack.toml", "--headless"]

    def run(self, step, *, success=True, native=False):
        before = inventory(self.minecraft)
        command = self.command()
        if native:
            command = ["java", "-Djava.awt.headless=true", "-cp", str(self.testcase.native),
                       "link.infra.packwiz.installer.Main", "-g", "-s", "client", "--multimc-folder", ".", self.url + "/pack.toml"]
        process = subprocess.run(command, cwd=self.minecraft, capture_output=True, text=True, timeout=90)
        after = inventory(self.minecraft)
        EVIDENCE.append({"scenario": self.label, "step": step, "actualPinnedInstaller": True,
                         "nativeDirect": native, "returncode": process.returncode,
                         "expectedSuccess": success, "exitExpectationMet": (process.returncode == 0) == success,
                         "stdout": process.stdout, "stderr": process.stderr,
                         "installerLog": (self.minecraft / ".cozy/installer.log").read_text(errors="replace")
                             if (self.minecraft / ".cozy/installer.log").exists() else None,
                         "before": before, "after": after})
        if success:
            self.testcase.assertEqual(process.returncode, 0, process.stdout + process.stderr + str(EVIDENCE[-1]["installerLog"]))
        else:
            self.testcase.assertNotEqual(process.returncode, 0, "Unsafe update unexpectedly succeeded")
        return before, after, process

    def preserve(self, relative, expected):
        self.testcase.assertEqual(self.read(relative), expected, relative)

    def disabled(self, relative):
        (self.minecraft / relative).rename(self.minecraft / (relative + ".disabled"))

    def no_abandoned_stage(self):
        stage = self.minecraft / ".cozy/stage"
        self.testcase.assertFalse(stage.exists() and any(stage.iterdir()),
                                 "Ordinary failed updates must reclaim their own completed native stage")

    def upgrade_gameplay(self):
        self.specs["mods/gameplay.pw.toml"]["data"] += b"-next"
        self.publish()


class CustomizationE2ETests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        require = os.environ.get("COZY_REQUIRE_E2E") == "1"
        installer = os.environ.get("PACKWIZ_INSTALLER_JAR") or os.environ.get("ACA_INSTALLER_JAR")
        if not installer:
            fallback = ROOT / "build/customization/packwiz-installer.jar"
            installer = str(fallback) if fallback.is_file() else None
        if not installer or not shutil.which("java") or not shutil.which("javac"):
            message = "Real E2E requires a JDK and PACKWIZ_INSTALLER_JAR pinned v0.5.14 (no automatic downloads)."
            if require:
                raise AssertionError(message)
            raise unittest.SkipTest(message)
        cls.native = Path(installer).resolve()
        native = build_prism.verified_jar(cls.native, build_serverpack.INSTALLER_SHA256, "Packwiz v0.5.14")
        cls.workspace = tempfile.TemporaryDirectory(prefix="cozy-e2e-compiled-")
        cls.jar = Path(os.environ["COZY_TEST_JAR"]).resolve() if os.environ.get("COZY_TEST_JAR") else Path(cls.workspace.name) / "cozy-customization.jar"
        if not os.environ.get("COZY_TEST_JAR"):
            cls.jar.write_bytes(build_prism.compile_launcher(ROOT, native))

    @classmethod
    def tearDownClass(cls):
        report = os.environ.get("ACA_TEST_REPORT")
        if report:
            target = Path(report)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps({"schemaVersion": 1, "installerVersion": "v0.5.14",
                "installerSha256": sha(cls.native.read_bytes()), "protectionJarSha256": sha(cls.jar.read_bytes()),
                "isolation": "All operations in newly generated temporary fixture directories; no production instances used.",
                "testResults": TEST_RESULTS, "evidence": EVIDENCE}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        cls.workspace.cleanup()

    def tearDown(self):
        result = self._outcome.result
        errors = [message for test, message in result.errors + result.failures if test is self or getattr(test, "test_case", None) is self]
        skips = [reason for test, reason in result.skipped if test is self]
        TEST_RESULTS.append({"test": self.id(), "status": "failed" if errors else "skipped" if skips else "passed",
                             "errors": errors, "skipReasons": skips})

    def fixture(self, label):
        return Fixture(self, label)

    @unittest.skipUnless(os.name == "nt", "Windows 8.3 aliases are platform-specific")
    def test_windows_short_path_instance_installs_and_updates(self):
        import ctypes
        from ctypes import wintypes

        f = self.fixture("Windows 8.3 alias for a legitimate instance directory")
        canonical = f.minecraft.resolve()
        get_short_path = ctypes.WinDLL("kernel32", use_last_error=True).GetShortPathNameW
        get_short_path.argtypes = (wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.DWORD)
        get_short_path.restype = wintypes.DWORD
        required = get_short_path(str(canonical), None, 0)
        self.assertGreater(required, 0, f"GetShortPathNameW failed: {ctypes.get_last_error()}")
        buffer = ctypes.create_unicode_buffer(required)
        written = get_short_path(str(canonical), buffer, required)
        self.assertGreater(written, 0, f"GetShortPathNameW failed: {ctypes.get_last_error()}")
        self.assertLess(written, required)
        self.assertIn("~", buffer.value, "Windows regression requires an actual 8.3 alias")
        short = Path(buffer.value)
        self.assertEqual(short.resolve(), canonical)
        f.minecraft = short
        f.run("fresh installation launched with real short-path cwd")
        f.preserve("mods/gameplay.jar", b"required-v1")
        f.write("mods/private.jar", b"personal mod through short path")
        f.upgrade_gameplay()
        f.run("update launched with the same short-path cwd")
        f.preserve("mods/private.jar", b"personal mod through short path")
        self.assertTrue((canonical / ".cozy/state.json").is_file())

    def test_01_fresh_defaults_and_configuration_seed(self):
        f = self.fixture("01 fresh default installation")
        f.run("install")
        for path, data in (("mods/gameplay.jar", b"required-v1"), ("mods/colorlight.jar", b"colorlight-v1"),
                           ("resourcepacks/cozy.zip", b"official-resources-v1"), ("config/cozy.json", b'{"seed":1}\n')):
            f.preserve(path, data)
        self.assertEqual(len(f.state()["entries"]), 3)

    def test_02_personal_mod_survives_multiple_updates(self):
        f = self.fixture("02 private client mod across updates")
        f.run("initial")
        f.write("mods/player-added.jar", b"personal-mod")
        for i in range(3):
            f.upgrade_gameplay()
            f.run(f"update {i + 1}")
            f.preserve("mods/player-added.jar", b"personal-mod")

    def test_03_optional_disabled_across_updates_and_04_reenabled(self):
        f = self.fixture("03 disable / 04 reenable optional client mod")
        f.run("initial")
        f.disabled("mods/colorlight.jar")
        for i in range(2):
            f.upgrade_gameplay()
            f.run(f"disabled update {i + 1}")
            self.assertFalse((f.minecraft / "mods/colorlight.jar").exists())
            f.preserve("mods/colorlight.jar.disabled", b"colorlight-v1")
        (f.minecraft / "mods/colorlight.jar.disabled").rename(f.minecraft / "mods/colorlight.jar")
        f.run("reactivate by supported .disabled rename")
        f.preserve("mods/colorlight.jar", b"colorlight-v1")
        self.assertTrue(f.state()["entries"]["mods/colorlight.pw.toml"]["enabled"])

    def test_05_disable_resource_and_06_private_resource_and_07_order(self):
        f = self.fixture("05 resource off / 06 private resource / 07 order")
        f.run("initial")
        f.disabled("resourcepacks/cozy.zip")
        options = b'resourcePacks:["vanilla","file/private-top.zip","file/private-base.zip"]\nincompatibleResourcePacks:[]\n'
        f.write("options.txt", options)
        f.write("resourcepacks/private-top.zip", b"private-top")
        f.write("resourcepacks/private-base.zip", b"private-base")
        for i in range(2):
            f.upgrade_gameplay()
            f.run(f"resource selection preserved update {i + 1}")
            f.preserve("options.txt", options)
            f.preserve("resourcepacks/private-top.zip", b"private-top")
            f.preserve("resourcepacks/private-base.zip", b"private-base")
            self.assertFalse((f.minecraft / "resourcepacks/cozy.zip").exists())
        # In-game selection/reordering is independent of whether a ZIP exists.
        (f.minecraft / "resourcepacks/cozy.zip.disabled").rename(f.minecraft / "resourcepacks/cozy.zip")
        f.run("resource component reactivated while options order remains personal")
        f.preserve("options.txt", options)

    def test_08_shaders_options_and_modified_config_survive(self):
        f = self.fixture("08 personal shader and client settings")
        f.run("initial")
        personal = {"shaderpacks/private.zip": b"private shader", "config/iris.properties": b"shaderPack=private.zip\n",
                    "options.txt": b"gamma:0.75\nfov:100\n", "config/cozy.json": b'{"seed":"player choice"}\n',
                    "saves/world/level.dat": b"personal world", "screenshots/personal.png": b"screenshot"}
        for path, data in personal.items():
            f.write(path, data)
        f.specs["config/cozy.json"]["data"] = b'{"seed":"new official default"}\n'
        f.specs["config/new-setting.json"] = {"data": b'{"new":true}\n'}
        f.publish()
        f.run("official config defaults update")
        for path, data in personal.items():
            f.preserve(path, data)
        f.preserve("config/new-setting.json", b'{"new":true}\n')
        (f.minecraft / "config/cozy.json").unlink()
        f.upgrade_gameplay()
        f.run("intentional personal deletion of a seeded config remains deleted")
        self.assertFalse((f.minecraft / "config/cozy.json").exists())

    def test_personal_keybindings_survive_first_install_and_repeated_updates(self):
        f = self.fixture("personal keybindings before first protected install and updates")
        options = (b'key_key.attack:key.mouse.left\nkey_key.inventory:key.keyboard.i\n'
                   b'key_zoomify.key.zoom:key.keyboard.v\n'
                   b'resourcePacks:["vanilla","file/my-pack.zip"]\n')
        zoom = b'{"zoomKeyBehaviour":"toggle","scrollZoom":false}\n'
        layout = b'keyboardLayout=102\n'
        f.specs["config/zoomify.json"] = {"data": b'{"zoomKeyBehaviour":"hold"}\n'}
        f.specs["config/studiouskeybinds.properties"] = {"data": b'keyboardLayout=100\n'}
        f.publish()
        f.write("options.txt", options)
        f.write("config/zoomify.json", zoom)
        f.write("config/studiouskeybinds.properties", layout)
        f.run("existing personal keybinds before first protected installation")
        for revision in range(2):
            f.specs["config/zoomify.json"]["data"] = b'{"newOfficialDefault":true}\n'
            f.specs["config/studiouskeybinds.properties"]["data"] = b'keyboardLayout=101\n'
            f.upgrade_gameplay()
            f.run(f"keybinds retained across official update {revision + 1}")
            f.preserve("options.txt", options)
            f.preserve("config/zoomify.json", zoom)
            f.preserve("config/studiouskeybinds.properties", layout)
        self.assertNotIn("options.txt", f.state()["entries"])

    def test_09_required_update_and_10_disabled_option_version_update(self):
        f = self.fixture("09 required upgrade / 10 disabled optional upgrade")
        f.run("initial")
        f.disabled("mods/colorlight.jar")
        f.specs["mods/gameplay.pw.toml"].update(filename="gameplay-v2.jar", data=b"required-v2")
        f.specs["mods/colorlight.pw.toml"].update(filename="colorlight-v2.jar", data=b"colorlight-v2")
        f.publish()
        f.run("upgrade with disabled old version")
        f.preserve("mods/gameplay-v2.jar", b"required-v2")
        self.assertFalse((f.minecraft / "mods/gameplay.jar").exists())
        f.preserve("mods/colorlight.jar.disabled", b"colorlight-v1")
        self.assertFalse((f.minecraft / "mods/colorlight-v2.jar").exists())
        (f.minecraft / "mods/colorlight.jar.disabled").rename(f.minecraft / "mods/colorlight.jar")
        f.run("reenable retrieves the current pinned version")
        f.preserve("mods/colorlight-v2.jar", b"colorlight-v2")
        self.assertFalse((f.minecraft / "mods/colorlight.jar").exists())

    def lifecycle(self, identifier, target, disabled):
        kind = "ColorLight" if identifier.startswith("mods/") else "resource pack"
        f = self.fixture(f"11–13 {kind} four-state lifecycle, initially {'disabled' if disabled else 'active'}")
        f.pack_version = "1.0.0"
        f.publish()
        f.run("1 officially present")
        if disabled:
            f.disabled(target)
            f.run("record official disabled state")
        old_data = f.specs.pop(identifier)["data"]
        f.pack_version = "1.0.1"
        f.publish()
        f.run("2 officially removed; ownership retired")
        self.assertFalse((f.minecraft / target).exists())
        self.assertFalse((f.minecraft / (target + ".disabled")).exists())
        self.assertNotIn(identifier, f.state()["entries"])
        # Exact same bytes and filename are private after ownership was retired.
        f.write(target, old_data)
        f.run("3 privately reinstalled, same previous official hash")
        f.preserve(target, old_data)
        for i in range(2):
            f.upgrade_gameplay()
            f.run(f"4 later official update {i + 1}")
            f.preserve(target, old_data)
            self.assertNotIn(identifier, f.state()["entries"])

    def test_11_12_colorlight_lifecycle_active_and_disabled(self):
        for disabled in (False, True):
            with self.subTest(disabled=disabled):
                self.lifecycle("mods/colorlight.pw.toml", "mods/colorlight.jar", disabled)

    def test_released_v100_launcher_upgrades_without_reset_and_removes_colorlight_once(self):
        previous = Path(os.environ.get("COZY_PREVIOUS_JAR", str(ROOT / "build/customization/v1.0.0-protection.jar")))
        if not previous.exists():
            if os.environ.get("COZY_REQUIRE_E2E") == "1":
                self.fail("Released v1.0.0 JAR required for upgrade regression")
            self.skipTest("Released v1.0.0 JAR not present")
        build_prism.verified_jar(previous, "99dc680b056805515d48cab3800a096239b4206ee584402873107fe06023ffc6", "released v1.0.0 protector")
        for disabled in (False, True):
            with self.subTest(disabled=disabled):
                f = self.fixture("Released v1.0.0 protection to v1.0.1, active/disabled removal")
                instance = f.minecraft.parent
                command = chr(92) + chr(34) + "$INST_JAVA" + chr(92) + chr(34) + " -jar cozy-customization.jar --pack " + build_prism.PACK_URL
                (instance / "instance.cfg").write_text("[General]\nOverrideCommands=true\nPreLaunchCommand=" + command + "\n")
                installed = f.minecraft / "cozy-customization.jar"
                installed.write_bytes(previous.read_bytes())
                f.jar = installed
                f.pack_version = "1.0.0"
                f.publish()
                f.run("actual released v1.0.0 installs official ColorLight")
                if disabled:
                    f.disabled("mods/colorlight.jar")
                state_before = f.read(".cozy/state.json")
                result = subprocess.run(["java", "-Djava.awt.headless=true", "-jar", str(self.jar), "--migrate", str(instance)], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(f.read(".cozy/state.json"), state_before)
                self.assertEqual(installed.read_bytes(), self.jar.read_bytes())
                self.assertEqual(f.read("cozy-customization.jar.before-v1.0.1"), previous.read_bytes())
                personal = {"XaeroWorldMap/server/map.zip": b"existing map", "options.txt": b"key_key.forward:key.keyboard.z", "mods/private.jar": b"private"}
                for path, data in personal.items():
                    f.write(path, data)
                old = f.specs.pop("mods/colorlight.pw.toml")["data"]
                f.pack_version = "1.0.1"
                f.publish()
                f.run("new protector updates existing v1.0.0 state")
                self.assertNotIn("mods/colorlight.pw.toml", f.state()["entries"])
                self.assertFalse((f.minecraft / "mods/colorlight.jar").exists())
                self.assertFalse((f.minecraft / "mods/colorlight.jar.disabled").exists())
                for path, data in personal.items():
                    f.preserve(path, data)
                target = "mods/colorlight.jar" + (".disabled" if disabled else "")
                f.write(target, old)
                for _ in range(2):
                    f.upgrade_gameplay()
                    f.run("later update leaves private same-byte reinstall untouched")
                    f.preserve(target, old)

    def test_13_resource_lifecycle_active_and_disabled(self):
        for disabled in (False, True):
            with self.subTest(disabled=disabled):
                self.lifecycle("resourcepacks/cozy.pw.toml", "resourcepacks/cozy.zip", disabled)

    def test_14_personal_filename_collision_including_identical_bytes(self):
        for content in (b"personal different bytes", b"colorlight-v1"):
            with self.subTest(hash=sha(content)):
                f = self.fixture("14 private filename collision, including identical content")
                f.write("mods/colorlight.jar", content)
                before, after, _ = f.run("fresh install conflict", success=False)
                self.assertEqual(gameplay(before), gameplay(after))
                f.no_abandoned_stage()
                self.assertFalse((f.minecraft / ".cozy/state.json").exists())
                self.assertIn("colorlight.jar", f.read(".cozy/conflicts.txt").decode())

    def test_15_modified_managed_file_is_preserved(self):
        for disabled in (False, True):
            with self.subTest(disabled=disabled):
                f = self.fixture("15 ambiguous ownership blocks removal, including Prism disabled")
                f.run("initial")
                target = "mods/colorlight.jar"
                if disabled:
                    f.disabled(target)
                    target += ".disabled"
                f.write(target, b"player replacement")
                f.specs.pop("mods/colorlight.pw.toml")
                f.publish()
                before, after, _ = f.run("ambiguous removal blocked", success=False)
                self.assertEqual(gameplay(before), gameplay(after))
                self.assertEqual(before[".cozy/state.json"], after[".cozy/state.json"])
                f.preserve(target, b"player replacement")
                self.assertIn("mods/colorlight.pw.toml", f.state()["entries"])
                # Resolving the conflict without resetting state permits the transaction.
                f.write(target, b"colorlight-v1")
                f.run("proven official removal")
                self.assertNotIn("mods/colorlight.pw.toml", f.state()["entries"])
                f.write(target, b"player replacement")
                f.upgrade_gameplay()
                f.run("future update preserves private reinstall")
                f.preserve(target, b"player replacement")

    def test_v101_removal_preserves_personal_xaero_maps_and_settings(self):
        f = self.fixture("v1.0.0 to v1.0.1 removal with personal maps and preferences")
        f.pack_version = "1.0.0"
        f.publish()
        f.run("v1.0.0 installed")
        personal = {
            "XaeroWorldMap/Multiplayer_server/DIM0/region.zip": b"personal world map",
            "XaeroWaypoints/Multiplayer_server/dim%0/waypoints.txt": b"personal waypoints",
            "config/xaeroworldmap.txt": b"personal map preferences",
            "options.txt": b'key_key.forward:key.keyboard.z\nresourcePacks:["vanilla","file/private.zip","file/cozy.zip"]\n',
            "resourcepacks/private.zip": b"personal resources",
            "mods/private.jar": b"personal mod",
        }
        for path, data in personal.items():
            f.write(path, data)
        f.specs.pop("mods/colorlight.pw.toml")
        f.pack_version = "1.0.1"
        f.publish()
        f.run("v1.0.1 removes official ColorLight")
        for path, data in personal.items():
            f.preserve(path, data)
        self.assertFalse((f.minecraft / "mods/colorlight.jar").exists())
        self.assertNotIn("mods/colorlight.pw.toml", f.state()["entries"])

    def test_removed_colorlight_duplicate_active_disabled_fails_closed(self):
        f = self.fixture("removed ColorLight duplicate paths are ambiguous even with identical hashes")
        f.run("initial")
        f.write("mods/colorlight.jar.disabled", b"colorlight-v1")
        f.specs.pop("mods/colorlight.pw.toml")
        f.publish()
        before, after, _ = f.run("ambiguous duplicate removal blocked", success=False)
        self.assertEqual(gameplay(before), gameplay(after))
        self.assertEqual(before[".cozy/state.json"], after[".cozy/state.json"])

    def test_16_missing_and_corrupt_metadata_fail_closed(self):
        for manifest in (None, b"not JSON", b"{}"):
            with self.subTest(manifest=manifest):
                f = self.fixture("16 missing/corrupt legacy ownership metadata")
                f.write("mods/colorlight.jar", b"preexisting unproven ownership")
                if manifest is not None:
                    f.write("packwiz.json", manifest)
                before, after, _ = f.run("unproven metadata", success=False)
                self.assertEqual(gameplay(before), gameplay(after))
        f = self.fixture("16 corrupted protection state")
        f.run("initial")
        f.write(".cozy/state.json", b"{broken")
        before, after, _ = f.run("damaged state rejected", success=False)
        self.assertEqual(gameplay(before), gameplay(after))

    def test_17_interrupted_download_never_commits_then_retries(self):
        f = self.fixture("17 interrupted pinned native download")
        f.run("initial")
        f.upgrade_gameplay()
        f.faults["/downloads/gameplay.jar"] = "truncate"
        before, after, _ = f.run("truncated HTTP payload", success=False)
        self.assertEqual(gameplay(before), gameplay(after))
        self.assertEqual(before[".cozy/state.json"], after[".cozy/state.json"])
        f.no_abandoned_stage()
        f.faults.clear()
        f.run("restart completes verified download")
        f.preserve("mods/gameplay.jar", f.specs["mods/gameplay.pw.toml"]["data"])

    def test_18_aborted_process_restarts_safely(self):
        f = self.fixture("18 killed update process then restart")
        f.run("initial")
        f.upgrade_gameplay()
        f.faults["/downloads/gameplay.jar"] = "block"
        before = inventory(f.minecraft)
        kwargs = {"start_new_session": True} if os.name != "nt" else {}
        process = subprocess.Popen(f.command(), cwd=f.minecraft, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs)
        self.addCleanup(lambda: process.poll() is None and process.kill())
        self.assertTrue(f.block.wait(20), "Native installer never reached the fixture download")
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True, timeout=15)
        else:
            os.killpg(process.pid, signal.SIGKILL)
        stdout, stderr = process.communicate(timeout=15)
        f.release.set()
        after = inventory(f.minecraft)
        EVIDENCE.append({"scenario": f.label, "step": "actual process killed during native download",
                         "returncode": process.returncode, "stdout": stdout.decode(errors="replace"),
                         "stderr": stderr.decode(errors="replace"), "before": before, "after": after})
        self.assertEqual(gameplay(before), gameplay(after))
        f.faults.clear()
        f.run("restart after killed native update")
        f.preserve("mods/gameplay.jar", f.specs["mods/gameplay.pw.toml"]["data"])

    def test_18_partially_applied_journal_resumes_idempotently(self):
        f = self.fixture("18 interrupted commit journal recovery")
        f.run("initial")
        next_state = f.state()
        operations = []
        for identifier, target in (("mods/gameplay.pw.toml", "mods/gameplay.jar"),
                                   ("resourcepacks/cozy.pw.toml", "resourcepacks/cozy.zip")):
            before = sha(f.read(target))
            data = f.specs[identifier]["data"] + b"-next"
            f.specs[identifier]["data"] = data
            source = ".cozy/stage/recovery/" + target
            f.write(source, data)
            operations.append({"path": target, "before": before, "after": sha(data), "source": source})
            next_state["entries"][identifier]["hash"] = sha(data)
        f.write(operations[0]["path"], f.specs["mods/gameplay.pw.toml"]["data"])
        f.write(".cozy/journal.json", json.dumps({"schema": 1, "operations": operations, "state": next_state}))
        f.publish()
        f.run("resume journal with first write already applied")
        for identifier, target in (("mods/gameplay.pw.toml", "mods/gameplay.jar"),
                                   ("resourcepacks/cozy.pw.toml", "resourcepacks/cozy.zip")):
            f.preserve(target, f.specs[identifier]["data"])
        self.assertFalse((f.minecraft / ".cozy/journal.json").exists())
        f.run("idempotent journal recovery subsequent start")

    def test_18_wrapper_only_kill_isolates_orphan_native_stage(self):
        f = self.fixture("18 wrapper-only kill leaves a live native child")
        f.run("initial")
        f.upgrade_gameplay()
        f.faults["/downloads/gameplay.jar"] = "block-once"
        before = inventory(f.minecraft)
        process = subprocess.Popen(f.command(), cwd=f.minecraft, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.addCleanup(lambda: process.poll() is None and process.kill())
        self.assertTrue(f.block.wait(20), "Native child did not reach its blocked fixture download")
        orphan_manifests = list((f.minecraft / ".cozy/stage").glob("*/files/packwiz.json"))
        self.assertEqual(len(orphan_manifests), 1, "Every native invocation needs a distinct private stage")
        orphan_manifest = orphan_manifests[0]
        # Kill just the wrapper. The native child intentionally remains blocked
        # while a second wrapper starts, downloads and commits in another stage.
        process.kill()
        stdout, stderr = process.communicate(timeout=15)
        after_kill = inventory(f.minecraft)
        self.assertEqual(gameplay(before), gameplay(after_kill))
        EVIDENCE.append({"scenario": f.label, "step": "kill only wrapper while native remains alive",
                         "returncode": process.returncode, "stdout": stdout.decode(errors="replace"),
                         "stderr": stderr.decode(errors="replace"), "before": before, "after": after_kill})
        f.run("second wrapper commits independently while orphan download is blocked")
        f.preserve("mods/gameplay.jar", f.specs["mods/gameplay.pw.toml"]["data"])
        self.assertTrue(orphan_manifest.exists(), "New updater must not delete another process's stage")
        after_restart = inventory(f.minecraft)
        f.release.set()
        deadline = time.monotonic() + 15
        orphan_complete = False
        while time.monotonic() < deadline:
            try:
                orphan_complete = bool(json.loads(orphan_manifest.read_text())["packFileHash"])
            except (OSError, ValueError, KeyError):
                pass
            if orphan_complete:
                break
            time.sleep(0.1)
        self.assertTrue(orphan_complete, "Orphan native child did not finish in its isolated stage")
        # Give native Java time to close its JAR/log handles before fixture cleanup.
        time.sleep(0.2)
        after_orphan = inventory(f.minecraft)
        self.assertEqual(gameplay(after_restart), gameplay(after_orphan))
        self.assertEqual(after_restart[".cozy/state.json"], after_orphan[".cozy/state.json"])
        EVIDENCE.append({"scenario": f.label, "step": "orphan finishes without changing committed game/state",
                         "before": after_restart, "after": after_orphan, "orphanStageRetained": True})

    def test_19_migrate_actual_native_v002_manifest(self):
        f = self.fixture("19 migration from actual v0.0.2-style native installation")
        f.run("original official v0.5.14 installer creates legacy packwiz.json", native=True)
        legacy = f.read("packwiz.json")
        self.assertIn("cachedFiles", json.loads(legacy))
        f.disabled("mods/colorlight.jar")
        f.write("mods/private-before-migration.jar", b"legacy personal mod")
        personal = b"fov:111\nresourcePacks:[\"vanilla\"]\n"
        f.write("options.txt", personal)
        f.run("first protected start adopts verified legacy ownership")
        f.preserve(".cozy/legacy-packwiz.json", legacy)
        self.assertEqual(json.loads(f.read("packwiz.json"))["cachedFiles"], {})
        f.preserve("mods/private-before-migration.jar", b"legacy personal mod")
        f.preserve("options.txt", personal)
        f.preserve("mods/colorlight.jar.disabled", b"colorlight-v1")
        self.assertFalse(f.state()["entries"]["mods/colorlight.pw.toml"]["enabled"])
        f.upgrade_gameplay()
        f.run("migrated installation next update")
        f.preserve("mods/private-before-migration.jar", b"legacy personal mod")
        f.preserve("options.txt", personal)

    def test_20_server_selection_unchanged_and_21_repository_integrity(self):
        # Existing serverpack integration tests also build full isolated archives.
        plan = build_serverpack.load_plan(ROOT)
        policy = json.loads((ROOT / build_serverpack.POLICY).read_text(encoding="utf-8"))
        self.assertEqual(len(plan.mods), policy["expectedServerMods"])
        self.assertTrue(all(mod.side != "client" for mod in plan.mods))
        self.assertEqual(len(plan.mods) + len(plan.excluded), policy["expectedTotalMods"])
        EVIDENCE.append({"scenario": "20 serverpack selection / 21 Packwiz index integrity",
                         "result": "Existing strict load_plan verifies pack/index hashes and every indexed source; client options stay excluded.",
                         "serverModCount": len(plan.mods), "excludedClientCount": len(plan.excluded),
                         "managedInputs": {name: {"bytes": len(raw), "sha256": sha(raw)} for name, raw in plan.inputs.items()}})

    def test_21_remote_metadata_and_file_hash_mismatch(self):
        for target in ("index.toml", "mods/colorlight.pw.toml", "downloads/colorlight.jar"):
            with self.subTest(target=target):
                f = self.fixture("21 remote hash-integrity failure")
                f.run("initial")
                f.specs["mods/colorlight.pw.toml"]["data"] += b"-new"
                f.publish()
                (f.source / target).write_bytes((f.source / target).read_bytes() + b"tampered")
                before, after, _ = f.run(f"tampered {target}", success=False)
                self.assertEqual(gameplay(before), gameplay(after))
                self.assertEqual(before[".cozy/state.json"], after[".cozy/state.json"])

    def test_22_repeat_start_does_not_rewrite_user_or_state(self):
        f = self.fixture("22 repeated start without update")
        f.run("initial")
        f.write("options.txt", b"personal options")
        watched = ["mods/gameplay.jar", "mods/colorlight.jar", "resourcepacks/cozy.zip", "config/cozy.json", "options.txt", ".cozy/state.json"]
        timestamps = {name: (f.minecraft / name).stat().st_mtime_ns for name in watched}
        for i in range(2):
            f.requests.clear()
            before, after, result = f.run(f"unchanged start {i + 1}")
            self.assertEqual(before, after, "No-op start must preserve staged files too")
            self.assertEqual(f.requests, ["/pack.toml"], "No-op start must avoid index/JAR downloads")
            self.assertEqual(timestamps, {name: (f.minecraft / name).stat().st_mtime_ns for name in watched})
            self.assertIn("0 file changes", result.stdout)

    def test_fresh_disabled_without_owned_path_never_claims_personal_bytes(self):
        f = self.fixture("regression fresh disabled has no owned file")
        # A native disabled option with cachedLocation=null establishes a choice,
        # not ownership of a nonexistent file. This is also the fresh GUI result.
        f.write("packwiz.json", json.dumps({"cachedFiles": {
            "mods/colorlight.pw.toml": {"isOptional": True, "optionValue": False, "cachedLocation": None}}}))
        f.run("migrate never-installed disabled option")
        self.assertNotIn("path", f.state()["entries"]["mods/colorlight.pw.toml"])
        f.specs.pop("mods/colorlight.pw.toml")
        f.publish()
        f.write("mods/colorlight.jar", b"colorlight-v1")
        f.run("removed disabled option does not own personal identical bytes")
        f.preserve("mods/colorlight.jar", b"colorlight-v1")
        f.upgrade_gameplay()
        f.run("future update still preserves private bytes")
        f.preserve("mods/colorlight.jar", b"colorlight-v1")

    def test_modified_renamed_disabled_file_blocks_update(self):
        f = self.fixture("regression modified disabled previous-version filename")
        f.run("initial")
        f.disabled("mods/colorlight.jar")
        f.write("mods/colorlight.jar.disabled", b"personal modified disabled bytes")
        f.specs["mods/colorlight.pw.toml"].update(filename="colorlight-v2.jar", data=b"colorlight-v2")
        f.publish()
        before, after, _ = f.run("modified old filename is preserved and replacement blocks", success=False)
        self.assertEqual(gameplay(before), gameplay(after))
        self.assertFalse((f.minecraft / "mods/colorlight-v2.jar").exists())

    def test_initialized_marker_blocks_missing_state_and_legacy_reimport(self):
        f = self.fixture("regression lost state after ownership retirement")
        f.run("initial")
        (f.minecraft / ".cozy/state.json").unlink()
        # Even a plausible old legacy manifest cannot revive retired ownership.
        f.write("packwiz.json", json.dumps({"cachedFiles": {}}))
        before, after, _ = f.run("initialized installation missing authoritative state", success=False)
        self.assertEqual(gameplay(before), gameplay(after))
        self.assertFalse((f.minecraft / ".cozy/state.json").exists())

    def test_repository_optional_policy_matches_audited_pinned_dependencies(self):
        report = json.loads((ROOT / "docs/customization/dependencies.json").read_text(encoding="utf-8"))
        records = report["mods"]
        self.assertEqual(len(records), report["counts"]["mods"])
        actual = {path.relative_to(ROOT).as_posix(): tomllib.loads(path.read_text(encoding="utf-8"))
                  for path in (ROOT / "mods").glob("*.pw.toml")}
        self.assertEqual(set(actual), {record["packwizFile"] for record in records})
        for record in records:
            mod = actual[record["packwizFile"]]
            self.assertEqual(mod["filename"], record["filename"], record["id"])
            self.assertEqual(mod["download"]["hash-format"], record["hashFormat"], record["id"])
            self.assertEqual(mod["download"]["hash"], record["hash"], record["id"])
        optional = {record["id"] for record in records
                    if actual[record["packwizFile"]].get("option", {}).get("optional") is True}
        self.assertEqual(len(optional), report["counts"]["independentOptions"])
        self.assertEqual(optional, set(report["optionalDefaultOn"]))
        for record in records:
            mod = actual[record["packwizFile"]]
            if record["id"] in optional:
                self.assertIs(mod["option"]["default"], True)
                self.assertEqual(mod["side"], "client")
            if record["id"] in report["requiredClientSupport"]:
                self.assertNotIn("option", mod)
        self.assertEqual(len(report["requiredClientSupport"]), 4)
        resources = list((ROOT / "resourcepacks").glob("*.pw.toml"))
        self.assertEqual(len(resources), 4)
        for path in resources:
            resource = tomllib.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(resource["side"], "client")
            self.assertIs(resource["option"]["optional"], True)
            self.assertIs(resource["option"]["default"], True)
        index = tomllib.loads((ROOT / "index.toml").read_text(encoding="utf-8"))
        self.assertFalse(any(entry["file"] == "options.txt" for entry in index["files"]))
        configs = [entry for entry in index["files"] if entry["file"].startswith("config/")]
        self.assertTrue(configs)
        self.assertTrue(all(entry.get("preserve") is True for entry in configs))
        EVIDENCE.append({"scenario": "repository customization policy", "auditedMods": len(records),
                         "independentDefaultOnOptions": len(optional), "requiredClientSupport": report["requiredClientSupport"],
                         "optionalResources": len(resources), "preservedIndexedConfigs": len(configs),
                         "result": "All pinned download filenames/hashes and repository option/preserve policy match the dependency audit."})

    def test_prism_component_mismatch_stops_before_gameplay_changes(self):
        f = self.fixture("Prism Minecraft/Fabric version preflight")
        metadata = f.minecraft.parent / "mmc-pack.json"
        original = metadata.read_bytes()
        components = json.loads(original)
        components["components"][0]["version"] = "1.21.1"
        mismatch = json.dumps(components).encode()
        metadata.write_bytes(mismatch)
        f.write("mods/private.jar", b"personal mod")
        before, after, _ = f.run("reject Minecraft component mismatch", success=False)
        self.assertEqual(gameplay(before), gameplay(after))
        self.assertEqual(metadata.read_bytes(), mismatch, "Updater must never silently edit Prism's parent metadata")
        self.assertFalse((f.minecraft / ".cozy/state.json").exists())
        metadata.write_bytes(original)
        f.run("matching Prism components allow installation")
        f.preserve("mods/private.jar", b"personal mod")

    def test_legacy_archive_then_interrupted_retirement_resumes(self):
        f = self.fixture("legacy migration crash after archive before manifest retirement")
        f.run("original v0.5.14 native installation", native=True)
        legacy = f.read("packwiz.json")
        f.run("obtain committed migration state")
        f.preserve(".cozy/legacy-packwiz.json", legacy)
        # Recreate exactly the durable filesystem after state/marker/archive
        # writes and before the legacy cachedFiles ledger is decommissioned.
        f.write("packwiz.json", legacy)
        f.write(".cozy/journal.json", json.dumps({"schema": 1, "operations": [], "state": f.state()}))
        f.run("restart completes legacy retirement even when archive already exists")
        f.preserve(".cozy/legacy-packwiz.json", legacy)
        self.assertEqual(json.loads(f.read("packwiz.json"))["cachedFiles"], {})
        self.assertFalse((f.minecraft / ".cozy/journal.json").exists())

    def test_security_traversal_and_symlink_paths(self):
        f = self.fixture("security metadata traversal")
        f.specs["mods/colorlight.pw.toml"]["filename"] = "../escape.jar"
        f.publish()
        outside = f.base / "escape.jar"
        f.run("reject traversal before instance mutation", success=False)
        self.assertFalse(outside.exists())
        f = self.fixture("security symlink target")
        outside = f.base / "outside"
        outside.mkdir()
        sentinel = outside / "colorlight.jar"
        sentinel.write_bytes(b"outside sentinel")
        try:
            (f.minecraft / "mods").symlink_to(outside, target_is_directory=True)
        except (OSError, NotImplementedError):
            if os.name != "nt":
                self.skipTest("OS account cannot create symlinks; traversal test still ran")
            # Windows directory junctions require no developer-mode privilege.
            # Both destinations are disposable fixture paths and remain inside
            # this test's temporary directory, including during cleanup.
            junction = subprocess.run(["cmd", "/c", "mklink", "/J", str(f.minecraft / "mods"), str(outside)],
                                      capture_output=True, timeout=10)
            if junction.returncode:
                self.skipTest("OS account cannot create symlinks or junctions; traversal test still ran")
        f.run("reject symlink target", success=False)
        self.assertEqual(sentinel.read_bytes(), b"outside sentinel")

    def test_security_journal_preflight_preserves_concurrent_edit(self):
        f = self.fixture("security concurrent edit before journal recovery")
        f.run("initial")
        state = f.state()
        operations = [{"path": "mods/gameplay.jar", "before": sha(f.read("mods/gameplay.jar")), "after": None, "source": None},
                      {"path": "mods/colorlight.jar", "before": sha(f.read("mods/colorlight.jar")), "after": None, "source": None}]
        f.write(".cozy/journal.json", json.dumps({"schema": 1, "operations": operations, "state": state}))
        f.write("mods/colorlight.jar", b"concurrent personal edit")
        before, after, _ = f.run("full journal preflight rejects changed ownership", success=False)
        self.assertEqual(gameplay(before), gameplay(after))
        f.preserve("mods/gameplay.jar", b"required-v1")


if __name__ == "__main__":
    unittest.main()
