# GitHub PR timeline report (`github-analysis`)

> **Protected document:** Do not change this file unless the **project owner explicitly allows it**. This README is the **canonical backup spec** for report output (especially the TSV column reference). **Coding assistants:** see **`AGENTS.md`** in this directory—you must not edit this README without direct permission, and you must not silently “fix” or resync it after code changes.

Small utility to pull **pull-request lifecycle timing** for **one GitHub repository per run** into a **tab-separated (TSV)** file for spreadsheets. It uses the [GitHub CLI](https://cli.github.com/) (`gh`), which must be authenticated on the machine where you run it.

**Output specification:** The full, ordered list of TSV columns and meanings is **[TSV column reference (canonical contract)](#tsv-column-reference-canonical-contract)** below. The Python script should match that table; keeping code and this document aligned is a **human-owned** change unless you have been **explicitly told** you may edit this file (see **`AGENTS.md`** for assistants).

There is **no multi-repo mode**: each invocation analyzes exactly the repo you pass with `--repo` (see below).

## Prerequisites

- **Python 3.9+** (uses `zoneinfo` for time zones; otherwise standard library + `gh`).
- **GitHub CLI** installed and logged in: `gh auth login`  
  For private org repos you need a token with appropriate access (for example `repo`) and, if your org uses SSO, the token authorized for that org.
- Run from this directory (or pass the full path to the script).

## Report timezone (default: US Eastern)

At the **top of** `github_pr_timeline_report.py`, set **`REPORT_TZ`** (see the comment block there for copy-paste examples).

```python
REPORT_TZ = ZoneInfo("America/New_York")  # default — US Eastern
```

**Other common choices:**

| Region | Typical `ZoneInfo(...)` value |
|--------|-------------------------------|
| US Eastern | `America/New_York` |
| US Central | `America/Chicago` |
| US Mountain | `America/Denver` |
| US Pacific (West) | `America/Los_Angeles` |
| UTC | `UTC` |

- **`--start-date` / `--end-date`** are **calendar days in `REPORT_TZ`** (half-open interval; DST is handled correctly).
- **Every absolute timestamp in the TSV** is formatted in **`REPORT_TZ`** (ISO-8601 with offset, for example `2026-03-15T14:30:00-04:00` in Eastern).
- GitHub search uses **UTC instants** under the hood; the script converts your calendar window to UTC and prints those bounds on stderr when it starts.

> **Note:** Datetime column headers are short names (`branch_start`, `pr_created`, …); the **timezone** for those values is stated in the first two lines and the footer of each TSV (`REPORT_TZ` in the script, default US Eastern).

## Which repository (`--repo`)

The tool is built for **exactly one GitHub.com repository per run**. There is no batch or multi-repo mode.

**Pilot / example repo:** [global-services](https://github.com/Customer-Engagement-Digital-Technology/global-services)  
(`Customer-Engagement-Digital-Technology` / `global-services` — same as clone URL `https://github.com/Customer-Engagement-Digital-Technology/global-services.git`.)

### How should you pass the repo? (advice)

| Style | Example | When to use |
|--------|---------|-------------|
| **HTTPS URL** | `https://github.com/Customer-Engagement-Digital-Technology/global-services.git` | Easiest when copying from the browser address bar or a `git clone` line. Typos in org/name are less common. |
| **`owner/name`** | `Customer-Engagement-Digital-Technology/global-services` | Compact; matches how `gh` and many docs refer to repos. Good for scripts and shared runbooks. |
| **Short name** | `global-services` | Fastest if **`DEFAULT_GITHUB_OWNER`** in the script matches your org (default is `Customer-Engagement-Digital-Technology`). Use **`--owner OtherOrg`** if the repo lives under a different org. |

**Recommendation:** Use a **full URL** for ad-hoc runs (paste and go). Use **`owner/name`** in automation. Use the **short name** only when your team agrees on the default org in the script.

The script also accepts **SSH** clone URLs (`git@github.com:org/repo.git`). For an `https://…` or `git@…` URL, **`--owner` is ignored** (the URL already defines the owner).

Branch links such as `https://github.com/org/repo/tree/main` work: only the **`org`** and **`repo`** segments are read.

**GitHub Enterprise hosts:** If your clone URL is `https://github.mycompany.com/org/repo`, the same parsing applies (first two path segments after the host).

## Quick start

**Option A — paste the clone URL (global-services)**  
By default writes **`analysis-results/global-services_2026-03-01_to_2026-04-01.tsv`** (under the repo’s **`analysis-results/`** folder, created if missing; rerunning the same command **overwrites** that file). That directory is **gitignored** so reports stay local unless you force-add them.

```bash
cd ~/Dev/github-analysis
python3 github_pr_timeline_report.py \
  --repo https://github.com/Customer-Engagement-Digital-Technology/global-services.git \
  --start-date 2026-03-01 \
  --end-date 2026-04-01
```

**Option B — short repo name** (uses `DEFAULT_GITHUB_OWNER` in the script) — same default filename pattern.

```bash
python3 github_pr_timeline_report.py \
  --repo global-services \
  --start-date 2026-03-01 \
  --end-date 2026-04-01
```

**Option C — `owner/name`** — default path is still **`analysis-results/{repo}_{start}_to_{end}.tsv`**.

```bash
python3 github_pr_timeline_report.py \
  --repo Customer-Engagement-Digital-Technology/global-services \
  --start-date 2026-03-01 \
  --end-date 2026-04-01
```

Use **`-o path.tsv`** to choose any path or filename; **`-o -`** prints TSV to stdout.

## More examples

**1 — Short repo name, different org**

```bash
python3 github_pr_timeline_report.py \
  --repo my-service \
  --owner SomeOtherOrg \
  --start-date 2026-03-01 \
  --end-date 2026-04-01 \
  -o out.tsv
```

**2 — One week in US Eastern** (Mon 2026-03-02 through Sun 2026-03-08, inclusive of full days in Eastern), same default org — writes `analysis-results/global-services_2026-03-02_to_2026-03-09.tsv` by default.
```bash
python3 github_pr_timeline_report.py \
  --repo global-services \
  --start-date 2026-03-02 \
  --end-date 2026-03-09
```

**3 — Use US Central for the calendar window and timestamps**  
Edit the script: `REPORT_TZ = ZoneInfo("America/Chicago")`, then run the same command; `--start-date` / `--end-date` are now interpreted in Chicago time.

**4 — Use UTC for everything**  
Edit the script: `REPORT_TZ = ZoneInfo("UTC")`. Then “all of March 2026 UTC” is still `--start-date 2026-03-01 --end-date 2026-04-01`.

**5 — Print TSV to the terminal** (`-o -`; progress on stderr)

```bash
python3 github_pr_timeline_report.py --repo global-services \
  --start-date 2026-03-01 --end-date 2026-04-01 -o - 2>progress.log | head -20
```

### Date range (important)

Half-open interval in **`REPORT_TZ`** (default US Eastern):

- **`--start-date`** — Included from **00:00** on that calendar day in the report timezone.
- **`--end-date`** — **Excluded**: the window ends just before **00:00** on this calendar day in the report timezone.

So **all of March 2026** in Eastern is:

`--start-date 2026-03-01 --end-date 2026-04-01`

### What PRs are included (Phase 1)

A PR is in the report if **either** is true (same time window as above):

1. **Merged** during the window — merge time falls in `[start-date, end-date)`.
2. **Opened** during the window — the PR was **created** during `[start-date, end-date)`, even if it merges later or is still open.

So you capture branches **finished** in the period and work **started as a PR** in the period.  
**Not included:** commits on a branch with **no** PR created in the window (no GitHub PR to attach to).

### Arguments

| Argument | Required | Meaning |
|----------|----------|---------|
| `--repo` | Yes | **Single** repository: HTTPS/SSH URL, `owner/name`, or short name (e.g. `global-services`). |
| `--owner` | No | Org/user when `--repo` is **only** the repo name (no URL, no slash). Defaults to `DEFAULT_GITHUB_OWNER` in the script. Ignored for URLs and `owner/name`. |
| `--start-date` | Yes | `YYYY-MM-DD`, inclusive, in `REPORT_TZ`. |
| `--end-date` | Yes | `YYYY-MM-DD`, exclusive, in `REPORT_TZ`. |
| `-o` / `--output` | No | TSV path. **Default:** **`analysis-results/{repo}_{start-date}_to_{end-date}.tsv`** (directory created if needed; different date ranges → different files; **same** command overwrites). **`-`** = write to **stdout**. |

---

## What the script does (three phases)

### Phase 1 — Which PRs count?

For **that one repository**, it unions two GitHub searches (still the same repo — “merged” vs “created” are two filters, not two repos). UTC bounds match your **report timezone** calendar window:

1. **Merged in the window**
2. **PR created (opened) in the window**

It prints `Repository: owner/name`, the report timezone, UTC search bounds, PR/user counts, and user logins.

### Phase 2 — Group by user

PR numbers are grouped by opener login from search so the report is ordered by **committer**, then by PR.

### Phase 3 — Per-PR details

For each PR it calls the GitHub API (via `gh api`) and builds one table row. Progress is logged as **`[current/total]`** plus the head branch name when done.

If a PR cannot be analyzed (network error after retries, permissions, etc.), the script **logs `skip PR #…` and continues**. At the end it prints how many rows were written and how many PRs were skipped.

---

## TSV column reference (canonical contract)

**Why this exists:** This section is the **backup specification** for report output. The **`headers` list in `_emit_tsv`** (`github_pr_timeline_report.py`) must match this table (**names** and **left-to-right order**). **Only someone authorized to edit this README** should update this section when the script changes; coding assistants need **explicit permission** (see **`AGENTS.md`**).

**TSV layout**

| Part | Content |
|------|---------|
| **Lines 1–2** | Preamble only: plain text, **no tab characters**. States repo, calendar window, and that datetimes use `REPORT_TZ`. |
| **Line 3** | Header row: **tab-separated** column names, exactly as in the table below. |
| **Following lines** | One data row per analyzed PR (tabs between fields). |
| **Last 2 lines** | Footer “END NOTES” (plain text). You may delete preamble + footer for a clean spreadsheet; **do not** delete the header row. |

**Timezone (Eastern by default):** Every **milestone datetime** in the TSV is ISO-8601 **wall-clock time in `REPORT_TZ`**. Out of the box, `REPORT_TZ = ZoneInfo("America/New_York")`, so you get **US Eastern** with correct **DST** (`-05:00` / `-04:00` in the string). Change `REPORT_TZ` in `github_pr_timeline_report.py` if you want another zone. Header names do **not** say “eastern”; lines 1–2 and the footer of the TSV name the active zone.

### Lifecycle fields you asked for → which columns

This table ties **plain-English asks** to the **exact** column names the script writes. Each milestone has **two** columns when applicable: the **datetime** and **`…_hours_since_branch`** (decimal hours from the **branch-start proxy**; see columns 6–7).

| What you want (plain English) | Datetime column | Hours-since-branch column |
|-------------------------------|-----------------|----------------------------|
| **Branch / work started** — best timestamp GitHub exposes for “when did this line of work begin” (see caveat below) | **`branch_start`** | **`branch_start_hours_since_branch`** (always `0.0000` when present) |
| **Draft PR** — first time the PR was marked draft in the issue timeline | **`first_draft`** | **`first_draft_hours_since_branch`** |
| **Regular PR opened** — when the pull request was created | **`pr_created`** | **`pr_created_hours_since_branch`** |
| **Ready for review** — first `ready_for_review` event, or PR open when the script treats the PR as never-draft | **`ready_for_review`** | **`ready_for_review_hours_since_branch`** |
| **First activity on the PR** — earliest **issue comment** *or* **any review submission** (whichever is earlier; not “comments only”) | **`first_feedback`** | **`first_feedback_hours_since_branch`** |
| **PR approval** — first review whose GitHub state is **`APPROVED`** | **`approved`** | **`approved_hours_since_branch`** |
| **PR merge** — when the PR was merged into the base branch (empty if still open) | **`merged`** | **`merged_hours_since_branch`** |

**Caveat — “branch creation”:** GitHub does not give a single “branch created at” field in this report. **`branch_start`** is a **proxy**: the **earliest author or committer timestamp** among commits returned for the PR. If that cannot be computed, **`branch_start`** is empty, **`notes`** may contain `branch_start_unavailable`, and all **`…_hours_since_branch`** fields for milestones are empty (datetimes for PR open, merge, etc. can still be present).

**Caveat — “first comment”:** Implementation is **`first_feedback`**: the **minimum** of review `submitted_at` times and issue **comment** `created_at` times (first **100** of each per PR). So the first row is not strictly “comment only” if a review landed first.

**After those pairs**, the TSV adds **segment durations** (all measured from **PR opened** `pr_created`, not “since branch”): **`hours_pr_created_to_first_feedback`** (open → first feedback), **`hours_pr_created_to_approved`** (open → first **APPROVED** review), **`hours_pr_created_to_closed`** (open → **`closed_at`** from GitHub: merged, closed without merge, or empty while still open). Then **file** and **commit** counts: **`pr_files_total`**, **`pr_files_added`**, **`pr_files_modified`**, **`pr_files_removed`**, **`pr_commits_total`**, **`pr_commits_before_pr_open`**, **`pr_commits_after_pr_open`**.

### Full column list in output order (quick reference)

1. **`committer`** — Grouping login (search opener).  
2. **`head_branch`** — Head ref name.  
3. **`pr_number`** — PR #.  
4. **`notes`** — Flags (`branch_start_unavailable`, truncation, …).  
5. **`pr_url`** — Link to PR.  
6–7. **`branch_start`**, **`branch_start_hours_since_branch`** — Branch-work proxy + anchor hours.  
8–9. **`pr_created`**, **`pr_created_hours_since_branch`** — PR opened (“regular PR”).  
10–11. **`first_draft`**, **`first_draft_hours_since_branch`** — Draft milestone.  
12–13. **`ready_for_review`**, **`ready_for_review_hours_since_branch`** — Ready milestone.  
14–15. **`first_feedback`**, **`first_feedback_hours_since_branch`** — First comment *or* review.  
16–17. **`approved`**, **`approved_hours_since_branch`** — First **APPROVED** review.  
18–19. **`merged`**, **`merged_hours_since_branch`** — **PR merge** time.  
20. **`hours_pr_created_to_first_feedback`** — PR opened → first feedback (comment or review).  
21. **`hours_pr_created_to_approved`** — PR opened → first **APPROVED** review.  
22. **`hours_pr_created_to_closed`** — PR opened → **`closed_at`** (covers merge or close-without-merge; empty if PR still open).  
23–26. **`pr_files_total`**, **`pr_files_added`**, **`pr_files_modified`**, **`pr_files_removed`**.  
27–29. **`pr_commits_total`**, **`pr_commits_before_pr_open`**, **`pr_commits_after_pr_open`**.

**Canonical columns (exact order, detailed)** — `#` is the column index (1-based) for spreadsheets.

| # | Column | Type | Meaning |
|---|--------|------|---------|
| 1 | `committer` | string | Login used to **group** the row (Phase 1 search opener); usually the PR author. |
| 2 | `head_branch` | string | PR **head ref** name. |
| 3 | `pr_number` | integer (as text) | GitHub pull request number. |
| 4 | `notes` | string | Semicolon-separated flags, e.g. `branch_start_unavailable`, `pr_commits_list_truncated`, `pr_files_list_truncated`. Often empty. Placed **before** `pr_url` so URLs don’t visually swamp notes in Excel. |
| 5 | `pr_url` | string | Browser URL for the PR. |
| 6 | `branch_start` | datetime or empty | **Branch-start proxy:** earliest **author** or **committer** timestamp among commits returned for this PR (not Git’s literal “branch created” event). Empty when the proxy could not be computed; see **`notes`** (`branch_start_unavailable`). |
| 7 | `branch_start_hours_since_branch` | decimal hours or empty | Hours from branch-start anchor to **`branch_start`** event (always **`0.0000`** when present). Empty if branch start could not be computed. |
| 8 | `pr_created` | datetime or empty | When the PR was **opened** (`created_at`). |
| 9 | `pr_created_hours_since_branch` | decimal or empty | Hours from **branch start** to PR open. Negative values are **clamped to `0`** (proxy timing). Empty if branch start unknown. |
| 10 | `first_draft` | datetime or empty | First **`converted_to_draft`** issue event time, if any. |
| 11 | `first_draft_hours_since_branch` | decimal or empty | Hours from branch start to first draft event. Empty if branch start unknown or no draft time. |
| 12 | `ready_for_review` | datetime or empty | First **`ready_for_review`** issue event, or **`pr_created`** when the script treats the PR as never draft from events. |
| 13 | `ready_for_review_hours_since_branch` | decimal or empty | Hours from branch start to that ready time. Empty if branch start unknown or ready time unknown. |
| 14 | `first_feedback` | datetime or empty | **Earliest** of: any **review** `submitted_at`, or any **issue comment** `created_at` (each list capped—see Limits). |
| 15 | `first_feedback_hours_since_branch` | decimal or empty | Hours from branch start to first feedback. Empty if branch start or feedback unknown. |
| 16 | `approved` | datetime or empty | **Earliest** review with **`state: APPROVED`** and `submitted_at`. Empty if none in the fetched reviews (merged PRs may still have no `APPROVED` row). |
| 17 | `approved_hours_since_branch` | decimal or empty | Hours from branch start to first approval. Empty if branch start or approval unknown. |
| 18 | `merged` | datetime or empty | Merge time if the PR is merged; empty if open. |
| 19 | `merged_hours_since_branch` | decimal or empty | Hours from branch start to merge. Empty if branch start unknown or not merged. |
| 20 | `hours_pr_created_to_first_feedback` | decimal or empty | Elapsed hours **PR opened → first feedback** (not “since branch”). Empty if either timestamp missing. |
| 21 | `hours_pr_created_to_approved` | decimal or empty | Elapsed hours **PR opened → first approval** (first **APPROVED** review). Empty if PR open time or approval missing. |
| 22 | `hours_pr_created_to_closed` | decimal or empty | Elapsed hours **PR opened → GitHub `closed_at`** (PR merged or otherwise closed). Empty if still open or close time missing. |
| 23 | `pr_files_total` | integer (as text) | Count of file rows in the PR diff (`pulls/{n}/files`), all statuses. |
| 24 | `pr_files_added` | integer (as text) | Files with GitHub `status: added`. |
| 25 | `pr_files_modified` | integer (as text) | Files with other statuses except `removed` (e.g. `modified`, `renamed`, `copied`, `changed`). |
| 26 | `pr_files_removed` | integer (as text) | Files with `status: removed`. |
| 27 | `pr_commits_total` | integer (as text) | Commits returned for the PR (`pulls/{n}/commits`); same list as branch-start / before-after logic. |
| 28 | `pr_commits_before_pr_open` | integer or empty | Commits whose author/committer timestamp is **strictly before** PR `created_at`. Empty if PR open time missing. |
| 29 | `pr_commits_after_pr_open` | integer or empty | Commits on or after open, plus undated commits in the payload. **Before + after = total** when open time exists. Empty if PR open time missing. |

**Empty cells:** Any field can be empty when the underlying GitHub data is missing, the script’s **100-item caps** hide the event, or branch-start could not be computed. That is expected for some PRs; see **[Limits and caveats](#limits-and-caveats)** and **[Troubleshooting](#troubleshooting)** below.

---

## What is collected and how it is defined

Output is **one row per PR** that was successfully analyzed. Rows are **tab-separated** with a header row. The **authoritative column list and order** is **[TSV column reference (canonical contract)](#tsv-column-reference-canonical-contract)** above; the subsections below expand on definitions and limits.

### Identity and links

- **`committer`** — Grouping key from Phase 1 (search opener); usually the PR author.
- **`head_branch`** — Head ref name from the PR (still available after “delete branch on merge” for merged PRs).
- **`pr_number`** — GitHub PR number.
- **`notes`** — For example `branch_start_unavailable` if the branch-start proxy could not be computed from the PR commits API (empty or unusable timestamps, permissions, etc.—not necessarily “no commits”) (placed before **`pr_url`** so spreadsheet columns don’t visually collide with long URLs).
- **`pr_url`** — Web URL for the PR.

### “Branch start” and milestones

**Datetime columns** (`branch_start`, `pr_created`, `first_draft`, etc.) are **ISO-8601 in `REPORT_TZ`** (see the TSV preamble/footer for the zone name). Internally, durations use UTC from the API; **hours-since-branch** and segment hours are real elapsed hours.

**Branch start (proxy)** — Earliest **author** (or committer) timestamp among commits returned for that PR (paginated; same commit list as for **before/after PR** counts below). This approximates “when work on this PR branch began,” not a literal “branch created at” event from GitHub. If the proxy time is slightly **after** PR creation (ordering / API quirks), **hours since branch** for that milestone is shown as **0** rather than a tiny negative value.

For each milestone there are **two** columns: **datetime** and **hours since branch start** (`…_hours_since_branch`).

| Milestone | Meaning |
|-----------|---------|
| **branch_start** | The branch-start proxy (hours column is `0`). |
| **pr_created** | When the PR was opened. |
| **first_draft** | First `converted_to_draft` issue event, if any. |
| **ready_for_review** | First `ready_for_review` event, or PR created time when treated as never draft from events. |
| **first_feedback** | Earliest **submitted** review or **issue comment** (up to 100 items each — see limits). |
| **approved** | Earliest **APPROVED** review with `submitted_at`. |
| **merged** | Merge time if merged. |

### Segment hours (from PR opened)

Durations in **hours**, each anchored at **`pr_created`** (not “since branch”):

- **`hours_pr_created_to_first_feedback`** — Open → first feedback.
- **`hours_pr_created_to_approved`** — Open → first **APPROVED** review.
- **`hours_pr_created_to_closed`** — Open → **`closed_at`** (merge or close; empty while open).

Empty cells mean a timestamp was missing.

### PR size metrics (from GitHub’s PR commits / files APIs)

These columns appear **after** the segment hour columns. **`pr_files_total`** is the overall **files changed** count; **`pr_files_*`** break that total down by GitHub file `status`.

| Column | Meaning |
|--------|---------|
| **`pr_files_total`** | Total paths in the PR diff (rows from `GET …/pulls/{n}/files`). |
| **`pr_files_added`** | `status: added`. |
| **`pr_files_modified`** | `modified`, `renamed`, `copied`, `changed`, etc. (not add/remove). |
| **`pr_files_removed`** | `status: removed`. |
| **`pr_commits_total`** | Commits returned for the PR (same list used for branch-start and before/after). |
| **`pr_commits_before_pr_open`** | Commits whose **author** date (fallback **committer** date) is **strictly before** PR **`created_at`**. Empty if open time is missing. |
| **`pr_commits_after_pr_open`** | Commits with that timestamp **on or after** `created_at`, plus any commit with no parseable date (**before + after** = **`pr_commits_total`** when open time exists). Empty if open time is missing. |

Paginated list caps apply (see below); **`notes`** may flag truncation.

---

## Limits and caveats

- **Only PRs** — No GitHub PR means no row.
- **Search cap** — Phase 1 paginates search (up to 2000 hits per query slice); huge months may need a different approach.
- **Reviews / comments / events** — First **100** items per list per PR.
- **Commits / PR files** — Paginated up to **100 pages × 100 items** per PR (10k each). If either list hits that cap, **`notes`** may include `pr_commits_list_truncated` or `pr_files_list_truncated`; counts are then incomplete.
- **Draft timing** — Inferred from issue events; not always perfect via REST alone.
- **Retries** — Transient network errors are retried a few times per `gh api` call.
- **Default output** — Reports go under **`analysis-results/`** (see `DEFAULT_OUTPUT_DIR` in the script). Override with **`-o`**.

---

## Files

| File | Purpose |
|------|---------|
| `github_pr_timeline_report.py` | CLI entrypoint (`REPORT_TZ` at top); `_emit_tsv` defines output columns—must match this README’s canonical table. |
| `.gitignore` | Ignores **`analysis-results/`** (default report output). |
| `README.md` | User-facing usage and **canonical TSV column contract** (this document). **Protected—see notice at top.** |
| `AGENTS.md` | **Instructions for AI assistants** (README protection, workflow). |
| `analysis-results/` | **Default output directory** for `.tsv` files (not tracked by git). |

---

## Troubleshooting

- **`gh api` / search failures** — Run `gh auth status` and `gh api user`. For org repos, confirm SSO for the token.
- **404 on `/search/issues`** — The script uses path-style `gh api` calls; use an updated copy if you see full-URL 404s.
- **Empty or tiny TSV** — Check dates, year, and `REPORT_TZ`. Confirm merged or created PRs exist in that window.
- **Many `skip PR` lines** — Network or rate limits; re-run or inspect stderr.
