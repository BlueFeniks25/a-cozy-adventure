#!/usr/bin/env python3
"""Build review-only versioned artifacts from pinned tools and existing original JARs.

Never tags, pushes, releases, deploys, changes the pack or starts Minecraft.
Python 3.11+, JDK 17+, TLS verification and all pinned hashes are mandatory.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
import subprocess
import sys
import tomllib
from urllib.request import Request, urlopen
import zipfile

import build_prism as prism
import build_serverpack as server

ROOT = Path(__file__).resolve().parents[1]

def pack_version():
    version = tomllib.loads((ROOT / "pack.toml").read_text(encoding="utf-8"))["version"]
    if not isinstance(version, str) or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+(?:-[A-Za-z0-9.-]+)?", version):
        raise server.BuildError("Unsafe or unsupported pack version")
    return version


VERSION = pack_version()
SOURCE_URL = "https://github.com/BlueFeniks25/a-cozy-adventure/releases/download/v0.0.2/A-Cozy-Adventure-Server-v0.0.2.zip"
SOURCE_SHA256 = "95f6ff8346cb45c3303555bf8837b1cbd15ca96ce736711ce5101d36256d0f36"


def verified_download(target, url, expected, limit):
    """Retain only complete hash-verified HTTPS files; recheck cached bytes."""
    if target.exists():
        if target.is_symlink() or target.stat().st_size > limit:
            raise server.BuildError("Unsafe cached download")
        server.verify(target.read_bytes(), "sha256", expected, target.name)
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".download")
    if temporary.exists():
        raise server.BuildError("Previous partial download exists; inspect and remove it before retrying")
    try:
        request = Request(url, headers={"User-Agent": "A-Cozy-Adventure-release-preparation/1.0"})
        digest = hashlib.sha256()
        total = 0
        with urlopen(request, timeout=90) as response, temporary.open("xb") as output:
            while chunk := response.read(1024 * 1024):
                total += len(chunk)
                if total > limit:
                    raise server.BuildError("Download exceeds permitted size")
                digest.update(chunk)
                output.write(chunk)
        if digest.hexdigest() != expected:
            raise server.BuildError("Release source checksum mismatch")
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)


def original_server_jars(plan):
    """Read expected ZIP members only, never extract arbitrary archive paths."""
    archive = ROOT / "build/release-source/A-Cozy-Adventure-Server-v0.0.2.zip"
    verified_download(archive, SOURCE_URL, SOURCE_SHA256, 350 * 1024 * 1024)
    identity = hashlib.sha256("\n".join(m.filename + ":" + m.hash for m in plan.mods).encode()).hexdigest()
    destination = ROOT / "build/release-source/mods" / identity
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as source:
        if len(source.namelist()) != len(set(source.namelist())):
            raise server.BuildError("Duplicate paths in original server archive")
        for mod in plan.mods:
            try:
                member = source.getinfo("mods/" + mod.filename)
            except KeyError:
                continue  # New mod: the official installer must supply verified bytes.
            if member.file_size > 128 * 1024 * 1024:
                raise server.BuildError("Unexpected original JAR size")
            data = source.read(member)
            if server.digest(data, mod.algorithm) != mod.hash:
                continue  # Historical version is not a source for this new pin.
            server.verify(data, mod.algorithm, mod.hash, mod.filename)
            target = destination / mod.filename
            if target.is_symlink():
                raise server.BuildError("Symlink in original JAR cache")
            server.atomic_write(target, data)
    return destination


def build():
    pack = tomllib.loads((ROOT / "pack.toml").read_text(encoding="utf-8"))
    if pack.get("version") != VERSION:
        raise server.BuildError("Pack version changed during release build")
    plan = server.load_plan(ROOT)  # Check full Packwiz hash chain before downloading.
    tools = ROOT / "build/customization"
    for name, url, expected in [
        ("packwiz-installer.jar", server.INSTALLER_URL, server.INSTALLER_SHA256),
        ("v1.0.0-protection.jar", "https://github.com/BlueFeniks25/a-cozy-adventure/releases/download/v1.0.0/A-Cozy-Adventure-Prism-v1.0.0.migration.jar", "99dc680b056805515d48cab3800a096239b4206ee584402873107fe06023ffc6"),
        ("packwiz-installer-bootstrap.jar", prism.BOOTSTRAP_URL, prism.BOOTSTRAP_SHA256),
    ]:
        target = tools / name
        verified_download(target, url, expected, 32 * 1024 * 1024)
        prism.verified_jar(target, expected, name)
    originals = original_server_jars(plan)
    destination = ROOT / "dist" / ("v" + VERSION)
    destination.mkdir(parents=True, exist_ok=True)
    built = prism.build(ROOT, installer=tools / "packwiz-installer.jar",
                        bootstrap=tools / "packwiz-installer-bootstrap.jar",
                        output=destination / f"A-Cozy-Adventure-Prism-v{VERSION}.zip")
    server_zip = destination / f"A-Cozy-Adventure-Server-v{VERSION}.zip"
    report = server.build(ROOT, source_mods=originals, output=server_zip, download=True)
    if report["status"] != "built" or not report["archiveWritten"]:
        raise server.BuildError("Server archive failed; inspect " + str(server_zip.with_suffix(".report.json")))
    for filename in [built["archive"], str(server_zip)]:
        with zipfile.ZipFile(filename) as archive:
            if archive.testzip() is not None:
                raise server.BuildError("Built ZIP failed CRC validation")
    # Assert exact original server payload, not just counts or exit status.
    with zipfile.ZipFile(server_zip) as archive:
        for mod in plan.mods:
            server.verify(archive.read("mods/" + mod.filename), mod.algorithm, mod.hash, mod.filename)
        for name, data in plan.configs.items():
            if archive.read(name) != data:
                raise server.BuildError("Server config payload changed: " + name)
        manifest = json.loads(archive.read("build-manifest.json"))
        if manifest["pack"]["version"] != VERSION:
            raise server.BuildError("Wrong pack version in server manifest")
    result = {
        "schemaVersion": 1, "version": VERSION, "status": "built-for-review",
        "source": plan.source,
        "toolchain": subprocess.check_output(["javac", "-version"], text=True, stderr=subprocess.STDOUT).strip(),
        "minecraft": pack["versions"]["minecraft"], "fabric": pack["versions"]["fabric"], "gameJava": "25",
        "verifiedServerJars": len(plan.mods), "unchangedServerConfigs": len(plan.configs),
        "sourceArchiveSha256": SOURCE_SHA256,
        "installerSha256": server.INSTALLER_SHA256, "bootstrapSha256": prism.BOOTSTRAP_SHA256,
        "minecraftGui": "not-run", "dedicatedServerRuntime": "not-run", "published": False,
        "tests": "Separate current-run unittest/browser logs required; build success is not a test result",
        "prismPackEndpoint": prism.PACK_URL,
        "rolloutWarning": "Migrate old instances before main/Pages changes. Do not accept fresh imports against older live pack metadata.",
    }
    server.atomic_write(destination / "validation.json", server.json_bytes(result))
    for name in [f"v{VERSION}.md", f"v{VERSION}-rollout.md"]:
        server.atomic_write(destination / name, (ROOT / "docs/releases" / name).read_bytes())
    outputs = sorted(p for p in destination.iterdir() if p.is_file() and p.name != "SHA256SUMS.txt")
    checksums = "".join(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}\n" for p in outputs)
    server.atomic_write(destination / "SHA256SUMS.txt", checksums.encode())
    print(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    try:
        build()
    except (server.BuildError, OSError, ValueError, KeyError, zipfile.BadZipFile) as error:
        sys.exit(str(error))
