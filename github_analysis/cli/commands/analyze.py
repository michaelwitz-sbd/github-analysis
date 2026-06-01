from __future__ import annotations

import argparse
import os
import sys

from github_analysis.config import DEFAULT_GITHUB_OWNER, DEFAULT_OUTPUT_DIR, REPORT_TZ
from github_analysis.export.paths import (
    default_detail_path,
    default_summary_path,
    summary_path_from_detail,
)
from github_analysis.export.tsv import write_detail_tsv, write_summary_tsv
from github_analysis.models import ReportConfig
from github_analysis.pipeline.runner import run_report
from github_analysis.repo import resolve_repository
from github_analysis.time_utils import parse_calendar_date


def register(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser(
        "analyze",
        help="Fetch GitHub data and write TSV reports",
        description=(
            "Analyze pull-request activity for one repository and write tab-separated reports. "
            "Produces a per-person team summary and optional per-PR detail file."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=_examples(),
    )
    _add_repo_args(parser)
    _add_date_args(parser)
    parser.add_argument(
        "-o",
        "--output",
        metavar="PATH",
        help=f"Detail TSV path. Default: {DEFAULT_OUTPUT_DIR}/{{repo}}_{{start}}_to_{{end}}.tsv. Use - for stdout.",
    )
    parser.add_argument(
        "--summary-output",
        metavar="PATH",
        help="Team summary TSV path. Default: detail path with _team_summary suffix.",
    )
    parser.add_argument(
        "--no-summary",
        action="store_true",
        help="Skip the per-person team summary file",
    )
    parser.add_argument(
        "--merged-only",
        action="store_true",
        help="Include only PRs merged during the date window (exclude opened-but-not-merged)",
    )
    parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        metavar="DIR",
        help=f"Directory for report files (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.set_defaults(handler=run)


def _add_repo_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--repo",
        required=True,
        help="Repository: HTTPS/SSH URL, owner/name, or short name",
    )
    parser.add_argument(
        "--owner",
        default="",
        help=f"Org/user when --repo is a short name only (default: {DEFAULT_GITHUB_OWNER!r})",
    )


def _add_date_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--start-date",
        required=True,
        metavar="YYYY-MM-DD",
        help=f"First calendar day included (timezone: {REPORT_TZ.key})",
    )
    parser.add_argument(
        "--end-date",
        required=True,
        metavar="YYYY-MM-DD",
        help=f"First calendar day excluded — e.g. 2026-06-01 for all of May ({REPORT_TZ.key})",
    )


def _examples() -> str:
    return (
        "Examples:\n"
        "  github-analysis analyze --repo global-services --start-date 2026-05-01 --end-date 2026-06-01\n"
        "  github-analysis analyze --repo global-services --start-date 2026-05-01 --end-date 2026-06-01 --merged-only\n"
        "  github-analysis analyze --repo org/repo --start-date 2026-05-01 --end-date 2026-06-01 -o -  # stdout"
    )


def run(args: argparse.Namespace) -> int:
    try:
        repository = resolve_repository(args.repo, args.owner)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    start_date = parse_calendar_date(args.start_date)
    end_date = parse_calendar_date(args.end_date)
    if end_date <= start_date:
        print("Error: --end-date must be after --start-date (end is exclusive)", file=sys.stderr)
        return 2

    config = ReportConfig(
        repository=repository,
        start_date=start_date,
        end_date=end_date,
        report_tz=REPORT_TZ,
        merged_only=args.merged_only,
        include_summary=not args.no_summary,
    )
    result = run_report(config)

    output_dir = os.path.expanduser(args.output_dir)
    os.makedirs(output_dir, exist_ok=True)

    if args.output is None:
        detail_path = default_detail_path(
            repository.name, args.start_date, args.end_date, output_dir=output_dir
        )
        close_output = True
        output_handle = open(detail_path, "w", encoding="utf-8")
        print(f"Writing {detail_path}", file=sys.stderr)
    elif args.output == "-":
        close_output = False
        output_handle = sys.stdout
    else:
        detail_path = args.output
        close_output = True
        output_handle = open(detail_path, "w", encoding="utf-8")
        print(f"Writing {detail_path}", file=sys.stderr)

    try:
        write_detail_tsv(result.rows, output_handle, config)
    finally:
        if close_output:
            output_handle.close()

    if args.no_summary or args.output == "-":
        if args.output == "-" and not args.no_summary:
            print(
                "Note: team summary is not written when detail output is stdout (-o -).",
                file=sys.stderr,
            )
        return 0

    if args.summary_output:
        summary_path = args.summary_output
    elif args.output is None:
        summary_path = default_summary_path(
            repository.name,
            args.start_date,
            args.end_date,
            output_dir=output_dir,
        )
    else:
        summary_path = summary_path_from_detail(args.output)

    print(f"Writing {summary_path}", file=sys.stderr)
    with open(summary_path, "w", encoding="utf-8") as summary_handle:
        write_summary_tsv(result.summaries, summary_handle, config)
    return 0
