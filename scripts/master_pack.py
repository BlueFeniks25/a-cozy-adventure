#!/usr/bin/env python3
"""Offline, read-only master inspection and explicit local pack preparation (Python 3.11+).

No launcher/mod code is executed. Nothing downloads, uploads or publishes files.
Only approve writes the checked-in lock/defaults; scan and prepare write new build/dist
directories. The Minecraft source is always read-only.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import tomllib
from urllib.parse import urlsplit
import zipfile

# Reuse the existing stateless Fabric version-range parser, never its Packwiz
# planner, downloader, builder or configuration selection.
from build_serverpack import BuildError as VersionError, matches_version

ROOT = Path(__file__).resolve().parents[1]
LOCK = "docs/automodpack/pack.lock.json"
BASE = "docs/automodpack"
MAX_JAR = 512 * 1024 * 1024
SIDES = {"client", "server", "both"}
BLOCKED_IDS = {"colorlight", "color_light", "color-light"}
ID = re.compile(r"[a-z][a-z0-9_-]{1,63}\Z")
HASH = re.compile(r"[a-f0-9]{64}\Z")
GROUP = re.compile(r"[a-z][a-z0-9-]{0,63}\Z")
# No personal client profiles, connection settings, accounts, maps or runtime caches.
DENIED_PARTS = {"saves", "screenshots", "logs", "cache", "caches", "downloads",
                "credentials", "automodpack", "xaero", "server_profiles", "profiles",
                "voicechat", "inventoryprofilesnext", "spark", "chunky"}
DENIED_NAMES = {"options.txt", "servers.dat", "usercache.json", "ribbits.json",
                "iris.properties", "sodium-options.json", "sodium-fingerprint.json",
                "tag_cache.json", "loot_fallback_report.json", "auto-host.json",
                "resource-pack.json", "security.cfg", "remote_texture.cfg", "storage.cfg"}


class PackError(Exception):
    """A validation failure that never includes file contents or credentials."""


def sha(data):
    return hashlib.sha256(data).hexdigest()


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def no_links(path):
    """Reject symlinks AND Windows junctions/reparse points, including ancestors."""
    for p in (path, *path.parents):
        if p.is_symlink() or (p.exists() and getattr(p.lstat(), "st_file_attributes", 0) & 0x400):
            raise PackError("Symlinks/Junctions sind als Ein- oder Ausgabe nicht erlaubt.")


def relative(value):
    if not isinstance(value, str) or not value or "\\" in value:
        raise PackError("Ungültiger relativer Dateipfad.")
    for part in value.split("/"):
        if (part in {"", ".", ".."} or part.endswith((".", " "))
                or re.search(r'[\x00-\x1f\x7f<>:"|?*]', part)
                or part.split(".")[0].upper() in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}):
            raise PackError("Unsicherer relativer Dateipfad.")
    return value


def read_file(base, name):
    p = Path(base) / relative(name)
    no_links(p)
    if not p.is_file() or not p.resolve().is_relative_to(Path(base).resolve()):
        raise PackError(f"Datei fehlt: {name}")
    return p.read_bytes()


def unique_pairs(pairs):
    result = {}
    for k, v in pairs:
        if k in result:
            raise PackError("Doppelter JSON-Schlüssel.")
        result[k] = v
    return result


def read_json(data, *, fabric=False):
    try:
        return json.loads(data.decode("utf-8-sig"), strict=not fabric, object_pairs_hook=unique_pairs)
    except (UnicodeError, ValueError):
        raise PackError("Ungültige JSON-Datei.") from None


def check_hash(data, record, label):
    if not HASH.fullmatch(str(record.get("sha256", ""))) or sha(data) != record["sha256"]:
        raise PackError(f"SHA-256 stimmt nicht: {label}")
    if type(record.get("size")) is not int or len(data) != record["size"]:
        raise PackError(f"Dateigröße stimmt nicht: {label}")


def blocked(value):
    return "colorlight" in re.sub(r"[^a-z0-9]", "", value.lower())


def metadata(data, label, *, depth=0, budget=None):
    budget = [MAX_JAR] if budget is None else budget
    budget[0] -= len(data)
    if depth > 8 or budget[0] < 0:
        raise PackError(f"JAR-Limit überschritten: {label}")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            if len(z.namelist()) != len(set(z.namelist())):
                raise PackError(f"Doppelte JAR-Einträge: {label}")
            if z.getinfo("fabric.mod.json").file_size > 2 * 1024 * 1024:
                raise PackError(f"Zu große Mod-Metadaten: {label}")
            d = read_json(z.read("fabric.mod.json"), fabric=True)
            if not isinstance(d, dict) or not ID.fullmatch(str(d.get("id", ""))):
                raise PackError(f"Ungültige Fabric-ID: {label}")
            if blocked(d["id"]) or blocked(label):
                raise PackError("ColorLight bleibt ausdrücklich ausgeschlossen.")
            version = d.get("version")
            env = d.get("environment", "*")
            if not isinstance(version, str) or not version or env not in {"*", "client", "server"}:
                raise PackError(f"Ungültige Fabric-Version/Umgebung: {label}")
            for field in ("depends", "breaks", "conflicts"):
                requirements = d.get(field, {})
                if not isinstance(requirements, dict):
                    raise PackError(f"Ungültige Abhängigkeiten: {label}")
                for key, constraint in requirements.items():
                    if not ID.fullmatch(key):
                        raise PackError(f"Ungültige Abhängigkeits-ID: {label}")
                    try:
                        matches_version("0", constraint)
                    except VersionError:
                        raise PackError(f"Ungültiger Versionsbereich: {label}") from None
            if not isinstance(d.get("provides", []), list) or not all(ID.fullmatch(str(v)) for v in d.get("provides", [])):
                raise PackError(f"Ungültige Fabric-Aliase: {label}")
            nodes = [{"id": d["id"], "version": version, "environment": env,
                      "depends": d.get("depends", {}), "provides": d.get("provides", []),
                      "breaks": d.get("breaks", {}), "conflicts": d.get("conflicts", {})}]
            for nested in d.get("jars", []):
                path = relative(nested["file"])
                if z.getinfo(path).file_size > budget[0]:
                    raise PackError(f"Zu große eingebettete JAR: {label}")
                nodes.extend(metadata(z.read(path), label + "!" + path, depth=depth + 1, budget=budget))
            return nodes
    except (zipfile.BadZipFile, KeyError, TypeError, RuntimeError, NotImplementedError):
        raise PackError(f"Ungültige Fabric-JAR: {label}") from None


def master_folder(value, pack):
    if value is None:
        value = Path(os.environ.get("APPDATA", str(Path.home() / "AppData/Roaming"))) / "PrismLauncher/instances/A Cozy Adventure – Schutztest"
    p = Path(value).absolute()
    no_links(p)
    if (p / "mmc-pack.json").is_file():
        choices = [p / n for n in ("minecraft", ".minecraft") if (p / n).is_dir()]
        if len(choices) != 1:
            raise PackError("Minecraft-Ordner der Instanz ist nicht eindeutig.")
        p = choices[0]
    no_links(p)
    mmc = read_json(read_file(p.parent, "mmc-pack.json"))
    versions = {c["uid"]: c.get("version") for c in mmc["components"]}
    if versions.get("net.minecraft") != pack["minecraft"] or versions.get("net.fabricmc.fabric-loader") != pack["fabric"]:
        raise PackError("Minecraft/Fabric der Master-Instanz passen nicht zum Manifest.")
    if not (p / "mods").is_dir():
        raise PackError("Modordner der Master-Instanz fehlt.")
    no_links(p / "mods")
    return p


def source_valid(source):
    if not isinstance(source, dict) or source.get("provider") not in {"modrinth", "curseforge"}:
        return False
    hosts = {"modrinth": {"modrinth.com"}, "curseforge": {"www.curseforge.com", "curseforge.com"}}
    try:
        u = urlsplit(source.get("url", ""))
        return (u.scheme == "https" and u.hostname in hosts[source["provider"]]
                and not u.username and not u.password and not u.query and not u.fragment
                and bool(source.get("projectId")) and bool(source.get("versionId")))
    except ValueError:
        return False


def source_from_packwiz(d, data):
    """Use local installer metadata only when its pinned upstream hash matches."""
    h = d.get("download", {})
    alg = h.get("hash-format")
    if alg not in {"sha1", "sha256", "sha512"} or hashlib.new(alg, data).hexdigest() != h.get("hash"):
        return None
    update = d.get("update", {})
    if "modrinth" in update:
        v = update["modrinth"]
        source = {"provider": "modrinth", "projectId": v.get("mod-id"), "versionId": v.get("version"),
                  "url": f"https://modrinth.com/project/{v.get('mod-id')}/version/{v.get('version')}"}
    elif "curseforge" in update:
        v = update["curseforge"]
        source = {"provider": "curseforge", "projectId": v.get("project-id"), "versionId": v.get("file-id"),
                  "url": f"https://www.curseforge.com/projects/{v.get('project-id')}/files/{v.get('file-id')}"}
    else:
        u = urlsplit(h.get("url", ""))
        match = re.fullmatch(r"/data/([A-Za-z0-9]+)/versions/([A-Za-z0-9]+)/[^/]+", u.path)
        if u.scheme != "https" or u.hostname != "cdn.modrinth.com" or u.query or u.fragment or not match:
            return None
        source = {"provider": "modrinth", "projectId": match[1], "versionId": match[2],
                  "url": f"https://modrinth.com/project/{match[1]}/version/{match[2]}"}
    source["hashes"] = {alg: h["hash"]}
    return source if source_valid(source) else None


def upstream_hashes(data, source):
    if not source_valid(source):
        raise PackError("Quellenzuordnung fehlt oder ist ungültig.")
    hashes = source.get("hashes", {})
    if not hashes or any(a not in {"sha1", "sha256", "sha512"} or hashlib.new(a, data).hexdigest() != h for a, h in hashes.items()):
        raise PackError("Datei stimmt nicht mit den freigegebenen Quellenhashes überein.")


def local_sources(mc, data_by_name):
    result = {}
    directory = mc / "mods/.index"
    if not directory.exists():
        return result
    no_links(directory)
    for p in sorted(directory.glob("*.pw.toml")):
        d = tomllib.loads(read_file(directory, p.name).decode("utf-8"))
        name = d.get("filename")
        if name in data_by_name:
            source = source_from_packwiz(d, data_by_name[name])
            if source:
                result[name] = source
    return result


def safe_config(path):
    relative(path)
    parts = path.lower().split("/")
    return (parts[0] == "config" and len(parts) > 1 and not any(p.startswith(".") or p in DENIED_PARTS for p in parts[1:])
            and parts[-1] not in DENIED_NAMES and not blocked(path)
            and not any(x in parts[-1] for x in ("password", "secret", "token", "credential", "fingerprint", "username", "bookmark", "waypoint"))
            and Path(path).suffix.lower() in {".json", ".json5", ".toml", ".properties", ".cfg", ".txt", ".config"})


def config_content(data, path):
    """Reject credential-bearing settings without ever printing their values."""
    try:
        text = data.decode("utf-8-sig")
    except UnicodeError:
        raise PackError(f"Keine Textkonfiguration: {path}") from None
    if "-----BEGIN " in text or re.search(r"(?i)(?:https?://)[^\s/]+:[^\s/]+@", text):
        raise PackError(f"Mögliche Zugangsdaten in Konfiguration: {path}")
    for line in text.splitlines():
        if line.lstrip().startswith(("#", "//", "*")):
            continue
        pattern = r'''(?i)["']?([\w.-]*(?:password|secret|token|api.?key|username|proxyhost)[\w.-]*)["']?\s*[:=]\s*("[^"\r\n]*"|'[^'\r\n]*'|[^,\r\n}]+)'''
        for match in re.finditer(pattern, line):
            value = match[2].strip().rstrip(",").strip().strip('"\'')
            if value not in {"", "null", "false"}:
                raise PackError(f"Mögliche Zugangsdaten in Konfiguration: {path}")


def validate_lock(lock, *, approved=True):
    if not isinstance(lock, dict):
        raise PackError("Manifest muss ein JSON-Objekt sein.")
    if lock.get("schemaVersion") != 1 or lock.get("status") != ("approved" if approved else "candidate"):
        raise PackError("Manifest ist nicht im erwarteten Freigabestatus.")
    pack = lock.get("pack", {})
    if not isinstance(pack, dict) or not all(isinstance(pack.get(k), str) and pack[k] for k in ("name", "minecraft", "fabric", "java", "automodpack")):
        raise PackError("Plattformangaben im Manifest fehlen.")
    groups = lock.get("groups", {})
    if not isinstance(groups, dict) or not all(isinstance(g, dict) for g in groups.values()):
        raise PackError("Ungültige Gruppenliste.")
    if not all(isinstance(lock.get(field), list) and all(isinstance(r, dict) for r in lock[field]) for field in ("mods", "configs", "resourcepacks")):
        raise PackError("Manifest benötigt Mod-, Konfigurations- und Ressourcenpaketlisten.")
    if "main" not in groups or groups["main"].get("selection") != "REQUIRED":
        raise PackError("Pflichtgruppe main fehlt.")
    for gid, group in groups.items():
        if not GROUP.fullmatch(gid) or group.get("selection") not in {"REQUIRED", "RECOMMENDED", "OPTIONAL"}:
            raise PackError("Ungültige AutoModpack-Gruppe.")
        if not isinstance(group.get("displayName"), str):
            raise PackError("Gruppenname fehlt.")
        if not isinstance(group.get("requires", []), list) or not all(isinstance(dep, str) for dep in group.get("requires", [])):
            raise PackError("Ungültige Gruppenabhängigkeiten.")
        if any(dep not in groups or dep == gid for dep in group.get("requires", [])):
            raise PackError("Ungültige Gruppenabhängigkeit.")
    def visit(gid, active):
        if gid in active:
            raise PackError("Zyklische Gruppenabhängigkeit.")
        for dep in groups[gid].get("requires", []):
            visit(dep, active | {gid})
    for gid in groups:
        visit(gid, set())
    seen = set()
    names = set()
    bootstrap = []
    for mod in lock.get("mods", []):
        mid, name = mod.get("id"), mod.get("filename")
        relative(name)
        if not ID.fullmatch(str(mid)) or blocked(mid) or blocked(name):
            raise PackError("Ungültige oder gesperrte Mod-ID.")
        if "/" in name or not name.endswith(".jar") or name.lower() in names or mid in seen:
            raise PackError("Doppelte Mod-ID/Datei oder ungültiger JAR-Name.")
        seen.add(mid)
        names.add(name.lower())
        if not isinstance(mod.get("version"), str) or not HASH.fullmatch(str(mod.get("sha256", ""))) or type(mod.get("size")) is not int:
            raise PackError(f"Version/Hash/Größe fehlen: {mid}")
        if mod.get("side") not in SIDES or not mod.get("sideReason"):
            raise PackError(f"Modzuordnung muss geprüft werden: {mid}")
        meta = mod.get("metadata")
        if not isinstance(meta, dict) or not isinstance(mod.get("nestedMods"), list):
            raise PackError(f"Fabric-Metadaten fehlen: {mid}")
        if meta.get("id") != mid or meta.get("version") != mod["version"]:
            raise PackError(f"Fabric-Identität widerspricht dem Manifest: {mid}")
        for node in [meta, *mod["nestedMods"]]:
            if (not isinstance(node, dict) or not ID.fullmatch(str(node.get("id", "")))
                    or not isinstance(node.get("version"), str) or node.get("environment") not in {"*", "client", "server"}
                    or not isinstance(node.get("depends"), dict) or not isinstance(node.get("provides"), list)):
                raise PackError(f"Ungültige Fabric-Metadaten: {mid}")
        env = meta.get("environment")
        if env not in {"*", "client", "server"} or (env == "client" and mod["side"] != "client") or (env == "server" and mod["side"] != "server"):
            raise PackError(f"Modzuordnung widerspricht Fabric-Metadaten: {mid}")
        if not source_valid(mod.get("source")):
            raise PackError(f"Geprüfte Quelle fehlt: {mid}")
        if mod.get("role") == "bootstrap":
            bootstrap.append(mod)
        elif mod.get("role") != "mod":
            raise PackError(f"Unbekannte Modrolle: {mid}")
    if len(bootstrap) != 1 or bootstrap[0]["id"] != "automodpack" or bootstrap[0]["side"] != "both" or bootstrap[0]["version"] != pack["automodpack"]:
        raise PackError("Genau eine passende AutoModpack-Bootstrap-JAR ist erforderlich.")
    paths = set()
    for record in lock.get("configs", []):
        path = record.get("path")
        if not safe_config(path) or path.lower() in paths:
            raise PackError(f"Konfiguration ist persönlich, doppelt oder nicht erlaubt: {path}")
        paths.add(path.lower())
        snapshot = record.get("snapshot", "")
        relative(snapshot)
        if snapshot != f"defaults/{record.get('sha256')}.txt" or not HASH.fullmatch(str(record.get("sha256", ""))):
            raise PackError("Ungültige Konfigurations-Snapshotreferenz.")
        if record.get("side") not in SIDES or type(record.get("editable")) is not bool or type(record.get("size")) is not int:
            raise PackError("Konfigurationszuordnung fehlt.")
    for record in lock.get("resourcepacks", []):
        name = relative(record.get("filename"))
        if "/" in name or not name.endswith(".zip") or name.lower() in paths or record.get("group") not in groups or record["group"] == "main":
            raise PackError("Ressourcenpaket muss einer eigenen gültigen Gruppe zugeordnet sein.")
        paths.add(name.lower())
        if not source_valid(record.get("source")) or not HASH.fullmatch(str(record.get("sha256", ""))) or type(record.get("size")) is not int:
            raise PackError("Ressourcenpaketquelle oder Hash fehlt.")
    if not lock.get("mods"):
        raise PackError("Modliste ist leer.")
    validate_dependencies(lock)


def validate_dependencies(lock):
    """Check required providers/ranges on each side; this is not Fabric's solver."""
    warnings = []
    builtins = {"minecraft": lock["pack"]["minecraft"], "fabricloader": lock["pack"]["fabric"],
                "java": lock["pack"]["java"], "mixinextras": "0.5.5"}
    for side in ("client", "server"):
        nodes = []
        disabled = set()
        for mod in lock["mods"]:
            if mod.get("side") in {side, "both"}:
                for node in [mod["metadata"], *mod["nestedMods"]]:
                    if node["environment"] in {"*", side}:
                        nodes.append(node)
                    else:
                        disabled.update([node["id"], *node.get("provides", [])])
        providers = {key: [v] for key, v in builtins.items()}
        for node in nodes:
            for key in [node["id"], *node.get("provides", [])]:
                providers.setdefault(key, []).append(node["version"])
        for node in nodes:
            for key, constraint in node.get("depends", {}).items():
                if key not in providers and key in disabled:
                    warnings.append(f"Im Fabric-Server-Test prüfen ({side}): {node['id']} -> {key}; eingebettetes Modul auf dieser Seite deaktiviert.")
                    continue
                try:
                    found = any(matches_version(v, constraint) for v in providers.get(key, []))
                except VersionError:
                    raise PackError(f"Versionsbereich muss manuell geprüft werden: {node['id']} / {key}") from None
                if not found:
                    raise PackError(f"Fehlende/unpassende Abhängigkeit ({side}): {node['id']} benötigt {key} {constraint}")
    return sorted(set(warnings))


def load_lock(root):
    lock = read_json(read_file(root, LOCK))
    validate_lock(lock)
    return lock


def inventory(mc):
    records, contents, ids, names = [], {}, set(), set()
    for p in sorted((mc / "mods").iterdir(), key=lambda p: p.name.lower()):
        if p.name == ".index":
            continue
        if p.is_dir() or p.suffix.lower() != ".jar":
            raise PackError(f"Ungeprüfte Datei im Modordner (auch deaktivierte Mods prüfen): {p.name}")
        relative(p.name)
        if p.stat().st_size > MAX_JAR:
            raise PackError(f"JAR zu groß: {p.name}")
        data = read_file(mc, "mods/" + p.name)
        nodes = metadata(data, p.name)
        top = nodes[0]
        if top["id"] in ids or p.name.lower() in names:
            raise PackError(f"Doppelte Mod-ID/Datei: {top['id']}")
        ids.add(top["id"])
        names.add(p.name.lower())
        record = {"id": top["id"], "version": top["version"], "filename": p.name,
                  "sha256": sha(data), "size": len(data), "metadata": top,
                  "nestedMods": nodes[1:]}
        records.append(record)
        contents[p.name] = data
    # Fabric may materialize the selected universal AutoModpack implementation.
    # Ignore only a byte-identical implementation referenced by the outer JAR;
    # an arbitrary file with this name remains an unknown mod and blocks prepare.
    generated = next((m for m in records if m["filename"] == "automodpack-generated.jar"), None)
    outer = next((m for m in records if m["id"] == "automodpack"), None)
    if generated and outer and generated["id"] == "automodpack_mod":
        with zipfile.ZipFile(io.BytesIO(contents[outer["filename"]])) as z:
            if "impl/manifest.json" in z.namelist() and z.getinfo("impl/manifest.json").file_size <= 1024 * 1024:
                implementations = read_json(z.read("impl/manifest.json")).get("impls", [])
                mmc = read_json(read_file(mc.parent, "mmc-pack.json"))
                game = next(c["version"] for c in mmc["components"] if c["uid"] == "net.minecraft")
                data = contents[generated["filename"]]
                if generated["version"] == outer["version"] and any(
                    impl.get("id") == game + "-fabric" and impl.get("length") == len(data)
                    and impl.get("sha1") == hashlib.sha1(data).hexdigest() for impl in implementations
                ):
                    records.remove(generated)
                    del contents[generated["filename"]]
    return sorted(records, key=lambda m: m["id"]), contents


def scan(root, master=None):
    lock = load_lock(root)
    mc = master_folder(master, lock["pack"])
    actual, contents = inventory(mc)
    local = local_sources(mc, contents)
    previous = {m["id"]: m for m in lock["mods"]}
    candidate = copy.deepcopy(lock)
    candidate["status"] = "candidate"
    candidate["baseLockSha256"] = sha(read_file(root, LOCK))
    candidate["mods"] = []
    changes = {"new": [], "updated": [], "renamed": [], "removed": [], "configs": [], "resourcepacks": []}
    blockers = []
    for record in actual:
        old = previous.pop(record["id"], None)
        if old:
            record.update({k: copy.deepcopy(old[k]) for k in ("name", "side", "sideReason", "role")})
            if old["sha256"] == record["sha256"]:
                record["source"] = copy.deepcopy(old["source"])
                if old["filename"] != record["filename"]:
                    changes["renamed"].append({"id": record["id"], "old": old["filename"], "new": record["filename"]})
            else:
                record["source"] = local.get(record["filename"])
                changes["updated"].append({"id": record["id"], "oldVersion": old["version"], "version": record["version"], "oldSha256": old["sha256"], "sha256": record["sha256"]})
        else:
            record.update(name=record["id"], side=None, sideReason="", role="mod", source=local.get(record["filename"]))
            changes["new"].append({"id": record["id"], "version": record["version"], "sha256": record["sha256"]})
            blockers.append(f"Neue Mod: {record['id']} — Seite und Quelle ausdrücklich prüfen.")
        if not source_valid(record.get("source")):
            blockers.append(f"Geprüfte Quelle fehlt: {record['id']} (alte Quellen werden bei Updates nicht übernommen).")
        if record.get("side") and record["metadata"]["environment"] in {"client", "server"} and record["side"] != record["metadata"]["environment"]:
            blockers.append(f"Geänderte Fabric-Umgebung erfordert neue Zuordnung: {record['id']}")
        if record["id"] == "automodpack" and record["version"] != candidate["pack"]["automodpack"]:
            blockers.append("AutoModpack-Version geändert; Plattformangabe im Kandidaten ausdrücklich prüfen.")
        candidate["mods"].append(record)
    changes["removed"] = [{"id": m["id"], "version": m["version"], "sha256": m["sha256"]} for m in previous.values()]
    try:
        validate_dependencies(candidate)
    except PackError as e:
        blockers.append(str(e))
    for record in candidate["configs"]:
        data = read_file(mc, record["path"])
        config_content(data, record["path"])
        if sha(data) != record["sha256"]:
            changes["configs"].append({"path": record["path"], "oldSha256": record["sha256"], "sha256": sha(data)})
            record.update(sha256=sha(data), size=len(data), snapshot=f"defaults/{sha(data)}.txt")
    for record in candidate["resourcepacks"]:
        data = read_file(mc, "resourcepacks/" + record["filename"])
        if sha(data) != record["sha256"]:
            changes["resourcepacks"].append({"filename": record["filename"], "oldSha256": record["sha256"], "sha256": sha(data)})
            record.update(sha256=sha(data), size=len(data), source=None)
            blockers.append(f"Neue Ressourcenpaketquelle prüfen: {record['filename']}")
    report = {"schemaVersion": 1, "lockSha256": candidate["baseLockSha256"], "modCount": len(actual),
              "changes": changes, "blockers": blockers, "changed": any(changes.values()),
              "scope": "Nur mods/*.jar und ausdrücklich freigegebene Konfigurationen/Ressourcenpakete; keine Veröffentlichung.",
              "dependencyWarnings": validate_dependencies(candidate) if not blockers else []}
    return report, candidate


def report_text(report):
    lines = ["A Cozy Adventure — lokaler Master-Abgleich", f"Geprüfte Mods: {report['modCount']}"]
    labels = {"new": "NEU", "updated": "AKTUALISIERT", "renamed": "UMBENANNT", "removed": "ENTFERNT", "configs": "KONFIGURATION", "resourcepacks": "RESSOURCENPAKET"}
    for key, label in labels.items():
        items = report["changes"][key]
        lines.append(f"{label}: {len(items)}")
        for item in items:
            name = item.get("id", item.get("path", item.get("filename")))
            detail = f" {item.get('oldVersion', '')} → {item['version']}" if key == "updated" else ""
            lines.append(f"  {name}{detail}")
    lines.extend("PRÜFEN: " + b for b in report["blockers"])
    lines.extend("LAUFZEITPRÜFUNG OFFEN: " + w for w in report.get("dependencyWarnings", []))
    lines.append("Keine Änderungen." if not report["changed"] else "Kandidat prüfen; anschließend ausdrücklich lokal freigeben.")
    return "\n".join(lines) + "\n"


def output_path(root, value, allowed, mc):
    p = Path(value).absolute()
    root = Path(root).resolve()
    no_links(p)
    p = p.resolve()
    if not any(p.is_relative_to(root / name) and p != root / name for name in allowed):
        raise PackError("Ausgabe muss ein neuer Unterordner unter build/ oder dist/ sein.")
    if p.is_relative_to(mc) or mc.is_relative_to(p) or p.exists():
        raise PackError("Ausgabe existiert bereits oder überschneidet sich mit der Master-Instanz.")
    return p


def new_directory(destination, callback):
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".cozy-prepare-", dir=destination.parent) as temporary:
        staged = Path(temporary) / "payload"
        staged.mkdir()
        callback(staged)
        if destination.exists():
            raise PackError("Ausgabe wurde inzwischen angelegt; nichts überschrieben.")
        staged.rename(destination)


def write_scan(root, master, output):
    report, candidate = scan(root, master)
    mc = master_folder(master, candidate["pack"])
    destination = output_path(root, output, ["build"], mc)
    def write(directory):
        (directory / "report.json").write_bytes(json_bytes(report))
        (directory / "report.txt").write_text(report_text(report), encoding="utf-8", newline="\n")
        (directory / "candidate.json").write_bytes(json_bytes(candidate))
    new_directory(destination, write)
    return report


def verify_selected(lock, mc):
    actual, contents = inventory(mc)
    by_id = {m["id"]: m for m in actual}
    if set(by_id) != {m["id"] for m in lock["mods"]}:
        raise PackError("Fehlende oder unbekannte Mods: erneut scan ausführen und Auswahl prüfen.")
    for mod in lock["mods"]:
        observed = by_id[mod["id"]]
        if any(observed[k] != mod[k] for k in ("filename", "version", "metadata", "nestedMods")):
            raise PackError(f"Fabric-Metadaten/Dateiname weichen vom Manifest ab: {mod['id']}")
        data = contents[mod["filename"]]
        check_hash(data, mod, mod["id"])
        upstream_hashes(data, mod["source"])
    for config in lock["configs"]:
        data = read_file(mc, config["path"])
        check_hash(data, config, config["path"])
        config_content(data, config["path"])
    for resource in lock["resourcepacks"]:
        data = read_file(mc, "resourcepacks/" + resource["filename"])
        check_hash(data, resource, resource["filename"])
        upstream_hashes(data, resource["source"])


def approve(root, master, candidate_path):
    root = Path(root).resolve()
    candidate_path = Path(candidate_path).absolute()
    no_links(candidate_path)
    candidate_path = candidate_path.resolve()
    if not candidate_path.is_relative_to(root / "build"):
        raise PackError("Freigabekandidat muss aus build/ stammen.")
    candidate = read_json(candidate_path.read_bytes())
    validate_lock(candidate, approved=False)
    if candidate.get("baseLockSha256") != sha(read_file(root, LOCK)):
        raise PackError("Veralteter Kandidat: freigegebenes Manifest hat sich geändert.")
    mc = master_folder(master, candidate["pack"])
    if root.is_relative_to(mc) or mc.is_relative_to(root / BASE):
        raise PackError("Repository und Master-Instanz müssen getrennt bleiben.")
    verify_selected(candidate, mc)
    snapshots = {}
    for config in candidate["configs"]:
        data = read_file(mc, config["path"])
        check_hash(data, config, config["path"])
        snapshots[config["snapshot"]] = data
    approved = copy.deepcopy(candidate)
    del approved["baseLockSha256"]
    approved["status"] = "approved"
    validate_lock(approved)
    for name, data in snapshots.items():
        destination = root / BASE / name
        no_links(destination)
        if destination.exists():
            if destination.read_bytes() != data:
                raise PackError("Bestehender Konfigurationssnapshot ist verändert.")
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open("xb") as f:
                f.write(data)
    target = root / LOCK
    no_links(target)
    if sha(target.read_bytes()) != candidate["baseLockSha256"]:
        raise PackError("Manifest wurde während der Prüfung verändert.")
    with tempfile.NamedTemporaryFile(dir=target.parent, prefix=".lock-", delete=False) as f:
        temporary = Path(f.name)
        f.write(json_bytes(approved))
    try:
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    return approved


def server_conf(lock):
    lines = ["# A Cozy Adventure — AutoModpack 5.0.0-rc.5; vorbereitet, noch nicht veröffentlicht.",
             "modpack-host: true", "generate-modpack-on-start: false", "require-modpack: true",
             "self-updater: false", "connection-mode: HOLEPUNCH", "bind-port: -1",
             "validate-secrets: true", "modpack {", "  name: " + json.dumps(lock["pack"]["name"]), "  General {"]
    for gid, group in sorted(lock["groups"].items(), key=lambda x: (x[0] != "main", x[0])):
        editable = sorted(c["path"] for c in lock["configs"] if c["side"] != "server" and c["editable"] and gid == "main")
        lines.extend([f"    {gid} {{", "      display-name: " + json.dumps(group["displayName"], ensure_ascii=False),
                      "      selection: " + group["selection"], "      from-server: []",
                      "      exclude: [\"**/.*\", \"**/.*/**\", \"**/*.{tmp,disabled,bak}\"]",
                      "      auto-exclude-server-side-mods: METADATA",
                      "      editable: " + json.dumps(editable, ensure_ascii=False),
                      "      requires: " + json.dumps(group.get("requires", [])), "    }"])
    return ("\n".join(lines + ["  }", "}", ""])).encode("utf-8")


def prepare(root, master, output):
    root = Path(root).resolve()
    lock = load_lock(root)
    lock_raw = read_file(root, LOCK)
    mc = master_folder(master, lock["pack"])
    destination = output_path(root, output, ["build", "dist"], mc)
    verify_selected(lock, mc)  # All checks precede creation of any output directory.
    inputs = {}
    def add(target, base, path, record):
        relative(target)
        if target.lower() in {p.lower() for p in inputs}:
            raise PackError("Doppelte Ausgabedatei.")
        inputs[target] = (base, path, record)
    for mod in lock["mods"]:
        path = "mods/" + mod["filename"]
        if mod["side"] != "client":
            add("server/" + path, mc, path, mod)
        if mod["role"] == "bootstrap":
            add("bootstrap-client/" + path, mc, path, mod)
        elif mod["side"] != "server":
            add("server/automodpack/host-modpack/main/" + path, mc, path, mod)
    for config in lock["configs"]:
        data = read_file(root / BASE, config["snapshot"])
        check_hash(data, config, config["path"])
        config_content(data, config["path"])
        if config["side"] != "client":
            add("server/" + config["path"], root / BASE, config["snapshot"], config)
        if config["side"] != "server":
            add("server/automodpack/host-modpack/main/" + config["path"], root / BASE, config["snapshot"], config)
    for resource in lock["resourcepacks"]:
        path = "resourcepacks/" + resource["filename"]
        add("server/automodpack/host-modpack/" + resource["group"] + "/" + path, mc, path, resource)
    def write(directory):
        files = {}
        def put(name, data):
            target = directory / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            files[name] = {"sha256": sha(data), "size": len(data)}
        for target, (base, path, record) in sorted(inputs.items()):
            data = read_file(base, path)
            check_hash(data, record, path)  # Recheck at copy time; master may change.
            put(target, data)
        put("server/automodpack/server.conf", server_conf(lock))
        put("pack.lock.json", lock_raw)
        report = {"schemaVersion": 1, "lockSha256": sha(lock_raw), "status": "prepared-offline",
                  "dedicatedServerTest": "pending", "published": False, "uploaded": False,
                  "serverMods": sum(m["side"] != "client" for m in lock["mods"]),
                  "managedClientMods": sum(m["side"] != "server" and m["role"] != "bootstrap" for m in lock["mods"]),
                  "resourcepacks": len(lock["resourcepacks"]), "files": files.copy(),
                  "dependencyWarnings": validate_dependencies(lock)}
        put("build-report.json", json_bytes(report))
        put("SHA256SUMS.txt", ("\n".join(f"{v['sha256']}  {k}" for k, v in sorted(files.items())) + "\n").encode("utf-8"))
        if read_file(root, LOCK) != lock_raw:
            raise PackError("Manifest wurde während der Vorbereitung verändert.")
    new_directory(destination, write)
    return destination


def main(argv=None):
    parser = argparse.ArgumentParser(description="A Cozy Adventure: Master prüfen und lokal für AutoModpack vorbereiten (offline).")
    parser.add_argument("command", choices=["scan", "approve", "prepare"])
    parser.add_argument("--master", help="Prism-Instanz oder ihr Minecraft-Ordner; Standard: lokale Schutztest-Instanz")
    parser.add_argument("--output", help="Neuer Unterordner in build/ (scan) oder build/dist (prepare)")
    parser.add_argument("--candidate", help="Geprüfte candidate.json aus einem vorherigen scan")
    args = parser.parse_args(argv)
    try:
        if args.command == "scan":
            report = write_scan(ROOT, args.master, args.output) if args.output else scan(ROOT, args.master)[0]
            print(report_text(report), end="")
            return 2 if report["blockers"] else 1 if report["changed"] else 0
        if args.command == "approve":
            if not args.candidate:
                parser.error("approve benötigt --candidate")
            approved = approve(ROOT, args.master, args.candidate)
            print(f"Lokal freigegeben: {len(approved['mods'])} Mods. Kein Commit/Upload/Publish ausgeführt.")
        else:
            if not args.output:
                parser.error("prepare benötigt --output")
            print("Lokal vorbereitet: " + str(prepare(ROOT, args.master, args.output)))
        return 0
    except (PackError, OSError, ValueError, tomllib.TOMLDecodeError) as e:
        print("Abbruch: " + (str(e) if isinstance(e, PackError) else "Datei oder Metadaten nicht lesbar; Eingaben prüfen."), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
