#!/bin/bash
# Run all decades sequentially, then write summary.csv.
#
# Usage (from cannon_river/):
#   bash run_all_decades.sh
#
# Each decade's results are archived to decades/<label>/runs/ as they complete.
# Ephemeral Dakota files (dakota.dat, out/, etc.) are overwritten each run and
# are not retained after archiving -- decades must run sequentially to avoid
# conflicts on these shared files.

set -euo pipefail

PYTHON=/home/awickert/anaconda3/envs/dakota-env/bin/python

for decade_dir in $(ls -d decades/*/); do
    bash run.sh "$decade_dir"
done

echo "=== All decades complete. Writing summary.csv ==="
$PYTHON summarize.py
echo "=== Done ==="
