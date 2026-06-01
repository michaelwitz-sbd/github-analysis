from __future__ import annotations

from collections import defaultdict

from github_analysis.models import PullRequestRow, UserSummary


def compute_user_summaries(
    rows: list[PullRequestRow],
    review_counts_by_user: dict[str, int],
) -> list[UserSummary]:
    by_author: dict[str, list[PullRequestRow]] = defaultdict(list)
    for row in rows:
        by_author[row.author or "(unknown)"].append(row)

    all_users = sorted(
        set(by_author.keys()) | set(review_counts_by_user.keys()),
        key=str.lower,
    )
    summaries: list[UserSummary] = []
    for user in all_users:
        authored = by_author.get(user, [])
        merged = sum(1 for row in authored if row.merged is not None)
        open_count = len(authored) - merged
        if authored:
            avg_changed = sum(row.pr_files_total for row in authored) / len(authored)
            avg_added = sum(row.pr_files_added for row in authored) / len(authored)
            avg_changed_s = f"{avg_changed:.2f}"
            avg_added_s = f"{avg_added:.2f}"
        else:
            avg_changed_s = ""
            avg_added_s = ""
        summaries.append(
            UserSummary(
                user=user,
                prs_authored=len(authored),
                prs_merged=merged,
                prs_open=open_count,
                prs_reviewed=review_counts_by_user.get(user, 0),
                avg_files_changed=avg_changed_s,
                avg_files_added=avg_added_s,
            )
        )
    return summaries
