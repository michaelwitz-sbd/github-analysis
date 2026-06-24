#!/usr/bin/env bash
# Run the three standard CEDT repos and build a combined Excel workbook.
#
# Usage:
#   ./scripts/run_cedt_trio.sh START END [OUTPUT_DIR] [COMBINED_XLSX_NAME]
# Example (June 1–23 2026 inclusive):
#   ./scripts/run_cedt_trio.sh 2026-06-01 2026-06-24
# Full month July 2026:
#   ./scripts/run_cedt_trio.sh 2026-07-01 2026-08-01 ~/Dev/github-analysis-results combined-2026-07.xlsx

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

START="${1:?start-date YYYY-MM-DD (inclusive)}"
END="${2:?end-date YYYY-MM-DD (exclusive)}"
OUT_DIR="${3:-${GITHUB_ANALYSIS_RESULTS:-$HOME/Dev/github-analysis-results}}"
COMBINED_NAME="${4:-combined-${START}_to_${END}.xlsx}"
mkdir -p "$OUT_DIR"

STEM_SUFFIX="${START}_to_${END}"

echo "==> uv sync"
uv sync --group excel

run_one() {
  local repo="$1"
  local workers="$2"
  local stem="${repo}-${STEM_SUFFIX}"
  echo "==> github-analysis run: $repo"
  uv run github-analysis run \
    --repo "$repo" \
    --start-date "$START" \
    --end-date "$END" \
    --merged-only \
    --workers "$workers" \
    --output-dir "$OUT_DIR" \
    -o "$OUT_DIR/${stem}.xlsx"
}

run_one global-services 4
run_one global-user-services 3
run_one polaris-turbo 4

COMBINED="$OUT_DIR/$COMBINED_NAME"
echo "==> combine person summaries -> $COMBINED"
uv run python scripts/combine_person_summaries.py \
  --input-dir "$OUT_DIR" \
  --stem-suffix "$STEM_SUFFIX" \
  -o "$COMBINED"

echo "Done. Outputs in $OUT_DIR"
