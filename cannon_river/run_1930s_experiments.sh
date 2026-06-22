#!/bin/bash
# Two calibration experiments for 1931-1940 to isolate the ET multiplier effect.
#
# Experiment 1 (global_et):   enforce_water_balance='global', full-record
#                              multiplier (0.6818), et_scale fixed at 1.
#                              Baseline with the corrected code.
#
# Experiment 2 (free_et):     enforce_water_balance='none', et_scale free
#                              parameter [0.3, 1.2]; optimizer finds best ET
#                              scale directly from discharge observations.
#
# Run from cannon_river/:
#   nohup bash run_1930s_experiments.sh >run_1930s_experiments.log 2>&1 &

set -euo pipefail

DECADE="decades/1931-1940"
PARAMS_ORIG="${DECADE}/params.yml"
PARAMS_SAVED="${DECADE}/params_global_et.yml"
PARAMS_FREE="${DECADE}/params_free_et.yml"

PYTHON=${PYTHON:-/home/awickert/anaconda3/envs/dakota-env/bin/python}
DAKOTA=${DAKOTA:-/home/awickert/anaconda3/envs/dakota-env/bin/dakota}
export PYTHON DAKOTA

# --- Experiment 1: global ET multiplier (full-record), et_scale fixed ---
echo "=== Experiment 1: global ET multiplier (full-record) ==="
cp "$PARAMS_ORIG" "$PARAMS_SAVED"
bash run.sh --overwrite "$DECADE" global_et

# --- Experiment 2: enforce_water_balance='none', et_scale free ---
echo "=== Experiment 2: free et_scale (enforce_water_balance=none) ==="

# Build modified params.yml: flip enforce_water_balance and activate et_scale
$PYTHON - << PYEOF
import yaml, re

with open('${PARAMS_SAVED}') as f:
    cfg = yaml.safe_load(f)

cfg['driver']['enforce_water_balance'] = 'none'

cfg['parameters']['et_scale'] = {
    'description': 'global ET multiplier — free parameter; replaces WB enforcement',
    'lower':   0.3,
    'upper':   1.2,
    'initial': 0.6818,   # full-record global multiplier
    'fixed':   0.6818,
    'active':  True,
}

with open('${PARAMS_FREE}', 'w') as f:
    yaml.dump(cfg, f, default_flow_style=False, sort_keys=False)

print("Wrote ${PARAMS_FREE}")
PYEOF

cp "$PARAMS_FREE" "$PARAMS_ORIG"
bash run.sh --overwrite "$DECADE" free_et

# Restore original params.yml
cp "$PARAMS_SAVED" "$PARAMS_ORIG"
echo "=== Both experiments complete. params.yml restored. ==="
