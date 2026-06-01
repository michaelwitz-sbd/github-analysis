from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

from github_analysis.config import SEARCH_MAX_PAGES
from github_analysis.github.client import GhClient
from github_analysis.models import RepositoryRef


def _catalog_from_queries(client: GhClient, queries: list[str]) -> dict[int, str]:
    """Map pull number -> PR creator login (`user` from search; assignees are not used)."""
    catalog: dict[int, str] = {}
    for query in queries:
        for item in client.search_issues(query, max_pages=SEARCH_MAX_PAGES):
            number = item.get("number")
            if number is None:
                continue
            login = ((item.get("user") or {}).get("login")) or ""
            catalog[int(number)] = login
    return catalog


def _repo_pr_base(repository: RepositoryRef) -> str:
    return f"repo:{repository.slug} is:pr"


def _last_inclusive_day(end_exclusive: date) -> date:
    return end_exclusive - timedelta(days=1)


def _calendar_range(field: str, start_inclusive: date, end_exclusive: date) -> str:
    """GitHub search inclusive date range matching the report calendar window."""
    return f"{field}:{start_inclusive.isoformat()}..{_last_inclusive_day(end_exclusive).isoformat()}"


def build_open_at_month_end_candidate_catalog(
    client: GhClient,
    repository: RepositoryRef,
    start_date: date,
    end_date: date,
) -> dict[int, str]:
    """
    PRs that may have been open at month-end (regardless of when created).

    Candidates include PRs still open today, merged after the window, or closed after
    the window — then timestamp checks confirm the month-end snapshot.
    """
    end = end_date.isoformat()
    start = start_date.isoformat()
    last = _last_inclusive_day(end_date).isoformat()
    base = _repo_pr_base(repository)
    queries = [
        f"{base} is:open created:<{end}",
        f"{base} created:<{end} merged:>={end}",
        f"{base} created:<{end} closed:>={end}",
        f"{base} created:<{start} updated:{start}..{last}",
    ]
    catalog: dict[int, str] = {}
    for query in queries:
        catalog.update(_catalog_from_queries(client, [query]))
    return catalog


def build_created_in_window_catalog(
    client: GhClient,
    repository: RepositoryRef,
    start_date: date,
    end_date: date,
) -> dict[int, str]:
    """PRs created (opened) in the calendar window — used for authored/open-at-month-end counts."""
    base = _repo_pr_base(repository)
    return _catalog_from_queries(
        client, [f"{base} {_calendar_range('created', start_date, end_date)}"]
    )


def build_activity_catalog(
    client: GhClient,
    repository: RepositoryRef,
    start_date: date,
    end_date: date,
    *,
    merged_only: bool = False,
) -> dict[int, str]:
    base = _repo_pr_base(repository)
    queries = [f"{base} is:merged {_calendar_range('merged', start_date, end_date)}"]
    if not merged_only:
        queries.append(f"{base} {_calendar_range('created', start_date, end_date)}")
    return _catalog_from_queries(client, queries)


def build_review_catalog(
    client: GhClient,
    repository: RepositoryRef,
    start_date: date,
    end_date: date,
    *,
    activity_catalog: dict[int, str],
) -> dict[int, str]:
    base = _repo_pr_base(repository)
    catalog = dict(activity_catalog)
    catalog.update(
        _catalog_from_queries(
            client, [f"{base} {_calendar_range('updated', start_date, end_date)}"]
        )
    )
    return catalog


def group_prs_by_user(catalog: dict[int, str]) -> list[tuple[str, list[int]]]:
    by_user: dict[str, list[int]] = defaultdict(list)
    for pr_number, login in catalog.items():
        by_user[login or "(unknown)"].append(pr_number)
    return [
        (author, sorted(numbers))
        for author, numbers in sorted(by_user.items(), key=lambda item: item[0].lower())
    ]
