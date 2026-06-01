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
8. [Understanding the output](#understanding-the-output)
9. [Configuration](#configuration)
10. [Troubleshooting](#troubleshooting)
11. [Extending the CLI](#extending-the-cli)

---

## What you get

Each report run writes files to **`~/Documents`** by default (override with `--output-dir`):

| File | Audience | Contents |
|------|----------|----------|
| `*_team_summary.tsv` / Excel **Team Summary** sheet | Managers | **One row per GitHub user** — merged PRs, reviews, average file counts |
| `*.tsv` / Excel **PR Detail** sheet | Deep dives | One row per pull request — lifecycle timing, file counts, URLs |

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
    │   └── pulls.py            # Pull request, commit, file, review endpoints
    │
    ├── catalog/                # PR discovery
    │   └── search.py           # GitHub issue search (merged, created, updated)
    │
    ├── analysis/               # Metrics computation
    │   ├── pr_builder.py       # Build one row per PR
    │   ├── reviews.py          # Count reviews by person in date window
    │   └── summaries.py        # Roll up per-person team summary
    │
    ├── export/                 # Output writers
    │   ├── paths.py            # Default filenames and paths
    │   ├── tsv.py              # Write detail and summary TSV
    │   └── xlsx.py             # Write Excel workbook (requires openpyxl)
    │
    └── pipeline/
        └── runner.py           # Orchestrates catalog → analysis → result
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

**All PRs merged in May 2026** on `global-services`:

```bash
uv run github-analysis run \
  --repo global-services \
  --start-date 2026-05-01 \
  --end-date 2026-06-01 \
  --merged-only
```

**Outputs** (default: `~/Documents/`):

```
~/Documents/global-services_2026-05-01_to_2026-06-01_team_summary.tsv
~/Documents/global-services_2026-05-01_to_2026-06-01.tsv
~/Documents/global-services_2026-05-01_to_2026-06-01.xlsx
```

**Custom output directory:**

```bash
uv run github-analysis run \
  --repo global-services \
  --start-date 2026-05-01 \
  --end-date 2026-06-01 \
  --merged-only \
  --output-dir ~/Documents/github-reports
```

**Shell wrapper (same result):**

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
  --end-date 2026-06-01
```

**Merged PRs only:**

```bash
uv run github-analysis analyze \
  --repo global-services \
  --start-date 2026-05-01 \
  --end-date 2026-06-01 \
  --merged-only
```

**Custom output paths:**

```bash
uv run github-analysis analyze \
  --repo global-services \
  --start-date 2026-05-01 \
  --end-date 2026-06-01 \
  -o reports/may-detail.tsv \
  --summary-output reports/may-team-summary.tsv
```

**Print detail TSV to terminal:**

```bash
uv run github-analysis analyze \
  --repo global-services \
  --start-date 2026-05-01 \
  --end-date 2026-06-01 \
  -o -
```

---

### Step 2 — Export to Excel

After `analyze`, or when TSV files already exist:

```bash
uv run github-analysis export \
  --summary analysis-results/global-services_2026-05-01_to_2026-06-01_team_summary.tsv \
  --detail analysis-results/global-services_2026-05-01_to_2026-06-01.tsv \
  -o analysis-results/global-services_2026-05-01_to_2026-06-01.xlsx
```

**Team summary only (manager view):**

```bash
uv run github-analysis export \
  --summary analysis-results/global-services_2026-05-01_to_2026-06-01_team_summary.tsv \
  --summary-only \
  -o analysis-results/may-team-summary.xlsx
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
| `-o`, `--output` | analyze, export | Output file path (`-` = stdout for analyze) |
| `--summary-output` | analyze | Custom path for team summary TSV |
| `--summary` | export | Input team summary TSV (required) |
| `--detail` | export | Input PR detail TSV (optional second Excel sheet) |
| `--summary-only` | export, run | Excel workbook with Team Summary sheet only |
| `--output-dir` | analyze, run | Output directory (default: `~/Documents`) |

---

## Understanding the output

### Team summary (one row per GitHub user)

| Column | Meaning |
|--------|---------|
| `user` | GitHub login |
| `prs_authored` | PRs authored by this person in the report window |
| `prs_merged` | Of those, how many were merged |
| `prs_open` | Authored PRs still open or closed without merge |
| `prs_reviewed` | Distinct PRs where this person **submitted a review** in the window |
| `avg_files_changed` | Average total files in the diff per authored PR |
| `avg_files_added` | Average new files per authored PR |

- **Review counts** use review `submitted_at` inside your date window.
- **Averages** are over **authored** PRs only; reviewers with no authored PRs show blank averages.

### PR detail (optional)

Key columns for sizing and tracing work:

| Column | Meaning |
|--------|---------|
| `committer` | PR author (GitHub login) |
| `pr_number` / `pr_url` | PR identity and link |
| `merged` | Merge timestamp (empty if not merged) |
| `pr_files_total` | Total files changed |
| `pr_files_added` | New files |
| `pr_files_modified` | Modified/renamed files |
| `pr_files_removed` | Deleted files |

The detail file also includes lifecycle timestamps (opened, first feedback, approval, merge) and elapsed hours between milestones.

### Opening files

- **Excel:** open the `.xlsx` directly.
- **TSV in Excel:** File → Open → select `.tsv` → choose **Tab** as delimiter. You may delete the first two note rows and footer rows for a clean table.

---

## Configuration

Edit `github_analysis/config.py`:

| Setting | Default | Purpose |
|---------|---------|---------|
| `REPORT_TZ` | `America/New_York` | Timezone for calendar dates and report timestamps |
| `DEFAULT_GITHUB_OWNER` | `Customer-Engagement-Digital-Technology` | Org used when `--repo` is a short name |
| `DEFAULT_OUTPUT_DIR` | `~/Documents` | Default folder for TSV and Excel output |

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
| Very slow run | Many PRs in window | Normal — each PR requires multiple API calls; progress prints to terminal |

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
3. Run monthly reports with `uv run github-analysis run ...` or `./run_monthly_report.sh`
4. Distribute the `.xlsx` or `.tsv` files from `analysis-results/` — they are not committed to git

---

## Limits

- **One repository per run** — run separately for each repo you track
- **GitHub search pagination** — very large months may hit ~2000 hits per search query
- **Reviews/comments** — first 100 items per PR inspected for timing
- **Files/commits** — up to 10,000 per PR; truncation noted in the `notes` column
