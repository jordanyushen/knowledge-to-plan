#!/usr/bin/env python3
"""Check fixed inputs, reference calculations and archived run structure, not facts."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent / 'knowledge-to-plan' / 'scripts'))
from validate_plan import validate_plan


def check():
    reference = json.loads((ROOT / 'reference' / 'rubric-and-oracles.json').read_text())
    # Handwritten trusted oracle examples, never eval/exec generated lesson code.
    a = [4, 7, 9]
    actual = [[a[0], a[-1], a[1:3]]]
    a = [1]
    a.append([2, 3])
    actual.append(a)
    a = [1]
    a.extend([2, 3])
    actual.append(a)
    a = [3, 1, 2]
    b = a.sort()
    actual.append([a, b])
    a = [1, 2]
    b, c = a, a[:]
    b.append(3)
    actual.append([a, c])
    assert actual == [x['expected'] for x in reference['python-lists']['checks']]
    values = [250 / 1000, 100 * 100, (30 / 100) * (20 / 100), 150 / 30]
    assert values == [x['expected'] for x in reference['si-basics']['checks']]
    source_results = []
    for item in json.loads((ROOT / 'source-manifest.json').read_text()):
        path = ROOT / item['path']
        if path.is_file():
            assert hashlib.sha256(path.read_bytes()).hexdigest() == item['sha256'], item['id']
            status = 'hash-verified'
        elif item['artifact_kind'] == 'downloaded-html':
            status = 'local-snapshot-not-present; fetch-source-before-generation'
        else:
            raise ValueError('Missing tracked source notes: ' + item['path'])
        source_results.append({'id': item['id'], 'status': status})
    runs = []
    for raw in sorted((ROOT / 'runs').glob('*/raw-plan.json')):
        metadata = json.loads((raw.parent / 'run.json').read_text())
        case = json.loads((ROOT / 'cases' / (metadata['case_id'] + '.json')).read_text())
        plan = json.loads(raw.read_text())
        errors = validate_plan(plan, case['days'], case['daily_minutes'])
        assert (not errors) == metadata['initial_structure_valid'], 'Original validation changed: ' + str(raw)
        validated_path = raw.parent / 'plan.json'
        validated = json.loads(validated_path.read_text())
        revised_errors = validate_plan(validated, case['days'], case['daily_minutes'])
        if revised_errors:
            raise ValueError(str(validated_path) + ': ' + '; '.join(revised_errors))
        assert hashlib.sha256(raw.read_bytes()).hexdigest() == metadata['raw_plan_sha256']
        assert hashlib.sha256(validated_path.read_bytes()).hexdigest() == metadata['validated_plan_sha256']
        runs.append({'run': raw.parent.name, 'raw_structure_valid': not errors,
                     'validated_structure_valid': True,
                     'days': case['days'], 'daily_minutes': case['daily_minutes'],
                     'questions': sum(len(x['questions']) for x in plan['lessons'])})
    return {'reference_checks': 9, 'sources': source_results, 'runs': runs,
            'facts_verified': False, 'learner_trial': 'pending',
            'note': 'Counts report program checks only; read individual content reviews.'}


if __name__ == '__main__':
    print(json.dumps(check(), ensure_ascii=False, indent=2))
