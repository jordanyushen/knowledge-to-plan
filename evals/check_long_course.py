#!/usr/bin/env python3
"""Recheck one frozen, authored long-course fixture, never certify new courses.

The trusted oracle consumes hand-written rational polynomial data. It does not
parse or execute code from generated lessons, use eval/exec, or call a model.
Source meaning and teaching effectiveness remain separate review questions.
"""
import argparse
import copy
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'knowledge-to-plan' / 'scripts'))
from budget_evidence import check_budget_record, fingerprint
from build_course import build_course
from lint_pedagogy import lint_pedagogy
from merge_plan import merge_plan


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def value(coefficients, x):
    return sum((coefficient * x ** power for power, coefficient in enumerate(coefficients)), Fraction(0))


def derivative(coefficients):
    return [power * coefficient for power, coefficient in enumerate(coefficients) if power]


def integral(coefficients, start, end):
    return sum((coefficient * (end ** (power + 1) - start ** (power + 1)) / (power + 1)
                for power, coefficient in enumerate(coefficients)), Fraction(0))


def same_sign(coefficients, start, end):
    """Verify sign on each split interval, including a quadratic's vertex."""
    points = [start, end]
    if len(coefficients) == 3 and coefficients[2]:
        vertex = -coefficients[1] / (2 * coefficients[2])
        if start < vertex < end:
            points.append(vertex)
    results = [value(coefficients, point) for point in points]
    return min(results) >= 0 or max(results) <= 0


def calculate(record):
    coefficients = [Fraction(item) for item in record['coefficients']]
    kind = record['kind']
    if kind == 'value':
        return value(coefficients, Fraction(record['x']))
    if kind == 'derivative':
        return value(derivative(coefficients), Fraction(record['x']))
    start, end = Fraction(record['a']), Fraction(record['b'])
    if kind == 'delta':
        return value(coefficients, end) - value(coefficients, start)
    if kind == 'average':
        if start == end:
            raise ValueError('average-rate oracle cannot divide by a zero input change')
        return (value(coefficients, end) - value(coefficients, start)) / (end - start)
    if kind == 'integral':
        return integral(coefficients, start, end)
    if kind == 'absolute_integral':
        points = [start] + [Fraction(item) for item in record['splits']] + [end]
        if points != sorted(set(points)):
            raise ValueError('total-area oracle needs increasing, unique split points')
        if not all(same_sign(coefficients, a, b) for a, b in zip(points, points[1:])):
            raise ValueError('area interval crosses an unrecorded zero')
        return sum((abs(integral(coefficients, a, b)) for a, b in zip(points, points[1:])), Fraction(0))
    raise ValueError('unknown trusted oracle operation: ' + kind)


def numeric_option(text):
    return Fraction(text.replace('−', '-').replace(' ', ''))


def diagram_checks(plan, reference):
    checked = 0
    for record in reference['diagrams']:
        section = plan['lessons'][record['day'] - 1]['sections'][0]
        drawing = ET.fromstring(section['diagrams'][0]['svg'])
        elements = {element.get('id'): element for element in drawing.iter() if element.get('id')}
        x_origin, y_origin = Fraction(record['x_origin']), Fraction(record['y_origin'])
        x_scale, y_scale = Fraction(record['x_scale']), Fraction(record['y_scale'])

        def logical(px, py):
            return (Fraction(px) - x_origin) / x_scale, (y_origin - Fraction(py)) / y_scale

        if record['kind'] == 'secant':
            points = []
            for point in record['points']:
                element = elements[point['id']]
                x, y = logical(element.get('cx'), element.get('cy'))
                assert (x, y) == (Fraction(point['x']), Fraction(point['y'])), 'secant point coordinates'
                assert y == x * x, 'secant point must lie on y=x²'
                points.append((x, y)); checked += 2
            line = elements[record['line_id']]
            endpoints = [logical(line.get('x' + str(i)), line.get('y' + str(i))) for i in [1, 2]]
            assert endpoints == points, 'secant line must join the labelled points'
            assert (points[1][1] - points[0][1]) / (points[1][0] - points[0][0]) == Fraction(record['slope']), 'secant slope'
            # This path is an exact quadratic Bezier representation: x=4t,
            # y=16t². Its control points are author-reviewed fixed geometry.
            path = next(element for element in drawing.iter() if element.tag.endswith('}path'))
            assert path.get('d') == 'M 50 250 Q 170 250 290 10', 'quadratic path geometry changed'
            checked += 3
        elif record['kind'] == 'signed_area':
            line = elements[record['graph_id']]
            for i in [1, 2]:
                x, y = logical(line.get('x' + str(i)), line.get('y' + str(i)))
                assert y == x and abs(x) == 1, 'signed-area graph endpoints'
                checked += 1
            for name, sign in [(record['negative_region'], -1), (record['positive_region'], 1)]:
                polygon = elements[name]
                points = [logical(*pair.split(',')) for pair in polygon.get('points').split()]
                double_area = sum((x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(points, points[1:] + points[:1])), Fraction(0))
                assert abs(double_area) / 2 == Fraction(record['each_triangle_area']), 'triangle area'
                assert all(sign * y >= 0 for x, y in points), 'triangle must be on declared side of axis'
                checked += 2
        else:
            raise ValueError('unrecognized diagram oracle')
    return checked


def negative_controls(plan, mapping, reference):
    """Separate mechanical risk finding from trusted content-defect finding."""
    all_a = copy.deepcopy(plan)
    for lesson in all_a['lessons']:
        question = lesson['questions'][0]
        index = question['correct_index']
        for field in ('options', 'explanations'):
            question[field].insert(0, question[field].pop(index))
        question['correct_index'] = 0
    result = lint_pedagogy(all_a)
    assert not result['passed'] and any(item['code'] == 'answer_position_constant' for item in result['issues']), 'all-A control escaped'

    late = copy.deepcopy(plan)
    for lesson in late['lessons']:
        lesson.pop('review_of', None)
    late['lessons'][-1]['review_of'] = [1]
    result = lint_pedagogy(late)
    assert any(item['code'] == 'review_starts_late' for item in result['issues']), 'late-review control escaped'

    missing = copy.deepcopy(mapping)
    missing['goals'][0]['taught_in'] = []
    result = lint_pedagogy(plan, missing)
    assert not result['passed'] and any(item['code'] == 'goal_coverage_missing' for item in result['issues']), 'missing-goal control escaped'

    wrong_formula = copy.deepcopy(plan)
    wrong_formula['lessons'][13]['sections'][0]['formulas'][0]['expression'] = 'F(x) = x³/2'
    # A semantic reviewer, not the linter's regex, identifies this defect:
    # derivative(x³/2) = 3x²/2, which differs from the required x².
    assert derivative([Fraction(0), Fraction(0), Fraction(0), Fraction(1, 2)]) != [Fraction(0), Fraction(0), Fraction(1)]
    review = {'plan_sha256': fingerprint(wrong_formula), 'content_findings': [
        {'kind': 'formula', 'location': '$.lessons[13].sections[0].formulas[0]',
         'message': 'Inserted x³/2 is not an antiderivative of x².',
         'status': 'open', 'evidence': ['Exact polynomial derivative gives 3x²/2, not x²; OpenStax 5.3 power antiderivative rule.']}], 'resolutions': []}
    result = lint_pedagogy(wrong_formula, review=review)
    assert not result['passed'] and any(item['code'] == 'confirmed_content_defect' and not item['waivable'] for item in result['issues']), 'confirmed formula defect escaped'

    wrong_diagram = copy.deepcopy(plan)
    image = wrong_diagram['lessons'][1]['sections'][0]['diagrams'][0]
    image['svg'] = image['svg'].replace('cy="115"', 'cy="130"')
    try:
        diagram_checks(wrong_diagram, reference)
    except AssertionError:
        pass
    else:
        raise AssertionError('inconsistent SVG point escaped trusted geometry check')
    return 5


def check_fixture(folder):
    if not __debug__:
        raise ValueError('run checks without Python -O; oracle assertions must remain enabled')
    manifest = read(folder / 'frozen-files.json')
    for relative, digest in manifest['files'].items():
        path = (folder / relative).resolve()
        if folder.resolve() not in path.parents:
            raise ValueError('fixture manifest path escaped the fixture')
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError(relative + ' differs from the reviewed authored fixture; re-review before updating records')
    plan, merged = merge_plan(folder, 21, 30)
    reference = read(folder / 'reference.json')
    assert fingerprint(plan) == reference['plan_sha256'], 'reference is bound to a different plan'
    assert merged['batches'] == 5 and len(plan['lessons']) == 21, 'long-course batch coverage'
    estimate, budget = read(folder / 'estimate.json'), read(folder / 'budget.json')
    assessment = check_budget_record(plan, estimate, budget, 21, 30)
    mapping = read(folder / 'goal-map.json')
    assert {item['id']: item['description'] for item in mapping['goals']} == {item['id']: item['outcome'] for item in estimate['goals']}, 'estimate goals and coverage must agree'
    lint = lint_pedagogy(plan, mapping, read(folder / 'review.json'))
    assert lint['passed'], json.dumps(lint, ensure_ascii=False)
    assert all(item['reviewed'] for item in lint['issues']), 'fixture has unresolved heuristic risks'
    for lesson in plan['lessons']:
        assert sum(activity['minutes'] for activity in lesson['activities']) == 24, 'scheduled work must leave explicit reserve'

    question_days, example_days, practice_days = set(), set(), set()
    checked = 0
    for record in reference['checks']:
        answer = calculate(record)
        assert answer == Fraction(record['expected']), record['location'] + ' reference arithmetic mismatch'
        day = int(record['location'].split('[', 1)[1].split(']', 1)[0]) + 1
        if record['category'] == 'question':
            question = plan['lessons'][day - 1]['questions'][0]
            results = [numeric_option(option) for option in question['options']]
            assert results.count(answer) == 1 and results[question['correct_index']] == answer, record['location'] + ' answer not unique or correct'
            assert len(question['explanations']) == len(results), 'each choice must have an explanation'
            question_days.add(day)
        elif record['category'] == 'example':
            example_days.add(day)
        elif record['category'] == 'practice':
            practice_days.add(day)
        else:
            raise ValueError('unrecognized calculation category')
        checked += 1
    assert question_days == example_days == practice_days == set(range(1, 22)), 'all 21 lessons need question, example and practice oracles'
    # Algebraic identities supporting the generic formulas, independently of
    # lesson prose. The source meaning/conditions are recorded in the review.
    for a, b, c in [(2, 3, 1), (-1, 4, -2), (0, -3, 5)]:
        assert derivative([Fraction(c), Fraction(b), Fraction(a)]) == [Fraction(b), Fraction(2 * a)]
        checked += 1
    assert derivative([Fraction(0), Fraction(0), Fraction(0), Fraction(1, 3)]) == [Fraction(0), Fraction(0), Fraction(1)], 'given primitive x³/3'
    checked += 1
    for entry in reference['formulas']:
        block = plan['lessons'][entry['day'] - 1]['sections'][0]['formulas'][0]
        assert block['expression'] == entry['expression'], 'reviewed generic relation changed'
        checked += 1
    geometry = diagram_checks(plan, reference)
    controls = negative_controls(plan, mapping, reference)
    with tempfile.TemporaryDirectory(prefix='ktp-long-course-check-') as directory:
        delivery = build_course(plan, estimate, budget, mapping, Path(directory), 21, 30,
                                review=read(folder / 'review.json'))
        assert Path(delivery['html']).is_file(), 'complete-course gate must produce an offline HTML'
        assert read(Path(directory) / 'plan.json') == plan, 'delivery cannot rewrite lesson content'
        assert delivery['delivery_status'] == 'generated_pending_content_review', 'program must not certify semantic completeness'
        stored = read(Path(directory) / 'delivery-report.json')
        assert stored['facts_verified'] is False and stored['learner_trial'] == 'not_recorded', 'stored report must not invent fact or learner certification'
        assert stored['time_feasibility'] == 'estimated', 'stored report must preserve timing uncertainty'
        for filename, expected in [('estimate.json', estimate), ('budget.json', budget), ('goal-map.json', mapping), ('review.json', read(folder / 'review.json'))]:
            assert read(Path(directory) / filename) == expected, filename + ' must accompany the offline course without mutation'
    return {'passed': True, 'fixture': 'authored_synthetic_tool_evaluation', 'lessons': 21,
            'batches': merged['batches'], 'scored_questions': len(question_days),
            'rational_and_formula_checks': checked, 'geometry_checks': geometry,
            'negative_controls': controls, 'complete_course_gate': 'passed_in_temporary_directory',
            'budget_status': assessment['status'], 'estimated_minutes': assessment['estimated_minutes'],
            'pedagogy_risks': len(lint['issues']), 'all_risks_reviewed': True,
            'facts_verified': False, 'learner_trial': 'not_performed', 'time_feasibility': 'estimated'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixture', type=Path, default=ROOT / 'evals' / 'long-course')
    args = parser.parse_args()
    try:
        result = check_fixture(args.fixture)
        print(json.dumps(result, ensure_ascii=False))
    except (AssertionError, KeyError, OSError, TypeError, ValueError, ZeroDivisionError) as error:
        print(json.dumps({'passed': False, 'error': str(error)}, ensure_ascii=False), file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
