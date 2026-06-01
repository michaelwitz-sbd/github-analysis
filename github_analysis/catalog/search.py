from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from github_analysis.config import SEARCH_MAX_PAGES
from github_analysis.github.client import GhClient
from github_analysis.models import RepositoryRef
from github_analysis.time_utils import iso_utc_z


def _catalog_from_queries(client: GhClient, queries: list[str]) -> dict[int, str]:
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


def build_activity_catalog(
    client: GhClient,
    repository: RepositoryRef,
    start_inclusive_utc: datetime,
    end_exclusive_utc: datetime,
    *,
    merged_only: bool = False,
) -> dict[int, str]:
    start = iso_utc_z(start_inclusive_utc)
    end = iso_utc_z(end_exclusive_utc)
    base = _repo_pr_base(repository)
    queries = [f"{base} is:merged merged:>={start} merged:<{end}"]
    if not merged_only:
        queries.append(f"{base} created:>={start} created:<{end}")
    return _catalog_from_queries(client, queries)


def build_review_catalog(
    client: GhClient,
    repository: RepositoryRef,
    start_inclusive_utc: datetime,
    end_exclusive_utc: datetime,
    *,
    activity_catalog: dict[int, str],
) -> dict[int, str]:
    start = iso_utc_z(start_inclusive_utc)
    end = iso_utc_z(end_exclusive_utc)
    base = _repo_pr_base(repository)
    catalog = dict(activity_catalog)
    catalog.update(
        _catalog_from_queries(client, [f"{base} updated:>={start} updated:<{end}"])
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
