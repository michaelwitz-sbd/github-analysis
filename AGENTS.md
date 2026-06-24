# Instructions for AI assistants (`github-analysis`)

This file is for **agents working on this codebase** and for **agents helping a human run reports** on their machine. Read it before changing code or executing analysis.

---

## Repository layout

```
github-analysis/
├── pyproject.toml                 # package github-analysis v2.x, uv project
├── README.md                      # human runbook + column definitions (update when CLI/columns change)
├── AGENTS.md                      # this file
├── github_pr_timeline_report.py   # legacy wrapper → `analyze`
├── export_report_xlsx.py          # legacy wrapper → `export`
├── scripts/
│   ├── run_cedt_trio.sh           # three standard CEDT repos + combined Excel
│   └── combine_person_summaries.py # build multi-repo workbook from *_person_summary.tsv
├── docs/
│   ├── architecture.md            # module map, pipeline phases
│   └── extending-the-cli.md
└── github_analysis/
    ├── config.py                  # timezone, default org, DEFAULT_OUTPUT_DIR
    ├── cli/commands/              # analyze | export | run
    ├── pipeline/runner.py         # orchestration
    ├── catalog/search.py          # Phase 1 PR discovery
    ├── analysis/                  # metrics, person summaries
    ├── github/                    # GhClient, preflight (gh auth + repo access)
    ├── cache/raw_store.py         # _raw.json
    └── export/                    # TSV + Excel paths
```

**Related (sibling, not in this repo):**

| Path | Purpose |
|------|---------|
| `~/Dev/github-analysis-results/` | Default output for production runs (flat; date in filenames) |
| `~/Dev/github-analysis-results/run_monthly.sh` | One-command full calendar month |
| `~/Dev/github-analysis-results/AGENTS.md` | Agent runbook for results folder |

---

## Prerequisites (verify before running)

The human (or you on their behalf) needs:

| Requirement | Check |
|-------------|--------|
| [uv](https://docs.astral.sh/uv/) | `uv --version` |
| [GitHub CLI](https://cli.github.com/) 2.30+ | `gh --version` |
| **GitHub auth** — interactive login **or** PAT via `gh auth login --with-token` | `gh auth status` |
| Token with **`repo`** scope (classic PAT) or fine-grained read on target repos | `gh repo view Customer-Engagement-Digital-Technology/global-services` |
| Org SSO authorized (CEDT) if enforced | token works on a private org repo |

**PAT setup (when human asks):** See README [Install and setup → Authenticate with GitHub](README.md#4-authenticate-with-github). For automation, `GH_TOKEN` or `GITHUB_TOKEN` in the environment is picked up by `gh`.

**Project install:**

```bash
cd ~/Dev/michaelwitz-sbd/github-analysis   # or cloned path
uv sync --group excel
uv run github-analysis --version
```

---

## CLI commands

Single entry point: `uv run github-analysis` (or `github-analysis` after `uv sync`).

| Command | Purpose |
|---------|---------|
| `run` | Full pipeline: fetch → TSV + Excel + cache + log |
| `analyze` | Fetch/analyze only (no Excel unless combined elsewhere) |
| `export` | Re-export from `--from-cache` without re-fetching |

### Common flags

| Flag | Meaning |
|------|---------|
| `--repo NAME` | Short name (`global-services`) or `owner/repo` |
| `--month YYYY-MM` | Full calendar month (Eastern by default) |
| `--start-date` / `--end-date` | Half-open window; **end date is exclusive** |
| `--merged-only` | PR detail sheet: merged only; person summary still has all counts |
| `--workers N` | Parallel PR fetch threads (default 4) |
| `--output-dir DIR` | Directory for sibling artifacts (default `~/Dev/github-analysis-results`) |
| `-o PATH.xlsx` | Excel path; TSV/cache/log share the same stem |

### Standard CEDT trio (production)

| Repo | Workers |
|------|---------|
| `global-services` | 4 |
| `global-user-services` | 3 |
| `polaris-turbo` | 4 |

Always use **`--merged-only`** unless the human explicitly asks otherwise.

### Date windows (America/New_York, half-open)

| Human says | `--start-date` | `--end-date` |
|------------|----------------|--------------|
| Full July 2026 | `2026-07-01` | `2026-08-01` |
| June 1–23 inclusive | `2026-06-01` | `2026-06-24` |

---

## When the human asks you to run analysis

**Run it yourself.** Do not paste long command sequences and ask them to execute unless auth is broken and only they can complete OAuth.

### Full calendar month (preferred)

```bash
bash ~/Dev/github-analysis-results/run_monthly.sh YYYY-MM
```

Deliverable: `~/Dev/github-analysis-results/combined-YYYY-MM.xlsx`

### Custom / partial window

```bash
cd ~/Dev/michaelwitz-sbd/github-analysis
./scripts/run_cedt_trio.sh START END
# optional: ./scripts/run_cedt_trio.sh START END ~/Dev/github-analysis-results combined-my-label.xlsx
```

### Re-combine only (existing `*_person_summary.tsv`)

When raw data already exists and you only need a fixed combined workbook:

```bash
cd ~/Dev/michaelwitz-sbd/github-analysis
uv run python scripts/combine_person_summaries.py \
  --input-dir ~/Dev/github-analysis-results \
  --stem-suffix "2026-06-01_to_2026-06-23" \
  -o ~/Dev/github-analysis-results/combined-2026-06-01_to_2026-06-23.xlsx
```

Use `--stem-suffix` whenever the input directory holds more than one date window.

### Agent checklist

1. `gh auth status` — if this fails, guide human through README auth section; you cannot complete browser OAuth.
2. Run the appropriate script for the requested window.
3. On failure, read `{repo}_*_run.log` in the output directory first.
4. Report the path to **`combined-*.xlsx`** when done.
5. Do not commit generated `.tsv` / `.xlsx` / `.json` / `.log` files.

### Communicating with the human

- Confirm the **calendar window** in plain language (“June 1–23, Eastern, merged-only production run”).
- Say **where files landed** (full paths to combined Excel and per-repo logs).
- If a run takes several minutes, say so once — do not ask them to run parallel fetches.
- If shell output is empty in Cursor, set **`working_directory`** to the tool repo or results folder and retry before claiming failure.

---

## Combined Excel workbook

Built by `scripts/combine_person_summaries.py`:

| Sheet | Contents |
|-------|----------|
| **Totals** | One row per **user**; all count columns **summed across repos**. Same columns as person summary — **no repo column** (org-wide user metrics). |
| `{repo}` | Person summary for that repo only. **Tab name is the repo** — no repo column on the sheet. |

Weighted averages on Totals: file averages by `prs_authored`; merge-cycle avg by `prs_merged`; min/max hours across repos.

---

## Working on the codebase

| Task | Where to look |
|------|----------------|
| Add CLI command | `docs/extending-the-cli.md`, `github_analysis/cli/commands/` |
| Pipeline / phases | `docs/architecture.md`, `github_analysis/pipeline/runner.py` |
| Output columns | `github_analysis/models.py`, `export/xlsx.py`, **update README.md** |
| Default paths / org | `github_analysis/config.py` |
| Combined workbook logic | `scripts/combine_person_summaries.py` |

After changing CLI surface, output columns, or default output directory, update **README.md** and, if run behavior changes, **`~/Dev/github-analysis-results/README.md`** and **`AGENTS.md`** there (only with human permission for protected results docs — monthly run path changes are expected).

---

## Module map (quick reference)

| Command | Module |
|---------|--------|
| `analyze` | `github_analysis/cli/commands/analyze.py` |
| `export` | `github_analysis/cli/commands/export.py` |
| `run` | `github_analysis/cli/commands/run.py` |

Full architecture: [docs/architecture.md](docs/architecture.md).
