#!/usr/bin/env python3
"""Build a verified server ZIP from the local Packwiz pack, using Python 3.11+."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass, field
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
import zipfile

ROOT = Path(__file__).resolve().parents[1]
POLICY = "docs/serverpack/config-selection.json"
SERVER_README = "docs/serverpack/README-SERVER.md"
TARGET = {"minecraft": "26.3", "fabric": "0.19.5"}
BUILTINS = {"minecraft": "26.3", "fabricloader": "0.19.5", "java": "25", "mixinextras": "0.5.5"}
INSTALLER_URL = "https://github.com/packwiz/packwiz-installer/releases/download/v0.5.14/packwiz-installer.jar"
INSTALLER_SHA256 = "c9f646908d340d84773948a9a7d98bc1dae250d35e1016dc6e2b8459760b5598"
MAX_JAR = 512 * 1024 * 1024
MOD_ID = re.compile(r"[a-z][a-z0-9_-]{1,63}\Z")


class BuildError(Exception):
    """An actionable validation failure, safe to include in a public report."""


def safe_path(value, *, filename=False):
    """Accept portable relative paths without traversal or Windows aliases."""
    if not isinstance(value, str) or not value or "\\" in value:
        raise BuildError("Invalid relative file path.")
    parts = value.split("/")
    if filename and len(parts) != 1:
        raise BuildError("A mod filename must be a single portable .jar filename.")
    for part in parts:
        if (part in ("", ".", "..") or part.endswith((" ", "."))
                or re.search(r'[\x00-\x1f\x7f<>:"|?*]', part)
                or part.split(".")[0].upper() in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}):
            raise BuildError("Unsafe or non-portable relative file path.")
    if PurePosixPath(value).is_absolute():
        raise BuildError("Absolute paths are not allowed in pack metadata.")
    return value


def contained_file(root, relative):
    relative = safe_path(relative)
    root = root.resolve()
    p = root / relative
    for parent in [p, *p.parents]:
        if parent == root:
            break
        if parent.is_symlink():
            raise BuildError(f"Symlinks are not allowed: {relative}")
    if not p.resolve().is_relative_to(root) or not p.is_file():
        raise BuildError(f"Missing or unsafe source file: {relative}")
    return p


def digest(data, algorithm):
    if algorithm not in {"sha1", "sha256", "sha512", "md5"}:
        raise BuildError("Unsupported Packwiz hash format; expected sha1, sha256, sha512 or md5.")
    return hashlib.new(algorithm, data).hexdigest()


def check_hash_spec(algorithm, value):
    length = len(digest(b"", algorithm))
    if not isinstance(value, str) or not re.fullmatch(f"[0-9a-fA-F]{{{length}}}", value):
        raise BuildError("Invalid Packwiz hash value.")


def verify(data, algorithm, expected, label):
    check_hash_spec(algorithm, expected)
    if digest(data, algorithm) != expected.lower():
        raise BuildError(f"Hash mismatch: {label} ({algorithm}, expected {expected.lower()}).")


def read_toml(data, label):
    try:
        return tomllib.loads(data.decode("utf-8"))
    except (UnicodeError, tomllib.TOMLDecodeError):
        raise BuildError(f"Invalid TOML: {label}") from None


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise BuildError("Duplicate JSON property.")
        result[key] = value
    return result


def read_json(data, label):
    try:
        # Fabric's JSON reader accepts literal control characters in descriptions.
        return json.loads(data.decode("utf-8-sig"), strict=False, object_pairs_hook=unique_object)
    except (UnicodeError, ValueError, BuildError):
        raise BuildError(f"Invalid JSON: {label}") from None


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


@dataclass
class Mod:
    path: str
    name: str
    filename: str
    side: str
    algorithm: str
    hash: str
    source: str
    raw: bytes = field(repr=False)

    def public(self):
        return {"name": self.name, "filename": self.filename, "side": self.side,
                "hashFormat": self.algorithm, "hash": self.hash, "originalSource": self.source,
                "packwizFile": self.path}


@dataclass
class Plan:
    root: Path
    mods: list[Mod]
    excluded: list[Mod]
    configs: dict[str, bytes]
    excluded_configs: list[dict]
    questions: list[dict]
    source: dict
    inputs: dict[str, bytes] = field(repr=False)


def parse_mod(path, raw):
    meta = read_toml(raw, path)
    name, filename, side = (meta.get(k) for k in ("name", "filename", "side"))
    if not isinstance(name, str) or not name.strip() or len(name) > 256 or any(ord(c) < 32 for c in name):
        raise BuildError(f"Invalid mod name: {path}")
    safe_path(filename, filename=True)
    if not filename.lower().endswith(".jar"):
        raise BuildError(f"Expected a JAR filename: {path}")
    if side not in ("client", "server", "both"):
        raise BuildError(f"Unknown or missing side: {path}; expected client, server or both.")
    download = meta.get("download", {})
    if not isinstance(download, dict):
        raise BuildError(f"Invalid download metadata: {path}")
    algorithm, file_hash = download.get("hash-format"), download.get("hash")
    check_hash_spec(algorithm, file_hash)
    update = meta.get("update", {})
    if not isinstance(update, dict):
        raise BuildError(f"Invalid version metadata: {path}")
    mode = download.get("mode", "url")
    if mode not in ("url", "metadata:curseforge"):
        raise BuildError(f"Unsupported download mode: {path}")
    source = None
    if "curseforge" in update:
        cf = update["curseforge"]
        if not isinstance(cf, dict) or not all(type(cf.get(k)) is int and cf[k] > 0 for k in ("project-id", "file-id")):
            raise BuildError(f"Invalid CurseForge project/file version: {path}")
        source = f"https://www.curseforge.com/projects/{cf['project-id']}/files/{cf['file-id']}"
    if "modrinth" in update:
        mr = update["modrinth"]
        if not isinstance(mr, dict) or not all(isinstance(mr.get(k), str) and re.fullmatch(r"[A-Za-z0-9]+", mr[k]) for k in ("mod-id", "version")):
            raise BuildError(f"Invalid Modrinth project/version: {path}")
        source = f"https://modrinth.com/mod/{mr['mod-id']}/version/{mr['version']}"
    if mode == "metadata:curseforge" and "curseforge" not in update:
        raise BuildError(f"CurseForge download mode without project/file metadata: {path}")
    if mode == "url":
        url = download.get("url")
        if not isinstance(url, str):
            raise BuildError(f"Missing download URL: {path}")
        parsed = urlsplit(url)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise BuildError(f"Expected a public HTTPS download URL without credentials or query parameters: {path}")
        source = source or url
    return Mod(path, name, filename, side, algorithm, file_hash.lower(), source, raw)


def source_revision(root):
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, stderr=subprocess.DEVNULL, text=True).strip()
        dirty = bool(subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=normal"], cwd=root, stderr=subprocess.DEVNULL))
        return {"commit": commit, "dirty": dirty}
    except (OSError, subprocess.CalledProcessError):
        return {"commit": None, "dirty": True}


def load_plan(root=ROOT):
    root = root.resolve()
    inputs = {}

    def read(relative):
        data = contained_file(root, relative).read_bytes()
        inputs[relative] = data
        return data

    pack = read_toml(read("pack.toml"), "pack.toml")
    if pack.get("versions") != TARGET:
        raise BuildError("This A2 builder supports only Minecraft 26.3 and Fabric Loader 0.19.5.")
    info = pack.get("index", {})
    index_path = safe_path(info.get("file"))
    raw = read(index_path)
    verify(raw, info.get("hash-format"), info.get("hash"), index_path)
    index = read_toml(raw, index_path)
    files = index.get("files")
    if not isinstance(files, list):
        raise BuildError("Invalid Packwiz index file list.")
    seen, indexed, configs, mods = set(), set(), {}, []
    for entry in files:
        if not isinstance(entry, dict):
            raise BuildError("Invalid Packwiz index entry.")
        path = safe_path(entry.get("file"))
        if path.casefold() in seen or entry.get("alias"):
            raise BuildError("Duplicate paths or unsupported aliases in Packwiz index.")
        seen.add(path.casefold())
        indexed.add(path)
        raw = read(path)
        verify(raw, entry.get("hash-format", index.get("hash-format")), entry.get("hash"), path)
        if path.startswith("mods/"):
            if not entry.get("metafile") or not path.endswith(".pw.toml"):
                raise BuildError("The mods index must contain only Packwiz metadata.")
            mods.append(parse_mod(path, raw))
        elif path.startswith("config/"):
            if entry.get("metafile"):
                raise BuildError("Remote configuration metadata is not supported in A2.")
            configs[path] = raw
        elif path.startswith("resourcepacks/"):
            resource = read_toml(raw, path)
            if not entry.get("metafile") or resource.get("side") not in ("client", "server", "both"):
                raise BuildError(f"Invalid resource-pack metadata: {path}")
            safe_path(resource.get("filename"), filename=True)
            download = resource.get("download", {})
            if not isinstance(download, dict):
                raise BuildError(f"Invalid resource-pack download metadata: {path}")
            check_hash_spec(download.get("hash-format"), download.get("hash"))
    disk_mods = {p.relative_to(root).as_posix() for p in (root / "mods").glob("*.pw.toml")}
    if disk_mods != {m.path for m in mods}:
        raise BuildError("Mod metadata inventory differs from the Packwiz index; refresh and review it first.")
    names = [m.filename.casefold() for m in mods]
    if len(names) != len(set(names)):
        raise BuildError("Duplicate mod filenames, including case-insensitive collisions.")
    selected = sorted((m for m in mods if m.side in ("both", "server")), key=lambda m: m.path)
    excluded = sorted((m for m in mods if m.side == "client"), key=lambda m: m.path)
    policy = read_json(read(POLICY), POLICY)
    if not isinstance(policy, dict) or policy.get("schemaVersion") != 1:
        raise BuildError("Unsupported config-selection schema.")
    if len(selected) != policy.get("expectedServerMods") or len(mods) != policy.get("expectedTotalMods"):
        raise BuildError("Mod counts differ from the reviewed config-selection policy; review before building.")
    included, excluded_configs, classified = {}, [], set()
    for decision in ("include", "exclude"):
        groups = policy.get(decision)
        if not isinstance(groups, list):
            raise BuildError("Missing explicit configuration decisions.")
        for group in groups:
            if not isinstance(group, dict) or not isinstance(group.get("reason"), str) or not group["reason"] or not isinstance(group.get("files"), list):
                raise BuildError("Invalid configuration decision group.")
            for path in group["files"]:
                safe_path(path)
                if not path.startswith("config/") or path not in configs or path in classified:
                    raise BuildError("Configuration policy must classify each indexed config file exactly once.")
                classified.add(path)
                if decision == "include":
                    included[path] = configs[path]
                else:
                    excluded_configs.append({"path": path, "reason": group["reason"]})
    if classified != set(configs):
        raise BuildError("Unreviewed configuration files; update the explicit config-selection policy.")
    questions = policy.get("questions")
    if not isinstance(questions, list) or not all(isinstance(q, dict) and isinstance(q.get("id"), str) and isinstance(q.get("detail"), str) for q in questions):
        raise BuildError("Invalid configuration questions.")
    read(SERVER_README)
    # Include the implementation in the fingerprint without embedding local paths.
    inputs["scripts/build_serverpack.py"] = Path(__file__).read_bytes()
    source = source_revision(root)
    h = hashlib.sha256()
    for path, raw in sorted(inputs.items()):
        h.update(path.encode() + b"\0" + hashlib.sha256(raw).digest())
    source["inputSha256"] = h.hexdigest()
    return Plan(root, selected, excluded, dict(sorted(included.items())), excluded_configs, questions, source, inputs)


def version_parts(value):
    match = re.fullmatch(r"(\d+(?:\.\d+)*)(?:-([0-9A-Za-z.-]*))?(?:\+.*)?", value)
    if not match:
        return None
    return tuple(map(int, match[1].split("."))), None if match[2] is None else match[2].split(".")


def compare_versions(left, right):
    a, b = version_parts(left), version_parts(right)
    if a is None or b is None:
        if left == right:
            return 0
        raise BuildError("A non-semantic version cannot be ordered; manual review required.")
    width = max(len(a[0]), len(b[0]))
    av, bv = a[0] + (0,) * (width - len(a[0])), b[0] + (0,) * (width - len(b[0]))
    if av != bv:
        return (av > bv) - (av < bv)
    if a[1] is None or b[1] is None:
        return (a[1] is None) - (b[1] is None)
    for x, y in zip(a[1], b[1]):
        if x == y:
            continue
        if x == "" or y == "":
            return (x != "") - (y != "")
        if x.isdigit() and y.isdigit():
            return (int(x) > int(y)) - (int(x) < int(y))
        if x.isdigit() != y.isdigit():
            return -1 if x.isdigit() else 1
        return (x > y) - (x < y)
    return (len(a[1]) > len(b[1])) - (len(a[1]) < len(b[1]))


def matches_version(version, ranges):
    """Implement Fabric's AND ranges, OR arrays, X ranges, tilde and caret."""
    if isinstance(ranges, list):
        if not ranges or not all(isinstance(r, str) for r in ranges):
            raise BuildError("Invalid dependency version range.")
        return any(matches_version(version, r) for r in ranges)
    if not isinstance(ranges, str) or not ranges.strip():
        raise BuildError("Invalid dependency version range.")
    if "||" in ranges:
        return any(matches_version(version, part.strip()) for part in ranges.split("||"))
    for token in ranges.split():
        if token == "*":
            continue
        m = re.fullmatch(r"(>=|<=|>|<|=|~|\^)?(.+)", token)
        if not m:
            raise BuildError("Unsupported dependency version range.")
        op, target = m[1] or "=", m[2]
        if re.search(r"(?:^|\.)(?:x|X|\*)(?:\.|$)", target):
            parts = target.split(".")
            prefix = []
            for part in parts:
                if part in ("x", "X", "*"):
                    break
                if not part.isdigit():
                    raise BuildError("Invalid wildcard dependency range.")
                prefix.append(int(part))
            if op != "=" or not prefix or not version_parts(version):
                raise BuildError("Unsupported wildcard dependency range.")
            actual = version_parts(version)[0]
            if (actual + (0,) * len(prefix))[:len(prefix)] != tuple(prefix):
                return False
            continue
        if op == "=" and (version_parts(version) is None or version_parts(target) is None):
            if version != target:
                return False
            continue
        c = compare_versions(version, target)
        if op in ("~", "^"):
            parts = list(version_parts(target)[0])
            at = 0 if op == "^" or len(parts) == 1 else 1
            upper = parts[:at + 1]
            upper[at] += 1
            if c < 0 or compare_versions(version, ".".join(map(str, upper)) + "-") >= 0:
                return False
        elif not {"=": c == 0, ">": c > 0, ">=": c >= 0, "<": c < 0, "<=": c <= 0}[op]:
            return False
    return True


def inspect_jar(data, label, *, depth=0, budget=None):
    """Read declared nested metadata without extracting any archive members."""
    budget = budget if budget is not None else [MAX_JAR]
    budget[0] -= len(data)
    if depth > 8 or budget[0] < 0:
        raise BuildError(f"Nested JAR size/depth limit exceeded: {label}")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            if len(archive.namelist()) != len(set(archive.namelist())):
                raise BuildError(f"Duplicate JAR members: {label}")
            meta_info = archive.getinfo("fabric.mod.json")
            if meta_info.file_size > 2 * 1024 * 1024:
                raise BuildError(f"Oversized Fabric metadata: {label}")
            meta = read_json(archive.read(meta_info), label)
            if not isinstance(meta, dict) or not isinstance(meta.get("id"), str) or not MOD_ID.fullmatch(meta["id"]) or not isinstance(meta.get("version"), str) or not meta["version"]:
                raise BuildError(f"Invalid Fabric id/version: {label}")
            env = meta.get("environment", "*")
            if env not in ("*", "client", "server"):
                raise BuildError(f"Invalid Fabric environment: {label}")
            aliases = meta.get("provides", [])
            if not isinstance(aliases, list) or not all(isinstance(v, str) and MOD_ID.fullmatch(v) for v in aliases):
                raise BuildError(f"Invalid Fabric provides aliases: {label}")
            for kind in ("depends", "breaks", "conflicts"):
                deps = meta.get(kind, {})
                if not isinstance(deps, dict) or not all(isinstance(k, str) and MOD_ID.fullmatch(k) for k in deps):
                    raise BuildError(f"Invalid Fabric {kind}: {label}")
                for requirement in deps.values():
                    matches_version("0", requirement)
            node = {"id": meta["id"], "version": meta["version"], "environment": env,
                    "provides": aliases, "depends": meta.get("depends", {}),
                    "breaks": meta.get("breaks", {}), "conflicts": meta.get("conflicts", {}),
                    "location": label, "topLevel": depth == 0}
            nodes = [node]
            nested = meta.get("jars", [])
            if not isinstance(nested, list):
                raise BuildError(f"Invalid nested JAR list: {label}")
            for entry in nested:
                if not isinstance(entry, dict):
                    raise BuildError(f"Invalid nested JAR entry: {label}")
                path = safe_path(entry.get("file"))
                info = archive.getinfo(path)
                if info.file_size > budget[0]:
                    raise BuildError(f"Oversized nested JAR: {label}")
                nodes.extend(inspect_jar(archive.read(info), label + "!" + path, depth=depth + 1, budget=budget))
            return nodes
    except (zipfile.BadZipFile, KeyError, RuntimeError, NotImplementedError):
        raise BuildError(f"Invalid JAR or missing Fabric/nested metadata: {label}") from None


def validate_dependencies(nodes):
    """Check available versions; leave complete loader resolution to Phase B."""
    providers, disabled, warnings = defaultdict(list), set(), []
    for key, version in BUILTINS.items():
        providers[key].append({"id": key, "version": version})
    active, roots = {}, set()
    for node in nodes:
        if node.get("topLevel"):
            if node["id"] in roots:
                raise BuildError(f"Duplicate top-level Fabric mod id: {node['id']}")
            roots.add(node["id"])
        if node["environment"] == "client":
            disabled.update([node["id"], *node["provides"]])
            continue
        key = node["id"]
        previous = active.get(key)
        if previous is None or compare_versions(node["version"], previous["version"]) > 0:
            active[key] = node
    for node in active.values():
        for key in [node["id"], *node["provides"]]:
            providers[key].append(node)
    errors = []
    for node in sorted(active.values(), key=lambda n: n["id"]):
        for key, requirement in node["depends"].items():
            if key not in providers and key in disabled:
                warnings.append(f"Environment-disabled dependency: {node['id']} -> {key}; confirm with Fabric in Phase B.")
            elif not any(matches_version(p["version"], requirement) for p in providers.get(key, [])):
                errors.append(f"{node['id']} {node['version']} requires {key} {json.dumps(requirement)}; no matching available version.")
        for kind in ("breaks", "conflicts"):
            for key, requirement in node[kind].items():
                if any(matches_version(p["version"], requirement) for p in providers.get(key, [])):
                    message = f"{node['id']} declares {kind} with {key} {json.dumps(requirement)}."
                    (errors if kind == "breaks" else warnings).append(message)
    return {"status": "failed" if errors else "passed", "errors": errors,
            "warnings": sorted(set(warnings)), "availableModIds": sorted(providers),
            "scope": "Static availability check, not a complete Fabric resolver or runtime test."}


def collect_jars(mods, source, destination):
    missing, invalid, nodes, found, roots = [], [], [], [], set()
    for mod in mods:
        if source is None or not (source / mod.filename).exists():
            missing.append(mod.public())
            continue
        try:
            path = contained_file(source, mod.filename)
            if path.stat().st_size > MAX_JAR:
                raise BuildError(f"Oversized JAR: {mod.filename}")
            data = path.read_bytes()
            verify(data, mod.algorithm, mod.hash, mod.filename)
            jar_nodes = inspect_jar(data, mod.filename)
            first = jar_nodes[0]
            if first["environment"] == "client":
                raise BuildError(f"Selected server mod declares client-only Fabric environment: {mod.filename}")
            if first["id"] in roots:
                raise BuildError(f"Duplicate top-level Fabric mod id: {first['id']}")
            roots.add(first["id"])
            (destination / mod.filename).write_bytes(data)
            found.append({**mod.public(), "fabricId": first["id"], "fabricVersion": first["version"]})
            nodes.extend(jar_nodes)
        except BuildError as exc:
            invalid.append({**mod.public(), "error": str(exc)})
        except OSError:
            invalid.append({**mod.public(), "error": "Cannot read or stage the expected local JAR."})
    return missing, invalid, nodes, found


def write_server_definition(plan, root, mods):
    """Emit only missing server mod metadata, never the live Pages definition."""
    lines = ['hash-format = "sha256"', ""]
    for mod in mods:
        path = root / mod.path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(mod.raw)
        lines += ["[[files]]", "file = " + json.dumps(mod.path),
                  "hash = " + json.dumps(digest(mod.raw, "sha256")), "metafile = true", ""]
    index = ("\n".join(lines) + "\n").encode()
    (root / "index.toml").write_bytes(index)
    pack = ('name = "A Cozy Adventure - isolated server downloads"\npack-format = "packwiz:1.1.0"\n'
            '[index]\nfile = "index.toml"\nhash-format = "sha256"\nhash = ' + json.dumps(digest(index, "sha256")) +
            '\n[versions]\nminecraft = "26.3"\nfabric = "0.19.5"\n')
    (root / "pack.toml").write_text(pack, encoding="utf-8")


def run_installer(plan, missing, workspace, java):
    definition, installed = workspace / "definition", workspace / "installed"
    definition.mkdir()
    installed.mkdir()
    requested = {m["filename"] for m in missing}
    write_server_definition(plan, definition, [m for m in plan.mods if m.filename in requested])
    tool = workspace / "packwiz-installer.jar"
    try:
        request = Request(INSTALLER_URL, headers={"User-Agent": "A-Cozy-Adventure-serverpack-builder/1.0"})
        with urlopen(request, timeout=60) as response:
            data = response.read(16 * 1024 * 1024 + 1)
        verify(data, "sha256", INSTALLER_SHA256, "official packwiz-installer v0.5.14")
        tool.write_bytes(data)
        # The official installer supports file URIs, so no HTTP listener is needed.
        # Invoke its Main entry point without the bootstrapper's automatic updates.
        command = [java, "-Djava.awt.headless=true", "-cp", str(tool),
                   "link.infra.packwiz.installer.Main", "-g", "-s", "server",
                   "--pack-folder", str(installed), "--multimc-folder", str(workspace / "launcher"),
                   (definition / "pack.toml").as_uri()]
        with (workspace / "installer.log").open("wb") as log:
            result = subprocess.run(command, cwd=installed, stdin=subprocess.DEVNULL,
                                    stdout=log, stderr=subprocess.STDOUT, timeout=600)
        issue = None if result.returncode == 0 else "Official Packwiz installer failed or requires manual downloads; see the missing-file list and original project sources."
        return installed / "mods", issue
    except subprocess.TimeoutExpired:
        return installed / "mods", "Official Packwiz installer timed out; restricted files may require a manual download."
    except (OSError, BuildError):
        return installed / "mods", "Official Packwiz installer could not be verified or started. Check Java, network access and the pinned official release."


def report_text(report):
    lines = ["A Cozy Adventure - Serverpack Build Report", f"Status: {report['status']}",
             f"Selected server mods: {report.get('selectedModCount', 0)}",
             f"Verified JARs: {report.get('verifiedModCount', 0)}",
             f"Included config files: {report.get('configCount', 0)}",
             "Archive written: " + str(report.get("archiveWritten", False)), ""]
    if report.get("previousArchivePreserved"):
        if report["status"] == "planned":
            message = "An existing archive was left unchanged by this dry run. This run did not create a new archive."
        elif report["status"] == "failed":
            message = "An existing archive was preserved. It is NOT the result of this failed build."
        else:
            message = "An existing archive was left unchanged."
        lines += [message, ""]
    for title, key in [("Errors", "errors"), ("Warnings", "warnings")]:
        if report.get(key):
            lines += [title + ":", *["- " + e for e in report[key]], ""]
    for title, key in [("Missing JARs", "missing"), ("Invalid JARs", "invalid")]:
        if report.get(key):
            lines.append(title + ":")
            for mod in report[key]:
                lines += [f"- {mod['name']} | {mod['filename']}",
                          f"  {mod['hashFormat']}: {mod['hash']}", f"  Source: {mod['originalSource']}"]
                if mod.get("error"):
                    lines.append("  " + mod["error"])
            lines.append("")
    lines += ["Open configuration questions:"]
    for question in report.get("configurationQuestions", []):
        lines.append(f"- {question['id']}: {question['detail']}")
    lines += ["", "Phase B Dedicated-Server runtime compatibility has not been tested."]
    return "\n".join(lines) + "\n"


def atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".serverpack-", suffix=".tmp", delete=False) as handle:
            temp = Path(handle.name)
            handle.write(data)
        temp.replace(path)
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)


def write_archive(output, entries):
    """Replace the archive only after all entries pass ZIP integrity checks."""
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=output.parent, prefix=".serverpack-", suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_STORED) as archive:
            for name in sorted(entries):
                safe_path(name)
                info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                value = entries[name]
                if isinstance(value, Path):
                    with value.open("rb") as source, archive.open(info, "w", force_zip64=True) as target:
                        shutil.copyfileobj(source, target)
                else:
                    archive.writestr(info, value)
        with zipfile.ZipFile(temporary) as archive:
            if archive.testzip() is not None:
                raise BuildError("ZIP integrity validation failed.")
        temporary.replace(output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def validate_output(root, output):
    if output.suffix.lower() != ".zip" or output.is_symlink():
        raise BuildError("--output must name a regular ZIP file.")
    resolved = output.resolve()
    if resolved.is_relative_to(root.resolve()):
        relative = resolved.relative_to(root.resolve())
        if len(relative.parts) < 2 or relative.parts[0] not in ("build", "dist"):
            raise BuildError("Repository outputs must be inside build/ or dist/ to protect source files.")
    for path in [output, output.with_suffix(".report.json"), output.with_suffix(".report.txt")]:
        if path.is_symlink() or path.is_dir():
            raise BuildError("Output targets must not be symlinks or directories.")


def build(root=ROOT, *, source_mods=None, output=None, dry_run=False, download=False, java="java"):
    root = Path(root).resolve()
    output = Path(output) if output is not None else root / "dist/A-Cozy-Adventure-Server.zip"
    output = output.absolute()
    validate_output(root, output)
    report = {"schemaVersion": 1, "status": "failed", "archiveWritten": False,
              "previousArchivePreserved": output.exists(), "errors": [], "warnings": [],
              "missing": [], "invalid": [], "configurationQuestions": []}
    try:
        plan = load_plan(root)
        if plan.source["commit"] is None:
            raise BuildError("A source Git commit is required; run the builder in the local Git checkout.")
        report.update(source=plan.source, selectedModCount=len(plan.mods), excludedModCount=len(plan.excluded),
                      configCount=len(plan.configs), configurationQuestions=plan.questions)
        with tempfile.TemporaryDirectory(prefix="cozy-serverpack-") as temp:
            workspace = Path(temp)
            staged = workspace / "verified"
            staged.mkdir()
            source = Path(source_mods).resolve() if source_mods is not None else None
            if source is not None and not source.is_dir():
                raise BuildError("--source-mods must name an existing directory containing the expected JAR filenames.")
            missing, invalid, nodes, found = collect_jars(plan.mods, source, staged)
            if download and not dry_run and missing and not invalid:
                retrieved, issue = run_installer(plan, missing, workspace, java)
                requested = {m["filename"] for m in missing}
                missing, invalid, extra_nodes, extra_found = collect_jars([m for m in plan.mods if m.filename in requested], retrieved, staged)
                nodes.extend(extra_nodes)
                found.extend(extra_found)
                if issue:
                    report["errors"].append(issue)
            report.update(missing=missing, invalid=invalid, verifiedModCount=len(found))
            if invalid:
                report["errors"].append("Invalid JARs; no archive was created.")
            if missing and not dry_run:
                report["errors"].append("Missing required JARs. Supply exact originals with --source-mods or explicitly try --download.")
            if len(found) == len(plan.mods):
                dependencies = validate_dependencies(nodes)
                report["dependencies"] = dependencies
                report["errors"].extend(dependencies["errors"])
                report["warnings"].extend(dependencies["warnings"])
            else:
                report["dependencies"] = {"status": "pending", "scope": "Complete original JAR inventory required."}
            if report["errors"]:
                pass
            elif dry_run:
                report["status"] = "planned"
                report["readyForArchive"] = not missing
            else:
                # Recheck the input snapshot before making any artifact visible.
                for path, raw in plan.inputs.items():
                    current = Path(__file__).read_bytes() if path == "scripts/build_serverpack.py" else contained_file(root, path).read_bytes()
                    if current != raw:
                        raise BuildError("Source inputs changed during the build; retry from a stable checkout.")
                report.update(status="built", archiveWritten=True, previousArchivePreserved=False)
                manifest = {"schemaVersion": 1, "pack": {"name": "A Cozy Adventure",
                            "version": read_toml(plan.inputs["pack.toml"], "pack.toml").get("version"), **TARGET, "java": "25"},
                            "source": plan.source, "mods": sorted(found, key=lambda m: m["packwizFile"]),
                            "excludedMods": [m.public() for m in plan.excluded],
                            "configs": [{"path": p, "sha256": digest(b, "sha256")} for p, b in plan.configs.items()],
                            "excludedConfigs": sorted(plan.excluded_configs, key=lambda c: c["path"]),
                            "configurationQuestions": plan.questions, "dependencies": report["dependencies"]}
                entries = {"mods/" + m.filename: staged / m.filename for m in plan.mods}
                entries.update(plan.configs)
                entries.update({"README-SERVER.md": plan.inputs[SERVER_README], "build-manifest.json": json_bytes(manifest),
                                "build-report.json": json_bytes(report), "build-report.txt": report_text(report).encode("utf-8")})
                write_archive(output, entries)
    except (BuildError, OSError, ValueError, TypeError, KeyError) as exc:
        report.update(status="failed", archiveWritten=False, previousArchivePreserved=output.exists())
        report["errors"].append(str(exc) if isinstance(exc, BuildError) else "Invalid input or filesystem failure; check metadata and output permissions.")
    if not dry_run:
        atomic_write(output.with_suffix(".report.json"), json_bytes(report))
        atomic_write(output.with_suffix(".report.txt"), report_text(report).encode("utf-8"))
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Validate and report without downloads or output files; missing JARs remain pending.")
    parser.add_argument("--source-mods", type=Path, help="Directory containing exact original mod JARs; only expected filenames are read.")
    parser.add_argument("--output", type=Path, default=ROOT / "dist/A-Cozy-Adventure-Server.zip", help="ZIP path (default: dist/A-Cozy-Adventure-Server.zip).")
    parser.add_argument("--download", action="store_true", help="Explicitly use the pinned official Packwiz installer to fetch missing originals.")
    parser.add_argument("--java", default="java", help="Java executable for the optional Packwiz installer.")
    args = parser.parse_args(argv)
    try:
        report = build(source_mods=args.source_mods, output=args.output, dry_run=args.dry_run, download=args.download, java=args.java)
        print(report_text(report))
        if report["status"] == "built":
            print(f"Verified server ZIP created ({report['verifiedModCount']} mods).")
        return 1 if report["status"] == "failed" else 0
    except (BuildError, OSError):
        print("Build failed: invalid or unwritable output location. No successful build is reported.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
