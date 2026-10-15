#!/usr/bin/env python3
"""Read Packwiz metadata and write a static catalog. Python 3.11+, stdlib only.

Never downloads jars, resolves newer releases, or writes Packwiz files.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import time
import tomllib
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
USER_AGENT = "BlueFeniks25/a-cozy-adventure-catalog/1.0 (https://github.com/BlueFeniks25/a-cozy-adventure)"
MODRINTH = "https://api.modrinth.com/v2"
CATEGORIES = {
    "Abenteuer": "Erweitert das Erkunden und die Abenteuer in deiner Minecraft-Welt.",
    "Magie": "Ergänzt magische Spielmechaniken für dein Abenteuer.",
    "Bauen": "Erweitert die Möglichkeiten zum Bauen und Dekorieren.",
    "Welt": "Ergänzt die Landschaften und die Natur deiner Minecraft-Welt.",
    "Tiere": "Erweitert die Tierwelt oder die Interaktion mit Tieren.",
    "Küche & Garten": "Ergänzt Inhalte rund ums Kochen, Anbauen und Genießen.",
    "Komfort": "Erleichtert den Minecraft-Alltag mit zusätzlichen Komfortfunktionen.",
    "Atmosphäre": "Ergänzt die visuelle oder akustische Atmosphäre deiner Welt.",
    "Performance": "Optimiert technische Abläufe für ein flüssigeres Spielerlebnis.",
    "Bibliotheken": "Technische Grundlage, die Funktionen für andere Mods bereitstellt.",
    "Sonstiges": "Gehört zum Modpack. Eine genauere deutsche Beschreibung ist noch nicht verfügbar.",
}
TAG_CATEGORIES = {
    "adventure": "Abenteuer", "worldgen": "Welt", "world gen": "Welt",
    "biomes": "Welt", "dimensions": "Welt", "magic": "Magie",
    "decoration": "Bauen", "building": "Bauen", "mobs": "Tiere",
    "food": "Küche & Garten", "farming": "Küche & Garten",
    "optimization": "Performance", "performance": "Performance",
    "library": "Bibliotheken", "api and library": "Bibliotheken",
    "utility": "Komfort", "storage": "Komfort", "equipment": "Abenteuer",
    "game mechanics": "Komfort", "cosmetic": "Atmosphäre",
    "structures": "Abenteuer", "storage and utility": "Komfort",
}
NAME_RULES = [
    (r"\b(api|lib|library|core|kotlin|lithostitched|architectury|balm|collective|glitchcore|iceberg|polymer|prism)\b|lib$", "Bibliotheken"),
    (r"sodium|lithium|ferritecore|entity.?culling|immediatelyfast|chunky|spark", "Performance"),
    (r"spell|wizard|paladin|rune|jewelry", "Magie"),
    (r"delight|tavern|farmer", "Küche & Garten"),
    (r"frog|naturalist|horse|axolotl|ribbit", "Tiere"),
    (r"terralith|tectonic|river|wild|tree|season|waters|puddle", "Welt"),
    (r"furniture|beautify|lantern|lamp|stoneworks|pyrite|plush", "Bauen"),
    (r"sound|ambient|particle|iris|continuity|rain|texture|model.features|trims|colorlight|footstep", "Atmosphäre"),
    (r"archer|armor|armory|arsenal|rogue|weapon|combat|relic|dungeon|quest|skill|critical", "Abenteuer"),
    (r"map|chat|inventory|backpack|grave|zoom|key|menu|tooltip|waystone|claim|portal|lighty|woodcutter|appleskin", "Komfort"),
]


def read_json(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def write_json(path: Path, data):
    """Replace complete files atomically, avoiding half-written catalog data."""
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n",
                                         dir=path.parent, delete=False) as handle:
            temp_path = Path(handle.name)
            handle.write(content)
        temp_path.replace(path)
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink()


def https_url(value, *, icon=False):
    if not isinstance(value, str):
        return None
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        return None
    if icon and not (parsed.hostname == "cdn.modrinth.com" or
                     parsed.hostname.endswith(".forgecdn.net")):
        return None
    return value


def request_json(url, payload=None, api_key=None):
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if payload is not None:
        headers["Content-Type"] = "application/json"
    if api_key:
        headers["x-api-key"] = api_key
    data = json.dumps(payload).encode() if payload is not None else None
    for attempt in range(3):
        try:
            with urlopen(Request(url, data=data, headers=headers), timeout=20) as response:
                return json.load(response)
        except HTTPError as exc:
            retry_after = exc.headers.get("Retry-After", "2")
            exc.close()
            if exc.code not in (429, 500, 502, 503, 504) or attempt == 2:
                print(f"Metadata request failed (HTTP {exc.code}); using cache/fallback.", file=sys.stderr)
                return None
            try:
                delay = float(retry_after)
            except ValueError:
                delay = 2
            time.sleep(max(0, min(delay, 5)))
        except (URLError, TimeoutError, OSError, ValueError):
            if attempt == 2:
                print("Metadata unavailable; using cache/fallback.", file=sys.stderr)
                return None
            time.sleep(1)
    return None


def load_pack(root):
    pack_path = root / "pack.toml"
    pack = tomllib.loads(pack_path.read_text(encoding="utf-8"))
    fingerprint = hashlib.sha256()
    fingerprint.update(b"pack.toml\0" + pack_path.read_bytes())
    records = []
    for path in sorted((root / "mods").glob("*.pw.toml")):
        raw = path.read_bytes()
        mod = tomllib.loads(raw.decode("utf-8"))
        relative = path.relative_to(root).as_posix()
        fingerprint.update(relative.encode() + b"\0" + raw)
        updates = mod.get("update", {})
        source, project = "Unbekannt", None
        if "modrinth" in updates:
            source, project = "Modrinth", str(updates["modrinth"]["mod-id"])
        elif "curseforge" in updates:
            source, project = "CurseForge", str(updates["curseforge"]["project-id"])
        download = mod.get("download", {})
        identity = ":".join([source, project or relative,
                             str(download.get("hash-format", "")), str(download.get("hash", ""))])
        records.append({"id": path.name.removesuffix(".pw.toml"), "packwizName": mod["name"],
                        "filename": mod.get("filename"), "side": mod.get("side", "both"),
                        "packwizFile": relative, "source": source, "projectId": project,
                        "hash": download.get("hash"), "hashAlgorithm": download.get("hash-format"),
                        "identity": identity})
    if not records:
        raise ValueError("No mods/*.pw.toml found; refusing to generate an empty catalog.")
    return pack, records, fingerprint.hexdigest()


def normalize_modrinth(project):
    project_id = str(project["id"])
    return {"name": project["title"], "icon": https_url(project.get("icon_url"), icon=True),
            "summary": str(project.get("description", ""))[:400],
            "tags": sorted(set((project.get("categories") or []) + (project.get("additional_categories") or []))),
            "license": (project.get("license") or {}).get("id"), "authors": [],
            "metadataSource": "Modrinth", "metadataUrl": f"https://modrinth.com/mod/{quote(project_id, safe='')}",
            "codeUrl": https_url(project.get("source_url")), "wikiUrl": https_url(project.get("wiki_url"))}


def fetch_metadata(records, cached, request=request_json):
    """Use exact hashes to cross-reference CF files; never guess project names/slugs."""
    result = {r["identity"]: cached[r["identity"]] for r in records if r["identity"] in cached}
    mr_ids = {r["identity"]: r["projectId"] for r in records if r["source"] == "Modrinth"}
    for algorithm in ("sha1", "sha512"):
        candidates = [r for r in records if r["source"] == "CurseForge" and r["hashAlgorithm"] == algorithm and r["hash"]]
        if not candidates:
            continue
        matches = request(f"{MODRINTH}/version_files", {"hashes": [r["hash"] for r in candidates], "algorithm": algorithm})
        if isinstance(matches, dict):
            for record in candidates:
                matched = matches.get(record["hash"], {})
                if matched.get("project_id"):
                    mr_ids[record["identity"]] = matched["project_id"]
    ids = sorted(set(mr_ids.values()))
    projects = {}
    for offset in range(0, len(ids), 50):
        response = request(f"{MODRINTH}/projects?" + urlencode({"ids": json.dumps(ids[offset:offset + 50])}))
        if isinstance(response, list):
            projects.update({str(p["id"]): p for p in response if isinstance(p, dict) and p.get("id") and p.get("title")})
    for identity, project_id in mr_ids.items():
        if project_id in projects:
            result[identity] = normalize_modrinth(projects[project_id])
    # Optional: only the generator sees this environment variable. Never persisted.
    api_key = os.environ.get("CURSEFORGE_API_KEY")
    cf_records = [r for r in records if r["source"] == "CurseForge"]
    if api_key and cf_records:
        response = request("https://api.curseforge.com/v1/mods",
                           {"modIds": sorted({int(r["projectId"]) for r in cf_records})}, api_key=api_key)
        if isinstance(response, dict) and isinstance(response.get("data"), list):
            by_id = {str(p["id"]): p for p in response["data"] if isinstance(p, dict) and p.get("id")}
            for record in cf_records:
                if project := by_id.get(record["projectId"]):
                    result[record["identity"]] = {
                        "name": project["name"], "icon": https_url((project.get("logo") or {}).get("thumbnailUrl"), icon=True),
                        "summary": str(project.get("summary", ""))[:400],
                        "tags": [c["name"].lower() for c in project.get("categories", [])],
                        "authors": [a["name"] for a in project.get("authors", [])], "license": None,
                        "metadataSource": "CurseForge", "metadataUrl": https_url(project.get("links", {}).get("websiteUrl")) or f"https://www.curseforge.com/projects/{record['projectId']}",
                        "codeUrl": https_url(project.get("links", {}).get("sourceUrl")),
                        "wikiUrl": https_url(project.get("links", {}).get("wikiUrl")),
                    }
    return result


def choose_categories(record, metadata, editorial):
    if editorial.get("categories"):
        chosen = editorial["categories"]
    else:
        name = f"{record['id']} {record['packwizName']}".lower()
        inferred = next((category for pattern, category in NAME_RULES if re.search(pattern, name)), None)
        tags = [TAG_CATEGORIES[tag.lower()] for tag in metadata.get("tags", []) if tag.lower() in TAG_CATEGORIES]
        chosen = ([inferred] if inferred else []) + tags
        # Libraries should not be advertised as player-facing content via API tags.
        if inferred == "Bibliotheken":
            chosen = [inferred]
    return list(dict.fromkeys(c for c in chosen if c in CATEGORIES)) or ["Sonstiges"]


def build_catalog(pack, records, fingerprint, metadata, descriptions):
    mods = []
    for record in records:
        info = metadata.get(record["identity"], {})
        editorial = descriptions.get(record["id"], {})
        categories = choose_categories(record, info, editorial)
        project = quote(record["projectId"] or "", safe="")
        url = (f"https://modrinth.com/mod/{project}" if record["source"] == "Modrinth" else
               f"https://www.curseforge.com/projects/{project}" if record["source"] == "CurseForge" else None)
        mods.append({k: v for k, v in {
            **{k: record[k] for k in ("id", "packwizName", "filename", "side", "packwizFile", "source", "projectId")},
            "name": info.get("name") or record["packwizName"], "url": url,
            "icon": https_url(info.get("icon"), icon=True), "categories": categories,
            "description": editorial.get("description") or CATEGORIES[categories[0]],
            "descriptionKind": "editorial" if editorial.get("description") else "category-fallback",
            "featured": bool(editorial.get("featured", False)),
            "originalSummary": info.get("summary") or None,
            "metadataSource": info.get("metadataSource"), "metadataUrl": https_url(info.get("metadataUrl")),
            "license": info.get("license"), "authors": info.get("authors", []),
            "codeUrl": https_url(info.get("codeUrl")), "wikiUrl": https_url(info.get("wikiUrl")),
        }.items()})
    mods.sort(key=lambda m: (m["name"].casefold(), m["id"]))
    counts = Counter(category for mod in mods for category in mod["categories"])
    return {"schemaVersion": 1, "inputSha256": fingerprint,
            "pack": {"name": pack.get("name", "A Cozy Adventure"), "version": pack.get("version"),
                     "minecraft": pack.get("versions", {}).get("minecraft"),
                     "fabric": pack.get("versions", {}).get("fabric")},
            "total": len(mods), "categories": [{"name": c, "count": counts[c]} for c in CATEGORIES if counts[c]],
            "mods": mods}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, help="Default: <root>/mods.json")
    parser.add_argument("--offline", action="store_true", help="Use checked-in metadata cache, without network access")
    parser.add_argument("--check", action="store_true", help="Check that mods.json matches an offline rebuild; write nothing")
    args = parser.parse_args()
    root = args.root.resolve()
    output = (args.output or root / "mods.json").resolve()
    # Keep accidental CLI paths from overwriting pack files or arbitrary files.
    if output.suffix != ".json" or output.name == "metadata-cache.json":
        parser.error("--output must be a separate .json catalog file")
    cache_path = root / "catalog" / "metadata-cache.json"
    try:
        pack, records, fingerprint = load_pack(root)
        cached = read_json(cache_path, {"schemaVersion": 1, "entries": {}})["entries"]
        if args.offline or args.check:
            metadata = {r["identity"]: cached[r["identity"]] for r in records if r["identity"] in cached}
        else:
            metadata = fetch_metadata(records, cached)
        descriptions = read_json(root / "catalog" / "descriptions.de.json", {})
        catalog = build_catalog(pack, records, fingerprint, metadata, descriptions)
        if args.check:
            if read_json(output, None) != catalog:
                print("Catalog is stale. Run python scripts/generate_mods.py", file=sys.stderr)
                return 1
        else:
            write_json(output, catalog)
            if not args.offline:
                write_json(cache_path, {"schemaVersion": 1, "entries": metadata})
        fallback_count = sum(not m["metadataSource"] for m in catalog["mods"])
        print(f"Catalog OK: {len(records)} mods, {len(records) - fallback_count} with API metadata, {fallback_count} using Packwiz fallback.")
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"Cannot generate catalog: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
