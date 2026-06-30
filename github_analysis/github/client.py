from __future__ import annotations

import json
import subprocess
from threading import BoundedSemaphore, Lock
from time import monotonic, sleep
from typing import Any, Optional

from github_analysis.config import (
    GH_API_MAX_IN_FLIGHT,
    GH_API_MIN_INTERVAL_SEC,
    GH_API_RETRIES,
    GH_API_RETRY_BASE_SEC,
    GH_API_TIMEOUT_SEC,
)


def _transient_gh_failure(message: str) -> bool:
    lowered = message.lower()
    return any(
        token in lowered
        for token in (
            "connection reset",
            "connection refused",
            "broken pipe",
            "eof",
            "timeout",
            "temporarily unavailable",
            "503",
            "502",
            "504",
            "429",
            "api rate limit exceeded",
            "secondary rate limit",
            "abuse detection",
            "tls handshake",
            "i/o timeout",
        )
    )


_GH_API_SEMAPHORE = BoundedSemaphore(GH_API_MAX_IN_FLIGHT)
_GH_API_RATE_LOCK = Lock()
_GH_API_NEXT_START = 0.0


def _wait_for_rate_slot() -> None:
    global _GH_API_NEXT_START
    if GH_API_MIN_INTERVAL_SEC <= 0:
        return
    with _GH_API_RATE_LOCK:
        now = monotonic()
        wait = max(0.0, _GH_API_NEXT_START - now)
        _GH_API_NEXT_START = max(now, _GH_API_NEXT_START) + GH_API_MIN_INTERVAL_SEC
    if wait:
        sleep(wait)


class GhClient:
    """Thin wrapper around `gh api` with retries for transient failures."""

    def get(self, path: str, query: Optional[dict[str, str]] = None) -> Any:
        if path.startswith("https://api.github.com"):
            path = path[len("https://api.github.com") :]
        elif path.startswith("http://") or path.startswith("https://"):
            raise ValueError(f"unsupported URL for gh api: {path!r}")
        if not path.startswith("/"):
            path = "/" + path

        args = ["gh", "api", "-X", "GET", path]
        if query:
            for key, value in query.items():
                args.extend(["-f", f"{key}={value}"])

        last_error: Optional[BaseException] = None
        for attempt in range(1, GH_API_RETRIES + 1):
            try:
                _wait_for_rate_slot()
                with _GH_API_SEMAPHORE:
                    proc = subprocess.run(
                        args,
                        capture_output=True,
                        text=True,
                        timeout=GH_API_TIMEOUT_SEC,
                    )
            except subprocess.TimeoutExpired as exc:
                last_error = exc
                if attempt < GH_API_RETRIES and _transient_gh_failure(str(exc)):
                    sleep(GH_API_RETRY_BASE_SEC * attempt)
                    continue
                raise RuntimeError(f"gh api timeout: {path}\n{exc}") from exc

            err_text = (proc.stderr or proc.stdout or "").strip()
            if proc.returncode == 0:
                return json.loads(proc.stdout) if proc.stdout.strip() else None

            last_error = RuntimeError(
                f"gh api failed: {path}\n{err_text or proc.stderr or proc.stdout}"
            )
            if attempt < GH_API_RETRIES and _transient_gh_failure(err_text):
                sleep(GH_API_RETRY_BASE_SEC * attempt)
                continue
            raise last_error

    def get_list(self, path: str, *, per_page: int = 100) -> list[dict[str, Any]]:
        separator = "&" if "?" in path else "?"
        data = self.get(f"{path}{separator}per_page={per_page}")
        if not data:
            return []
        if not isinstance(data, list):
            raise RuntimeError(f"expected JSON array from {path!r}")
        return data

    def paginate_list(
        self,
        path: str,
        *,
        per_page: int = 100,
        max_pages: int,
    ) -> tuple[list[dict[str, Any]], bool]:
        items: list[dict[str, Any]] = []
        truncated = False
        for page in range(1, max_pages + 1):
            separator = "&" if "?" in path else "?"
            chunk = self.get(f"{path}{separator}per_page={per_page}&page={page}")
            if not chunk or not isinstance(chunk, list):
                break
            items.extend(chunk)
            if len(chunk) < per_page:
                break
            if page == max_pages:
                truncated = True
                break
        return items, truncated

    def search_issues(
        self, query: str, *, max_pages: int
    ) -> tuple[list[dict[str, Any]], bool]:
        """Return matching issues and whether results hit the GitHub search cap."""
        items: list[dict[str, Any]] = []
        truncated = False
        total_count = 0
        for page in range(1, max_pages + 1):
            data = self.get(
                "/search/issues",
                {"q": query, "per_page": "100", "page": str(page)},
            )
            if not data:
                break
            total_count = int(data.get("total_count") or 0)
            if data.get("incomplete_results"):
                truncated = True
            batch = data.get("items") or []
            items.extend(batch)
            if len(batch) < 100:
                break
            if page == max_pages:
                truncated = True
        if total_count > len(items):
            truncated = True
        return items, truncated
