#!/usr/bin/env python3
"""
Tab-delimited PR timeline report for a single GitHub repository (via `gh`).

Runs in three phases for exactly one repository (half-open window in REPORT_TZ — see below).
Every GitHub search and REST call is scoped to that single repo (`repo:owner/name` in search;
`/repos/owner/name/...` on the API). No other repository is queried.

  1) Discover PRs in that repo with activity in the window: merged in the window and/or PR created in the
     window (captures work that started as a PR in the month or finished in the month).
  2) Group those PR numbers by opening author (from search results).
  3) For each author, for each PR, fetch timeline fields, commit/file metrics, and append one TSV row.

Branches with no GitHub PR are not included.

--repo is one of: clone URL (https or git@), owner/name, or repo name only (see DEFAULT_GITHUB_OWNER).

Example (pilot repo global-services):
  --repo https://github.com/Customer-Engagement-Digital-Technology/global-services.git
  --start-date 2026-03-01 --end-date 2026-04-01
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from time import sleep
from urllib.parse import urlparse
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from typing import Any, Optional
from zoneinfo import ZoneInfo

GH_API_TIMEOUT_SEC = 90
GH_API_RETRIES = 4
GH_API_RETRY_BASE_SEC = 2
# Typical monthly run: a few PRs; one page (100 items) is enough for reviews/comments/events.
# Commits / PR files: paginate until a short page; cap pages so a pathological PR cannot loop forever.
API_LIST_PAGES_MAX = 100  # × 100 items/page = up to 10k commits or file rows per PR

# Calendar dates for --start-date / --end-date are interpreted in this timezone (DST-aware).
# All absolute times written to the TSV are formatted in this same timezone.
#
# Examples (uncomment one, or assign REPORT_TZ similarly):
#   REPORT_TZ = ZoneInfo("America/New_York") # US Eastern (default)
#   REPORT_TZ = ZoneInfo("America/Chicago")     # US Central
#   REPORT_TZ = ZoneInfo("America/Denver")      # US Mountain
#   REPORT_TZ = ZoneInfo("America/Los_Angeles") # US Pacific
#   REPORT_TZ = ZoneInfo("UTC")                 # UTC (calendar days & timestamps in Z/offset +00:00)
#   REPORT_TZ = ZoneInfo("Europe/London")       # UK (handles BST)
REPORT_TZ = ZoneInfo("America/New_York")

# If --repo is only the repository name (no "/"), this org/user is used unless you pass --owner.
DEFAULT_GITHUB_OWNER = "Customer-Engagement-Digital-Technology"

# Default TSV output directory (created automatically; listed in .gitignore).
DEFAULT_OUTPUT_DIR = "analysis-results"


def _transient_gh_failure(msg: str) -> bool:
    m = msg.lower()
    return any(
        s in m
        for s in (
            "connection reset",
            "connection refused",
            "broken pipe",
            "eof",
            "timeout",
            "temporarily unavailable",
            "503",
            "502",
            "504",
            "429",
            "tls handshake",
            "i/o timeout",
        )
    )


def _parse_report_calendar_date(s: str) -> date:
    """Parse YYYY-MM-DD for the report window (interpreted in REPORT_TZ)."""
    return datetime.strptime(s.strip(), "%Y-%m-%d").date()


def _window_bounds_utc_from_report_calendar(
    start_d: date, end_exclusive_d: date
) -> tuple[datetime, datetime]:
    """
    Half-open [start_d00:00, end_exclusive_d 00:00) in REPORT_TZ,
    returned as timezone-aware UTC datetimes for GitHub API search.
    """
    start_local = datetime.combine(start_d, time.min, tzinfo=REPORT_TZ)
    end_exclusive_local = datetime.combine(end_exclusive_d, time.min, tzinfo=REPORT_TZ)
    return (
        start_local.astimezone(timezone.utc),
        end_exclusive_local.astimezone(timezone.utc),
    )


def _iso_utc_z(utc_dt: datetime) -> str:
    utc_dt = utc_dt.astimezone(timezone.utc)
    return utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_github_ts(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    s = s.replace("Z", "+00:00")
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _hours_since(branch_start: datetime, event: Optional[datetime]) -> str:
    if event is None:
        return ""
    delta = event - branch_start
    hours = delta.total_seconds() / 3600.0
    # Branch start is a commit-time proxy; PR opened can be seconds before the oldest
    # returned commit. Clamp to zero so spreadsheets don't show misleading negatives.
    if hours < 0:
        hours = 0.0
    return f"{hours:.4f}"


def _fmt_ts(dt: Optional[datetime]) -> str:
    if dt is None:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(REPORT_TZ).isoformat(timespec="seconds")


def _gh_api_get(path: str, query: Optional[dict[str, str]] = None) -> Any:
    """
    GET a REST resource. Pass a path like /search/issues — not https://api.github.com/...
    Retries a few times on transient network / rate-limit style failures.
    """
    if path.startswith("https://api.github.com"):
        path = path[len("https://api.github.com") :]
    elif path.startswith("http://") or path.startswith("https://"):
        raise ValueError(f"unsupported URL for gh api: {path!r}")
    if not path.startswith("/"):
        path = "/" + path
    args = ["gh", "api", "-X", "GET", path]
    if query:
        for k, v in query.items():
            args.extend(["-f", f"{k}={v}"])

    last_err: Optional[BaseException] = None
    for attempt in range(1, GH_API_RETRIES + 1):
        try:
            proc = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=GH_API_TIMEOUT_SEC,
            )
        except subprocess.TimeoutExpired as e:
            last_err = e
            if attempt < GH_API_RETRIES and _transient_gh_failure(str(e)):
                sleep(GH_API_RETRY_BASE_SEC * attempt)
                continue
            raise RuntimeError(f"gh api timeout: {path}\n{e}") from e

        err_text = (proc.stderr or proc.stdout or "").strip()
        if proc.returncode == 0:
            return json.loads(proc.stdout) if proc.stdout.strip() else None

        last_err = RuntimeError(f"gh api failed: {path}\n{err_text or proc.stderr or proc.stdout}")
        if attempt < GH_API_RETRIES and _transient_gh_failure(err_text):
            sleep(GH_API_RETRY_BASE_SEC * attempt)
            continue
        raise last_err


def _get_list_100(path: str) -> list[dict[str, Any]]:
    """One GET, up to 100 items (enough for a small monthly set of PRs per person)."""
    sep = "&" if "?" in path else "?"
    data = _gh_api_get(f"{path}{sep}per_page=100")
    if not data:
        return []
    if not isinstance(data, list):
        raise RuntimeError(f"expected JSON array from {path!r}")
    return data


def _search_issues_all_pages(q: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for page in range(1, 21):
        data = _gh_api_get(
            "/search/issues",
            {"q": q, "per_page": "100", "page": str(page)},
        )
        if not data:
            break
        batch = data.get("items") or []
        items.extend(batch)
        if len(batch) < 100:
            break
    return items


def phase1_catalog_prs_merged_or_created(
    owner: str, repo: str, start_inclusive_utc: datetime, end_exclusive_utc: datetime
) -> dict[int, str]:
    """
    Phase 1: PRs active in the window — merged in range and/or PR opened (created) in range.
    Search bounds are UTC instants matching the REPORT_TZ calendar window.
    Returns pull number -> author login from issue search (same as PR opener in typical cases).

    Both searches use the same GitHub qualifier `repo:{owner}/{repo}` only — never org-wide or
    multi-repo. Branches/PRs from other repositories cannot appear in the catalog.
    """
    s = _iso_utc_z(start_inclusive_utc)
    e = _iso_utc_z(end_exclusive_utc)
    # Single-repository scope (required by GitHub issue search for this use case):
    base = f"repo:{owner}/{repo} is:pr"
    q_merged = f"{base} is:merged merged:>={s} merged:<{e}"
    q_created = f"{base} created:>={s} created:<{e}"
    catalog: dict[int, str] = {}
    for it in _search_issues_all_pages(q_merged) + _search_issues_all_pages(q_created):
        num = it.get("number")
        if num is None:
            continue
        login = ((it.get("user") or {}).get("login")) or ""
        catalog[int(num)] = login
    return catalog


def phase2_group_prs_by_user(catalog: dict[int, str]) -> list[tuple[str, list[int]]]:
    """Phase 2: ordered (author, sorted pr numbers) for stable report grouping."""
    by_user: dict[str, list[int]] = defaultdict(list)
    for pr_num, login in catalog.items():
        by_user[login or "(unknown)"].append(pr_num)
    return [
        (author, sorted(nums))
        for author, nums in sorted(by_user.items(), key=lambda kv: kv[0].lower())
    ]


def _commit_author_or_committer_ts(commit_payload: dict[str, Any]) -> Optional[datetime]:
    commit = commit_payload.get("commit") or {}
    authored = commit.get("author") or {}
    raw = authored.get("date") or (commit.get("committer") or {}).get("date")
    if not raw:
        return None
    return _parse_github_ts(raw)


def _pull_commits_all(
    owner: str, repo: str, pull_number: int
) -> tuple[list[dict[str, Any]], bool]:
    """
    All commits listed on the PR (API order newest-first). Returns (commits, truncated)
    if the safety page cap was hit with a full last page.
    """
    base = f"/repos/{owner}/{repo}/pulls/{pull_number}/commits"
    all_c: list[dict[str, Any]] = []
    truncated = False
    for page in range(1, API_LIST_PAGES_MAX + 1):
        sep = "&" if "?" in base else "?"
        chunk = _gh_api_get(f"{base}{sep}per_page=100&page={page}")
        if not chunk or not isinstance(chunk, list):
            break
        all_c.extend(chunk)
        if len(chunk) < 100:
            break
        if page == API_LIST_PAGES_MAX:
            truncated = True
            break
    return all_c, truncated


def _branch_start_from_commits(commits: list[dict[str, Any]]) -> Optional[datetime]:
    best: Optional[datetime] = None
    for c in commits:
        dt = _commit_author_or_committer_ts(c)
        if dt and (best is None or dt < best):
            best = dt
    return best


def _commits_before_after_open(
    commits: list[dict[str, Any]], pr_open: Optional[datetime]
) -> tuple[Optional[int], Optional[int]]:
    """Counts vs PR opened_at; (None, None) if open time unknown. before + after == len(commits)."""
    if pr_open is None:
        return None, None
    before = 0
    after = 0
    for c in commits:
        dt = _commit_author_or_committer_ts(c)
        if dt is None:
            after += 1
            continue
        if dt < pr_open:
            before += 1
        else:
            after += 1
    return before, after


def _pr_file_counts(files: list[dict[str, Any]]) -> tuple[int, int, int, int]:
    """
    (total_paths, added, modified, removed).
    modified = modified, renamed, copied, changed, and any other non-add non-remove status.
    """
    added = removed = modified = 0
    for f in files:
        st = (f.get("status") or "").lower()
        if st == "added":
            added += 1
        elif st == "removed":
            removed += 1
        else:
            modified += 1
    return len(files), added, modified, removed


def _pull_pr_files_all(
    owner: str, repo: str, pull_number: int
) -> tuple[list[dict[str, Any]], bool]:
    base = f"/repos/{owner}/{repo}/pulls/{pull_number}/files"
    all_f: list[dict[str, Any]] = []
    truncated = False
    for page in range(1, API_LIST_PAGES_MAX + 1):
        sep = "&" if "?" in base else "?"
        chunk = _gh_api_get(f"{base}{sep}per_page=100&page={page}")
        if not chunk or not isinstance(chunk, list):
            break
        all_f.extend(chunk)
        if len(chunk) < 100:
            break
        if page == API_LIST_PAGES_MAX:
            truncated = True
            break
    return all_f, truncated


def _append_note(existing: str, part: str) -> str:
    part = part.strip()
    if not part:
        return existing
    if not existing:
        return part
    return f"{existing}; {part}"


def _pull_detail(owner: str, repo: str, pull_number: int) -> dict[str, Any]:
    return _gh_api_get(f"/repos/{owner}/{repo}/pulls/{pull_number}")


def _issue_events(owner: str, repo: str, issue_number: int) -> list[dict[str, Any]]:
    return _get_list_100(f"/repos/{owner}/{repo}/issues/{issue_number}/events")


def _issue_comments(owner: str, repo: str, issue_number: int) -> list[dict[str, Any]]:
    return _get_list_100(f"/repos/{owner}/{repo}/issues/{issue_number}/comments")


def _pull_reviews(owner: str, repo: str, pull_number: int) -> list[dict[str, Any]]:
    return _get_list_100(f"/repos/{owner}/{repo}/pulls/{pull_number}/reviews")


def _first_draft_and_ready(
    pr_created: datetime,
    events: list[dict[str, Any]],
    head_json: dict[str, Any],
) -> tuple[Optional[datetime], Optional[datetime]]:
    """
    first_draft_at: earliest time PR was in draft (opening-as-draft approximated by
    first `converted_to_draft`, or if only `ready_for_review` exists after create, draft may be unknown).

    ready_for_review_at: first `ready_for_review` event, or pr_created if never draft.
    """
    evs = sorted(events, key=lambda e: e.get("created_at") or "")
    first_draft: Optional[datetime] = None
    ready: Optional[datetime] = None

    for ev in evs:
        et = ev.get("event") or ""
        ts = _parse_github_ts(ev.get("created_at"))
        if not ts:
            continue
        if et == "converted_to_draft":
            if first_draft is None:
                first_draft = ts
        elif et == "ready_for_review":
            if ready is None:
                ready = ts

    # If never draft in events, treat as non-draft at creation
    if first_draft is None and ready is None:
        ready = pr_created
    elif first_draft is not None and ready is None:
        # Still draft at end — leave ready empty
        pass
    elif first_draft is None and ready is not None:
        # Opened non-draft, then maybe toggled — if ready exists before any draft, it's first non-draft
        ready = ready

    return first_draft, ready


def _first_feedback_time(
    reviews: list[dict[str, Any]],
    comments: list[dict[str, Any]],
) -> Optional[datetime]:
    times: list[datetime] = []
    for r in reviews:
        st = _parse_github_ts(r.get("submitted_at"))
        if st:
            times.append(st)
    for c in comments:
        ct = _parse_github_ts(c.get("created_at"))
        if ct:
            times.append(ct)
    return min(times) if times else None


def _first_approval_time(reviews: list[dict[str, Any]]) -> Optional[datetime]:
    approved: list[datetime] = []
    for r in reviews:
        if (r.get("state") or "").upper() != "APPROVED":
            continue
        st = _parse_github_ts(r.get("submitted_at"))
        if st:
            approved.append(st)
    return min(approved) if approved else None


@dataclass
class Row:
    author: str
    branch: str
    pr_number: int
    pr_url: str
    branch_start: Optional[datetime]
    pr_created: Optional[datetime]
    first_draft: Optional[datetime]
    ready_for_review: Optional[datetime]
    first_feedback: Optional[datetime]
    approved: Optional[datetime]
    merged: Optional[datetime]
    closed_at: Optional[datetime]
    notes: str = ""
    pr_files_total: int = 0
    pr_files_added: int = 0
    pr_files_modified: int = 0
    pr_files_removed: int = 0
    pr_commits_total: int = 0
    pr_commits_before_pr_open: Optional[int] = None
    pr_commits_after_pr_open: Optional[int] = None


def _build_row(
    owner: str,
    repo: str,
    pull_number: int,
    *,
    report_author: Optional[str] = None,
) -> Row:
    detail = _pull_detail(owner, repo, pull_number)
    author = report_author if report_author is not None else (((detail.get("user") or {}).get("login")) or "")
    branch = detail.get("head", {}).get("ref") or ""
    html_url = detail.get("html_url") or ""
    pr_created = _parse_github_ts(detail.get("created_at"))
    merged = _parse_github_ts(detail.get("merged_at"))
    closed_at = _parse_github_ts(detail.get("closed_at"))

    commits, commits_trunc = _pull_commits_all(owner, repo, pull_number)
    branch_start = _branch_start_from_commits(commits)
    pr_commits_before, pr_commits_after = _commits_before_after_open(commits, pr_created)
    files, files_trunc = _pull_pr_files_all(owner, repo, pull_number)
    f_total, f_add, f_mod, f_rem = _pr_file_counts(files)

    events = _issue_events(owner, repo, pull_number)
    first_draft, ready = _first_draft_and_ready(pr_created or datetime.now(timezone.utc), events, detail)

    reviews = _pull_reviews(owner, repo, pull_number)
    comments = _issue_comments(owner, repo, pull_number)
    first_fb = _first_feedback_time(reviews, comments)
    appr = _first_approval_time(reviews)

    notes = ""
    if branch_start is None:
        notes = "branch_start_unavailable"
    if commits_trunc:
        notes = _append_note(notes, "pr_commits_list_truncated")
    if files_trunc:
        notes = _append_note(notes, "pr_files_list_truncated")

    return Row(
        author=author,
        branch=branch,
        pr_number=pull_number,
        pr_url=html_url,
        branch_start=branch_start,
        pr_created=pr_created,
        first_draft=first_draft,
        ready_for_review=ready,
        first_feedback=first_fb,
        approved=appr,
        merged=merged,
        closed_at=closed_at,
        notes=notes,
        pr_files_total=f_total,
        pr_files_added=f_add,
        pr_files_modified=f_mod,
        pr_files_removed=f_rem,
        pr_commits_total=len(commits),
        pr_commits_before_pr_open=pr_commits_before,
        pr_commits_after_pr_open=pr_commits_after,
    )


def _ts_pair(branch_start: Optional[datetime], event: Optional[datetime]) -> tuple[str, str]:
    if branch_start is None:
        return _fmt_ts(event), ""
    return _fmt_ts(event), _hours_since(branch_start, event)


def _emit_tsv(
    rows: list[Row],
    fh: Any,
    *,
    owner: str,
    repo: str,
    start_date_str: str,
    end_date_str: str,
) -> None:
    """
    Writes a short preamble/footer without tab characters so Excel opens them as full-width
    note rows; the table starts at the header row (line 3).
    """
    tz_key = REPORT_TZ.key
    fh.write(
        f"GitHub PR timeline — {owner}/{repo} — calendar window {start_date_str} .. "
        f"{end_date_str} (end date exclusive) — event times {tz_key}\n"
    )
    fh.write(
        f"Datetime columns in the table below are local wall-clock in {tz_key} (ISO-8601 with offset). "
        "Hour/delta columns are decimal elapsed hours. Row 3 is the column header; rows 1–2 are notes.\n"
    )

    headers = [
        "committer",
        "head_branch",
        "pr_number",
        "notes",
        "pr_url",
        "branch_start",
        "branch_start_hours_since_branch",
        "pr_created",
        "pr_created_hours_since_branch",
        "first_draft",
        "first_draft_hours_since_branch",
        "ready_for_review",
        "ready_for_review_hours_since_branch",
        "first_feedback",
        "first_feedback_hours_since_branch",
        "approved",
        "approved_hours_since_branch",
        "merged",
        "merged_hours_since_branch",
        "hours_pr_created_to_first_feedback",
        "hours_pr_created_to_approved",
        "hours_pr_created_to_closed",
        "pr_files_total",
        "pr_files_added",
        "pr_files_modified",
        "pr_files_removed",
        "pr_commits_total",
        "pr_commits_before_pr_open",
        "pr_commits_after_pr_open",
    ]
    fh.write("\t".join(headers) + "\n")

    for r in rows:
        bs = r.branch_start
        p_c = r.pr_created
        fd = r.first_draft
        rf = r.ready_for_review
        ff = r.first_feedback
        ap = r.approved
        mg = r.merged

        def seg(a: Optional[datetime], b: Optional[datetime]) -> str:
            if a is None or b is None:
                return ""
            return f"{(b - a).total_seconds() / 3600.0:.4f}"

        line = [
            r.author,
            r.branch,
            str(r.pr_number),
            r.notes,
            r.pr_url,
            *_ts_pair(bs, bs),
            *_ts_pair(bs, p_c),
            *_ts_pair(bs, fd),
            *_ts_pair(bs, rf),
            *_ts_pair(bs, ff),
            *_ts_pair(bs, ap),
            *_ts_pair(bs, mg),
            seg(p_c, ff),
            seg(p_c, ap),
            seg(p_c, r.closed_at),
            str(r.pr_files_total),
            str(r.pr_files_added),
            str(r.pr_files_modified),
            str(r.pr_files_removed),
            str(r.pr_commits_total),
            "" if r.pr_commits_before_pr_open is None else str(r.pr_commits_before_pr_open),
            "" if r.pr_commits_after_pr_open is None else str(r.pr_commits_after_pr_open),
        ]
        fh.write("\t".join(line) + "\n")

    fh.write(
        f"END NOTES — All datetime columns above use IANA timezone {tz_key} "
        f"(change REPORT_TZ at top of script). Repository {owner}/{repo} only.\n"
    )
    fh.write(
        "END NOTES — For a clean table in Excel you may delete this line and the line above, "
        "plus the two title lines at the top of the file.\n"
    )


def _default_output_filename(repo: str, start_date_str: str, end_date_str: str) -> str:
    """{repo}_{start}_to_{end}.tsv — safe for common filesystems; reruns overwrite the same path."""
    safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in repo.strip())
    return f"{safe or 'repo'}_{start_date_str}_to_{end_date_str}.tsv"


def _default_output_path(repo: str, start_date_str: str, end_date_str: str) -> str:
    """Default path under DEFAULT_OUTPUT_DIR (relative to process cwd unless overridden later)."""
    return os.path.join(DEFAULT_OUTPUT_DIR, _default_output_filename(repo, start_date_str, end_date_str))


def _resolve_repository(repo_arg: str, owner_override: str) -> tuple[str, str]:
    """
    One repository per run. Accepts:
 - https://github.com/org/repo or https://github.com/org/repo.git (browser / clone URL)
      - git@github.com:org/repo.git (SSH)
      - org/repo
      - repo-name only (uses --owner or DEFAULT_GITHUB_OWNER)
    """
    s = repo_arg.strip().rstrip("/")
    note_owner_ignored = False

    if s.startswith("git@"):
        if ":" not in s:
            raise ValueError(f"invalid git SSH URL: {repo_arg!r}")
        _, _, rest = s.partition(":")
        rest = rest.removesuffix(".git").strip()
        parts = rest.split("/", 1)
        if len(parts) != 2 or not parts[0] or not parts[1]:
            raise ValueError(f"could not parse owner/repo from SSH URL: {repo_arg!r}")
        owner, name = parts[0], parts[1]
        note_owner_ignored = True
    elif s.startswith("http://") or s.startswith("https://"):
        parsed = urlparse(s)
        path = (parsed.path or "").strip("/")
        if path.endswith(".git"):
            path = path[:-4]
        segments = [p for p in path.split("/") if p]
        if len(segments) < 2:
            raise ValueError(
                f"expected a URL like https://github.com/owner/repo — got: {repo_arg!r}"
            )
        owner, name = segments[0], segments[1]
        note_owner_ignored = True
    elif "/" in s:
        owner, _, name = s.partition("/")
        owner, name = owner.strip(), name.strip().strip("/")
        note_owner_ignored = True
    else:
        name = s.strip("/")
        owner = owner_override.strip() or DEFAULT_GITHUB_OWNER

    if not owner or not name:
        raise ValueError("owner and repository name must be non-empty")

    if note_owner_ignored and owner_override.strip():
        print(
            "Note: --owner ignored because --repo already includes owner (URL or owner/name).",
            file=sys.stderr,
        )
    return owner, name


def main() -> int:
    p = argparse.ArgumentParser(
        description=(
            "PR timeline report for a single GitHub repository: merged or created in date range, "
            "grouped by author. "
            f"Calendar dates use {REPORT_TZ.key} (set REPORT_TZ in script to change)."
        ),
        epilog=(
            "Examples (one repository per run):\n"
            "  %(prog)s --repo global-services --start-date 2026-03-01 --end-date 2026-04-01\n"
            f"    -> writes {DEFAULT_OUTPUT_DIR}/global-services_2026-03-01_to_2026-04-01.tsv (overwrites if rerun)\n"
            "  %(prog)s --repo https://github.com/Customer-Engagement-Digital-Technology/global-services.git \\\n"
            " --start-date 2026-03-01 --end-date 2026-04-01 -o my-report.tsv\n"
            "  %(prog)s --repo global-services --start-date 2026-03-01 --end-date 2026-04-01 -o - # stdout"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--repo",
        required=True,
        help=(
            "Single repository: HTTPS/SSH clone URL, owner/name, or repo name only "
            f"(name-only uses --owner or DEFAULT_GITHUB_OWNER={DEFAULT_GITHUB_OWNER!r})."
        ),
    )
    p.add_argument(
        "--owner",
        default="",
        help=(
            "GitHub org or user when --repo is only the repository name (no URL, no slash). "
            f"Default from script: {DEFAULT_GITHUB_OWNER!r}. Ignored for URLs and owner/name."
        ),
    )
    p.add_argument(
        "--start-date",
        required=True,
        help=f"Start date inclusive in report TZ ({REPORT_TZ.key}), YYYY-MM-DD",
    )
    p.add_argument(
        "--end-date",
        required=True,
        help=(
            f"End date exclusive in report TZ ({REPORT_TZ.key}): first calendar day not in range. "
            "E.g. 2026-04-01 for all of March through 2026-03-31."
        ),
    )
    p.add_argument(
        "-o",
        "--output",
        metavar="PATH",
        help=(
            f"Output .tsv path. Default: {DEFAULT_OUTPUT_DIR}/{{repo}}_{{start-date}}_to_{{end-date}}.tsv "
            f"(directory is created if missing; same repo + dates overwrites). Use - for stdout."
        ),
    )
    args = p.parse_args()

    try:
        owner, repo = _resolve_repository(args.repo, args.owner)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2

    start_d = _parse_report_calendar_date(args.start_date)
    end_d = _parse_report_calendar_date(args.end_date)
    if end_d <= start_d:
        print("Error: --end-date must be after --start-date (end is exclusive)", file=sys.stderr)
        return 2

    start_utc, end_exclusive_utc = _window_bounds_utc_from_report_calendar(start_d, end_d)

    print(
        f"Repository: {owner}/{repo} (single repo per run)",
        file=sys.stderr,
    )
    print(
        f"Report timezone: {REPORT_TZ.key} — window {args.start_date} .. {args.end_date} "
        f"(half-open; UTC bounds {_iso_utc_z(start_utc)} .. {_iso_utc_z(end_exclusive_utc)})",
        file=sys.stderr,
    )
    print(
        "Phase 1: GitHub search is limited to this repo only (repo:… qualifier on every query)…",
        file=sys.stderr,
    )
    catalog = phase1_catalog_prs_merged_or_created(owner, repo, start_utc, end_exclusive_utc)
    users = sorted({login or "(unknown)" for login in catalog.values()}, key=str.lower)
    print(
        f"Phase 1: {len(catalog)} PR(s), {len(users)} user(s)",
        file=sys.stderr,
    )
    if users:
        print("Users:", file=sys.stderr)
        for u in users:
            print(f"  {u}", file=sys.stderr)
    else:
        print("Users: (none)", file=sys.stderr)

    print("Running…", file=sys.stderr)
    grouped = phase2_group_prs_by_user(catalog)
    total_prs = sum(len(nums) for _, nums in grouped)
    built: list[Row] = []
    skipped = 0
    idx = 0
    for author, pr_numbers in grouped:
        for num in pr_numbers:
            idx += 1
            print(f"[{idx}/{total_prs}] PR #{num} ({author}) …", file=sys.stderr, flush=True)
            try:
                row = _build_row(owner, repo, num, report_author=author)
                built.append(row)
                print(
                    f"    → branch {row.branch!r} (done)",
                    file=sys.stderr,
                    flush=True,
                )
            except Exception as ex:
                skipped += 1
                print(
                    f"    → skip PR #{num}: {ex}",
                    file=sys.stderr,
                    flush=True,
                )

    print(
        f"Done: {len(built)} row(s) in report; skipped {skipped} PR(s).",
        file=sys.stderr,
    )

    if args.output is None:
        os.makedirs(DEFAULT_OUTPUT_DIR, exist_ok=True)
        out_path = _default_output_path(repo, args.start_date, args.end_date)
        print(f"Writing {out_path} (default; overwrites if it already exists)", file=sys.stderr)
        out = open(out_path, "w", encoding="utf-8")
        close_out = True
    elif args.output == "-":
        out = sys.stdout
        close_out = False
    else:
        print(f"Writing {args.output!r} (overwrites if it already exists)", file=sys.stderr)
        out = open(args.output, "w", encoding="utf-8")
        close_out = True
    try:
        _emit_tsv(
            built,
            out,
            owner=owner,
            repo=repo,
            start_date_str=args.start_date,
            end_date_str=args.end_date,
        )
    finally:
        if close_out:
            out.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
