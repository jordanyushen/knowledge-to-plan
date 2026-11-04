"""Completed batches merge deterministically; broken author inputs stay untouched."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from merge_plan import merge_plan
from test_workflow import fixture


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')


def workspace(root):
    plan = fixture()
    plan['course']['days'] = 11
    base = plan['lessons'][0]
    plan['lessons'] = []
    for day in range(1, 12):
        lesson = copy.deepcopy(base)
        lesson.update(day=day, id=f'lesson-{day}', title=f'长度换算练习{day}')
        if day > 1:
            lesson['review_of'] = [day - 1]
        plan['lessons'].append(lesson)
    write_json(root / 'course.json', plan['course'])
    write_json(root / 'sources.json', plan['sources'])
    # Deliberately write in a different filesystem creation order.
    for start, end in [(11, 11), (6, 10), (1, 5)]:
        write_json(root / 'lessons' / f'{start:03d}-{end:03d}.json', plan['lessons'][start - 1:end])
    return plan


class MergeTests(unittest.TestCase):
    def test_three_batches_preserve_content_and_are_deterministic(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            expected = workspace(root)
            before = {path: path.read_bytes() for path in root.rglob('*.json')}
            plan, report = merge_plan(root, 11, 12)
            self.assertEqual(plan, expected)
            self.assertEqual(report['batches'], 3)
            self.assertEqual(merge_plan(root, 11, 12), (plan, report))
            self.assertEqual({path: path.read_bytes() for path in before}, before)
            self.assertFalse(report['budget_verified'])
            self.assertFalse(report['facts_verified'])

    def test_cross_batch_review_reference_and_sources_checked(self):
        for mutation in [lambda batch: batch[0].update(review_of=[6]),
                         lambda batch: batch[0].update(source_ids=['absent']),
                         lambda batch: batch[0].update(id='lesson-1')]:
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as folder:
                root = Path(folder); workspace(root)
                path = root / 'lessons/006-010.json'
                batch = json.loads(path.read_text(encoding='utf-8'))
                mutation(batch); write_json(path, batch)
                with self.assertRaises(ValueError):
                    merge_plan(root, 11, 12)

    def test_missing_overlap_order_and_oversized_batch_fail(self):
        for action in ('missing', 'overlap', 'order', 'oversize', 'wrapper', 'unexpected'):
            with self.subTest(action=action), tempfile.TemporaryDirectory() as folder:
                root = Path(folder); plan = workspace(root)
                path = root / 'lessons/006-010.json'
                if action == 'missing':
                    path.unlink()
                elif action == 'overlap':
                    write_json(root / 'lessons/005-005.json', [plan['lessons'][4]])
                elif action == 'order':
                    write_json(path, list(reversed(plan['lessons'][5:10])))
                elif action == 'oversize':
                    (root / 'lessons/001-005.json').rename(root / 'lessons/001-006.json')
                elif action == 'wrapper':
                    write_json(path, {'course': plan['course'], 'lessons': plan['lessons'][5:10]})
                else:
                    write_json(root / 'lessons/notes.json', [])
                with self.assertRaises(ValueError):
                    merge_plan(root, 11, 12)

    def test_constraints_independently_checked_not_inferred_from_course(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); workspace(root)
            for days, minutes in [(10, 12), (11, 30), (True, 12), (11, 0), (None, 12), (11, None)]:
                with self.subTest(days=days, minutes=minutes), self.assertRaises(ValueError):
                    merge_plan(root, days, minutes)

    def test_metadata_conflicts_duplicate_json_keys_and_incomplete_content(self):
        for action in ('course-wrapper', 'lesson-metadata', 'json-duplicate', 'missing-teaching'):
            with self.subTest(action=action), tempfile.TemporaryDirectory() as folder:
                root = Path(folder); plan = workspace(root)
                path = root / 'lessons/001-005.json'
                batch = plan['lessons'][:5]
                if action == 'course-wrapper':
                    write_json(root / 'course.json', {'course': plan['course']})
                elif action == 'lesson-metadata':
                    batch[0]['course'] = {'days': 1}; write_json(path, batch)
                elif action == 'json-duplicate':
                    raw = (root / 'course.json').read_text(encoding='utf-8')
                    (root / 'course.json').write_text('{"days":1,' + raw[1:], encoding='utf-8')
                else:
                    batch[0]['sections'] = []; write_json(path, batch)
                with self.assertRaises(ValueError):
                    merge_plan(root, 11, 12)

    def test_resume_hashes_show_only_changed_batch_and_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); workspace(root)
            write_json(root / 'estimate.json', {'status': 'estimated'})
            write_json(root / 'budget.json', {'status': 'fits'})
            before_plan, before = merge_plan(root, 11, 12)
            path = root / 'lessons/011-011.json'
            batch = json.loads(path.read_text(encoding='utf-8'))
            batch[0]['title'] = '最后一课：回顾换算'
            write_json(path, batch)
            after_plan, after = merge_plan(root, 11, 12)
            old_hashes = {item['path']: item['sha256'] for item in before['inputs']}
            new_hashes = {item['path']: item['sha256'] for item in after['inputs']}
            self.assertEqual([name for name in old_hashes if old_hashes[name] != new_hashes[name]], ['lessons/011-011.json'])
            self.assertNotEqual(before['plan_sha256'], after['plan_sha256'])
            self.assertEqual(before_plan['lessons'][:10], after_plan['lessons'][:10])
            self.assertEqual(new_hashes['budget.json'], hashlib.sha256((root / 'budget.json').read_bytes()).hexdigest())

    def test_cli_works_elsewhere_and_refuses_overwriting_inputs(self):
        script = Path(__file__).with_name('merge_plan.py').resolve()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); expected = workspace(root)
            output, report = root / 'output/plan.json', root / 'output/merge-report.json'
            command = [sys.executable, '-B', str(script), '--workspace', str(root), '--output', str(output), '--report', str(report), '--expected-days', '11', '--expected-daily-minutes', '12']
            run = subprocess.run(command, cwd=root.parent, text=True, capture_output=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(json.loads(output.read_text(encoding='utf-8')), expected)
            self.assertEqual(json.loads(report.read_text(encoding='utf-8'))['batches'], 3)
            original = output.read_bytes()
            again = subprocess.run(command, cwd=root.parent, text=True, capture_output=True)
            self.assertNotEqual(again.returncode, 0)
            self.assertEqual(output.read_bytes(), original)
            course = root / 'course.json'; original = course.read_bytes()
            command[command.index('--output') + 1] = str(course)
            run = subprocess.run(command + ['--overwrite'], cwd=root.parent, text=True, capture_output=True)
            self.assertNotEqual(run.returncode, 0)
            self.assertEqual(course.read_bytes(), original)
            for forbidden in [root / 'budget.json', root / 'lessons/nested/plan.json']:
                command[command.index('--output') + 1] = str(forbidden)
                run = subprocess.run(command + ['--overwrite'], cwd=root.parent, text=True, capture_output=True)
                self.assertNotEqual(run.returncode, 0)
                self.assertFalse(forbidden.exists())

    def test_invalid_input_writes_nothing(self):
        script = Path(__file__).with_name('merge_plan.py').resolve()
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); workspace(root)
            (root / 'lessons/011-011.json').unlink()
            output = root / 'out/plan.json'
            run = subprocess.run([sys.executable, '-B', str(script), '--workspace', str(root), '--output', str(output), '--expected-days', '11', '--expected-daily-minutes', '12'], text=True, capture_output=True)
            self.assertEqual(run.returncode, 2)
            self.assertFalse(output.parent.exists())


if __name__ == '__main__':
    unittest.main()
