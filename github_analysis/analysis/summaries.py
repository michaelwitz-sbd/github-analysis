from __future__ import annotations

from collections import defaultdict

from github_analysis.models import PullRequestRow, UserSummary


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
            )
        )
    return summaries
