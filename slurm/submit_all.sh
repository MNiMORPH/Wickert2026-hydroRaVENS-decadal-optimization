#!/bin/bash
# Submit SLURM calibration jobs for all watersheds that have forcing data
# but no completed calibration (summary.csv absent).
#
# Usage (from the study root):
#   bash slurm/submit_all.sh            # dry run — prints sbatch commands
#   bash slurm/submit_all.sh --go       # actually submits
#   bash slurm/submit_all.sh --overwrite --go  # overwrite existing runs

set -euo pipefail

DRY=true
OVERWRITE=""
for arg in "$@"; do
    case "$arg" in
        --go)        DRY=false ;;
        --overwrite) OVERWRITE="--overwrite" ;;
    esac
done

STUDY_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$STUDY_ROOT"

submitted=0
skipped=0

for cfg in watershed_configs/*.yml; do
    name=$(python3 -c "import yaml; print(yaml.safe_load(open('$cfg'))['name'])")
    config_name=$(python3 -c "import yaml; print(yaml.safe_load(open('$cfg'))['forcing']['config_name'])")

    forcing_ready=false
    [[ -f "${name}/${config_name}" ]] && forcing_ready=true

    calib_done=false
    [[ -f "${name}/summary.csv" ]] && calib_done=true

    if $forcing_ready && ! $calib_done; then
        cmd="sbatch --job-name=hr_${name} slurm/job.sh $OVERWRITE ${name}"
        if $DRY; then
            echo "[dry-run] $cmd"
        else
            echo "Submitting: $cmd"
            eval "$cmd"
        fi
        submitted=$((submitted + 1))
    else
        reason=""
        $forcing_ready  || reason="no forcing"
        $calib_done     && reason="already done"
        echo "skip  ${name}  (${reason})"
        skipped=$((skipped + 1))
    fi
done

echo ""
if $DRY; then
    echo "Dry run: $submitted job(s) would be submitted, $skipped skipped."
    echo "Re-run with --go to submit."
else
    echo "Submitted: $submitted  |  Skipped: $skipped"
fi
