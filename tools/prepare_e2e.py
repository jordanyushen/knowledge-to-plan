#!/usr/bin/env python3
"""Create a small, unseeded course for browser state and layout tests."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'knowledge-to-plan' / 'scripts'))
from build_learning_site import build


def prepare():
    plan = {
        'schema_version': 1,
        'course': {'id': 'ktp-browser-regression', 'title': '浏览器回归测试课程',
                   'goal': '验证离线课程交互，不作为教学质量评测。', 'background': '测试夹具',
                   'days': 2, 'daily_minutes': 10, 'timezone': 'Asia/Hong_Kong'},
        'sources': [{'id': 'fixture', 'title': '测试数据定义',
                     'locator': '1米等于1000毫米；本数据仅供交互回归测试。'}],
        'lessons': []}
    for day in (1, 2):
        plan['lessons'].append({
            'id': 'day-' + str(day), 'day': day, 'title': '长度换算 ' + str(day),
            'objectives': ['将毫米换算成米'],
            'activities': [{'kind': 'read', 'minutes': 4}, {'kind': 'practice', 'minutes': 3},
                           {'kind': 'quiz', 'minutes': 3}],
            'sections': [{'title': '长度单位', 'body': '1米等于1000毫米。毫米换算成米时除以1000。',
                          'example': '500毫米等于0.5米。'}],
            'practice': '计算250毫米是多少米，再反向检查。',
            'takeaways': ['毫米换米时除以1000'], 'source_ids': ['fixture'],
            'questions': [
                {'id': 'q1', 'prompt': '500毫米等于多少米？', 'options': ['0.5米', '500米', '5米'],
                 'correct_index': 0, 'explanations': ['500除以1000等于0.5。', '遗漏了单位换算。', '结果大了10倍。']},
                {'id': 'q2', 'prompt': '250毫米等于多少米？', 'options': ['2.5米', '0.25米', '250米'],
                 'correct_index': 1, 'explanations': ['结果大了10倍。', '250除以1000等于0.25。', '遗漏了单位换算。']}]
        })
    output = ROOT / '.e2e' / 'site'
    result = build(plan, output, overwrite=True, expected_days=2, expected_daily_minutes=10)
    stem = json.loads((ROOT / 'knowledge-to-plan' / 'assets' / 'stem-example' / 'plan.json').read_text(encoding='utf-8'))
    build(stem, output / 'stem', overwrite=True)
    return result


if __name__ == '__main__':
    print(json.dumps(prepare()))
