"""Generator contracts: inventory, identity, failure recovery and Packwiz safety."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import generate_mods as generator


class GeneratorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "mods").mkdir()
        (self.root / "resourcepacks").mkdir()
        (self.root / "pack.toml").write_text('name = "Test Pack"\n[versions]\nminecraft = "test-version"\nfabric = "test-fabric"\n', encoding="utf-8")
        self.add_mod("cozy", 'name = "Cozy Test"\nfilename = "cozy.jar"\n[download]\nhash-format = "sha1"\nhash = "abc123"\n[update.curseforge]\nproject-id = 1234\nfile-id = 42\n')

    def add_mod(self, name, content):
        (self.root / "mods" / f"{name}.pw.toml").write_text(content, encoding="utf-8")

    def load(self):
        return generator.load_pack(self.root)

    def test_only_installed_mod_metadata_is_included(self):
        (self.root / "resourcepacks" / "not-a-mod.pw.toml").write_text('name = "Resource pack"')
        (self.root / "mods" / "not-metadata.jar").write_bytes(b"not a jar")
        pack, records, fingerprint = self.load()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["source"], "CurseForge")
        data = generator.build_catalog(pack, records, fingerprint, {}, {})
        self.assertEqual(data["pack"]["minecraft"], "test-version")
        self.assertEqual(data["mods"][0]["url"], "https://www.curseforge.com/projects/1234")
        self.assertEqual(data["mods"][0]["name"], "Cozy Test")
        self.assertEqual(data["mods"][0]["descriptionKind"], "category-fallback")

    def test_offline_command_does_not_change_pack_files(self):
        before = {p: p.read_bytes() for p in self.root.rglob("*.toml")}
        proc = subprocess.run([sys.executable, "-B", str(generator.ROOT / "scripts/generate_mods.py"),
                               "--root", str(self.root), "--offline"], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(before, {p: p.read_bytes() for p in self.root.rglob("*.toml")})
        self.assertEqual(json.loads((self.root / "mods.json").read_text(encoding="utf-8"))["total"], 1)

    def test_hash_match_preserves_curseforge_source(self):
        pack, records, fingerprint = self.load()
        calls = []
        def api(url, payload=None, **kwargs):
            calls.append((url, payload))
            if url.endswith("/version_files"):
                self.assertEqual(payload, {"algorithm": "sha1", "hashes": ["abc123"]})
                return {"abc123": {"project_id": "Verified"}}
            return [{"id": "Verified", "title": "Verified Mod", "description": "An original summary", "categories": ["adventure"], "icon_url": "https://cdn.modrinth.com/icon.png"}]
        with patch.dict(generator.os.environ, {}, clear=True):
            metadata = generator.fetch_metadata(records, {}, request=api)
        mod = generator.build_catalog(pack, records, fingerprint, metadata, {})["mods"][0]
        self.assertEqual(mod["source"], "CurseForge")
        self.assertEqual(mod["metadataSource"], "Modrinth")
        self.assertEqual(mod["metadataUrl"], "https://modrinth.com/mod/Verified")
        self.assertEqual(mod["name"], "Verified Mod")
        self.assertEqual(len(calls), 2)

    def test_api_failure_preserves_cache_and_excludes_removed_mods(self):
        _, records, _ = self.load()
        identity = records[0]["identity"]
        cached = {identity: {"name": "Cached"}, "removed": {"name": "Gone"}}
        with patch.dict(generator.os.environ, {}, clear=True):
            result = generator.fetch_metadata(records, cached, request=lambda *a, **k: None)
        self.assertEqual(result, {identity: {"name": "Cached"}})

    def test_changed_hash_cannot_reuse_old_metadata(self):
        _, records, _ = self.load()
        old_identity = records[0]["identity"]
        self.add_mod("cozy", (self.root / "mods/cozy.pw.toml").read_text().replace("abc123", "newhash"))
        _, changed, _ = self.load()
        self.assertNotEqual(changed[0]["identity"], old_identity)
        with patch.dict(generator.os.environ, {}, clear=True):
            result = generator.fetch_metadata(changed, {old_identity: {"name": "Old"}}, request=lambda *a, **k: None)
        self.assertEqual(result, {})

    def test_native_modrinth_and_missing_update_fields(self):
        self.add_mod("native", 'name = "Native"\n[update.modrinth]\nmod-id = "NativeID"\nversion = "unchanged"\n')
        self.add_mod("custom", 'name = "Custom"\n')
        pack, records, fingerprint = self.load()
        with patch.dict(generator.os.environ, {}, clear=True):
            metadata = generator.fetch_metadata(records, {}, request=lambda *a, **k: None)
        mods = {m["id"]: m for m in generator.build_catalog(pack, records, fingerprint, metadata, {})["mods"]}
        self.assertEqual(mods["native"]["url"], "https://modrinth.com/mod/NativeID")
        self.assertIsNone(mods["custom"]["url"])
        self.assertEqual(mods["custom"]["source"], "Unbekannt")

    def test_optional_curseforge_key_never_enters_generated_data(self):
        pack, records, fingerprint = self.load()
        key = "FAKE-TEST-KEY-NEVER-REAL"
        def api(url, payload=None, **kwargs):
            if "api.curseforge.com" in url:
                self.assertEqual(kwargs["api_key"], key)
                return {"data": [{"id": 1234, "name": "CF Name", "summary": "Official", "categories": [{"name": "Magic"}], "authors": [{"name": "Author"}], "links": {"websiteUrl": "https://www.curseforge.com/projects/1234"}}]}
            return None
        with patch.dict(generator.os.environ, {"CURSEFORGE_API_KEY": key}, clear=True):
            metadata = generator.fetch_metadata(records, {}, request=api)
        data = generator.build_catalog(pack, records, fingerprint, metadata, {})
        self.assertEqual(data["mods"][0]["metadataSource"], "CurseForge")
        self.assertNotIn(key, json.dumps(data))
        self.assertNotIn(key, json.dumps(metadata))

    def test_unsafe_links_and_unapproved_icon_hosts_are_removed(self):
        for value in ["javascript:alert(1)", "http://example.com", "https://name:password@example.com", None]:
            self.assertIsNone(generator.https_url(value))
        self.assertIsNone(generator.https_url("https://tracking.example.com/icon.png", icon=True))
        self.assertIsNone(generator.https_url("https://cdn.modrinth.com.evil.test/a", icon=True))
        self.assertEqual(generator.https_url("https://media.forgecdn.net/icon.png", icon=True), "https://media.forgecdn.net/icon.png")

    def test_missing_optional_project_fields(self):
        data = generator.normalize_modrinth({"id": "ABC", "title": "Minimal", "license": None,
                                             "categories": None, "additional_categories": None})
        self.assertIsNone(data["icon"])
        self.assertIsNone(data["license"])
        self.assertEqual(data["tags"], [])
        self.assertEqual(data["summary"], "")

    def test_rate_limit_http_date_does_not_break_fallback(self):
        from urllib.error import HTTPError
        error = HTTPError("https://api.modrinth.com/v2/projects", 429, "Rate limited",
                          {"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"}, None)
        with patch.object(generator, "urlopen", side_effect=error) as request, patch.object(generator.time, "sleep"):
            self.assertIsNone(generator.request_json("https://api.modrinth.com/v2/projects"))
            self.assertEqual(request.call_count, 3)

    def test_description_and_category_fallbacks_are_deterministic(self):
        pack, records, fingerprint = self.load()
        records[0]["packwizName"] = "Brand New Magic Mod"
        metadata = {records[0]["identity"]: {"tags": ["magic", "adventure"]}}
        before = deepcopy(records)
        data = generator.build_catalog(pack, records, fingerprint, metadata, {})
        self.assertIn("Magie", data["mods"][0]["categories"])
        self.assertTrue(data["mods"][0]["description"])
        self.assertEqual(data, generator.build_catalog(pack, records, fingerprint, metadata, {}))
        self.assertEqual(records, before)

    def test_check_detects_added_removed_and_changed_mods(self):
        script = str(generator.ROOT / "scripts/generate_mods.py")
        command = [sys.executable, "-B", script, "--root", str(self.root)]
        self.assertEqual(subprocess.run(command + ["--offline"], capture_output=True).returncode, 0)
        self.assertEqual(subprocess.run(command + ["--check"], capture_output=True).returncode, 0)
        self.add_mod("new", 'name = "New Mod"\n')
        self.assertEqual(subprocess.run(command + ["--check"], capture_output=True).returncode, 1)
        subprocess.run(command + ["--offline"], capture_output=True, check=True)
        (self.root / "mods/cozy.pw.toml").unlink()
        self.assertEqual(subprocess.run(command + ["--check"], capture_output=True).returncode, 1)

    def test_bad_toml_fails_without_replacing_catalog(self):
        output = self.root / "mods.json"
        output.write_text('{"sentinel": true}')
        self.add_mod("bad", "not = valid toml[")
        proc = subprocess.run([sys.executable, "-B", str(generator.ROOT / "scripts/generate_mods.py"), "--root", str(self.root), "--offline"], capture_output=True)
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(json.loads(output.read_text()), {"sentinel": True})

    def test_repository_catalog_covers_exact_inventory(self):
        pack, records, fingerprint = generator.load_pack(generator.ROOT)
        cache = generator.read_json(generator.ROOT / "catalog/metadata-cache.json", {"entries": {}})
        descriptions = generator.read_json(generator.ROOT / "catalog/descriptions.de.json", {})
        data = generator.build_catalog(pack, records, fingerprint, cache["entries"], descriptions)
        self.assertEqual({m["id"] for m in data["mods"]}, {r["id"] for r in records})
        self.assertEqual(len(data["mods"]), len({m["id"] for m in data["mods"]}))
        self.assertTrue(all(m["description"] and m["categories"] for m in data["mods"]))
        self.assertEqual(sum(c["count"] for c in data["categories"]), sum(len(m["categories"]) for m in data["mods"]))

class AutoModpackCatalogTests(unittest.TestCase):
    def test_repository_catalog_tracks_approved_manifest(self):
        lock = json.loads((generator.ROOT / 'docs/automodpack/pack.lock.json').read_text())
        _, records, _ = generator.load_pack(generator.ROOT)
        expected = {m['id']: m for m in lock['mods'] if m['side'] != 'server'}
        self.assertEqual({r['fabricId'] for r in records}, set(expected))
        self.assertEqual(len({r['id'] for r in records}), len(records))
        versions = {r['fabricId']: r['version'] for r in records}
        self.assertEqual(versions['fabric-api'], '0.165.0+26.3')
        self.assertEqual(versions['automodpack'], '5.0.0-rc.5')
        self.assertTrue(any(r['version'] == '2.15.2' and 'streams' in r['fabricId'] for r in records))
        self.assertNotIn('colorlight', versions)
        for r in records:
            self.assertEqual(r['filename'], expected[r['fabricId']]['filename'])

    def test_lock_inventory_works_without_packwiz_and_ignores_private_fields(self):
        lock = json.loads((generator.ROOT / 'docs/automodpack/pack.lock.json').read_text())
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'docs/automodpack/pack.lock.json'
            path.parent.mkdir(parents=True)
            lock['configs'] = [{'private': 'DO-NOT-PUBLISH'}]
            lock['mods'][0]['side'] = 'server'
            path.write_text(json.dumps(lock))
            pack, records, fingerprint = generator.load_pack(root)
            data = generator.build_catalog(pack, records, fingerprint, {}, {})
            self.assertNotIn(lock['mods'][0]['id'], {r['fabricId'] for r in records})
            self.assertNotIn('DO-NOT-PUBLISH', json.dumps(data))
            self.assertEqual(len(records), len(lock['mods']) - 1)
            lock['status'] = 'candidate'
            path.write_text(json.dumps(lock))
            with self.assertRaises(ValueError): generator.load_pack(root)


if __name__ == "__main__":
    unittest.main()
