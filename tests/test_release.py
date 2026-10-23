"""Release consistency and fail-closed integrity regressions; no network required."""
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import sys
import tempfile
import tomllib
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import build_prism
import build_serverpack
import prepare_release

ROOT = Path(__file__).resolve().parents[1]


class PriorityParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.inside = False
        self.in_code = False
        self.filenames = []

    def handle_starttag(self, tag, attributes):
        if tag == 'ol' and dict(attributes).get('id') == 'resource-order':
            self.inside = True
        if self.inside and tag == 'code':
            self.in_code = True

    def handle_endtag(self, tag):
        if tag == 'code':
            self.in_code = False
        if tag == 'ol':
            self.inside = False

    def handle_data(self, text):
        if self.in_code:
            self.filenames.append(text.strip())


class ReleaseTests(unittest.TestCase):
    def test_fresh_options_seed_no_personal_keys_and_menu_priority_matches(self):
        options = build_prism.fresh_options(ROOT).decode()
        self.assertEqual({line.split(':', 1)[0] for line in options.splitlines()},
                         {'resourcePacks', 'incompatibleResourcePacks'})
        internal = json.loads(options.splitlines()[0].split(':', 1)[1])
        self.assertEqual(internal[0], 'vanilla')
        menu = PriorityParser()
        menu.feed((ROOT / 'index.html').read_text(encoding="utf-8"))
        self.assertEqual(menu.filenames, [name.removeprefix('file/') for name in reversed(internal[1:])])

    def test_release_keeps_original_game_versions_and_full_hash_chain(self):
        pack = tomllib.loads((ROOT / 'pack.toml').read_text(encoding="utf-8"))
        self.assertEqual(pack['version'], prepare_release.VERSION)
        self.assertEqual(pack['versions'], {'minecraft': '26.3', 'fabric': '0.19.5'})
        plan = build_serverpack.load_plan(ROOT)
        self.assertEqual(len(plan.mods), 108)
        self.assertEqual(len(plan.excluded), 28)
        self.assertEqual(len(plan.configs), 105)
        self.assertNotIn('options.txt', plan.inputs)

    def test_corrupted_cached_release_source_is_rejected_without_network(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'original.zip'
            target.write_bytes(b'corrupted archive')
            with patch.object(prepare_release, 'urlopen') as request:
                with self.assertRaises(build_serverpack.BuildError):
                    prepare_release.verified_download(target, 'https://example.invalid/original.zip',
                                                      hashlib.sha256(b'original').hexdigest(), 100)
                request.assert_not_called()
            self.assertEqual(target.read_bytes(), b'corrupted archive')

class V101PreparationTests(unittest.TestCase):
    def test_colorlight_removed_from_pack_catalog_and_server_plan(self):
        index = tomllib.loads((ROOT / 'index.toml').read_text(encoding="utf-8"))
        paths = {item['file'] for item in index['files']}
        for path in ('mods/colorlight.pw.toml', 'config/colorlight.json'):
            self.assertNotIn(path, paths)
            self.assertFalse((ROOT / path).exists())
        catalog = json.loads((ROOT / 'mods.json').read_text(encoding="utf-8"))
        self.assertNotIn('ColorLight', (ROOT / 'mods.json').read_text(encoding="utf-8"))
        lock = json.loads((ROOT / 'docs/automodpack/pack.lock.json').read_text(encoding="utf-8"))
        self.assertEqual(catalog["total"], sum(m['side'] != 'server' for m in lock['mods']))
        plan = build_serverpack.load_plan(ROOT)
        self.assertFalse(any('colorlight' in m.path for m in (*plan.mods, *plan.excluded)))

    def test_website_removes_stale_release_notice_and_colorlight_reactivation(self):
        html = (ROOT / 'index.html').read_text(encoding="utf-8")
        self.assertNotIn('Vorbereitung von v1.0.0', html)
        self.assertNotIn('Wie deaktiviere ich ColorLight?', html)
        self.assertNotIn('ColorLight', (ROOT / 'assets/guides/mods.svg').read_text(encoding="utf-8"))
        self.assertIn('GitHub-Releases bleiben als historisches Archiv', html)
        self.assertNotIn('assets/releases.js', html)
        self.assertNotIn('.migration.jar', html)

    def test_cached_dependency_audit_rejects_unknown_or_changed_pins(self):
        import audit_customization
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'mods').mkdir()
            (root / 'mods/unknown.pw.toml').write_text(
                'filename="unknown.jar"\nside="both"\n[download]\nhash-format="sha256"\nhash="abc"\n')
            with self.assertRaisesRegex(build_serverpack.BuildError, 'added or changed'):
                audit_customization.audit_snapshot(root, ROOT / 'docs/customization/dependencies.json')


if __name__ == "__main__":
    unittest.main()
