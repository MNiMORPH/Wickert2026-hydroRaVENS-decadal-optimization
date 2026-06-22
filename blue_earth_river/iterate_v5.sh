#!/bin/bash
# iterate_v5.sh — Backbone→transient→backbone iteration for Blue Earth River v5.x.
#
# 1-reservoir till+tile architecture, no Hmax, per-decade free b:
#   - backbone calibrates snow/FGI only (PDD, FGI threshold)
#   - transient calibrates per-decade: κ_till, b_till, et_scale
#   - iteration carries per-decade κ_till and b_till back into backbone
#
# Usage: bash iterate_v5.sh <existing_backbone_run_dir> <current_minor_ver> [max_iters]
# e.g.:  bash iterate_v5.sh backbone_runs/2026-06-19_XXXXXX_backbone_v5.0 0 4
#
# Run from blue_earth_river/

set -euo pipefail

BE_DIR="$(pwd)"
PYTHON=/home/awickert/anaconda3/envs/dakota-env/bin/python
MAJOR_VER=5
CONVERGE_TOL=0.005

EXISTING_BB_DIR="${1:?Usage: bash iterate_v5.sh <backbone_run_dir> <minor_ver> [max_iters]}"
MINOR_VER="${2:?}"
MAX_ITERS="${3:-4}"

ts()  { date '+%Y-%m-%d %H:%M:%S'; }
log() { echo "[$(ts)] $*"; }

# ================================================================
backbone_summary() {
    local eval_path="$1" ver="$2"
    log "=== Backbone v${ver} Summary ==="
    $PYTHON - "$eval_path" "$ver" << 'PYEOF'
import sys
eval_path, ver = sys.argv[1], sys.argv[2]
rows = []
with open(eval_path) as f:
    header = f.readline().lstrip('%').split()
    for line in f:
        parts = line.split()
        if len(parts) < len(header): continue
        try:
            row = {h: (parts[i] if i==1 else float(parts[i])) for i,h in enumerate(header)}
            rows.append(row)
        except (ValueError, IndexError): pass
valid = [r for r in rows if r['neg_kge'] < 9.0]
if not valid:
    print("  No valid evaluations found.")
    sys.exit(0)
best = min(valid, key=lambda r: r['neg_kge'])
kge  = 1.0 - best['neg_kge']
print(f"\n  Backbone v{ver}: mean KGE_logKGE = {kge:.4f}  ({len(valid)} valid evals)")
print("  Best-fit parameters:")
for p in ['PDD_melt_factor', 'log__fdd_threshold']:
    if p in best:
        print(f"    {p:<45s} = {best[p]:.4f}")
PYEOF
}

# ================================================================
transient_summary() {
    local ver="$1"
    log "=== Transient v${ver} Summary ==="
    $PYTHON - "$ver" << 'PYEOF'
import sys, glob
ver = sys.argv[1]
decades_order = ['1951-1960','1961-1970','1971-1980','1981-1990',
                 '1991-2000','2001-2010','2011-2020']
rows_out = []
for dec in decades_order:
    pattern = f"decades/{dec}/runs/*_transient_v{ver}/evaluations.dat"
    matches = sorted(glob.glob(pattern))
    if not matches:
        rows_out.append((dec, None, None, None, None, 0))
        continue
    rows = []
    with open(matches[-1]) as f:
        header = f.readline().lstrip('%').split()
        for line in f:
            parts = line.split()
            if len(parts) < len(header): continue
            try:
                row = {h: (parts[i] if i==1 else float(parts[i])) for i,h in enumerate(header)}
                rows.append(row)
            except (ValueError, IndexError): pass
    valid = [r for r in rows if r['neg_kge'] < 9.0]
    if not valid:
        rows_out.append((dec, None, None, None, None, len(rows)))
        continue
    best = min(valid, key=lambda r: r['neg_kge'])
    rows_out.append((
        dec,
        1.0 - best['neg_kge'],
        best.get('log__recession_coeff_till', float('nan')),
        best.get('recession_b_till', float('nan')),
        best.get('et_scale', float('nan')),
        len(valid),
    ))

print(f"\n  {'Decade':<12} {'KGE_logKGE':>11} {'log_κ_till':>11} {'b_till':>7} {'et_scale':>9} {'evals':>6}")
print(f"  {'-'*12} {'-'*11} {'-'*11} {'-'*7} {'-'*9} {'-'*6}")
kges = []
for dec, kge, lk, b, es, n in rows_out:
    if kge is not None:
        print(f"  {dec:<12} {kge:>11.4f} {lk:>11.4f} {b:>7.4f} {es:>9.4f} {n:>6}")
        kges.append(kge)
    else:
        print(f"  {dec:<12} {'—':>11} {'—':>11} {'—':>7} {'—':>9} {n:>6}")
if kges:
    print(f"  {'Mean':<12} {sum(kges)/len(kges):>11.4f}")
PYEOF
}

# Extract mean KGE from transient runs
transient_mean_kge() {
    local ver="$1"
    $PYTHON - "$ver" << 'PYEOF'
import sys, glob
ver = sys.argv[1]
decades_order = ['1951-1960','1961-1970','1971-1980','1981-1990',
                 '1991-2000','2001-2010','2011-2020']
kges = []
for dec in decades_order:
    pattern = f"decades/{dec}/runs/*_transient_v{ver}/evaluations.dat"
    matches = sorted(glob.glob(pattern))
    if not matches: continue
    rows = []
    with open(matches[-1]) as f:
        header = f.readline().lstrip('%').split()
        for line in f:
            parts = line.split()
            if len(parts) < len(header): continue
            try:
                row = {h: (parts[i] if i==1 else float(parts[i])) for i,h in enumerate(header)}
                rows.append(row)
            except (ValueError, IndexError): pass
    valid = [r for r in rows if r['neg_kge'] < 9.0]
    if valid:
        kges.append(1.0 - min(valid, key=lambda r: r['neg_kge'])['neg_kge'])
print(f"{sum(kges)/len(kges):.6f}" if kges else "0")
PYEOF
}

# ================================================================
# Step 0: Wait for the already-running backbone to finish
log "Waiting for backbone v${MAJOR_VER}.${MINOR_VER} (${EXISTING_BB_DIR}) to finish..."
while [[ ! -f "${EXISTING_BB_DIR}/dakota_log.txt" ]]; do
    sleep 60
done
log "Backbone v${MAJOR_VER}.${MINOR_VER} complete."

CURRENT_BB_EVAL="${EXISTING_BB_DIR}/evaluations.dat"
CURRENT_BB_PARAMS="params_backbone_v${MAJOR_VER}.${MINOR_VER}.yml"
PREV_TRANSIENT_KGE=0.0

# ================================================================
# Main iteration loop
for ITER in $(seq 1 $MAX_ITERS); do
    VER="${MAJOR_VER}.${MINOR_VER}"
    NEXT_MINOR=$((MINOR_VER + 1))
    NEXT_VER="${MAJOR_VER}.${NEXT_MINOR}"

    # 1. Backbone summary
    backbone_summary "$CURRENT_BB_EVAL" "$VER"

    # 2. Generate transient params seeded from this backbone
    log "Generating params_transient_v${VER}.yml for all decades..."
    $PYTHON make_transient_params_v5.0.py --backbone "$CURRENT_BB_EVAL" --version "$VER"

    # 3. Run transient
    log "Starting transient v${VER}..."
    bash run_transient.sh "transient_v${VER}" driver_transient_v5.0.py "_v${VER}" \
        2>&1 | tee "/tmp/transient_be_v${VER}.log"

    # 4. Transient summary
    transient_summary "$VER"

    # 5. Extract κ_till and b_till per decade
    $PYTHON extract_ktill_b_best.py --desc "transient_v${VER}" --save "ktill_b_v${VER}.yml"

    # 6. Convergence check
    MEAN_KGE=$(transient_mean_kge "$VER")
    DELTA=$(echo "$MEAN_KGE $PREV_TRANSIENT_KGE" | awk '{d=$1-$2; if(d<0) d=-d; print d}')
    log "Transient v${VER}: mean KGE=${MEAN_KGE}  ΔKGE vs prior=${DELTA}  (tol=${CONVERGE_TOL})"
    PREV_TRANSIENT_KGE="$MEAN_KGE"

    if [[ "$ITER" -gt 1 ]]; then
        CONVERGED=$(echo "$DELTA $CONVERGE_TOL" | awk '{print ($1 < $2) ? "yes" : "no"}')
        if [[ "$CONVERGED" == "yes" ]]; then
            log "Converged: ΔKGE=${DELTA} < tol=${CONVERGE_TOL} after transient v${VER}. Stopping."
            break
        fi
    fi

    # 7. Generate next backbone params
    log "Generating params_backbone_v${NEXT_VER}.yml..."
    $PYTHON make_backbone_next_v5.py \
        --from-backbone "$CURRENT_BB_EVAL" \
        --ktill-summary  "ktill_b_v${VER}.yml" \
        --from-params    "$CURRENT_BB_PARAMS"

    # 8. Run next backbone
    log "Starting backbone v${NEXT_VER}..."
    bash run_backbone.sh "backbone_v${NEXT_VER}" "params_backbone_v${NEXT_VER}.yml" \
        driver_backbone_v5.0.py 2>&1 | tee "/tmp/backbone_be_v${NEXT_VER}.log"

    NEW_BB_DIR=$(ls -td backbone_runs/*backbone_v${NEXT_VER} 2>/dev/null | head -1 || true)
    if [[ -z "$NEW_BB_DIR" ]]; then
        log "ERROR: Cannot find backbone_v${NEXT_VER} run directory — aborting."
        exit 1
    fi

    CURRENT_BB_EVAL="${NEW_BB_DIR}/evaluations.dat"
    CURRENT_BB_PARAMS="params_backbone_v${NEXT_VER}.yml"
    MINOR_VER=$NEXT_MINOR

    log "Completed iteration ${ITER}  (backbone v${NEXT_VER} done)"
done

log "=== Iteration loop complete at v${MAJOR_VER}.${MINOR_VER} ==="
