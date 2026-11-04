"""Budget provenance and complete-delivery behavior, using small synthetic tasks."""
import copy
from fractions import Fraction
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from assess_budget import assess_budget
from budget_evidence import check_budget_record, evaluate_estimate, fingerprint
from test_workflow import fixture


def estimate_fixture(plan=None):
    plan = plan or fixture()
    return {
        'schema_version': 1,
        'constraints': {'days': plan['course']['days'], 'daily_minutes': plan['course']['daily_minutes']},
        'original_goal': plan['course']['goal'], 'selected_goal': plan['course']['goal'],
        'background': plan['course']['background'],
        'scope': {'mode': 'full', 'excluded': []},
        'prerequisite_basis': 'Synthetic task assumes elementary division; not a learner timing claim.',
        'prerequisites': [{'skill': 'division', 'status': 'assumed', 'evidence': 'fixture assumption'}],
        'buffer_percent': 15, 'buffer_reason': 'Extra reserve, separate from scheduled review and feedback.',
        'goals': [{'id': 'units', 'outcome': '理解单位比例', 'source_ids': ['raw'],
                   'basis': 'Given relation 1 m = 1000 mm; one worked example and two concrete conversions.',
                   'tasks': [{'kind': kind, 'count': 1, 'minutes_low': 1, 'minutes_high': 2,
                              'description': kind + ' for length conversion',
                              'basis': 'One synthetic small task; estimated, not measured.'}
                             for kind in ('learn', 'example', 'practice', 'feedback', 'review', 'quiz')]}]
    }


def goal_map_fixture(plan=None):
    plan = plan or fixture()
    return {'plan_sha256': fingerprint(plan), 'goals': [{
        'id': 'units', 'description': '理解单位比例', 'core': True,
        'taught_in': ['day-1'], 'practiced_in': ['day-1'],
        'assessed_by': [{'lesson_id': 'day-1', 'question_id': 'q1'}], 'reviewed_in': ['day-2']
    }]}


class EvidenceTests(unittest.TestCase):
    def test_counts_and_bound_provenance(self):
        p, e = fixture(), estimate_fixture()
        e['goals'][0]['tasks'][0]['count'] = 2
        b = evaluate_estimate(e, 2, 12, p)
        self.assertEqual(b['estimated_minutes'], {'low': 7.0, 'high': 14.0})
        self.assertEqual(b['plan_sha256'], fingerprint(p))
        self.assertEqual(b['status'], 'fits')
        self.assertEqual(check_budget_record(p, e, b, 2, 12), b)
        self.assertFalse(b['evidence_truth_verified'])

    def test_exact_minute_boundary_does_not_round_into_wrong_status(self):
        b = assess_budget(1, 7, Fraction(7, 60), Fraction(7, 60), 0)
        self.assertEqual(b['status'], 'fits')
        self.assertEqual(b['recommended_total_days_range']['high'], 1)
        json.dumps(b, allow_nan=False)

    def test_independent_constraints_and_goal_binding(self):
        for mutate in (lambda e: e['constraints'].update(days=3),
                       lambda e: e.update(selected_goal='Different scope'),
                       lambda e: e.update(background='Already expert')):
            e = estimate_fixture(); mutate(e)
            with self.subTest(e=e), self.assertRaises(ValueError): evaluate_estimate(e, 2, 12, fixture())

    def test_stale_modified_and_unbound_records_rejected(self):
        p, e = fixture(), estimate_fixture()
        b = evaluate_estimate(e, 2, 12, p)
        for mutate in (lambda p, e, b: p['lessons'][0]['sections'][0].update(body='Revised teaching'),
                       lambda p, e, b: e['goals'][0]['tasks'][0].update(count=2),
                       lambda p, e, b: b.update(status='insufficient'),
                       lambda p, e, b: b.update(plan_sha256=None),
                       lambda p, e, b: b.update(evidence_truth_verified=0)):
            pp, ee, bb = copy.deepcopy((p, e, b)); mutate(pp, ee, bb)
            with self.subTest(mutation=mutate), self.assertRaises(ValueError):
                check_budget_record(pp, ee, bb, 2, 12)
        pre_authoring = evaluate_estimate(e, 2, 12)
        with self.assertRaises(ValueError): check_budget_record(p, e, pre_authoring, 2, 12)

    def test_evidence_and_task_categories_cannot_be_omitted(self):
        for mutate in (lambda e: e.update(buffer_reason=''),
                       lambda e: e.update(prerequisite_basis=''),
                       lambda e: e['goals'][0].update(basis=''),
                       lambda e: e['goals'][0].update(source_ids=['unknown']),
                       lambda e: e['goals'][0]['tasks'].pop(),
                       lambda e: e['goals'][0]['tasks'][0].update(count=True),
                       lambda e: e['goals'][0]['tasks'][0].update(minutes_low=0)):
            e = estimate_fixture(); mutate(e)
            with self.subTest(mutation=mutate), self.assertRaises(ValueError): evaluate_estimate(e, 2, 12, fixture())

    def test_borderline_requires_explicit_core_boundary_insufficient_stops(self):
        p, e = fixture(), estimate_fixture()
        e['buffer_percent'] = 0
        for task in e['goals'][0]['tasks']: task['minutes_high'] = 5
        b = evaluate_estimate(e, 2, 12, p)
        self.assertEqual(b['status'], 'borderline')
        with self.assertRaisesRegex(ValueError, 'borderline'): check_budget_record(p, e, b, 2, 12)
        e['original_goal'] = 'Convert length, area and rates'
        e['scope'] = {'mode': 'core', 'excluded': ['area', 'rates'], 'change_basis': 'Explicit synthetic core-first evaluation input'}
        b = evaluate_estimate(e, 2, 12, p)
        self.assertEqual(check_budget_record(p, e, b, 2, 12)['status'], 'borderline')
        for task in e['goals'][0]['tasks']: task['minutes_low'] = 5
        b = evaluate_estimate(e, 2, 12, p)
        self.assertEqual(b['status'], 'insufficient')
        with self.assertRaisesRegex(ValueError, 'insufficient'): check_budget_record(p, e, b, 2, 12)

    def test_cli_pre_authoring_does_not_require_plan_or_destroy_estimate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); path = root / 'estimate.json'
            path.write_text(json.dumps(estimate_fixture()), encoding='utf-8')
            command = [sys.executable, '-B', str(Path(__file__).with_name('budget_evidence.py')),
                       '--estimate', str(path), '--output', str(root / 'budget.json'),
                       '--expected-days', '2', '--expected-daily-minutes', '12']
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(json.loads(result.stdout)['plan_bound'])
            command[command.index(str(root / 'budget.json'))] = str(path)
            self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)
            self.assertEqual(json.loads(path.read_text()), estimate_fixture())


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        from build_course import build_course
        self.build_course = build_course
        self.plan, self.estimate = fixture(), estimate_fixture()
        self.budget = evaluate_estimate(self.estimate, 2, 12, self.plan)
        self.goal_map = goal_map_fixture()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name) / 'output'

    def build(self, **kwargs):
        return self.build_course(self.plan, self.estimate, self.budget, self.goal_map,
                                 self.output, 2, 12, **kwargs)

    def test_valid_scoped_delivery_keeps_reports_and_legacy_builder(self):
        result = self.build()
        self.assertTrue(result['budget_arithmetic_verified'])
        self.assertFalse(result['facts_verified'])
        self.assertEqual(result['time_feasibility'], 'estimated')
        self.assertEqual(result['delivery_status'], 'generated_pending_content_review')
        for name in ('index.html', 'plan.json', 'estimate.json', 'budget.json', 'goal-map.json',
                     'pedagogy-report.json', 'delivery-report.json'):
            self.assertTrue((self.output / name).is_file(), name)
        from build_learning_site import build
        self.assertEqual(build(self.plan, Path(self.temp.name) / 'legacy')['delivery_status'], 'structure_only')

    def test_gate_failures_do_not_write_partial_course(self):
        self.budget['status'] = 'fits-but-forged'
        with self.assertRaises(ValueError): self.build()
        self.assertFalse(self.output.exists())
        self.budget = evaluate_estimate(self.estimate, 2, 12, self.plan)
        self.goal_map['goals'] = []
        with self.assertRaises(ValueError): self.build()
        self.assertFalse(self.output.exists())

    def test_silent_goal_removal_and_unresolved_quality_blockers_fail(self):
        self.goal_map['goals'][0]['assessed_by'] = []
        with self.assertRaises(ValueError): self.build()
        self.assertFalse(self.output.exists())

    def test_existing_report_protected_before_building_html(self):
        self.output.mkdir()
        (self.output / 'delivery-report.json').write_text('keep', encoding='utf-8')
        with self.assertRaises(ValueError): self.build()
        self.assertFalse((self.output / 'index.html').exists())

    def test_nonfinite_metadata_is_rejected_before_any_course_output(self):
        self.goal_map['extra'] = float('nan')
        with self.assertRaises(ValueError): self.build()
        self.assertFalse(self.output.exists())

    def test_valid_structure_does_not_claim_semantic_completeness(self):
        self.plan['lessons'][0]['sections'][0]['body'] = '这一课会介绍单位换算。'
        self.budget = evaluate_estimate(self.estimate, 2, 12, self.plan)
        self.goal_map = goal_map_fixture(self.plan)
        result = self.build()
        self.assertEqual(result['delivery_status'], 'generated_pending_content_review')
        self.assertFalse(result['facts_verified'])
        self.assertEqual(result['content_review_status'], 'not_performed')


if __name__ == '__main__':
    unittest.main()
