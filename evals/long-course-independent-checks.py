#!/usr/bin/env python3
"""Independent, hand-transcribed calculations for the frozen narrow long course.

Does not read the author's reference.json/oracle or run course-provided code.
Semantic prose and source review are recorded separately in the review document.
"""
from fractions import Fraction as F
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
COURSE = ROOT / 'long-course'
FINAL_SHA256 = '478386dafb5cc8e73df24f70928b7e0cc035bca8c4a84bb90c32f28cae7de5c3'
FIRST_SHA256 = '1180c052dd6977c336fa51ef02df4731fc63eca8de5fe3b97398657e6f2d2d62'


def fingerprint(data):
    return hashlib.sha256(json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')).hexdigest()


def value(coefficients, x):
    return sum(F(coefficient) * F(x)**power for power, coefficient in enumerate(coefficients))


def derivative(coefficients):
    return [power * F(coefficient) for power, coefficient in enumerate(coefficients)][1:]


def anti(coefficients):
    return [F(0)] + [F(coefficient, power+1) for power, coefficient in enumerate(coefficients)]


def delta(coefficients, a, b):
    return value(coefficients,b)-value(coefficients,a)


def average(coefficients, a, b):
    return delta(coefficients,a,b)/F(b-a)


def integral(coefficients, a, b):
    return delta(anti(coefficients),a,b)


def numbers(value):
    return [F(number) for number in re.findall(r'[-+]?(?:\d+\.\d+|\d+)',value)]


def main():
    read = lambda path: json.loads(path.read_text(encoding='utf-8'))
    data = dict(schema_version=1, course=read(COURSE/'course.json'), sources=read(COURSE/'sources.json'),
                lessons=sum([read(path) for path in sorted((COURSE/'lessons').glob('*.json'))], []))
    if fingerprint(data) != FINAL_SHA256:
        raise ValueError('Course changed: independently re-review it before updating the frozen review hash')
    history = read(COURSE/'review-history'/'first-reviewed-plan.json')
    if fingerprint(history) != FIRST_SHA256:
        raise ValueError('The initial independently reviewed plan changed')
    checks = []

    def check(name, actual, expected):
        if actual != expected:
            raise AssertionError(f'{name}: {actual!r} != {expected!r}')
        checks.append(name)

    # Each input is independently transcribed from the actual question, not from author oracles.
    x2 = [0,0,1]
    scored = [delta([1,0,1],1,2), average(x2,1,3), average(x2,-2,0),
              value(derivative(x2),2), average(x2,2,4), value(derivative([-2,3]),-4),
              value(derivative([0,0,2]),3), value(derivative([2,3,1]),2),
              value(derivative([0,4,-1]),1), value(derivative([0,-4,1]),2),
              value(derivative([3,0,1]),1), value([5,1,2],1), integral([3],1,4),
              integral(x2,0,3), integral([1,2],1,3), integral([0,1],-1,1),
              integral([1,2],3,1), delta(x2,1,3), integral([0,0,-1],0,3),
              integral([1,0,1],0,2), value(derivative([0,-2,1]),3)]
    check('number_of_actual_scored_tasks', len(data['lessons']), len(scored))
    for day, (lesson, actual) in enumerate(zip(data['lessons'],scored),1):
        check(f'd{day}_has_one_scored_question',len(lesson['questions']),1)
        question = lesson['questions'][0]
        option_values = [F(option.replace('−','-')) for option in question['options']]
        check(f'd{day}_answer_is_unique', sum(option==actual for option in option_values),1)
        check(f'd{day}_key_matches_independent_calculation', option_values[question['correct_index']],actual)

    # Independent practice and example calculations, including intermediate outputs.
    check('d1_practice', [value([1,0,1],0),value([1,0,1],3),delta([1,0,1],0,3)],[1,10,9])
    check('d2_practice',average(x2,0,2),2)
    check('d3_practice_and_reverse', [average(x2,-3,-1),average(x2,-1,-3)],[-4,-4])
    check('d4_practice',value(derivative(x2),3),6)
    # (a+h)^2-a^2 = 2ah+h^2. Two nonzero h checks plus direct polynomial identity.
    check('d4_difference_quotient_identity', [average(x2,3,3+F(1,2)),average(x2,3,3-F(1,2))], [F(13,2),F(11,2)])
    check('d5_practice',[average(x2,1,5),value(derivative(x2),1)],[6,2])
    check('d6_practice',[derivative([5,-2]),value(derivative([5,-2]),3),average([5,-2],0,1)],[[-2],-2,-2])
    check('d7_practice',value(derivative([0,0,3]),2),12)
    check('d8_practice',[derivative([4,-1,2]),value(derivative([4,-1,2]),1)],[[-1,4],3])
    check('d9_practice',[derivative([0,6,-2]),value(derivative([0,6,-2]),2),value([0,6,-2],2)],[[6,-4],-2,4])
    check('d10_practice',[value(derivative([0,-6,1]),x) for x in [3,2,4]],[0,-2,2])
    check('d11_two_antiderivatives',[derivative(x2),derivative([5,0,1])],[[0,2],[0,2]])
    check('d11_practice_derivative',value(derivative([5,0,1]),2),4)
    check('d12_given_antiderivative',derivative([5,1,2]),[1,4])
    check('d12_example_values',[value([5,1,2],0),value([5,1,2],1)],[5,8])
    check('d12_practice',[derivative([3,2,1]),value([3,2,1],0),value([3,2,1],2)],[[2,2],3,11])
    check('d13_practice_integral',integral([-2],0,3),-6)
    check('d13_practice_geometric_area',F(2)*3,6)
    check('d14_given_antiderivative',derivative([0,0,0,F(1,3)]),x2)
    check('d14_practice',integral(x2,0,2),F(8,3))
    check('d15_given_antiderivative',derivative([0,1,1]),[1,2])
    check('d15_practice_constant_cancels',[delta([0,1,1],0,2),delta([7,1,1],0,2)],[6,6])
    check('d16_example_signed_halves',[integral([0,1],-1,0),integral([0,1],0,1)],[F(-1,2),F(1,2)])
    check('d16_practice_integral',integral([0,1],-2,2),0)
    check('d16_practice_geometric_area',-integral([0,1],-2,0)+integral([0,1],0,2),4)
    check('d17_practice_partition',[integral([0,1],0,1),integral([0,1],1,2),integral([0,1],0,2),integral([0,1],2,0)],[F(1,2),F(3,2),2,-2])
    check('d18_practice',[value(derivative(x2),3),delta(x2,2,4),integral(derivative(x2),2,4)],[6,12,12])
    check('d19_practice',[integral([0,0,-1],0,2),-integral([0,0,-1],0,2)],[F(-8,3),F(8,3)])
    check('d20_practice',[integral(x2,0,1),integral([1],0,1),integral([1,0,1],0,1)],[F(1,3),1,F(4,3)])
    check('d21_practice',[value(derivative([0,-2,1]),1),delta([0,-2,1],0,3),integral([0,-2,1],0,3)],[0,3,0])
    check('d21_given_antiderivative',derivative([0,0,-1,F(1,3)]),[0,-2,1])
    check('LC02_counterexample_same_numeric_value',[value(derivative(x2),2),delta(x2,0,2)],[4,4])

    ns = {'s':'http://www.w3.org/2000/svg'}
    svg = ET.fromstring(data['lessons'][1]['sections'][0]['diagrams'][0]['svg'])
    curve = numbers(svg.find('s:path',ns).attrib['d'])
    check('diagram1_curve_control_points',curve,[50,250,170,250,290,10])
    def quadratic(t):
        return [curve[axis]*(1-t)**2+2*curve[2+axis]*(1-t)*t+curve[4+axis]*t*t for axis in [0,1]]
    for label,x,t in [('a',1,F(1,4)),('b',3,F(3,4))]:
        point = svg.find(f's:circle[@id="point-{label}"]',ns)
        screen = [F(point.attrib['cx']),F(point.attrib['cy'])]
        check(f'diagram1_point_{label}_on_curve',screen,quadratic(t))
        check(f'diagram1_point_{label}_coordinate_transform',[(screen[0]-50)/60,(250-screen[1])/15],[x,x*x])
    secant = svg.find('s:line[@id="secant"]',ns)
    coordinates = [F(secant.attrib[key]) for key in ['x1','y1','x2','y2']]
    check('diagram1_secant_endpoints',coordinates,[110,235,230,115])
    check('diagram1_secant_mathematical_slope',F(coordinates[1]-coordinates[3],15)/F(coordinates[2]-coordinates[0],60),4)
    svg = ET.fromstring(data['lessons'][15]['sections'][0]['diagrams'][0]['svg'])
    areas = []
    for name in ['negative-region','positive-region']:
        raw = numbers(svg.find(f's:polygon[@id="{name}"]',ns).attrib['points'])
        points = [(raw[i],raw[i+1]) for i in range(0,len(raw),2)]
        transformed = [((x-170)/100,(180-y)/100) for x,y in points]
        area = abs(sum(x*y2-y*x2 for (x,y),(x2,y2) in zip(transformed,transformed[1:]+transformed[:1])))/2
        areas.append(area)
        check(f'diagram2_{name}_triangle_area',area,F(1,2))
    graph = svg.find('s:line[@id="graph"]',ns)
    for suffix in ['1','2']:
        x,y=F(graph.attrib['x'+suffix]),F(graph.attrib['y'+suffix])
        check('diagram2_graph_endpoint_'+suffix,(x-170)/100,(180-y)/100)
    check('diagram2_net_and_total',[-areas[0]+areas[1],sum(areas)],[0,1])
    print(json.dumps(dict(passed=True,plan_sha256=FINAL_SHA256,initial_plan_sha256=FIRST_SHA256,
                         checks=len(checks),scored_questions=21,option_values_checked=84,diagrams=2,
                         review_kind='independent hand-written fixed calculations',facts_verified=False,
                         learner_trial='not_performed'),ensure_ascii=False))


if __name__ == '__main__':
    main()
