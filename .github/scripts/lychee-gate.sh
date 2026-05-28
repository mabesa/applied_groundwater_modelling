#!/usr/bin/env bash
# Parse the lychee markdown summary and fail the job only on real broken
# links (4xx/5xx). Timeouts are reported as warnings, not failures, because
# scholarly and government sites frequently throttle CI runner IPs even
# when the URLs are valid in a browser.
#
# Usage:  lychee-gate.sh <path-to-lychee-report.md>

set -euo pipefail

report="${1:?usage: $0 <report.md>}"

if [[ ! -f "$report" ]]; then
  echo "::error::lychee report not found at $report"
  exit 1
fi

# Extract counts from the lychee summary table. The relevant rows look like:
#   | 🚫 Errors      | 0     |
#   | ⏳ Timeouts    | 1     |
errors=$(grep -E '🚫 Errors' "$report" | grep -oE '[0-9]+' | head -1 || true)
timeouts=$(grep -E '⏳ Timeouts' "$report" | grep -oE '[0-9]+' | head -1 || true)
errors="${errors:-0}"
timeouts="${timeouts:-0}"

echo "Lychee summary — Errors: ${errors}, Timeouts: ${timeouts}"

if [[ "$errors" -gt 0 ]]; then
  echo "::error::${errors} real broken link(s) found — see job summary"
  exit 1
fi

if [[ "$timeouts" -gt 0 ]]; then
  echo "::warning::${timeouts} timeout(s) detected — treated as transient, not failed. See job summary."
fi

exit 0
