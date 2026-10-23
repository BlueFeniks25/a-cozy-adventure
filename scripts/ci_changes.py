#!/usr/bin/env python3
"""Conservative CI routing from the entire PR (never only the last commit).

Unknown inputs select everything. Missing git objects fail the job. No network,
GitHub token, caches or previous-run results are used to infer test success.
"""
import json
import os
import tomllib
from pathlib import Path
import subprocess

FLAGS = ('pack', 'catalog', 'protection', 'website', 'candidate')


def classify(paths, full=False, version=None):
    if version is None:
        version = tomllib.loads((Path(__file__).resolve().parents[1] / "pack.toml").read_text(encoding="utf-8"))["version"]
    selected = set(FLAGS) if full else set()
    for path in paths:
        if path.startswith(('.github/', 'tests/test_ci')):
            # CI/build/updater changes can alter any dependency or routing rule.
            selected.update(FLAGS)
        elif path.startswith('src/') or path in ('scripts/build_prism.py', 'scripts/build_serverpack.py', 'scripts/audit_customization.py'):
            selected.update(('pack', 'catalog', 'protection', 'candidate'))
        elif path == 'scripts/generate_mods.py':
            selected.update(('catalog', 'website'))
        elif path == 'scripts/prepare_release.py':
            selected.update(('pack', 'candidate'))
        elif path.startswith(('mods/', 'config/', 'resourcepacks/')) or path in ('pack.toml', 'index.toml', '.packwizignore'):
            selected.update(('pack', 'catalog', 'candidate'))
        elif path.startswith(('assets/', 'catalog/')) or path in ('index.html', 'mods.json', '.nojekyll') or path.endswith(('.cjs', 'package.json', 'package-lock.json')):
            selected.update(('website', 'catalog'))
        elif path in ('docs/customization/dependencies.json', 'docs/customization/PACKWIZ-LICENSE.txt'):
            selected.update(('pack', 'protection', 'candidate'))
        elif path in ('docs/serverpack/config-selection.json', 'docs/serverpack/README-SERVER.md') or path in (f'docs/releases/v{version}.md', f'docs/releases/v{version}-rollout.md'):
            # Includes README-SERVER.md and release Markdown embedded in ZIPs.
            selected.update(('pack', 'candidate'))
        elif path == 'tests/test_generator.py':
            selected.add('catalog')
        elif path == 'tests/test_serverpack.py':
            selected.update(('pack', 'candidate'))
        elif path in ('tests/test_prism.py', 'tests/test_customization.py'):
            selected.update(('protection', 'candidate'))
        elif path == 'tests/test_release.py':
            selected.update(('pack', 'website', 'candidate'))
        elif path.endswith('.md'):
            pass
        else:
            selected.update(FLAGS)
    return {flag: flag in selected for flag in FLAGS}


def changed_paths(base, head):
    # --no-renames exposes both deleted and added inputs, including moves to docs.
    raw = subprocess.check_output(['git', 'diff', '--no-renames', '--name-only', '-z', f'{base}...{head}'])
    return [p.decode('utf-8', errors='strict') for p in raw.split(b'\0') if p]


def main():
    base, head = os.environ.get('CI_BASE'), os.environ.get('CI_HEAD')
    full = os.environ.get('GITHUB_EVENT_NAME') != 'pull_request'
    if not full and (not base or not head):
        raise RuntimeError('PR base/head SHA missing; refusing to skip tests')
    result = classify([] if full else changed_paths(base, head), full=full)
    with Path(os.environ['GITHUB_OUTPUT']).open('a', encoding='utf-8') as output:
        for key, value in result.items():
            output.write(f'{key}={str(value).lower()}\n')
    print(json.dumps({'scope': result, 'comparison': 'full' if full else 'PR merge-base...head'}, sort_keys=True))


if __name__ == '__main__':
    main()
