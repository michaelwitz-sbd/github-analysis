# Instructions for AI assistants

## CLI structure

Single entry point: `github-analysis` (via `uv run github-analysis`).

| Command | Module |
|---------|--------|
| `analyze` | `github_analysis/cli/commands/analyze.py` |
| `export` | `github_analysis/cli/commands/export.py` |
| `run` | `github_analysis/cli/commands/run.py` |

To add a command: create a module with `register(subparsers)` and `run(args) -> int`, then add to `COMMAND_REGISTRARS` in `github_analysis/cli/commands/__init__.py`.

## Package layout

```
github-analysis/
├── pyproject.toml
├── run_monthly_report.sh
├── github_pr_timeline_report.py   # legacy → analyze
├── export_report_xlsx.py          # legacy → export
└── github_analysis/
    ├── config.py                  # timezone, default org, API limits
    ├── models.py                  # ReportConfig, PullRequestRow, UserSummary
    ├── repo.py                    # parse --repo
    ├── time_utils.py              # date windows, timestamps
    ├── cli/commands/              # analyze, export, run
    ├── github/                    # GhClient, preflight, pulls
    ├── catalog/search.py          # Phase 1 PR discovery (calendar date ranges)
    ├── analysis/                  # pr_builder, reviews, summaries
    ├── cache/raw_store.py         # _raw.json read/write
    ├── export/                    # paths, tsv, xlsx
    └── pipeline/runner.py         # run_report() orchestration
```

**Data flow:** CLI → `pipeline/runner.py` (catalog → fetch → summarize) → `export/`

## Phase 2 API calls (per PR)

Each merged PR triggers ~6 REST calls via `gh api`:

| Call | Endpoint |
|------|----------|
| Metadata | `GET /pulls/{n}` |
| Commits | `GET /pulls/{n}/commits` (paginated) |
| Files | `GET /pulls/{n}/files` (paginated) |
| Events | `GET /issues/{n}/events` |
| Reviews | `GET /pulls/{n}/reviews` |
| Comments | `GET /issues/{n}/comments` |

Phase 2 uses `ThreadPoolExecutor` in `runner.py` with `--workers N` (default 4). Each worker has its own `GhClient`. Results merge and sort by PR number.

## Catalog search

`catalog/search.py` builds Phase 1 queries using GitHub **calendar date ranges** (`merged:2026-05-01..2026-05-31`), aligned with `--start-date` and the day before `--end-date`. Do not use ISO timestamp `>=`/`<` qualifiers in search — GitHub ignores or mishandles them.

## Config defaults (`config.py`)

| Setting | Default |
|---------|---------|
| `DEFAULT_FETCH_WORKERS` | 4 |
| `GH_API_RETRIES` | 4 |
| `SEARCH_MAX_PAGES` | 20 (GitHub hard cap: 1,000 results) |
| `API_LIST_PAGES_MAX` | 100 |

Update `README.md` when CLI surface or output columns change.
