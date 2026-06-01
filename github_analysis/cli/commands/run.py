from __future__ import annotations

import argparse
import os
import sys

from github_analysis.cli.commands import analyze, export
from github_analysis.config import DEFAULT_OUTPUT_DIR
from github_analysis.export.paths import (
    default_detail_path,
    default_summary_path,
    default_xlsx_path,
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
            "  github-analysis run --repo global-services --start-date 2026-05-01 --end-date 2026-06-01\n"
            "  github-analysis run --repo global-services --start-date 2026-05-01 --end-date 2026-06-01 --merged-only\n"
            f"  github-analysis run --repo global-services --start-date 2026-05-01 --end-date 2026-06-01 --output-dir ~/Documents"
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
        help="Excel workbook contains only the Team Summary sheet",
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        metavar="DIR",
        help=f"Directory for all outputs (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.set_defaults(handler=run)


def run(args: argparse.Namespace) -> int:
    try:
        repository = resolve_repository(args.repo, args.owner)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    output_dir = os.path.expanduser(args.output_dir)
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
    return export.run(export_args)
