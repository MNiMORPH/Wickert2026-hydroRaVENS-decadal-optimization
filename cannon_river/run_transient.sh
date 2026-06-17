#!/bin/bash
# Sequential transient calibration: runs each full-coverage decade in
# chronological order, chaining end-of-decade reservoir states as ICs
# for the next decade.
#
# Prerequisites:
#   1. Run make_transient_params.py to create params_transient.yml in each
#      decade directory (optionally with --backbone <run_dir>/evaluations.dat).
#   2. Backbone fixed values must be set in params_transient.yml already.
#
# Usage: bash run_transient.sh [description]
# e.g.:  bash run_transient.sh transient_v1
#
# Run from cannon_river/

set -euo pipefail

DESC="${1:-transient}"
TIMESTAMP=$(date +%Y-%m-%d_%H%M%S)

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

PREV_FINAL_STATES=""  # path to final_states.yml from prior decade

for DECADE_DIR in "${DECADES[@]}"; do
    DECADE_NAME=$(basename "$DECADE_DIR")
    PARAMS="${DECADE_DIR}/params_transient.yml"

    if [[ ! -f "$PARAMS" ]]; then
        echo "=== Skipping ${DECADE_NAME}: no params_transient.yml found ==="
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

# Set spin_up_cycles=0 (chained run, no pre-decade spin-up)
cfg['driver']['spin_up_cycles'] = 0

with open(params_path, 'w') as f:
    yaml.dump(cfg, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
print(f"Updated {params_path} with chained ICs from {states_path}")
PYEOF
    fi

    # Create run directory and populate
    mkdir -p "$RUN_DIR"
    cp driver_transient.py  "$RUN_DIR/driver.py"
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
    $PYTHON - params.yml << 'PYEOF' || { echo "ERROR: Pre-flight failed." >&2; cd - > /dev/null; continue; }
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
' || { cd - > /dev/null; continue; }

    mv dakota.dat evaluations.dat
    mv dakota.out dakota_log.txt

    # Extract end-of-decade reservoir states for chaining
    if $PYTHON "$(cd - > /dev/null; echo $PWD)/extract_end_state.py" .; then
        PREV_FINAL_STATES="$(pwd)/final_states.yml"
    else
        echo "Warning: extract_end_state.py failed for ${DECADE_NAME}; next decade uses analytical SS." >&2
        PREV_FINAL_STATES=""
    fi

    echo "=== Completed: ${RUN_DIR} ==="
    cd - > /dev/null
done

echo "=== Transient calibration complete ==="
