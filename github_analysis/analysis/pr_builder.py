from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any, Optional

from github_analysis.config import PR_RESOURCE_FETCH_WORKERS
from github_analysis.github.pulls import (
    PullRequestService,
    branch_start_from_commits,
    commits_before_after_open,
    file_counts,
    line_counts,
)
from github_analysis.models import PullRequestRow, RepositoryRef
from github_analysis.time_utils import parse_github_ts


def _append_note(existing: str, part: str) -> str:
    part = part.strip()
    if not part:
        return existing
    if not existing:
        return part
    return f"{existing}; {part}"


def _first_draft_and_ready(
    pr_created: datetime,
    events: list[dict[str, Any]],
) -> tuple[Optional[datetime], Optional[datetime]]:
    sorted_events = sorted(events, key=lambda event: event.get("created_at") or "")
    first_draft: Optional[datetime] = None
    ready: Optional[datetime] = None

    for event in sorted_events:
        event_type = event.get("event") or ""
        ts = parse_github_ts(event.get("created_at"))
        if not ts:
            continue
        if event_type == "converted_to_draft" and first_draft is None:
            first_draft = ts
        elif event_type == "ready_for_review" and ready is None:
            ready = ts

    if first_draft is None and ready is None:
        ready = pr_created
    return first_draft, ready


def _first_feedback_time(
    reviews: list[dict[str, Any]],
    comments: list[dict[str, Any]],
) -> Optional[datetime]:
    times: list[datetime] = []
    for review in reviews:
        submitted = parse_github_ts(review.get("submitted_at"))
        if submitted:
            times.append(submitted)
    for comment in comments:
        created = parse_github_ts(comment.get("created_at"))
        if created:
            times.append(created)
    return min(times) if times else None


def _first_approval_time(reviews: list[dict[str, Any]]) -> Optional[datetime]:
    approved: list[datetime] = []
    for review in reviews:
        if (review.get("state") or "").upper() != "APPROVED":
            continue
        submitted = parse_github_ts(review.get("submitted_at"))
        if submitted:
            approved.append(submitted)
    return min(approved) if approved else None


def _first_approver_login(reviews: list[dict[str, Any]]) -> str:
    best_login = ""
    best_time: Optional[datetime] = None
    for review in reviews:
        if (review.get("state") or "").upper() != "APPROVED":
            continue
        submitted = parse_github_ts(review.get("submitted_at"))
        if submitted is None:
            continue
        if best_time is None or submitted < best_time:
            best_time = submitted
            best_login = ((review.get("user") or {}).get("login")) or ""
    return best_login


def _pull_creator_login(detail: dict[str, Any]) -> str:
    """PR opener/creator from GitHub API (`user` field). Assignees are ignored."""
    return ((detail.get("user") or {}).get("login")) or ""


def _fetch_pull_resources(
    service: PullRequestService,
    pull_number: int,
    *,
    reviews: Optional[list[dict[str, Any]]] = None,
    resource_workers: int = PR_RESOURCE_FETCH_WORKERS,
) -> tuple[
    tuple[list[dict[str, Any]], bool],
    tuple[list[dict[str, Any]], bool],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    if resource_workers <= 1:
        commits = service.commits(pull_number)
        files = service.files(pull_number)
        events = service.issue_events(pull_number)
        fetched_reviews = reviews if reviews is not None else service.reviews(pull_number)
        comments = service.issue_comments(pull_number)
        return commits, files, events, fetched_reviews, comments

    with ThreadPoolExecutor(max_workers=resource_workers) as executor:
        futures = {
            "commits": executor.submit(service.commits, pull_number),
            "files": executor.submit(service.files, pull_number),
            "events": executor.submit(service.issue_events, pull_number),
            "comments": executor.submit(service.issue_comments, pull_number),
        }
        if reviews is None:
            futures["reviews"] = executor.submit(service.reviews, pull_number)

        commits = futures["commits"].result()
        files = futures["files"].result()
        events = futures["events"].result()
        fetched_reviews = reviews if reviews is not None else futures["reviews"].result()
        comments = futures["comments"].result()

    return commits, files, events, fetched_reviews, comments


def build_pull_request_row(
    service: PullRequestService,
    pull_number: int,
    *,
    report_author: Optional[str] = None,
    reviews: Optional[list[dict[str, Any]]] = None,
    resource_workers: int = PR_RESOURCE_FETCH_WORKERS,
) -> tuple[PullRequestRow, list[dict[str, Any]]]:
    detail = service.detail(pull_number)
    creator = _pull_creator_login(detail)
    if report_author and report_author != creator:
        notes_prefix = f"catalog_author_mismatch:{report_author}"
    else:
        notes_prefix = ""
    branch = detail.get("head", {}).get("ref") or ""
    html_url = detail.get("html_url") or ""
    pr_created = parse_github_ts(detail.get("created_at"))
    merged = parse_github_ts(detail.get("merged_at"))
    closed_at = parse_github_ts(detail.get("closed_at"))

    (
        (commits, commits_truncated),
        (files, files_truncated),
        events,
        reviews,
        comments,
    ) = _fetch_pull_resources(
        service,
        pull_number,
        reviews=reviews,
        resource_workers=resource_workers,
    )

    branch_start = branch_start_from_commits(commits)
    commits_before, commits_after = commits_before_after_open(commits, pr_created)
    total_files, added_files, modified_files, removed_files = file_counts(files)
    lines_added, lines_removed = line_counts(files)

    first_draft, ready = _first_draft_and_ready(
        pr_created or datetime.now(timezone.utc), events
    )

    first_feedback = _first_feedback_time(reviews, comments)
    approved = _first_approval_time(reviews)
    approved_by = _first_approver_login(reviews)

    notes = notes_prefix
    if branch_start is None:
        notes = _append_note(notes, "branch_start_unavailable")
    if commits_truncated:
        notes = _append_note(notes, "pr_commits_list_truncated")
    if files_truncated:
        notes = _append_note(notes, "pr_files_list_truncated")

    return (
        PullRequestRow(
            author=creator,
            branch=branch,
            pr_number=pull_number,
            pr_url=html_url,
            branch_start=branch_start,
            pr_created=pr_created,
            first_draft=first_draft,
            ready_for_review=ready,
            first_feedback=first_feedback,
            approved=approved,
            approved_by=approved_by,
            merged=merged,
            closed_at=closed_at,
            notes=notes,
            pr_files_total=total_files,
            pr_files_added=added_files,
            pr_files_modified=modified_files,
            pr_files_removed=removed_files,
            pr_lines_added=lines_added,
            pr_lines_removed=lines_removed,
            pr_commits_total=len(commits),
            pr_commits_before_pr_open=commits_before,
            pr_commits_after_pr_open=commits_after,
        ),
        reviews,
    )
