from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from statistics import median

from github_analysis.models import PullRequestRow

SECONDS_PER_DAY = 24 * 60 * 60


@dataclass(frozen=True)
class TimeMetrics:
    avg_feedback_hours: float | None
    avg_approval_hours: float | None
    avg_merge_hours: float | None
    median_merge_hours: float | None
    p90_merge_hours: float | None
    approval_to_merge_hours: float | None
    avg_open_age_hours: float | None
    stale_rate: float | None
    feedback_target_rate: float | None
    merge_target_rate: float | None

    def to_payload(self) -> dict[str, float | None]:
        return {
            "avgFeedbackHours": self.avg_feedback_hours,
            "avgApprovalHours": self.avg_approval_hours,
            "avgMergeHours": self.avg_merge_hours,
            "medianMergeHours": self.median_merge_hours,
            "p90MergeHours": self.p90_merge_hours,
            "approvalToMergeHours": self.approval_to_merge_hours,
            "avgOpenAgeHours": self.avg_open_age_hours,
            "staleRate": self.stale_rate,
            "feedbackTargetRate": self.feedback_target_rate,
            "mergeTargetRate": self.merge_target_rate,
        }


def hours_between(start: datetime | None, end: datetime | None) -> float | None:
    if start is None or end is None:
        return None
    return (end - start).total_seconds() / 3600.0


def average(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def percentile_90(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, int((len(ordered) - 1) * 0.9)))
    return ordered[index]


def percent(numerator: int | float, denominator: int | float) -> float | None:
    if denominator == 0:
        return None
    return (float(numerator) / float(denominator)) * 100.0


def days_between(start: datetime | None, end: datetime | None) -> float:
    if start is None or end is None:
        return 1.0
    return max((end - start).total_seconds() / SECONDS_PER_DAY, 1.0)


def per_active_week(count: int, eligible_days: float) -> float:
    return (float(count) / max(eligible_days, 1.0)) * 7.0


def numeric_string(value: str) -> float | None:
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def time_metrics(
    rows: list[PullRequestRow],
    *,
    end_at: datetime | None,
    stale_hours: float = 24 * 7,
    feedback_target_hours: float = 48,
    merge_target_hours: float = 72,
) -> TimeMetrics:
    feedback = [
        value
        for row in rows
        if (value := hours_between(row.pr_created, row.first_feedback)) is not None
    ]
    approval = [
        value
        for row in rows
        if (value := hours_between(row.pr_created, row.approved)) is not None
    ]
    merge = [
        value
        for row in rows
        if (value := hours_between(row.pr_created, row.merged)) is not None
    ]
    approval_to_merge = [
        value
        for row in rows
        if (value := hours_between(row.approved, row.merged)) is not None
    ]
    open_age = [
        value
        for row in rows
        if row.merged is None
        and row.closed_at is None
        and (value := hours_between(row.pr_created, end_at)) is not None
    ]
    stale_open = [value for value in open_age if value > stale_hours]
    return TimeMetrics(
        avg_feedback_hours=average(feedback),
        avg_approval_hours=average(approval),
        avg_merge_hours=average(merge),
        median_merge_hours=median(merge) if merge else None,
        p90_merge_hours=percentile_90(merge),
        approval_to_merge_hours=average(approval_to_merge),
        avg_open_age_hours=average(open_age),
        stale_rate=percent(len(stale_open), len(open_age)),
        feedback_target_rate=percent(
            sum(1 for value in feedback if value <= feedback_target_hours),
            len(feedback),
        ),
        merge_target_rate=percent(
            sum(1 for value in merge if value <= merge_target_hours),
            len(merge),
        ),
    )

