#!/usr/bin/env python3
"""Validate a KnowledgeToPlan course; structure checks do not verify teaching facts."""
import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

from stem_content import validate_section_visuals
from timezone_support import resolve_timezone


def valid_date(value):
    try:
        return isinstance(value, str) and dt.date.fromisoformat(value).isoformat() == value
    except (ValueError, TypeError):
        return False


def positive_int(value):
    return type(value) is int and value > 0


def text(value):
    return isinstance(value, str) and bool(value.strip())


def text_list(value):
    return isinstance(value, list) and bool(value) and all(text(x) for x in value)


def validate_plan(data, expected_days=None, expected_daily_minutes=None):
    errors = []
    if not isinstance(data, dict):
        return ['根对象必须是JSON对象']
    if type(data.get('schema_version')) is not int or data.get('schema_version') != 1:
        errors.append('schema_version必须为整数1')
    course = data.get('course')
    if not isinstance(course, dict):
        return errors + ['course必须是对象']
    for key in ['id', 'title', 'goal', 'background', 'timezone']:
        if not text(course.get(key)):
            errors.append('course.' + key + '必须是非空字符串')
    days, budget = course.get('days'), course.get('daily_minutes')
    if not positive_int(days):
        errors.append('course.days必须为正整数')
    if not positive_int(budget) or budget > 1440:
        errors.append('course.daily_minutes必须为1至1440的整数')
    if expected_days is not None:
        if not positive_int(expected_days):
            errors.append('外部约定的expected_days必须为正整数')
        elif days != expected_days:
            errors.append(f'计划天数{days}与用户约定{expected_days}天不一致')
    if expected_daily_minutes is not None:
        if not positive_int(expected_daily_minutes) or expected_daily_minutes > 1440:
            errors.append('外部约定的expected_daily_minutes必须为1至1440的整数')
        elif budget != expected_daily_minutes:
            errors.append(f'每日预算{budget}与用户约定{expected_daily_minutes}分钟不一致')
    if text(course.get('timezone')):
        try:
            resolve_timezone(course['timezone'])
        except ValueError as error:
            errors.append('course.timezone：' + str(error))
    if 'start_date' in course and not valid_date(course['start_date']):
        errors.append('course.start_date必须为YYYY-MM-DD')
    if 'study_time' in course and (not isinstance(course['study_time'], str) or not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', course['study_time'])):
        errors.append('course.study_time必须为24小时制HH:MM')
    if 'study_dates' in course:
        dates = course['study_dates']
        if not isinstance(dates, list) or not positive_int(days) or len(dates) != days or not all(valid_date(x) for x in dates):
            errors.append('course.study_dates必须恰好包含days个有效日期')
        elif dates != sorted(set(dates)):
            errors.append('course.study_dates必须递增且无重复')
        elif 'start_date' in course and dates[0] != course['start_date']:
            errors.append('start_date与study_dates第一个日期不一致')
    sources, source_ids = data.get('sources'), set()
    if not isinstance(sources, list) or not sources:
        errors.append('sources必须至少有一个已定位来源')
        sources = []
    for i, source in enumerate(sources):
        p = f'sources[{i}]'
        if not isinstance(source, dict):
            errors.append(p + '必须是对象')
            continue
        sid = source.get('id')
        if not text(sid) or (text(sid) and sid in source_ids):
            errors.append(p + '.id缺失或重复')
        elif text(sid):
            source_ids.add(sid)
        if not text(source.get('title')):
            errors.append(p + '.title缺失')
        if not any(text(source.get(k)) for k in ['url', 'path', 'locator']):
            errors.append(p + '缺少url/path/locator定位信息')
        if source.get('url') is not None:
            u = urlparse(source['url']) if isinstance(source['url'], str) else None
            if not u or u.scheme not in ['http', 'https'] or not u.netloc:
                errors.append(p + '.url只支持有效http(s)链接，本地文件请用path')
    lessons, lesson_ids = data.get('lessons'), set()
    if not isinstance(lessons, list):
        return errors + ['lessons必须是数组']
    if positive_int(days) and len(lessons) != days:
        errors.append(f'需要{days}课，实际{len(lessons)}课')
    for i, lesson in enumerate(lessons):
        p = f'lessons[{i}]'
        if not isinstance(lesson, dict):
            errors.append(p + '必须是对象')
            continue
        if type(lesson.get('day')) is not int or lesson['day'] != i + 1:
            errors.append(p + '.day必须按顺序连续1至days')
        lid = lesson.get('id')
        if not text(lid) or (text(lid) and lid in lesson_ids):
            errors.append(p + '.id缺失或重复')
        elif text(lid):
            lesson_ids.add(lid)
        for key in ['title']:
            if not text(lesson.get(key)):
                errors.append(p + '.' + key + '缺失')
        for key in ['objectives', 'takeaways', 'source_ids']:
            if not text_list(lesson.get(key)):
                errors.append(p + '.' + key + '必须为非空字符串数组')
        refs = lesson.get('source_ids')
        if text_list(refs) and (len(set(refs)) != len(refs) or any(s not in source_ids for s in refs)):
            errors.append(p + '.source_ids存在重复或未知来源')
        acts, minutes = lesson.get('activities'), 0
        if not isinstance(acts, list) or not acts:
            errors.append(p + '.activities必须含分钟分配')
            acts = []
        for a in acts:
            if not isinstance(a, dict) or not text(a.get('kind')) or not positive_int(a.get('minutes')):
                errors.append(p + '.activities每项需kind与正整数minutes')
            else:
                minutes += a['minutes']
        if positive_int(budget) and minutes > budget:
            errors.append(f'{p}活动{minutes}分钟超过每日预算{budget}分钟')
        sections = lesson.get('sections')
        if not isinstance(sections, list) or not sections:
            errors.append(p + '.sections必须包含实际讲解')
            sections = []
        for section_index, s in enumerate(sections):
            if not isinstance(s, dict) or not text(s.get('title')) or not text(s.get('body')):
                errors.append(p + '.sections每项需title与body')
            elif s['body'].strip().lower() in ['todo', 'tbd', 'placeholder', '待补充', '待完善', '待生成']:
                errors.append(p + '.sections包含占位文本')
            if isinstance(s, dict):
                lesson_refs = set(refs) if text_list(refs) else set()
                errors.extend(validate_section_visuals(s, f'{p}.sections[{section_index}]', source_ids, lesson_refs))
        if 'review_of' in lesson and (not isinstance(lesson['review_of'], list) or any(type(n) is not int or n < 1 or n >= i + 1 for n in lesson['review_of'])):
            errors.append(p + '.review_of只能引用此前课次')
        questions, qids = lesson.get('questions'), set()
        if not isinstance(questions, list) or not questions:
            errors.append(p + '.questions至少需要一道可判断的题')
            questions = []
        for j, q in enumerate(questions):
            qp = f'{p}.questions[{j}]'
            if not isinstance(q, dict):
                errors.append(qp + '必须是对象')
                continue
            qid = q.get('id')
            if not text(qid) or (text(qid) and qid in qids):
                errors.append(qp + '.id缺失或课内重复')
            elif text(qid):
                qids.add(qid)
            if not text(q.get('prompt')):
                errors.append(qp + '.prompt缺失')
            options = q.get('options')
            options_ok = text_list(options) and len(options) >= 2
            if not options_ok or len(set(x.strip() for x in options)) != len(options):
                errors.append(qp + '.options至少有两个不同选项')
            correct = q.get('correct_index')
            if type(correct) is not int or not options_ok or not 0 <= correct < len(options):
                errors.append(qp + '.correct_index必须是选项内的整数索引')
            if not text_list(q.get('explanations')) or not options_ok or len(q['explanations']) != len(options):
                errors.append(qp + '.explanations必须覆盖每个选项')
    return errors


def load_validated(path, expected_days=None, expected_daily_minutes=None):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    issues = validate_plan(data, expected_days, expected_daily_minutes)
    if issues:
        raise ValueError('\n'.join(issues))
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('plan', type=Path)
    parser.add_argument('--expected-days', type=int, help='从用户已确认要求独立传入，不从待校验JSON抄回')
    parser.add_argument('--expected-daily-minutes', type=int, help='用户已确认的每日预算')
    args = parser.parse_args()
    try:
        data = load_validated(args.plan, args.expected_days, args.expected_daily_minutes)
    except (ValueError, OSError) as error:
        print(json.dumps({'valid': False, 'error': str(error)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps({'valid': True, 'days': data['course']['days'], 'daily_minutes': data['course']['daily_minutes'], 'questions': sum(len(l['questions']) for l in data['lessons']), 'facts_verified': False}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
