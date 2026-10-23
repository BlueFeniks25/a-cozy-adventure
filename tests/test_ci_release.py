"""Version/path validation and historical source reuse must fail closed."""
import hashlib
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import prepare_release as release


class ReleaseRoutingTests(unittest.TestCase):
    def test_dynamic_version_rejects_output_or_path_injection(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(release, 'ROOT', Path(directory)):
            pack = Path(directory)/'pack.toml'
            for version in ['1.0.2', '1.1.0', '2.0.0-beta.1']:
                pack.write_text('version="' + version + '"')
                self.assertEqual(release.pack_version(), version)
            for version in ['../1.0.2', 'v1.0.2', '1.0.2/extra', '1.0.2\\nvalue=bad']:
                pack.write_text('version="' + version + '"')
                with self.assertRaises(release.server.BuildError): release.pack_version()

    def test_historical_archive_only_seeds_matching_current_hashes(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(release, 'ROOT', Path(directory)), patch.object(release, 'verified_download'):
            archive = Path(directory)/'build/release-source/A-Cozy-Adventure-Server-v0.0.2.zip'
            archive.parent.mkdir(parents=True)
            with zipfile.ZipFile(archive, 'w') as z:
                z.writestr('mods/unchanged.jar', b'unchanged')
                z.writestr('mods/updated.jar', b'old')
            def mod(name, data): return SimpleNamespace(filename=name, algorithm='sha256', hash=hashlib.sha256(data).hexdigest())
            plan = SimpleNamespace(mods=[mod('unchanged.jar', b'unchanged'), mod('updated.jar', b'new'), mod('added.jar', b'added')])
            folder = release.original_server_jars(plan)
            self.assertEqual([p.name for p in folder.iterdir()], ['unchanged.jar'])
            self.assertEqual((folder/'unchanged.jar').read_bytes(), b'unchanged')
