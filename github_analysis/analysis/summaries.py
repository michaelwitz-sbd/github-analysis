from __future__ import annotations

from collections import defaultdict

from github_analysis.models import PullRequestRow, UserSummary


def _hours_created_to_merged(row: PullRequestRow) -> float | None:
    if row.pr_created is None or row.merged is None:
        return None
    return (row.merged - row.pr_created).total_seconds() / 3600.0


def _format_hours(value: float) -> str:
    return f"{value:.2f}"


def _merge_cycle_stats(authored: list[PullRequestRow]) -> tuple[str, str, str]:
    """Min, max, and mean hours from PR open to merge for authored merged PRs."""
    hours = [value for row in authored if (value := _hours_created_to_merged(row)) is not None]
    if not hours:
        return "", "", ""
    return (
        _format_hours(min(hours)),
        _format_hours(max(hours)),
        _format_hours(sum(hours) / len(hours)),
    )


def compute_user_summaries(
    rows: list[PullRequestRow],
    review_counts_by_user: dict[str, int],
    approval_counts_by_user: dict[str, int],
) -> list[UserSummary]:
    """Roll up PR creator, reviewer, and approver metrics to one row per GitHub login."""
    by_creator: dict[str, list[PullRequestRow]] = defaultdict(list)
    for row in rows:
        by_creator[row.author or "(unknown)"].append(row)

    all_users = sorted(
        set(by_creator.keys())
        | set(review_counts_by_user.keys())
        | set(approval_counts_by_user.keys()),
        key=str.lower,
    )
    summaries: list[UserSummary] = []
    for user in all_users:
        authored = by_creator.get(user, [])
        merged = sum(1 for row in authored if row.merged is not None)
        open_count = len(authored) - merged
        if authored:
            avg_added = sum(row.pr_files_added for row in authored) / len(authored)
            avg_modified = sum(row.pr_files_modified for row in authored) / len(authored)
            avg_added_s = f"{avg_added:.2f}"
            avg_modified_s = f"{avg_modified:.2f}"
        else:
            avg_added_s = ""
            avg_modified_s = ""
        min_hours, max_hours, avg_hours = _merge_cycle_stats(authored)
        summaries.append(
            UserSummary(
                user=user,
                prs_merged=merged,
                prs_reviewed=review_counts_by_user.get(user, 0),
                prs_approved=approval_counts_by_user.get(user, 0),
                prs_authored=len(authored),
                prs_open=open_count,
                avg_files_added_per_pr=avg_added_s,
                avg_files_changed_per_pr=avg_modified_s,
                min_hours_created_to_merged=min_hours,
                max_hours_created_to_merged=max_hours,
                avg_hours_created_to_merged=avg_hours,
            )
        )
    return summaries
