from __future__ import annotations

import argparse
import os
import sys

from github_analysis.cli.commands import analyze, export
from github_analysis.config import DEFAULT_FETCH_WORKERS, DEFAULT_OUTPUT_DIR
from github_analysis.export.paths import (
    default_detail_path,
    default_summary_path,
    default_xlsx_path,
    paths_from_excel_output,
    run_log_path_from_detail,
)
from github_analysis.repo import resolve_repository


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "run",
        help="Analyze and export Excel in one step",
        description=(
            "Convenience command: runs `analyze` then `export` with default output paths. "
            "Best for monthly manager reports."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  # May 2026 merged PRs only (recommended for monthly reports):\n"
            "  github-analysis run --repo global-services --start-date 2026-05-01 --end-date 2026-06-01 --merged-only\n"
            "  github-analysis run --repo global-services --start-date 2026-05-01 --end-date 2026-06-01 --merged-only --workers 4 \\\n"
            "    -o ~/Documents/global-services-may-2026.xlsx"
        ),
    )
    analyze._add_repo_args(parser)
    analyze._add_date_args(parser)
    parser.add_argument(
        "--merged-only",
        action="store_true",
        help="Include only PRs merged during the date window",
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
            "Primary output file path (.xlsx Excel workbook). "
            "Also writes sibling TSV files: {name}_person_summary.tsv and {name}.tsv"
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
    parser.set_defaults(handler=run)


def run(args: argparse.Namespace) -> int:
    try:
        repository = resolve_repository(args.repo, args.owner)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    output_dir = os.path.expanduser(args.output_dir)

    if args.output:
        xlsx_path, summary_path, detail_path = paths_from_excel_output(args.output)
        os.makedirs(os.path.dirname(xlsx_path) or ".", exist_ok=True)
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

    analyze_args = argparse.Namespace(
        repo=args.repo,
        owner=args.owner,
        start_date=args.start_date,
        end_date=args.end_date,
        output=detail_path,
        summary_output=summary_path,
        no_summary=False,
        merged_only=args.merged_only,
        output_dir=output_dir,
        from_cache=None,
        workers=args.workers,
    )
    exit_code = analyze.run(analyze_args)
    if exit_code != 0:
        return exit_code

    export_args = argparse.Namespace(
        summary=summary_path,
        detail=None if args.summary_only else detail_path,
        output=xlsx_path,
        summary_only=args.summary_only,
    )
    exit_code = export.run(export_args)
    if exit_code == 0:
        log_hint = run_log_path_from_detail(detail_path)
        print(f"Run log: {log_hint}", file=sys.stderr)
    return exit_code
