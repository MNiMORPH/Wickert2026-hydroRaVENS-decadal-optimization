#!/bin/bash
# Sequential transient calibration: runs each full-coverage decade in
# chronological order, chaining end-of-decade reservoir states as ICs
# for the next decade.
#
# Prerequisites:
#   1. Run make_transient_params.py (or make_transient_params_v5.0.py) to
#      create params_transient[_vX.Y].yml in each decade directory.
#   2. Backbone fixed values must be set in those params files already.
#
# Usage: bash run_transient.sh [description] [driver_file] [params_suffix] [--prev-states PATH]
# e.g.:  bash run_transient.sh transient_v1
#        bash run_transient.sh transient_v5.0 driver_transient_v5.0.py _v5.0
#        bash run_transient.sh transient_v3 driver_transient.py "" --prev-states decades/1931-1940/runs/.../final_states.yml
#
# driver_file   : driver script to copy as driver.py (default: driver_transient.py)
# params_suffix : suffix appended to "params_transient" to form the params filename
#                 (default: ""; result is params_transient.yml)
#                 e.g. "_v5.0" → params_transient_v5.0.yml
# --prev-states PATH : pre-load end-states from a prior run and skip the first
#                      decade in DECADES (it was already calibrated externally).
#
# Run from cannon_river/

set -euo pipefail

DESC="${1:-transient}"
TIMESTAMP=$(date +%Y-%m-%d_%H%M%S)
DRIVER="${2:-driver_transient.py}"
PARAMS_SUFFIX="${3:-}"
PREV_STATES_ARG=""
SKIP_FIRST=false
shift 3 || shift $# || true
while [[ $# -gt 0 ]]; do
    case "$1" in
        --prev-states) PREV_STATES_ARG="$2"; SKIP_FIRST=true; shift 2 ;;
        *) shift ;;
    esac
done
CANNON_RIVER_DIR="$(pwd)"

DAKOTA=${DAKOTA:-/home/awickert/anaconda3/envs/dakota-env/bin/dakota}
PYTHON=${PYTHON:-/home/awickert/anaconda3/envs/dakota-env/bin/python}

# Chronological order of full-coverage decades.
DECADES=(
    "decades/1931-1940"
    "decades/1941-1950"
    "decades/1951-1960"
    "decades/1961-1970"
    "decades/1991-2000"
    "decades/2001-2010"
    "decades/2011-2020"
)

PREV_FINAL_STATES="${PREV_STATES_ARG}"  # path to final_states.yml from prior decade

FIRST_ITERATION=true
for DECADE_DIR in "${DECADES[@]}"; do
    # If an external prev-states was supplied, skip the first decade
    # (it was already calibrated and its end-states are in PREV_STATES_ARG).
    if $SKIP_FIRST && $FIRST_ITERATION; then
        FIRST_ITERATION=false
        echo "=== Skipping $(basename $DECADE_DIR): already calibrated (using provided prev-states) ==="
        continue
    fi
    FIRST_ITERATION=false
    DECADE_NAME=$(basename "$DECADE_DIR")
    PARAMS="${DECADE_DIR}/params_transient${PARAMS_SUFFIX}.yml"

    if [[ ! -f "$PARAMS" ]]; then
        echo "=== Skipping ${DECADE_NAME}: no params_transient${PARAMS_SUFFIX}.yml found ==="
        continue
    fi

    # Check discharge coverage
    N_OBS=$($PYTHON -c "
import yaml, pandas as pd
with open('$PARAMS') as f:
    cfg = yaml.safe_load(f)
drv = cfg['driver']
with open(drv['config_template']) as f:
    mcfg = yaml.safe_load(f)
df = pd.read_csv(mcfg['timeseries']['datafile'], parse_dates=['Date'])
q = 'Discharge [m^3/s]'
t0 = pd.Timestamp(drv['decade_start'])
t1 = pd.Timestamp(drv['decade_end'])
n = int(df[(df['Date'] >= t0) & (df['Date'] <= t1) & df[q].notna()].shape[0])
print(n)
" 2>/dev/null || echo 0)

    if [[ "${N_OBS:-0}" -lt 3000 ]]; then
        echo "=== Skipping ${DECADE_NAME}: only ${N_OBS} obs (need 3000) ==="
        continue
    fi

    RUN_NAME="${TIMESTAMP}_${DESC}"
    RUN_DIR="${DECADE_DIR}/runs/${RUN_NAME}"
    echo "=== Run: ${DECADE_NAME} / ${RUN_NAME} ==="

    # If we have end-states from the prior decade, inject them into this
    # decade's params_transient.yml before the run.
    if [[ -n "$PREV_FINAL_STATES" && -f "$PREV_FINAL_STATES" ]]; then
        $PYTHON - "$PARAMS" "$PREV_FINAL_STATES" << 'PYEOF'
import sys, yaml, math

params_path = sys.argv[1]
states_path = sys.argv[2]

with open(params_path) as f:
    cfg = yaml.safe_load(f)
with open(states_path) as f:
    states = yaml.safe_load(f)

res_order = cfg['driver'].get('reservoir_order', ['soil', 'intermediate', 'deep'])
params = cfg['parameters']

# Update reservoir H0 fixed values (log10 scale, floor at 0.01 mm)
for i, label in enumerate(res_order):
    key = f'log__H0_{label}'
    if key in params:
        h = max(states['reservoirs'][label], 0.01)
        params[key]['fixed']   = round(math.log10(h), 6)
        params[key]['initial'] = round(math.log10(h), 6)

# Update snowpack and FGI
if 'H0_snowpack' in params:
    params['H0_snowpack']['fixed']   = round(max(states.get('snowpack', 0.0), 0.0), 4)
    params['H0_snowpack']['initial'] = params['H0_snowpack']['fixed']
if 'H0_fgi' in params:
    params['H0_fgi']['fixed']   = round(max(states.get('fgi', 0.0), 0.0), 4)
    params['H0_fgi']['initial'] = params['H0_fgi']['fixed']

# Update H_deficit_carry
if 'H0_deficit_carry' in params:
    params['H0_deficit_carry']['fixed']   = round(states.get('H_deficit_carry', 0.0), 6)
    params['H0_deficit_carry']['initial'] = params['H0_deficit_carry']['fixed']

# Set spin_up_cycles=0 (chained run, no pre-decade spin-up)
cfg['driver']['spin_up_cycles'] = 0

with open(params_path, 'w') as f:
    yaml.dump(cfg, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
print(f"Updated {params_path} with chained ICs from {states_path}")
PYEOF
    fi

    # Create run directory and populate
    mkdir -p "$RUN_DIR"
    cp "$CANNON_RIVER_DIR/$DRIVER" "$RUN_DIR/driver.py"
    cp run_driver.sh        "$RUN_DIR/"
    cp generate_dakota_in.py "$RUN_DIR/"
    cp plot_best.py         "$RUN_DIR/"
    cp "$PARAMS"            "$RUN_DIR/params.yml"

    CONFIG=$($PYTHON -c "
import yaml
with open('$PARAMS') as f:
    cfg = yaml.safe_load(f)
print(cfg['driver']['config_template'])
")
    cp "$CONFIG" "$RUN_DIR/"

    cd "$RUN_DIR"
    $PYTHON generate_dakota_in.py --params params.yml

    # Pre-flight
    $PYTHON - params.yml << 'PYEOF' || { echo "ERROR: Pre-flight failed." >&2; cd "$CANNON_RIVER_DIR"; continue; }
import yaml, sys
from mnished import Buckets
with open(sys.argv[1]) as f:
    p = yaml.safe_load(f)
cfg = p["driver"]["config_template"]
ewb = p["driver"].get("enforce_water_balance", None)
b = Buckets()
b.initialize(cfg, enforce_water_balance=ewb)
PYEOF

    $DAKOTA -i dakota.in -o dakota.out

    # Check for all-penalty failure
    $PYTHON -c '
import sys
PENALTY = 10.0
with open("dakota.dat") as f:
    lines = f.readlines()
hdr = next((l.lstrip("%").split() for l in lines if l.startswith("%")), [])
if "neg_kge" not in hdr:
    sys.exit(0)
col = hdr.index("neg_kge")
scores = [float(l.split()[col]) for l in lines if not l.startswith("%") and l.strip()]
if scores and all(abs(s - PENALTY) < 1e-9 for s in scores):
    print(f"ERROR: all {len(scores)} evals returned PENALTY.", file=sys.stderr)
    sys.exit(1)
best = min(s for s in scores if abs(s - PENALTY) > 1e-9)
print(f"Best neg_kge={best:.6f}  (KGE={1-best:.4f})")
' || { cd "$CANNON_RIVER_DIR"; continue; }

    mv dakota.dat evaluations.dat
    mv dakota.out dakota_log.txt

    # Extract end-of-decade reservoir states for chaining
    if $PYTHON "$CANNON_RIVER_DIR/extract_end_state.py" .; then
        PREV_FINAL_STATES="$(pwd)/final_states.yml"
    else
        echo "Warning: extract_end_state.py failed for ${DECADE_NAME}; next decade uses analytical SS." >&2
        PREV_FINAL_STATES=""
    fi

    echo "=== Completed: ${RUN_DIR} ==="
    cd "$CANNON_RIVER_DIR"
done

echo "=== Transient calibration complete ==="
