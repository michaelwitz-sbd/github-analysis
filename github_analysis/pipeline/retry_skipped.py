from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Optional

from github_analysis.analysis.reviews import (
    collect_approval_counts_by_user,
    collect_first_review_activity_by_user,
    collect_review_counts_by_user,
)
from github_analysis.cache.raw_store import (
    _legacy_merged_pr_states_from_rows,
    _pr_states_from_json,
    _row_from_dict,
    load_raw_payload,
    update_payload_after_row_merge,
)
from github_analysis.config import PR_RESOURCE_FETCH_WORKERS
from github_analysis.github.client import GhClient
from github_analysis.github.pulls import PullRequestService
from github_analysis.models import ReportConfig, ReportResult, RepositoryRef
from github_analysis.pipeline.runner import _fetch_pr_details


def _merge_review_counts(existing: dict[str, int], added: dict[str, int]) -> dict[str, int]:
    merged = dict(existing)
    for user, count in added.items():
        merged[user] = merged.get(user, 0) + count
    return merged


def _merge_first_review_activity(
    existing: dict[str, datetime],
    added: dict[str, datetime],
) -> dict[str, datetime]:
    merged = dict(existing)
    for user, submitted in added.items():
        current = merged.get(user)
        if current is None or submitted < current:
            merged[user] = submitted
    return merged


def retry_skipped_in_payload(
    payload: dict[str, Any],
    *,
    workers: int = 1,
    resource_workers: int = PR_RESOURCE_FETCH_WORKERS,
    emit: Callable[[str], None] = lambda _msg: None,
    emit_error: Callable[[str], None] = lambda _msg: None,
) -> tuple[ReportResult, dict[str, Any], list[int], list[int]]:
    """Fetch PR details that previously failed and merge them into a raw cache payload."""
    if workers < 1:
        raise ValueError("workers must be at least 1")
    if resource_workers < 1:
        raise ValueError("resource_workers must be at least 1")

    skipped = [int(n) for n in payload.get("skipped_pr_numbers", [])]
    if not skipped:
        result = load_raw_payload(payload)
        return result, payload, [], []

    cfg = payload["config"]
    repository = RepositoryRef(
        owner=cfg["repository"]["owner"],
        name=cfg["repository"]["name"],
    )
    baseline = load_raw_payload(payload)
    start_utc = baseline.start_utc
    end_exclusive_utc = baseline.end_exclusive_utc

    activity_catalog = {
        int(key): value for key, value in (payload.get("activity_catalog") or {}).items()
    }
    by_author: dict[str, list[int]] = {}
    for pull_number in skipped:
        author = activity_catalog.get(pull_number, "(unknown)")
        by_author.setdefault(author, []).append(pull_number)
    grouped = [
        (author, sorted(numbers))
        for author, numbers in sorted(by_author.items(), key=lambda item: item[0].lower())
    ]

    emit(f"Retrying {len(skipped)} skipped PR(s) for {repository.slug}")
    new_rows, reviews_cache, still_skipped = _fetch_pr_details(
        repository=repository,
        grouped=grouped,
        workers=workers,
        resource_workers=resource_workers,
        emit=emit,
        emit_error=emit_error,
    )

    existing_rows = [_row_from_dict(row) for row in payload.get("rows", [])]
    existing_by_pr = {row.pr_number: row for row in existing_rows}
    for row in new_rows:
        existing_by_pr[row.pr_number] = row
    merged_rows = sorted(existing_by_pr.values(), key=lambda item: item.pr_number)
    recovered = sorted(row.pr_number for row in new_rows)

    review_counts = {
        key: int(value) for key, value in (payload.get("review_counts_by_user") or {}).items()
    }
    approval_counts = {
        key: int(value) for key, value in (payload.get("approval_counts_by_user") or {}).items()
    }
    review_first_activity = dict(baseline.review_first_activity_by_user)

    if recovered and start_utc is not None and end_exclusive_utc is not None:
        service = PullRequestService(GhClient(), repository)
        review_counts = _merge_review_counts(
            review_counts,
            collect_review_counts_by_user(
                service,
                recovered,
                start_utc,
                end_exclusive_utc,
                reviews_cache=reviews_cache,
            ),
        )
        approval_counts = _merge_review_counts(
            approval_counts,
            collect_approval_counts_by_user(
                service,
                recovered,
                start_utc,
                end_exclusive_utc,
                reviews_cache=reviews_cache,
            ),
        )
        review_first_activity = _merge_first_review_activity(
            review_first_activity,
            collect_first_review_activity_by_user(
                service,
                recovered,
                start_utc,
                end_exclusive_utc,
                reviews_cache=reviews_cache,
            ),
        )

    merged_pr_states = _pr_states_from_json(payload.get("merged_pr_states") or {})
    if not merged_pr_states:
        merged_pr_states = _legacy_merged_pr_states_from_rows(existing_rows)
    for row in new_rows:
        merged_pr_states[row.pr_number] = {
            "author": row.author,
            "pr_created": row.pr_created,
            "merged": row.merged,
            "closed_at": row.closed_at,
        }

    updated_payload = update_payload_after_row_merge(
        payload,
        merged_rows=merged_rows,
        review_counts=review_counts,
        approval_counts=approval_counts,
        review_first_activity=review_first_activity,
        merged_pr_states=merged_pr_states,
        skipped_pr_numbers=still_skipped,
    )
    result = load_raw_payload(updated_payload)
    emit(
        f"Retry complete: recovered {len(recovered)} PR(s); "
        f"{len(still_skipped)} still skipped"
    )
    return result, updated_payload, recovered, still_skipped


def retry_skipped_for_config(
    data_dir: str,
    config: ReportConfig,
    *,
    workers: int = 1,
    resource_workers: int = PR_RESOURCE_FETCH_WORKERS,
    emit: Callable[[str], None] = lambda _msg: None,
    emit_error: Callable[[str], None] = lambda _msg: None,
) -> Optional[tuple[ReportResult, list[int], list[int]]]:
    """Load a data-dir snapshot, retry skipped PRs, and save the updated snapshot."""
    from github_analysis.cache.data_store import load_snapshot, load_snapshot_payload, save_snapshot_payload

    result = load_snapshot(data_dir, config)
    if result is None:
        return None
    if not result.skipped_pr_numbers:
        emit(f"No skipped PRs for {config.repository.slug}")
        return result, [], []

    wrapper, payload = load_snapshot_payload(data_dir, config)
    if payload is None or wrapper is None:
        return None

    updated_result, updated_payload, recovered, still_skipped = retry_skipped_in_payload(
        payload,
        workers=workers,
        resource_workers=resource_workers,
        emit=emit,
        emit_error=emit_error,
    )
    save_snapshot_payload(
        data_dir,
        config,
        updated_payload,
        source=wrapper.get("source", "github"),
    )
    return updated_result, recovered, still_skipped
