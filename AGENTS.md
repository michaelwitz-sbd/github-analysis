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

- `github/` — gh api client
- `catalog/` — PR search/discovery
- `analysis/` — row building, reviews, summaries
- `export/` — TSV and xlsx writers
- `pipeline/runner.py` — `run_report()` orchestration

Update `README.md` when CLI surface or output columns change.
