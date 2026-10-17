"""Offline unit and integration tests for the local server-pack builder."""
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import tomllib
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_serverpack as builder


def jar_bytes(mod_id, version="1.0.0", *, depends=None, provides=None, nested=None,
              environment="*", breaks=None, conflicts=None):
    meta = {"schemaVersion": 1, "id": mod_id, "version": version,
            "environment": environment, "depends": depends or {}, "provides": provides or [],
            "breaks": breaks or {}, "conflicts": conflicts or {}}
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        if nested:
            meta["jars"] = [{"file": p} for p in nested]
            for path, data in nested.items():
                archive.writestr(path, data)
        archive.writestr("fabric.mod.json", json.dumps(meta))
    return stream.getvalue()


class ServerpackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "repo"
        self.root.mkdir()
        self.source = self.base / "private-local-jars"
        self.source.mkdir()
        self.output = self.root / "dist/server.zip"
        for folder in ("mods", "resourcepacks", "config", "docs/serverpack", "config-review", "saves"):
            (self.root / folder).mkdir(parents=True)
        self.specs = {"common": ("both", jar_bytes("commonmod")),
                      "server": ("server", jar_bytes("servermod", depends={"commonmod": ">=1.0.0", "minecraft": "~26.3-", "fabricloader": ">=0.19.5", "java": ">=25", "mixinextras": ">=0.5.5"})),
                      "client": ("client", jar_bytes("clientmod", environment="client"))}
        for name, (_, data) in self.specs.items():
            (self.source / f"{name}.jar").write_bytes(data)
            self.write_mod(name)
        (self.root / "config/server.json").write_text('{"gameplay": true}\n')
        (self.root / "config/client.json").write_text('{"hud": true}\n')
        (self.root / "config-review/security.cfg").write_text("secret=must-not-be-copied")
        (self.root / "saves/private-world.txt").write_text("private-world")
        (self.root / "index.html").write_text("website")
        resource = 'name = "Client resources"\nfilename = "client.zip"\nside = "client"\n[download]\nurl = "https://cdn.modrinth.com/client.zip"\nhash-format = "sha256"\nhash = "' + "a" * 64 + '"\n'
        (self.root / "resourcepacks/client.pw.toml").write_text(resource)
        self.policy = {"schemaVersion": 1, "expectedTotalMods": 3, "expectedServerMods": 2,
                       "include": [{"reason": "Server gameplay.", "files": ["config/server.json"]}],
                       "exclude": [{"reason": "Client HUD.", "files": ["config/client.json"]}],
                       "questions": [{"id": "host-voicechat", "detail": "Obtain the assigned UDP port; no production default."}]}
        self.write_policy()
        (self.root / builder.SERVER_README).write_text("# Server\nMinecraft 26.3 / Fabric 0.19.5 / Java 25\n")
        self.refresh()
        self.addCleanup(patch.stopall)
        patch.object(builder, "source_revision", return_value={"commit": "a" * 40, "dirty": False}).start()
        patch.object(builder, "urlopen", side_effect=AssertionError("Network disabled in tests.")).start()

    def write_mod(self, name):
        side, data = self.specs[name]
        text = (f'name = "Test {name}"\nfilename = "{name}.jar"\nside = "{side}"\n'
                '[download]\nurl = "https://cdn.modrinth.com/test.jar"\nhash-format = "sha256"\nhash = "'
                + hashlib.sha256(data).hexdigest() + '"\n[update.modrinth]\nmod-id = "TestMod"\nversion = "Version1"\n')
        (self.root / f"mods/{name}.pw.toml").write_text(text, encoding="utf-8")

    def replace_jar(self, name, data):
        self.specs[name] = (self.specs[name][0], data)
        (self.source / f"{name}.jar").write_bytes(data)
        self.write_mod(name)
        self.refresh()

    def write_policy(self):
        (self.root / builder.POLICY).write_bytes(builder.json_bytes(self.policy))

    def refresh(self):
        lines = ['hash-format = "sha256"', ""]
        for folder in ("config", "mods", "resourcepacks"):
            for path in sorted((self.root / folder).rglob("*")):
                if not path.is_file():
                    continue
                lines += ["[[files]]", "file = " + json.dumps(path.relative_to(self.root).as_posix()),
                          "hash = " + json.dumps(hashlib.sha256(path.read_bytes()).hexdigest())]
                if path.name.endswith(".pw.toml"):
                    lines.append("metafile = true")
                lines.append("")
        raw = ("\n".join(lines) + "\n").encode()
        (self.root / "index.toml").write_bytes(raw)
        (self.root / "pack.toml").write_text('name = "Test Pack"\npack-format = "packwiz:1.1.0"\n[index]\nfile = "index.toml"\nhash-format = "sha256"\nhash = "' + hashlib.sha256(raw).hexdigest() + '"\n[versions]\nminecraft = "26.3"\nfabric = "0.19.5"\n')

    def run_build(self, **kwargs):
        return builder.build(self.root, source_mods=self.source, output=self.output, **kwargs)

    def snapshot(self):
        return {p.relative_to(self.root).as_posix(): p.read_bytes() for p in self.root.rglob("*") if p.is_file() and p.suffix == ".toml"}

    def test_selects_both_and_server_excludes_client(self):
        plan = builder.load_plan(self.root)
        self.assertEqual([m.filename for m in plan.mods], ["common.jar", "server.jar"])
        self.assertEqual([m.filename for m in plan.excluded], ["client.jar"])

    def test_real_repository_has_107_and_preserves_five_libraries(self):
        plan = builder.load_plan()
        self.assertEqual(len(plan.mods), 107)
        self.assertEqual(len(plan.excluded), 29)
        paths = {m.path for m in plan.mods}
        for name in ("creativecore", "iceberg-fabric", "fabric-language-kotlin", "yacl", "baguettelib"):
            self.assertIn(f"mods/{name}.pw.toml", paths)
        self.assertEqual(len(plan.configs), 106)
        self.assertEqual(len(plan.excluded_configs), 125)

    def test_unknown_side_fails(self):
        p = self.root / "mods/common.pw.toml"
        p.write_text(p.read_text().replace('side = "both"', 'side = "mystery"'))
        self.refresh()
        report = self.run_build()
        self.assertEqual(report["status"], "failed")
        self.assertIn("side", " ".join(report["errors"]))
        self.assertFalse(self.output.exists())

    def test_missing_side_and_invalid_toml_fail(self):
        p = self.root / "mods/common.pw.toml"
        original = p.read_text()
        for text in (original.replace('side = "both"\n', ''), 'name = ['):
            with self.subTest(text=text[:20]):
                p.write_text(text)
                self.refresh()
                self.assertEqual(self.run_build()["status"], "failed")

    def test_corrupt_pack_index_and_metadata_hashes_fail(self):
        for relative in ("index.toml", "mods/common.pw.toml", "config/server.json"):
            with self.subTest(relative=relative):
                self.refresh()
                p = self.root / relative
                original = p.read_bytes()
                p.write_bytes(original + b"\n")
                self.assertEqual(self.run_build()["status"], "failed")
                p.write_bytes(original)

    def test_duplicate_filenames_case_insensitive_fail(self):
        p = self.root / "mods/server.pw.toml"
        p.write_text(p.read_text().replace('filename = "server.jar"', 'filename = "COMMON.jar"'))
        self.refresh()
        self.assertEqual(self.run_build()["status"], "failed")

    def test_unsafe_mod_filenames_fail(self):
        p = self.root / "mods/common.pw.toml"
        original = p.read_text()
        for name in ("../escape.jar", "/absolute.jar", "C:/private.jar", "sub/evil.jar", "NUL.jar", "bad.jar."):
            with self.subTest(name=name):
                p.write_text(original.replace('"common.jar"', json.dumps(name)))
                self.refresh()
                self.assertEqual(self.run_build()["status"], "failed")

    def test_unsafe_paths(self):
        for path in ("../a", "/a", "a/../b", "a//b", "a\\b", "C:/a", "a:stream", "a\x00b", "a/CON.txt", "file. "):
            with self.subTest(path=path), self.assertRaises(builder.BuildError):
                builder.safe_path(path)

    def test_unknown_hash_algorithm_and_invalid_hash_fail(self):
        p = self.root / "mods/common.pw.toml"
        original = p.read_text()
        for text in (original.replace('"sha256"', '"unknown"'), original.replace(hashlib.sha256(self.specs['common'][1]).hexdigest(), "bad")):
            p.write_text(text)
            self.refresh()
            self.assertEqual(self.run_build()["status"], "failed")

    def test_source_url_credentials_are_rejected(self):
        p = self.root / "mods/common.pw.toml"
        p.write_text(p.read_text().replace('https://cdn.modrinth.com/test.jar', 'https://user:secret@example.com/test.jar'))
        self.refresh()
        report = self.run_build()
        self.assertEqual(report['status'], 'failed')
        self.assertNotIn('user:secret', json.dumps(report))

    def test_invalid_project_version_metadata_fails(self):
        p = self.root / "mods/common.pw.toml"
        p.write_text(p.read_text().replace('version = "Version1"', 'version = ""'))
        self.refresh()
        self.assertEqual(self.run_build()["status"], "failed")

    def test_nonindexed_mod_metadata_fails(self):
        (self.root / 'mods/unindexed.pw.toml').write_text('side = "both"')
        self.assertEqual(self.run_build()['status'], 'failed')

    def test_expected_count_guard(self):
        self.policy['expectedServerMods'] = 107
        self.write_policy()
        self.assertEqual(self.run_build()['status'], 'failed')

    def test_missing_jars_report_names_hashes_sources_without_zip(self):
        (self.source / "server.jar").unlink()
        report = self.run_build()
        self.assertEqual(report["status"], "failed")
        self.assertFalse(self.output.exists())
        self.assertEqual(report["missing"][0]["name"], "Test server")
        self.assertEqual(report["missing"][0]["filename"], "server.jar")
        self.assertEqual(len(report["missing"][0]["hash"]), 64)
        self.assertIn("modrinth.com", report["missing"][0]["originalSource"])
        self.assertTrue(self.output.with_suffix(".report.json").is_file())
        self.assertTrue(self.output.with_suffix(".report.txt").is_file())

    def test_invalid_jar_hash_fails_without_network_fallback(self):
        (self.source / "common.jar").write_bytes(b"wrong version")
        with patch.object(builder, "run_installer") as install:
            report = self.run_build(download=True)
        install.assert_not_called()
        self.assertEqual(report["status"], "failed")
        self.assertEqual(len(report['invalid']), 1)
        self.assertIn('Hash mismatch', report['invalid'][0]['error'])
        self.assertFalse(self.output.exists())

    def test_valid_hash_but_invalid_fabric_jar_fails(self):
        self.replace_jar("common", b"hash-valid but not a JAR")
        self.assertEqual(self.run_build()["status"], "failed")

    def test_client_environment_in_server_selection_fails(self):
        self.replace_jar("common", jar_bytes("commonmod", environment="client"))
        self.assertEqual(self.run_build()["status"], "failed")

    def test_missing_and_wrong_dependency_versions_fail(self):
        for requirement in ({"missingmod": "*"}, {"commonmod": ">=2.0.0"}):
            self.replace_jar("server", jar_bytes("servermod", depends=requirement))
            report = self.run_build()
            self.assertEqual(report["status"], "failed")
            self.assertEqual(report["dependencies"]["status"], "failed")
            self.assertFalse(self.output.exists())

    def test_nested_dependencies_and_aliases_are_available(self):
        nested = jar_bytes("nestedlib", "2.0.0", provides=["aliaslib"])
        self.replace_jar("common", jar_bytes("commonmod", nested={"META-INF/jars/lib.jar": nested}))
        self.replace_jar("server", jar_bytes("servermod", depends={"aliaslib": ">=2.0.0"}))
        report = self.run_build()
        self.assertEqual(report['status'], 'built', report)
        with zipfile.ZipFile(self.output) as archive:
            manifest = json.loads(archive.read('build-manifest.json'))
            self.assertIn('aliaslib', manifest['dependencies']['availableModIds'])

    def test_nested_traversal_is_rejected(self):
        self.replace_jar('common', jar_bytes('commonmod', nested={'../escape.jar': jar_bytes('evillib')}))
        self.assertEqual(self.run_build()['status'], 'failed')

    def test_declared_breaks_prevents_build(self):
        self.replace_jar('server', jar_bytes('servermod', breaks={'commonmod': '>=1.0.0'}))
        self.assertEqual(self.run_build()['status'], 'failed')

    def test_soft_conflicts_are_reported(self):
        self.replace_jar('server', jar_bytes('servermod', conflicts={'commonmod': '*'}))
        report = self.run_build()
        self.assertEqual(report['status'], 'built')
        self.assertTrue(report['warnings'])

    def test_absent_conflict_ids_are_not_reported_as_available(self):
        self.replace_jar('server', jar_bytes('servermod', conflicts={'absentmod': '*'}))
        report = self.run_build()
        self.assertEqual(report['status'], 'built')
        self.assertNotIn('absentmod', report['dependencies']['availableModIds'])

    def test_duplicate_root_ids_across_download_batches_fail(self):
        (self.source/'server.jar').unlink()
        data = jar_bytes('commonmod', '1.0.0')
        self.specs['server'] = ('server', data)
        self.write_mod('server')
        self.refresh()
        retrieved = self.base/'retrieved'
        retrieved.mkdir()
        (retrieved/'server.jar').write_bytes(data)
        with patch.object(builder, 'run_installer', return_value=(retrieved, None)):
            report = self.run_build(download=True)
        self.assertEqual(report['status'], 'failed')
        self.assertFalse(self.output.exists())

    def test_nonobject_policy_fails_without_traceback(self):
        (self.root/builder.POLICY).write_text('[]')
        report = self.run_build()
        self.assertEqual(report['status'], 'failed')

    def test_config_whitelist_is_exhaustive_and_cannot_include_review_files(self):
        self.policy['include'][0]['files'].append('config-review/security.cfg')
        self.write_policy()
        self.assertEqual(self.run_build()['status'], 'failed')
        self.policy['include'][0]['files'].pop()
        self.policy['exclude'] = []
        self.write_policy()
        self.assertEqual(self.run_build()['status'], 'failed')

    def test_new_config_requires_explicit_review(self):
        (self.root / 'config/new.json').write_text('{}')
        self.refresh()
        self.assertEqual(self.run_build()['status'], 'failed')

    def test_zip_has_only_explicit_payload_and_manifest(self):
        before = self.snapshot()
        (self.source / 'unexpected.jar').write_bytes(b'never copy me')
        report = self.run_build()
        self.assertEqual(report['status'], 'built', report)
        with zipfile.ZipFile(self.output) as archive:
            expected = ['README-SERVER.md', 'build-manifest.json', 'build-report.json', 'build-report.txt',
                        'config/server.json', 'mods/common.jar', 'mods/server.jar']
            self.assertEqual(archive.namelist(), sorted(expected))
            self.assertEqual(archive.read('config/server.json'), (self.root/'config/server.json').read_bytes())
            manifest = json.loads(archive.read('build-manifest.json'))
            self.assertEqual(len(manifest['mods']), 2)
            self.assertEqual(manifest['mods'][0]['fabricVersion'], '1.0.0')
            self.assertEqual([m['filename'] for m in manifest['excludedMods']], ['client.jar'])
            self.assertEqual(manifest['source']['commit'], 'a'*40)
            public = archive.read('build-manifest.json').decode()
            self.assertNotIn(str(self.base), public)
            self.assertNotIn('private-local-jars', public)
            self.assertNotIn('secret=must-not-be-copied', public)
            self.assertTrue(all(i.date_time==(1980,1,1,0,0,0) for i in archive.infolist()))
        self.assertEqual(before, self.snapshot())

    def test_reproducible_archives(self):
        self.assertEqual(self.run_build()['status'], 'built')
        first = self.output.read_bytes()
        second = self.root / 'dist/other.zip'
        result = builder.build(self.root, source_mods=self.source, output=second)
        self.assertEqual(result['status'], 'built')
        self.assertEqual(first, second.read_bytes())

    def test_failure_preserves_previous_archive_and_reports_it(self):
        self.assertEqual(self.run_build()['status'], 'built')
        before = self.output.read_bytes()
        (self.source/'server.jar').unlink()
        report = self.run_build()
        self.assertEqual(report['status'], 'failed')
        self.assertTrue(report['previousArchivePreserved'])
        self.assertFalse(report['archiveWritten'])
        self.assertEqual(before, self.output.read_bytes())
        self.assertIn('NOT the result', self.output.with_suffix('.report.txt').read_text())

    def test_archive_write_failure_leaves_no_partial_zip(self):
        with patch.object(zipfile.ZipFile, 'writestr', side_effect=OSError('simulated write failure')):
            report = self.run_build()
        self.assertEqual(report['status'], 'failed')
        self.assertFalse(self.output.exists())
        self.assertFalse(list(self.output.parent.glob('.serverpack-*.tmp')))

    def test_input_changes_during_validation_stop_archive_creation(self):
        original = builder.validate_dependencies

        def change_source(nodes):
            result = original(nodes)
            (self.root/'config/server.json').write_text('{"changed": true}')
            return result

        with patch.object(builder, 'validate_dependencies', side_effect=change_source):
            report = self.run_build()
        self.assertEqual(report['status'], 'failed')
        self.assertIn('Source inputs changed', ' '.join(report['errors']))
        self.assertFalse(self.output.exists())

    def test_source_symlink_cannot_import_an_unreviewed_file(self):
        source = self.source/'common.jar'
        target = self.base/'external.jar'
        target.write_bytes(source.read_bytes())
        source.unlink()
        try:
            source.symlink_to(target)
        except OSError:
            if sys.platform != 'win32':
                raise
            self.skipTest('Creating symlinks is not permitted on this host.')
        report = self.run_build()
        self.assertEqual(report['status'], 'failed')
        self.assertFalse(self.output.exists())

    def test_invalid_resource_metadata_is_rejected(self):
        p = self.root/'resourcepacks/client.pw.toml'
        p.write_text(p.read_text().replace('filename = "client.zip"', 'filename = "../escape.zip"'))
        self.refresh()
        self.assertEqual(self.run_build()['status'], 'failed')

    def test_dry_run_is_offline_and_writes_no_outputs(self):
        with patch.object(builder, 'run_installer') as install:
            report = builder.build(self.root, output=self.output, dry_run=True, download=True)
        self.assertEqual(report['status'], 'planned')
        self.assertFalse(report['readyForArchive'])
        self.assertEqual(len(report['missing']), 2)
        self.assertEqual(report['dependencies']['status'], 'pending')
        install.assert_not_called()
        self.assertFalse(self.output.parent.exists())

    def test_dry_run_with_valid_jars_checks_dependencies(self):
        report = self.run_build(dry_run=True)
        self.assertEqual(report['status'], 'planned')
        self.assertTrue(report['readyForArchive'])
        self.assertEqual(report['dependencies']['status'], 'passed')
        self.assertFalse(self.output.exists())

    def test_dry_run_preserves_existing_archive_without_reporting_a_failed_build(self):
        self.assertEqual(self.run_build()['status'], 'built')
        paths = [self.output, self.output.with_suffix('.report.json'), self.output.with_suffix('.report.txt')]
        before = {p: p.read_bytes() for p in paths}
        for source in (None, self.source):
            with self.subTest(local_jars=source is not None):
                report = builder.build(self.root, source_mods=source, output=self.output, dry_run=True)
                self.assertEqual(report['status'], 'planned')
                self.assertTrue(report['previousArchivePreserved'])
                self.assertFalse(report['archiveWritten'])
                text = builder.report_text(report)
                self.assertIn('left unchanged by this dry run', text)
                self.assertNotIn('failed build', text)
                self.assertEqual(before, {p: p.read_bytes() for p in paths})

    def test_safe_output_location(self):
        with self.assertRaises(builder.BuildError):
            builder.build(self.root, output=self.root/'docs/overwrite.zip')
        with self.assertRaises(builder.BuildError):
            builder.build(self.root, output=self.root/'pack.toml')

    def test_installer_result_is_filtered_and_reverified(self):
        (self.source/'server.jar').unlink()
        retrieved = self.base/'installer-result'
        retrieved.mkdir()
        (retrieved/'server.jar').write_bytes(self.specs['server'][1])
        (retrieved/'client.jar').write_bytes(self.specs['client'][1])
        (retrieved/'unexpected.jar').write_bytes(b'unchecked')
        with patch.object(builder, 'run_installer', return_value=(retrieved, None)) as install:
            report = self.run_build(download=True)
        self.assertEqual(report['status'], 'built', report)
        self.assertEqual([m['filename'] for m in install.call_args.args[1]], ['server.jar'])
        with zipfile.ZipFile(self.output) as archive:
            self.assertNotIn('mods/client.jar', archive.namelist())
            self.assertNotIn('mods/unexpected.jar', archive.namelist())

    def test_installer_return_code_and_hash_failure_cannot_succeed(self):
        (self.source/'server.jar').unlink()
        retrieved = self.base/'installer-result'
        retrieved.mkdir()
        with patch.object(builder, 'run_installer', return_value=(retrieved, 'Installer failed.')):
            self.assertEqual(self.run_build(download=True)['status'], 'failed')
        (retrieved/'server.jar').write_bytes(b'wrong hash')
        with patch.object(builder, 'run_installer', return_value=(retrieved, None)):
            report = self.run_build(download=True)
            self.assertEqual(report['status'], 'failed')
            self.assertTrue(report['invalid'])

    def test_isolated_installer_definition_contains_only_expected_mods(self):
        plan = builder.load_plan(self.root)
        stage = self.base/'definition'
        stage.mkdir()
        builder.write_server_definition(plan, stage, plan.mods)
        index = tomllib.loads((stage/'index.toml').read_text())
        self.assertEqual([e['file'] for e in index['files']], ['mods/common.pw.toml', 'mods/server.pw.toml'])
        pack = tomllib.loads((stage/'pack.toml').read_text())
        self.assertEqual(hashlib.sha256((stage/'index.toml').read_bytes()).hexdigest(), pack['index']['hash'])
        for entry in index['files']:
            self.assertEqual((stage/entry['file']).read_bytes(), (self.root/entry['file']).read_bytes())

    def test_installer_uses_pinned_tool_and_local_file_uri(self):
        plan = builder.load_plan(self.root)
        fake_tool = b'official tool fixture'
        work = self.base/'installer-work'
        work.mkdir()
        with patch.object(builder, 'urlopen', return_value=io.BytesIO(fake_tool)) as request, \
                patch.object(builder, 'INSTALLER_SHA256', hashlib.sha256(fake_tool).hexdigest()), \
                patch.object(builder.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)) as run:
            folder, issue = builder.run_installer(plan, [plan.mods[0].public()], work, 'test-java')
        self.assertIsNone(issue)
        self.assertEqual(folder, work/'installed/mods')
        self.assertEqual(request.call_args.args[0].full_url, builder.INSTALLER_URL)
        command = run.call_args.args[0]
        self.assertEqual(command[0], 'test-java')
        self.assertIn('link.infra.packwiz.installer.Main', command)
        self.assertIn('-s', command)
        self.assertEqual(command[-1], (work/'definition/pack.toml').as_uri())
        self.assertEqual(run.call_args.kwargs['cwd'], work/'installed')
        self.assertEqual(run.call_args.kwargs['stdin'], subprocess.DEVNULL)

    def test_installer_hash_failure_never_executes_java(self):
        plan = builder.load_plan(self.root)
        work = self.base/'installer-work'
        work.mkdir()
        with patch.object(builder, 'urlopen', return_value=io.BytesIO(b'tampered tool')), \
                patch.object(builder.subprocess, 'run') as run:
            _, issue = builder.run_installer(plan, [plan.mods[0].public()], work, 'test-java')
        self.assertIsNotNone(issue)
        run.assert_not_called()

    def test_cli_help_and_offline_dry_run(self):
        script = builder.ROOT/'scripts/build_serverpack.py'
        help_result = subprocess.run([sys.executable, '-B', str(script), '--help'], capture_output=True, text=True)
        self.assertEqual(help_result.returncode, 0)
        self.assertIn('--source-mods', help_result.stdout)
        result = subprocess.run([sys.executable, '-B', str(script), '--dry-run', '--output', str(self.base/'dry.zip')], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Selected server mods: 107', result.stdout)
        self.assertIn('Status: planned', result.stdout)
        self.assertFalse((self.base/'dry.zip').exists())


class FabricVersionTests(unittest.TestCase):
    def test_fabric_ranges(self):
        cases = [('26.3', '~26.3-', True), ('26.4-pre-1', '~26.3-', False),
                 ('26.3', '26.3.X', True), ('26.3', '>=26.3 <26.4', True),
                 ('1.1.3+26.1', '>=1.1.0+26.2', True), ('0.9.3-alpha.1', '0.9.x', True),
                 ('0.3.0', '^0.2.0', True), ('2.0.0-alpha', '^1.0.0', False),
                 ('1.0.0', ['>=2', '=1.0'], True), ('1.0.0', '>1', False),
                 ('opaque', 'opaque', True), ('opaque', '*', True)]
        for version, requirement, expected in cases:
            with self.subTest(version=version, requirement=requirement):
                self.assertEqual(builder.matches_version(version, requirement), expected)

    def test_empty_prerelease_and_numeric_identifiers(self):
        self.assertLess(builder.compare_versions('1.0-', '1.0-alpha'), 0)
        self.assertLess(builder.compare_versions('1.0-alpha.2', '1.0-alpha.10'), 0)
        self.assertEqual(builder.compare_versions('1.0+old', '1.0.0+new'), 0)

    def test_invalid_ranges_fail_closed(self):
        for requirement in ('', [], {}, ['*', 7], '>=opaque', '>=1.x'):
            with self.subTest(requirement=requirement), self.assertRaises(builder.BuildError):
                builder.matches_version('1.0', requirement)


if __name__ == '__main__':
    unittest.main()
