#!/bin/bash
# SLURM job script for one hydroRaVENS forcing-data compute phase.
#
# Runs the IDW interpolation and db.out.hydroravens export for a single
# watershed.  The download phase (v.in.waterdata + v.in.ghcn) must have
# already run locally (with internet) and the GRASS mapset transferred to MSI.
#
# Submit from the study root:
#   sbatch slurm/pipeline_job.sh <watershed_name>
# e.g.:
#   sbatch slurm/pipeline_job.sh le_sueur_river

#SBATCH --job-name=hr_pipe
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --time=12:00:00
#SBATCH --output=logs/%x_%j.out
#SBATCH --error=logs/%x_%j.err
#SBATCH --mail-type=END,FAIL

set -euo pipefail

WATERSHED="${1:?Usage: sbatch slurm/pipeline_job.sh <watershed_name>}"

# --- environment ---
source ~/anaconda3/etc/profile.d/conda.sh 2>/dev/null \
    || source ~/miniconda3/etc/profile.d/conda.sh 2>/dev/null \
    || { echo "Could not find conda init script"; exit 1; }
conda activate dakota-env

# Resolve PROJ data directory: prefer conda env, fall back to system.
PROJ_DATA="${PROJ_DATA:-${CONDA_PREFIX:+$CONDA_PREFIX/share/proj}}"
PROJ_DATA="${PROJ_DATA:-/usr/share/proj}"
export PROJ_DATA PROJ_LIB="$PROJ_DATA"

# --- locate pipeline script ---
STUDY_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$STUDY_ROOT/logs"

# Pipeline compute scripts live in db.out.hydroravens/examples/<name>/
COMPUTE_SCRIPT="$STUDY_ROOT/db.out.hydroravens/examples/${WATERSHED}/${WATERSHED}_pipeline_compute.sh"
if [[ ! -f "$COMPUTE_SCRIPT" ]]; then
    echo "ERROR: compute script not found: $COMPUTE_SCRIPT" >&2
    exit 1
fi

# --- locate GRASS location for this watershed ---
# The GRASS location is expected at ~/grassdata/<watershed_name>_aea/PERMANENT
# (or as configured in the watershed config).
GRASS_LOC=$(python3 -c "
import yaml, glob, sys
for cfg in glob.glob('$STUDY_ROOT/watershed_configs/*.yml'):
    d = yaml.safe_load(open(cfg))
    if d.get('name') == '$WATERSHED':
        print(d['forcing']['grass_location'])
        sys.exit(0)
sys.exit(1)
")

GRASS_DB="${HOME}/grassdata"
MAPSET_PATH="${GRASS_DB}/${GRASS_LOC}/PERMANENT"

if [[ ! -d "$MAPSET_PATH" ]]; then
    echo "ERROR: GRASS mapset not found: $MAPSET_PATH" >&2
    echo "Transfer the GRASS mapset from the download machine first." >&2
    exit 1
fi

echo "=== Pipeline compute: $WATERSHED  ($(date)) ==="
echo "=== Node: $SLURM_NODELIST  CPUs: $SLURM_CPUS_PER_TASK ==="
echo "=== GRASS mapset: $MAPSET_PATH ==="
echo "=== PROJ_DATA: $PROJ_DATA ==="

grass "$MAPSET_PATH" --exec bash "$COMPUTE_SCRIPT"

echo "=== Finished: $WATERSHED  ($(date)) ==="
