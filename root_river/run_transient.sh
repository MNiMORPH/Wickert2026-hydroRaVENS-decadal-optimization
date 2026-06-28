#!/bin/bash
# Run all decades in a transient run directory.
# Usage: bash run_transient.sh transient_run1 [--overwrite]
set -euo pipefail

DIR="${1:?Usage: bash run_transient.sh <transient_runN_dir>}"
shift
OVERWRITE="${1:-}"

if [[ ! -d "$DIR" ]]; then
    echo "ERROR: directory $DIR not found." >&2
    exit 1
fi

for decade_dir in $(ls -d "$DIR"/*/); do
    bash run.sh $OVERWRITE "$decade_dir"
done

echo "=== All decades complete: $DIR ==="
