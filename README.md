# GitHub Team Metrics

Pull **per-person engineering metrics** from any GitHub repository you can access: merged PRs, reviews, file-change averages, and optional PR-level detail. Output is Excel and TSV for managers and team leads.

Uses the [GitHub CLI](https://cli.github.com/) (`gh`) for API access. See [Install and setup](#install-and-setup) for prerequisites, token setup, and verification.

---

## Monthly combined workbook (CEDT)

**Primary deliverable each month:** `~/Dev/github-analysis-results/combined-YYYY-MM.xlsx`

That workbook has four sheets:

| Sheet | Contents |
|-------|----------|
| **Totals** | One row per GitHub user — PR counts **summed across all three repos** (no repo column) |
| **global-services** | Person metrics for that repo |
| **global-user-services** | Person metrics for that repo |
| **polaris-turbo** | Person metrics for that repo |

The monthly script **fetches raw data from GitHub** for all three CEDT repos, writes per-repo Excel/TSV/cache files, then **builds the combined workbook** automatically. Expect **10–20 minutes** depending on API volume.

### One-time setup

Complete [Install and setup](#install-and-setup) once: `uv`, `gh`, PAT or `gh auth login`, clone this repo, `uv sync --group excel`.

Verify before your first monthly run:

```bash
gh auth status
gh repo view Customer-Engagement-Digital-Technology/global-services
```

### Each month — run in Terminal

Replace `YYYY-MM` with the calendar month you are reporting (e.g. `2026-07` for all of July 2026):

```bash
cd ~/Dev/michaelwitz-sbd/github-analysis
./scripts/run_monthly.sh YYYY-MM
```

**Example — July 2026:**

```bash
./scripts/run_monthly.sh 2026-07
```

When it finishes, open:

```text
~/Dev/github-analysis-results/combined-2026-07.xlsx
```

**Dry-run** (prints the date window and output paths without fetching):

```bash
./scripts/run_monthly.sh 2026-07 --dry-run
```

### What the monthly script creates

All files land in **`~/Dev/github-analysis-results/`** (flat folder; the date window is in each filename):

| File | Purpose |
|------|---------|
| `combined-YYYY-MM.xlsx` | **Final deliverable** — Totals + three repo tabs |
| `{repo}-YYYY-MM-01_to_YYYY-MM-NN.xlsx` | Per-repo Excel (Individual Production + PR Detail) |
| `{repo}-…_person_summary.tsv` | Person rollup for that repo (input to Totals) |
| `{repo}-….tsv` | PR-level detail |
| `{repo}-…_raw.json` | Cache — re-export without re-fetching GitHub |
| `{repo}-…_run.log` | Progress and errors — **read this first if a run fails** |

Repos analyzed (production defaults):

| Repo | Parallel workers |
|------|------------------|
| `global-services` | 4 |
| `global-user-services` | 3 |
| `polaris-turbo` | 4 |

Flags applied automatically: **`--merged-only`**, US Eastern (`America/New_York`), half-open date window.

### Partial month (not a full calendar month)

```bash
cd ~/Dev/michaelwitz-sbd/github-analysis
./scripts/run_cedt_trio.sh START END
```

`END` is **exclusive** — for June 1–23 inclusive use `2026-06-01` and `2026-06-24`.

Produces `combined-START_to_END.xlsx` in `~/Dev/github-analysis-results/`.

### Rebuild combined Excel only (no GitHub fetch)

If per-repo `*_person_summary.tsv` files already exist:

```bash
cd ~/Dev/michaelwitz-sbd/github-analysis
uv run python scripts/combine_person_summaries.py \
  --input-dir ~/Dev/github-analysis-results \
  --stem-suffix "2026-07-01_to_2026-08-01" \
  -o ~/Dev/github-analysis-results/combined-2026-07.xlsx
```

Use `--stem-suffix` when the results folder contains more than one date window.

Human runbook: [docs/monthly-runbook.md](docs/monthly-runbook.md) and **`~/Dev/github-analysis-results/README.md`** (local output folder).

---

## Single-repo quick start

**Prerequisites:** [uv](https://docs.astral.sh/uv/), [GitHub CLI 2.30+](https://cli.github.com/) authenticated with a **personal access token (PAT)** or `gh auth login`, and read access to the target repo. See [Install and setup](#install-and-setup) for PAT scope, SSO, and verification.

```bash
git clone https://github.com/michaelwitz-sbd/github-analysis.git
cd github-analysis
uv sync --group excel

uv run github-analysis run \
  --repo global-services \
  --month 2026-05 \
  --merged-only \
  --workers 4
```

| Flag | Meaning |
|------|---------|
| `--month` | Full calendar month (`YYYY-MM`) — sets start/end dates automatically |
| `--timezone` | IANA timezone for calendar dates (default `America/New_York`) |
| `--start-date` | First calendar day **included** (use instead of `--month` for partial windows) |
| `--end-date` | First calendar day **excluded** — with `--month 2026-05`, same as `2026-05-01` .. `2026-06-01` |
| `--merged-only` | PR detail sheet: merged PRs only; person summary still includes authored, open, and review counts |
| `--workers` | Parallel fetch threads (default `4`) |
| `-o` | Excel path; sibling TSV, cache, and log share the same base name |

**Outputs** — default base name `{repo}_{start}_to_{end}` (date range in every filename; omit `-o` to use this pattern):

| File | Purpose |
|------|---------|
| `.xlsx` | Excel — **Individual Production** + **PR Detail** sheets (`run` only) |
| `_person_summary.tsv` | One row per person |
| `.tsv` | One row per pull request |
| `_raw.json` | Cache for `--from-cache` rebuilds |
| `_run.log` | Auth checks, progress, errors — **read this first if a run fails** |

Example: `global-services_2026-05-15_to_2026-06-01_run.log` for May 15–31 does not overwrite a full-month `..._2026-05-01_to_2026-06-01.*` report.

---

## Install and setup

Everything needed before your first report: install tools, clone the project, authenticate `gh`, and verify access.

### Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| [uv](https://docs.astral.sh/uv/) | latest | Python runtime and project dependencies |
| [GitHub CLI](https://cli.github.com/) (`gh`) | 2.30+ | All GitHub API calls (`gh api`) — **must be installed and authenticated** |
| **GitHub PAT or `gh auth login`** | — | Token with **`repo`** scope (classic) or fine-grained read on pull requests + contents |
| GitHub account | — | Read access to the repository you will analyze |
| Network | — | Reach `github.com` (no proxy config in this tool) |

Default report output directory: **`~/Dev/github-analysis-results/`** (override with `--output-dir` or `GITHUB_ANALYSIS_RESULTS`).

### 1. Install `uv`

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh   # macOS / Linux
```

Restart your shell or ensure `~/.local/bin` is on your `PATH`. Windows: see [uv installation docs](https://docs.astral.sh/uv/getting-started/installation/).

### 2. Install GitHub CLI (`gh`)

The tool does **not** call the GitHub REST API directly — every fetch goes through `gh api`. You must install and authenticate `gh` separately.

**macOS (Homebrew):**

```bash
brew install gh
gh --version    # expect 2.30 or newer
```

**Other platforms:** [cli.github.com](https://cli.github.com/) (Windows installer, Linux packages, etc.).

### 3. Clone the project and install dependencies

```bash
git clone https://github.com/michaelwitz-sbd/github-analysis.git
cd github-analysis
uv sync --group excel
uv run github-analysis --version    # expect 2.0.0
```

`uv sync` installs Python 3.9+ automatically. The `excel` group adds `openpyxl` for `.xlsx` output.

### 4. Authenticate with GitHub

Reports need a token that can **read** the target repository (including private org repos).

**Option A — interactive login (typical for local use):**

```bash
gh auth login
```

Choose: **GitHub.com** → **HTTPS** → authenticate via **browser** or **paste a token**. For private repositories, ensure the token has **`repo`** scope (classic PAT) or equivalent read access (fine-grained PAT).

**Option B — personal access token (PAT):**

1. Create a token at [github.com/settings/tokens](https://github.com/settings/tokens):
   - **Classic PAT:** enable the **`repo`** scope (full control of private repositories is not required — read is enough).
   - **Fine-grained PAT:** grant read access to **Contents** and **Pull requests** for the target repository (or org).
2. Log in with the token:

```bash
gh auth login --with-token <<< "ghp_YOUR_TOKEN_HERE"
```

**Organization SSO:** If your org enforces SAML SSO (e.g. `Customer-Engagement-Digital-Technology`), authorize the token for that org under GitHub → **Settings** → **Applications** → **Authorized OAuth Apps** / **Personal access tokens**.

**CI / automation:** Set `GH_TOKEN` or `GITHUB_TOKEN` in the environment before running `gh` or this tool — `gh` picks either variable automatically.

### 5. Verify setup

Run these before a large report. All should succeed without errors:

```bash
gh auth status
gh api user --jq .login
gh repo view Customer-Engagement-Digital-Technology/global-services   # or your target repo
uv run github-analysis --version
```

`gh auth status` should show a logged-in account with `Token scopes` including `repo` (or sufficient fine-grained permissions). If `gh repo view` returns 404, fix token scope or SSO authorization before running a report.

Each run also performs a **preflight** check (auth + repo read access) and writes the result to `_run.log`.

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
| `--month` | analyze, run | Full calendar month (`YYYY-MM`); cannot combine with `--start-date` / `--end-date` |
| `--timezone` | analyze, run | IANA timezone for dates and timestamps (default `America/New_York`) |
| `--start-date` | analyze, run | Start inclusive (`YYYY-MM-DD`); required unless `--month` is set |
| `--end-date` | analyze, run | End exclusive (`YYYY-MM-DD`); required unless `--month` is set |
| `--merged-only` | analyze, run | Detail sheet: merged PRs only (see [Monthly metrics](#monthly-metrics)) |
| `--workers` | analyze, run | Parallel fetch threads (default `4`; use `3` or `1` under rate pressure) |
| `-o`, `--output` | run | Excel path (`.xlsx`); writes sibling TSV files |
| `-o`, `--output` | analyze | Detail TSV path (`-` = stdout) |
| `-o`, `--output` | export | Excel path (required) |
| `--output-dir` | analyze, run | Output folder when `-o` omitted (default `~/Dev/github-analysis-results`) |
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

Reports use a **half-open** calendar window in the report timezone (`--timezone`, default `America/New_York`):

```
start <= event time < end   (end date is exclusive)
```

**Shorthand for a full calendar month:**

```bash
--month 2026-05    # same as --start-date 2026-05-01 --end-date 2026-06-01
```

Use `--start-date` and `--end-date` instead of `--month` for partial windows (e.g. May 15–31).

| Flag | Boundary | Meaning |
|------|----------|---------|
| `--month` | Full month | Sets start to the 1st and end to the 1st of the next month |
| `--start-date` | **Inclusive** (`>=`) | First calendar day **included** — activity from **00:00** in `--timezone` |
| `--end-date` | **Exclusive** (`<`) | First calendar day **excluded** — window ends the instant **before** 00:00 on this date |

**Important:** The end date uses **strict less-than**, not less-than-or-equal. A PR merged at **June 1 00:00** in the report timezone is **not** in a May report (`--month 2026-05` or `--end-date 2026-06-01`).

**Example — all of May 2026:**

| | Value |
|--|-------|
| `--month` | `2026-05` |
| equivalent dates | `2026-05-01` .. `2026-06-01` |
| **Includes** | May 1 00:00:00 through May 31 23:59:59 (in `--timezone`) |
| **Excludes** | June 1 and later |

Every metric (merged, authored, reviews, `prs_open` snapshot at month-end) uses this same window. GitHub search queries use the equivalent inclusive calendar range (`2026-05-01..2026-05-31` for the example above).

**More examples:**

| Period | `--month` or dates | Last day included |
|--------|-------------------|-------------------|
| All of May 2026 | `--month 2026-05` | May 31 |
| One week (May 1–7) | `2026-05-01` .. `2026-05-08` | May 7 |
| May 15–31 | `2026-05-15` .. `2026-06-01` | May 31 |
| Q1 2026 | `2026-01-01` .. `2026-04-01` | March 31 |

### Common workflows

**Auto-named files** (no `-o`):

```bash
uv run github-analysis run \
  --repo global-services \
  --month 2026-05 \
  --merged-only --workers 4
# → ~/Dev/github-analysis-results/global-services_2026-05-01_to_2026-06-01.xlsx (+ siblings)
```

**Three repos + combined workbook** — use the [monthly script](#each-month--run-in-terminal) or `scripts/run_cedt_trio.sh`.

**Analyze then export separately:**

```bash
uv run github-analysis analyze \
  --repo global-services \
  --start-date 2026-05-01 --end-date 2026-06-01 \
  --merged-only --workers 4 \
  -o ~/Dev/github-analysis-results/global-services-may-2026.tsv

uv run github-analysis export \
  --summary ~/Dev/github-analysis-results/global-services-may-2026_person_summary.tsv \
  --detail ~/Dev/github-analysis-results/global-services-may-2026.tsv \
  -o ~/Dev/github-analysis-results/global-services-may-2026.xlsx
```

**Rebuild from cache** (no GitHub fetch; person summary recomputed from cached timestamps):

```bash
uv run github-analysis analyze \
  --from-cache ~/Dev/github-analysis-results/global-services-may-2026_raw.json \
  --repo global-services \
  --start-date 2026-05-01 --end-date 2026-06-01 \
  --merged-only \
  -o ~/Dev/github-analysis-results/global-services-may-2026.tsv
```

**Monitor a run** (log path matches your `--start-date` and `--end-date`; written as soon as the run starts):

```bash
tail -f ~/Dev/github-analysis-results/global-services_2026-05-15_to_2026-06-01_run.log
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
| `prs_closed_unmerged` | PRs **they opened in the window** and **closed without merge** before window end |
| `prs_reviewed` | Distinct PRs with any review submitted in the window |
| `prs_approved` | Distinct PRs with an APPROVED review in the window |
| `avg_files_added_per_pr` | Mean new files per PR in the detail report |
| `avg_files_changed_per_pr` | Mean modified/renamed files per detail-row PR |
| `min/max/avg_hours_pr_created_to_merged` | Hours from PR open to merge (merged-in-window only; excludes `prs_open`) |

**PR count columns for PRs opened in the window** reconcile as:

For PRs **opened in the window only**, at window end each falls into exactly one outcome bucket:

`prs_authored` ≈ (window-opened PRs merged in window) + (window-opened PRs still open at end) + `prs_closed_unmerged`

**`prs_merged` and `prs_open` are not subsets of `prs_authored`** — they include carry-over PRs opened before the window, so column totals do not sum this way.

Example for May 2026 (`2026-05-01` .. `2026-06-01`):

| Scenario | `prs_authored` | `prs_merged` | `prs_open` | `prs_closed_unmerged` |
|----------|----------------|--------------|------------|------------------------|
| Opened May 31, merged in June | 1 | 0 | 1 | 0 |
| Opened May 15, merged May 20 | 1 | 1 | 0 | 0 |
| Opened in April, merged in May | 0 | 1 | 0 | 0 |
| Opened in April, still open May 31 | 0 | 0 | 1 | 0 |
| Opened May 10, closed without merge May 12 | 1 | 0 | 0 | 1 |
| Opened 8 in May; all 5 merges are among those 8; 2 still open; 1 closed unmerged | 8 | 5 | 2 | 1 |

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
- **Person summary** — still computes `prs_authored`, `prs_open`, `prs_closed_unmerged`, and review counts via separate searches

A PR counts toward **`prs_open`** at window end if it existed, had not merged, and was not closed without merge before window end — regardless of when it was opened.

A PR counts toward **`prs_closed_unmerged`** if they opened it in the window and it was closed without merge before window end.

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
| `DEFAULT_REPORT_TZ_NAME` / `--timezone` | `America/New_York` | Calendar dates and timestamps (override per run) |
| `DEFAULT_GITHUB_OWNER` | `Customer-Engagement-Digital-Technology` | Org for short `--repo` names |
| `DEFAULT_OUTPUT_DIR` | `~/Dev/github-analysis-results` | Default output folder |
| `DEFAULT_FETCH_WORKERS` | `4` | Default `--workers` |

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| `uv` / `gh` not found | Complete [Install and setup](#install-and-setup) steps 1–2; ensure both are on `PATH` |
| `gh auth status` fails | Step 4: `gh auth login` or `gh auth login --with-token`; set `GH_TOKEN` for CI |
| `401` / `403` / `404` on org repo | PAT needs `repo` scope (classic) or read Contents + Pull requests (fine-grained); authorize org SSO |
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

---

## For contributors

See [docs/](docs/README.md) for architecture and CLI extension notes.
