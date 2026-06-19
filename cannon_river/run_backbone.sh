#!/bin/bash
# Run the joint backbone calibration.
# Run from cannon_river/
#
# Usage:  bash run_backbone.sh [description] [params_file] [driver_file]
# e.g.:   bash run_backbone.sh backbone_v2
#         bash run_backbone.sh backbone_v5.0 params_backbone_v5.0.yml driver_backbone_v5.0.py

set -euo pipefail

DESC="${1:-backbone}"
TIMESTAMP=$(date +%Y-%m-%d_%H%M%S)
RUN_NAME="${TIMESTAMP}_${DESC}"
RUN_DIR="backbone_runs/${RUN_NAME}"

DAKOTA=${DAKOTA:-/home/awickert/anaconda3/envs/dakota-env/bin/dakota}
PYTHON=${PYTHON:-/home/awickert/anaconda3/envs/dakota-env/bin/python}

PARAMS="${2:-params_backbone.yml}"
DRIVER="${3:-driver_backbone.py}"

echo "=== Backbone run: ${RUN_NAME} ==="
mkdir -p "$RUN_DIR"

# Copy backbone driver as driver.py so run_driver.sh and Dakota's copy_files work.
cp "$DRIVER"            "$RUN_DIR/driver.py"
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
$PYTHON - params.yml << 'PYEOF' || { echo "ERROR: Pre-flight failed." >&2; exit 1; }
import yaml, sys
from mnished import Buckets
with open(sys.argv[1]) as f:
    p = yaml.safe_load(f)
cfg = p["driver"]["config_template"]
ewb = p["driver"].get("enforce_water_balance", None)
b = Buckets()
b.initialize(cfg, enforce_water_balance=ewb)
print(f"Pre-flight OK: {len(b.reservoirs)} reservoirs")
PYEOF

$DAKOTA -i dakota.in -o dakota.out

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
print(f"Best neg_kge={best:.6f}  (mean KGE={1-best:.4f})")
' || exit 1

mv dakota.dat evaluations.dat
mv dakota.out dakota_log.txt

# Remove per-evaluation scratch output (~2 GB/run); evaluations.dat holds all results.
# Reached only after a successful run (set -euo pipefail + penalty check above).
rm -rf out/

echo "=== Completed: ${RUN_DIR} ==="
