#!/bin/bash
# Usage: bash archive_run.sh <decade-dir> <run-name>
# e.g.:  bash archive_run.sh decades/1911-1920 2026-06-14_083000_full
#
# Copies the configuration and outputs of the current Dakota run into
# <decade-dir>/runs/<run-name>/ for version-controlled storage.
#
# Files archived:
#   dakota.in, driver.py, params.yml, run_driver.sh  -- exact config
#   <config_template>  (resolved from params.yml)    -- hydroRaVENS config
#   evaluations.dat  (dakota.dat renamed)            -- all evaluations
#   dakota_log.txt   (dakota.out renamed)            -- Dakota log
#   best_fit.png     if present                      -- diagnostic plot

set -euo pipefail

DECADE_DIR="${1:?Usage: bash archive_run.sh <decade-dir> <run-name>}"
NAME="${2:?}"
DEST="${DECADE_DIR}/runs/${NAME}"

if [[ -d "$DEST" ]]; then
    echo "Error: $DEST already exists. Choose a different name." >&2
    exit 1
fi

mkdir -p "$DEST"

PARAMS="${DECADE_DIR}/params.yml"

# Resolve config template from this decade's params.yml
CONFIG=$(python3 -c "
import yaml
with open('${PARAMS}') as f:
    cfg = yaml.safe_load(f)
print(cfg['driver']['config_template'])
")

cp dakota.in       "$DEST/"
cp driver.py       "$DEST/"
cp "$PARAMS"       "$DEST/params.yml"
cp run_driver.sh   "$DEST/"
cp "$CONFIG"       "$DEST/"
cp dakota.dat      "$DEST/evaluations.dat"
cp dakota.out      "$DEST/dakota_log.txt"
[[ -f best_fit.png ]] && cp best_fit.png "$DEST/"

N=$(( $(wc -l < "$DEST/evaluations.dat") - 1 ))
echo "Archived to $DEST  ($N evaluations)"
