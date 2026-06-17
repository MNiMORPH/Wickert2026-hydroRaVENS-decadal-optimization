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

DAKOTA=${DAKOTA:-dakota}
PYTHON=${PYTHON:-python}

PARAMS="${DECADE_DIR}/params.yml"

# --- skip decades with no discharge observations in their window ---
N_OBS=$($PYTHON -c "
import yaml, pandas as pd, sys
try:
    with open('$PARAMS') as f:
        cfg = yaml.safe_load(f)
    drv = cfg['driver']
    with open(drv['config_template']) as f:
        mcfg = yaml.safe_load(f)
    df = pd.read_csv(mcfg['timeseries']['datafile'], parse_dates=['Date'])
    q = 'Discharge [m^3/s]'
    t0 = pd.Timestamp(drv.get('decade_start', str(df['Date'].min())))
    t1 = pd.Timestamp(drv.get('decade_end', str(df['Date'].max())))
    n = int(df[(df['Date'] >= t0) & (df['Date'] <= t1) & df[q].notna()].shape[0])
    print(n)
except Exception:
    print(0)
" 2>/dev/null || echo 0)
if [[ "${N_OBS:-0}" -eq 0 ]]; then
    echo "=== Skipping ${DECADE_NAME}: no discharge observations in decade window ==="
    exit 0
fi

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

# Pre-flight: initialise the model with the config template before spending
# 500+ evaluations — catches config errors (missing keys, bad paths) immediately.
$PYTHON - "$PARAMS" << 'PYEOF' || { echo "ERROR: Pre-flight config check failed. Aborting." >&2; exit 1; }
import yaml, sys
from mnished import Buckets
with open(sys.argv[1]) as f:
    p = yaml.safe_load(f)
cfg = p["driver"]["config_template"]
ewb = p["driver"].get("enforce_water_balance", None)
b = Buckets()
b.initialize(cfg, enforce_water_balance=ewb)
PYEOF

# Optimise
$DAKOTA -i dakota.in -o dakota.out

# Abort before archiving if every evaluation returned the penalty score —
# indicates a model or config error rather than a genuine calibration result.
$PYTHON -c '
import sys
PENALTY = 10.0
with open("dakota.dat") as f:
    lines = f.readlines()
hdr = next((l.lstrip("%").split() for l in lines if l.startswith("%")), [])
if "neg_kge" not in hdr:
    sys.exit(0)
col = hdr.index("neg_kge")
scores = [float(l.split()[col]) for l in lines
          if not l.startswith("%") and l.strip()]
if scores and all(abs(s - PENALTY) < 1e-9 for s in scores):
    n = len(scores)
    print(f"ERROR: all {n} evaluations returned PENALTY={PENALTY}; "
          "model or config error. Aborting without archiving.", file=sys.stderr)
    sys.exit(1)
' || exit 1

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
