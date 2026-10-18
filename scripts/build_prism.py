#!/usr/bin/env python3
"""Build a deterministic Prism import and standalone migration JAR with JDK 17+."""
from __future__ import annotations

import argparse
import io
import json
from pathlib import Path
import re
import subprocess
import tempfile
import zipfile

import build_serverpack as shared

ROOT = Path(__file__).resolve().parents[1]
BOOTSTRAP_SHA256 = "a8fbb24dc604278e97f4688e82d3d91a318b98efc08d5dbfcbcbcab6443d116c"
BOOTSTRAP_URL = "https://github.com/packwiz/packwiz-installer-bootstrap/releases/download/v0.0.3/packwiz-installer-bootstrap.jar"
PACK_URL = "https://bluefeniks25.github.io/a-cozy-adventure/pack.toml"
# Preserve the four official resource packs' relative priority from v0.0.2.
RESOURCE_PACK_ORDER = ("colorful-trims-rp", "fresh-animations", "fa-player-extension", "fresh-animations-extensions")


def verified_jar(path, expected, label):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise shared.BuildError(f"Expected a regular {label} JAR.")
    data = path.read_bytes()
    shared.verify(data, "sha256", expected, label)
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            if archive.testzip() is not None:
                raise shared.BuildError(f"Invalid {label} JAR CRC.")
    except zipfile.BadZipFile:
        raise shared.BuildError(f"Invalid {label} JAR.") from None
    return data


def archive_bytes(entries):
    result = io.BytesIO()
    with zipfile.ZipFile(result, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(entries.items()):
            shared.safe_path(name)
            info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data, compresslevel=9)
    return result.getvalue()


def validate_destination(root, output):
    shared.validate_output(root, output)
    for target in (output, output.with_suffix(".migration.jar")):
        for ancestor in (target, *target.parents):
            if ancestor.is_symlink():
                raise shared.BuildError("Output paths must not traverse symbolic links.")
        if target.is_dir():
            raise shared.BuildError("Output targets must be regular files.")


def fresh_options(root):
    """Seed fresh imports only; this file must never enter Packwiz or migration."""
    selected = ["vanilla"]
    for name in RESOURCE_PACK_ORDER:
        path = "resourcepacks/" + name + ".pw.toml"
        meta = shared.read_toml(shared.contained_file(root, path).read_bytes(), path)
        filename = shared.safe_path(meta.get("filename"), filename=True)
        if not filename.lower().endswith(".zip"):
            raise shared.BuildError("Official resource-pack defaults require ZIP filenames.")
        selected.append("file/" + filename)
    return ("resourcePacks:" + json.dumps(selected, ensure_ascii=False, separators=(",", ":"))
            + "\nincompatibleResourcePacks:[]\n").encode("utf-8")


def compile_launcher(root, installer, *, javac="javac"):
    source = root / "src/customization"
    sources = sorted(source.rglob("*.java"))
    if not sources or not (source / "cozy/Protector.java").is_file():
        raise shared.BuildError("Missing customization Java sources.")
    for item in sources:
        shared.contained_file(root, item.relative_to(root).as_posix())
    with tempfile.TemporaryDirectory(prefix="cozy-prism-build-") as directory:
        work = Path(directory)
        native = work / "packwiz-installer.jar"
        native.write_bytes(installer)
        classes = work / "classes"
        classes.mkdir()
        try:
            completed = subprocess.run([javac, "--release", "17", "-encoding", "UTF-8", "-cp", str(native),
                                        "-d", str(classes), *map(str, sources)], capture_output=True, text=True)
        except OSError:
            raise shared.BuildError("A JDK 17 or newer with javac is required to build the launcher.") from None
        if completed.returncode:
            raise shared.BuildError("Java compilation failed:\n" + completed.stderr)
        entries = {p.relative_to(classes).as_posix(): p.read_bytes() for p in sorted(classes.rglob("*.class"))}
    entries["META-INF/MANIFEST.MF"] = b"Manifest-Version: 1.0\r\nMain-Class: cozy.Launcher\r\n\r\n"
    entries["cozy/packwiz-installer.jar"] = installer
    entries["META-INF/PACKWIZ-LICENSE.txt"] = shared.contained_file(ROOT, "docs/customization/PACKWIZ-LICENSE.txt").read_bytes()
    return archive_bytes(entries)


def build(root=ROOT, *, installer, bootstrap, output=None, javac="javac"):
    root = Path(root).resolve()
    output = Path(output) if output else root / "dist/A-Cozy-Adventure-Prism.zip"
    validate_destination(root, output)
    native = verified_jar(installer, shared.INSTALLER_SHA256, "official Packwiz installer v0.5.14")
    bootstrap_data = verified_jar(bootstrap, BOOTSTRAP_SHA256, "official Packwiz bootstrap v0.0.3")
    # Verify every indexed source using the existing strict serverpack parser.
    shared.load_plan(root)
    pack = shared.read_toml(shared.contained_file(root, "pack.toml").read_bytes(), "pack.toml")
    version = pack.get("version")
    if not isinstance(version, str) or not re.fullmatch(r"[A-Za-z0-9.+_-]{1,80}", version):
        raise shared.BuildError("Unsafe pack version for Prism instance name.")
    launcher = compile_launcher(root, native, javac=javac)
    components = [{"uid": "net.minecraft", "version": pack["versions"]["minecraft"], "important": True},
                  {"uid": "net.fabricmc.fabric-loader", "version": pack["versions"]["fabric"]}]
    config = ("[General]\nConfigVersion=1.3\nInstanceType=OneSix\n"
              f"name=A Cozy Adventure v{version}\nAutomaticJava=true\nOverrideJavaLocation=false\n"
              "OverrideCommands=true\nPreLaunchCommand=\\\"$INST_JAVA\\\" -jar cozy-customization.jar --pack "
              + PACK_URL + "\n")
    entries = {"instance.cfg": config.encode(),
               "mmc-pack.json": shared.json_bytes({"formatVersion": 1, "components": components}),
               "minecraft/options.txt": fresh_options(root),
               "minecraft/cozy-customization.jar": launcher,
               "minecraft/packwiz-installer-bootstrap.jar": bootstrap_data}
    migration = output.with_suffix(".migration.jar")
    validate_destination(root, output)
    shared.atomic_write(output, archive_bytes(entries))
    shared.atomic_write(migration, launcher)
    return {"archive": str(output), "sha256": shared.digest(output.read_bytes(), "sha256"),
            "migrationJar": str(migration), "migrationSha256": shared.digest(launcher, "sha256"),
            "installerSha256": shared.INSTALLER_SHA256, "bootstrapSha256": BOOTSTRAP_SHA256,
            "packUrl": PACK_URL}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--installer", required=True, type=Path, help="Official v0.5.14 installer JAR (SHA-256 verified).")
    parser.add_argument("--bootstrap", required=True, type=Path, help="Original v0.0.3 bootstrap JAR (SHA-256 verified).")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--javac", default="javac")
    args = parser.parse_args(argv)
    try:
        print(json.dumps(build(installer=args.installer, bootstrap=args.bootstrap, output=args.output, javac=args.javac), indent=2))
    except shared.BuildError as error:
        parser.exit(1, str(error) + "\n")


if __name__ == "__main__":
    main()
