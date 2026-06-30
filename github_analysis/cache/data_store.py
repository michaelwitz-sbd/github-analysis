from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from github_analysis.cache.raw_store import load_raw_payload
from github_analysis.models import ReportConfig, ReportResult

SCHEMA_VERSION = 1


def _safe_repo_slug(owner: str, name: str) -> str:
    safe_owner = "".join(c if c.isalnum() or c in "._-" else "_" for c in owner)
    safe_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in name)
    return f"{safe_owner}__{safe_name}"


def snapshot_path(data_dir: str | Path, config: ReportConfig) -> Path:
    """Return the deterministic local data-cache path for a report window."""
    repo = config.repository
    filename = (
        f"{_safe_repo_slug(repo.owner, repo.name)}__"
        f"{config.start_date.isoformat()}_to_{config.end_date.isoformat()}.json"
    )
    return Path(data_dir).expanduser() / "raw" / filename


def _load_compatible_snapshot(path: Path, config: ReportConfig) -> ReportResult | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if payload.get("schema_version") != SCHEMA_VERSION:
        return None
    if payload.get("repository") != config.repository.slug:
        return None
    if payload.get("start_date") != config.start_date.isoformat():
        return None
    if payload.get("end_date") != config.end_date.isoformat():
        return None
    if payload.get("report_timezone") != config.report_tz.key:
        return None

    raw_payload = payload.get("result")
    if not isinstance(raw_payload, dict):
        return None
    return load_raw_payload(raw_payload)


def load_snapshot(data_dir: str | Path, config: ReportConfig) -> ReportResult | None:
    """Load a compatible cached report result from any data/raw snapshot."""
    root = Path(data_dir).expanduser() / "raw"
    preferred = snapshot_path(data_dir, config)
    candidates = [preferred] if preferred.is_file() else []
    if root.is_dir():
        candidates.extend(
            path
            for path in sorted(root.rglob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
            if path != preferred
        )

    for path in candidates:
        result = _load_compatible_snapshot(path, config)
        if result is not None:
            return result
    return None


def save_snapshot_from_raw_cache(
    data_dir: str | Path,
    config: ReportConfig,
    raw_cache_path: str | Path,
) -> Path:
    """Wrap an existing *_raw.json cache file in the data-cache format."""
    raw_path = Path(raw_cache_path).expanduser()
    raw_payload: dict[str, Any] = json.loads(raw_path.read_text(encoding="utf-8"))
    return save_snapshot_payload(data_dir, config, raw_payload)


def _load_snapshot_wrapper(path: Path, config: ReportConfig) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if payload.get("schema_version") != SCHEMA_VERSION:
        return None
    if payload.get("repository") != config.repository.slug:
        return None
    if payload.get("start_date") != config.start_date.isoformat():
        return None
    if payload.get("end_date") != config.end_date.isoformat():
        return None
    if payload.get("report_timezone") != config.report_tz.key:
        return None
    return payload


def load_snapshot_payload(
    data_dir: str | Path,
    config: ReportConfig,
) -> tuple[dict[str, Any], dict[str, Any]] | tuple[None, None]:
    """Return the wrapper and inner raw payload for a compatible data snapshot."""
    root = Path(data_dir).expanduser() / "raw"
    preferred = snapshot_path(data_dir, config)
    candidates = [preferred] if preferred.is_file() else []
    if root.is_dir():
        candidates.extend(
            path
            for path in sorted(root.rglob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
            if path != preferred
        )

    for path in candidates:
        wrapper = _load_snapshot_wrapper(path, config)
        if wrapper is None:
            continue
        raw_payload = wrapper.get("result")
        if isinstance(raw_payload, dict):
            return wrapper, raw_payload
    return None, None


def save_snapshot_payload(
    data_dir: str | Path,
    config: ReportConfig,
    raw_payload: dict[str, Any],
    *,
    source: str = "github",
) -> Path:
    """Write or overwrite a data-cache snapshot from a raw result payload."""
    target = snapshot_path(data_dir, config)
    target.parent.mkdir(parents=True, exist_ok=True)
    wrapper = {
        "schema_version": SCHEMA_VERSION,
        "source": source,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "repository": config.repository.slug,
        "start_date": config.start_date.isoformat(),
        "end_date": config.end_date.isoformat(),
        "report_timezone": config.report_tz.key,
        "result": raw_payload,
    }
    target.write_text(json.dumps(wrapper, indent=2), encoding="utf-8")
    return target
