from __future__ import annotations

import os

from github_analysis.config import DEFAULT_OUTPUT_DIR


def safe_repo_filename(repo_name: str, start_date: str, end_date: str) -> str:
    safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in repo_name.strip())
    return f"{safe or 'repo'}_{start_date}_to_{end_date}.tsv"


def _output_dir(output_dir: str | None = None) -> str:
    return os.path.expanduser(output_dir or DEFAULT_OUTPUT_DIR)


def default_detail_path(
    repo_name: str,
    start_date: str,
    end_date: str,
    *,
    output_dir: str | None = None,
) -> str:
    return os.path.join(
        _output_dir(output_dir),
        safe_repo_filename(repo_name, start_date, end_date),
    )


def default_summary_path(
    repo_name: str,
    start_date: str,
    end_date: str,
    *,
    output_dir: str | None = None,
) -> str:
    stem = safe_repo_filename(repo_name, start_date, end_date).removesuffix(".tsv")
    return os.path.join(_output_dir(output_dir), f"{stem}_team_summary.tsv")


def default_xlsx_path(
    repo_name: str,
    start_date: str,
    end_date: str,
    *,
    output_dir: str | None = None,
) -> str:
    stem = safe_repo_filename(repo_name, start_date, end_date).removesuffix(".tsv")
    return os.path.join(_output_dir(output_dir), f"{stem}.xlsx")


def summary_path_from_detail(detail_path: str) -> str:
    if detail_path.endswith(".tsv"):
        return detail_path[:-4] + "_team_summary.tsv"
    return detail_path + "_team_summary.tsv"


def xlsx_path_from_detail(detail_path: str) -> str:
    if detail_path.endswith(".tsv"):
        return detail_path[:-4] + ".xlsx"
    return detail_path + ".xlsx"
