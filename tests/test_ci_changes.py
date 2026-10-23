"""Routing is a safety boundary: test scopes and cumulative/rename git behavior."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from ci_changes import classify, changed_paths, FLAGS


class RoutingTests(unittest.TestCase):
    def assert_scope(self, paths, expected):
        self.assertEqual({k for k, v in classify(paths).items() if v}, set(expected))

    def test_mod_only(self):
        self.assert_scope(['mods/example.pw.toml', 'index.toml'], ['pack', 'catalog', 'candidate'])

    def test_website_only(self):
        self.assert_scope(['assets/styles.css'], ['website', 'catalog'])

    def test_documentation_only(self):
        self.assert_scope(['README.md', 'docs/ci.md', 'docs/customization/README.md', 'docs/releases/v1.0.1-pr.md'], [])

    def test_updater_and_combined(self):
        self.assert_scope(['src/customization/Launcher.java'], ['pack', 'catalog', 'protection', 'candidate'])
        self.assert_scope(['mods/test.pw.toml', 'assets/app.js'], ['pack', 'catalog', 'candidate', 'website'])

    def test_build_markdown_is_not_skipped(self):
        self.assertTrue(classify(['docs/serverpack/README-SERVER.md'])['candidate'])
        self.assertTrue(classify(['docs/releases/v1.1.0.md'], version='1.1.0')['candidate'])
        self.assertTrue(classify(['docs/customization/PACKWIZ-LICENSE.txt'])['protection'])

    def test_unknown_ci_and_manual_fail_closed(self):
        for path in ['new-build-input.dat', '.github/workflows/serverpack.yml', 'tests/new_test.py']:
            self.assert_scope([path], FLAGS)
        self.assertEqual(classify([], full=True), dict.fromkeys(FLAGS, True))

    def test_entire_pr_and_renames_include_earlier_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            def git(*args):
                return subprocess.check_output(['git', '-C', directory, *args], stderr=subprocess.DEVNULL).decode().strip()
            git('init'); git('config', 'user.name', 'CI'); git('config', 'user.email', 'ci@example.invalid')
            p = Path(directory)
            (p/'input.dat').write_text('initial'); git('add', '.'); git('commit', '-m', 'base')
            base = git('rev-parse', 'HEAD')
            (p/'input.dat').write_text('changed'); git('commit', '-am', 'critical change')
            (p/'README.md').write_text('docs'); git('add', '.'); git('commit', '-m', 'docs only last commit')
            head = git('rev-parse', 'HEAD')
            previous = os.getcwd()
            try:
                os.chdir(directory)
                self.assertEqual(set(changed_paths(base, head)), {'input.dat', 'README.md'})
                git('mv', 'input.dat', 'renamed.md'); git('commit', '-m', 'move critical input')
                self.assertIn('input.dat', changed_paths(base, git('rev-parse', 'HEAD')))
                with self.assertRaises(subprocess.CalledProcessError): changed_paths('missing-base', head)
            finally:
                os.chdir(previous)
