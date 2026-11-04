#!/usr/bin/env python3
"""Complete-course delivery gate: budget evidence, goal coverage and quality risks.

The low-level build_learning_site remains available for legacy plans and drafts.
Neither entrypoint can certify teaching facts or genuine learner mastery.
"""
import argparse
import json
from pathlib import Path
import sys

from budget_evidence import check_budget_record, load_json
from build_learning_site import build
from lint_pedagogy import lint_pedagogy
from validate_plan import validate_plan


def build_course(plan, estimate, budget, goal_map, output, expected_days,
                 expected_daily_minutes, review=None, calendar=False, overwrite=False):
    errors = validate_plan(plan, expected_days, expected_daily_minutes)
    if errors:
        raise ValueError('\n'.join(errors))
    checked_budget = check_budget_record(plan, estimate, budget, expected_days, expected_daily_minutes)
    if not isinstance(goal_map, dict) or not isinstance(goal_map.get('goals'), list):
        raise ValueError('goal-map.json is required for complete-course delivery')
    mapped = {g.get('id'): g.get('description') for g in goal_map['goals'] if isinstance(g, dict)}
    estimated = {g['id']: g['outcome'] for g in estimate['goals']}
    if mapped != estimated or len(mapped) != len(goal_map['goals']):
        raise ValueError('goal-map goals must match every estimated outcome exactly without duplicates')
    quality = lint_pedagogy(plan, goal_map=goal_map, review=review)
    if not quality['passed']:
        blockers = [i for i in quality['issues'] if i['severity'] == 'error' and not i.get('resolved', False)]
        raise ValueError('teaching quality gate blocked delivery:\n' + '\n'.join(
            i['code'] + ' at ' + i['location'] + ': ' + i['message'] for i in blockers))
    output = Path(output).resolve()
    artifacts = {'estimate.json': estimate, 'budget.json': budget,
                 'goal-map.json': goal_map, 'pedagogy-report.json': quality}
    if review is not None:
        artifacts['review.json'] = review
    names = set(artifacts) | {'index.html', 'plan.json', 'delivery-report.json'}
    if calendar:
        names.add('schedule.ics')
    if not overwrite and any((output / name).exists() for name in names):
        raise ValueError('delivery output already exists; inspect it before using --overwrite')
    report = {
        'delivery_status': 'generated_pending_content_review',
        'course_structure_complete': True,
        'plan_sha256': checked_budget['plan_sha256'],
        'scope': estimate['scope'], 'selected_goal': estimate['selected_goal'],
        'budget_status': checked_budget['status'], 'budget_arithmetic_verified': True,
        'structure_valid': True, 'pedagogy_checks_passed': True,
        'content_review_status': quality['content_review_status'],
        'facts_verified': False, 'time_feasibility': 'estimated',
        'learner_trial': 'not_recorded',
        'note': 'Author-supplied coverage and quality checks passed. Semantic content completeness, facts and task times still require scoped review.'
    }
    artifacts['delivery-report.json'] = report
    # Reject malformed/NaN author metadata before creating any usable course.
    # Goal maps and finding records are evidence shape, not proof of completeness.
    serialized = {name: json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
                  for name, value in artifacts.items()}
    result = build(plan, output, calendar=calendar, overwrite=overwrite,
                   expected_days=expected_days, expected_daily_minutes=expected_daily_minutes)
    for name, value in serialized.items():
        (output / name).write_text(value, encoding='utf-8')
    return {**result, **report, 'report': str(output / 'delivery-report.json')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('plan', 'estimate', 'budget', 'goal-map', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--review', type=Path, help='Exact-plan content findings and per-issue resolutions')
    parser.add_argument('--expected-days', type=int, required=True)
    parser.add_argument('--expected-daily-minutes', type=int, required=True)
    parser.add_argument('--calendar', action='store_true')
    parser.add_argument('--overwrite', action='store_true')
    args = parser.parse_args()
    try:
        result = build_course(load_json(args.plan), load_json(args.estimate), load_json(args.budget),
                              load_json(args.goal_map), args.output, args.expected_days,
                              args.expected_daily_minutes, load_json(args.review) if args.review else None,
                              args.calendar, args.overwrite)
    except (OSError, ValueError, TypeError, KeyError, OverflowError) as error:
        print(json.dumps({'delivered': False, 'error': str(error)}, ensure_ascii=False), file=sys.stderr)
        return 2
    print(json.dumps({'delivered': True, **result}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
