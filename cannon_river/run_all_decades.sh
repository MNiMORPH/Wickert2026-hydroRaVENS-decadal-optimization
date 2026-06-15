#!/bin/bash
# Run all decades sequentially, then write summary.csv.
#
# Usage (from cannon_river/):
#   bash run_all_decades.sh              # abort if prior outputs exist
#   bash run_all_decades.sh --overwrite  # delete prior outputs and rerun
#
# Each decade's results are archived to decades/<label>/runs/ as they complete.
# Decades must run sequentially: ephemeral Dakota files (dakota.dat, out/, etc.)
# are written to the shared cannon_river/ working directory.

set -euo pipefail

OVERWRITE=""
[[ "${1:-}" == "--overwrite" ]] && OVERWRITE="--overwrite"

PYTHON=${PYTHON:-python}

for decade_dir in $(ls -d decades/*/); do
    bash run.sh $OVERWRITE "$decade_dir"
done

echo "=== All decades complete. Writing summary.csv ==="
$PYTHON summarize.py
echo "=== Done ==="
