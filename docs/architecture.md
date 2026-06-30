# Architecture

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
    ├── catalog/search.py          # Phase 1 PR discovery
    ├── analysis/                  # pr_builder, reviews, summaries
    ├── reporting/                 # metric formulas and bucket helpers
    ├── cache/raw_store.py         # _raw.json read/write
    ├── cache/data_store.py        # local data/ snapshot cache
    ├── export/                    # paths, tsv, xlsx, html
    └── pipeline/runner.py         # run_report() orchestration
```

## Data flow

```
CLI command
  → pipeline/runner.py     (discover PRs, fetch details, summarize)
  → analysis/              (per-PR and per-person metrics)
  → reporting/             (shared rate, time, and bucket helpers)
  → export/                (TSV, Excel, and/or HTML)
```

`run --html` can also use `data/` as a generated local snapshot cache:

```
run --html
  → cache/data_store.py    (cache-first lookup)
  → pipeline/runner.py     (only on cache miss / refresh)
  → cache/data_store.py    (save fetched snapshot)
  → export/html.py         (render self-contained dashboard)
```

## Pipeline phases

| Phase | Module | What happens |
|-------|--------|----------------|
| Preflight | `github/preflight.py` | `gh auth status`, repo access check |
| Phase 1 | `catalog/search.py` | GitHub search → PR number catalog |
| Phase 2 | `analysis/pr_builder.py` | Fetch PR detail (parallel via `--workers`) |
| Phase 3 | `analysis/reviews.py`, `summaries.py` | Review counts, person rollups |
| Phase 3b | `analysis/authored_activity.py` | Open-at-window-end snapshot |
| Write | `export/`, `cache/raw_store.py`, `cache/data_store.py` | TSV, `_raw.json`, Excel, optional HTML and `data/` snapshot |

## Phase 2 — REST calls per PR

Each PR triggers about six `gh api` calls:

| Call | Endpoint |
|------|----------|
| Metadata | `GET /pulls/{n}` |
| Commits | `GET /pulls/{n}/commits` (paginated) |
| Files | `GET /pulls/{n}/files` (paginated) |
| Events | `GET /issues/{n}/events` |
| Reviews | `GET /pulls/{n}/reviews` |
| Comments | `GET /issues/{n}/comments` |

Phase 2 uses `ThreadPoolExecutor` in `pipeline/runner.py`. Each worker gets its own `GhClient`. After the initial PR metadata request, independent per-PR resources can also be fetched concurrently inside the PR worker. A global `gh api` semaphore caps total in-flight subprocess calls across both layers. Results are merged and sorted by PR number after the pool finishes.

## Catalog search

`catalog/search.py` builds Phase 1 queries with GitHub **calendar date ranges**:

```
merged:2026-05-01..2026-05-31
```

Ranges align with `--start-date` and the day before `--end-date`. ISO timestamp qualifiers (`merged:>=2026-05-01T04:00:00Z`) are unreliable in GitHub search and must not be used.

## Configuration (`config.py`)

| Setting | Default | Purpose |
|---------|---------|---------|
| `REPORT_TZ` | `America/New_York` | Calendar dates and report timestamps |
| `DEFAULT_GITHUB_OWNER` | org slug | Short `--repo` names |
| `DEFAULT_OUTPUT_DIR` | `~/Documents` | Default output folder |
| `DEFAULT_FETCH_WORKERS` | `4` | Default `--workers` |
| `GH_API_TIMEOUT_SEC` | `90` | Per-request timeout |
| `GH_API_RETRIES` | `4` | Retries on 429, 502, timeouts |
| `SEARCH_MAX_PAGES` | `20` | Search pagination (GitHub hard cap: 1,000 results) |
| `API_LIST_PAGES_MAX` | `100` | Max commit/file list pages per PR |
| `GH_API_MAX_IN_FLIGHT` | `12` | Global cap for concurrent `gh api` subprocess calls |
| `GH_API_MIN_INTERVAL_SEC` | `0.12` | Minimum spacing between starting `gh api` subprocess calls |
| `PR_RESOURCE_FETCH_WORKERS` | `5` | Default concurrent resource fetches inside each PR detail worker |

## HTML dashboard and `data/` cache

The HTML dashboard path is owned by `export/html.py`. It converts one or more
`ReportResult` objects into an embedded JSON view model, using
`reporting/metrics.py` for shared rate/time calculations and
`reporting/periods.py` for weekly/monthly bucket labels. It then writes a
self-contained static document with inline CSS and JavaScript. Tables are
sortable in-browser and large comparison/breakdown tables are scrollable.

`run --html --bucket weekly|monthly|none` controls the trend bucket granularity
used by the generated dashboard.

The generated `data/` folder stores reusable raw snapshots to reduce GitHub API
pressure. `cache/data_store.py` wraps the existing raw cache payload with
metadata such as schema version, repository, date window, timezone, and fetch
timestamp. With `run --cache-policy cache-first`, matching snapshots are loaded
before GitHub is contacted; cache misses are fetched and saved back into
`data/raw/`.
