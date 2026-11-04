"""Synthetic risks with known expectations; never pretend to certify real teaching."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from lint_pedagogy import lint_pedagogy, plan_sha256
from test_workflow import fixture


def course(days=10, constant=False):
    data = fixture()
    data['course']['days'] = days
    template = data['lessons'][0]
    data['lessons'] = []
    for day in range(1, days + 1):
        lesson = copy.deepcopy(template)
        lesson.update(day=day, id='d-' + str(day), title='单位练习' + str(day))
        question = lesson['questions'][0]
        if day % 2 == 0 and not constant:
            question['options'].reverse()
            question['explanations'].reverse()
            question['correct_index'] = 1
        if day in [4, 8]:
            lesson['review_of'] = [max(1, day - 3)]
        data['lessons'].append(lesson)
    return data


def goal_map(data):
    return dict(plan_sha256=plan_sha256(data), goals=[dict(
        id='units', description='换算长度', core=True, taught_in=['d-1'], practiced_in=['d-1'],
        assessed_by=[dict(lesson_id='d-2', question_id='q1')], reviewed_in=['d-4'])])


def codes(report):
    return {issue['code'] for issue in report['issues']}


class PedagogyTests(unittest.TestCase):
    def test_short_course_is_not_forced_into_balance_or_maps(self):
        report = lint_pedagogy(fixture())
        self.assertTrue(report['passed'])
        self.assertFalse(report['facts_verified'])
        self.assertEqual(report['content_review_status'], 'not_performed')
        self.assertEqual(report['issues'], [])

    def test_all_same_answers_block_only_sufficient_same_arity_sample(self):
        data = course(constant=True)
        report = lint_pedagogy(data)
        self.assertFalse(report['passed'])
        issue = next(issue for issue in report['issues'] if issue['code'] == 'answer_position_constant')
        self.assertEqual(issue['severity'], 'error')
        self.assertTrue(lint_pedagogy(course(days=7, constant=True))['passed'])
        # Five 2-choice questions + five 3-choice questions do not form an 8-item group.
        for lesson in data['lessons'][5:]:
            lesson['questions'][0]['options'].append('另一个错误答案')
            lesson['questions'][0]['explanations'].append('没有保持实际长度。')
        self.assertNotIn('answer_position_constant', codes(lint_pedagogy(data)))

    def test_skew_and_runs_are_warnings_without_mechanical_rebalancing(self):
        data = course()
        for lesson in data['lessons'][:8]:
            question = lesson['questions'][0]
            if question['correct_index'] == 1:
                question['options'].reverse(); question['explanations'].reverse(); question['correct_index'] = 0
        report = lint_pedagogy(data)
        self.assertTrue(report['passed'])
        self.assertTrue({'answer_position_skew', 'answer_position_run'} <= codes(report))

    def test_late_review_and_missing_mapping_warn_on_long_course(self):
        data = course()
        for lesson in data['lessons']:
            lesson.pop('review_of', None)
        report = lint_pedagogy(data)
        self.assertTrue({'review_missing', 'goal_map_missing'} <= codes(report))
        data['lessons'][-1]['review_of'] = [1]
        self.assertIn('review_starts_late', codes(lint_pedagogy(data)))

    def test_goal_coverage_and_early_review_must_point_to_existing_content(self):
        data = course(); mapping = goal_map(data)
        self.assertTrue(lint_pedagogy(data, mapping)['passed'])
        for field in ['taught_in', 'practiced_in', 'assessed_by']:
            changed = copy.deepcopy(mapping); changed['goals'][0][field] = []
            self.assertFalse(lint_pedagogy(data, changed)['passed'])
        changed = copy.deepcopy(mapping); changed['goals'][0]['reviewed_in'] = ['d-10']
        self.assertIn('goal_review_late', codes(lint_pedagogy(data, changed)))
        changed = copy.deepcopy(mapping); changed['goals'][0]['reviewed_in'] = []
        self.assertIn('goal_review_missing', codes(lint_pedagogy(data, changed)))
        changed = copy.deepcopy(mapping); changed['goals'][0]['assessed_by'][0]['question_id'] = 'not-a-question'
        self.assertIn('goal_reference_invalid', codes(lint_pedagogy(data, changed)))

    def test_mapping_cannot_claim_missing_practice_or_use_outdated_course(self):
        data = course(); mapping = goal_map(data)
        data['lessons'][0].pop('practice')
        self.assertIn('goal_map_invalid', codes(lint_pedagogy(data, mapping)))
        mapping['plan_sha256'] = plan_sha256(data)
        self.assertIn('goal_practice_missing', codes(lint_pedagogy(data, mapping)))

    def test_missing_answer_remains_structure_error(self):
        data = course(); del data['lessons'][0]['questions'][0]['correct_index']
        report = lint_pedagogy(data)
        self.assertFalse(report['passed'])
        self.assertIn('structure_invalid', codes(report))

    def test_diagram_and_inline_math_are_risks_not_automatic_fact_errors(self):
        data = fixture()
        data['lessons'][0]['sections'][0]['body'] += r' 在坐标中画出曲线，公式为 \frac{a}{b}。'
        report = lint_pedagogy(data)
        self.assertTrue(report['passed'])
        self.assertTrue({'diagram_need_review', 'inline_math_review'} <= codes(report))
        plain = fixture(); plain['lessons'][0]['sections'][0]['body'] += ' v = s/t。'
        self.assertNotIn('diagram_need_review', codes(lint_pedagogy(plain)))

    def test_unknown_label_and_possible_placeholder_are_warnings(self):
        data = fixture()
        data['lessons'][0]['activities'][0]['kind'] = 'memorize'
        data['lessons'][0]['sections'][0]['body'] += ' 后续补充另一个例题。'
        report = lint_pedagogy(data)
        self.assertTrue(report['passed'])
        self.assertTrue({'activity_label_unknown', 'possible_placeholder'} <= codes(report))

    def test_complete_mastery_claim_short_budget_requires_scope_review(self):
        data = course(); data['course']['goal'] = '掌握完整基础微积分'
        report = lint_pedagogy(data)
        self.assertFalse(report['passed'])
        self.assertIn('scope_budget_overclaim', codes(report))
        data['course']['goal'] = '认识差商含义并计算两个线性函数的斜率'
        self.assertNotIn('scope_budget_overclaim', codes(lint_pedagogy(data)))
        data['course']['goal'] = '掌握完整基础微积分'
        self.assertNotIn('scope_budget_overclaim', codes(lint_pedagogy(data, scope_review_hours=1)))

    def test_obvious_negated_exclusions_do_not_suppress_separate_promises(self):
        data = course()
        for negation in ['不含', '不包括', '不承诺', '不涉及', '不要求', '并非']:
            data['course']['goal'] = '计算线性函数斜率，' + negation + '完整微积分或证明掌握承诺'
            self.assertNotIn('goal_scope_review', codes(lint_pedagogy(data)))
            data['course']['goal'] += '。同时掌握完整基础微积分。'
            self.assertIn('scope_budget_overclaim', codes(lint_pedagogy(data)))
        data['course']['goal'] = '不包括证明但掌握完整微积分'
        self.assertIn('scope_budget_overclaim', codes(lint_pedagogy(data)))

    def test_review_is_bound_to_exact_risk_location_and_course(self):
        data = course(constant=True); report = lint_pedagogy(data)
        issue = next(i for i in report['issues'] if i['code'] == 'answer_position_constant')
        review = dict(plan_sha256=plan_sha256(data), resolutions=[dict(
            code=issue['code'], location=issue['location'], rationale='固定题库按外部考试顺序保留，已逐题核对。',
            evidence=['review/fixed-bank.md#q1-q10'])])
        checked = lint_pedagogy(data, review=review)
        self.assertTrue(checked['passed'])
        self.assertFalse(checked['facts_verified'])
        self.assertTrue(next(i for i in checked['issues'] if i['code'] == issue['code'])['reviewed'])
        for mutation in [lambda r: r.update(plan_sha256='old'),
                         lambda r: r['resolutions'][0].update(location='*'),
                         lambda r: r['resolutions'][0].update(evidence=[]),
                         lambda r: r['resolutions'].append(copy.deepcopy(r['resolutions'][0]))]:
            changed = copy.deepcopy(review); mutation(changed)
            self.assertFalse(lint_pedagogy(data, review=changed)['passed'])

    def test_semantic_formula_and_graph_errors_need_external_review(self):
        data = fixture()
        data['lessons'][0]['sections'][0]['body'] = '三角形的面积是底乘高。图中边长100厘米的正方形被标为100平方厘米。'
        # These facts are deliberately false. A text heuristic cannot certify them.
        report = lint_pedagogy(data)
        self.assertTrue(report['passed'])
        self.assertFalse(report['facts_verified'])
        review = dict(plan_sha256=plan_sha256(data), content_findings=[dict(
            kind='formula', location='$.lessons[0].sections[0].body', status='open',
            message='三角形面积缺少二分之一；底4高3的独立复算应得6，课文公式得12。',
            evidence=['review/area.md#triangle-4x3']), dict(
            kind='diagram', location='$.lessons[0].sections[0].body', status='open',
            message='100 cm × 100 cm = 10000 cm²，标签100 cm²与边长冲突。',
            evidence=['review/area.md#square-100x100'])])
        report = lint_pedagogy(data, review=review)
        self.assertFalse(report['passed'])
        self.assertEqual(sum(i['code'] == 'confirmed_content_defect' for i in report['issues']), 2)
        review['resolutions'] = [dict(code='confirmed_content_defect', location='$.lessons[0].sections[0].body',
                                      rationale='忽略', evidence=['anything'])]
        self.assertFalse(lint_pedagogy(data, review=review)['passed'])

    def test_hash_ignores_whitespace_and_object_key_order_but_not_content(self):
        data = fixture()
        self.assertEqual(plan_sha256(data), plan_sha256(json.loads(json.dumps(data, sort_keys=True))))
        changed = copy.deepcopy(data); changed['lessons'][0]['title'] += '修订'
        self.assertNotEqual(plan_sha256(data), plan_sha256(changed))

    def test_cli_returns_blocked_status_and_writes_complete_report(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); (root / 'plan.json').write_text(json.dumps(course(constant=True)), encoding='utf-8')
            run = subprocess.run([sys.executable, '-B', str(Path(__file__).with_name('lint_pedagogy.py')),
                                  str(root / 'plan.json'), '--output', str(root / 'report.json')],
                                 capture_output=True, text=True)
            self.assertEqual(run.returncode, 2, run.stderr)
            self.assertFalse(json.loads((root / 'report.json').read_text(encoding='utf-8'))['passed'])

    def test_invalid_mappings_and_thresholds_fail_cleanly(self):
        data = course()
        for field in ['taught_in', 'practiced_in', 'reviewed_in']:
            mapping = goal_map(data); mapping['goals'][0][field] = [{}]
            self.assertFalse(lint_pedagogy(data, mapping)['passed'])
        for threshold in [0, 1, True]:
            with self.assertRaises(ValueError): lint_pedagogy(data, min_questions=threshold)


if __name__ == '__main__':
    unittest.main()
