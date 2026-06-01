from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any, Optional

from github_analysis.github.pulls import PullRequestService
from github_analysis.time_utils import parse_github_ts


def reviewers_in_window(
    reviews: list[dict[str, Any]],
    start_inclusive_utc: datetime,
    end_exclusive_utc: datetime,
) -> set[str]:
    reviewers: set[str] = set()
    for review in reviews:
        submitted = parse_github_ts(review.get("submitted_at"))
        if submitted is None:
            continue
        if submitted < start_inclusive_utc or submitted >= end_exclusive_utc:
            continue
        login = ((review.get("user") or {}).get("login")) or ""
        if login:
            reviewers.add(login)
    return reviewers


def collect_review_counts_by_user(
    service: PullRequestService,
    pull_numbers: list[int],
    start_inclusive_utc: datetime,
    end_exclusive_utc: datetime,
    *,
    reviews_cache: Optional[dict[int, list[dict[str, Any]]]] = None,
) -> dict[str, int]:
    cache = reviews_cache if reviews_cache is not None else {}
    counts: dict[str, set[int]] = defaultdict(set)
    for pull_number in sorted(set(pull_numbers)):
        if pull_number not in cache:
            cache[pull_number] = service.reviews(pull_number)
        for login in reviewers_in_window(
            cache[pull_number], start_inclusive_utc, end_exclusive_utc
        ):
            counts[login].add(pull_number)
    return {login: len(prs) for login, prs in counts.items()}
