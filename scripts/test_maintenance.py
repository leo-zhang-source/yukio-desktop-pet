"""Fail-closed maintenance contracts, exercised without accounts or network."""
from copy import deepcopy
from datetime import date
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import maintenance as cli
import maintenance_lib as lib


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


class GateTests(unittest.TestCase):
    def test_real_test_processes_expose_skips_and_zero_tests(self):
        # A skipped suite exits 0; an empty suite exits 5 on newer Python.
        # Reject either even when another runner reports a successful exit.
        for program, skipped, count in [
            ('import unittest; unittest.main()', 0, 0),
            ('import unittest\nclass T(unittest.TestCase):\n @unittest.skip("intentional probe")\n def test_skip(self): pass\nunittest.main()', 1, 1),
        ]:
            run = subprocess.run([sys.executable, '-c', program], capture_output=True, text=True)
            parsed = lib.parse_counts('python', run.stderr)
            self.assertIn(run.returncode, (0, 5) if count == 0 else (0,))
            self.assertEqual((parsed['skipped'], parsed['tests']), (skipped, count))
            self.assertFalse(lib.suite_passed(dict(exit_code=0, timed_out=False, **parsed)))

    def test_all_formats_reject_unknown_partial_failed_and_skipped(self):
        good = {'swift': '✔ Test run with 10 tests passed after 1 second.',
                'python': 'Ran 10 tests in 0.1s\n\nOK\n',
                'node': '# tests 10\n# fail 0\n# cancelled 0\n# skipped 0\n# todo 0\n'}
        for kind, output in good.items():
            with self.subTest(kind=kind):
                suite = dict(exit_code=0, timed_out=False, **lib.parse_counts(kind, output))
                self.assertTrue(lib.suite_passed(suite))
                for mutation in [dict(timed_out=True), dict(exit_code=1), dict(tests=0),
                                 dict(tests=None), dict(skipped=1), dict(todo=1)]:
                    self.assertFalse(lib.suite_passed(suite | mutation))
                self.assertFalse(lib.suite_passed(dict(exit_code=0, timed_out=False,
                                                      **lib.parse_counts(kind, 'unknown output'))))
        self.assertEqual(lib.parse_counts('swift', '◇ Test "probe" skipped.\n✔ Test run with 1 test passed')['skipped'], 1)
        self.assertEqual(lib.parse_counts('python', 'Ran 1 test in 0.1s\nOK (expected failures=1)')['todo'], 1)
        self.assertFalse(lib.parse_counts('swift', 'Test run with 1 test failed')['summary_passed'])
        self.assertEqual(lib.parse_counts('swift', 'Test run with 1 test passed with 1 known issue')['todo'], 1)

    def test_fingerprint_covers_scripts_config_modes_and_missing_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            names = ['scripts/check.py', 'config/build.json', 'docs/notes.md']
            for name in names:
                path = root / name; path.parent.mkdir(exist_ok=True); path.write_text('original')
            initial = lib.source_fingerprint(root, names)
            (root / names[2]).write_text('documentation only')
            self.assertEqual(initial, lib.source_fingerprint(root, names))
            for name in names[:2]:
                path = root / name; path.write_text('changed')
                self.assertNotEqual(initial, lib.source_fingerprint(root, names))
                path.write_text('original')
            (root / names[0]).chmod(0o755)
            self.assertNotEqual(initial, lib.source_fingerprint(root, names))
            (root / names[0]).unlink()
            self.assertNotEqual(initial, lib.source_fingerprint(root, names))

    def test_test_inventory_rejects_added_or_removed_test(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, (folder, pattern) in lib.SUITES.items():
                path = root / folder / pattern.replace('*', 'test_probe' if pattern == '*.swift' else 'probe')
                path.parent.mkdir(parents=True, exist_ok=True); path.touch()
            write(root/'maintenance/test-inventory.json', {'schema_version': 1, 'suites': lib.discover(root)})
            self.assertEqual(lib.inventory_errors(root), [])
            extra = root/'scripts/test_unregistered.py'; extra.touch()
            self.assertTrue(lib.inventory_errors(root))
            extra.unlink()
            (root/lib.discover(root)['node'][0]).unlink()
            self.assertTrue(lib.inventory_errors(root))

    def test_stale_partial_changed_logs_wrong_package_and_unverified_acceptance(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report = dict(schema_version=2, git_head='a'*40, source_sha256='b'*64,
                          full_suite=True, gate_passed=True, repeat_consistent=True,
                          inventory_errors=[], runs=[], evidence_hashes={})
            for index in (1, 2):
                folder = root/f'run-{index}'; folder.mkdir()
                log = folder/'python.log'; log.write_text('Ran 3 tests in 0.1s\nOK\n')
                suite = dict(exit_code=0, timed_out=False, log='python.log', **lib.parse_counts('python', log.read_text()))
                counts = dict(PASS=3, KNOWN_FAIL=0, UNEXPECTED_FAIL=0, UNEXPECTED_PASS=0)
                controls = dict(passed=True)
                write(folder/'shared.json', {'checks': counts})
                write(folder/'negative-controls/summary.json', controls)
                report['runs'].append(dict(run=index, suites={'python': suite}, shared_exit=0,
                    shared_counts=counts, negative_controls=controls, source_unchanged=True))
            report['evidence_hashes'] = {str(p.relative_to(root)): lib.sha(p) for p in root.rglob('*') if p.is_file()}
            def verify(value, **options):
                write(root/'summary.json', value)
                return lib.verify_evidence(root, 'a'*40, 'b'*64, ['python'], **options)
            self.assertEqual(verify(report), [])
            for mutation in [dict(git_head='c'*40), dict(source_sha256='d'*64),
                             dict(full_suite=False), dict(runs=report['runs'][:1]),
                             dict(evidence_hashes={}), dict(inventory_errors=['missing test'])]:
                self.assertTrue(verify(report | mutation))
            for field, value in [('source_unchanged', False), ('suites', {}), ('shared_exit', 1),
                                 ('shared_counts', dict(PASS=2, KNOWN_FAIL=1, UNEXPECTED_FAIL=0, UNEXPECTED_PASS=0))]:
                broken = deepcopy(report); broken['runs'][0][field] = value
                self.assertTrue(verify(broken))
            log = root/'run-1/python.log'; log.write_text('Ran 0 tests in 0s\nOK\n')
            self.assertTrue(verify(report))
            # Recalculating a corrupted log hash still cannot make inconsistent counts pass.
            changed = deepcopy(report); changed['evidence_hashes']['run-1/python.log'] = lib.sha(log)
            self.assertTrue(verify(changed))
            log.write_text('Ran 3 tests in 0.1s\nOK\n')
            package = root/'candidate.zip'; package.write_bytes(b'synthetic archive')
            build = dict(inputs=dict(source_revision='a'*40, maintenance_source_sha256='b'*64),
                         source_unchanged=True, archives={package.name: dict(sha256=lib.sha(package))})
            write(root/'build.json', build)
            self.assertEqual(verify(report, package=package), [])
            package.write_bytes(b'changed archive')
            self.assertTrue(verify(report, package=package))
            package.write_bytes(b'synthetic archive')
            acceptance = root/'independent.json'; write(acceptance, {'status': 'passed'})
            self.assertTrue(verify(report, package=package, independent=acceptance))
            self.assertTrue(verify(report, independent=acceptance))

    def test_evidence_cannot_escape_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ('../secret', '/tmp/secret'):
                with self.assertRaises(ValueError): lib.safe_evidence(root, name)
            (root/'link').symlink_to('/tmp')
            with self.assertRaises(ValueError): lib.safe_evidence(root, 'link/secret')


class MaintenanceTests(unittest.TestCase):
    def test_due_boundary_and_future_date(self):
        policy = {'reviews': {'dependencies': {'owner': 'maintainer', 'last_reviewed': '2026-10-08', 'interval_days': 30}}}
        self.assertEqual(cli.due_reviews(policy, date(2026, 11, 6))[0]['state'], 'current')
        self.assertEqual(cli.due_reviews(policy, date(2026, 11, 7))[0]['state'], 'due')
        self.assertEqual(cli.due_reviews(policy, date(2026, 10, 7))[0]['state'], 'invalid_future_review')

    def test_float_unhashed_duplicate_or_empty_dependency_locks_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root/'scripts').mkdir()
            path = root/'scripts/macos-build-requirements.txt'
            valid = 'example==1.0 --hash=sha256:'+'1'*64+'\n'
            for content in ('', 'example>=1.0\n', 'example==1.0\n', valid+valid):
                path.write_text(content)
                with self.assertRaises(ValueError): cli.locked_dependencies(root)
            path.write_text(valid); self.assertEqual(cli.locked_dependencies(root)['example']['version'], '1.0')

    def test_audit_network_failure_and_skipped_dependency_remain_unknown(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root/'scripts').mkdir()
            (root/'scripts/macos-build-requirements.txt').write_text('example==1.0 --hash=sha256:'+'1'*64+'\n')
            out = root/'out'; out.mkdir()
            with patch.object(cli.subprocess, 'check_output', side_effect=subprocess.TimeoutExpired('audit', 10)):
                self.assertEqual(cli.audit_dependencies('/missing/auditor', out, root)['status'], 'unknown')
            other = root/'other'; other.mkdir()
            write(other/'audit.json', {'dependencies': [{'name': 'example', 'version': '1.0', 'skip_reason': 'network'}]})
            with patch.object(cli.subprocess, 'check_output', return_value='pip-audit fixture'), \
                 patch.object(cli.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)):
                result = cli.audit_dependencies('/missing/auditor', other, root)
                self.assertEqual(result['status'], 'unknown')
                self.assertFalse(result['complete'])


if __name__ == '__main__': unittest.main()
