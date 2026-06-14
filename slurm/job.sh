#!/bin/bash
# SLURM job script for one hydroRaVENS watershed calibration.
#
# Submit from the study root:
#   sbatch slurm/job.sh <watershed_name>
# e.g.:
#   sbatch slurm/job.sh le_sueur_river
#   sbatch slurm/job.sh --overwrite blue_earth_river
#
# The job runs all decades sequentially inside the watershed directory,
# then writes summary.csv. Wall time is generous (48 h) to accommodate
# watersheds with 12 decades; most will finish in 12–24 h.

#SBATCH --job-name=hydroravens
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --mem=16G
#SBATCH --time=48:00:00
#SBATCH --output=logs/%x_%j.out
#SBATCH --error=logs/%x_%j.err
#SBATCH --mail-type=END,FAIL

set -euo pipefail

# --- parse args ---
OVERWRITE=""
POSITIONAL=()
for arg in "$@"; do
    case "$arg" in
        --overwrite) OVERWRITE="--overwrite" ;;
        *) POSITIONAL+=("$arg") ;;
    esac
done
WATERSHED="${POSITIONAL[0]:?Usage: sbatch slurm/job.sh [--overwrite] <watershed_name>}"

# --- environment ---
# Activate the dakota-env conda environment.
# Adjust the path to your conda installation on MSI, e.g.:
#   module load conda  (if MSI provides a module)
# or:
#   source ~/miniconda3/etc/profile.d/conda.sh
source ~/anaconda3/etc/profile.d/conda.sh 2>/dev/null \
    || source ~/miniconda3/etc/profile.d/conda.sh 2>/dev/null \
    || { echo "Could not find conda init script"; exit 1; }
conda activate dakota-env

# Make python and dakota available without full paths (picked up from conda env).
export PYTHON=python
export DAKOTA=dakota

# --- run ---
STUDY_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WS_DIR="$STUDY_ROOT/$WATERSHED"

if [[ ! -d "$WS_DIR" ]]; then
    echo "ERROR: watershed directory not found: $WS_DIR" >&2
    exit 1
fi

mkdir -p "$STUDY_ROOT/logs"

echo "=== Job: $WATERSHED  ($(date)) ==="
echo "=== Node: $SLURM_NODELIST  CPUs: $SLURM_CPUS_PER_TASK ==="

cd "$WS_DIR"
bash run_all_decades.sh $OVERWRITE

echo "=== Finished: $WATERSHED  ($(date)) ==="
