from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from github_analysis.cache.data_store import load_snapshot, save_snapshot_from_raw_cache
from github_analysis.cache.raw_store import load_raw_cache
from github_analysis.cli.commands import analyze, export
from github_analysis.cli.commands.analyze import MERGED_ONLY_HELP, OUTPUT_FILES_EPILOG
from github_analysis.cli.report_window import (
    add_period_args,
    apply_resolved_window_to_args,
    date_window_note,
    resolve_report_window,
)
from github_analysis.config import (
    DEFAULT_FETCH_WORKERS,
    DEFAULT_OUTPUT_DIR,
    PR_RESOURCE_FETCH_WORKERS,
)
from github_analysis.export.paths import (
    default_detail_path,
    default_html_path,
    default_summary_path,
    default_xlsx_path,
    html_path_from_detail,
    paths_from_excel_output,
    raw_cache_path_from_detail,
    run_log_path_from_detail,
)
from github_analysis.export.html import export_html_report
from github_analysis.export.tsv import write_detail_tsv, write_summary_tsv
from github_analysis.export.xlsx import export_workbook
from github_analysis.models import ReportConfig, ReportResult, RepositoryRef
from github_analysis.repo import resolve_repository


@dataclass(frozen=True)
class _RepoRunPaths:
    detail_path: str
    summary_path: str
    xlsx_path: str
    html_path: str


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "run",
        help="Analyze and export Excel in one step",
        description=(
            "Convenience command: runs `analyze` then `export` with default output paths. "
            "Best for monthly manager reports.\n\n"
            f"{date_window_note()}.\n\n"
            "To rebuild Excel from an existing *_raw.json cache, use `analyze --from-cache` "
            "then `export` instead."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            f"{OUTPUT_FILES_EPILOG}"
            "  {repo}_{start}_to_{end}.xlsx\n\n"
            "Examples:\n"
            "  # All of May 2026 (recommended):\n"
            "  github-analysis run --repo global-services --month 2026-05 --merged-only\n"
            "  # May 15 through month end — separate files from a full-month run:\n"
            "  github-analysis run --repo global-services --start-date 2026-05-15 --end-date 2026-06-01 --merged-only\n"
            "  # Custom Excel base name (sibling TSV, cache, and log share this stem):\n"
            "  github-analysis run --repo global-services --month 2026-05 --merged-only --workers 4 \\\n"
            "    -o ~/Documents/global-services-may-2026.xlsx"
        ),
    )
    analyze._add_repo_args(parser)
    add_period_args(parser)
    parser.add_argument(
        "--merged-only",
        action="store_true",
        help=MERGED_ONLY_HELP,
    )
    parser.add_argument(
        "--summary-only",
        action="store_true",
        help="Excel workbook contains only the Individual Production sheet",
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        metavar="DIR",
        help=f"Directory for auto-named files when -o is not used (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "-o",
        "--output",
        metavar="PATH",
        help=(
            f"Excel workbook path (.xlsx). Default: {DEFAULT_OUTPUT_DIR}/{{repo}}_{{start}}_to_{{end}}.xlsx. "
            "Also writes sibling files: {{stem}}.tsv, {{stem}}_person_summary.tsv, "
            "{{stem}}_raw.json, {{stem}}_run.log"
        ),
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=DEFAULT_FETCH_WORKERS,
        metavar="N",
        help=(
            f"Parallel workers for Phase 2 PR detail fetch (default: {DEFAULT_FETCH_WORKERS}). "
            "Use 1 for serial fetch."
        ),
    )
    parser.add_argument(
        "--pr-resource-workers",
        type=int,
        default=PR_RESOURCE_FETCH_WORKERS,
        metavar="N",
        help=(
            "Parallel resource fetches inside each PR detail worker "
            f"(default: {PR_RESOURCE_FETCH_WORKERS}; use 1 for serial baseline)."
        ),
    )
    parser.add_argument(
        "--html",
        action="store_true",
        help="Also write a self-contained HTML dashboard report",
    )
    parser.add_argument(
        "--html-output",
        metavar="PATH",
        help="HTML dashboard path. Default: sibling .html next to the Excel output",
    )
    parser.add_argument(
        "--bucket",
        choices=("weekly", "monthly", "none"),
        default="weekly",
        help="Bucket granularity for HTML trend charts (default: weekly)",
    )
    parser.add_argument(
        "--data-dir",
        default="data",
        metavar="DIR",
        help="Local cache directory for reusable raw snapshots (default: data)",
    )
    parser.add_argument(
        "--cache-policy",
        choices=("cache-first", "github-only"),
        default="cache-first",
        help="Use local data snapshots before GitHub, or always fetch GitHub (default: cache-first)",
    )
    parser.add_argument(
        "--refresh-all",
        action="store_true",
        help="Ignore data-dir snapshots and fetch from GitHub",
    )
    parser.set_defaults(handler=run)


def run(args: argparse.Namespace) -> int:
    try:
        repo_args = [part.strip() for part in args.repo.split(",") if part.strip()]
        repositories = [resolve_repository(repo_arg, args.owner) for repo_arg in repo_args]
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    if not repositories:
        print("Error: --repo must include at least one repository", file=sys.stderr)
        return 2

    try:
        start_date, end_date, report_tz = resolve_report_window(args)
        apply_resolved_window_to_args(args, start_date, end_date, report_tz)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if getattr(args, "workers", DEFAULT_FETCH_WORKERS) < 1:
        print("Error: --workers must be at least 1", file=sys.stderr)
        return 2
    if getattr(args, "pr_resource_workers", PR_RESOURCE_FETCH_WORKERS) < 1:
        print("Error: --pr-resource-workers must be at least 1", file=sys.stderr)
        return 2

    output_dir = os.path.expanduser(args.output_dir)
    if len(repositories) > 1:
        return _run_multiple_repositories(args, repositories, start_date, end_date, report_tz, output_dir)

    repository = repositories[0]
    paths = _resolve_single_repo_paths(args, repository, output_dir)
    config = _report_config(repository, start_date, end_date, report_tz, args.merged_only)
    cache_allowed = args.cache_policy == "cache-first" and not args.refresh_all

    exit_code, result = _run_repository(
        args,
        repository=repository,
        config=config,
        paths=paths,
        output_dir=output_dir,
        cache_allowed=cache_allowed,
        log_run=True,
        cache_log_label=args.data_dir,
    )
    if exit_code != 0:
        return exit_code

    if args.html and result is not None:
        export_html_report([result], paths.html_path, bucket_granularity=args.bucket)
        print(f"Wrote {paths.html_path}", file=sys.stderr)
    return 0


def _report_config(
    repository: RepositoryRef,
    start_date,
    end_date,
    report_tz,
    merged_only: bool,
) -> ReportConfig:
    return ReportConfig(
        repository=repository,
        start_date=start_date,
        end_date=end_date,
        report_tz=report_tz,
        merged_only=merged_only,
        include_summary=True,
    )


def _resolve_single_repo_paths(
    args: argparse.Namespace,
    repository: RepositoryRef,
    output_dir: str,
) -> _RepoRunPaths:
    if args.output:
        xlsx_path, summary_path, detail_path = paths_from_excel_output(args.output)
        os.makedirs(os.path.dirname(xlsx_path) or ".", exist_ok=True)
        html_path = args.html_output or html_path_from_detail(detail_path)
    else:
        os.makedirs(output_dir, exist_ok=True)
        detail_path = default_detail_path(
            repository.name, args.start_date, args.end_date, output_dir=output_dir
        )
        summary_path = default_summary_path(
            repository.name, args.start_date, args.end_date, output_dir=output_dir
        )
        xlsx_path = default_xlsx_path(
            repository.name, args.start_date, args.end_date, output_dir=output_dir
        )
        html_path = args.html_output or default_html_path(
            repository.name, args.start_date, args.end_date, output_dir=output_dir
        )
    return _RepoRunPaths(
        detail_path=detail_path,
        summary_path=summary_path,
        xlsx_path=xlsx_path,
        html_path=html_path,
    )


def _resolve_multi_repo_paths(
    args: argparse.Namespace,
    repository: RepositoryRef,
    output_dir: str,
) -> _RepoRunPaths:
    return _RepoRunPaths(
        detail_path=default_detail_path(
            repository.name, args.start_date, args.end_date, output_dir=output_dir
        ),
        summary_path=default_summary_path(
            repository.name, args.start_date, args.end_date, output_dir=output_dir
        ),
        xlsx_path=default_xlsx_path(
            repository.name, args.start_date, args.end_date, output_dir=output_dir
        ),
        html_path=default_html_path(
            repository.name, args.start_date, args.end_date, output_dir=output_dir
        ),
    )


def _build_analyze_args(
    args: argparse.Namespace,
    *,
    repository: RepositoryRef,
    paths: _RepoRunPaths,
    output_dir: str,
) -> argparse.Namespace:
    return argparse.Namespace(
        repo=repository.slug,
        owner="",
        month=None,
        start_date=args.start_date,
        end_date=args.end_date,
        timezone=args.timezone,
        output=paths.detail_path,
        summary_output=paths.summary_path,
        no_summary=False,
        merged_only=args.merged_only,
        output_dir=output_dir,
        from_cache=None,
        workers=args.workers,
        pr_resource_workers=args.pr_resource_workers,
    )


def _build_export_args(args: argparse.Namespace, paths: _RepoRunPaths) -> argparse.Namespace:
    return argparse.Namespace(
        summary=paths.summary_path,
        detail=None if args.summary_only else paths.detail_path,
        output=paths.xlsx_path,
        summary_only=args.summary_only,
    )


def _save_data_cache(data_dir: str, result: ReportResult, detail_path: str) -> None:
    raw_cache_path = raw_cache_path_from_detail(detail_path)
    try:
        saved = save_snapshot_from_raw_cache(data_dir, result.config, raw_cache_path)
        print(f"Data cache saved: {saved}", file=sys.stderr)
    except Exception as exc:
        print(f"Warning: failed to save data cache: {exc}", file=sys.stderr)


def _run_repository(
    args: argparse.Namespace,
    *,
    repository: RepositoryRef,
    config: ReportConfig,
    paths: _RepoRunPaths,
    output_dir: str,
    cache_allowed: bool,
    log_run: bool,
    cache_log_label: str | None = None,
) -> tuple[int, ReportResult | None]:
    cached_result = load_snapshot(args.data_dir, config) if cache_allowed else None
    if cached_result is not None:
        _write_outputs_from_result(
            cached_result,
            detail_path=paths.detail_path,
            summary_path=paths.summary_path,
            xlsx_path=paths.xlsx_path,
            summary_only=args.summary_only,
        )
        if log_run:
            label = cache_log_label or repository.slug
            print(f"Loaded data cache: {label}", file=sys.stderr)
        return 0, cached_result

    exit_code = analyze.run(_build_analyze_args(args, repository=repository, paths=paths, output_dir=output_dir))
    if exit_code != 0:
        return exit_code, None

    result = load_raw_cache(raw_cache_path_from_detail(paths.detail_path))
    _save_data_cache(args.data_dir, result, paths.detail_path)

    exit_code = export.run(_build_export_args(args, paths))
    if exit_code != 0:
        return exit_code, result

    if log_run:
        print(f"Run log: {run_log_path_from_detail(paths.detail_path)}", file=sys.stderr)
    return 0, result


def _run_multiple_repositories(
    args: argparse.Namespace,
    repositories,
    start_date,
    end_date,
    report_tz,
    output_dir: str,
) -> int:
    if args.output:
        print("Error: use --html-output instead of -o/--output for multi-repo runs", file=sys.stderr)
        return 2

    os.makedirs(output_dir, exist_ok=True)
    cache_allowed = args.cache_policy == "cache-first" and not args.refresh_all
    results: list[ReportResult] = []

    for repository in repositories:
        paths = _resolve_multi_repo_paths(args, repository, output_dir)
        config = _report_config(repository, start_date, end_date, report_tz, args.merged_only)
        exit_code, result = _run_repository(
            args,
            repository=repository,
            config=config,
            paths=paths,
            output_dir=output_dir,
            cache_allowed=cache_allowed,
            log_run=False,
        )
        if exit_code != 0:
            return exit_code
        if result is not None:
            results.append(result)

    if args.html:
        html_path = args.html_output or default_html_path(
            "all-repositories", args.start_date, args.end_date, output_dir=output_dir
        )
        export_html_report(results, html_path, bucket_granularity=args.bucket)
        print(f"Wrote {html_path}", file=sys.stderr)
    return 0


def _write_outputs_from_result(
    result: ReportResult,
    *,
    detail_path: str,
    summary_path: str,
    xlsx_path: str,
    summary_only: bool,
) -> None:
    os.makedirs(os.path.dirname(detail_path) or ".", exist_ok=True)
    with open(detail_path, "w", encoding="utf-8") as detail_handle:
        write_detail_tsv(result.rows, detail_handle, result.config)
    with open(summary_path, "w", encoding="utf-8") as summary_handle:
        write_summary_tsv(result.summaries, summary_handle, result.config)
    export_workbook(
        summary_path=Path(summary_path),
        detail_path=None if summary_only else Path(detail_path),
        output_path=Path(xlsx_path),
        include_detail=not summary_only,
    )
