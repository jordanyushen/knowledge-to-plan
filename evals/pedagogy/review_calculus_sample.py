#!/usr/bin/env python3
"""Recompute selected frozen-sample arithmetic and SVG geometry, not arbitrary facts.

The private HTML is supplied by path and is never copied or executed. Expected
defects remain expected defects: this script passing does not approve the course.
"""
import argparse
from fractions import Fraction as F
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'knowledge-to-plan' / 'scripts'))
from lint_pedagogy import lint_pedagogy, plan_sha256

HTML_SHA256 = '0ad3099bb5960507daa3cd4d442dbc5ef4685e12be92a98553f34892fcae37f8'


def derivative(coefficients):
    return [index * value for index, value in enumerate(coefficients)][1:]


def integral(coefficients):
    return [F(0)] + [F(value, index + 1) for index, value in enumerate(coefficients)]


def at(coefficients, x):
    return sum(value * x ** index for index, value in enumerate(coefficients))


def cubic_derivatives(points, t):
    dx, dy = [], []
    for axis in [0, 1]:
        p = [F(point[axis]) for point in points]
        first = 3 * ((p[1]-p[0])*(1-t)**2 + 2*(p[2]-p[1])*(1-t)*t + (p[3]-p[2])*t**2)
        second = 6 * ((p[2]-2*p[1]+p[0])*(1-t) + (p[3]-2*p[2]+p[1])*t)
        (dx if axis == 0 else dy).extend([first, second])
    return dx, dy


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--html', required=True, type=Path)
    args = parser.parse_args()
    raw = args.html.read_bytes()
    if hashlib.sha256(raw).hexdigest() != HTML_SHA256:
        raise ValueError('Original HTML changed; do not reuse this frozen-sample review')
    match = re.search(r'window\.COURSE\s*=\s*(.*?)</script>', raw.decode('utf-8'), re.S)
    data = json.loads(match.group(1).strip().rstrip(';'))
    checks = []

    def check(name, actual, expected):
        if actual != expected:
            raise AssertionError(f'{name}: {actual} != {expected}')
        checks.append(name)

    check('course_lessons', len(data['lessons']), 21)
    check('question_count', sum(len(l['questions']) for l in data['lessons']), 64)
    check('all_answer_positions_are_A', {q['correct_index'] for l in data['lessons'] for q in l['questions']}, {0})
    check('first_explicit_review_day', next(l['day'] for l in data['lessons'] if l.get('review_of')), 20)
    check('d1_q3', 2**2-1, 3)
    check('d2_reducible_limit', 1+1, 2)
    check('d3_q1', (2+3)*(1-4), -15)
    check('d3_q2', F(4, 2), 2)
    check('d3_example', F(2**2+3*2, 2+1), F(10,3))
    check('d3_practice_regular_limit', F(0+1,0-1), -1)
    check('d4_hole_limit', 2+2, 4)
    check('d6_q1_derivative', at(derivative([0,0,1]),3), 6)
    check('d6_q3_secant', F(4-1,2-1), 3)
    check('d7_polynomial_derivative', derivative([2,-5,0,4]), [-5,0,12])
    check('d7_practice_derivative_at_one', at(derivative([-8,1,-3,0,1]),1), -1)
    check('d8_quotient_numerator', [2*3+1, 2-2], [7,0])
    check('d9_second_derivative', derivative(derivative([0,-3,0,1])), [0,6])
    check('d10_balloon_pi_coefficient', F(2,4*3**2), F(1,18))
    check('d10_practice_pi_coefficient', F(2,4*6**2), F(1,72))
    check('d11_derivative_signs', [at(derivative([0,-3,0,1]), x)>0 for x in [-2,0,2]], [True,False,True])
    check('d11_values_at_critical_points', [at([0,-3,0,1],x) for x in [-1,1]], [2,-2])
    check('d11_values_at_endpoints', [at([0,-3,0,1],x) for x in [-2,2]], [-2,2])
    check('d13_optimum_width', F(100,4), 25)
    check('d13_optimum_area', 25*(100-2*25), 1250)
    check('d13_practice_fixed_perimeter', 10*10, 100)
    check('d14_linear_estimate', F(3)+F(1,6)*F(1,5), F(91,30))
    check('d15_antiderivative_verification', derivative([0,1,-2,2]), [1,-4,6])
    check('d15_practice_antiderivative', derivative([0,0,F(-1,2),0,0,F(3,5)]), [0,-1,0,0,3])
    check('d17_two_right_rectangles', 1+2, 3)
    check('d17_four_left_rectangles', sum(F(index,2)*F(1,2) for index in range(4)), F(3,2))
    check('d17_integral', at(integral([0,1]),2)-at(integral([0,1]),0), 2)
    check('d18_q1', at(integral([0,0,1]),2)-at(integral([0,0,1]),1), F(7,3))
    check('d18_q3', at(integral([0,2]),3)-at(integral([0,2]),0), 9)
    check('d18_practice_one', at(integral([-1,0,0,4]),1)-at(integral([-1,0,0,4]),0), 0)
    check('d18_practice_two', at(integral([5]),4)-at(integral([5]),2), 10)
    check('d19_area', at(integral([4,0,-1]),2)-at(integral([4,0,-1]),-2), F(32,3))
    check('d19_odd_integral', at(integral([0,1]),1)-at(integral([0,1]),-1), 0)
    check('d20_q2', at(integral([0,2]),1)-at(integral([0,2]),0), 1)
    check('d21_q3', at(integral([0,0,3]),2)-at(integral([0,0,3]),0), 8)

    # Day12 cubic SVG has screen y downward. Convert curvature sign to Cartesian y upward.
    left = [(80,200),(160,200),(200,80),(300,80)]
    right = [(300,80),(400,80),(440,200),(560,200)]
    curvature = []
    for points, t in [(left,F(1)),(right,F(0))]:
        (dx,ddx),(dy,ddy) = cubic_derivatives(points,t)
        curvature.append(-(ddy*dx-dy*ddx)/dx**3)
        check('d12_join_horizontal_' + str(t), dy, 0)
    check('d12_same_negative_curvature_both_sides', curvature, [F(-1,125),F(-1,125)])
    # Day6 B marker (400,120) is not on its quadratic curve: at x=400, t=1/2, y=132.5.
    check('d6_curve_y_at_B_x', F(190,4)+F(140,2)+F(60,4), F(265,2))
    check('d6_B_marker_curve_gap', F(265,2)-120, F(25,2))
    # Dashed secant endpoint line (160,240) to (480,70), at B's x=400.
    check('d6_secant_y_at_B_x', 240+F(70-240,480-160)*(400-160), F(225,2))
    check('d6_B_marker_secant_gap', 120-F(225,2), F(15,2))
    report = lint_pedagogy(data)
    check('lint_does_not_approve_original', report['passed'], False)
    check('lint_flags_scope', any(i['code']=='scope_budget_overclaim' for i in report['issues']), True)
    print(json.dumps(dict(html_sha256=HTML_SHA256, plan_sha256=plan_sha256(data), selected_checks=len(checks),
                         expected_defects_confirmed=['day12_false_inflection','day6_point_off_curve_and_secant'],
                         facts_verified=False, content_review_scope='selected_arithmetic_and_svg_geometry'), ensure_ascii=False))


if __name__ == '__main__':
    main()
