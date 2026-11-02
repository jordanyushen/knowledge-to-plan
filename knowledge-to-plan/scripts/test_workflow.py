"""Behavioral tests using synthetic lessons; no accounts, network or original courses."""
import copy
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from assess_budget import assess_budget
from build_learning_site import build, fold_ics_line, make_ics
from validate_plan import validate_plan


def fixture():
    return {
        'schema_version': 1,
        'course': {'id': 'units-test', 'title': '单位练习', 'goal': '换算长度单位', 'background': '入门', 'days': 2, 'daily_minutes': 12, 'timezone': 'Asia/Hong_Kong', 'start_date': '2026-11-02', 'study_time': '14:30'},
        'sources': [{'id': 'raw', 'title': '给定知识', 'locator': '1米=1000毫米'}],
        'lessons': [{
            'id': f'day-{day}', 'day': day, 'title': f'第{day}天长度换算',
            'objectives': ['理解单位比例'], 'activities': [{'kind': 'learn', 'minutes': 5}, {'kind': 'practice', 'minutes': 4}, {'kind': 'quiz', 'minutes': 3}],
            'sections': [{'title': '换算关系', 'body': '1米等于1000毫米。从毫米变成米时除以1000，改变表示方式而不改变实际长度。', 'example': '500毫米=0.5米'}],
            'practice': '将250毫米换成米。', 'takeaways': ['毫米换成米需除以1000'], 'source_ids': ['raw'],
            'questions': [{'id': 'q1', 'prompt': '500毫米是多少米？', 'options': ['0.5米', '500米'], 'correct_index': 0, 'explanations': ['500除以1000得到0.5米。', '只改单位不改数值会放大实际长度。']}]
        } for day in [1, 2]]
    }


class BudgetTests(unittest.TestCase):
    def test_budget_and_fixed_alternatives(self):
        result = assess_budget(5, 10, 2, 3, 0)
        self.assertEqual(result['status'], 'insufficient')
        self.assertEqual(result['current_plan']['days'], 5)
        self.assertEqual(result['current_plan']['daily_minutes'], 10)
        self.assertEqual(result['recommended_total_days_range']['low'], 12)
        self.assertEqual(result['recommended_daily_minutes_range']['low'], 24)
        self.assertFalse(result['recommendation_rules']['automatic_plan_changes'])

    def test_fit_borderline_boundary(self):
        self.assertEqual(assess_budget(2, 30, .5, .85, 15)['status'], 'fits')
        self.assertEqual(assess_budget(2, 30, .8, 1, 15)['status'], 'borderline')
        self.assertEqual(assess_budget(2, 30, .86, 1, 15)['status'], 'insufficient')

    def test_impossible_daily_proposal_identified(self):
        result = assess_budget(1, 30, 30, 40, 0)
        self.assertFalse(result['recommended_daily_minutes_range']['low_within_24_hours'])
        with self.assertRaises(ValueError):
            assess_budget(1, 1441, 1, 2)

    def test_invalid_parameters(self):
        for args in [(True, 30, 1, 2), (1, 0, 1, 2), (1, 30, 2, 1), (1, 30, float('nan'), 1), (1, 30, 1, float('inf')), (1, 30, 1, 2, 100)]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                assess_budget(*args)


class PlanTests(unittest.TestCase):
    def test_valid_variable_course(self):
        self.assertEqual(validate_plan(fixture()), [])

    def test_excess_daily_time_rejected(self):
        p = fixture()
        p['lessons'][0]['activities'][0]['minutes'] = 13
        self.assertTrue(any('预算' in e for e in validate_plan(p)))

    def test_independent_original_constraints(self):
        p = fixture()
        self.assertEqual(validate_plan(p, expected_days=2, expected_daily_minutes=12), [])
        self.assertTrue(any('用户约定' in e for e in validate_plan(p, expected_days=5, expected_daily_minutes=10)))
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError): build(p, folder, expected_days=5)
            self.assertEqual(list(Path(folder).iterdir()), [])

    def test_gaps_duplicates_missing_content(self):
        for mutation in [lambda p: p['lessons'].pop(), lambda p: p['lessons'][1].update(day=1), lambda p: p['lessons'][1].update(id='day-1'), lambda p: p['lessons'][0].update(sections=[]), lambda p: p['lessons'][0].update(questions=[])]:
            p = fixture(); mutation(p)
            self.assertTrue(validate_plan(p))

    def test_answers_and_sources_must_be_consistent(self):
        for mutation in [lambda p: p['lessons'][0]['questions'][0].update(correct_index=True), lambda p: p['lessons'][0]['questions'][0].update(correct_index=2), lambda p: p['lessons'][0]['questions'][0].update(explanations=['only one']), lambda p: p['lessons'][0].update(source_ids=['missing']), lambda p: p['sources'][0].update(url='javascript:alert(1)')]:
            p = fixture(); mutation(p)
            self.assertTrue(validate_plan(p))

    def test_earlier_review_only(self):
        p = fixture(); p['lessons'][1]['review_of'] = [1]
        self.assertEqual(validate_plan(p), [])
        p['lessons'][0]['review_of'] = [2]
        self.assertTrue(validate_plan(p))

    def test_unsafe_types_do_not_crash_validation(self):
        p = fixture(); p['lessons'][0]['questions'][0]['options'] = None
        self.assertTrue(validate_plan(p))
        self.assertTrue(validate_plan({'course': None}))


class OutputTests(unittest.TestCase):
    def test_offline_html_embeds_data_and_guards_script_boundary(self):
        p = fixture()
        p['lessons'][0]['sections'][0]['body'] += '</script><script>alert(1)</script> {{SCRIPT}}'
        with tempfile.TemporaryDirectory() as folder:
            result = build(p, folder, calendar=True)
            html = Path(result['html']).read_text()
            self.assertNotIn('<script>alert(1)</script>', html)
            self.assertIn('\\u003c/script>', html)
            self.assertFalse(re.search(r'<script[^>]+src=', html))
            self.assertNotIn('@import', ''.join(re.findall(r'<style\b[^>]*>(.*?)</style>', html, re.S)))
            self.assertNotIn('fetch(', html)
            self.assertIn('第2天长度换算', html)
            self.assertFalse(result['calendar_events_created'])
            with self.assertRaises(ValueError):
                build(p, folder)
            build(p, folder, overwrite=True)

    def test_calendar_dates_duration_and_unique_stable_uids(self):
        p = fixture()
        a, b = make_ics(p), make_ics(p)
        self.assertEqual(a.count('BEGIN:VEVENT'), 2)
        self.assertIn('DTSTART:20261102T063000Z', a)
        self.assertIn('DTEND:20261102T064200Z', a)
        self.assertEqual(re.findall(r'UID:(.+)', a), re.findall(r'UID:(.+)', b))
        self.assertEqual(len(set(re.findall(r'UID:(.+)', a))), 2)
        self.assertNotIn('ATTENDEE', a)

    def test_calendar_explicit_nonconsecutive_dates(self):
        p = fixture(); p['course']['study_dates'] = ['2026-11-02', '2026-11-05']
        self.assertEqual(validate_plan(p), [])
        self.assertIn('DTSTART:20261105T063000Z', make_ics(p))

    def test_calendar_needs_time_and_handles_dst(self):
        p = fixture(); del p['course']['study_time']
        with self.assertRaises(ValueError): make_ics(p)
        for date, time in [('2026-03-08', '02:30'), ('2026-11-01', '01:30')]:
            p = fixture(); p['course'].update(timezone='America/New_York', start_date=date, study_time=time)
            with self.subTest(date=date), self.assertRaises(ValueError): make_ics(p)

    def test_utf8_calendar_line_folding(self):
        lines = fold_ics_line('DESCRIPTION:' + '中文内容,' * 60).split('\r\n')
        self.assertGreater(len(lines), 1)
        self.assertTrue(all(len(line.encode()) <= 75 for line in lines))
        self.assertEqual(''.join([lines[0]] + [line[1:] for line in lines[1:]]), 'DESCRIPTION:' + '中文内容,' * 60)

    def test_invalid_calendar_does_not_write_partial_files(self):
        p = fixture(); del p['course']['study_time']
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(ValueError): build(p, folder, calendar=True)
            self.assertEqual(list(Path(folder).iterdir()), [])

    def test_cli_in_another_working_directory(self):
        script = Path(__file__).with_name('build_learning_site.py').resolve()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'input.json'; path.write_text(json.dumps(fixture()))
            run = subprocess.run([sys.executable, '-B', str(script), '--plan', str(path), '--output', str(Path(folder) / 'output')], cwd=folder, text=True, capture_output=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertTrue(Path(json.loads(run.stdout)['html']).is_file())


if __name__ == '__main__':
    unittest.main()
