#!/bin/bash
# Usage: bash run.sh <decade-dir> [description]
# e.g.:  bash run.sh decades/1911-1920
#        bash run.sh decades/1911-1920 rerun
#
# Run from cannon_river/.  Creates the timestamped run directory upfront,
# copies all necessary files into it, and works there so that multiple
# decades can run simultaneously without sharing any state.

set -euo pipefail

DECADE_DIR="${1:?Usage: bash run.sh <decade-dir>  e.g. decades/1911-1920}"
DESC="${2:-full}"
DECADE_NAME=$(basename "$DECADE_DIR")
TIMESTAMP=$(date +%Y-%m-%d_%H%M%S)
RUN_NAME="${TIMESTAMP}_${DESC}"

DAKOTA=${DAKOTA:-dakota}
PYTHON=${PYTHON:-python}

PARAMS="${DECADE_DIR}/params.yml"
RUN_DIR="${DECADE_DIR}/runs/${RUN_NAME}"

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

echo "=== Run: ${DECADE_NAME} / ${RUN_NAME} ==="

# --- create run directory and populate it ---
mkdir -p "$RUN_DIR"

cp "$PARAMS"             "$RUN_DIR/params.yml"
cp driver.py             "$RUN_DIR/"
cp run_driver.sh         "$RUN_DIR/"
cp generate_dakota_in.py "$RUN_DIR/"
cp plot_best.py          "$RUN_DIR/"

# Resolve and copy the model config template so the archive is self-contained
CONFIG=$($PYTHON -c "
import yaml
with open('$PARAMS') as f:
    cfg = yaml.safe_load(f)
print(cfg['driver']['config_template'])
")
cp "$CONFIG" "$RUN_DIR/"

# --- work inside the run directory from here on ---
cd "$RUN_DIR"

# Regenerate dakota.in from this decade's params.yml
$PYTHON generate_dakota_in.py --params params.yml

# Pre-flight: initialise the model before spending 500+ evaluations on a bad config.
$PYTHON - params.yml << 'PYEOF' || { echo "ERROR: Pre-flight config check failed. Aborting." >&2; exit 1; }
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

# Abort if every evaluation returned the penalty score.
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
          "model or config error. Aborting.", file=sys.stderr)
    sys.exit(1)
' || exit 1

# Rename outputs to archive-friendly names
mv dakota.dat evaluations.dat
mv dakota.out dakota_log.txt

# Save figure
if $PYTHON plot_best.py --params params.yml --save best_fit.png --no-show; then
    echo "Best-fit plot saved."
else
    echo "Warning: plot_best.py failed; continuing without plot." >&2
fi

echo "=== Completed: ${RUN_DIR} ==="
