#!/usr/bin/env python3
"""Hash-verify pinned JARs and audit independent optional client components.

Reads JARs only; never starts Minecraft or changes an installed instance.
Python 3.11+, standard library only. No network or API credentials required.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import io
import json
from pathlib import Path
import sys
import tomllib
import zipfile

from build_serverpack import BUILTINS, BuildError, inspect_jar, matches_version, verify

ROOT = Path(__file__).resolve().parents[1]


def supplementary_metadata(data, label, result=None):
    """Keep advisory metadata separate from Fabric's required dependencies."""
    result = result if result is not None else {}
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        raw = archive.read("fabric.mod.json")
        meta = json.loads(raw.decode("utf-8-sig"), strict=False)
        result[label] = {"recommends": meta.get("recommends", {}),
                         "suggests": meta.get("suggests", {}),
                         "metadataSha256": hashlib.sha256(raw).hexdigest()}
        for entry in meta.get("jars", []):
            supplementary_metadata(archive.read(entry["file"]), label + "!" + entry["file"], result)
    return result


def audit(root: Path, jars: Path):
    records, nodes = [], []
    for path in sorted((root / "mods").glob("*.pw.toml")):
        meta = tomllib.loads(path.read_text(encoding="utf-8"))
        data = (jars / meta["filename"]).read_bytes()
        download = meta["download"]
        verify(data, download["hash-format"], download["hash"], meta["filename"])
        owner = path.stem.removesuffix(".pw")
        found = inspect_jar(data, meta["filename"])
        extra = supplementary_metadata(data, meta["filename"])
        for node in found:
            node["owner"] = owner
            node.update(extra[node["location"]])
        nodes.extend(found)
        records.append({"id": owner, "name": meta["name"], "side": meta["side"],
                        "packwizFile": path.relative_to(root).as_posix(),
                        "filename": meta["filename"], "hashFormat": download["hash-format"],
                        "hash": download["hash"], "jarSha256": hashlib.sha256(data).hexdigest(),
                        "fabricId": found[0]["id"], "fabricVersion": found[0]["version"],
                        "fabricEnvironment": found[0]["environment"], "nodes": found})
    by_owner = {record["id"]: record for record in records}
    builtins = dict(BUILTINS)
    pack = tomllib.loads((root / "pack.toml").read_text(encoding="utf-8"))
    builtins.update(minecraft=pack["versions"]["minecraft"], fabricloader=pack["versions"]["fabric"])

    def providers(enabled, environment="client"):
        available = defaultdict(list)
        for identifier, version in builtins.items():
            available[identifier].append({"id": identifier, "version": version, "owner": None})
        for node in nodes:
            if node["owner"] not in enabled or node["environment"] not in ("*", environment):
                continue
            for identifier in (node["id"], *node["provides"]):
                available[identifier].append(node)
        return available

    def missing(enabled, environment="client"):
        available = providers(enabled, environment)
        errors, breaks, conflicts = [], [], []
        for node in nodes:
            if node["owner"] not in enabled or node["environment"] not in ("*", environment):
                continue
            for identifier, requirement in node["depends"].items():
                if not any(matches_version(provider["version"], requirement) for provider in available[identifier]):
                    errors.append({"owner": node["owner"], "fabricId": node["id"],
                                   "requires": identifier, "version": requirement})
            for kind, target in (("breaks", breaks), ("conflicts", conflicts)):
                for identifier, requirement in node[kind].items():
                    if any(matches_version(provider["version"], requirement) for provider in available[identifier]):
                        target.append({"owner": node["owner"], "fabricId": node["id"],
                                       "other": identifier, "version": requirement})
        return {"missingDependencies": errors, "breaks": breaks, "conflicts": conflicts}

    all_roots = set(by_owner)
    clients = {r["id"] for r in records if r["side"] == "client"}
    available = providers(all_roots)
    for record in records:
        edges = []
        for node in record["nodes"]:
            for identifier, requirement in sorted(node["depends"].items()):
                owners = sorted({p["owner"] for p in available[identifier]
                                 if p["owner"] is not None and matches_version(p["version"], requirement)})
                edges.append({"from": node["id"], "requires": identifier,
                              "version": requirement, "providers": owners,
                              "builtin": identifier in builtins})
        record["mandatoryDependencies"] = edges
        if record["id"] in clients:
            record["removeIndividually"] = missing(all_roots - {record["id"]})
    # This closure preserves alternative providers: an owner named here is not
    # necessarily required by itself when another JAR bundles the same library.
    for record in records:
        reachable, pending = set(), [record["id"]]
        while pending:
            owner = pending.pop()
            for edge in by_owner[owner]["mandatoryDependencies"]:
                for provider in edge["providers"]:
                    if provider != record["id"] and provider not in reachable:
                        reachable.add(provider)
                        pending.append(provider)
        record["transitivePossibleProviderOwners"] = sorted(reachable)
    retained = {identifier for identifier in clients
                if any(missing(all_roots - {identifier})[kind]
                       for kind in ("missingDependencies", "breaks"))}
    optional = clients - retained
    # Every enabled option must be valid against mandatory roots alone. This is a
    # compositional proof for positive depends clauses across all 2**N choices:
    # adding options cannot remove a provider. Check cross-option breaks too.
    mandatory = all_roots - optional
    combinations = {"mandatoryOnly": missing(mandatory), "eachOptionalWithMandatory": {},
                    "allEnabled": missing(all_roots), "optionalCount": len(optional),
                    "coveredSelectionCount": 2 ** len(optional),
                    "method": "Every optional root is checked with mandatory roots alone; all enabled roots are checked for breaks/conflicts. Positive dependencies remain satisfied under every union of these independent options. Static availability is not a full Fabric resolver or runtime compatibility test."}
    for identifier in sorted(optional):
        combinations["eachOptionalWithMandatory"][identifier] = missing(mandatory | {identifier})
    for record in records:
        if record["id"] in clients:
            record["recommendation"] = "required-support" if record["id"] in retained else "optional-default-on"
    return {"schemaVersion": 1, "scope": "Exact pinned JAR metadata including declared nested JARs; read-only inspection, no production instance tests.",
            "builtins": builtins, "counts": {"mods": len(records), "clientOnlyPackwiz": len(clients),
            "fabricMetadataNodes": len(nodes), "independentOptions": len(optional), "requiredClientSupport": len(retained)},
            "requiredClientSupport": sorted(retained), "optionalDefaultOn": sorted(optional),
            "selectionValidation": combinations, "mods": records}


def markdown(report):
    counts = report["counts"]
    lines = ["# Dependency audit for player customization", "",
             f"All {counts['mods']} pinned mod JARs were verified against their Packwiz hashes, then {counts['fabricMetadataNodes']} top-level/nested Fabric metadata records were read. No installed instance was launched or modified.", "",
             "Reproduce with Python 3.11+: `python scripts/audit_customization.py --jars PATH_TO_PINNED_JARS`. The input directory is read only. The output JSON records hashes, exact versions, environment, dependency ranges, aliases, nested origins, breaks/conflicts, and dependency providers for every mod.", "",
             "`depends` is mandatory; `breaks` is a hard incompatibility; `conflicts` is a Fabric warning. `recommends`/`suggests` are recorded as advisory. Shared libraries remain required when making their users independent options. Packwiz `side` alone does not establish dependency safety.", "",
             "Dependency provider lists are alternatives: Fabric API modules can be supplied by Fabric API itself or by another mod's bundled JAR. A listed provider is not individually mandatory when another compatible provider remains. The JSON also includes each root's transitive possible provider closure; it deliberately preserves these alternatives.", "",
             "## Client-only decisions", "", "| Component | Fabric ID | Decision | Required users if removed |", "|---|---|---|---|"]
    for record in report["mods"]:
        if record["side"] != "client":
            continue
        users = record["removeIndividually"]["missingDependencies"]
        detail = "; ".join(sorted({f"{e['fabricId']} → {e['requires']}" for e in users})) or "None"
        lines.append(f"| {record['name']} | `{record['fabricId']}` | {record['recommendation']} | {detail} |")
    validation = report["selectionValidation"]
    errors = []
    for label, result in [("mandatory only", validation["mandatoryOnly"]), ("all enabled", validation["allEnabled"]), *validation["eachOptionalWithMandatory"].items()]:
        for kind in ("missingDependencies", "breaks", "conflicts"):
            errors.extend(f"{label}: {kind}: `{json.dumps(error, ensure_ascii=False)}`" for error in result[kind])
    lines += ["", "## Selection validation", "",
              f"{counts['independentOptions']} independent client options represent {validation['coveredSelectionCount']:,} selections. Each option plus the mandatory set is checked, and the full set is checked for incompatibilities. This proves availability of positive mandatory dependencies under all unions of options; it is not a complete Fabric version resolver, client launch, rendering, or server join test.", ""]
    lines.extend(["Findings:", "", *[f"- {error}" for error in errors]] if errors else ["All static mandatory-dependency and declared incompatibility checks pass."])
    lines += ["", "## Complete inventory", "", "| Packwiz file | Fabric ID / version | Side | Available dependency provider owners (including nested metadata) |", "|---|---|---|---|"]
    for record in report["mods"]:
        owners = sorted({owner for edge in record["mandatoryDependencies"] for owner in edge["providers"] if owner != record["id"]})
        lines.append(f"| `{record['packwizFile']}` | `{record['fabricId']}` / `{record['fabricVersion']}` | {record['side']} | {', '.join(owners) or 'Builtins / bundled only'} |")
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--jars", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "docs/customization/dependencies.json")
    args = parser.parse_args()
    try:
        report = audit(args.root, args.jars)
    except (OSError, ValueError, BuildError) as error:
        parser.exit(1, f"Dependency audit failed: {error}\n")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    args.output.with_suffix(".md").write_text(markdown(report), encoding="utf-8")
    print(json.dumps(report["counts"], sort_keys=True))
    print("Required client support: " + ", ".join(report["requiredClientSupport"]))
    findings = [report["selectionValidation"]["allEnabled"], report["selectionValidation"]["mandatoryOnly"],
                *report["selectionValidation"]["eachOptionalWithMandatory"].values()]
    return int(any(result["missingDependencies"] or result["breaks"] for result in findings))


if __name__ == "__main__":
    sys.exit(main())
