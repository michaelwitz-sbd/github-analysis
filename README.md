# GitHub Team Metrics

Pull **per-person engineering metrics** from any GitHub repository you can access: merged PRs, reviews, file-change averages, and optional PR-level detail. Output is Excel and TSV for managers and team leads.

Uses the [GitHub CLI](https://cli.github.com/) (`gh`) for API access — authenticate `gh` with a token that can read the target repository.

---

## Quick start

```bash
git clone https://github.com/michaelwitz-sbd/github-analysis.git
cd github-analysis
uv sync --group excel
gh auth login

uv run github-analysis run \
  --repo global-services \
  --start-date 2026-05-01 \
  --end-date 2026-06-01 \
  --merged-only \
  --workers 4 \
  -o ~/Documents/global-services-may-2026.xlsx
```

| Flag | Meaning |
|------|---------|
| `--start-date` | First calendar day **included** (US Eastern) |
| `--end-date` | First calendar day **excluded** → all of May 2026 above |
| `--merged-only` | PR detail sheet: merged PRs only; person summary still includes authored, open, and review counts |
| `--workers` | Parallel fetch threads (default `4`) |
| `-o` | Excel path; sibling TSV, cache, and log share the same base name |

**Outputs** (example base name `global-services-may-2026`):

| File | Purpose |
|------|---------|
| `.xlsx` | Excel — **Individual Production** + **PR Detail** sheets |
| `_person_summary.tsv` | One row per person |
| `.tsv` | One row per pull request |
| `_raw.json` | Cache for `--from-cache` rebuilds |
| `_run.log` | Auth checks, progress, errors — **read this first if a run fails** |

---

## Install

**Requirements:** [uv](https://docs.astral.sh/uv/), [GitHub CLI 2.30+](https://cli.github.com/), network access to `github.com`.

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh   # macOS/Linux
cd github-analysis
uv sync --group excel
uv run github-analysis --version                  # expect 2.0.0
```

Python 3.9+ is installed by `uv` automatically.

---

## GitHub authentication

Reports call GitHub through `gh api`. Without a valid login, runs fail or return empty data.

**Interactive login (typical):**

```bash
gh auth login          # GitHub.com, HTTPS, browser or token; need repo scope for private repos
gh auth status
gh repo view Customer-Engagement-Digital-Technology/global-services
```

**Personal access token:** create at [github.com/settings/tokens](https://github.com/settings/tokens) with **`repo`** scope (classic) or read access to Contents + Pull requests (fine-grained). Then:

```bash
gh auth login --with-token <<< "ghp_YOUR_TOKEN"
```

**Organization SSO:** authorize the token for your org (e.g. `Customer-Engagement-Digital-Technology`) under GitHub → Settings → Applications.

**CI / scripts:** set `GH_TOKEN` or `GITHUB_TOKEN` before running `gh`.

---

## Commands

| Command | Description |
|---------|-------------|
| **`run`** | Fetch from GitHub and write Excel + TSV + cache (recommended) |
| **`analyze`** | Fetch and write TSV + cache only |
| **`export`** | Build Excel from existing TSV files |

All commands: `uv run github-analysis <command> --help`

### CLI options

| Option | Commands | Description |
|--------|----------|-------------|
| `--repo` | analyze, run | HTTPS URL, `owner/name`, or short name (uses default org in `config.py`) |
| `--owner` | analyze, run | Org when `--repo` is a short name only |
| `--start-date` | analyze, run | Start inclusive (`YYYY-MM-DD`) |
| `--end-date` | analyze, run | End exclusive (`YYYY-MM-DD`) |
| `--merged-only` | analyze, run | Detail sheet: merged PRs only (see [Monthly metrics](#monthly-metrics)) |
| `--workers` | analyze, run | Parallel fetch threads (default `4`; use `3` or `1` under rate pressure) |
| `-o`, `--output` | run | Excel path (`.xlsx`); writes sibling TSV files |
| `-o`, `--output` | analyze | Detail TSV path (`-` = stdout) |
| `-o`, `--output` | export | Excel path (required) |
| `--output-dir` | analyze, run | Output folder when `-o` omitted (default `~/Documents`) |
| `--from-cache` | analyze | Rebuild TSV from `{name}_raw.json` without GitHub fetch |
| `--summary-output` | analyze | Custom path for person summary TSV |
| `--no-summary` | analyze | Skip person summary TSV |
| `--summary` | export | Input person summary TSV (required) |
| `--detail` | export | Input PR detail TSV (optional second sheet) |
| `--summary-only` | export, run | Excel with Individual Production sheet only |

### Repository formats

| Format | Example |
|--------|---------|
| HTTPS URL | `https://github.com/Customer-Engagement-Digital-Technology/global-services.git` |
| Owner/name | `Customer-Engagement-Digital-Technology/global-services` |
| Short name | `global-services` |

### Date windows

Half-open calendar window in US Eastern (`America/New_York`):

| Period | `--start-date` | `--end-date` |
|--------|----------------|--------------|
| All of May 2026 | `2026-05-01` | `2026-06-01` |
| One week | `2026-05-01` | `2026-05-08` |
| Q1 2026 | `2026-01-01` | `2026-04-01` |

### Common workflows

**Auto-named files** (no `-o`):

```bash
uv run github-analysis run \
  --repo global-services \
  --start-date 2026-05-01 --end-date 2026-06-01 \
  --merged-only --workers 4 \
  --output-dir ~/Documents
# → global-services_2026-05-01_to_2026-06-01.xlsx (+ siblings)
```

**Analyze then export separately:**

```bash
uv run github-analysis analyze \
  --repo global-services \
  --start-date 2026-05-01 --end-date 2026-06-01 \
  --merged-only --workers 4 \
  -o ~/Documents/global-services-may-2026.tsv

uv run github-analysis export \
  --summary ~/Documents/global-services-may-2026_person_summary.tsv \
  --detail ~/Documents/global-services-may-2026.tsv \
  -o ~/Documents/global-services-may-2026.xlsx
```

**Rebuild from cache** (no GitHub fetch; person summary recomputed from cached timestamps):

```bash
uv run github-analysis analyze \
  --from-cache ~/Documents/global-services-may-2026_raw.json \
  --repo global-services \
  --start-date 2026-05-01 --end-date 2026-06-01 \
  --merged-only \
  -o ~/Documents/global-services-may-2026.tsv
```

**Shell wrapper:**

```bash
./run_monthly_report.sh global-services 2026-05-01 2026-06-01 --merged-only
```

**Monitor a run:**

```bash
tail -f ~/Documents/global-services-may-2026_run.log
```

---

## How a run works

| Phase | What happens |
|-------|----------------|
| Preflight | Verify `gh` auth and repo access |
| Phase 1 | Search for PRs in the date window |
| Phase 2 | Fetch each PR (metadata, commits, files, reviews) — **dominates runtime** |
| Phase 3 | Roll up per-person metrics |
| Phase 3b | Resolve PRs still open at window end |
| Write | TSV, cache, Excel |

Progress appears in `_run.log` as `[42/492] PR #317 (author)`. Files are written only after Phase 2 finishes. A busy month (~500 merged PRs) typically takes **6–10 minutes** with 4 workers.

---

## GitHub API limits

| Limit | Value | Affects |
|-------|-------|---------|
| REST quota | 5,000 requests/hour | ~6 calls per merged PR in Phase 2–3 |
| Search results | 1,000 matches per query | Phase 1 discovery |

**Check quota before a large run:**

```bash
gh api rate_limit --jq '.resources.core | "remaining=\(.remaining) reset=\(.reset)"'
```

Prefer **`remaining > 1,000`** before a full-month report on a busy repo. Quota resets hourly (`date -r RESET` on macOS).

**If a run fails**, open `_run.log`:

| Log message | Action |
|-------------|--------|
| `API rate limit exceeded` | Wait for reset; re-run one repo with `--workers 3` |
| Many `Skip PR #…` with rate-limit errors | Incomplete — re-run after reset |
| `Only the first 1000 search results are available` | Split the calendar window (e.g. two half-months); distinct `-o` paths |
| Missing `Fetch complete` or `skipped` > 0 | Do not use for production — re-run |

**Practices:** one full-month fetch per repo per hour; use `--from-cache` to rebuild Excel without re-fetching; shorter date windows for trial runs.

---

## Output columns

### Individual Production (`_person_summary.tsv`)

| Column | Description |
|--------|-------------|
| `user` | GitHub login |
| `prs_authored` | PRs **opened** in the calendar window (merged or not) |
| `prs_merged` | Their PRs **merged** in the window (any open date, including carry-over) |
| `prs_open` | Their PRs **still unmerged at window end** (any open date) |
| `prs_reviewed` | Distinct PRs with any review submitted in the window |
| `prs_approved` | Distinct PRs with an APPROVED review in the window |
| `avg_files_added_per_pr` | Mean new files per PR in the detail report |
| `avg_files_changed_per_pr` | Mean modified/renamed files per detail-row PR |
| `min/max/avg_hours_pr_created_to_merged` | Hours from PR open to merge (merged-in-window only; excludes `prs_open`) |

**The three PR counts are independent.** Example for May 2026 (`2026-05-01` .. `2026-06-01`):

| Scenario | `prs_authored` | `prs_merged` | `prs_open` |
|----------|----------------|--------------|------------|
| Opened May 31, merged in June | 1 | 0 | 1 |
| Opened May 15, merged May 20 | 1 | 1 | 0 |
| Opened in April, merged in May | 0 | 1 | 0 |
| Opened in April, still open May 31 | 0 | 0 | 1 |
| Opened 8 in May; merged 5; 2 still open; 1 closed unmerged | 8 | 5 | 2 |

Merge-cycle hours and file averages come from **detail report rows** only (merged PRs when `--merged-only`). Review counts use review `submitted_at`, not merge date.

### PR Detail (`.tsv`, header on row 3)

| Column | Description |
|--------|-------------|
| `pr_creator` | Who opened the PR |
| `pr_number`, `pr_url`, `head_branch` | PR identity |
| `branch_start` | First commit on the branch |
| `pr_created` | When the PR was opened |
| `first_draft`, `ready_for_review` | Draft / ready-for-review timestamps |
| `first_feedback`, `approved`, `approved_by` | Review timeline |
| `merged` | Merge timestamp (blank if not merged) |
| `*_hours_since_branch` | Elapsed hours from branch start |
| `hours_pr_created_to_*` | Elapsed hours from PR open |
| `pr_files_total/addded/modified/removed` | File counts |
| `pr_commits_total/before_pr_open/after_pr_open` | Commit counts |
| `notes` | Warnings (truncation, catalog mismatch, etc.) |

Timestamps use the report timezone as ISO-8601 with offset.

**Opening files:** open `.xlsx` directly. For TSV in Excel, import with Tab delimiter; rows 1–2 of the detail file are notes.

---

## Monthly metrics

With **`--merged-only`** (recommended for monthly manager reports):

- **PR detail sheet** — only PRs merged in the calendar window
- **Person summary** — still computes `prs_authored`, `prs_open`, and review counts via separate searches

A PR counts toward **`prs_open`** at window end if it existed, had not merged, and was not closed without merge before window end — regardless of when it was opened.

---

## Attribution rules

| Metric | Counted as | Not used |
|--------|------------|----------|
| PR author | GitHub `user` on the pull request | Assignees, merge committer |
| Reviewer | Formal review with `submitted_at` in window | Comments without a review |
| Approver | Review with `state: APPROVED` | LGTM comments alone |
| File averages | Mean over detail-report PRs | — |
| Merge cycle time | PRs merged in the window | Still-open PRs, late merges |

---

## Configuration

Edit `github_analysis/config.py`:

| Setting | Default | Purpose |
|---------|---------|---------|
| `REPORT_TZ` | `America/New_York` | Calendar dates and timestamps |
| `DEFAULT_GITHUB_OWNER` | `Customer-Engagement-Digital-Technology` | Org for short `--repo` names |
| `DEFAULT_OUTPUT_DIR` | `~/Documents` | Default output folder |
| `DEFAULT_FETCH_WORKERS` | `4` | Default `--workers` |

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `uv` / `gh` not found | Install and ensure on PATH |
| `gh auth status` fails | `gh auth login` or set `GH_TOKEN` |
| `401` / `403` / `404` on org repo | PAT with `repo` scope; authorize SSO for the org |
| `openpyxl is required` | `uv sync --group excel` |
| Empty report | Widen dates; confirm activity in the window |
| Very slow / stuck at `[N/M]` | Normal for large months; wait or check `_run.log` |
| Rate limit / search cap | See [GitHub API limits](#github-api-limits) |

```bash
uv run github-analysis --version
gh auth status
gh repo view OWNER/REPO
```

---

## Limits

- One repository per run
- GitHub search: max **1,000 results per query** — split long date ranges if needed
- Reviews/comments: first 100 items per PR for timing
- Files/commits: up to 10,000 per PR (truncation noted in `notes`)
