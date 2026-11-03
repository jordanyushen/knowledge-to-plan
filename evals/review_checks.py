#!/usr/bin/env python3
"""Handwritten checks for four frozen course samples; never execute course text.

This is a finite calculation record, not a factual validator for arbitrary courses.
All operations below were independently transcribed by the reviewing agent.
Run with no arguments after archiving the four runs, or repeat --run ID=PATH.
"""
import argparse
from fractions import Fraction as F
import hashlib
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
FROZEN = {
    'python-lists-run-1': '72b0b196d53a8035d8714756fbcefe9391f7a899ef2855d1d0b99ed8d5e3885d',
    'python-lists-run-2': 'c652c349221aa9f4d018502ddaed2dfc46ff1d0abf8db304b5c344d02041a4d7',
    'si-basics-run-1': '3bc76a3c958414f1d4e560a142ec02730b939ddfc9b60145044bb957cd1ce3fc',
    'si-basics-run-2': 'efdb9816a18c7e64fe5351aa795cf80c398500a48a559987badc5e340a9fa684',
}
RECORDS = []
PLANS = {}


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def check(name, actual, expected):
    require(actual == expected, name + ': ' + repr(actual) + ' != ' + repr(expected))
    RECORDS.append({'check': name, 'observed': actual, 'expected': expected, 'matches': True})


def question(run, number, observed, normalized_options):
    """Options were normalized by the reviewer, not parsed/executed from JSON."""
    lesson = PLANS[run]['lessons'][(number - 1) // 3]
    q = lesson['questions'][(number - 1) % 3]
    matches = [i for i, option in enumerate(normalized_options) if option == observed]
    check(run + ':Q' + str(number) + ':unique-correct-index', matches, [q['correct_index']])
    require(len(normalized_options) == len(q['options']), 'Reviewer option count differs')
    RECORDS[-1]['observed_result'] = observed
    RECORDS[-1]['correct_option_text'] = q['options'][q['correct_index']]


def python_run_one():
    r = 'python-lists-run-1'
    a = [11, 22, 33, 44]
    question(r, 1, (a[0], a[-2]), [(22, 44), (11, 33), (11, 22), ([11], [33])])
    question(r, 2, a[1:3], [[11, 22, 33], [22, 33, 44], [22, 33], 22])
    try:
        a[9]
        failure = None
    except IndexError:
        failure = 'IndexError'
    question(r, 3, (a[9:12], failure), [([], 'IndexError'), ([], []), (44, 44), ('IndexError', [])])
    a = [1]; a.append([2, 3]); b = [1]; b.extend([2, 3])
    question(r, 4, (a, b), [([1, 2, 3], [1, 2, 3]), ([1, [2, 3]], [1, [2, 3]]),
                            ([1, 2, 3], [1, [2, 3]]), ([1, [2, 3]], [1, 2, 3])])
    a = [5, 9, 2]; x = a.pop(1)
    question(r, 5, (x, a), [(2, [5, 9]), (9, [5, 2]), (1, [5, 9, 2]), (None, [5, 2])])
    a = [4, 1, 3]; value = a.sort()
    question(r, 6, (a, value), [([4, 1, 3], [1, 3, 4]), ([1, 3, 4], [1, 3, 4]),
                                ([1, 3, 4], None), (None, [1, 3, 4])])
    a = [6, 2]; b = a; c = a.copy(); b.append(4); c.sort()
    question(r, 7, (a, b, c), [([6, 2, 4], [6, 2, 4], [2, 6]),
                                ([6, 2], [6, 2, 4], [2, 6]),
                                ([2, 4, 6], [2, 4, 6], [2, 4, 6]),
                                ([6, 2, 4], [6, 2, 4], None)])
    a = [[3], 8]; c = a.copy(); c[0].append(4); c.append(9)
    question(r, 8, a, [[[3], 8], [[3, 4], 8, 9], [[3, 4], 8], [3, 4, 8]])
    a = [9, 1]; b = a; b = [7]; b.append(2)
    question(r, 9, (a, b), [([7, 2], [7, 2]), ([9, 1, 2], [7, 2]),
                            ([9, 1], [7]), ([9, 1], [7, 2])])
    n = [7, 14, 21, 28, 35]
    check(r + ':practice1', (n[-1], n[1:4], n[:2], n[4:99], n[::2], n[::-1]),
          (35, [14, 21, 28], [7, 14], [35], [7, 21, 35], [35, 28, 21, 14, 7]))
    a = [6, 2]; a.append(4); a.extend([1, 5]); removed = a.pop(1); before = a[:]; result = a.sort()
    check(r + ':practice2', (removed, before, a, result), (2, [6, 4, 1, 5], [1, 4, 5, 6], None))
    a = [7, 2, 5]; alias = a; saved = a[:]; alias.append(1); a.sort(); x = a.pop(0)
    check(r + ':practice3', (x, a, alias, saved[1:]), (1, [2, 5, 7], [2, 5, 7], [2, 5]))
    a = [7, 2, 5]; saved = a; a.append(1); a.sort(); a.pop(0)
    check(r + ':practice3-variant', saved[1:], [5, 7])
    v = [12, 24, 36, 48, 60]
    check(r + ':lesson1-examples', (v[0], v[-2], v[1:4], v[:1], v[-3:-1], v[::2], v[::-1], v),
          (12, 48, [24, 36, 48], [12], [36, 48], [12, 36, 60], [60, 48, 36, 24, 12], [12, 24, 36, 48, 60]))
    a = [9, 3, 6]; last = a.pop(); middle = a[:]; first = a.pop(0)
    check(r + ':pop-example', (last, middle, first, a), (6, [9, 3], 9, [3]))
    a = [3, 1]; b = a; b.append(2); b.sort()
    check(r + ':alias-example', (a, b), ([1, 2, 3], [1, 2, 3]))
    a = [3, 1]; c = a.copy(); d = a[:]; c.sort(); d[0] = 8
    check(r + ':copy-example', (a, c, d), ([3, 1], [1, 3], [8, 1]))
    a = [[5], 9]; c = a.copy(); c[0].append(6); c.append(7)
    check(r + ':nested-example', (a, c), ([[5, 6], 9], [[5, 6], 9, 7]))
    a = [4, 2]; b = a; b = [7]
    check(r + ':rebind-example', (a, b), ([4, 2], [7]))


def python_run_two():
    r = 'python-lists-run-2'
    a = [10, 20, 30, 40]
    question(r, 1, (a[-2], len(a)), [(20, 3), (40, 4), (30, 4), (30, 3)])
    question(r, 2, a[1:3], [[20, 30], [20, 30, 40], [10, 20, 30], 20])
    try:
        value = a[4]
    except IndexError:
        value = 'IndexError'
    # Normalize the truth of each independently run statement.
    question(r, 3, True, [value == 40, a[2:99] == 'IndexError', a[3:1] == [40, 30, 20], a[4:99] == []])
    a = [1]; b = [1]; a.append([2, 3]); b.extend([2, 3])
    question(r, 4, (a, b), [([1, 2, 3], [1, [2, 3]]), ([1, [2, 3]], [1, 2, 3]),
                            ([1, 2, 3], [1, 2, 3]), ([1, [2, 3]], [1, [2, 3]])])
    a = [4, 8, 12]; x = a.pop(1)
    question(r, 5, (x, a), [(4, [8, 12]), (8, [4, 8, 12]), (None, [4, 12]), (8, [4, 12])])
    a = [3]; result = a.append(7)
    question(r, 6, (result, a), [(None, [3, 7]), ([3, 7], [3, 7]), (7, [3]), (None, [3])])
    a = [3, 1, 2]; b = a; c = a.copy(); result = a.sort()
    question(r, 7, (b, c, result), [([3, 1, 2], [3, 1, 2], [1, 2, 3]),
                                    ([1, 2, 3], [1, 2, 3], None),
                                    ([1, 2, 3], [3, 1, 2], None),
                                    ([3, 1, 2], [1, 2, 3], None)])
    a = [[1], 7]; c = a.copy(); c[0].append(2); c.append(9)
    question(r, 8, (a, c), [([[1], 7], [[1, 2], 7, 9]), ([[1, 2], 7], [[1, 2], 7, 9]),
                            ([[1, 2], 7, 9], [[1, 2], 7, 9]), ([[1], 7, 9], [[1, 2], 7])])
    a = [4, 1, 3]; b = a; c = a[:]; a.extend([2]); x = a.pop(0); a.sort()
    question(r, 9, (b, c, x), [([1, 2, 3, 4], [4, 1, 3], None), ([1, 3], [4, 1, 3], 2),
                                ([4, 1, 3], [1, 2, 3], 4), ([1, 2, 3], [4, 1, 3], 4)])
    n = [6, 12, 18, 24]
    check(r + ':practice1', (n[0], n[-1], len(n), n[1:3], n[2:], n[8:]),
          (6, 24, 4, [12, 18], [18, 24], []))
    bag = [5]; bag.append([6, 7]); bag.extend([8, 9]); last = bag.pop(); first = bag.pop(0)
    check(r + ':practice2', (first, last, bag), (5, 9, [[6, 7], 8]))
    a = [6, 2, 4]; b = a; c = a[:]; a.append(1); x = a.pop(0); a.sort()
    check(r + ':practice3', (b, c, x), ([1, 2, 4], [6, 2, 4], 6))
    n = [6, 12, 18, 24]; length = len(n); n[1] = 99
    check(r + ':element-replace-example', (length, n), (4, [6, 99, 18, 24]))
    a = [5, 8, 2]; x = a.pop(); first_state = a[:]; y = a.pop(0)
    check(r + ':pop-example', (x, first_state, y, a), (2, [5, 8], 5, [8]))
    a = [3, 1]; b = a; c = a.copy(); b.append(2); c[0] = 9
    check(r + ':alias-copy-example', (a, b, c), ([3, 1, 2], [3, 1, 2], [9, 1]))


def quantity(value, unit):
    return (F(value), unit)


def si_run_one():
    r = 'si-basics-run-1'
    question(r, 1, quantity(F('2.4') * 100, 'cm'), [quantity(x, 'cm') for x in ('24', '240', '0.024', '2400')])
    question(r, 2, quantity(F(75) / 1000, 'm'), [quantity(x, 'm') for x in ('0.75', '7.5', '75000', '0.075')])
    question(r, 3, quantity(F('6.8') * 10, 'mm'), [quantity('68', 'mm'), quantity('0.68', 'mm'), quantity('680', 'mm'), quantity('68', 'mms')])
    question(r, 4, quantity(100 * 100, 'cm2'), [quantity(x, 'cm2') for x in (100, 200, 10000, 1000000)])
    question(r, 5, quantity(F(450) / 10000, 'm2'), [quantity(x, 'm2') for x in ('0.045', '4.5', '4500000', '0.0045')])
    question(r, 6, quantity(F('0.2') * F(15) / 100, 'm2'), [quantity('3', 'm2'), quantity('0.03', 'm'), quantity('0.003', 'm2'), quantity('0.03', 'm2')])
    question(r, 7, quantity(F(4500) / 1000 / 3, 'm/s'), [quantity('1500', 'm/s'), quantity('1.5', 'm/s'), quantity('0.002', 'm/s'), quantity('1.5', 'm2')])
    question(r, 8, quantity(F(60 + 60) / (20 + 30), 'm/s'), [quantity(x, 'm/s') for x in ('2.5', '3', '2.4', '2')])
    question(r, 9, quantity(F(40 + 40) / (20 + 20 + 10), 'm/s'), [quantity(x, 'm/s') for x in ('0', '2', '0.8', '1.6')])
    pairs = [
        ('length-m-to-cm', F('2.35') * 100, F(235)), ('length-mm-to-m', F(480) / 1000, F('0.48')),
        ('length-cm-to-mm', F('7.2') * 10, F(72)), ('conversion-ratio', F(320) / 1000, F('0.32')),
        ('practice-length1-cm', F('0.64') * 100, F(64)), ('practice-length1-mm', F('0.64') * 1000, F(640)),
        ('practice-length2-cm', F(95) / 10, F('9.5')), ('practice-length2-m', F(95) / 1000, F('0.095')),
        ('rectangle-cm2', F(4) * 3, F(12)), ('m2-to-mm2', F(1000) ** 2, F(1000000)),
        ('cm2-to-mm2', F(10) ** 2, F(100)), ('area-forward', F('0.35') * 10000, F(3500)),
        ('area-back', F(2500) / 10000, F('0.25')), ('square-side', F(50) / 100 * F(50) / 100, F('0.25')),
        ('mixed-area-m2', F('0.3') * F(20) / 100, F('0.06')), ('mixed-area-cm2', F(30) * 20, F(600)),
        ('practice-area1', F('0.08') * 10000, F(800)), ('practice-area2', F(300) / 100, F(3)),
        ('practice-area3', F(2) ** 2 * 100, F(400)), ('full-speed-with-stop', F(120) / 60, F(2)),
        ('speed-before-stop', F(120) / 50, F('2.4')), ('bad-arithmetic-mean', (F(3) + 2) / 2, F('2.5')),
        ('speed-practice', F(72) / 24, F(3)), ('moving-only', F(72) / 18, F(4))]
    for name, actual, expected in pairs:
        check(r + ':' + name, actual, expected)


def si_run_two():
    r = 'si-basics-run-2'
    question(r, 1, quantity(F('0.72') * 1000, 'mm'), [quantity(x, 'mm') for x in ('72', '720', '7200', '0.72')])
    question(r, 2, quantity(F(85) / 10, 'cm'), [quantity(x, 'cm') for x in ('0.85', '85', '850', '8.5')])
    target = (F('2.4'),) * 3
    question(r, 3, target, [(F('2.4'), F(cm) / 100, F(mm) / 1000) for cm, mm in ((240, 2400), (24, 240), (2400, 240), (240, 240))])
    question(r, 4, quantity(F('0.08') * 10000, 'cm2'), [quantity(x, 'cm2') for x in (8, 80, 800, 8000)])
    question(r, 5, quantity(F(3) * 10 ** 2, 'mm2'), [quantity(x, 'mm2') for x in ('300', '30', '0.03', '3000')])
    area = F('0.6') * F('0.4')
    question(r, 6, (area, area), [(F(m2), F(cm2) / 10000) for m2, cm2 in (('0.24', 24), ('0.024', 240), ('2.4', 24000), ('0.24', 2400))])
    question(r, 7, quantity(F(18) / 6, 'm/s'), [quantity(x, 'm/s') for x in ('108', '0.333', '3', '12')])
    question(r, 8, quantity(F(20 + 30) / (5 + 15), 'm/s'), [quantity(x, 'm/s') for x in ('3', '2.5', '4', '2')])
    question(r, 9, quantity(F(120) / 100 / (4 + 2), 'm/s'), [quantity(x, 'm/s') for x in ('0.3', '20', '0.02', '0.2')])
    pairs = [
        ('length-example-cm', F('0.36') * 100, F(36)), ('length-example-mm', F('0.36') * 1000, F(360)),
        ('length-example2-cm', F(75) / 10, F('7.5')), ('length-example2-m', F(75) / 1000, F('0.075')),
        ('practice-length1-cm', F('1.35') * 100, F(135)), ('practice-length1-mm', F('1.35') * 1000, F(1350)),
        ('practice-length2-cm', F(46) / 10, F('4.6')), ('practice-length2-m', F(46) / 1000, F('0.046')),
        ('card-area-cm2', F(30) * 20, F(600)), ('card-area-m2', F(30) / 100 * F(20) / 100, F('0.06')),
        ('square-practice-mm2', F(50) ** 2, F(2500)), ('square-practice-cm2', F(50) ** 2 / 100, F(25)),
        ('square-practice-m2', F(50) ** 2 / 1000000, F('0.0025')),
        ('diagram-distance', F(40 + 0 + 60), F(100)), ('diagram-time', F(10 + 10 + 30), F(50)),
        ('diagram-speed', F(40 + 0 + 60) / (10 + 10 + 30), F(2)),
        ('segment-speed1', F(40) / 10, F(4)), ('segment-speed2', F(60) / 30, F(2)),
        ('bad-arithmetic-mean', (F(4) + 2) / 2, F(3)),
        ('speed-practice-distance', F(90 + 150) / 100, F('2.4')),
        ('speed-practice', F(90 + 150) / 100 / (3 + 3 + 2), F('0.3'))]
    for name, actual, expected in pairs:
        check(r + ':' + name, actual, expected)


def diagram_checks():
    ns = {'s': 'http://www.w3.org/2000/svg'}
    for run in ('si-basics-run-1', 'si-basics-run-2'):
        p = PLANS[run]
        grid = ET.fromstring(p['lessons'][1]['sections'][1]['diagrams'][0]['svg'])
        rectangles = grid.findall('s:rect', ns)
        square = next(item for item in rectangles if item.get('width') == '220')
        highlighted = next(item for item in rectangles if item.get('width') == '22')
        check(run + ':area-grid-ratio', (F(square.get('width')) / F(highlighted.get('width')),
                                        F(square.get('height')) / F(highlighted.get('height'))), (F(10), F(10)))
        check(run + ':grid-area-cm2', F(10) * 10 * (10 * 10), F(10000))
        chart = ET.fromstring(p['lessons'][2]['sections'][1]['diagrams'][0]['svg'])
        if run.endswith('1'):
            polyline = chart.find('s:polyline', ns)
            points = [tuple(map(F, point.split(','))) for point in polyline.get('points').split()]
            actual = [((x - 70) / 7, (280 - y) / F('1.75')) for x, y in points]
            check(run + ':chart-time-distance-coordinates', actual, [(F(0), F(0)), (F(20), F(60)), (F(50), F(120)), (F(60), F(120))])
        else:
            text = ''.join(chart.itertext())
            require(all(token in text for token in ('40 m', '10 s', '60 m', '30 s', '100 m', '50 s')), 'Timeline labels differ')
            check(run + ':timeline-total', (40 + 0 + 60, 10 + 10 + 30), (100, 50))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='append', default=[], metavar='ID=PATH', help='Override a frozen raw-plan input path')
    args = parser.parse_args()
    paths = {run: ROOT / 'runs' / run / 'raw-plan.json' for run in FROZEN}
    for value in args.run:
        run, path = value.split('=', 1)
        require(run in FROZEN, 'Unknown run ID: ' + run)
        paths[run] = Path(path)
    for run, path in paths.items():
        content = path.read_bytes()
        require(hashlib.sha256(content).hexdigest() == FROZEN[run], 'Input changed; content must be reviewed again: ' + run)
        plan = json.loads(content)
        require(plan['course']['days'] == 3 and plan['course']['daily_minutes'] == 20, 'Independent case constraints changed')
        require(len(plan['lessons']) == 3 and all(len(l['questions']) == 3 for l in plan['lessons']), 'Case shape changed')
        PLANS[run] = plan
    python_run_one(); python_run_two(); si_run_one(); si_run_two(); diagram_checks()
    print(json.dumps({'calculation_checks_passed': len(RECORDS), 'questions_independently_calculated': 36,
                      'review_type': 'agent review with handwritten execution and primary-source reading; not human review',
                      'arbitrary_course_facts_verified': False,
                      'reference_scope_discrepancy': 'SI oracle asks kilo although the input case only asks m/cm/mm; both SI runs omit kilo',
                      'learner_trial': 'pending', 'raw_plan_sha256': FROZEN, 'checks': RECORDS},
                     ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, AssertionError) as error:
        print('Independent review checks failed: ' + str(error), file=sys.stderr)
        sys.exit(1)
