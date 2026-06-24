#!/usr/bin/env python3
"""Combine per-repo *_person_summary.tsv files into one Excel workbook."""

from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

# Allow running from repo root without install
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from github_analysis.export.xlsx import read_tsv_table, _autosize_columns  # noqa: E402

COUNT_COLUMNS = {
    "prs_merged",
    "prs_reviewed",
    "prs_approved",
    "prs_authored",
    "prs_open",
    "prs_closed_unmerged",
}
WEIGHT_AUTHORED = {"avg_files_added_per_pr", "avg_files_changed_per_pr"}
WEIGHT_MERGED = {
    "min_hours_pr_created_to_merged",
    "max_hours_pr_created_to_merged",
    "avg_hours_pr_created_to_merged",
}


def _parse_float(s: str) -> float | None:
    s = (s or "").strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _parse_int(s: str) -> int:
    s = (s or "").strip()
    if not s:
        return 0
    return int(s)


_DATE_WINDOW_SUFFIX = re.compile(r"[-_]\d{4}-\d{2}-\d{2}_to_\d{4}-\d{2}-\d{2}$")


def _repo_label_from_summary_path(path: Path) -> str:
    stem = path.name
    if stem.endswith("_person_summary.tsv"):
        label = stem[: -len("_person_summary.tsv")]
    else:
        label = path.stem
    label = _DATE_WINDOW_SUFFIX.sub("", label)
    return label


def _sheet_title(name: str) -> str:
    """Excel sheet names: max 31 chars, no : \\ / ? * [ ]"""
    title = re.sub(r"[:\\/?*\[\]]", "-", name)[:31]
    return title or "repo"


def _aggregate_totals(
    headers: list[str],
    repo_rows: list[tuple[str, list[list[str]]]],
) -> tuple[list[str], list[list[str]]]:
    """Roll up person-summary rows across repos — one row per user, same columns as source."""
    idx = {h: i for i, h in enumerate(headers)}
    by_user: dict[str, dict] = defaultdict(
        lambda: {
            "counts": defaultdict(int),
            "file_w": defaultdict(float),
            "file_n": defaultdict(float),
            "merge_w": defaultdict(float),
            "merge_n": defaultdict(float),
            "min_hours": {},
            "max_hours": {},
        }
    )

    for _repo, rows in repo_rows:
        for row in rows:
            user = row[idx["user"]]
            rec = by_user[user]
            for col in COUNT_COLUMNS:
                rec["counts"][col] += _parse_int(row[idx[col]])
            authored = _parse_int(row[idx["prs_authored"]])
            merged = _parse_int(row[idx["prs_merged"]])
            for col in WEIGHT_AUTHORED:
                val = _parse_float(row[idx[col]])
                if val is not None and authored > 0:
                    rec["file_w"][col] += val * authored
                    rec["file_n"][col] += authored
            for col in WEIGHT_MERGED:
                val = _parse_float(row[idx[col]])
                if col == "min_hours_pr_created_to_merged" and val is not None:
                    prev = rec["min_hours"].get(col)
                    rec["min_hours"][col] = val if prev is None else min(prev, val)
                elif col == "max_hours_pr_created_to_merged" and val is not None:
                    prev = rec["max_hours"].get(col)
                    rec["max_hours"][col] = val if prev is None else max(prev, val)
                elif col == "avg_hours_pr_created_to_merged" and val is not None and merged > 0:
                    rec["merge_w"][col] += val * merged
                    rec["merge_n"][col] += merged

    def _fmt_avg(w: float, n: float) -> str:
        if n <= 0:
            return ""
        return f"{w / n:.2f}"

    out: list[list[str]] = []
    for user in sorted(by_user.keys(), key=str.lower):
        rec = by_user[user]
        line = [""] * len(headers)
        line[idx["user"]] = user
        for col in COUNT_COLUMNS:
            line[idx[col]] = str(rec["counts"][col])
        for col in WEIGHT_AUTHORED:
            line[idx[col]] = _fmt_avg(rec["file_w"][col], rec["file_n"][col])
        line[idx["min_hours_pr_created_to_merged"]] = (
            f"{rec['min_hours']['min_hours_pr_created_to_merged']:.4f}"
            if "min_hours_pr_created_to_merged" in rec["min_hours"]
            else ""
        )
        line[idx["max_hours_pr_created_to_merged"]] = (
            f"{rec['max_hours']['max_hours_pr_created_to_merged']:.4f}"
            if "max_hours_pr_created_to_merged" in rec["max_hours"]
            else ""
        )
        line[idx["avg_hours_pr_created_to_merged"]] = _fmt_avg(
            rec["merge_w"]["avg_hours_pr_created_to_merged"],
            rec["merge_n"]["avg_hours_pr_created_to_merged"],
        )
        out.append(line)

    return headers, out


def combine_workbook(
    summary_paths: list[Path],
    output_path: Path,
    *,
    repo_order: list[str] | None = None,
) -> None:
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font
    except ImportError as exc:
        raise SystemExit("openpyxl required: uv sync --group excel") from exc

    if not summary_paths:
        raise SystemExit("no *_person_summary.tsv files found")

    labeled: list[tuple[str, Path]] = []
    for path in summary_paths:
        label = _repo_label_from_summary_path(path)
        labeled.append((label, path))

    if repo_order:
        order_map = {name: i for i, name in enumerate(repo_order)}
        labeled.sort(key=lambda t: (order_map.get(t[0], 999), t[0].lower()))
    else:
        labeled.sort(key=lambda t: t[0].lower())

    repo_rows: list[tuple[str, list[str], list[list[str]]]] = []
    headers: list[str] | None = None
    for label, path in labeled:
        h, rows = read_tsv_table(path)
        if headers is None:
            headers = h
        elif h != headers:
            raise SystemExit(f"header mismatch in {path}")
        repo_rows.append((label, h, rows))

    assert headers is not None
    totals_headers, totals_rows = _aggregate_totals(
        headers, [(label, rows) for label, _, rows in repo_rows]
    )

    workbook = Workbook()
    totals_ws = workbook.active
    totals_ws.title = "Totals"
    totals_ws.append(totals_headers)
    for row in totals_rows:
        totals_ws.append(row)
    for cell in totals_ws[1]:
        cell.font = Font(bold=True)
    _autosize_columns(totals_ws, totals_headers, totals_rows)

    for label, h, rows in repo_rows:
        ws = workbook.create_sheet(_sheet_title(label))
        ws.append(h)
        for row in rows:
            ws.append(row)
        for cell in ws[1]:
            cell.font = Font(bold=True)
        _autosize_columns(ws, h, rows)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(output_path)


def main() -> int:
    from github_analysis.config import OUTPUT_DIR_HELP, default_output_dir, resolve_output_dir

    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Output directory precedence: --output-dir → GITHUB_ANALYSIS_RESULTS → "
            f"built-in default ({default_output_dir()}).\n"
            "CLI --output-dir overrides the environment variable when both are set."
        ),
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        help="Directory containing *_person_summary.tsv files (default: --output-dir)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help=OUTPUT_DIR_HELP,
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Combined Excel output path (.xlsx). Required unless --output-dir and --combined-name are set",
    )
    parser.add_argument(
        "--combined-name",
        default="",
        help="Filename under --output-dir when -o is omitted (e.g. combined-2026-07.xlsx)",
    )
    parser.add_argument(
        "--repo-order",
        nargs="*",
        default=["global-services", "global-user-services", "polaris-turbo"],
        help="Sheet order after Totals (default: CEDT trio)",
    )
    parser.add_argument(
        "--stem-suffix",
        default="",
        help=(
            "Only include summaries whose filename contains this string "
            "(e.g. 2026-06-01_to_2026-06-23). Required when --input-dir holds "
            "multiple date windows."
        ),
    )
    args = parser.parse_args()

    out_dir = Path(resolve_output_dir(str(args.output_dir) if args.output_dir else None)).expanduser()
    input_dir = (args.input_dir or out_dir).expanduser()

    if args.output:
        output_path = args.output.expanduser()
    elif args.combined_name:
        output_path = out_dir / args.combined_name
    else:
        raise SystemExit("error: specify -o/--output or --output-dir with --combined-name")

    paths = sorted(input_dir.glob("*_person_summary.tsv"))
    if args.stem_suffix:
        paths = [p for p in paths if args.stem_suffix in p.name]
        if not paths:
            raise SystemExit(
                f"no *_person_summary.tsv matching stem-suffix {args.stem_suffix!r} in {input_dir}"
            )
    combine_workbook(paths, output_path, repo_order=args.repo_order)
    print(f"Wrote {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
