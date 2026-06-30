from __future__ import annotations

import unittest
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from github_analysis.export.html import build_report_payload, render_html
from github_analysis.models import PullRequestRow, ReportConfig, ReportResult, RepositoryRef, UserSummary
from github_analysis.reporting.metrics import (
    days_between,
    percent,
    per_active_week,
    time_metrics,
)
from github_analysis.reporting.periods import bucket_key, split_period


def pr_row(
    number: int,
    author: str,
    created: datetime,
    *,
    feedback_hours: int | None = None,
    approval_hours: int | None = None,
    merge_hours: int | None = None,
    approved_by: str = "",
    lines_added: int | None = 10,
    lines_removed: int | None = 2,
) -> PullRequestRow:
    return PullRequestRow(
        author=author,
        branch=f"feature/{number}",
        pr_number=number,
        pr_url=f"https://example.test/pulls/{number}",
        branch_start=None,
        pr_created=created,
        first_draft=None,
        ready_for_review=None,
        first_feedback=created + timedelta(hours=feedback_hours)
        if feedback_hours is not None
        else None,
        approved=created + timedelta(hours=approval_hours)
        if approval_hours is not None
        else None,
        merged=created + timedelta(hours=merge_hours) if merge_hours is not None else None,
        closed_at=None,
        approved_by=approved_by,
        pr_files_total=3,
        pr_files_added=1,
        pr_files_modified=1,
        pr_files_removed=1,
        pr_lines_added=lines_added,
        pr_lines_removed=lines_removed,
        pr_commits_total=2,
    )


class ReportingMetricTests(unittest.TestCase):
    def test_percent_and_normalization_helpers(self) -> None:
        self.assertEqual(percent(3, 4), 75.0)
        self.assertIsNone(percent(1, 0))
        self.assertEqual(days_between(datetime(2026, 1, 1), datetime(2026, 1, 8)), 7.0)
        self.assertEqual(per_active_week(4, 14), 2.0)

    def test_time_metrics_and_targets(self) -> None:
        base = datetime(2026, 1, 5, tzinfo=timezone.utc)
        rows = [
            pr_row(1, "alice", base, feedback_hours=24, approval_hours=30, merge_hours=48),
            pr_row(2, "alice", base, feedback_hours=72, approval_hours=80, merge_hours=120),
            pr_row(3, "bob", base),
        ]
        metrics = time_metrics(rows, end_at=base + timedelta(days=10))

        self.assertEqual(metrics.avg_feedback_hours, 48.0)
        self.assertEqual(metrics.avg_approval_hours, 55.0)
        self.assertEqual(metrics.avg_merge_hours, 84.0)
        self.assertEqual(metrics.median_merge_hours, 84.0)
        self.assertEqual(metrics.feedback_target_rate, 50.0)
        self.assertEqual(metrics.merge_target_rate, 50.0)
        self.assertEqual(metrics.stale_rate, 100.0)


class PeriodTests(unittest.TestCase):
    def test_weekly_and_monthly_bucket_keys(self) -> None:
        value = datetime(2026, 6, 17, 12, tzinfo=timezone.utc)
        self.assertEqual(bucket_key(value, "weekly"), "2026-06-15")
        self.assertEqual(bucket_key(value, "monthly"), "2026-06-01")

    def test_split_period(self) -> None:
        weekly = split_period(date(2026, 6, 3), date(2026, 6, 18), "weekly")
        monthly = split_period(date(2026, 5, 15), date(2026, 7, 2), "monthly")

        self.assertEqual([bucket.label for bucket in weekly], ["2026-06-01", "2026-06-08", "2026-06-15"])
        self.assertEqual([bucket.label for bucket in monthly], ["2026-05-01", "2026-06-01", "2026-07-01"])


class HtmlRendererTests(unittest.TestCase):
    def test_html_payload_and_rendered_sections(self) -> None:
        tz = ZoneInfo("UTC")
        base = datetime(2026, 6, 1, tzinfo=timezone.utc)
        result = ReportResult(
            config=ReportConfig(
                repository=RepositoryRef("owner", "repo"),
                start_date=date(2026, 6, 1),
                end_date=date(2026, 7, 1),
                report_tz=tz,
                merged_only=True,
            ),
            rows=[
                pr_row(1, "alice", base, feedback_hours=3, approval_hours=5, merge_hours=8, approved_by="bob"),
                pr_row(2, "bob", base + timedelta(days=8), feedback_hours=4, approval_hours=6, merge_hours=10, approved_by="alice"),
            ],
            summaries=[
                UserSummary("alice", 1, 1, 1, 1, 0, 0, "1.0", "3.0"),
                UserSummary("bob", 1, 1, 1, 1, 0, 0, "1.0", "3.0"),
            ],
            start_utc=base,
            end_exclusive_utc=base + timedelta(days=30),
            review_first_activity_by_user={"alice": base, "bob": base},
        )

        payload = build_report_payload([result], bucket_granularity="monthly")
        html = render_html(payload)

        self.assertEqual(payload["bucketGranularity"], "monthly")
        self.assertIn("Metric Formulas & Equations", html)
        self.assertIn("Compare Everyone", html)
        self.assertIn("Teams", html)
        self.assertIn("sortable-table", html)
        self.assertIn("winner-chart", html)


if __name__ == "__main__":
    unittest.main()

