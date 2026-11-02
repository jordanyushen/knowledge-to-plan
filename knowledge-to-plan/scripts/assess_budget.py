#!/usr/bin/env python3
"""Compare a supplied learning-time estimate with an unchanged time budget.

The caller must supply a grounded estimate range that already includes teaching,
practice, review, and tests. This script does not infer learning time from pages,
topics, or a learner's background. The buffer is an additional uncertainty reserve.
Recommendations are arithmetic alternatives, not changes to the user's plan.
The script only prints JSON; it does not write files or take external actions.
"""

from __future__ import annotations

import argparse
from fractions import Fraction
import json
import math
from typing import Any


def _positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise argparse.ArgumentTypeError("must be a positive integer") from None
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return parsed


def _finite_nonnegative(value: str) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        raise argparse.ArgumentTypeError("must be a finite number at least 0") from None
    if not math.isfinite(parsed) or parsed < 0:
        raise argparse.ArgumentTypeError("must be a finite number at least 0")
    return parsed


def _buffer_percent(value: str) -> float:
    parsed = _finite_nonnegative(value)
    if parsed >= 100:
        raise argparse.ArgumentTypeError("must be at least 0 and less than 100")
    return parsed


def _number(value: Any, name: str) -> float:
    """Validate programmatic calls as well as the command-line interface."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite number")
    try:
        number = float(value)
    except (OverflowError, ValueError):
        raise ValueError(f"{name} must be a finite number") from None
    if not math.isfinite(number):
        raise ValueError(f"{name} must be a finite number")
    return number


def _positive_target(value: Fraction) -> int:
    """Round a required budget upward, retaining positive plan constraints."""
    return max(1, (value.numerator + value.denominator - 1) // value.denominator)


def assess_budget(
    days: int,
    minutes: int,
    estimated_hours_low: float,
    estimated_hours_high: float,
    buffer_percent: float = 15.0,
) -> dict[str, Any]:
    """Assess caller-supplied estimates; do not derive pedagogical estimates.

    Recommended days hold daily minutes fixed. Recommended daily minutes hold
    days fixed. Both retain the requested buffer and have a minimum value of 1,
    including when the supplied estimate is zero.
    """
    for name, value in (("days", days), ("minutes", minutes)):
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(f"{name} must be a positive integer")
    if minutes > 1440:
        raise ValueError('minutes cannot exceed 1440 in one day')
    low = _number(estimated_hours_low, "estimated_hours_low")
    high = _number(estimated_hours_high, "estimated_hours_high")
    buffer = _number(buffer_percent, "buffer_percent")
    if low < 0 or high < 0:
        raise ValueError("estimated hours must be at least 0")
    if high < low:
        raise ValueError("estimated_hours_high must be at least estimated_hours_low")
    if not 0 <= buffer < 100:
        raise ValueError("buffer_percent must be at least 0 and less than 100")

    # Exact decimal fractions keep boundary comparisons and upward rounding
    # stable and avoid overflowing while calculating recommended integers.
    remaining = 1 - Fraction(str(buffer)) / 100
    available = Fraction(days * minutes, 60)
    usable = available * remaining
    low_hours, high_hours = Fraction(str(low)), Fraction(str(high))
    try:
        available_hours, usable_hours = float(available), float(usable)
    except OverflowError:
        raise ValueError("time budget is too large to express as finite hours") from None
    if not math.isfinite(available_hours) or not math.isfinite(usable_hours):
        raise ValueError("time budget is too large to express as finite hours")

    if high_hours <= usable:
        status = "fits"
    elif low_hours <= usable:
        status = "borderline"
    else:
        status = "insufficient"

    total_days = {
        "low": _positive_target(low_hours * 60 / (minutes * remaining)),
        "high": _positive_target(high_hours * 60 / (minutes * remaining)),
        "fixed_daily_minutes": minutes,
    }
    daily_minutes = {
        "low": _positive_target(low_hours * 60 / (days * remaining)),
        "high": _positive_target(high_hours * 60 / (days * remaining)),
        "fixed_total_days": days,
        "low_within_24_hours": _positive_target(low_hours * 60 / (days * remaining)) <= 1440,
        "high_within_24_hours": _positive_target(high_hours * 60 / (days * remaining)) <= 1440,
    }
    daily_minutes['feasibility_note'] = (
        'Even the low estimate needs more than 1440 minutes/day; this alternative is impossible. Extend duration or reduce scope.'
        if not daily_minutes['low_within_24_hours'] else
        'The high estimate exceeds 1440 minutes/day; only part of this arithmetic range fits in one day. Check realistic human availability.'
        if not daily_minutes['high_within_24_hours'] else
        'Arithmetic range fits within 24 hours; still check the learner\'s actual availability and workload.'
    )
    options = []
    if status != "fits":
        options = [
            {
                "option": "extend_duration",
                "description": "Keep scope and daily minutes; consider the recommended total days range.",
            },
            {
                "option": "increase_daily_time",
                "description": "Keep scope and total days; consider the recommended daily minutes range.",
                "possible_within_24_hours": daily_minutes['low_within_24_hours'],
            },
            {
                "option": "reduce_scope",
                "description": "Define a smaller subset, then supply a new grounded estimate for it.",
            },
            {
                "option": "core_first",
                "description": "Prioritize essential concepts and practice; estimate remaining material as a separate phase.",
            },
        ]

    return {
        "current_plan": {
            "days": days,
            "daily_minutes": minutes,
            "buffer_percent": buffer,
        },
        "available_hours": available_hours,
        "usable_hours": usable_hours,
        "estimate_range": {"low": low, "high": high, "unit": "hours"},
        "status": status,
        "recommended_total_days_range": total_days,
        "recommended_daily_minutes_range": daily_minutes,
        "recommendation_rules": {
            "rounding": "up to the next whole unit, minimum 1",
            "buffer_percent": buffer,
            "automatic_plan_changes": False,
        },
        "candidate_options": options,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=_positive_int, required=True)
    parser.add_argument("--minutes", type=_positive_int, required=True, help="Daily minutes.")
    parser.add_argument("--estimated-hours-low", type=_finite_nonnegative, required=True)
    parser.add_argument("--estimated-hours-high", type=_finite_nonnegative, required=True)
    parser.add_argument("--buffer-percent", type=_buffer_percent, default=15.0)
    parser.add_argument("--pretty", action="store_true", help="Indent the output JSON.")
    args = parser.parse_args()
    try:
        result = assess_budget(
            days=args.days,
            minutes=args.minutes,
            estimated_hours_low=args.estimated_hours_low,
            estimated_hours_high=args.estimated_hours_high,
            buffer_percent=args.buffer_percent,
        )
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2 if args.pretty else None))


if __name__ == "__main__":
    main()
