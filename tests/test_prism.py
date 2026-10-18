"""Prism packaging and real Java migration against isolated instance fixtures."""
import hashlib
import io
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build_prism as builder


class PrismPackagingTests(unittest.TestCase):
    def test_archives_are_deterministic_and_portable(self):
        first = builder.archive_bytes({"b": b"two", "a": b"one"})
        self.assertEqual(first, builder.archive_bytes({"a": b"one", "b": b"two"}))
        with zipfile.ZipFile(io.BytesIO(first)) as archive:
            self.assertIsNone(archive.testzip())
            self.assertEqual(archive.namelist(), ["a", "b"])
            self.assertEqual(archive.getinfo("a").date_time, (1980, 1, 1, 0, 0, 0))
        with self.assertRaises(builder.shared.BuildError):
            builder.archive_bytes({"../escape": b"bad"})

    def test_native_tool_integrity_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "tampered.jar"
            source.write_bytes(b"not the official tool")
            with self.assertRaisesRegex(builder.shared.BuildError, "Hash mismatch"):
                builder.verified_jar(source, builder.shared.INSTALLER_SHA256, "installer")

    def test_protected_source_and_output_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(builder.shared.BuildError):
                builder.validate_destination(root, root / "docs/danger.zip")
            (root / "dist").mkdir()
            (root / "dist/out.migration.jar").mkdir()
            with self.assertRaises(builder.shared.BuildError):
                builder.validate_destination(root, root / "dist/out.zip")


@unittest.skipUnless(shutil.which("java") and shutil.which("javac"), "A JDK 17+ is required for migration tests.")
class MigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workspace = tempfile.TemporaryDirectory()
        cls.root = Path(cls.workspace.name)
        sources = cls.root / "src/customization/cozy"
        sources.mkdir(parents=True)
        shutil.copyfile(builder.ROOT / "src/customization/cozy/Launcher.java", sources / "Launcher.java")
        # Exercise the launcher and migration without replacing native E2E coverage.
        (sources / "Protector.java").write_text(
            'package cozy; public final class Protector { public static void main(String[] args) {} }', encoding="utf-8")
        cls.jar = cls.root / "migration.jar"
        cls.jar.write_bytes(builder.compile_launcher(cls.root, builder.archive_bytes({"fixture": b"unused-native"})))

    @classmethod
    def tearDownClass(cls):
        cls.workspace.cleanup()

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.instance = Path(self.temporary.name) / "Cozy Instance with spaces"
        self.minecraft = self.instance / "minecraft"
        self.minecraft.mkdir(parents=True)
        self.original = ('[General]\r\nname=My Cozy Instance\r\nInstanceType=OneSix\r\n'
                         'OverrideCommands=true\r\nPreLaunchCommand=\\"$INST_JAVA\\" -jar '
                         'packwiz-installer-bootstrap.jar ' + builder.PACK_URL + '\r\n'
                         'CustomSetting=preserve me\r\n[Other]\r\nkeep=42\r\n').encode()
        (self.instance / "instance.cfg").write_bytes(self.original)
        (self.instance / "mmc-pack.json").write_text('{"formatVersion":1,"components":[]}', encoding="utf-8")
        for relative in ("mods/private.jar", "resourcepacks/private.zip", "shaderpacks/private.zip", "options.txt",
                         "saves/world/level.dat", "packwiz.json", "config/personal.json"):
            target = self.minecraft / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(("personal " + relative).encode())

    def migrate(self):
        return subprocess.run(["java", "-Djava.awt.headless=true", "-jar", str(self.jar), "--migrate", str(self.instance)],
                              capture_output=True, text=True, timeout=30)

    def inventory(self):
        return {p.relative_to(self.minecraft).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in self.minecraft.rglob("*") if p.is_file()}

    def test_migration_backs_up_settings_preserves_personal_files_and_is_idempotent(self):
        personal = self.inventory()
        result = self.migrate()
        self.assertEqual(result.returncode, 0, result.stderr)
        backup = self.instance / "instance.cfg.before-customization"
        self.assertEqual(backup.read_bytes(), self.original)
        config = (self.instance / "instance.cfg").read_bytes()
        self.assertIn(b"-jar cozy-customization.jar --pack ", config)
        self.assertIn(b"CustomSetting=preserve me\r\n[Other]\r\nkeep=42\r\n", config)
        after = self.inventory()
        self.assertEqual({p: after[p] for p in personal}, personal)
        self.assertEqual((self.minecraft / "cozy-customization.jar").read_bytes(), self.jar.read_bytes())
        target = self.minecraft / "cozy-customization.jar"
        before = (target.stat().st_mtime_ns, (self.instance / "instance.cfg").stat().st_mtime_ns, backup.stat().st_mtime_ns)
        result = self.migrate()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(before, (target.stat().st_mtime_ns, (self.instance / "instance.cfg").stat().st_mtime_ns, backup.stat().st_mtime_ns))

    def test_dot_minecraft_layout(self):
        self.minecraft.rename(self.instance / ".minecraft")
        result = self.migrate()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.instance / ".minecraft/cozy-customization.jar").is_file())

    def test_interrupted_migration_resumes_with_existing_backup_and_jar(self):
        backup = self.instance / "instance.cfg.before-customization"
        backup.write_bytes(self.original)
        target = self.minecraft / "cozy-customization.jar"
        target.write_bytes(self.jar.read_bytes())
        personal = self.inventory()
        result = self.migrate()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(b"-jar cozy-customization.jar --pack", (self.instance / "instance.cfg").read_bytes())
        self.assertEqual(backup.read_bytes(), self.original)
        self.assertEqual(self.inventory(), personal)
        # A missing launcher after the command switch can also be restored safely.
        target.unlink()
        result = self.migrate()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(target.read_bytes(), self.jar.read_bytes())
        self.assertEqual(backup.read_bytes(), self.original)

    def test_unknown_prelaunch_is_preserved(self):
        config = self.instance / "instance.cfg"
        unknown = self.original.replace(b"packwiz-installer-bootstrap.jar", b"my-custom-script.jar")
        config.write_bytes(unknown)
        personal = self.inventory()
        result = self.migrate()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Unknown PreLaunchCommand", result.stderr)
        self.assertEqual(config.read_bytes(), unknown)
        self.assertEqual(self.inventory(), personal)
        self.assertFalse((self.instance / "instance.cfg.before-customization").exists())

    def test_existing_unrelated_jar_is_never_overwritten(self):
        (self.minecraft / "cozy-customization.jar").write_bytes(b"personal collision")
        personal = self.inventory()
        result = self.migrate()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.inventory(), personal)
        self.assertEqual((self.instance / "instance.cfg").read_bytes(), self.original)

    def test_backup_collision_is_preserved(self):
        backup = self.instance / "instance.cfg.before-customization"
        backup.write_bytes(b"previous unrelated backup")
        result = self.migrate()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(backup.read_bytes(), b"previous unrelated backup")
        self.assertEqual((self.instance / "instance.cfg").read_bytes(), self.original)
        self.assertFalse((self.minecraft / "cozy-customization.jar").exists())

    def test_ambiguous_minecraft_directory_fails_without_changes(self):
        (self.instance / ".minecraft").mkdir()
        result = self.migrate()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.instance / "instance.cfg").read_bytes(), self.original)

    def test_duplicate_commands_fail_without_changes(self):
        config = self.instance / "instance.cfg"
        duplicate = self.original.replace(b"CustomSetting=", b"PreLaunchCommand=malicious\r\nCustomSetting=")
        config.write_bytes(duplicate)
        result = self.migrate()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(config.read_bytes(), duplicate)

    def test_native_integrity_failure_creates_no_tools(self):
        result = subprocess.run(["java", "-Djava.awt.headless=true", "-jar", str(self.jar), "--pack", builder.PACK_URL,
                                 "--headless"], cwd=self.minecraft, capture_output=True, text=True, timeout=30)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("integrity check failed", result.stderr)
        self.assertFalse((self.minecraft / ".cozy").exists())

    def test_symlink_minecraft_is_rejected(self):
        outside = Path(self.temporary.name) / "outside"
        outside.mkdir()
        self.minecraft.rename(self.instance / "saved-minecraft")
        try:
            self.minecraft.symlink_to(outside, target_is_directory=True)
        except OSError:
            self.skipTest("Creating symbolic links is not permitted on this host.")
        result = self.migrate()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(list(outside.iterdir()), [])
        self.assertEqual((self.instance / "instance.cfg").read_bytes(), self.original)

    def test_complete_prism_build_is_repeatable_and_seeds_only_resource_defaults(self):
        installer = self.instance / "native.jar"
        bootstrap = self.instance / "bootstrap.jar"
        installer.write_bytes(builder.archive_bytes({"fixture": b"native"}))
        bootstrap.write_bytes(b"bootstrap-fixture")
        (self.root / "pack.toml").write_text('version="0.0.2"\n[versions]\nminecraft="26.3"\nfabric="0.19.5"\n', encoding="utf-8")
        resources = self.root / "resourcepacks"
        resources.mkdir(exist_ok=True)
        for index, name in enumerate(builder.RESOURCE_PACK_ORDER):
            (resources / (name + ".pw.toml")).write_text('filename="Resource ' + str(index) + '.zip"\n', encoding="utf-8")
        output = self.root / "dist/Prism.zip"
        with patch.object(builder, "verified_jar", side_effect=lambda path, *_: Path(path).read_bytes()), \
                patch.object(builder.shared, "load_plan"):
            builder.build(self.root, installer=installer, bootstrap=bootstrap, output=output)
            before = output.read_bytes()
            builder.build(self.root, installer=installer, bootstrap=bootstrap, output=output)
        self.assertEqual(before, output.read_bytes())
        with zipfile.ZipFile(io.BytesIO(before)) as archive:
            self.assertEqual(set(archive.namelist()), {"instance.cfg", "mmc-pack.json", "minecraft/options.txt", "minecraft/cozy-customization.jar",
                                                      "minecraft/packwiz-installer-bootstrap.jar"})
            self.assertEqual(archive.read("minecraft/options.txt"),
                             b'resourcePacks:["vanilla","file/Resource 0.zip","file/Resource 1.zip","file/Resource 2.zip","file/Resource 3.zip"]\nincompatibleResourcePacks:[]\n')
            self.assertIn(b"--pack " + builder.PACK_URL.encode(), archive.read("instance.cfg"))
            with zipfile.ZipFile(io.BytesIO(archive.read("minecraft/cozy-customization.jar"))) as jar:
                self.assertEqual(jar.read("cozy/packwiz-installer.jar"), installer.read_bytes())


if __name__ == "__main__":
    unittest.main()
