#!/usr/bin/env python3
"""Find teaching risks, never certify the truth or effectiveness of a course."""

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import re
import sys

from validate_plan import validate_plan


def plan_sha256(data):
    """Fingerprint JSON meaning; whitespace and object key order do not matter."""
    raw = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _evidence(value):
    return isinstance(value, list) and bool(value) and all(_text(item) for item in value)


def _exists_location(data, location):
    """Accept an existing, explicit JSON path, never a wildcard or executable path."""
    if not _text(location) or not location.startswith('$'):
        return False
    cursor, value = 1, data
    for token in re.finditer(r'\.([A-Za-z_][A-Za-z_0-9]*)|\[(\d+)\]', location[1:]):
        if token.start() + 1 != cursor:
            return False
        if token.group(1) is not None:
            if not isinstance(value, dict) or token.group(1) not in value:
                return False
            value = value[token.group(1)]
        else:
            index = int(token.group(2))
            if not isinstance(value, list) or index >= len(value):
                return False
            value = value[index]
        cursor = token.end() + 1
    return cursor == len(location)


def _broad_claim(goal):
    """Recognize explicit claims, excluding nearby negation within each clause.

    This deliberately narrow wording check is a review trigger, not language
    understanding. A negated exclusion never suppresses a separate positive
    promise, including one following a contrast such as '但'.
    """
    pattern = re.compile(r'(?:掌握|精通).{0,8}(?:完整|全部|所有)|(?:完整|全部|所有).{0,8}(?:掌握|精通)|完整.{0,8}微积分|\bmaster\s+(?:all|the\s+entire)\b', re.I)
    clauses = re.split(r'[。！？!?；;，,\n]|但是|然而|不过|而是|但', goal)
    for clause in clauses:
        for match in pattern.finditer(clause):
            prefix = clause[:match.start()]
            if not re.search(r'(?:不含|不包括|不承诺|不涉及|不要求|并非|不是|不会|不保证|不代表).{0,8}$|\b(?:not|never)\s+.{0,8}$', prefix, re.I):
                return True
    return False


def lint_pedagogy(data, goal_map=None, review=None, min_questions=8, review_window=5, scope_review_hours=12):
    """Return risks and traceable review dispositions for one exact course.

    `passed` means no unresolved blocking risk, not fact verification. The optional
    goal map is author-supplied coverage evidence, not semantic proof. Review
    dispositions can waive heuristic risks only; structural and confirmed content
    defects cannot be waived. See references/pedagogy-review.md for file formats.
    """
    if type(min_questions) is not int or min_questions < 2:
        raise ValueError('min_questions must be an integer at least 2')
    if type(review_window) is not int or review_window < 1:
        raise ValueError('review_window must be a positive integer')
    if isinstance(scope_review_hours, bool) or not isinstance(scope_review_hours, (int, float)) or not math.isfinite(scope_review_hours) or scope_review_hours <= 0:
        raise ValueError('scope_review_hours must be a positive finite number')
    digest = plan_sha256(data)
    issues = []

    def add(code, severity, location, message, suggestion, waivable=True):
        issues.append(dict(code=code, severity=severity, location=location, message=message,
                           suggestion=suggestion, reviewed=False, resolved=False, waivable=waivable))

    structural = validate_plan(data)
    if structural:
        for index, message in enumerate(structural):
            add('structure_invalid', 'error', '$', message, '先修复课程结构再运行教学风险检查。', False)
        return dict(passed=False, plan_sha256=digest, issues=issues, facts_verified=False,
                    content_review_status='not_performed', content_findings=[])

    lessons = data['lessons']
    by_id = {lesson['id']: lesson for lesson in lessons}
    groups = defaultdict(list)
    for i, lesson in enumerate(lessons):
        for j, question in enumerate(lesson['questions']):
            groups[len(question['options'])].append((question['correct_index'], f'$.lessons[{i}].questions[{j}]'))
    for arity, questions in sorted(groups.items()):
        answers = [index for index, _ in questions]
        counts = Counter(answers)
        location = f'$.lessons[*].questions[options={arity}]'
        if len(answers) >= min_questions and len(counts) == 1:
            add('answer_position_constant', 'error', location,
                f'{len(answers)}道{arity}选项题的正确项全部位于第{answers[0] + 1}个位置。',
                '复核出题过程；重排时同步调整选项、正确索引和每项解析，再独立核对。')
        elif len(answers) >= min_questions and max(counts.values()) / len(answers) >= .75:
            add('answer_position_skew', 'warning', location,
                f'{len(answers)}道{arity}选项题的答案位置集中度至少75%。',
                '检查是否形成猜答案规律；不要求机械均匀，也不能只改正确索引。')
        if len(counts) > 1:
            longest = current = 1
            for previous, answer in zip(answers, answers[1:]):
                current = current + 1 if answer == previous else 1
                longest = max(longest, current)
            if longest >= 5:
                add('answer_position_run', 'warning', location,
                    f'同选项数量题目中有连续{longest}题的正确位置相同。',
                    '检查长串相同答案是否来自作者默认值；保留合理题目内容。')

    days = len(lessons)
    review_days = [lesson['day'] for lesson in lessons if lesson.get('review_of')]
    if days >= 8:
        if not review_days:
            add('review_missing', 'warning', '$.lessons', '长课没有显式的跨课复习引用。',
                '安排早期检索、后续复习与迁移任务，并用review_of定位。')
        else:
            if review_days[0] > review_window + 1:
                index = review_days[0] - 1
                add('review_starts_late', 'warning', f'$.lessons[{index}].review_of',
                    f'首次显式复习直到第{review_days[0]}课，晚于默认{review_window}课窗口。',
                    '把重要基础的首次检索提前；具体间隔应按目标难度复核。')
            if any(end - start > review_window for start, end in zip(review_days, review_days[1:] + [days])):
                add('review_long_gap', 'warning', '$.lessons',
                    f'相邻复习节点或最后复习到结课的间隔超过{review_window}课。',
                    '检查核心目标是否在间隔内得到真实复习，而不只是添加引用。')
        if goal_map is None:
            add('goal_map_missing', 'warning', '$.lessons', '长课未提供目标—教学—练习—检查映射。',
                '提供绑定当前课程指纹的goal-map.json，再独立审阅实际内容覆盖。')

    goal = data['course']['goal']
    broad_claim = _broad_claim(goal)
    if broad_claim:
        add('goal_scope_review', 'warning', '$.course.goal', '目标包含完整掌握等宽泛承诺。',
            '把可观察的能力、覆盖边界和预算依据写清楚；关键词本身不能判断目标可行性。')
        hours = data['course']['days'] * data['course']['daily_minutes'] / 60
        if hours <= scope_review_hours:
            add('scope_budget_overclaim', 'error', '$.course.goal',
                f'完整掌握类目标只安排{hours:g}小时，触发项目默认≤{scope_review_hours:g}小时的范围审阅规则。',
                '缩小并重新估算可观察目标，或附该学习者、范围和任务的具体证据逐项复核；阈值不是学科学时下限。')

    placeholder = re.compile(r'后续(?:再)?补充|稍后(?:再)?(?:补充|完善)|待(?:生成|补充|完善)|详见未提供|\b(?:TODO|TBD|placeholder)\b', re.I)
    complex_math = re.compile(r'\\(?:frac|int|sqrt|sum)\b|\b(?:integral|sqrt)\s*\(|(?:\w|\))\s*/\s*\(')
    diagram_context = re.compile(r'电路|受力|坐标|几何|时序|流程|\b(?:circuit|coordinate|geometry|force diagram|timing diagram)\b', re.I)
    known_activities = {'learn', 'read', 'reading', 'practice', 'quiz', 'review', 'notes', 'exercise'}
    for i, lesson in enumerate(lessons):
        for j, activity in enumerate(lesson['activities']):
            kind = activity['kind']
            if re.fullmatch(r'[A-Za-z_ -]+', kind) and kind.lower() not in known_activities:
                add('activity_label_unknown', 'warning', f'$.lessons[{i}].activities[{j}].kind',
                    f'活动名“{kind}”没有已知中文标签。', '使用约定活动名或清楚的中文标签。')
        for j, section in enumerate(lesson['sections']):
            location = f'$.lessons[{i}].sections[{j}]'
            prose = '\n'.join(section.get(key, '') for key in ['title', 'body', 'example'] if isinstance(section.get(key, ''), str))
            if placeholder.search(prose):
                add('possible_placeholder', 'warning', location,
                    '讲解包含疑似占位或尚未提供资料的措辞。', '核实是否缺实际教学内容；引用这些措辞作反例时可记录依据。')
            if complex_math.search(prose):
                add('inline_math_review', 'warning', location,
                    '纯文本中出现复杂线性公式或未渲染的数学标记。',
                    '核对表达无歧义，必要时改用支持的MathML公式块并检查实际排版。')
            if diagram_context.search(prose) and not section.get('diagrams'):
                add('diagram_need_review', 'warning', location,
                    '涉及可能需要关系图的内容，但该节未附示意图。',
                    '按实际推理判断是否需要图；不是每个公式或相关词都必须配图。')

    if goal_map is not None:
        if not isinstance(goal_map, dict) or goal_map.get('plan_sha256') != digest:
            add('goal_map_invalid', 'error', '$.goal_map', '目标映射缺失或指纹与当前课程不一致。',
                '根据当前课程重新核对映射，不复用过期记录。', False)
        elif not isinstance(goal_map.get('goals'), list) or not goal_map['goals']:
            add('goal_map_invalid', 'error', '$.goal_map.goals', '目标映射必须包含非空goals数组。',
                '逐目标填写教学、练习、检查和复习定位。', False)
        else:
            seen = set()
            for index, item in enumerate(goal_map['goals']):
                location = f'$.goal_map.goals[{index}]'
                if not isinstance(item, dict) or not _text(item.get('id')) or item.get('id') in seen or not _text(item.get('description')):
                    add('goal_map_invalid', 'error', location, '目标缺少唯一id或清楚的description。', '修复目标记录。', False)
                    continue
                seen.add(item['id'])
                core = item.get('core', True)
                if type(core) is not bool:
                    add('goal_map_invalid', 'error', location + '.core', 'core必须是布尔值。', '明确目标是否为核心目标。', False)
                refs = {}
                for field in ['taught_in', 'practiced_in', 'reviewed_in']:
                    value = item.get(field, [])
                    if not isinstance(value, list) or any(not _text(ref) or ref not in by_id for ref in value) or len(set(value)) != len(value):
                        add('goal_reference_invalid', 'error', location + '.' + field,
                            '目标定位必须是无重复的已存在课次ID数组。', '修正定位，不用标题或课次序号替代ID。', False)
                        refs[field] = []
                    else:
                        refs[field] = value
                for field in ['taught_in', 'practiced_in']:
                    if not refs[field]:
                        add('goal_coverage_missing', 'error', location + '.' + field,
                            f'目标“{item["description"]}”缺少{field}定位。', '补足实际内容后更新对应定位。', False)
                for ref in refs['practiced_in']:
                    if not _text(by_id[ref].get('practice')):
                        add('goal_practice_missing', 'error', location + '.practiced_in',
                            f'映射到的{ref}没有实际practice任务。', '提供练习输入与产出，再重新核对映射。', False)
                assessed = item.get('assessed_by', [])
                assessment_days = []
                if not isinstance(assessed, list) or not assessed:
                    add('goal_coverage_missing', 'error', location + '.assessed_by',
                        f'目标“{item["description"]}”没有检查题定位。', '补足检查任务并指向实际题目。', False)
                else:
                    for qi, ref in enumerate(assessed):
                        lesson = by_id.get(ref.get('lesson_id')) if isinstance(ref, dict) and _text(ref.get('lesson_id')) else None
                        if lesson is None or not _text(ref.get('question_id')) or ref['question_id'] not in {q['id'] for q in lesson['questions']}:
                            add('goal_reference_invalid', 'error', location + f'.assessed_by[{qi}]',
                                '检查定位必须引用实际lesson_id与question_id。', '修正定位。', False)
                        else:
                            assessment_days.append(lesson['day'])
                taught_days = [by_id[ref]['day'] for ref in refs['taught_in']]
                if taught_days and any(day < min(taught_days) for day in assessment_days):
                    add('goal_assessment_before_teaching', 'error', location + '.assessed_by',
                        '该目标的检查安排在其首次讲解之前。', '检查先修关系与映射；诊断题请与计分掌握检查分开。', False)
                if core and taught_days and min(taught_days) + review_window < days:
                    first = min(taught_days)
                    reviewed_days = [by_id[ref]['day'] for ref in refs['reviewed_in']]
                    if not reviewed_days:
                        add('goal_review_missing', 'error', location + '.reviewed_in',
                            '核心目标没有后续检索或复习定位。', '添加真实回忆/应用任务，再填写定位。')
                    elif not any(first < day <= first + review_window for day in reviewed_days):
                        add('goal_review_late', 'error', location + '.reviewed_in',
                            f'核心目标未在首次讲解后{review_window}课内复习。', '提前安排检索，或按目标难度提供可复核的间隔依据。')

    findings = []
    if review is not None:
        if not isinstance(review, dict) or review.get('plan_sha256') != digest:
            add('review_invalid', 'error', '$.review', '复核记录缺失或指纹与当前课程不一致。',
                '复核当前版本后生成记录，不复用旧记录。', False)
        else:
            findings = review.get('content_findings', [])
            if not isinstance(findings, list):
                add('review_invalid', 'error', '$.review.content_findings', 'content_findings必须为数组。', '修复复核记录。', False)
                findings = []
            for index, finding in enumerate(findings):
                location = f'$.review.content_findings[{index}]'
                if (not isinstance(finding, dict) or finding.get('kind') not in ['formula', 'diagram', 'answer', 'fact', 'unit']
                        or not _exists_location(data, finding.get('location')) or not _text(finding.get('message'))
                        or not _evidence(finding.get('evidence')) or finding.get('status') not in ['open', 'resolved']):
                    add('review_invalid', 'error', location, '内容发现缺少类型、定位、消息、证据或明确状态。', '补足独立核算/来源定位。', False)
                elif finding['status'] == 'open':
                    add('confirmed_content_defect', 'error', finding['location'], finding['message'],
                        '修正实际内容并对新版本重新复核；不能豁免已确认错误。', False)
            resolutions = review.get('resolutions', [])
            if not isinstance(resolutions, list):
                add('review_invalid', 'error', '$.review.resolutions', 'resolutions必须为数组。', '修复逐项复核记录。', False)
                resolutions = []
            keys = set()
            for index, resolution in enumerate(resolutions):
                location = f'$.review.resolutions[{index}]'
                if (not isinstance(resolution, dict) or not _text(resolution.get('code')) or not _text(resolution.get('location'))
                        or not _text(resolution.get('rationale')) or not _evidence(resolution.get('evidence'))):
                    add('review_invalid', 'error', location, '逐项复核必须包含规则、精确位置、理由和证据定位。', '不使用全局忽略。', False)
                    continue
                key = (resolution['code'], resolution['location'])
                matching = [issue for issue in issues if (issue['code'], issue['location']) == key and issue['waivable']]
                if key in keys or not matching:
                    add('review_invalid', 'error', location, '复核条目重复、未匹配具体风险或试图豁免不可豁免错误。',
                        '仅按本报告中的规则和精确位置逐项复核。', False)
                else:
                    keys.add(key)
                    for issue in matching:
                        issue['reviewed'] = True
                        issue['resolved'] = True
                        issue['review'] = dict(rationale=resolution['rationale'], evidence=resolution['evidence'])

    return dict(passed=not any(issue['severity'] == 'error' and not issue['reviewed'] for issue in issues),
                plan_sha256=digest, issues=issues, facts_verified=False,
                content_review_status='findings_recorded' if findings else 'not_performed', content_findings=findings)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('plan', type=Path)
    parser.add_argument('--goal-map', type=Path)
    parser.add_argument('--review', type=Path)
    parser.add_argument('--output', type=Path, help='保存报告；默认只输出到stdout')
    parser.add_argument('--min-questions', type=int, default=8)
    parser.add_argument('--review-window', type=int, default=5)
    parser.add_argument('--scope-review-hours', type=float, default=12, help='完整掌握承诺触发人工范围审阅的项目阈值，不是科学学时下限')
    args = parser.parse_args()
    try:
        read = lambda path: json.loads(path.read_text(encoding='utf-8')) if path else None
        report = lint_pedagogy(read(args.plan), read(args.goal_map), read(args.review), args.min_questions, args.review_window, args.scope_review_hours)
        rendered = json.dumps(report, ensure_ascii=False, indent=2) + '\n'
        if args.output:
            args.output.write_text(rendered, encoding='utf-8')
        print(rendered, end='')
        return 0 if report['passed'] else 2
    except (OSError, ValueError, TypeError) as error:
        print(json.dumps({'passed': False, 'error': str(error), 'facts_verified': False}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
