"""Privacy boundary and export safety regression checks; all data is synthetic."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from export_public import FILES, export, public_project


def fixture():
    return dict(schema_version=1, updated_at='2026-10-21T00:00:00Z', focus_id='sample',
                boundary='测试边界', current_note='PRIVATE_LOCAL_NOTE', work_state='PRIVATE_RUNTIME',
                public_current_note='公开说明', public_work_state='公开进度',
                stages=[dict(id='sample', status='planned', title='示例', summary='测试安排',
                             explanation=[dict(title='原因', paragraphs=['测试文字'])],
                             checks=[dict(label='测试检查', done=False)])],
                updates=[dict(at='2026-10-21', text='测试记录')])


class PublicExportTests(unittest.TestCase):
    def test_unknown_metadata_never_reaches_public_snapshot(self):
        source = fixture()
        for node in (source, source['stages'][0], source['stages'][0]['explanation'][0],
                     source['stages'][0]['checks'][0], source['updates'][0]):
            node['extra'] = {'private': 'PRIVATE_SENTINEL'}
        source['collector'] = {'session_id': 'PRIVATE_SENTINEL'}
        with tempfile.TemporaryDirectory() as tmp:
            out = export(Path(tmp) / 'site', source)
            self.assertEqual({p.name for p in out.iterdir()}, FILES)
            raw = (out / 'status.json').read_text()
            self.assertNotIn('PRIVATE_', raw)
            self.assertIsNone(json.loads(raw)['collector'])
            self.assertIn('data-view="published"', (out / 'index.html').read_text())
            for name in ('style.css', 'app.js'):
                version = hashlib.sha256((out / name).read_bytes()).hexdigest()[:16]
                self.assertIn('./' + name + '?v=' + version + '"', (out / 'index.html').read_text())

    def test_optional_work_keeps_only_reviewed_copy_and_does_not_change_stage_count(self):
        source=fixture()
        source['optional_tasks']=[dict(title='Windows 之后可选',summary='不计入本轮',
                                      details=['保留未验收范围'],private='PRIVATE_SENTINEL')]
        exported=public_project(source)
        self.assertEqual(len(exported['stages']),1)
        self.assertEqual(exported['optional_tasks'],[dict(title='Windows 之后可选',summary='不计入本轮',details=['保留未验收范围'])])
        source['optional_tasks'][0]['details']={'private':'hidden'}
        with self.assertRaises(ValueError):public_project(source)

    def test_populated_destination_preserves_existing_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            marker = out / 'keep.txt'
            marker.write_text('preserve')
            with self.assertRaises(ValueError):
                export(out, fixture())
            self.assertEqual(marker.read_text(), 'preserve')
            self.assertEqual(list(out.iterdir()), [marker])

    def test_reject_nested_metadata_in_text_field(self):
        for field in ('title', 'details'):
            source = fixture()
            source['stages'][0][field] = {'private': 'PRIVATE_SENTINEL'}
            with self.assertRaises(ValueError):
                public_project(source)

    def test_require_explicit_public_copy(self):
        source = fixture()
        del source['public_current_note']
        with self.assertRaises(KeyError):
            public_project(source)

    def test_reject_obvious_private_material(self):
        for value in ('/Users/person/file', '/home/person/file',
                      '-----BEGIN PRIVATE KEY-----', 'sk-' + 's' * 30):
            source = fixture()
            source['public_current_note'] = value
            with self.assertRaises(ValueError):
                public_project(source)

    def test_invalid_stage_links_fail_export(self):
        source = fixture()
        source['stages'].append(copy.deepcopy(source['stages'][0]))
        with self.assertRaises(ValueError):
            public_project(source)
        source = fixture()
        source['focus_id'] = 'missing'
        with self.assertRaises(ValueError):
            public_project(source)


if __name__ == '__main__':
    unittest.main()
