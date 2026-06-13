#!/bin/bash
# Usage: bash run.sh <decade-dir> [description]
# e.g.:  bash run.sh decades/1911-1920
#        bash run.sh decades/1911-1920 rerun
#
# Run from cannon_river/. Passes the decade's params.yml by path so Dakota
# copies it into each evaluation directory as params.yml. Outputs are archived
# into <decade-dir>/runs/<timestamp>_<desc>/.

set -euo pipefail

DECADE_DIR="${1:?Usage: bash run.sh <decade-dir>  e.g. decades/1911-1920}"
DESC="${2:-full}"
DECADE_NAME=$(basename "$DECADE_DIR")
TIMESTAMP=$(date +%Y-%m-%d_%H%M%S)
RUN_NAME="${TIMESTAMP}_${DESC}"

DAKOTA=/home/awickert/anaconda3/envs/dakota-env/bin/dakota
PYTHON=/home/awickert/anaconda3/envs/dakota-env/bin/python

PARAMS="${DECADE_DIR}/params.yml"

echo "=== Run: ${DECADE_NAME} / ${RUN_NAME} ==="

# Regenerate dakota.in from this decade's params.yml
$PYTHON generate_dakota_in.py --params "$PARAMS"

# Clean previous ephemeral outputs
rm -rf out dakota.dat dakota.out dakota.rst fort.13 LHS_*.out

# Optimise
$DAKOTA -i dakota.in -o dakota.out

# Save figure without showing it so we can archive before blocking on display.
if $PYTHON plot_best.py --params "$PARAMS" --save best_fit.png --no-show; then
    echo "Best-fit plot saved."
else
    echo "Warning: plot_best.py failed; archiving without plot." >&2
fi

# Archive into the decade directory
bash archive_run.sh "$DECADE_DIR" "$RUN_NAME"

echo "=== Archived to ${DECADE_DIR}/runs/${RUN_NAME} ==="

[[ -f "${DECADE_DIR}/runs/${RUN_NAME}/best_fit.png" ]] && xdg-open "${DECADE_DIR}/runs/${RUN_NAME}/best_fit.png" &
