#!/usr/bin/env python3
"""Validate a task-based estimate and bind a reproducible budget to its inputs.

This verifies arithmetic and evidence shape, never the truth of an author's
assumptions or the learning effectiveness of a course. No network or accounts.
"""
import argparse
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import sys

from assess_budget import assess_budget
from validate_plan import validate_plan

TASK_KINDS = {'learn', 'example', 'practice', 'feedback', 'review', 'quiz'}


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(',', ':'), allow_nan=False).encode('utf-8')).hexdigest()


def load_json(path):
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('duplicate JSON key: ' + key)
            result[key] = value
        return result
    def invalid_constant(value):
        raise ValueError('non-finite JSON constant: ' + value)
    return json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=unique_object,
                      parse_constant=invalid_constant)


def required_text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(label + ' must be a nonempty string')
    return value


def text_list(value, label, allow_empty=False):
    if not isinstance(value, list) or (not value and not allow_empty):
        raise ValueError(label + ' must be an array of nonempty strings')
    for item in value:
        required_text(item, label)
    if len(value) != len(set(value)):
        raise ValueError(label + ' must not contain duplicates')
    return value


def positive_number(value, label):
    if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
        raise ValueError(label + ' must be finite and positive')
    return Fraction(str(value))


def evaluate_estimate(estimate, expected_days, expected_daily_minutes, plan=None):
    """Recompute the budget from counts and per-task minutes, never a status flag."""
    if not isinstance(estimate, dict) or type(estimate.get('schema_version')) is not int or estimate['schema_version'] != 1:
        raise ValueError('estimate.schema_version must be 1')
    # Validate independent constraints even before teaching content is authored.
    assess_budget(expected_days, expected_daily_minutes, 0, 0)
    constraints = estimate.get('constraints')
    if (not isinstance(constraints, dict) or
            type(constraints.get('days')) is not int or
            type(constraints.get('daily_minutes')) is not int or
            constraints != {'days': expected_days, 'daily_minutes': expected_daily_minutes}):
        raise ValueError('estimate constraints differ from independently supplied user constraints')
    original = required_text(estimate.get('original_goal'), 'original_goal')
    selected = required_text(estimate.get('selected_goal'), 'selected_goal')
    background = required_text(estimate.get('background'), 'background')
    required_text(estimate.get('prerequisite_basis'), 'prerequisite_basis')
    prerequisites = estimate.get('prerequisites')
    if not isinstance(prerequisites, list):
        raise ValueError('prerequisites must be an array (empty is allowed with prerequisite_basis)')
    for item in prerequisites:
        if not isinstance(item, dict) or item.get('status') not in ('known', 'gap', 'assumed'):
            raise ValueError('prerequisite status must be known, gap or assumed')
        required_text(item.get('skill'), 'prerequisite.skill')
        required_text(item.get('evidence'), 'prerequisite.evidence')
    scope = estimate.get('scope')
    if not isinstance(scope, dict) or scope.get('mode') not in ('full', 'core'):
        raise ValueError('scope.mode must be full or core')
    excluded = text_list(scope.get('excluded'), 'scope.excluded', allow_empty=True)
    if scope['mode'] == 'full' and (original != selected or excluded):
        raise ValueError('full scope must preserve the original goal without exclusions')
    if scope['mode'] == 'core':
        if selected == original or not excluded:
            raise ValueError('core scope needs a distinct selected_goal and explicit exclusions')
        required_text(scope.get('change_basis'), 'scope.change_basis (user choice or explicit core-first boundary)')
    buffer = estimate.get('buffer_percent')
    if type(buffer) not in (int, float) or not math.isfinite(buffer) or not 0 <= buffer < 100:
        raise ValueError('buffer_percent must be finite, at least 0 and less than 100')
    required_text(estimate.get('buffer_reason'), 'buffer_reason (also required when zero)')
    goals = estimate.get('goals')
    if not isinstance(goals, list) or not goals:
        raise ValueError('goals must contain observable outcomes and task estimates')
    ids, kinds, totals = set(), set(), [Fraction(0), Fraction(0)]
    goal_totals = []
    sources = {s['id'] for s in plan['sources']} if plan is not None and not validate_plan(plan) else None
    for index, goal in enumerate(goals):
        label = 'goals[' + str(index) + ']'
        if not isinstance(goal, dict):
            raise ValueError(label + ' must be an object')
        gid = required_text(goal.get('id'), label + '.id')
        if gid in ids:
            raise ValueError('duplicate estimate goal id: ' + gid)
        ids.add(gid)
        required_text(goal.get('outcome'), label + '.outcome')
        required_text(goal.get('basis'), label + '.basis (source locator, task difficulty and quantities)')
        refs = text_list(goal.get('source_ids'), label + '.source_ids')
        if sources is not None and not set(refs).issubset(sources):
            raise ValueError(label + '.source_ids reference unknown plan sources')
        tasks = goal.get('tasks')
        if not isinstance(tasks, list) or not tasks:
            raise ValueError(label + '.tasks must not be empty')
        local_kinds, local = set(), [Fraction(0), Fraction(0)]
        for task in tasks:
            if not isinstance(task, dict) or task.get('kind') not in TASK_KINDS:
                raise ValueError(label + '.tasks.kind must be ' + ', '.join(sorted(TASK_KINDS)))
            required_text(task.get('description'), label + '.task.description')
            required_text(task.get('basis'), label + '.task.basis')
            count = task.get('count')
            if type(count) is not int or count <= 0:
                raise ValueError(label + '.task.count must be a positive integer')
            low = positive_number(task.get('minutes_low'), label + '.task.minutes_low')
            high = positive_number(task.get('minutes_high'), label + '.task.minutes_high')
            if high < low:
                raise ValueError(label + '.task.minutes_high must be >= minutes_low')
            local[0] += count * low
            local[1] += count * high
            local_kinds.add(task['kind'])
        if not {'practice', 'quiz'}.issubset(local_kinds):
            raise ValueError(label + ' must budget independent practice and an assessment')
        kinds.update(local_kinds)
        totals[0] += local[0]
        totals[1] += local[1]
        goal_totals.append({'id': gid, 'low_minutes': float(local[0]), 'high_minutes': float(local[1])})
    if not TASK_KINDS.issubset(kinds):
        raise ValueError('estimate omits activity categories: ' + ', '.join(sorted(TASK_KINDS - kinds)))
    if plan is not None:
        errors = validate_plan(plan, expected_days, expected_daily_minutes)
        if errors:
            raise ValueError('\n'.join(errors))
        if plan['course']['goal'] != selected or plan['course']['background'] != background:
            raise ValueError('plan goal/background differ from the estimate; revise and recompute')
    assessment = assess_budget(expected_days, expected_daily_minutes, totals[0] / 60, totals[1] / 60, buffer)
    return {
        'schema_version': 1, 'estimate_sha256': fingerprint(estimate),
        'plan_sha256': fingerprint(plan) if plan is not None else None,
        'original_goal': original, 'selected_goal': selected, 'scope': scope,
        'goal_totals': goal_totals,
        'estimated_minutes': {'low': float(totals[0]), 'high': float(totals[1])},
        'assessment': assessment, 'status': assessment['status'],
        'time_feasibility': 'estimated', 'evidence_truth_verified': False,
        'note': 'Arithmetic and input binding only; source, scope and task-time assumptions require review.'
    }


def check_budget_record(plan, estimate, record, expected_days, expected_daily_minutes):
    expected = evaluate_estimate(estimate, expected_days, expected_daily_minutes, plan)
    if fingerprint(record) != fingerprint(expected):
        raise ValueError('budget.json is stale, unbound or modified; recompute it from this estimate and plan')
    if expected['status'] == 'insufficient':
        raise ValueError('insufficient budget: present alternatives before generating a complete course')
    if expected['status'] == 'borderline' and estimate['scope']['mode'] != 'core':
        raise ValueError('borderline budget: only explicitly bounded core scope may be delivered')
    return expected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--estimate', type=Path, required=True)
    parser.add_argument('--plan', type=Path, help='Bind to the final plan; omit only for pre-authoring assessment')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--expected-days', type=int, required=True)
    parser.add_argument('--expected-daily-minutes', type=int, required=True)
    parser.add_argument('--overwrite', action='store_true')
    args = parser.parse_args()
    try:
        if args.output.resolve() in {args.estimate.resolve(), args.plan.resolve() if args.plan else None}:
            raise ValueError('output must not overwrite the estimate or plan input')
        if args.output.exists() and not args.overwrite:
            raise ValueError('output exists; inspect it before using --overwrite')
        record = evaluate_estimate(load_json(args.estimate), args.expected_days, args.expected_daily_minutes,
                                   load_json(args.plan) if args.plan else None)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(record, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    except (ValueError, OSError, TypeError, OverflowError) as error:
        print(json.dumps({'budget_recorded': False, 'error': str(error)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps({'budget_recorded': True, 'status': record['status'], 'plan_bound': bool(record['plan_sha256']),
                      'time_feasibility': 'estimated', 'output': str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
