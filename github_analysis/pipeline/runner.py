from __future__ import annotations

import sys
from typing import Any

from github_analysis.analysis.pr_builder import build_pull_request_row
from github_analysis.analysis.reviews import collect_review_counts_by_user
from github_analysis.analysis.summaries import compute_user_summaries
from github_analysis.catalog.search import (
    build_activity_catalog,
    build_review_catalog,
    group_prs_by_user,
)
from github_analysis.github.client import GhClient
from github_analysis.github.pulls import PullRequestService
from github_analysis.models import ReportConfig, ReportResult
from github_analysis.time_utils import iso_utc_z, window_bounds_utc


def run_report(config: ReportConfig) -> ReportResult:
    """Collect PR detail rows and per-person summaries for one repository."""
    client = GhClient()
    service = PullRequestService(client, config.repository)
    start_utc, end_exclusive_utc = window_bounds_utc(
        config.start_date, config.end_date, config.report_tz
    )

    print(
        f"Repository: {config.repository.slug} (single repo per run)",
        file=sys.stderr,
    )
    print(
        f"Report timezone: {config.report_tz.key} — window "
        f"{config.start_date.isoformat()} .. {config.end_date.isoformat()} "
        f"(half-open; UTC bounds {iso_utc_z(start_utc)} .. {iso_utc_z(end_exclusive_utc)})",
        file=sys.stderr,
    )
    if config.merged_only:
        print("Mode: merged PRs only", file=sys.stderr)

    print("Phase 1: discovering pull requests…", file=sys.stderr)
    activity_catalog = build_activity_catalog(
        client,
        config.repository,
        start_utc,
        end_exclusive_utc,
        merged_only=config.merged_only,
    )
    review_catalog = build_review_catalog(
        client,
        config.repository,
        start_utc,
        end_exclusive_utc,
        activity_catalog=activity_catalog,
    )
    authors = sorted(
        {login or "(unknown)" for login in activity_catalog.values()},
        key=str.lower,
    )
    print(
        f"Phase 1: {len(activity_catalog)} author-activity PR(s), "
        f"{len(review_catalog)} PR(s) for review scan, {len(authors)} author(s)",
        file=sys.stderr,
    )
    if authors:
        print("Authors:", file=sys.stderr)
        for author in authors:
            print(f"  {author}", file=sys.stderr)
    else:
        print("Authors: (none)", file=sys.stderr)

    print("Phase 2: fetching pull request details…", file=sys.stderr)
    grouped = group_prs_by_user(activity_catalog)
    total_prs = sum(len(numbers) for _, numbers in grouped)
    rows = []
    reviews_cache: dict[int, list[dict[str, Any]]] = {}
    skipped: list[int] = []
    index = 0

    for author, pr_numbers in grouped:
        for pull_number in pr_numbers:
            index += 1
            print(
                f"[{index}/{total_prs}] PR #{pull_number} ({author}) …",
                file=sys.stderr,
                flush=True,
            )
            try:
                row, reviews = build_pull_request_row(
                    service, pull_number, report_author=author
                )
                rows.append(row)
                reviews_cache[pull_number] = reviews
                print(f"    → branch {row.branch!r} (done)", file=sys.stderr, flush=True)
            except Exception as exc:
                skipped.append(pull_number)
                print(f"    → skip PR #{pull_number}: {exc}", file=sys.stderr, flush=True)

    print("Phase 3: building team summary…", file=sys.stderr)
    review_counts = collect_review_counts_by_user(
        service,
        list(review_catalog.keys()),
        start_utc,
        end_exclusive_utc,
        reviews_cache=reviews_cache,
    )
    summaries = compute_user_summaries(rows, review_counts)
    print(
        f"Done: {len(rows)} detail row(s); {len(summaries)} person(s) in summary; "
        f"skipped {len(skipped)} PR(s).",
        file=sys.stderr,
    )

    return ReportResult(
        config=config,
        rows=rows,
        summaries=summaries,
        skipped_pr_numbers=skipped,
        start_utc=start_utc,
        end_exclusive_utc=end_exclusive_utc,
    )
