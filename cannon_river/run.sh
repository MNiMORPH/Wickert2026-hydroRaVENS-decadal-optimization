#!/bin/bash
# Usage: bash run.sh [--overwrite] <decade-dir> [description]
# e.g.:  bash run.sh decades/1911-1920
#        bash run.sh --overwrite decades/1911-1920 rerun
#
# Run from cannon_river/. Passes the decade's params.yml by path so Dakota
# copies it into each evaluation directory as params.yml. Outputs are archived
# into <decade-dir>/runs/<timestamp>_<desc>/.
#
# By default the script aborts if ephemeral outputs from a prior run still
# exist (dakota.dat, dakota.out, out/, etc.). Use --overwrite to delete them first.
# --overwrite is necessary when a prior run produced more evaluations than the
# current one would, leaving stale out/run.*/ subdirectories.

set -euo pipefail

# --- argument parsing ---
FORCE=false
POSITIONAL=()
for arg in "$@"; do
    case "$arg" in
        --overwrite) FORCE=true ;;
        *)       POSITIONAL+=("$arg") ;;
    esac
done
set -- "${POSITIONAL[@]+"${POSITIONAL[@]}"}"

DECADE_DIR="${1:?Usage: bash run.sh [--overwrite] <decade-dir>  e.g. decades/1911-1920}"
DESC="${2:-full}"
DECADE_NAME=$(basename "$DECADE_DIR")
TIMESTAMP=$(date +%Y-%m-%d_%H%M%S)
RUN_NAME="${TIMESTAMP}_${DESC}"

DAKOTA=/home/awickert/anaconda3/envs/dakota-env/bin/dakota
PYTHON=/home/awickert/anaconda3/envs/dakota-env/bin/python

PARAMS="${DECADE_DIR}/params.yml"

# --- check for leftover outputs ---
EXISTING=()
for item in dakota.dat dakota.out dakota.rst fort.13 out best_fit.png; do
    [[ -e "$item" ]] && EXISTING+=("$item")
done
# glob LHS files separately to avoid unmatched-glob errors
for item in LHS_*.out; do
    [[ -e "$item" ]] && EXISTING+=("$item")
done

if [[ ${#EXISTING[@]} -gt 0 ]]; then
    if $FORCE; then
        echo "Warning: removing prior outputs: ${EXISTING[*]}"
        rm -rf out dakota.dat dakota.out dakota.rst fort.13 LHS_*.out best_fit.png
    else
        echo "Error: prior ephemeral outputs exist: ${EXISTING[*]}" >&2
        echo "Re-run with --overwrite to delete them and start fresh." >&2
        exit 1
    fi
fi

echo "=== Run: ${DECADE_NAME} / ${RUN_NAME} ==="

# Regenerate dakota.in from this decade's params.yml
$PYTHON generate_dakota_in.py --params "$PARAMS"

# Optimise
$DAKOTA -i dakota.in -o dakota.out

# Save figure
if $PYTHON plot_best.py --params "$PARAMS" --save best_fit.png --no-show; then
    echo "Best-fit plot saved."
else
    echo "Warning: plot_best.py failed; archiving without plot." >&2
fi

# Archive into the decade directory
bash archive_run.sh "$DECADE_DIR" "$RUN_NAME"

# Clean up ephemeral outputs so the next run.sh call starts clean
rm -rf out dakota.dat dakota.out dakota.rst fort.13 LHS_*.out best_fit.png

echo "=== Archived to ${DECADE_DIR}/runs/${RUN_NAME} ==="
