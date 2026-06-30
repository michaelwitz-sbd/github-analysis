from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import asdict
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any

from github_analysis.models import PullRequestRow, ReportResult, UserSummary
from github_analysis.reporting.metrics import (
    average as _avg,
    days_between as _days_between,
    hours_between as _hours_between,
    numeric_string as _num,
    per_active_week as _per_active_week,
    percent as _pct,
    time_metrics as _shared_time_metrics,
)
from github_analysis.reporting.periods import bucket_key

def _fmt_number(value: int | float | None, *, suffix: str = "", digits: int = 1) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, int):
        return f"{value}{suffix}"
    return f"{value:.{digits}f}{suffix}"


def _safe_dom_id(value: str) -> str:
    safe = "".join(c.lower() if c.isalnum() else "-" for c in value).strip("-")
    return safe or "unknown"


def _iso_date(value: datetime | None) -> str:
    return value.date().isoformat() if value else "N/A"


def _summary_by_user(summaries: list[UserSummary]) -> dict[str, UserSummary]:
    return {summary.user: summary for summary in summaries}


def _rows_by_author(rows: list[PullRequestRow]) -> dict[str, list[PullRequestRow]]:
    grouped: dict[str, list[PullRequestRow]] = defaultdict(list)
    for row in rows:
        grouped[row.author or "(unknown)"].append(row)
    return dict(grouped)


def _first_authored_activity_by_user(rows: list[PullRequestRow]) -> dict[str, datetime]:
    first_by_user: dict[str, datetime] = {}
    for row in rows:
        if row.pr_created is None:
            continue
        user = row.author or "(unknown)"
        current = first_by_user.get(user)
        if current is None or row.pr_created < current:
            first_by_user[user] = row.pr_created
    return first_by_user


def _time_metrics(rows: list[PullRequestRow], *, end_at: datetime | None) -> dict[str, float | None]:
    return _shared_time_metrics(rows, end_at=end_at).to_payload()


def _activity_score(person: dict[str, Any]) -> float:
    return sum(
        float(person.get(key) or 0)
        for key in (
            "authoredPerActiveWeek",
            "mergedPerActiveWeek",
            "reviewedPerActiveWeek",
            "approvedPerActiveWeek",
        )
    )


def _best_worst_people(people: list[dict[str, Any]]) -> list[dict[str, Any]]:
    metrics = [
        ("Overall Normalized Activity", "activityScore", "/wk", False),
        ("Approvals Given Per Active Week", "approvedPerActiveWeek", "/wk", False),
        ("Reviews Per Active Week", "reviewedPerActiveWeek", "/wk", False),
        ("Approval Rate", "approvalRate", "%", False),
        ("Review Share", "reviewShare", "%", False),
        ("Open Carryover Rate", "openCarryoverRate", "%", True),
        ("Closed Unmerged Rate", "closedUnmergedRate", "%", True),
    ]
    payload: list[dict[str, Any]] = []
    for label, key, suffix, lower_is_better in metrics:
        candidates: list[tuple[dict[str, Any], float]] = []
        for person in people:
            value = _activity_score(person) if key == "activityScore" else person.get(key)
            if value is None:
                continue
            numeric = float(value)
            if numeric <= 0:
                continue
            candidates.append((person, numeric))
        if not candidates:
            continue
        best_person, best_value = min(candidates, key=lambda item: item[1]) if lower_is_better else max(candidates, key=lambda item: item[1])
        worst_person, worst_value = max(candidates, key=lambda item: item[1]) if lower_is_better else min(candidates, key=lambda item: item[1])
        payload.append(
            {
                "label": label,
                "suffix": suffix,
                "lowerIsBetter": lower_is_better,
                "best": _winner_user_value(best_person, best_value),
                "worst": _winner_user_value(worst_person, worst_value),
            }
        )
    return payload


def _winner_user_value(person: dict[str, Any], value: float) -> dict[str, Any]:
    return {"user": person["user"], "value": value}


def _ui_specs() -> dict[str, Any]:
    return {
        "overview": {
            "bars": [
                {
                    "title": "Overall Normalized Activity",
                    "key": "activityScore",
                    "suffix": "/wk",
                },
            ],
        },
        "comparison": {
            "table": {
                "defaultSortCol": 4,
                "defaultSortDir": "desc",
                "columns": [
                    {"label": "User", "type": "text", "key": "user"},
                    {"label": "Inferred Start", "type": "text", "key": "inferredStart"},
                    {"label": "Eligible Days", "type": "number", "key": "eligibleDays", "format": "days"},
                    {"label": "Authored", "type": "number", "key": "authored"},
                    {"label": "Merged", "type": "number", "key": "merged"},
                    {"label": "Reviewed", "type": "number", "key": "reviewed"},
                    {"label": "Approvals Given", "type": "number", "key": "approved"},
                    {"label": "Authored/Wk", "type": "number", "key": "authoredPerActiveWeek", "format": "fixed"},
                    {"label": "Merged/Wk", "type": "number", "key": "mergedPerActiveWeek", "format": "fixed"},
                    {"label": "Reviewed/Wk", "type": "number", "key": "reviewedPerActiveWeek", "format": "fixed"},
                    {"label": "Approvals Given/Wk", "type": "number", "key": "approvedPerActiveWeek", "format": "fixed"},
                    {"label": "Avg Files Changed", "type": "number", "key": "avgFilesChanged", "format": "fixed"},
                    {"label": "Avg Lines Added", "type": "number", "key": "avgLinesAdded", "format": "fixed"},
                    {"label": "Avg Lines Removed", "type": "number", "key": "avgLinesRemoved", "format": "fixed"},
                    {"label": "Avg Lines Delta", "type": "number", "key": "avgLinesDelta", "format": "fixed"},
                    {"label": "Approval Rate", "type": "number", "key": "approvalRate", "format": "percent"},
                    {"label": "Review Share", "type": "number", "key": "reviewShare", "format": "percent"},
                    {"label": "Avg Feedback", "type": "number", "key": "avgFeedbackHours", "format": "hours"},
                    {"label": "Avg Approval", "type": "number", "key": "avgApprovalHours", "format": "hours"},
                    {"label": "Stale Rate", "type": "number", "key": "staleRate", "format": "percent"},
                ],
            },
            "bars": [
                {"title": "Overall Normalized Activity", "key": "activityScore", "suffix": "/wk"},
                {"title": "PRs Authored", "key": "authored", "suffix": ""},
                {"title": "PRs Merged", "key": "merged", "suffix": ""},
                {"title": "PRs Reviewed", "key": "reviewed", "suffix": ""},
                {"title": "Review Share By Person", "key": "reviewShare", "suffix": "%"},
                {"title": "Average Lines Delta", "key": "avgLinesDelta", "suffix": ""},
                {"title": "Average Files Changed", "key": "avgFilesChanged", "suffix": ""},
            ],
        },
        "teams": {
            "table": {
                "defaultSortCol": 2,
                "defaultSortDir": "desc",
                "columns": [
                    {"label": "Team", "type": "text", "key": "name"},
                    {"label": "Members", "type": "number", "key": "count"},
                    {"label": "Authored", "type": "number", "key": "authored"},
                    {"label": "Reviewed", "type": "number", "key": "reviewed"},
                    {"label": "Approvals", "type": "number", "key": "approved"},
                    {"label": "Norm Activity", "type": "number", "key": "normalized", "format": "perWeek"},
                    {"label": "Avg Line Delta", "type": "number", "key": "avgLinesDelta", "format": "fixed"},
                ],
            },
            "bars": [
                {"title": "Team Normalized Activity", "key": "normalized", "suffix": "/wk"},
                {"title": "Team Approvals Given", "key": "approved", "suffix": ""},
                {"title": "Team Reviews", "key": "reviewed", "suffix": ""},
                {"title": "Team Avg Lines Delta", "key": "avgLinesDelta", "suffix": ""},
            ],
        },
    }


def _period_key(value: datetime | None, granularity: str) -> str | None:
    if granularity == "none":
        return None
    return bucket_key(value, granularity)


def _winner_from_week(
    user_metrics: list[dict[str, Any]], key: str, *, lower_is_better: bool = False
) -> dict[str, Any] | None:
    candidates = [
        metric
        for metric in user_metrics
        if metric.get(key) is not None and float(metric.get(key) or 0) > 0
    ]
    if not candidates:
        return None
    winner = min(candidates, key=lambda item: float(item[key])) if lower_is_better else max(candidates, key=lambda item: float(item[key]))
    return {"user": winner["user"], "value": winner[key]}


def _weekly_winners(rows: list[PullRequestRow], *, granularity: str = "weekly") -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, dict[str, Any]]] = defaultdict(
        lambda: defaultdict(
            lambda: {
                "authored": 0,
                "merged": 0,
                "approved": 0,
                "approvalsGiven": 0,
                "feedback": 0,
                "mergedByMergeWeek": 0,
                "mergeHours": [],
                "linesAdded": [],
                "linesRemoved": [],
            }
        )
    )
    for row in rows:
        user = row.author or "(unknown)"
        if created_week := _period_key(row.pr_created, granularity):
            bucket = buckets[created_week][user]
            bucket["authored"] += 1
            if row.merged is not None:
                bucket["merged"] += 1
            if row.approved is not None:
                bucket["approved"] += 1
            if row.first_feedback is not None:
                bucket["feedback"] += 1
            if row.pr_lines_added is not None:
                bucket["linesAdded"].append(float(row.pr_lines_added))
            if row.pr_lines_removed is not None:
                bucket["linesRemoved"].append(float(row.pr_lines_removed))
        if row.approved is not None and row.approved_by and row.approved_by != user:
            approved_week = _period_key(row.approved, granularity)
            if approved_week:
                buckets[approved_week][row.approved_by]["approvalsGiven"] += 1
        if merged_week := _period_key(row.merged, granularity):
            bucket = buckets[merged_week][user]
            bucket["mergedByMergeWeek"] += 1
            if (merge_hours := _hours_between(row.pr_created, row.merged)) is not None:
                bucket["mergeHours"].append(merge_hours)

    payload: list[dict[str, Any]] = []
    for week in sorted(buckets):
        user_metrics = [
            {
                "user": user,
                "authored": values["authored"],
                "merged": values["mergedByMergeWeek"],
                "mergeRate": _pct(values["merged"], values["authored"]),
                "approvalCoverageRate": _pct(values["approved"], values["authored"]),
                "reviewCoverageRate": _pct(values["feedback"], values["authored"]),
                "approvalsGiven": values["approvalsGiven"],
                "avgMergeHours": _avg(values["mergeHours"]),
                "avgLinesAdded": _avg(values["linesAdded"]),
                "avgLinesRemoved": _avg(values["linesRemoved"]),
                "avgLinesDelta": (
                    _avg(values["linesAdded"]) - _avg(values["linesRemoved"])
                    if _avg(values["linesAdded"]) is not None
                    and _avg(values["linesRemoved"]) is not None
                    else None
                ),
            }
            for user, values in buckets[week].items()
        ]
        payload.append(
            {
                "week": week,
                "users": sorted(user_metrics, key=lambda item: item["user"].lower()),
                "topAuthored": _winner_from_week(user_metrics, "authored"),
                "topMerged": _winner_from_week(user_metrics, "merged"),
                "topApprovalsGiven": _winner_from_week(user_metrics, "approvalsGiven"),
                "topApprovalCoverageRate": _winner_from_week(
                    user_metrics, "approvalCoverageRate"
                ),
                "topReviewCoverageRate": _winner_from_week(user_metrics, "reviewCoverageRate"),
                "topLinesAdded": _winner_from_week(user_metrics, "avgLinesAdded"),
                "topLinesDelta": _winner_from_week(user_metrics, "avgLinesDelta"),
            }
        )
    return payload


def _person_payload(result: ReportResult) -> list[dict[str, Any]]:
    summaries = _summary_by_user(result.summaries)
    rows_by_author = _rows_by_author(result.rows)
    users = sorted(set(summaries) | set(rows_by_author), key=str.lower)
    team_authored = sum(summary.prs_authored for summary in summaries.values())
    team_reviewed = sum(summary.prs_reviewed for summary in summaries.values())
    authored_first = _first_authored_activity_by_user(result.rows)
    window_days = _days_between(result.start_utc, result.end_exclusive_utc)
    payload: list[dict[str, Any]] = []

    for user in users:
        summary = summaries.get(user)
        authored = summary.prs_authored if summary else len(rows_by_author.get(user, []))
        merged = summary.prs_merged if summary else sum(1 for row in rows_by_author.get(user, []) if row.merged)
        reviewed = summary.prs_reviewed if summary else 0
        approved = summary.prs_approved if summary else 0
        open_count = summary.prs_open if summary else 0
        closed_unmerged = summary.prs_closed_unmerged if summary else 0
        rows = rows_by_author.get(user, [])
        times = _time_metrics(rows, end_at=result.end_exclusive_utc)
        avg_lines_added = _avg(
            [float(row.pr_lines_added) for row in rows if row.pr_lines_added is not None]
        )
        avg_lines_removed = _avg(
            [float(row.pr_lines_removed) for row in rows if row.pr_lines_removed is not None]
        )
        activity_candidates = [
            ts
            for ts in (
                authored_first.get(user),
                result.review_first_activity_by_user.get(user),
            )
            if ts is not None
        ]
        inferred_start = min(activity_candidates) if activity_candidates else result.start_utc
        eligible_start = max(result.start_utc, inferred_start) if result.start_utc else inferred_start
        eligible_days = _days_between(eligible_start, result.end_exclusive_utc)
        authored_per_week = _per_active_week(authored, eligible_days)
        merged_per_week = _per_active_week(merged, eligible_days)
        reviewed_per_week = _per_active_week(reviewed, eligible_days)
        approved_per_week = _per_active_week(approved, eligible_days)
        payload.append(
            {
                "id": _safe_dom_id(user),
                "user": user,
                "inferredStart": _iso_date(inferred_start),
                "eligibleDays": eligible_days,
                "windowDays": window_days,
                "authored": authored,
                "merged": merged,
                "reviewed": reviewed,
                "approved": approved,
                "open": open_count,
                "closedUnmerged": closed_unmerged,
                "mergeRate": _pct(merged, authored),
                "approvalRate": _pct(approved, reviewed),
                "openCarryoverRate": _pct(open_count, authored),
                "closedUnmergedRate": _pct(closed_unmerged, authored),
                "authoredShare": _pct(authored, team_authored),
                "reviewShare": _pct(reviewed, team_reviewed),
                "authoredPerActiveWeek": authored_per_week,
                "mergedPerActiveWeek": merged_per_week,
                "reviewedPerActiveWeek": reviewed_per_week,
                "approvedPerActiveWeek": approved_per_week,
                "openPerActiveWeek": _per_active_week(open_count, eligible_days),
                "activityScore": _activity_score(
                    {
                        "authoredPerActiveWeek": authored_per_week,
                        "mergedPerActiveWeek": merged_per_week,
                        "reviewedPerActiveWeek": reviewed_per_week,
                        "approvedPerActiveWeek": approved_per_week,
                    }
                ),
                "avgFilesAdded": _num(summary.avg_files_added_per_pr) if summary else None,
                "avgFilesChanged": _num(summary.avg_files_changed_per_pr) if summary else None,
                "avgCommits": _avg([float(row.pr_commits_total) for row in rows]),
                "avgLinesAdded": avg_lines_added,
                "avgLinesRemoved": avg_lines_removed,
                "avgLinesDelta": (
                    avg_lines_added - avg_lines_removed
                    if avg_lines_added is not None and avg_lines_removed is not None
                    else None
                ),
                **times,
                "prs": [
                    {
                        "number": row.pr_number,
                        "status": "merged" if row.merged else "closed" if row.closed_at else "open",
                        "timeHours": _hours_between(row.pr_created, row.merged)
                        or _hours_between(row.pr_created, result.end_exclusive_utc),
                        "files": row.pr_files_total,
                        "linesAdded": row.pr_lines_added,
                        "linesRemoved": row.pr_lines_removed,
                        "url": row.pr_url,
                    }
                    for row in rows[:20]
                ],
            }
        )
    return payload


def _overview_payload(
    result: ReportResult,
    people: list[dict[str, Any]],
    *,
    bucket_granularity: str = "weekly",
) -> dict[str, Any]:
    authored = sum(person["authored"] for person in people)
    merged = sum(person["merged"] for person in people)
    reviewed = sum(person["reviewed"] for person in people)
    approved = sum(person["approved"] for person in people)
    open_count = sum(person["open"] for person in people)
    closed_unmerged = sum(person["closedUnmerged"] for person in people)
    all_times = _time_metrics(result.rows, end_at=result.end_exclusive_utc)
    largest_share = max((person.get("authoredShare") or 0 for person in people), default=0)
    avg_files_changed = _avg(
        [float(row.pr_files_added + row.pr_files_modified + row.pr_files_removed) for row in result.rows]
    )
    avg_commits = _avg([float(row.pr_commits_total) for row in result.rows])
    avg_lines_added = _avg(
        [float(row.pr_lines_added) for row in result.rows if row.pr_lines_added is not None]
    )
    avg_lines_removed = _avg(
        [float(row.pr_lines_removed) for row in result.rows if row.pr_lines_removed is not None]
    )
    return {
        "authored": authored,
        "merged": merged,
        "reviewed": reviewed,
        "approved": approved,
        "open": open_count,
        "closedUnmerged": closed_unmerged,
        "mergeRate": _pct(merged, authored),
        "reviewCoverageRate": _pct(sum(1 for row in result.rows if row.first_feedback), len(result.rows)),
        "approvalCoverageRate": _pct(sum(1 for row in result.rows if row.approved), len(result.rows)),
        "largestContributorShare": largest_share,
        "avgFilesChanged": avg_files_changed,
        "avgCommits": avg_commits,
        "avgLinesAdded": avg_lines_added,
        "avgLinesRemoved": avg_lines_removed,
        "winners": {
            "allTime": _best_worst_people(people),
            "weekly": _weekly_winners(result.rows, granularity=bucket_granularity),
        },
        **all_times,
    }


def build_report_payload(results: list[ReportResult], *, bucket_granularity: str = "weekly") -> dict[str, Any]:
    if not results:
        raise ValueError("at least one report result is required")
    # MVP: one generated report payload can include multiple result objects; person
    # records are combined by summing per-result payloads with a simple row merge.
    primary = results[0]
    merged_rows: list[PullRequestRow] = []
    merged_summaries: dict[str, UserSummary] = {}
    review_first_activity: dict[str, datetime] = {}
    for result in results:
        merged_rows.extend(result.rows)
        for user, ts in result.review_first_activity_by_user.items():
            current = review_first_activity.get(user)
            if current is None or ts < current:
                review_first_activity[user] = ts
        for summary in result.summaries:
            existing = merged_summaries.get(summary.user)
            if existing is None:
                merged_summaries[summary.user] = UserSummary(**asdict(summary))
            else:
                existing.prs_merged += summary.prs_merged
                existing.prs_reviewed += summary.prs_reviewed
                existing.prs_approved += summary.prs_approved
                existing.prs_authored += summary.prs_authored
                existing.prs_open += summary.prs_open
                existing.prs_closed_unmerged += summary.prs_closed_unmerged
    combined = ReportResult(
        config=primary.config,
        rows=merged_rows,
        summaries=sorted(merged_summaries.values(), key=lambda item: item.user.lower()),
        skipped_pr_numbers=[number for result in results for number in result.skipped_pr_numbers],
        start_utc=primary.start_utc,
        end_exclusive_utc=primary.end_exclusive_utc,
        review_first_activity_by_user=review_first_activity,
    )
    people = _person_payload(combined)
    views = [
        {
            "id": "all",
            "label": "All repositories",
            "overview": _overview_payload(
                combined,
                people,
                bucket_granularity=bucket_granularity,
            ),
            "people": people,
        }
    ]
    for result in results:
        repo_people = _person_payload(result)
        views.append(
            {
                "id": _safe_dom_id(result.config.repository.slug),
                "label": result.config.repository.slug,
                "overview": _overview_payload(
                    result,
                    repo_people,
                    bucket_granularity=bucket_granularity,
                ),
                "people": repo_people,
            }
        )
    return {
        "title": "GitHub Metrics Overview",
        "repository": primary.config.repository.slug if len(results) == 1 else "All repositories",
        "repositories": [
            {
                "name": result.config.repository.slug,
                "authored": sum(summary.prs_authored for summary in result.summaries),
                "merged": sum(summary.prs_merged for summary in result.summaries),
                "reviewed": sum(summary.prs_reviewed for summary in result.summaries),
                **_time_metrics(result.rows, end_at=result.end_exclusive_utc),
            }
            for result in results
        ],
        "startDate": primary.config.start_date.isoformat(),
        "endDate": primary.config.end_date.isoformat(),
        "timezone": primary.config.report_tz.key,
        "bucketGranularity": bucket_granularity,
        "overview": _overview_payload(
            combined,
            people,
            bucket_granularity=bucket_granularity,
        ),
        "people": people,
        "views": views,
        "skippedPrs": len(combined.skipped_pr_numbers),
        "uiSpecs": _ui_specs(),
    }


def _json_script(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")


def render_html(payload: dict[str, Any]) -> str:
    data = _json_script(payload)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(payload["title"])}</title>
  <style>
    :root {{ --bg:#090b0c; --panel:#151718; --ink:#f4f7f8; --muted:#7d858c; --border:#252a2e; --aqua:#1dd6e8; --good:#2ee68f; --warn:#f5aa27; --bad:#ff4d6d; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; background:var(--bg); color:var(--ink); font-family:Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    .app {{ display:grid; grid-template-columns:255px minmax(0,1fr); min-height:100vh; }}
    aside {{ background:#0d0f10; border-right:1px solid #202428; padding:18px 14px; position:sticky; top:0; height:100vh; overflow-y:auto; overscroll-behavior:contain; }}
    main {{ padding:30px 36px 48px; min-width:0; }}
    h1 {{ margin:0 0 6px; font-size:24px; }} h2 {{ margin:0 0 12px; font-size:18px; }}
    .muted {{ color:var(--muted); }} .brand {{ font-weight:900; margin:18px 0; }} .brand:before {{ content:""; display:inline-block; width:9px; height:9px; background:var(--aqua); border-radius:50%; margin-right:9px; box-shadow:0 0 18px rgba(29,214,232,.65); }}
    button.tab {{ display:block; width:100%; background:transparent; color:#8d979f; border:1px solid transparent; border-radius:9px; padding:10px 11px; text-align:left; font-weight:750; cursor:pointer; }}
    button.tab.active {{ background:rgba(29,214,232,.12); color:var(--aqua); border-color:rgba(29,214,232,.1); }}
    .card {{ background:var(--panel); border:1px solid var(--border); border-radius:10px; padding:18px; margin-top:18px; box-shadow:0 22px 50px rgba(0,0,0,.28); }}
    .section-heading {{ margin-top:24px; }} .section-heading h2 {{ margin-bottom:4px; }} .section-heading p {{ margin:0; color:var(--muted); font-size:13px; }}
    .grid {{ display:grid; gap:14px; }} .grid.two {{ grid-template-columns:repeat(2,minmax(0,1fr)); }} .grid.four {{ grid-template-columns:repeat(4,minmax(0,1fr)); }}
    .metric .label {{ color:var(--muted); font-size:12px; font-weight:800; }} .metric .value {{ margin-top:8px; font-size:30px; font-weight:900; }}
    .pill {{ border-radius:999px; padding:3px 8px; font-size:12px; font-weight:800; }} .good {{ background:rgba(46,230,143,.14); color:var(--good); }} .warn {{ background:rgba(245,170,39,.14); color:var(--warn); }}
    .alert {{ border:1px solid rgba(29,214,232,.32); border-left:4px solid var(--aqua); background:rgba(29,214,232,.1); border-radius:9px; padding:13px 16px; margin:20px 0; }}
    .formulas {{ display:grid; gap:12px; grid-template-columns:repeat(2,minmax(0,1fr)); }} .formula {{ background:#101314; border:1px solid var(--border); border-radius:14px; padding:14px; }} .formula code {{ display:block; background:rgba(29,214,232,.12); color:var(--aqua); border-radius:10px; padding:8px; margin:8px 0; }}
    .table-wrap {{ border:1px solid var(--border); border-radius:10px; overflow:auto; }} .scroll-y {{ max-height:360px; overflow:auto; }} .comparison-scroll {{ height:260px; overflow-x:auto; overflow-y:scroll; }}
    table {{ border-collapse:collapse; width:100%; }} th,td {{ border-bottom:1px solid var(--border); padding:10px 8px; white-space:nowrap; text-align:left; }} th {{ color:var(--muted); cursor:pointer; font-size:12px; text-transform:uppercase; letter-spacing:.06em; position:sticky; top:0; background:var(--panel); z-index:1; }} th.sorted-asc,th.sorted-desc {{ color:var(--aqua); }} th.sorted-asc:after {{ content:" ↑"; }} th.sorted-desc:after {{ content:" ↓"; }}
    .repo-switcher {{ display:flex; flex-wrap:wrap; gap:8px; margin:18px 0 6px; }} .repo-switcher button {{ background:#101314; color:var(--muted); border:1px solid var(--border); border-radius:999px; padding:8px 12px; font-weight:800; cursor:pointer; }} .repo-switcher button.active {{ color:var(--aqua); border-color:rgba(29,214,232,.55); background:rgba(29,214,232,.12); }}
    .side-label {{ color:var(--muted); font-size:11px; font-weight:900; letter-spacing:.08em; margin:20px 0 8px; text-transform:uppercase; }} .sidebar-switcher {{ display:grid; gap:8px; margin:8px 0 18px; }} .sidebar-switcher button {{ border-radius:9px; text-align:left; width:100%; }}
    .bars {{ display:grid; gap:10px; }} .bar-row {{ display:grid; grid-template-columns:130px 1fr 72px; gap:10px; align-items:center; font-size:13px; }} .track {{ height:12px; background:#262b2f; border-radius:999px; overflow:hidden; }} .fill {{ height:100%; background:var(--aqua); border-radius:999px; }}
    .winner-strip {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px; margin:14px 0; }} .winner-card {{ background:#101314; border:1px solid var(--border); border-radius:14px; padding:14px; }} .winner-card .name {{ color:var(--ink); font-size:20px; font-weight:900; margin:6px 0; }} .winner-card .score {{ color:var(--aqua); font-weight:900; }} .winner-chart {{ width:100%; height:190px; margin-top:10px; }} .winner-list {{ display:grid; gap:8px; margin-top:12px; }} .winner-list div {{ display:flex; justify-content:space-between; gap:12px; color:var(--muted); font-size:12px; }} .winner-list strong {{ color:var(--ink); }} .trend-legend {{ display:flex; flex-wrap:wrap; gap:8px 12px; margin-top:12px; max-height:92px; overflow:auto; }} .trend-legend span {{ color:var(--muted); font-size:12px; }} .legend-dot {{ display:inline-block; width:9px; height:9px; border-radius:50%; margin-right:5px; }}
    .team-control {{ display:grid; gap:8px; margin:12px 0; }} .team-control input {{ width:180px; background:#101314; border:1px solid var(--border); border-radius:9px; color:var(--ink); padding:8px; }} .team-control select {{ width:100%; max-width:420px; background:#151718; border:1px solid var(--border); border-radius:10px; color:var(--ink); padding:10px; }} .team-input-board {{ display:grid; gap:14px; grid-template-columns:repeat(2,minmax(0,1fr)); margin-top:14px; }} .team-input-card {{ background:#101314; border:1px solid var(--border); border-radius:14px; padding:14px; }} .team-input-card h3 {{ margin:0 0 10px; font-size:14px; }} .team-input-card select {{ width:100%; background:#151718; border:1px solid var(--border); border-radius:10px; color:var(--ink); padding:10px; }} .selected-members {{ display:flex; flex-wrap:wrap; gap:8px; min-height:42px; margin-top:12px; }} .member-chip {{ background:rgba(29,214,232,.1); color:var(--aqua); border:1px solid rgba(29,214,232,.35); border-radius:999px; padding:7px 10px; font-size:12px; font-weight:800; cursor:pointer; }} .empty-pill {{ color:var(--muted); font-size:12px; }} .compare-input-board {{ grid-template-columns:minmax(0,1fr); max-width:640px; }} .compare-clear {{ display:inline-block; margin-top:10px; background:transparent; color:var(--muted); border:none; padding:0; font-size:12px; font-weight:800; cursor:pointer; text-decoration:underline; text-underline-offset:3px; }} .compare-clear:hover {{ color:var(--aqua); }} .chip-rank {{ display:inline-flex; align-items:center; justify-content:center; min-width:18px; height:18px; border-radius:999px; background:rgba(29,214,232,.18); color:var(--aqua); font-size:10px; font-weight:900; margin-right:4px; }}
    .page {{ display:none; }} .page.active {{ display:block; }}
    @media (max-width:1100px) {{ .app {{ grid-template-columns:1fr; }} aside {{ position:static; height:auto; }} .grid.two,.grid.four,.formulas {{ grid-template-columns:1fr; }} }}
  </style>
</head>
<body>
<script id="report-data" type="application/json">{data}</script>
<div class="app">
  <aside>
    <div class="brand">GitHub PR Metrics</div>
    <div class="muted" id="scope"></div>
    <div class="side-label">Repository View</div>
    <div id="side-repo-switcher" class="repo-switcher sidebar-switcher"></div>
    <div style="margin-top:22px">
      <button class="tab active" data-tab="overview">Overview</button>
      <button class="tab" data-tab="comparison">Comparison</button>
      <button class="tab" data-tab="teams">Teams</button>
      <div id="person-tabs"></div>
    </div>
  </aside>
  <main>
    <h1>GitHub Metrics Overview</h1>
    <div class="muted" id="subtitle"></div>
    <div class="alert"><strong id="alert-count"></strong> metric alerts or skipped PRs may need review.</div>
    <div id="repo-switcher" class="repo-switcher"></div>
    <section id="overview" class="page active"></section>
    <section id="comparison" class="page"></section>
    <section id="teams" class="page"></section>
    <div id="person-pages"></div>
  </main>
</div>
<script>
const data = JSON.parse(document.getElementById("report-data").textContent);
const fmt = (v, suffix="", digits=1) => v === null || v === undefined ? "N/A" : `${{Number(v).toFixed(digits)}}${{suffix}}`;
const pct = (v) => fmt(v, "%");
document.getElementById("scope").textContent = data.repository;
document.getElementById("subtitle").textContent = `${{data.startDate}} to ${{data.endDate}} · ${{data.timezone}}`;
document.getElementById("alert-count").textContent = `${{data.skippedPrs}} skipped PR(s)`;
function activate(tab) {{ document.querySelectorAll(".tab").forEach(b => b.classList.toggle("active", b.dataset.tab === tab)); document.querySelectorAll(".page").forEach(p => p.classList.toggle("active", p.id === tab)); }}
document.addEventListener("click", event => {{ const button = event.target.closest(".tab"); if (button) activate(button.dataset.tab); }});
function metric(label, value, hint) {{ return `<div class="card metric"><div class="label">${{label}}</div><div class="value">${{value}}</div><div class="muted">${{hint}}</div></div>`; }}
function barRows(rows, key, suffix="%", lower=false, preserveOrder=false) {{ const ordered = preserveOrder ? rows.slice() : rows.slice().sort((a,b)=> lower ? (a[key]||0)-(b[key]||0) : (b[key]||0)-(a[key]||0)); const max = Math.max(...ordered.map(r => Math.abs(Number(r[key] || 0))), 1); return ordered.map(r => {{ const value = Number(r[key] || 0); const width = value === 0 ? 0 : Math.max((Math.abs(value)/max)*100,2); return `<div class="bar-row"><strong>${{r.user}}</strong><div class="track"><div class="fill" style="width:${{width}}%"></div></div><span>${{fmt(r[key], suffix)}}</span></div>`; }}).join(""); }}
function winnerCard(label, winner, suffix="") {{ return `<div class="winner-card"><div class="label">${{label}}</div><div class="name">${{winner ? winner.user : "N/A"}}</div><div class="score">${{winner ? fmt(winner.value, suffix) : "N/A"}}</div></div>`; }}
function topUser(users, key) {{ const candidates = (users || []).filter(u => u[key] !== null && u[key] !== undefined && Number(u[key]) > 0); if (!candidates.length) return null; const winner = candidates.sort((a,b) => Number(b[key])-Number(a[key]))[0]; return {{user:winner.user, value:winner[key]}}; }}
function latestWeeklyWinners(weekly) {{ const latest = weekly && weekly.length ? weekly[weekly.length - 1] : {{users:[]}}; return `<div class="winner-strip">${{winnerCard("This Week · Approvals Given", topUser(latest.users, "approvalsGiven"))}}${{winnerCard("This Week · Approval Coverage", topUser(latest.users, "approvalCoverageRate"), "%")}}${{winnerCard("This Week · Review Coverage", topUser(latest.users, "reviewCoverageRate"), "%")}}${{winnerCard("This Week · Avg Lines Delta", topUser(latest.users, "avgLinesDelta"))}}</div>`; }}
function allTimeWinnerCards(winners) {{ const overall = (winners || []).find(w => w.label === "Overall Normalized Activity"); const approvals = (winners || []).find(w => w.label === "Approvals Given Per Active Week"); const reviews = (winners || []).find(w => w.label === "Reviews Per Active Week"); const reviewShare = (winners || []).find(w => w.label === "Review Share"); return `<div class="winner-strip">${{winnerCard("All Time Best · Normalized Activity", overall && overall.best, "/wk")}}${{winnerCard("All Time Worst · Normalized Activity", overall && overall.worst, "/wk")}}${{winnerCard("All Time Best · Approvals Given", approvals && approvals.best, "/wk")}}${{winnerCard("All Time Best · Review Share", reviewShare && reviewShare.best, "%")}}</div>`; }}
function activityScore(p) {{ return Number(p.authoredPerActiveWeek || 0) + Number(p.mergedPerActiveWeek || 0) + Number(p.reviewedPerActiveWeek || 0) + Number(p.approvedPerActiveWeek || 0); }}
function allTimeLeaders(people) {{ const specs = [["Overall Normalized Activity", p => activityScore(p), "/wk", false], ["Approvals Given Per Active Week", p => p.approvedPerActiveWeek, "/wk", false], ["Reviews Per Active Week", p => p.reviewedPerActiveWeek, "/wk", false], ["Approval Rate", p => p.approvalRate, "%", false], ["Review Share", p => p.reviewShare, "%", false], ["Open Carryover Rate", p => p.openCarryoverRate, "%", true], ["Closed Unmerged Rate", p => p.closedUnmergedRate, "%", true]]; return specs.map(([label,getValue,suffix,lower]) => {{ const candidates = people.map(p => ({{user:p.user, value:getValue(p)}})).filter(p => p.value !== null && p.value !== undefined && Number(p.value) > 0); if (!candidates.length) return null; const sorted = candidates.sort((a,b) => lower ? Number(a.value)-Number(b.value) : Number(b.value)-Number(a.value)); return {{label, suffix, best:sorted[0], worst:sorted[sorted.length-1]}}; }}).filter(Boolean); }}
function chartColor(index) {{ return `hsl(${{(index * 47) % 360}} 82% 62%)`; }}
function personTrend(weekly, key, title, suffix="", zeroMissing=true) {{ const weeks = weekly || []; const users = Array.from(new Set(weeks.flatMap(w => (w.users || []).map(u => u.user)))).sort((a,b)=>a.localeCompare(b)); if (!weeks.length || !users.length) return `<div class="card"><h2>${{title}}</h2><div class="muted">No weekly data available.</div></div>`; const values = []; const weekValue = (week, user) => {{ const metric = (week.users || []).find(u => u.user === user); if (!metric || metric[key] === null || metric[key] === undefined) return zeroMissing ? 0 : null; return Number(metric[key]); }}; users.forEach(user => weeks.forEach(week => {{ const value = weekValue(week, user); if (value !== null) values.push(value); }})); const max = Math.max(...values, 1); const xFor = i => weeks.length === 1 ? 50 : 8 + (i/(weeks.length-1))*84; const yFor = value => 88 - ((Number(value)/max)*76); const lines = users.map((user,index) => {{ const points = weeks.map((week,i) => {{ const value = weekValue(week, user); return value === null ? null : `${{xFor(i)}},${{yFor(value)}}`; }}).filter(Boolean); if (!points.length) return ""; return `<polyline points="${{points.join(" ")}}" fill="none" stroke="${{chartColor(index)}}" stroke-width="2.5" opacity=".88" vector-effect="non-scaling-stroke"/>`; }}).join(""); const latest = users.map(user => {{ const last = weeks.slice().reverse().map(week => weekValue(week, user)).find(value => value !== null); return {{user, value:last ?? 0}}; }}); const leader = latest.slice().sort((a,b)=>b.value-a.value)[0]; return `<div class="card"><h2>${{title}}</h2><div class="muted">Every person with weekly data is graphed and labeled. Latest leader: ${{leader.user}} · ${{fmt(leader.value, suffix)}}</div><svg class="winner-chart" viewBox="0 0 100 100" preserveAspectRatio="none">${{lines}}<line x1="8" y1="92" x2="96" y2="92" stroke="rgba(255,255,255,.16)" vector-effect="non-scaling-stroke"/></svg><div class="trend-legend">${{users.map((user,index) => `<span><i class="legend-dot" style="background:${{chartColor(index)}}"></i>${{user}}</span>`).join("")}}</div></div>`; }}
function teamTrend(weekly, teams, key, title, suffix="", zeroMissing=true) {{ const activeTeams = teams.filter(t => t.members.length); const weeks = weekly || []; if (!weeks.length || !activeTeams.length) return `<div class="card"><h2>${{title}}</h2><div class="muted">Assign people to teams to generate this graph.</div></div>`; const aggregate = (week, team) => {{ const memberNames = new Set(team.members.map(p => p.user)); const values = (week.users || []).filter(u => memberNames.has(u.user)).map(u => u[key]).filter(v => v !== null && v !== undefined); if (!values.length) return zeroMissing ? 0 : null; if (key.includes("Rate") || key.includes("Coverage") || key.startsWith("avg")) return values.reduce((total,value) => total + Number(value), 0) / values.length; return values.reduce((total,value) => total + Number(value), 0); }}; const values = []; activeTeams.forEach(team => weeks.forEach(week => {{ const value = aggregate(week, team); if (value !== null) values.push(value); }})); const max = Math.max(...values, 1); const xFor = i => weeks.length === 1 ? 50 : 8 + (i/(weeks.length-1))*84; const yFor = value => 88 - ((Number(value)/max)*76); const lines = activeTeams.map((team,index) => {{ const points = weeks.map((week,i) => {{ const value = aggregate(week, team); return value === null ? null : `${{xFor(i)}},${{yFor(value)}}`; }}).filter(Boolean); return points.length ? `<polyline points="${{points.join(" ")}}" fill="none" stroke="${{chartColor(index)}}" stroke-width="3" opacity=".9" vector-effect="non-scaling-stroke"/>` : ""; }}).join(""); return `<div class="card"><h2>${{title}}</h2><div class="muted">Updates when people are assigned or unassigned.</div><svg class="winner-chart" viewBox="0 0 100 100" preserveAspectRatio="none">${{lines}}<line x1="8" y1="92" x2="96" y2="92" stroke="rgba(255,255,255,.16)" vector-effect="non-scaling-stroke"/></svg><div class="trend-legend">${{activeTeams.map((team,index) => `<span><i class="legend-dot" style="background:${{chartColor(index)}}"></i>${{team.name}}</span>`).join("")}}</div></div>`; }}
function table(headers, rows, cls="", tableAttrs="") {{ return `<div class="table-wrap ${{cls}}"><table class="sortable-table" ${{tableAttrs}}><thead><tr>${{headers.map(h=>`<th data-type="${{h.type||"text"}}">${{h.label}}</th>`).join("")}}</tr></thead><tbody>${{rows.map(row=>`<tr>${{row.map(cell=>`<td data-sort="${{cell.sort ?? cell.value}}">${{cell.html ?? cell.value}}</td>`).join("")}}</tr>`).join("")}}</tbody></table></div>`; }}
const uiSpecs = data.uiSpecs || {{}};
function cellFromSpec(row, col) {{ const raw = row[col.key]; let value = raw; let sort = raw; if (col.format === "percent") {{ value = pct(raw); sort = raw || 0; }} else if (col.format === "hours") {{ value = fmt(raw, "h"); sort = raw || 0; }} else if (col.format === "days") {{ value = fmt(raw, "d"); sort = raw || 0; }} else if (col.format === "perWeek") {{ value = fmt(raw, "/wk"); sort = raw || 0; }} else if (col.format === "fixed") {{ value = fmt(raw); sort = raw || 0; }} else if ((col.type || "text") === "number") {{ value = raw ?? 0; sort = raw || 0; }} else {{ value = raw ?? "N/A"; sort = raw ?? ""; }} return {{value, sort}}; }}
function specTable(spec, rows, cls="") {{ if (!spec) return ""; const attrs = `data-default-sort-col="${{spec.defaultSortCol}}" data-default-sort-dir="${{spec.defaultSortDir || "desc"}}"`; return table(spec.columns.map(c => ({{label:c.label, type:c.type||"text"}})), rows.map(r => spec.columns.map(c => cellFromSpec(r,c))), cls, attrs); }}
function specBarGrid(specs, rows) {{ return `<div class="grid two">${{(specs || []).map(s => `<div class="card"><h2>${{s.title}}</h2><div class="bars">${{barRows(rows, s.key, s.suffix ?? "%")}}</div></div>`).join("")}}</div>`; }}
const views = data.views || [{{id:"all", label:data.repository, overview:data.overview, people:data.people}}];
let activeViewId = views[0].id;
let teamCount = 2;
let teamAssignments = {{}};
let comparisonSelected = [];
function compareChip(user, index) {{ return `<button type="button" class="member-chip" data-remove-compare-user="${{user}}"><span class="chip-rank">${{index + 1}}</span>${{user}} ×</button>`; }}
function renderComparison(allPeople) {{
  const allowed = new Set(allPeople.map(p => p.user));
  comparisonSelected = comparisonSelected.filter(user => allowed.has(user));
  const focused = comparisonSelected.length > 0;
  const comparePeople = focused
    ? comparisonSelected.map(name => allPeople.find(p => p.user === name)).filter(Boolean)
    : allPeople.slice();
  const available = allPeople.filter(p => !comparisonSelected.includes(p.user)).sort((a,b) => a.user.localeCompare(b.user));
  const options = available.map(p => `<option value="${{p.user}}">${{p.user}}</option>`).join("");
  const selectionHint = focused
    ? `Comparing ${{comparePeople.length}} selected person${{comparePeople.length === 1 ? "" : "s"}}. Table and charts re-sort automatically when your selection changes.`
    : `Showing all ${{allPeople.length}} people. Pick names below to focus the comparison.`;
  const compareInput = `<div class="team-input-card"><h3>People to compare</h3><select id="compare-add"><option value="">Select people...</option>${{options}}</select><div class="selected-members">${{focused ? comparisonSelected.map((user, index) => compareChip(user, index)).join("") : `<span class="empty-pill">No members selected</span>`}}</div>${{focused ? `<button type="button" class="compare-clear" id="compare-clear">Clear selection</button>` : ""}}</div>`;
  const picker = `<div class="card"><h2>Compare People</h2><div class="muted">${{selectionHint}}</div><div class="team-input-board compare-input-board">${{compareInput}}</div></div>`;
  const compareSpec = uiSpecs.comparison || {{}};
  const tableBlock = comparePeople.length
    ? `<div class="card"><h2>Compare Everyone</h2>${{specTable(compareSpec.table, comparePeople, "comparison-scroll")}}</div>`
    : `<div class="card"><h2>Compare Everyone</h2><div class="muted">Select at least one person to compare.</div></div>`;
  const barsBlock = comparePeople.length
    ? `<div class="section-heading"><h2>Comparison Charts</h2><p>Normalized activity and raw PR counts for the selected scope. Each chart ranks people by that metric.</p></div>${{specBarGrid(compareSpec.bars, comparePeople)}}`
    : "";
  document.getElementById("comparison").innerHTML = `${{picker}}${{tableBlock}}${{barsBlock}}`;
}}
function applyTableSort(table, columnIndex, dir) {{ const header = table.querySelectorAll("th")[columnIndex]; if (!header || !table.tBodies[0]) return; table.querySelectorAll("th").forEach(x => {{ x.classList.remove("sorted-asc","sorted-desc"); delete x.dataset.sortDir; }}); header.dataset.sortDir = dir; header.classList.add(dir === "asc" ? "sorted-asc" : "sorted-desc"); Array.from(table.tBodies[0].rows).sort((a,b) => {{ const type = header.dataset.type; const av = a.cells[columnIndex].dataset.sort; const bv = b.cells[columnIndex].dataset.sort; if (type === "number") return dir === "asc" ? Number(av)-Number(bv) : Number(bv)-Number(av); return dir === "asc" ? String(av).localeCompare(String(bv)) : String(bv).localeCompare(String(av)); }}).forEach(r => table.tBodies[0].appendChild(r)); }}
function enableSort() {{ document.querySelectorAll("table.sortable-table").forEach(t => {{ t.querySelectorAll("th").forEach((h,i) => {{ h.onclick = () => {{ const dir = h.dataset.sortDir === "asc" ? "desc" : "asc"; applyTableSort(t, i, dir); }}; }}); if (t.dataset.defaultSortCol !== undefined) applyTableSort(t, Number(t.dataset.defaultSortCol), t.dataset.defaultSortDir || "desc"); }}); }}
function repoSwitcherButtons() {{ return views.map(v => `<button type="button" class="${{v.id === activeViewId ? "active" : ""}}" data-repo-view="${{v.id}}">${{v.label}}</button>`).join(""); }}
function renderRepoSwitcher() {{ const buttons = repoSwitcherButtons(); document.getElementById("repo-switcher").innerHTML = buttons; document.getElementById("side-repo-switcher").innerHTML = buttons; }}
function ensureUserState(people) {{ people.forEach(p => {{ if (teamAssignments[p.user] === undefined) teamAssignments[p.user] = ""; }}); }}
function filteredWeekly(weekly, people) {{ const allowed = new Set(people.map(p => p.user)); return (weekly || []).map(week => ({{...week, users:(week.users || []).filter(user => allowed.has(user.user))}})); }}
function teamName(team) {{ return `Team ${{team}}`; }}
function memberChip(person) {{ return `<button type="button" class="member-chip" data-remove-team-user="${{person.user}}">${{person.user}} ×</button>`; }}
function renderTeams(people, weekly) {{ people.forEach(p => {{ if (teamAssignments[p.user] && Number(teamAssignments[p.user]) > teamCount) teamAssignments[p.user] = ""; }}); const teams = Array.from({{length:teamCount}}, (_,i) => {{ const team = i + 1; const members = people.filter(p => Number(teamAssignments[p.user]) === team); const sum = key => members.reduce((total,p) => total + Number(p[key] || 0), 0); const avg = key => {{ const values = members.map(p => p[key]).filter(v => v !== null && v !== undefined); return values.length ? values.reduce((total,value) => total + Number(value), 0) / values.length : null; }}; return {{id:team, name:teamName(team), members, count:members.length, authored:sum("authored"), reviewed:sum("reviewed"), approved:sum("approved"), normalized:sum("authoredPerActiveWeek") + sum("mergedPerActiveWeek") + sum("reviewedPerActiveWeek") + sum("approvedPerActiveWeek"), avgLinesDelta:avg("avgLinesDelta")}}; }}); const available = people.filter(p => !teamAssignments[p.user]); const options = available.map(p => `<option value="${{p.user}}">${{p.user}}</option>`).join(""); const teamInputs = teams.map(team => `<div class="team-input-card"><h3>${{team.name}}</h3><select data-team-add="${{team.id}}"><option value="">Select people...</option>${{options}}</select><div class="selected-members">${{team.members.length ? team.members.map(memberChip).join("") : `<span class="empty-pill">No members selected</span>`}}</div></div>`); const teamSpec = uiSpecs.teams || {{}}; const graphRows = teams.map(t => ({{name:t.name, user:t.name, normalized:t.normalized, reviewed:t.reviewed, approved:t.approved, avgLinesDelta:t.avgLinesDelta || 0, count:t.count, authored:t.authored}})); document.getElementById("teams").innerHTML = `<div class="card"><h2>Teams</h2><div class="muted">Set the number of teams, then use each team's dropdown to select members. A person can only be selected in one team; remove a chip to make that person available again.</div><div class="team-control"><label class="side-label" for="team-count">Number of teams</label><input id="team-count" type="number" min="1" max="8" value="${{teamCount}}"></div><div class="team-input-board">${{teamInputs.join("")}}</div></div>${{specBarGrid(teamSpec.bars, graphRows)}}<div class="grid two">${{teamTrend(weekly, teams, "approvalsGiven", "Weekly Team Approvals Given")}}${{teamTrend(weekly, teams, "reviewCoverageRate", "Weekly Team Review Coverage", "%", false)}}${{teamTrend(weekly, teams, "approvalCoverageRate", "Weekly Team Approval Coverage", "%", false)}}${{teamTrend(weekly, teams, "avgLinesDelta", "Weekly Team Avg Lines Delta", "", false)}}</div><div class="card"><h2>Team Metrics</h2>${{specTable(teamSpec.table, teams)}}</div>`; }}
function renderDashboard(view) {{
const o = view.overview;
const allPeople = view.people;
const activePage = document.querySelector(".page.active")?.id || "overview";
ensureUserState(allPeople);
const people = allPeople;
const weekly = filteredWeekly(o.winners && o.winners.weekly, people);
const leaders = allTimeLeaders(people);
document.getElementById("scope").textContent = view.label;
document.getElementById("overview").innerHTML = `
  <div class="grid four">
    ${{metric("PRs Authored", o.authored, "Across selected scope")}}
    ${{metric("Team Merge Rate", pct(o.mergeRate), `${{o.merged}} merged`)}}
    ${{metric("Reviews", o.reviewed, "Distinct reviewed PRs")}}
    ${{metric("Median Merge Time", fmt(o.medianMergeHours, "h"), "Typical PR cycle")}}
    ${{metric("Avg Lines Added", fmt(o.avgLinesAdded), "Per authored PR detail row")}}
    ${{metric("Avg Lines Removed", fmt(o.avgLinesRemoved), "Per authored PR detail row")}}
  </div>
  <details class="card" open><summary><strong>Metric Formulas & Equations</strong></summary><div class="formulas" style="margin-top:14px">
    <div class="formula"><strong>Merge Rate</strong><code>prs_merged / prs_authored</code>How many opened PRs were merged.</div>
    <div class="formula"><strong>Review Coverage Rate</strong><code>authored_prs_with_first_feedback / prs_authored</code>Share of authored PRs that received review attention.</div>
    <div class="formula"><strong>Approval Coverage Rate</strong><code>authored_prs_with_approval / prs_authored</code>Share of authored PRs that received at least one approval.</div>
    <div class="formula"><strong>Approval Rate</strong><code>approvals_given / prs_reviewed</code>Of PRs a person reviewed, how many they approved.</div>
    <div class="formula"><strong>Open Carryover Rate</strong><code>prs_open_at_period_end / prs_authored</code>Share of authored PRs still open at the end of the period.</div>
    <div class="formula"><strong>Closed Unmerged Rate</strong><code>prs_closed_without_merge / prs_authored</code>Share of authored PRs closed without being merged.</div>
    <div class="formula"><strong>Authored Share</strong><code>person_prs_authored / team_prs_authored</code>How much of the selected scope's authored PR volume came from one person.</div>
    <div class="formula"><strong>Review Share</strong><code>person_prs_reviewed / team_prs_reviewed</code>How much of the selected scope's review activity came from one person.</div>
    <div class="formula"><strong>Largest Contributor Share</strong><code>max(person_authored_share)</code>The biggest authored PR share held by any one contributor.</div>
    <div class="formula"><strong>Inferred Start</strong><code>earliest authored PR or review in this window</code>If someone first appears inside the report window, normalized metrics use only their eligible active days.</div>
    <div class="formula"><strong>Normalized Activity Per Active Week</strong><code>activity_count / eligible_days * 7</code>Compares activity rates relative to the observed active span in the report.</div>
    <div class="formula"><strong>Overall Normalized Activity</strong><code>authored_per_active_week + merged_per_active_week + reviewed_per_active_week + approved_per_active_week</code>Combined normalized activity score used for all-time performance leaders.</div>
    <div class="formula"><strong>Approvals Given</strong><code>count(first_approvals_where_approved_by_user_and_author_is_someone_else)</code>Approvals a person gave to other people's PRs.</div>
    <div class="formula"><strong>Approvals Given Per Active Week</strong><code>approvals_given / eligible_days * 7</code>Normalized approval activity for review contribution comparisons.</div>
    <div class="formula"><strong>Avg Files Changed</strong><code>sum(files_added + files_modified + files_removed) / authored_prs</code>Average file-change breadth per authored PR.</div>
    <div class="formula"><strong>Avg Commits Per PR</strong><code>sum(pr_commits_total) / authored_prs</code>Average commit count across authored PRs.</div>
    <div class="formula"><strong>Avg Lines Added</strong><code>sum(pr_lines_added) / authored_prs_with_detail</code>Average added lines across authored PR detail rows.</div>
    <div class="formula"><strong>Avg Lines Removed</strong><code>sum(pr_lines_removed) / authored_prs_with_detail</code>Average removed lines across authored PR detail rows.</div>
    <div class="formula"><strong>Avg Lines Delta</strong><code>avg_lines_added - avg_lines_removed</code>Average net line delta per person's authored PR detail rows.</div>
    <div class="formula"><strong>Avg Time To First Feedback</strong><code>sum(first_feedback_at - pr_created_at) / prs_with_first_feedback</code>Average time from PR creation to first review/comment feedback.</div>
    <div class="formula"><strong>Avg Time To Approval</strong><code>sum(first_approval_at - pr_created_at) / approved_prs</code>Average time from PR creation to first approval.</div>
    <div class="formula"><strong>Avg Time To Merge</strong><code>sum(merged_at - pr_created_at) / merged_prs</code>Average PR cycle time for merged PRs.</div>
    <div class="formula"><strong>Median Time To Merge</strong><code>middle value of merged_at - pr_created_at</code>Typical merged PR cycle time, less sensitive to outliers than average.</div>
    <div class="formula"><strong>P90 Time To Merge</strong><code>90th percentile of merged_at - pr_created_at</code>Slow-tail merge time for merged PRs.</div>
    <div class="formula"><strong>Approval To Merge Time</strong><code>sum(merged_at - first_approval_at) / approved_and_merged_prs</code>Average time from approval to merge.</div>
    <div class="formula"><strong>Avg Open PR Age</strong><code>sum(report_end - pr_created_at) / open_prs</code>Average age of PRs still open at the end of the period.</div>
    <div class="formula"><strong>Stale PR Rate</strong><code>open_prs_older_than_7_days / open_prs</code>Share of open PRs older than the stale threshold.</div>
    <div class="formula"><strong>Review Response Target Rate</strong><code>prs_with_first_feedback_within_48h / prs_with_first_feedback</code>Share of feedback events that met the review response target.</div>
    <div class="formula"><strong>Merge Target Rate</strong><code>prs_merged_within_72h / merged_prs</code>Share of merged PRs that met the merge-time target.</div>
    <div class="formula"><strong>Weekly Approvals Given</strong><code>weekly_first_approvals_given_to_other_authors</code>Per-person weekly approval activity used in the Overview trend graph.</div>
    <div class="formula"><strong>Weekly Approval Coverage</strong><code>weekly_authored_prs_with_approval / weekly_authored_prs</code>Per-person weekly approval coverage used in the Overview trend graph.</div>
    <div class="formula"><strong>Weekly Review Coverage</strong><code>weekly_authored_prs_with_first_feedback / weekly_authored_prs</code>Per-person weekly review coverage used in the Overview trend graph.</div>
    <div class="formula"><strong>Weekly Avg Lines Delta</strong><code>weekly_avg_lines_added - weekly_avg_lines_removed</code>Per-person weekly net line delta used in the Overview trend graph.</div>
  </div></details>
  <div class="card"><h2>Winners & Performance Leaders</h2><div class="muted">All-time leaders use normalized activity plus review and approval activity. Approvals given count approvals a person gave to someone else's PR.</div>${{allTimeWinnerCards(leaders)}}${{latestWeeklyWinners(weekly)}}${{table([{{label:"Metric"}},{{label:"Best"}},{{label:"Best Value",type:"number"}},{{label:"Worst"}},{{label:"Worst Value",type:"number"}}], leaders.map(w => [{{value:w.label}},{{value:w.best.user}},{{value:fmt(w.best.value,w.suffix),sort:w.best.value}},{{value:w.worst.user}},{{value:fmt(w.worst.value,w.suffix),sort:w.worst.value}}]))}}</div>
  ${{specBarGrid((uiSpecs.overview || {{}}).bars, people)}}
  <div class="grid two">
    ${{personTrend(weekly, "approvalsGiven", "Weekly Approvals Given By Person")}}
    ${{personTrend(weekly, "approvalCoverageRate", "Weekly Approval Coverage By Person", "%", false)}}
    ${{personTrend(weekly, "reviewCoverageRate", "Weekly Review Coverage By Person", "%", false)}}
    ${{personTrend(weekly, "avgLinesDelta", "Weekly Avg Lines Delta By Person", "", false)}}
  </div>
  <div class="card"><h2>Repository Breakdown</h2>${{table([{{label:"Repository"}},{{label:"Authored",type:"number"}},{{label:"Merged",type:"number"}},{{label:"Reviewed",type:"number"}},{{label:"Avg Merge",type:"number"}},{{label:"P90 Merge",type:"number"}}], data.repositories.map(r => [{{value:r.name}},{{value:r.authored,sort:r.authored}},{{value:r.merged,sort:r.merged}},{{value:r.reviewed,sort:r.reviewed}},{{value:fmt(r.avgMergeHours,"h"),sort:r.avgMergeHours||0}},{{value:fmt(r.p90MergeHours,"h"),sort:r.p90MergeHours||0}}]), "scroll-y")}}</div>
  <div class="card"><h2>Overview Time-Based Metrics</h2><div class="formulas">
    <div class="formula"><strong>Avg Time To First Feedback</strong><code>${{fmt(o.avgFeedbackHours,"h")}} · lower is better</code>Shows how quickly PRs receive review attention.</div>
    <div class="formula"><strong>Avg Time To Approval</strong><code>${{fmt(o.avgApprovalHours,"h")}} · lower is better</code>Shows how long PRs wait before approval.</div>
    <div class="formula"><strong>Avg Time To Merge</strong><code>${{fmt(o.avgMergeHours,"h")}} · lower is better</code>Measures average PR cycle time.</div>
    <div class="formula"><strong>P90 Time To Merge</strong><code>${{fmt(o.p90MergeHours,"h")}} · lower is better</code>Highlights the slowest PR cycle-time tail.</div>
    <div class="formula"><strong>Stale PR Rate</strong><code>${{pct(o.staleRate)}} · lower is better</code>Share of open PRs older than threshold.</div>
  </div></div>`;
renderComparison(allPeople);
document.getElementById("person-tabs").innerHTML = "";
document.getElementById("person-pages").innerHTML = "";
people.forEach(p => {{ const pageId = `person-${{p.id}}`; document.getElementById("person-tabs").insertAdjacentHTML("beforeend", `<button class="tab" data-tab="${{pageId}}">${{p.user}}</button>`); document.getElementById("person-pages").insertAdjacentHTML("beforeend", `<section id="${{pageId}}" class="page"><div class="grid four">${{metric(p.user,p.authored,"PRs authored")}}${{metric("Approvals Given",p.approved,"approvals on others PRs")}}${{metric("Review Share",pct(p.reviewShare),"share of team reviews")}}${{metric("Avg Files Changed",fmt(p.avgFilesChanged,""),"per authored PR")}}</div><div class="card"><h2>Normalized Performance</h2><div class="formulas"><div class="formula"><strong>Inferred Start</strong><code>${{p.inferredStart}}</code>Earliest authored PR or review observed inside this report.</div><div class="formula"><strong>Eligible Days</strong><code>${{fmt(p.eligibleDays,"d")}}</code>Counts are normalized over this active span.</div><div class="formula"><strong>Authored Per Active Week</strong><code>${{fmt(p.authoredPerActiveWeek,"/wk")}}</code>Authored PR count divided by eligible days times seven.</div><div class="formula"><strong>Merged Per Active Week</strong><code>${{fmt(p.mergedPerActiveWeek,"/wk")}}</code>Merged PR count divided by eligible days times seven.</div><div class="formula"><strong>Reviewed Per Active Week</strong><code>${{fmt(p.reviewedPerActiveWeek,"/wk")}}</code>Reviewed PR count divided by eligible days times seven.</div><div class="formula"><strong>Approvals Given Per Active Week</strong><code>${{fmt(p.approvedPerActiveWeek,"/wk")}}</code>Approvals this person gave divided by eligible days times seven.</div></div></div><div class="card"><h2>Person Metrics</h2><div class="formulas"><div class="formula"><strong>Approval Rate</strong><code>${{pct(p.approvalRate)}}</code>${{p.approved}} approvals given across ${{p.reviewed}} reviewed PRs.</div><div class="formula"><strong>Open Carryover Rate</strong><code>${{pct(p.openCarryoverRate)}}</code>${{p.open}} PRs remained open at the end of the period.</div><div class="formula"><strong>Avg First Feedback</strong><code>${{fmt(p.avgFeedbackHours,"h")}}</code>Average created-to-first-feedback time.</div><div class="formula"><strong>P90 Merge Time</strong><code>${{fmt(p.p90MergeHours,"h")}}</code>Slow tail of this person's merged PRs.</div><div class="formula"><strong>Avg Files Changed</strong><code>${{fmt(p.avgFilesChanged,"")}}</code>Average files changed per PR.</div><div class="formula"><strong>Avg Commits</strong><code>${{fmt(p.avgCommits,"")}}</code>Average commits per PR.</div><div class="formula"><strong>Avg Lines Added</strong><code>${{fmt(p.avgLinesAdded,"")}}</code>Average code additions per authored PR detail row.</div><div class="formula"><strong>Avg Lines Removed</strong><code>${{fmt(p.avgLinesRemoved,"")}}</code>Average code deletions per authored PR detail row.</div><div class="formula"><strong>Avg Lines Delta</strong><code>${{fmt(p.avgLinesDelta,"")}}</code>Average lines added minus average lines removed.</div></div></div><div class="grid two"><div class="card"><h2>Review Activity Snapshot</h2><div class="bars">${{barRows([{{user:"Approval Rate",mergeRate:p.approvalRate}},{{user:"Review Share",mergeRate:p.reviewShare}},{{user:"Open Carryover",mergeRate:p.openCarryoverRate}},{{user:"Closed Unmerged",mergeRate:p.closedUnmergedRate}}],"mergeRate")}}</div></div><div class="card"><h2>Normalized Weekly Activity</h2><div class="bars">${{barRows([{{user:"Authored",authoredPerActiveWeek:p.authoredPerActiveWeek}},{{user:"Merged",authoredPerActiveWeek:p.mergedPerActiveWeek}},{{user:"Reviewed",authoredPerActiveWeek:p.reviewedPerActiveWeek}},{{user:"Approved",authoredPerActiveWeek:p.approvedPerActiveWeek}}],"authoredPerActiveWeek","/wk")}}</div></div><div class="card"><h2>Code Change Snapshot</h2><div class="bars">${{barRows([{{user:"Avg Files Changed",avgLinesAdded:p.avgFilesChanged}},{{user:"Avg Lines Added",avgLinesAdded:p.avgLinesAdded}},{{user:"Avg Lines Removed",avgLinesAdded:p.avgLinesRemoved}},{{user:"Avg Lines Delta",avgLinesAdded:p.avgLinesDelta}}],"avgLinesAdded","")}}</div></div></div><div class="card"><h2>PR Detail Highlights</h2>${{table([{{label:"PR",type:"number"}},{{label:"Status"}},{{label:"Time",type:"number"}},{{label:"Files",type:"number"}},{{label:"Lines Added",type:"number"}},{{label:"Lines Removed",type:"number"}}], p.prs.map(pr => [{{value:"#"+pr.number,sort:pr.number}},{{value:pr.status}},{{value:fmt(pr.timeHours,"h"),sort:pr.timeHours||0}},{{value:pr.files,sort:pr.files}},{{value:fmt(pr.linesAdded),sort:pr.linesAdded||0}},{{value:fmt(pr.linesRemoved),sort:pr.linesRemoved||0}}]), "scroll-y")}}</div></section>`); }});
renderRepoSwitcher();
renderTeams(people, weekly);
enableSort();
activate(document.getElementById(activePage) ? activePage : "overview");
}}
function activeView() {{ return views.find(v => v.id === activeViewId) || views[0]; }}
document.addEventListener("click", event => {{ const repoButton = event.target.closest("[data-repo-view]"); if (repoButton) {{ activeViewId = repoButton.dataset.repoView; renderDashboard(activeView()); return; }} const removeButton = event.target.closest("[data-remove-team-user]"); if (removeButton) {{ teamAssignments[removeButton.dataset.removeTeamUser] = ""; renderDashboard(activeView()); return; }} const removeCompare = event.target.closest("[data-remove-compare-user]"); if (removeCompare) {{ comparisonSelected = comparisonSelected.filter(user => user !== removeCompare.dataset.removeCompareUser); renderDashboard(activeView()); return; }} if (event.target.id === "compare-clear") {{ comparisonSelected = []; renderDashboard(activeView()); }} }});
document.addEventListener("change", event => {{ if (event.target.id === "team-count") {{ teamCount = Math.max(1, Math.min(8, Number(event.target.value) || 1)); renderDashboard(activeView()); return; }} if (event.target.id === "compare-add" && event.target.value) {{ comparisonSelected.push(event.target.value); renderDashboard(activeView()); return; }} const addSelect = event.target.closest("[data-team-add]"); if (addSelect && addSelect.value) {{ teamAssignments[addSelect.value] = Number(addSelect.dataset.teamAdd); renderDashboard(activeView()); }} }});
renderDashboard(views[0]);
</script>
</body>
</html>"""


def export_html_report(
    results: list[ReportResult],
    output_path: str | Path,
    *,
    bucket_granularity: str = "weekly",
) -> Path:
    payload = build_report_payload(results, bucket_granularity=bucket_granularity)
    target = Path(output_path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_html(payload), encoding="utf-8")
    return target
