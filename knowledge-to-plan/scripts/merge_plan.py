#!/usr/bin/env python3
"""Merge checked lesson batches without changing their content or constraints.

This is an authoring tool, not a budget or teaching-fact verifier. A completed
merge has the existing schema_version 1 shape and is checked by validate_plan.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

from validate_plan import validate_plan


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('JSON存在重复键：' + key)
        result[key] = value
    return result


def _read(path):
    try:
        raw = path.read_bytes()
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=_unique_object)
    except (OSError, UnicodeError, ValueError) as error:
        raise ValueError(str(path) + '：' + str(error)) from error
    return value, hashlib.sha256(raw).hexdigest()


def _plan_hash(plan):
    raw = json.dumps(plan, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')
    return hashlib.sha256(raw).hexdigest()


def merge_plan(workspace, expected_days, expected_daily_minutes):
    """Return (plan, audit report); never edit the workspace or infer constraints."""
    if type(expected_days) is not int or expected_days <= 0:
        raise ValueError('必须独立传入正整数学习天数，不从课程推断')
    if type(expected_daily_minutes) is not int or not 1 <= expected_daily_minutes <= 1440:
        raise ValueError('必须独立传入1至1440的每日分钟数，不从课程推断')
    workspace = Path(workspace).resolve()
    inputs = []

    def read(relative):
        value, digest = _read(workspace / relative)
        inputs.append({'path': relative, 'sha256': digest})
        return value

    course, sources = read('course.json'), read('sources.json')
    if not isinstance(course, dict):
        raise ValueError('course.json必须直接包含课程对象，不是带course键的plan或数组')
    if not isinstance(sources, list):
        raise ValueError('sources.json必须直接包含来源数组')
    # A wrapper or duplicated top-level sections must never silently win a merge.
    if any(key in course for key in ('course', 'sources', 'lessons', 'schema_version')):
        raise ValueError('course.json含顶层计划元数据；仅保留现有course对象')

    lesson_dir = workspace / 'lessons'
    if not lesson_dir.is_dir():
        raise ValueError('缺少lessons目录；请先编写完整分片，不能只合并目录或占位内容')
    batches = []
    for path in lesson_dir.iterdir():
        # Finder metadata is not an authored lesson and can be created by merely
        # opening this folder. Other unexpected files remain actionable errors.
        if path.name == '.DS_Store':
            continue
        match = re.fullmatch(r'([0-9]{3,})-([0-9]{3,})\.json', path.name)
        if not path.is_file() or not match:
            raise ValueError('lessons中存在非约定文件：' + path.name + '；使用NNN-NNN.json课次分片')
        start, end = map(int, match.groups())
        if start < 1 or end < start or end - start + 1 > 5:
            raise ValueError(path.name + '必须包含连续1至5课的有效课次范围')
        if path.name != f'{start:03d}-{end:03d}.json':
            raise ValueError(path.name + '课次范围必须使用至少三位的规范编号')
        batches.append((start, end, path.name))
    if not batches:
        raise ValueError('lessons目录没有课程分片')

    lessons, expected_start = [], 1
    for start, end, filename in sorted(batches):
        if start != expected_start:
            raise ValueError(filename + f'存在缺课或范围重叠；此处应从第{expected_start}课开始')
        batch = read('lessons/' + filename)
        if not isinstance(batch, list) or len(batch) != end - start + 1:
            raise ValueError(filename + '必须为与文件名范围一致的课程数组；分片不能包含course/sources元数据')
        for day, lesson in zip(range(start, end + 1), batch):
            if not isinstance(lesson, dict) or type(lesson.get('day')) is not int or lesson['day'] != day:
                raise ValueError(filename + f'课次必须依次为{start}至{end}；第{day}课内容缺失或乱序，不自动重编号')
            if any(key in lesson for key in ('course', 'sources', 'lessons', 'schema_version')):
                raise ValueError(filename + f'第{day}课含冲突的顶层元数据')
        lessons.extend(batch)
        expected_start = end + 1

    plan = {'schema_version': 1, 'course': course, 'sources': sources, 'lessons': lessons}
    issues = validate_plan(plan, expected_days, expected_daily_minutes)
    if issues:
        raise ValueError('合并后的完整课程校验失败：\n' + '\n'.join(issues))
    # These are evidence inputs for the delivery gate, not instructions or an
    # alternative source of course constraints. Validate JSON, then record bytes.
    for name in ('estimate.json', 'budget.json'):
        if (workspace / name).exists():
            read(name)
    report = {
        'merged': True, 'schema_version': 1,
        'days': course['days'], 'daily_minutes': course['daily_minutes'],
        'batches': len(batches), 'inputs': inputs,
        'plan_sha256': _plan_hash(plan),
        'budget_verified': False, 'facts_verified': False,
    }
    return plan, report


def _write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path, help='合并后的plan.json；不覆盖作者输入')
    parser.add_argument('--report', type=Path, help='可选：输入指纹与合并状态JSON')
    parser.add_argument('--expected-days', required=True, type=int, help='独立传入用户已约定的学习天数')
    parser.add_argument('--expected-daily-minutes', required=True, type=int, help='独立传入用户已约定的每日分钟')
    parser.add_argument('--overwrite', action='store_true', help='检查过目标后替换已有的合并产物')
    args = parser.parse_args()
    try:
        plan, report = merge_plan(args.workspace, args.expected_days, args.expected_daily_minutes)
        outputs = [args.output.resolve()] + ([args.report.resolve()] if args.report else [])
        if len(set(outputs)) != len(outputs):
            raise ValueError('课程输出与报告必须使用不同路径')
        inputs = {(args.workspace / item['path']).resolve() for item in report['inputs']}
        inputs.update((args.workspace / name).resolve() for name in ('course.json', 'sources.json', 'estimate.json', 'budget.json'))
        lesson_dir = (args.workspace / 'lessons').resolve()
        if any(path in inputs or path == lesson_dir or lesson_dir in path.parents for path in outputs):
            raise ValueError('输出不能覆盖course/sources/预算输入或写入lessons分片目录')
        if any(path in other.parents for path in outputs for other in outputs if other != path):
            raise ValueError('课程输出与报告不能互为父目录')
        if any(path.is_dir() or any(parent.exists() and not parent.is_dir() for parent in path.parents) for path in outputs):
            raise ValueError('输出必须为文件，且父路径不能是已有文件')
        if not args.overwrite and any(path.exists() for path in outputs):
            raise ValueError('输出已存在；先检查目标，再用--overwrite更新合并产物')
        _write_json(outputs[0], plan)
        if args.report:
            _write_json(outputs[1], report)
        print(json.dumps({**report, 'plan': str(outputs[0]), 'report': str(outputs[1]) if args.report else None}, ensure_ascii=False))
    except (OSError, ValueError) as error:
        print(json.dumps({'merged': False, 'error': str(error)}, ensure_ascii=False), file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
