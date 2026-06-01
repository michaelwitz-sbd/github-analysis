from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional
from zoneinfo import ZoneInfo

from github_analysis.analysis.summaries import compute_user_summaries
from github_analysis.models import (
    PullRequestRow,
    ReportConfig,
    ReportResult,
    RepositoryRef,
    UserSummary,
)
from github_analysis.time_utils import parse_github_ts


def _dt_to_json(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    return value.isoformat()


def _dt_from_json(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    return parse_github_ts(value)


def _row_to_dict(row: PullRequestRow) -> dict[str, Any]:
    data = asdict(row)
    for key in (
        "branch_start",
        "pr_created",
        "first_draft",
        "ready_for_review",
        "first_feedback",
        "approved",
        "merged",
        "closed_at",
    ):
        data[key] = _dt_to_json(data[key])
    return data


def _row_from_dict(data: dict[str, Any]) -> PullRequestRow:
    return PullRequestRow(
        author=data["author"],
        branch=data["branch"],
        pr_number=int(data["pr_number"]),
        pr_url=data["pr_url"],
        branch_start=_dt_from_json(data.get("branch_start")),
        pr_created=_dt_from_json(data.get("pr_created")),
        first_draft=_dt_from_json(data.get("first_draft")),
        ready_for_review=_dt_from_json(data.get("ready_for_review")),
        first_feedback=_dt_from_json(data.get("first_feedback")),
        approved=_dt_from_json(data.get("approved")),
        approved_by=data.get("approved_by", ""),
        merged=_dt_from_json(data.get("merged")),
        closed_at=_dt_from_json(data.get("closed_at")),
        notes=data.get("notes", ""),
        pr_files_total=int(data.get("pr_files_total", 0)),
        pr_files_added=int(data.get("pr_files_added", 0)),
        pr_files_modified=int(data.get("pr_files_modified", 0)),
        pr_files_removed=int(data.get("pr_files_removed", 0)),
        pr_commits_total=int(data.get("pr_commits_total", 0)),
        pr_commits_before_pr_open=data.get("pr_commits_before_pr_open"),
        pr_commits_after_pr_open=data.get("pr_commits_after_pr_open"),
    )


def _summary_from_dict(data: dict[str, Any]) -> UserSummary:
    return UserSummary(
        user=data["user"],
        prs_merged=int(data["prs_merged"]),
        prs_reviewed=int(data["prs_reviewed"]),
        prs_approved=int(data.get("prs_approved", 0)),
        prs_authored=int(data["prs_authored"]),
        prs_open=int(data["prs_open"]),
        avg_files_added_per_pr=data.get("avg_files_added_per_pr", ""),
        avg_files_changed_per_pr=data.get("avg_files_changed_per_pr", ""),
        min_hours_created_to_merged=data.get("min_hours_created_to_merged", ""),
        max_hours_created_to_merged=data.get("max_hours_created_to_merged", ""),
        avg_hours_created_to_merged=data.get("avg_hours_created_to_merged", ""),
    )


def save_raw_cache(
    path: str,
    *,
    result: ReportResult,
    activity_catalog: dict[int, str],
    review_catalog: dict[int, str],
    review_counts_by_user: dict[str, int],
    approval_counts_by_user: dict[str, int] | None = None,
) -> None:
    """Persist fetched GitHub data before writing TSV/Excel outputs."""
    config = result.config
    payload = {
        "version": 1,
        "config": {
            "repository": {
                "owner": config.repository.owner,
                "name": config.repository.name,
            },
            "start_date": config.start_date.isoformat(),
            "end_date": config.end_date.isoformat(),
            "report_tz": config.report_tz.key,
            "merged_only": config.merged_only,
        },
        "start_utc": _dt_to_json(result.start_utc),
        "end_exclusive_utc": _dt_to_json(result.end_exclusive_utc),
        "activity_catalog": {str(k): v for k, v in activity_catalog.items()},
        "review_catalog": {str(k): v for k, v in review_catalog.items()},
        "review_counts_by_user": review_counts_by_user,
        "approval_counts_by_user": approval_counts_by_user or {},
        "skipped_pr_numbers": result.skipped_pr_numbers,
        "rows": [_row_to_dict(row) for row in result.rows],
        "summaries": [asdict(summary) for summary in result.summaries],
    }
    target = Path(path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_raw_cache(path: str) -> ReportResult:
    """Rebuild ReportResult from a saved raw JSON cache."""
    payload = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
    cfg = payload["config"]
    config = ReportConfig(
        repository=RepositoryRef(owner=cfg["repository"]["owner"], name=cfg["repository"]["name"]),
        start_date=date.fromisoformat(cfg["start_date"]),
        end_date=date.fromisoformat(cfg["end_date"]),
        report_tz=ZoneInfo(cfg["report_tz"]),
        merged_only=bool(cfg.get("merged_only", False)),
    )
    rows = [_row_from_dict(row) for row in payload.get("rows", [])]
    review_counts = {
        key: int(value) for key, value in (payload.get("review_counts_by_user") or {}).items()
    }
    approval_counts = {
        key: int(value) for key, value in (payload.get("approval_counts_by_user") or {}).items()
    }
    summaries = compute_user_summaries(rows, review_counts, approval_counts)
    return ReportResult(
        config=config,
        rows=rows,
        summaries=summaries,
        skipped_pr_numbers=[int(n) for n in payload.get("skipped_pr_numbers", [])],
        start_utc=_dt_from_json(payload.get("start_utc")),
        end_exclusive_utc=_dt_from_json(payload.get("end_exclusive_utc")),
    )
