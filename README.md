# GitHub Team Metrics

Pull **per-person engineering metrics** from any GitHub repository you can access: merged PRs, reviews submitted, average files changed, and optional PR-level detail. Output is TSV and Excel, ready for managers and team leads.

This tool uses the [GitHub CLI](https://cli.github.com/) (`gh`) for all API access — no separate API keys in the Python code, but you **must** authenticate `gh` with a token that has repository read access.

---

## Table of contents

1. [What you get](#what-you-get)
2. [Prerequisites](#prerequisites)
3. [Install uv and this project](#install-uv-and-this-project)
4. [GitHub authentication (required)](#github-authentication-required)
5. [Project structure](#project-structure)
6. [CLI commands](#cli-commands)
7. [Running reports](#running-reports)
   - [Sample commands (copy-paste)](#sample-commands-copy-paste)
8. [How the report runs (phases)](#how-the-report-runs-phases)
9. [Performance and optimization](#performance-and-optimization)
10. [Understanding the output](#understanding-the-output)
11. [Attribution rules](#attribution-rules)
12. [Configuration](#configuration)
13. [Troubleshooting](#troubleshooting)
14. [Extending the CLI](#extending-the-cli)

---

## What you get

Each report run writes files to **`~/Documents`** by default.

### Output file formats

| Format | Extension | When | Best for |
|--------|-----------|------|----------|
| **Excel workbook** | `.xlsx` | `run` or `export` | **Managers** — open directly in Excel; not legacy `.xls` |
| **Tab-separated text** | `.tsv` | `analyze` or `run` | Spreadsheets, scripting, or re-exporting to Excel |

The **`run`** command (recommended) produces these files in the **same output directory**:

| File | Purpose |
|------|---------|
| `{name}.xlsx` | Excel workbook — **Individual Production** + **PR Detail** sheets |
| `{name}_person_summary.tsv` | One row per person (individual production metrics) |
| `{name}.tsv` | One row per pull request (detail) |
| `{name}_raw.json` | Raw fetched data (cache — reuse without re-calling GitHub) |
| `{name}_run.log` | **Run log** — auth checks, errors, skipped PRs, person list |

Specify the Excel path with **`-o`**; sibling files share the same base name:

```bash
cd ~/Dev/github-analysis

uv run github-analysis run \
  --repo https://github.com/Customer-Engagement-Digital-Technology/global-services.git \
  --start-date 2026-05-01 \
  --end-date 2026-06-01 \
  --merged-only \
  --workers 4 \
  -o ~/Documents/global-services-may-2026.xlsx
```

| Parameter | Value | Meaning |
|-----------|-------|---------|
| `--repo` | HTTPS URL (or `global-services` short name) | Repository to analyze |
| `--start-date` | `2026-05-01` | First calendar day **included** (US Eastern) |
| `--end-date` | `2026-06-01` | First calendar day **excluded** → all of May 2026 |
| `--merged-only` | (flag) | Only PRs **merged** in that window |
| `--workers` | `4` | Parallel fetch threads (default; omit to use 4) |
| `-o` | path to `.xlsx` | Excel output; siblings share the same base name |

Creates:

```
~/Documents/global-services-may-2026.xlsx
~/Documents/global-services-may-2026_person_summary.tsv
~/Documents/global-services-may-2026.tsv
~/Documents/global-services-may-2026_raw.json
~/Documents/global-services-may-2026_run.log
```

**If something fails, open `{name}_run.log` first.** It records GitHub authentication status, repository access checks, skipped PRs, and every person included in the summary.

Rebuild TSV/Excel from cache without re-fetching (person summaries are **recomputed** from cached PR rows, so new summary columns appear without calling GitHub again):

```bash
cd ~/Dev/github-analysis

uv run github-analysis analyze \
  --from-cache ~/Documents/global-services-may-2026_raw.json \
  --repo global-services \
  --start-date 2026-05-01 \
  --end-date 2026-06-01 \
  --merged-only \
  -o ~/Documents/global-services-may-2026.tsv

uv run github-analysis export \
  --summary ~/Documents/global-services-may-2026_person_summary.tsv \
  --detail ~/Documents/global-services-may-2026.tsv \
  -o ~/Documents/global-services-may-2026.xlsx
```

---

## Prerequisites

| Requirement | Version | Purpose |
|-------------|---------|---------|
| **uv** | latest | Python runtime, virtualenv, and dependencies |
| **GitHub CLI (`gh`)** | 2.30+ | Authenticated access to GitHub REST API |
| **Git** | any | Clone this repository |
| **Network** | — | Reach `github.com` (and SSO authorization if your org uses it) |

Python 3.9+ is installed automatically by `uv` — you do not need to install Python separately.

---

## Install uv and this project

### Step 1 — Install uv

**macOS / Linux:**

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Restart your terminal, then verify:

```bash
uv --version
```

**Windows (PowerShell):**

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Other install options: [uv documentation](https://docs.astral.sh/uv/getting-started/installation/).

### Step 2 — Clone the repository

```bash
git clone https://github.com/michaelwitz-sbd/github-analysis.git
cd github-analysis
```

Or use your local copy if you already have it:

```bash
cd ~/Dev/github-analysis
```

### Step 3 — Install project dependencies

This creates a `.venv` virtual environment and installs the CLI plus Excel support:

```bash
uv sync --group excel
```

You only need to run `uv sync` again when dependencies change (e.g. after `git pull`).

### Step 4 — Verify the CLI

```bash
uv run github-analysis --help
uv run github-analysis --version
```

You should see the command list and version `2.0.0`.

---

## GitHub authentication (required)

This tool calls GitHub through **`gh api`**. If `gh` is not logged in, or your token cannot read the target repository, reports will fail or return empty results.

### Option A — Interactive login (recommended for first-time setup)

```bash
gh auth login
```

Follow the prompts:

| Prompt | Recommended choice |
|--------|-------------------|
| Host | `GitHub.com` |
| Protocol | `HTTPS` |
| Authenticate | `Login with a web browser` (or paste a token — see Option B) |
| Token scopes | Accept defaults; **`repo`** scope is required for private repositories |

Verify:

```bash
gh auth status
gh api user
```

Both should succeed without errors.

### Option B — Personal Access Token (PAT)

Use a PAT when browser login is blocked, for automation, or when your IT team issues tokens centrally.

#### Create a PAT on GitHub

1. Open **GitHub → Settings → Developer settings → Personal access tokens**
   - Classic tokens: [github.com/settings/tokens](https://github.com/settings/tokens)
   - Fine-grained tokens: [github.com/settings/personal-access-tokens](https://github.com/settings/personal-access-tokens)
2. **Generate new token**
3. Grant access:
   - **Classic PAT:** enable scope **`repo`** (full control of private repositories)
   - **Fine-grained PAT:** select the organization/user, choose **Repository access** (specific repos or all), and set permissions:
     - **Contents:** Read
     - **Pull requests:** Read
     - **Metadata:** Read (usually automatic)
4. Copy the token — you will not see it again.

#### Log in with the PAT

```bash
gh auth login --with-token <<< "ghp_YOUR_TOKEN_HERE"
```

Or paste interactively:

```bash
gh auth login
# Choose: GitHub.com → HTTPS → Paste an authentication token
```

#### Organization SSO (common in enterprise)

If your company uses SAML SSO, authorize the token for the org:

1. GitHub → **Settings → Applications → Authorized OAuth Apps** (or visit the SSO banner after login)
2. Find **GitHub CLI** or your token
3. Click **Authorize** next to the organization (e.g. `Customer-Engagement-Digital-Technology`)

Verify access to a private org repo:

```bash
gh api repos/Customer-Engagement-Digital-Technology/global-services --jq .full_name
```

### Option C — Environment variable (CI / scripts)

For non-interactive environments:

```bash
export GH_TOKEN="ghp_YOUR_TOKEN_HERE"
gh auth status
```

`gh` uses `GH_TOKEN` or `GITHUB_TOKEN` when set.

### Confirm you can read the target repository

Replace with your repository:

```bash
gh repo view Customer-Engagement-Digital-Technology/global-services
```

If this fails, fix authentication before running reports.

---

## Project structure

```
github-analysis/
├── pyproject.toml              # Project metadata and uv dependency groups
├── uv.lock                     # Locked dependency versions (commit with repo)
├── README.md                   # This guide
├── run_monthly_report.sh       # Shell wrapper: uv sync + `github-analysis run`
├── github_pr_timeline_report.py  # Legacy wrapper → `analyze` subcommand
├── export_report_xlsx.py       # Legacy wrapper → `export` subcommand
├── analysis-results/           # Generated reports (gitignored, created at runtime)
│
└── github_analysis/            # Python package
    ├── __init__.py             # Package version
    ├── __main__.py             # `python -m github_analysis` entry
    ├── config.py               # Timezone, default org, output directory, API limits
    ├── models.py               # ReportConfig, PullRequestRow, UserSummary dataclasses
    ├── repo.py                 # Parse --repo (URL, owner/name, short name)
    ├── time_utils.py           # Date windows and timestamp formatting
    │
    ├── cli/                    # Command-line interface
    │   ├── main.py             # Root parser, --help, --version, dispatch
    │   └── commands/
    │       ├── analyze.py      # Fetch GitHub data → TSV
    │       ├── export.py       # TSV → Excel (.xlsx)
    │       └── run.py          # analyze + export in one step
    │
    ├── github/                 # GitHub API layer (via `gh api`)
    │   ├── client.py           # HTTP client with retries
    │   ├── preflight.py        # Auth and repo access checks before fetch
    │   └── pulls.py            # Pull request, commit, file, review endpoints
    │
    ├── catalog/                # PR discovery
    │   └── search.py           # GitHub issue search (merged, created, updated)
    │
    ├── analysis/               # Metrics computation
    │   ├── pr_builder.py       # Build one row per PR (creator, files, timeline)
    │   ├── reviews.py          # Count reviews and approvals by person
    │   └── summaries.py        # Roll up per-person individual production
    │
    ├── cache/                  # Raw JSON cache for offline rebuild
    │   └── raw_store.py
    │
    ├── logging/                # Run log writer
    │   └── run_log.py
    │
    ├── export/                 # Output writers
    │   ├── paths.py            # Default filenames and paths
    │   ├── tsv.py              # Write detail and summary TSV
    │   └── xlsx.py             # Write Excel workbook (requires openpyxl)
    │
    └── pipeline/
        └── runner.py           # Orchestrates catalog → fetch → summary
```

**Data flow:**

```
CLI command
  → pipeline/runner.py     (discover PRs, fetch details)
  → analysis/              (compute per-PR and per-person metrics)
  → export/                (write TSV and/or Excel)
  → analysis-results/
```

---

## CLI commands

All commands support `--help`:

```bash
uv run github-analysis --help
uv run github-analysis analyze --help
uv run github-analysis export --help
uv run github-analysis run --help
```

| Command | Description |
|---------|-------------|
| **`analyze`** | Query GitHub and write TSV files (team summary + PR detail) |
| **`export`** | Convert existing TSV files to a single Excel workbook |
| **`run`** | Run `analyze` then `export` with default paths (easiest for monthly use) |

---

## Running reports

### Sample commands (copy-paste)

Run from the project directory after `uv sync --group excel` and `gh auth login`.

#### Monthly merged-PR report (recommended)

All PRs **merged in May 2026** on `global-services`, with explicit output path and parallel fetch:

```bash
cd ~/Dev/github-analysis

uv run github-analysis run \
  --repo https://github.com/Customer-Engagement-Digital-Technology/global-services.git \
  --start-date 2026-05-01 \
  --end-date 2026-06-01 \
  --merged-only \
  --workers 4 \
  -o ~/Documents/global-services-may-2026.xlsx
```

Same report using the **short repo name** (default org from `config.py`):

```bash
uv run github-analysis run \
  --repo global-services \
  --owner Customer-Engagement-Digital-Technology \
  --start-date 2026-05-01 \
  --end-date 2026-06-01 \
  --merged-only \
  --workers 4 \
  -o ~/Documents/global-services-may-2026.xlsx
```

Auto-named files in `~/Documents` (omit `-o`):

```bash
uv run github-analysis run \
  --repo global-services \
  --start-date 2026-05-01 \
  --end-date 2026-06-01 \
  --merged-only \
  --workers 4 \
  --output-dir ~/Documents
```

Creates `global-services_2026-05-01_to_2026-06-01.xlsx` plus sibling TSV, `_raw.json`, and `_run.log`.

#### Analyze only (TSV + cache, no Excel)

```bash
uv run github-analysis analyze \
  --repo global-services \
  --start-date 2026-05-01 \
  --end-date 2026-06-01 \
  --merged-only \
  --workers 4 \
  -o ~/Documents/global-services-may-2026.tsv
```

#### Export only (TSV → Excel)

After `analyze` or when TSV files already exist:

```bash
uv run github-analysis export \
  --summary ~/Documents/global-services-may-2026_person_summary.tsv \
  --detail ~/Documents/global-services-may-2026.tsv \
  -o ~/Documents/global-services-may-2026.xlsx
```

Manager view — **Individual Production sheet only** (no PR detail):

```bash
uv run github-analysis export \
  --summary ~/Documents/global-services-may-2026_person_summary.tsv \
  --summary-only \
  -o ~/Documents/global-services-may-2026-managers.xlsx
```

#### Rebuild from cache (no GitHub fetch)

```bash
uv run github-analysis analyze \
  --from-cache ~/Documents/global-services-may-2026_raw.json \
  --repo global-services \
  --start-date 2026-05-01 \
  --end-date 2026-06-01 \
  --merged-only \
  -o ~/Documents/global-services-may-2026.tsv
```

#### Serial fetch (debugging or rate-limit issues)

```bash
uv run github-analysis run \
  --repo global-services \
  --start-date 2026-05-01 \
  --end-date 2026-06-01 \
  --merged-only \
  --workers 1 \
  -o ~/Documents/global-services-may-2026.xlsx
```

#### Monitor a long run

```bash
tail -f ~/Documents/global-services-may-2026_run.log
```

---

### Date ranges

Reports use a **half-open calendar window** in US Eastern time by default:

| Flag | Meaning |
|------|---------|
| `--start-date` | First day **included** (`YYYY-MM-DD`) |
| `--end-date` | First day **excluded** |

**Examples:**

| Period | `--start-date` | `--end-date` |
|--------|----------------|--------------|
| All of May 2026 | `2026-05-01` | `2026-06-01` |
| All of Q1 2026 | `2026-01-01` | `2026-04-01` |
| One week (Mon–Sun) | `2026-05-05` | `2026-05-12` |

### Repository argument (`--repo`)

One repository per run. Accepted formats:

| Format | Example |
|--------|---------|
| HTTPS clone URL | `https://github.com/Customer-Engagement-Digital-Technology/global-services.git` |
| Owner/name | `Customer-Engagement-Digital-Technology/global-services` |
| Short name | `global-services` (uses default org from `config.py`) |

---

### Recommended: one-command monthly report

**All PRs merged in May 2026** on `global-services` (see [Sample commands](#sample-commands-copy-paste) for full parameter list):

```bash
cd ~/Dev/github-analysis

uv run github-analysis run \
  --repo global-services \
  --start-date 2026-05-01 \
  --end-date 2026-06-01 \
  --merged-only \
  --workers 4 \
  -o ~/Documents/global-services-may-2026.xlsx
```

**Outputs** when using `-o ~/Documents/global-services-may-2026.xlsx`:

```
~/Documents/global-services-may-2026.xlsx
~/Documents/global-services-may-2026_person_summary.tsv
~/Documents/global-services-may-2026.tsv
~/Documents/global-services-may-2026_raw.json
~/Documents/global-services-may-2026_run.log
```

**Auto-named outputs** (omit `-o`, use `--output-dir` only):

```bash
uv run github-analysis run \
  --repo global-services \
  --start-date 2026-05-01 \
  --end-date 2026-06-01 \
  --merged-only \
  --workers 4 \
  --output-dir ~/Documents
```

Creates:

```
~/Documents/global-services_2026-05-01_to_2026-06-01.xlsx
~/Documents/global-services_2026-05-01_to_2026-06-01_person_summary.tsv
~/Documents/global-services_2026-05-01_to_2026-06-01.tsv
~/Documents/global-services_2026-05-01_to_2026-06-01_raw.json
~/Documents/global-services_2026-05-01_to_2026-06-01_run.log
```

**Custom output directory** (auto-named files inside that folder):

```bash
uv run github-analysis run \
  --repo global-services \
  --start-date 2026-05-01 \
  --end-date 2026-06-01 \
  --merged-only \
  --workers 4 \
  --output-dir ~/Documents/github-reports
```

**Shell wrapper:**

```bash
chmod +x run_monthly_report.sh
./run_monthly_report.sh global-services 2026-05-01 2026-06-01 --merged-only
```

---

### Step 1 — Analyze only (TSV)

Includes PRs **merged or opened** in the window (omit `--merged-only`):

```bash
uv run github-analysis analyze \
  --repo https://github.com/Customer-Engagement-Digital-Technology/global-services.git \
  --start-date 2026-05-01 \
  --end-date 2026-06-01 \
  --workers 4 \
  -o ~/Documents/global-services-may-2026-all-activity.tsv
```

**Merged PRs only** (typical monthly report):

```bash
uv run github-analysis analyze \
  --repo global-services \
  --start-date 2026-05-01 \
  --end-date 2026-06-01 \
  --merged-only \
  --workers 4 \
  -o ~/Documents/global-services-may-2026.tsv
```

**Custom detail and summary paths:**

```bash
uv run github-analysis analyze \
  --repo global-services \
  --start-date 2026-05-01 \
  --end-date 2026-06-01 \
  --merged-only \
  --workers 4 \
  -o ~/Documents/reports/may-detail.tsv \
  --summary-output ~/Documents/reports/may-person-summary.tsv
```

**Print detail TSV to terminal** (no summary file):

```bash
uv run github-analysis analyze \
  --repo global-services \
  --start-date 2026-05-01 \
  --end-date 2026-06-01 \
  --merged-only \
  --workers 4 \
  --no-summary \
  -o -
```

---

### Step 2 — Export to Excel

After `analyze`, or when TSV files already exist:

```bash
uv run github-analysis export \
  --summary ~/Documents/global-services-may-2026_person_summary.tsv \
  --detail ~/Documents/global-services-may-2026.tsv \
  -o ~/Documents/global-services-may-2026.xlsx
```

**Individual Production sheet only** (manager view):

```bash
uv run github-analysis export \
  --summary ~/Documents/global-services-may-2026_person_summary.tsv \
  --summary-only \
  -o ~/Documents/global-services-may-2026-managers.xlsx
```

---

### CLI option reference

| Option | Commands | Description |
|--------|----------|-------------|
| `--repo` | analyze, run | Repository URL, `owner/name`, or short name |
| `--owner` | analyze, run | Org/user when `--repo` is short name only |
| `--start-date` | analyze, run | Start date inclusive (`YYYY-MM-DD`) |
| `--end-date` | analyze, run | End date exclusive (`YYYY-MM-DD`) |
| `--merged-only` | analyze, run | Only PRs **merged** in the window |
| `--no-summary` | analyze | Skip team summary TSV |
| `-o`, `--output` | run | **Excel** path (`.xlsx`); also writes `{name}.tsv` and `{name}_person_summary.tsv` |
| `-o`, `--output` | analyze | **Detail TSV** path (`-` = stdout) |
| `-o`, `--output` | export | **Excel** path (`.xlsx`) — required |
| `--summary-output` | analyze | Custom path for team summary TSV |
| `--summary` | export | Input team summary TSV (required) |
| `--detail` | export | Input PR detail TSV (optional second Excel sheet) |
| `--summary-only` | export, run | Excel workbook with Individual Production sheet only |
| `--output-dir` | analyze, run | Folder for auto-named files when `-o` is not used (default: `~/Documents`) |
| `--from-cache` | analyze | Rebuild TSV from an existing `{name}_raw.json` without calling GitHub |
| `--workers` | analyze, run | Parallel Phase 2 fetch threads (default: **4**; use `1` for serial) |

---

## How the report runs (phases)

Each `analyze` or `run` command goes through three phases. Progress is written to **`{name}_run.log`** and stderr.

| Phase | What happens | Typical duration |
|-------|----------------|------------------|
| **Preflight** | `gh auth status`, verify read access to the repo | Seconds |
| **Phase 1 — Discover** | GitHub search finds PR numbers in the date window; builds author catalog | ~30 s for busy months |
| **Phase 2 — Fetch details** | For each PR: pull detail, commits, files, events, reviews, comments | **Dominates runtime** (~3 s/PR serial, ~6–10 min with 4 workers for ~500 PRs) |
| **Phase 3 — Summarize** | Count reviewers/approvers in window; roll up per-person metrics | Seconds to ~1 min |
| **Write outputs** | TSV files, optional raw JSON cache, then Excel on `run` | Seconds |

**Monitor progress:**

```bash
tail -f ~/Documents/global-services-may-2026_run.log
```

You should see lines like `[42/492] PR #317 (AlexsOrtiz)` advancing. Final `.xlsx` / `.tsv` files appear only after Phase 2 completes.

**Example scale:** `global-services` May 2026 (`--merged-only`) discovered **492 PRs**. At ~3 seconds per PR in serial mode, Phase 2 alone is roughly **25 minutes**.

---

## Performance and optimization

### Why fetch time adds up

By default Phase 2 uses **`--workers 4`** (parallel). With `--workers 1`, PRs are fetched **one at a time**. Each PR triggers **about six GitHub REST calls** via `gh api`:

| Call | Endpoint | Purpose |
|------|----------|---------|
| 1 | `GET /pulls/{n}` | PR metadata, creator, merge time |
| 2+ | `GET /pulls/{n}/commits` | Branch start, commit counts (paginated) |
| 2+ | `GET /pulls/{n}/files` | Added / modified / removed file counts |
| 1 | `GET /issues/{n}/events` | Draft / ready-for-review timeline |
| 1 | `GET /pulls/{n}/reviews` | First feedback, approval, reviewer counts |
| 1 | `GET /issues/{n}/comments` | First feedback from comments |

Large PRs with many commits or files add extra paginated requests. Phase 3 may fetch reviews again for PRs in the review catalog that were not in the activity catalog (cached when possible).

Every call spawns a **`gh api` subprocess** (`github/client.py`), so overhead adds up even when the network is fast.

### GitHub rate limits

Authenticated REST access is typically **5,000 requests/hour** per user/token. Search API is much lower (~30 requests/minute). A month with 500 PRs at ~6 calls each is ~3,000 REST calls — usually fine for one run, but aggressive parallelization can trigger **429** responses (the client retries transient errors including 429).

### What you can do now (no code changes)

| Approach | When to use |
|----------|-------------|
| **`--merged-only`** | Smaller PR set when you only care about merged work |
| **`--from-cache`** | Rebuild TSV/Excel after a successful fetch without hitting GitHub again |
| **Narrow date window** | Weekly or bi-weekly runs instead of full months during development |
| **Run in background** | `nohup uv run github-analysis run ... &` and monitor `_run.log` |
| **Split by period** | Run two half-month reports if you hit search pagination limits |

### Parallel fetch (`--workers`)

Phase 2 supports parallel PR detail fetch:

```bash
uv run github-analysis run \
  --repo https://github.com/Customer-Engagement-Digital-Technology/global-services.git \
  --start-date 2026-05-01 \
  --end-date 2026-06-01 \
  --merged-only \
  --workers 4 \
  -o ~/Documents/global-services-may-2026.xlsx
```

| Flag | Default | Notes |
|------|---------|-------|
| `--workers N` | **4** | Parallel threads for Phase 2. Use `1` for original serial behavior. |
| | | **3** is slightly more conservative on rate limits; **4** is the default balance. |

Progress lines in `_run.log` may complete out of PR order when `N > 1`; the detail TSV is sorted by PR number.

### Parallel fetch (implementation)

**You do not have to run serially.** Phase 2 is embarrassingly parallel: each PR is independent once you have the catalog from Phase 1.

A practical approach for this codebase:

1. **`--workers N`** on `analyze` and `run` (default **4**, use `1` for serial).
2. **`ThreadPoolExecutor`** in `runner.py` — each worker calls `build_pull_request_row()` with its own `GhClient`.
3. Results are merged and sorted by PR number after the pool finishes.

Start with **`N=4`** (default). Use **`N=3`** if you see 429 rate-limit retries in `_run.log`.

**Why not multiple OS processes?** Possible (`ProcessPoolExecutor`), but each process still shells out to `gh`; threads share one Python process and are simpler for logging and the review cache. Multiprocessing helps only if Python CPU work were the bottleneck — here it is not.

**Other optimizations (larger refactors):**

- **GraphQL** — batch multiple PRs in one query (fewer round trips, more complex schema).
- **Skip optional calls** — e.g. omit `issue_comments` if first-feedback-from-reviews-only is acceptable.
- **Direct HTTP client** — replace per-call `gh` subprocess with `httpx` + `GH_TOKEN` (faster, loses `gh auth` convenience).

---

## Understanding the output

### Individual production summary (one row per GitHub user)

File: `{name}_person_summary.tsv` — Excel sheet **Individual Production**.

| Column | Meaning |
|--------|---------|
| `user` | GitHub login |
| `prs_merged` | PRs **created by** this person that **merged** in the window |
| `prs_reviewed` | Distinct PRs where this person **submitted any review** in the window |
| `prs_approved` | Distinct PRs where this person submitted an **APPROVED** review in the window |
| `prs_authored` | PRs they **created** in the window |
| `prs_open` | Authored PRs still open or closed without merge |
| `avg_files_added_per_pr` | Mean **new files** (`status: added`) per **authored** PR |
| `avg_files_changed_per_pr` | Mean **modified/renamed** files per **authored** PR (excludes adds and deletions) |
| `min_hours_created_to_merged` | Shortest time (**hours**) from PR open to merge, over **authored merged** PRs |
| `max_hours_created_to_merged` | Longest time (**hours**) from PR open to merge, over authored merged PRs |
| `avg_hours_created_to_merged` | Mean time (**hours**) from PR open to merge, over authored merged PRs |

**Added vs changed:** GitHub classifies each file in a PR diff as `added`, `modified`/`renamed`, or `removed`.

- **`avg_files_added_per_pr`** — brand-new files only  
- **`avg_files_changed_per_pr`** — existing files edited or renamed (not new, not deleted)

**Merge cycle time:** computed from each PR’s `pr_created` and `merged` timestamps (hours, 2 decimal places). Only **authored** PRs that merged with both timestamps count. Blank when the person has no qualifying merged PRs.

Blank file averages mean the person **authored no PRs** in the window (they may still appear with review/approval counts).

Review and approval counts use review **`submitted_at`** inside your date window, not PR merge date.

### PR detail (optional)

File: `{name}.tsv` — Excel sheet **PR Detail**.

| Column | Meaning |
|--------|---------|
| `pr_creator` | Person who **opened** the PR (GitHub `user` field — not assignee) |
| `approved_by` | Login of the first **APPROVED** reviewer on the PR |
| `pr_number` / `pr_url` | PR identity and link |
| `merged` | Merge timestamp (empty if not merged) |
| `pr_files_total` | Total files changed |
| `pr_files_added` | New files |
| `pr_files_modified` | Modified/renamed files |
| `pr_files_removed` | Deleted files |

The detail file also includes lifecycle timestamps (opened, first feedback, approval, merge), hours since branch start, and elapsed hours between milestones. Check the **`notes`** column for truncation or catalog mismatches (e.g. `catalog_author_mismatch`).

### Opening files

- **Excel:** open the `.xlsx` directly.
- **TSV in Excel:** File → Open → select `.tsv` → choose **Tab** as delimiter. You may delete the first two note rows and footer rows for a clean table.

---

## Attribution rules

These rules drive manager-facing numbers. They are intentional — do not use assignees or commit authors for “who did the work.”

| Metric | Counted as | Not used |
|--------|------------|----------|
| **PR author / creator** | GitHub `user` on the pull request (who opened it) | Assignees, merge committer |
| **Reviewer** | Anyone who submitted a review (`submitted_at` in window) | Review comments without a formal review |
| **Approver** | Review with `state: APPROVED` in window | LGTM comments, CODEOWNERS without review |
| **File averages** | Mean over PRs **authored** by that person | Reviewed-only contributors get blank averages |
| **Merge cycle time** | Min/max/avg hours from PR open to merge on **authored merged** PRs | PRs missing `created_at` or `merged_at` |

The run log lists every person in the summary with merged / reviewed / approved / authored counts for audit.

---

## Configuration

Edit `github_analysis/config.py`:

| Setting | Default | Purpose |
|---------|---------|---------|
| `REPORT_TZ` | `America/New_York` | Timezone for calendar dates and report timestamps |
| `DEFAULT_GITHUB_OWNER` | `Customer-Engagement-Digital-Technology` | Org used when `--repo` is a short name |
| `DEFAULT_OUTPUT_DIR` | `~/Documents` | Default folder for TSV and Excel output |
| `DEFAULT_FETCH_WORKERS` | `4` | Default `--workers` for Phase 2 parallel fetch |
| `GH_API_TIMEOUT_SEC` | `90` | Per-request timeout for `gh api` |
| `GH_API_RETRIES` | `4` | Retries on transient failures (429, 502, timeouts) |
| `SEARCH_MAX_PAGES` | `20` | Max search pages (~2000 hits per query) |
| `API_LIST_PAGES_MAX` | `100` | Max pages for commits/files lists per PR |

After changing config, re-run reports — no reinstall needed.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `uv: command not found` | uv not installed or not on PATH | Reinstall uv; restart terminal; ensure `~/.local/bin` is on PATH |
| `gh: command not found` | GitHub CLI not installed | [Install gh](https://cli.github.com/) |
| `gh auth status` fails | Not logged in | Run `gh auth login` or set `GH_TOKEN` |
| `401` / `403` / `404` on org repo | Token lacks access or SSO not authorized | Create PAT with `repo` scope; authorize SSO for the org |
| `openpyxl is required` | Excel group not installed | `uv sync --group excel` |
| Empty report | Wrong date range or no activity | Widen dates; confirm PRs were merged/opened/reviewed in window |
| `skip PR #…` lines | Transient API error | Re-run; check `gh api` access to that repo |
| Excel shows one wide column | Wrong delimiter | Import as TSV with Tab separator |
| Very slow run | Many PRs; serial fetch (~6 API calls/PR) | Monitor `_run.log`; use `--from-cache` for rebuilds; see [Performance](#performance-and-optimization) |
| Log stopped at `[N/492]` | Still running or hung on one PR | Wait 2–3 min; if frozen, check `gh api` manually; re-run with `--from-cache` if `_raw.json` exists |
| `429` / rate limit | Too many API calls | Wait and retry; use `--workers 3` or `--workers 1` |

**Diagnostic commands:**

```bash
uv run github-analysis --version
gh auth status
gh api user
gh repo view OWNER/REPO
```

---

## Extending the CLI

New commands are added under `github_analysis/cli/commands/`:

1. Create `mycommand.py` with:
   - `register(subparsers)` — define flags and `parser.set_defaults(handler=run)`
   - `run(args) -> int` — command logic
2. Register in `github_analysis/cli/commands/__init__.py` → `COMMAND_REGISTRARS`

The new command automatically appears in `github-analysis --help` and gets its own `--help`.

---

## Sharing with your team

1. Share this repository: `https://github.com/michaelwitz-sbd/github-analysis`
2. Each person runs **Install uv**, **Clone**, **`uv sync --group excel`**, and **GitHub authentication** once
3. Run monthly reports, for example:

```bash
uv run github-analysis run \
  --repo global-services \
  --start-date 2026-05-01 \
  --end-date 2026-06-01 \
  --merged-only \
  --workers 4 \
  -o ~/Documents/global-services-may-2026.xlsx
```

Or use `./run_monthly_report.sh global-services 2026-05-01 2026-06-01 --merged-only`
4. Distribute the `.xlsx` or `.tsv` files from `~/Documents` (or your `--output-dir`) — they are not committed to git

---

## Limits

- **One repository per run** — run separately for each repo you track
- **GitHub search pagination** — very large months may hit ~2000 hits per search query
- **Reviews/comments** — first 100 items per PR inspected for timing
- **Files/commits** — up to 10,000 per PR; truncation noted in the `notes` column
