#!/usr/bin/env python3
"""Validate authored lessons and package a dependency-free offline HTML, optionally ICS."""
import argparse
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

from validate_plan import load_validated, validate_plan
from timezone_support import resolve_timezone

ASSETS = Path(__file__).resolve().parents[1] / 'assets' / 'learning-site'


def study_dates(course):
    if course.get('study_dates'):
        return [dt.date.fromisoformat(d) for d in course['study_dates']]
    if not course.get('start_date'):
        raise ValueError('导出日历需要start_date或明确的study_dates')
    start = dt.date.fromisoformat(course['start_date'])
    return [start + dt.timedelta(days=i) for i in range(course['days'])]


def ics_escape(value):
    return str(value).replace('\\', '\\\\').replace('\r\n', '\n').replace('\r', '\n').replace('\n', '\\n').replace(';', '\\;').replace(',', '\\,')


def fold_ics_line(line):
    """RFC5545 limits physical lines to 75 octets; never split a UTF-8 code point."""
    result, part, size = [], '', 0
    for char in line:
        n = len(char.encode('utf-8'))
        if size + n > 75:
            result.append(part)
            part, size = ' ', 1
        part += char
        size += n
    result.append(part)
    return '\r\n'.join(result)


def local_start(day, time_text, zone):
    naive = dt.datetime.combine(day, dt.time.fromisoformat(time_text))
    candidate = naive.replace(tzinfo=zone, fold=0)
    back = candidate.astimezone(dt.timezone.utc).astimezone(zone).replace(tzinfo=None)
    if back != naive:
        raise ValueError(f'{day} {time_text}在该时区不存在（夏令时跳变），请重新选择')
    alternate = naive.replace(tzinfo=zone, fold=1)
    if candidate.utcoffset() != alternate.utcoffset():
        raise ValueError(f'{day} {time_text}在该时区存在两个时刻，请选择明确时刻或用原生日历工具处理')
    return candidate


def make_ics(data):
    c = data['course']
    if not c.get('study_time'):
        raise ValueError('导出日历需要明确的study_time；每天分钟数不是开始时刻')
    dates, zone = study_dates(c), resolve_timezone(c['timezone'])
    stamp = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    lines = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//KnowledgeToPlan//Offline Learning//ZH-CN', 'CALSCALE:GREGORIAN', 'X-WR-CALNAME:' + ics_escape(c['title'])]
    for lesson, date in zip(data['lessons'], dates):
        start = local_start(date, c['study_time'], zone).astimezone(dt.timezone.utc)
        end = start + dt.timedelta(minutes=c['daily_minutes'])
        uid = hashlib.sha256((c['id'] + '|' + lesson['id'] + '|' + date.isoformat()).encode()).hexdigest() + '@knowledge-to-plan'
        acts = '\n'.join(f"{a['kind']}：{a['minutes']}分钟" for a in lesson['activities'])
        description = f"学习目标：{'；'.join(lesson['objectives'])}\n{acts}\n练习：{lesson.get('practice', '完成本课知识检查')}\n打开课程HTML并选择第{lesson['day']}天。\n本文件未检查已有日历冲突，请先检查再导入；不要与已创建的原生日历事件重复导入。"
        lines += ['BEGIN:VEVENT', 'UID:' + uid, 'DTSTAMP:' + stamp,
                  'DTSTART:' + start.strftime('%Y%m%dT%H%M%SZ'),
                  'DTEND:' + end.strftime('%Y%m%dT%H%M%SZ'),
                  'SUMMARY:' + ics_escape(f"D{lesson['day']:03d} {lesson['title']}"),
                  'DESCRIPTION:' + ics_escape(description), 'END:VEVENT']
    lines.append('END:VCALENDAR')
    return '\r\n'.join(fold_ics_line(line) for line in lines) + '\r\n'


def build(data, output, calendar=False, overwrite=False, expected_days=None, expected_daily_minutes=None):
    """No external writes; output and all required assets are on the local filesystem."""
    issues = validate_plan(data, expected_days, expected_daily_minutes)
    if issues:
        raise ValueError('\n'.join(issues))
    output = Path(output).resolve()
    names = ['index.html', 'plan.json'] + (['schedule.ics'] if calendar else [])
    if not overwrite and any((output / n).exists() for n in names):
        raise ValueError('输出已有同名文件；先检查目标，用--overwrite重新生成自己管理的产物')
    template = (ASSETS / 'index.html').read_text(encoding='utf-8')
    for token in ['{{STYLE}}', '{{COURSE_JSON}}', '{{SCRIPT}}']:
        if template.count(token) != 1:
            raise ValueError('模板缺少唯一占位标记：' + token)
    # Replace all markers in one pass so a marker in user text is never interpreted.
    import re
    substitutions = {
        '{{STYLE}}': (ASSETS / 'style.css').read_text(encoding='utf-8'),
        '{{COURSE_JSON}}': json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c').replace('\u2028', '\\u2028').replace('\u2029', '\\u2029'),
        '{{SCRIPT}}': (ASSETS / 'app.js').read_text(encoding='utf-8')
    }
    html = re.sub(r'\{\{(?:STYLE|COURSE_JSON|SCRIPT)\}\}', lambda m: substitutions[m.group()], template)
    ics = make_ics(data) if calendar else None  # Fail before writing any output if schedule is invalid.
    output.mkdir(parents=True, exist_ok=True)
    (output / 'index.html').write_text(html, encoding='utf-8')
    (output / 'plan.json').write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    if ics is not None:
        (output / 'schedule.ics').write_bytes(ics.encode('utf-8'))
    return {'html': str(output / 'index.html'), 'plan': str(output / 'plan.json'), 'calendar': str(output / 'schedule.ics') if calendar else None,
            'days': data['course']['days'], 'daily_minutes': data['course']['daily_minutes'],
            'questions': sum(len(l['questions']) for l in data['lessons']), 'offline_dependencies': 'none', 'calendar_events_created': False}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--plan', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--calendar', action='store_true', help='另行导出ICS；不会加入任何在线日历')
    p.add_argument('--overwrite', action='store_true', help='检查过目标后，重新生成同名产物')
    p.add_argument('--expected-days', type=int, help='用户已确认的学习天数')
    p.add_argument('--expected-daily-minutes', type=int, help='用户已确认的每日预算')
    args = p.parse_args()
    try:
        result = build(load_validated(args.plan), args.output, args.calendar, args.overwrite, args.expected_days, args.expected_daily_minutes)
    except (OSError, ValueError) as error:
        print(json.dumps({'built': False, 'error': str(error)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
