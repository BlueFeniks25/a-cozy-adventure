"""Offline fixtures for master scanning, review and deterministic preparation.

No real Prism instance is used by these tests. Every mutation stays in a temporary
fixture. Production-baseline tests read only the checked-in manifest/snapshots.
"""
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import master_pack as pack


def jar(mid, version="1.0", env="*", depends=None, nested=None):
    result = io.BytesIO()
    with zipfile.ZipFile(result, "w") as z:
        meta = {"schemaVersion": 1, "id": mid, "version": version,
                "environment": env, "depends": depends or {}}
        if nested:
            meta["jars"] = [{"file": path} for path in nested]
            for path, data in nested.items():
                z.writestr(path, data)
        z.writestr("fabric.mod.json", json.dumps(meta))
    return result.getvalue()


def source(data):
    return {"provider": "modrinth", "projectId": "Project1", "versionId": "Version1",
            "url": "https://modrinth.com/project/Project1/version/Version1",
            "hashes": {"sha512": hashlib.sha512(data).hexdigest()}}


def tree(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob("*") if p.is_file() and not p.is_symlink()}


class MasterPackTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="cozy-master-fixture-")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.root = self.base / "repo"
        self.root.mkdir()
        self.instance = self.base / "Prism instance with spaces"
        self.mc = self.instance / "minecraft"
        (self.mc / "mods").mkdir(parents=True)
        (self.instance / "mmc-pack.json").write_text(json.dumps({"components": [
            {"uid": "net.minecraft", "version": "26.3"},
            {"uid": "net.fabricmc.fabric-loader", "version": "0.19.5"}]}))
        self.lock = {"schemaVersion": 1, "status": "approved",
                     "pack": {"name": "Test Pack", "minecraft": "26.3", "fabric": "0.19.5", "java": "25", "automodpack": "5.0.0-rc.5"},
                     "groups": {"main": {"displayName": "Core", "selection": "REQUIRED", "requires": []},
                                "extras": {"displayName": "Extras", "selection": "OPTIONAL", "requires": ["main"]}},
                     "mods": [], "configs": [], "resourcepacks": []}
        self.put_mod("automodpack", version="5.0.0-rc.5", role="bootstrap")
        self.put_mod("commonmod", depends={"minecraft": "26.3", "java": ">=25"})
        self.put_mod("clientmod", side="client", env="client", depends={"commonmod": ">=1.0"})
        self.put_mod("servermod", side="server", env="server")
        self.put_config("config/gameplay.json", b'{"worldgen": true}\r\n', "both", False)
        self.put_config("config/client.json", b'{"particles": 2}\n', "client", True)
        data = b"reviewed resource fixture"
        self.write_mc("resourcepacks/reviewed.zip", data)
        self.lock["resourcepacks"].append({"filename": "reviewed.zip", "sha256": pack.sha(data),
                                           "size": len(data), "group": "extras", "source": source(data)})
        self.save_lock()
        self.addCleanup(patch.stopall)
        patch.object(socket, "create_connection", side_effect=AssertionError("Network forbidden")).start()

    def write_mc(self, name, data):
        p = self.mc / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    def put_mod(self, mid, version="1.0", side="both", env="*", depends=None, role="mod", nested=None):
        data = jar(mid, version, env, depends, nested)
        name = mid + ".jar"
        self.write_mc("mods/" + name, data)
        nodes = pack.metadata(data, name)
        record = {"id": mid, "name": mid, "version": version, "filename": name,
                  "sha256": pack.sha(data), "size": len(data), "metadata": nodes[0],
                  "nestedMods": nodes[1:], "side": side, "sideReason": "Reviewed fixture",
                  "role": role, "source": source(data)}
        self.lock["mods"] = [m for m in self.lock["mods"] if m["id"] != mid] + [record]
        return record

    def put_config(self, path, data, side, editable):
        self.write_mc(path, data)
        snap = "defaults/" + pack.sha(data) + ".txt"
        dest = self.root / pack.BASE / snap
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        self.lock["configs"].append({"path": path, "snapshot": snap, "sha256": pack.sha(data),
                                      "size": len(data), "side": side, "editable": editable})

    def save_lock(self):
        target = self.root / pack.LOCK
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(pack.json_bytes(self.lock))

    def prepare(self, name="one"):
        return pack.prepare(self.root, self.instance, self.root / "dist" / name)

    def candidate(self):
        folder = self.root / "build/review"
        pack.write_scan(self.root, self.instance, folder)
        return folder / "candidate.json"

    def test_scan_unchanged_and_master_read_only(self):
        before = tree(self.instance)
        report, _ = pack.scan(self.root, self.instance)
        self.assertFalse(report["changed"])
        self.assertEqual(report["blockers"], [])
        self.assertEqual(tree(self.instance), before)

    def test_scan_accepts_minecraft_folder(self):
        self.assertFalse(pack.scan(self.root, self.mc)[0]["changed"])

    def test_preparation_side_split_bootstrap_and_groups(self):
        before = tree(self.instance)
        out = self.prepare()
        self.assertTrue((out / "server/mods/commonmod.jar").is_file())
        self.assertTrue((out / "server/mods/servermod.jar").is_file())
        self.assertFalse((out / "server/mods/clientmod.jar").exists())
        host = out / "server/automodpack/host-modpack"
        self.assertTrue((host / "main/mods/commonmod.jar").is_file())
        self.assertTrue((host / "main/mods/clientmod.jar").is_file())
        self.assertFalse((host / "main/mods/servermod.jar").exists())
        self.assertFalse((host / "main/mods/automodpack.jar").exists())
        self.assertTrue((out / "bootstrap-client/mods/automodpack.jar").is_file())
        self.assertTrue((host / "extras/resourcepacks/reviewed.zip").is_file())
        self.assertFalse((out / "server/config/client.json").exists())
        self.assertEqual((out / "server/config/gameplay.json").read_bytes(), b'{"worldgen": true}\r\n')
        conf = (out / "server/automodpack/server.conf").read_text(encoding="utf-8")
        for setting in ("generate-modpack-on-start: false", "from-server: []", "connection-mode: HOLEPUNCH", "selection: OPTIONAL"):
            self.assertIn(setting, conf)
        self.assertNotIn('"config/gameplay.json"', conf)
        self.assertIn('"config/client.json"', conf)
        self.assertEqual(tree(self.instance), before)

    def test_deterministic_output_and_all_checksums(self):
        a, b = self.prepare("a"), self.prepare("b")
        self.assertEqual(tree(a), tree(b))
        for line in (a / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
            digest, name = line.split("  ", 1)
            self.assertEqual(pack.sha((a / name).read_bytes()), digest)
        report = json.loads((a / "build-report.json").read_text(encoding="utf-8"))
        self.assertEqual(report["dedicatedServerTest"], "pending")
        self.assertFalse(report["published"])
        self.assertNotIn(str(self.instance), (a / "build-report.json").read_text(encoding="utf-8"))

    def test_personal_files_and_unselected_packs_never_copied(self):
        forbidden = ["options.txt", "servers.dat", "saves/world/level.dat", "xaero/map.dat",
                     "logs/latest.log", "automodpack/credentials/private-key.pem", ".cozy/state.json",
                     "config/voicechat/username-cache.json", "config/colorlight.json",
                     "resourcepacks/private.zip", "shaderpacks/private.zip", "config/private.json"]
        for path in forbidden:
            self.write_mc(path, b"PRIVATE-MARKER-password")
        out = self.prepare()
        for f in out.rglob("*"):
            if f.is_file():
                self.assertNotIn(b"PRIVATE-MARKER", f.read_bytes(), str(f))

    def test_unknown_mod_requires_manual_side_and_source(self):
        self.write_mc("mods/new.jar", jar("newmod", env="client"))
        report, candidate = pack.scan(self.root, self.instance)
        self.assertEqual(report["changes"]["new"][0]["id"], "newmod")
        self.assertTrue(report["blockers"])
        record = next(m for m in candidate["mods"] if m["id"] == "newmod")
        self.assertIsNone(record["side"])
        with self.assertRaises(pack.PackError):
            self.prepare()
        with self.assertRaises(pack.PackError):
            pack.validate_lock(candidate, approved=False)

    def test_known_update_does_not_reuse_old_source(self):
        self.write_mc("mods/commonmod.jar", jar("commonmod", version="2.0"))
        report, candidate = pack.scan(self.root, self.instance)
        self.assertEqual(report["changes"]["updated"][0]["oldVersion"], "1.0")
        self.assertEqual(report["changes"]["updated"][0]["version"], "2.0")
        self.assertIsNone(next(m for m in candidate["mods"] if m["id"] == "commonmod")["source"])

    def test_verified_prism_source_detected_offline(self):
        data = jar("commonmod", "2.0")
        self.write_mc("mods/commonmod.jar", data)
        text = ('filename="commonmod.jar"\n[download]\nhash-format="sha512"\nhash="'
                + hashlib.sha512(data).hexdigest() + '"\n[update.modrinth]\nmod-id="Project1"\nversion="Version2"\n')
        self.write_mc("mods/.index/common.pw.toml", text.encode())
        report, candidate = pack.scan(self.root, self.instance)
        self.assertFalse(report["blockers"])
        self.assertEqual(next(m for m in candidate["mods"] if m["id"] == "commonmod")["source"]["versionId"], "Version2")

    def test_missing_mod_report_and_prepare_failure(self):
        (self.mc / "mods/servermod.jar").unlink()
        report, _ = pack.scan(self.root, self.instance)
        self.assertEqual(report["changes"]["removed"][0]["id"], "servermod")
        with self.assertRaisesRegex(pack.PackError, "Fehlende oder unbekannte"):
            self.prepare()
        self.assertFalse((self.root / "dist").exists())

    def test_missing_required_dependency_blocks_approval(self):
        (self.mc / "mods/commonmod.jar").unlink()
        report, candidate = pack.scan(self.root, self.instance)
        self.assertTrue(any("Abhängigkeit" in b for b in report["blockers"]))
        with self.assertRaisesRegex(pack.PackError, "Abhängigkeit"):
            pack.validate_lock(candidate, approved=False)

    def test_wrong_dependency_version_rejected(self):
        self.put_mod("commonmod", depends={"java": ">=99"})
        self.save_lock()
        with self.assertRaisesRegex(pack.PackError, "Abhängigkeit"):
            self.prepare()

    def test_nested_dependency_and_alias_available(self):
        self.put_mod("commonmod", nested={"META-INF/jars/library.jar": jar("nestedlib")})
        self.put_mod("clientmod", side="client", env="client", depends={"nestedlib": ">=1.0"})
        self.save_lock()
        self.prepare()

    def test_environment_disabled_dependency_is_explicit_runtime_warning(self):
        self.put_mod("commonmod", depends={"nestedlib": "*"}, nested={"META-INF/jars/client.jar": jar("nestedlib", env="client")})
        self.save_lock()
        warnings = pack.validate_dependencies(self.lock)
        self.assertTrue(any("server" in w and "nestedlib" in w for w in warnings))

    def test_duplicate_mod_id_rejected(self):
        self.write_mc("mods/duplicate.jar", jar("commonmod"))
        with self.assertRaisesRegex(pack.PackError, "Doppelte"):
            pack.scan(self.root, self.instance)

    def test_corrupt_jar_rejected(self):
        self.write_mc("mods/commonmod.jar", b"corrupted")
        with self.assertRaisesRegex(pack.PackError, "Ungültige Fabric-JAR"):
            self.prepare()

    def test_hash_tamper_rejected(self):
        data = (self.mc / "mods/commonmod.jar").read_bytes() + b"unapproved bytes"
        self.write_mc("mods/commonmod.jar", data)
        with self.assertRaisesRegex(pack.PackError, "SHA-256"):
            self.prepare()

    def test_wrong_upstream_hash_rejected(self):
        self.lock["mods"][0]["source"]["hashes"]["sha512"] = "a" * 128
        self.save_lock()
        with self.assertRaisesRegex(pack.PackError, "Quellenhashes"):
            self.prepare()

    def test_colorlight_id_filename_and_nested_rejected(self):
        for name, data in [("innocent.jar", jar("colorlight")), ("ColorLight.jar", jar("innocent")),
                           ("nested.jar", jar("nestedparent", nested={"inner.jar": jar("colorlight")}))]:
            with self.subTest(name=name):
                with self.assertRaisesRegex(pack.PackError, "ColorLight"):
                    pack.metadata(data, name)

    def test_disabled_mod_not_silently_ignored(self):
        self.write_mc("mods/old.jar.disabled", jar("oldmod"))
        with self.assertRaisesRegex(pack.PackError, "Ungeprüfte Datei"):
            pack.scan(self.root, self.instance)

    def test_client_jar_cannot_be_assigned_to_server(self):
        next(m for m in self.lock["mods"] if m["id"] == "clientmod")["side"] = "both"
        self.save_lock()
        with self.assertRaisesRegex(pack.PackError, "widerspricht"):
            self.prepare()

    def test_pack_side_override_for_universal_client_mod_preserved(self):
        self.put_mod("clientmod", side="client", env="*")
        self.save_lock()
        report, candidate = pack.scan(self.root, self.instance)
        self.assertFalse(report["changed"])
        self.assertEqual(next(m for m in candidate["mods"] if m["id"] == "clientmod")["side"], "client")
        self.assertFalse((self.prepare() / "server/mods/clientmod.jar").exists())

    def test_config_snapshot_tamper_rejected(self):
        (self.root / pack.BASE / self.lock["configs"][0]["snapshot"]).write_bytes(b"tampered")
        with self.assertRaisesRegex(pack.PackError, "SHA-256"):
            self.prepare()

    def test_changed_config_requires_explicit_approval(self):
        self.write_mc("config/gameplay.json", b'{"worldgen": false}\n')
        with self.assertRaisesRegex(pack.PackError, "SHA-256"):
            self.prepare()
        candidate = self.candidate()
        before = tree(self.instance)
        approved = pack.approve(self.root, self.instance, candidate)
        self.assertEqual(tree(self.instance), before)
        self.assertEqual(approved["status"], "approved")
        self.assertFalse(pack.scan(self.root, self.instance)[0]["changed"])
        self.assertEqual((self.prepare() / "server/config/gameplay.json").read_bytes(), b'{"worldgen": false}\n')

    def test_stale_candidate_rejected(self):
        candidate = self.candidate()
        self.lock["pack"]["name"] = "Changed separately"
        self.save_lock()
        with self.assertRaisesRegex(pack.PackError, "Veralteter"):
            pack.approve(self.root, self.instance, candidate)

    def test_candidate_not_auto_approved(self):
        _, candidate = pack.scan(self.root, self.instance)
        (self.root / pack.LOCK).write_bytes(pack.json_bytes(candidate))
        with self.assertRaisesRegex(pack.PackError, "Freigabestatus"):
            self.prepare()

    def test_rechecking_master_at_approval_prevents_stale_data(self):
        candidate = self.candidate()
        self.write_mc("mods/commonmod.jar", jar("commonmod", "2.0"))
        with self.assertRaises(pack.PackError):
            pack.approve(self.root, self.instance, candidate)

    def test_unknown_mod_can_be_reviewed_then_approved(self):
        data = jar("newclient", env="client")
        self.write_mc("mods/new.jar", data)
        candidate = self.candidate()
        d = json.loads(candidate.read_text(encoding="utf-8"))
        record = next(m for m in d["mods"] if m["id"] == "newclient")
        record.update(side="client", sideReason="Explicit review", source=source(data))
        candidate.write_bytes(pack.json_bytes(d))
        pack.approve(self.root, self.instance, candidate)
        self.assertFalse((self.prepare() / "server/mods/new.jar").exists())

    def test_unneeded_mod_removal_can_be_explicitly_approved(self):
        (self.mc / "mods/servermod.jar").unlink()
        pack.approve(self.root, self.instance, self.candidate())
        self.assertFalse((self.prepare() / "server/mods/servermod.jar").exists())

    def test_resourcepack_tamper_blocks_prepare_and_needs_new_source(self):
        self.write_mc("resourcepacks/reviewed.zip", b"new resource")
        with self.assertRaisesRegex(pack.PackError, "SHA-256"):
            self.prepare()
        report, candidate = pack.scan(self.root, self.instance)
        self.assertTrue(report["changes"]["resourcepacks"])
        self.assertIsNone(candidate["resourcepacks"][0]["source"])

    def test_private_config_paths_blocked_even_in_manifest(self):
        for path in ["config/voicechat/username-cache.json", "config/xaero/map.cfg", "config/ribbits.json",
                     "config/colorlight.json", "saves/level.dat", "config/sodium-fingerprint.json"]:
            with self.subTest(path=path):
                changed = copy.deepcopy(self.lock)
                changed["configs"][0]["path"] = path
                with self.assertRaises(pack.PackError):
                    pack.validate_lock(changed)

    def test_secrets_rejected_without_echoing_values(self):
        for text in ['{"network":{"proxyPassword":"DO-NOT-ECHO"}}', 'api_key="DO-NOT-ECHO"',
                     '-----BEGIN PRIVATE KEY-----', 'url=https://user:DO-NOT-ECHO@example.com']:
            with self.subTest(text=text):
                with self.assertRaises(pack.PackError) as error:
                    pack.config_content(text.encode(), "config/otherwise-safe.json")
                self.assertNotIn("DO-NOT-ECHO", str(error.exception))

    def test_empty_secret_fields_and_documentation_comments_allowed(self):
        pack.config_content(b'# secret=example\n{"proxyPassword":"", "api_key":null}\n', "config/default.json")

    def test_path_traversal_windows_aliases_and_case_duplicates(self):
        for path in ["../mods/test.jar", "C:/world", "mods\\bad.jar", "/absolute", "mods/CON.jar", "config/foo. "]:
            with self.subTest(path=path):
                with self.assertRaises(pack.PackError):
                    pack.relative(path)
        bad = copy.deepcopy(self.lock)
        other = copy.deepcopy(bad["mods"][1])
        other.update(id="othermod", filename=bad["mods"][1]["filename"].upper())
        bad["mods"].append(other)
        with self.assertRaises(pack.PackError):
            pack.validate_lock(bad)

    def test_output_refuses_existing_directory_and_keeps_files(self):
        destination = self.root / "dist/existing"
        destination.mkdir(parents=True)
        (destination / "private").write_bytes(b"keep")
        with self.assertRaises(pack.PackError):
            pack.prepare(self.root, self.instance, destination)
        self.assertEqual((destination / "private").read_bytes(), b"keep")

    def test_output_outside_build_dist_and_inside_master_rejected(self):
        for destination in [self.root / "server", self.root / "dist", self.mc / "mods", self.base / "production",
                            self.root / "dist/../config/danger"]:
            with self.subTest(destination=destination):
                with self.assertRaises(pack.PackError):
                    pack.prepare(self.root, self.instance, destination)

    def test_symlink_source_and_output_rejected(self):
        link = self.mc / "mods/link.jar"
        try:
            link.symlink_to(self.mc / "mods/commonmod.jar")
        except OSError:
            self.skipTest("Host account cannot create symlinks")
        with self.assertRaises(pack.PackError):
            pack.scan(self.root, self.instance)
        link.unlink()
        (self.root / "dist").symlink_to(self.mc, target_is_directory=True)
        with self.assertRaises(pack.PackError):
            self.prepare()

    def test_platform_mismatch_rejected(self):
        mmc = self.instance / "mmc-pack.json"
        d = json.loads(mmc.read_text())
        d["components"][0]["version"] = "other"
        mmc.write_text(json.dumps(d))
        with self.assertRaisesRegex(pack.PackError, "Minecraft/Fabric"):
            self.prepare()

    @unittest.skipUnless(os.name == "nt", "Windows junction test")
    def test_windows_junction_output_rejected_without_touching_target(self):
        link = self.root / "dist"
        result = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(self.mc)], capture_output=True)
        if result.returncode:
            self.skipTest("Host account cannot create junctions")
        self.addCleanup(lambda: os.rmdir(link) if link.exists() else None)
        before = tree(self.instance)
        with self.assertRaises(pack.PackError):
            self.prepare()
        self.assertEqual(tree(self.instance), before)

    def test_generated_automodpack_only_ignored_when_exact_embedded_hash_matches(self):
        generated = jar("automodpack_mod", "5.0.0-rc.5")
        outer = jar("automodpack", "5.0.0-rc.5")
        stream = io.BytesIO(outer)
        with zipfile.ZipFile(stream, "a") as z:
            z.writestr("impl/manifest.json", json.dumps({"impls": [{"id": "26.3-fabric", "length": len(generated), "sha1": hashlib.sha1(generated).hexdigest()}]}))
        outer = stream.getvalue()
        self.write_mc("mods/automodpack.jar", outer)
        record = next(m for m in self.lock["mods"] if m["id"] == "automodpack")
        record.update(sha256=pack.sha(outer), size=len(outer), source=source(outer))
        self.save_lock()
        self.write_mc("mods/automodpack-generated.jar", generated)
        self.assertFalse(pack.scan(self.root, self.instance)[0]["changed"])
        out = self.prepare()
        self.assertFalse(any(p.name == "automodpack-generated.jar" for p in out.rglob("*")))
        self.write_mc("mods/automodpack-generated.jar", generated + b"tamper")
        report, _ = pack.scan(self.root, self.instance)
        self.assertTrue(report["blockers"])
        with self.assertRaises(pack.PackError):
            self.prepare("tampered")

    def test_group_cycles_rejected(self):
        self.lock["groups"]["main"]["requires"] = ["extras"]
        with self.assertRaisesRegex(pack.PackError, "Zyklische"):
            pack.validate_lock(self.lock)

    def test_source_url_credentials_and_query_rejected(self):
        for url in ["http://modrinth.com/a", "https://user:password@modrinth.com/a", "https://modrinth.com/a?token=secret", "https://evil.test/a"]:
            s = source(b"x")
            s["url"] = url
            self.assertFalse(pack.source_valid(s))

    def test_malformed_manifest_tables_fail_cleanly(self):
        for field, value in [("mods", {}), ("pack", []), ("groups", []), ("configs", ["personal"]), ("resourcepacks", None)]:
            with self.subTest(field=field):
                broken = copy.deepcopy(self.lock)
                broken[field] = value
                with self.assertRaises(pack.PackError):
                    pack.validate_lock(broken)

    def test_copy_time_recheck_prevents_partial_output(self):
        original = pack.new_directory
        def race(destination, callback):
            self.write_mc("mods/commonmod.jar", jar("commonmod", "2.0"))
            return original(destination, callback)
        with patch.object(pack, "new_directory", side_effect=race):
            with self.assertRaises(pack.PackError):
                self.prepare()
        self.assertFalse((self.root / "dist/one").exists())


class CheckedInBaselineTests(unittest.TestCase):
    def test_complete_lock_and_required_bootstrap(self):
        lock = pack.load_lock(pack.ROOT)
        mods = {m["id"]: m for m in lock["mods"]}
        self.assertEqual(mods["automodpack"]["version"], lock["pack"]["automodpack"])
        self.assertEqual(mods["streamsreflowing"]["side"], "both")
        self.assertTrue(all(m["side"] == "client" for m in mods.values() if m["metadata"]["environment"] == "client"))
        self.assertFalse(any(pack.blocked(m["id"]) for m in mods.values()))

    def test_all_config_snapshots_and_protected_worldgen_hashes(self):
        lock = pack.load_lock(pack.ROOT)
        for config in lock["configs"]:
            data = pack.read_file(pack.ROOT / pack.BASE, config["snapshot"])
            pack.check_hash(data, config, config["path"])
            pack.config_content(data, config["path"])
        configs = {c["path"]: c for c in lock["configs"]}
        self.assertEqual(configs["config/tectonic.json"]["sha256"], "88ac9fd71410c3ba66e5a775a4d38ebd3fec819184996f3d6c3091188532adb1")
        self.assertEqual(configs["config/streamsreflowing.properties"]["sha256"], "c0b6a62d370b365df6f183f7fe0c7562e73272bfae6f6d9e85e2db732da31cff")

    def test_optional_resourcepack_groups(self):
        lock = pack.load_lock(pack.ROOT)
        self.assertEqual(len(lock["resourcepacks"]), 4)
        self.assertEqual({r["group"] for r in lock["resourcepacks"]}, {"animations", "colorful-trims"})
        self.assertTrue(all(lock["groups"][g]["selection"] == "RECOMMENDED" for g in ("animations", "colorful-trims")))


if __name__ == "__main__":
    unittest.main()
