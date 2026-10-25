#!/usr/bin/env python3
"""Export reviewed progress copy and three static assets; never read runtime data."""
import argparse
import hashlib
from datetime import datetime, timezone
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
FILES = {'index.html', 'app.js', 'style.css', 'status.json', '.nojekyll', 'README.md'}


def text(value):
    if not isinstance(value, str):
        raise ValueError('Public copy must contain text, not nested metadata')
    return value


def lines(value):
    if not isinstance(value, list):
        raise ValueError('Expected a list of public paragraphs')
    return [text(x) for x in value]


def public_project(source):
    # Deliberately reconstruct each level. Unrecognized fields cannot leak into Pages.
    if source['schema_version'] != 1:
        raise ValueError('Unknown progress schema')
    project = {key: text(source[key]) for key in ('updated_at', 'focus_id', 'boundary')}
    project['schema_version'] = 1
    project['current_note'] = text(source['public_current_note'])
    project['work_state'] = text(source['public_work_state'])
    stages = []
    for raw in source['stages']:
        stage = {key: text(raw[key]) for key in ('id', 'status', 'title', 'summary')}
        if not re.fullmatch(r'[a-z][a-z0-9-]*', stage['id']):
            raise ValueError('Invalid stage ID')
        if stage['status'] not in {'complete', 'active', 'planned', 'blocked'}:
            raise ValueError('Invalid stage status')
        for key in ('outcome', 'example', 'evidence'):
            if key in raw:
                stage[key] = text(raw[key])
        for key in ('details',):
            if key in raw:
                stage[key] = lines(raw[key])
        stage['explanation'] = [dict(title=text(x['title']), paragraphs=lines(x['paragraphs']))
                                for x in raw.get('explanation', [])]
        stage['checks'] = []
        for check in raw.get('checks', []):
            if type(check['done']) is not bool:
                raise ValueError('Invalid check completion')
            stage['checks'].append(dict(label=text(check['label']), done=check['done']))
        stages.append(stage)
    if not stages or len({s['id'] for s in stages}) != len(stages):
        raise ValueError('Missing or duplicate stages')
    if project['focus_id'] not in {s['id'] for s in stages}:
        raise ValueError('Unknown focus stage')
    project['stages'] = stages
    # Optional work is separate from the nine delivery stages.
    project['optional_tasks'] = [dict(title=text(x['title']), summary=text(x['summary']),
                                      details=lines(x.get('details', [])))
                                  for x in source.get('optional_tasks', [])]
    project['updates'] = [dict(at=text(x['at']), text=text(x['text'])) for x in source['updates']]
    # Editorial text still needs human review; these catch accidental obvious secrets/paths.
    serialized = json.dumps(project, ensure_ascii=False, allow_nan=False)
    if re.search(r'/Users/|/home/|BEGIN .*PRIVATE KEY|gh[pousr]_[A-Za-z0-9]{16,}|sk-[A-Za-z0-9]{16,}', serialized):
        raise ValueError('Review public copy: possible private path or credential')
    return project


def export(destination, source=None):
    source = source if source is not None else json.loads((ROOT / 'progress.json').read_text())
    project = public_project(source)
    if destination.is_symlink() or (destination.exists() and any(destination.iterdir())):
        raise ValueError('Export requires a new or empty directory')
    destination.mkdir(parents=True, exist_ok=True)
    html = (ROOT / 'dist/index.html').read_text().replace('<html lang="zh-CN">', '<html lang="zh-CN" data-view="published">')
    # CSP meta is needed on Pages, where we cannot set response headers ourselves.
    html = html.replace('<head>', '<head><meta http-equiv="Content-Security-Policy" content="default-src \'self\'; script-src \'self\'; style-src \'self\'; connect-src \'self\'; object-src \'none\'; base-uri \'none\'"><meta name="referrer" content="no-referrer">')
    # Pages/browser caches may otherwise combine new progress with an old renderer.
    for name in ('app.js', 'style.css'):
        version = hashlib.sha256((ROOT / 'dist' / name).read_bytes()).hexdigest()[:16]
        html = html.replace('./' + name + '"', './' + name + '?v=' + version + '"')
    (destination / 'index.html').write_text(html)
    for name in ('app.js', 'style.css'):
        (destination / name).write_bytes((ROOT / 'dist' / name).read_bytes())
    snapshot = dict(project=project, collector=None, publication=dict(mode='published',
                    exported_at=datetime.now(timezone.utc).isoformat()))
    (destination / 'status.json').write_text(json.dumps(snapshot, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    (destination / '.nojekyll').write_text('')
    (destination / 'README.md').write_bytes((ROOT / 'PUBLIC-README.md').read_bytes())
    assert {p.name for p in destination.iterdir()} == FILES
    return destination


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    print(export(args.out))
