from __future__ import annotations

from pathlib import Path
from zoneinfo import ZoneInfo

# Calendar dates for reports are interpreted in this timezone (DST-aware).
REPORT_TZ = ZoneInfo("America/New_York")

# Used when --repo is a short name without owner.
DEFAULT_GITHUB_OWNER = "Customer-Engagement-Digital-Technology"

# Default output directory for generated reports.
DEFAULT_OUTPUT_DIR = str(Path.home() / "Documents")

# GitHub API client settings
GH_API_TIMEOUT_SEC = 90
GH_API_RETRIES = 4
GH_API_RETRY_BASE_SEC = 2
API_LIST_PAGES_MAX = 100  # × 100 items/page
SEARCH_MAX_PAGES = 20
