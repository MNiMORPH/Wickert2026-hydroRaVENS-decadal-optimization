#!/usr/bin/env python3
"""
Warm-start each decade's params.yml with best parameter values from the
nearest well-calibrated decade, so Dakota begins exploration from a physically
plausible point rather than a fixed generic initial guess.

Workflow:
  1. Run all decades once:   bash run_all_decades.sh
  2. Warm-start:             python warm_start.py
  3. Re-run poor decades:    bash run_all_decades.sh --overwrite

Only `initial:` is updated — `fixed:` (used by inactive parameters) and
bounds are left untouched. Decades that already qualify as donors are skipped.

Usage (from watershed study dir, e.g. cannon_river/):
    python warm_start.py
    python warm_start.py --summary summary.csv --min-pct 50 --min-kge 0.5
    python warm_start.py --dry-run
"""

import argparse
import re
import sys
from pathlib import Path

import pandas as pd
import yaml

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

parser = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument('--summary',    default='summary.csv',
                    help='Path to summary.csv (default: summary.csv)')
parser.add_argument('--decades-dir', default='decades',
                    help='Path to decades/ directory (default: decades)')
parser.add_argument('--min-pct',    type=float, default=50.0,
                    help='Minimum discharge data coverage %% to qualify as donor (default: 50)')
parser.add_argument('--min-kge',    type=float, default=0.5,
                    help='Minimum KGE to qualify as donor decade (default: 0.5)')
parser.add_argument('--dry-run',    action='store_true',
                    help='Print what would change without writing files')
args = parser.parse_args()

# ---------------------------------------------------------------------------
# Load summary
# ---------------------------------------------------------------------------

summary_path = Path(args.summary)
if not summary_path.exists():
    sys.exit(f"ERROR: {summary_path} not found. Run summarize.py first.")

summary = pd.read_csv(summary_path)
if 'KGE' not in summary.columns or 'pct_data' not in summary.columns:
    sys.exit("ERROR: summary.csv missing KGE or pct_data columns. Re-run summarize.py.")

# Decade midpoint year for temporal proximity
summary['_mid'] = summary['decade'].apply(lambda d: (int(d[:4]) + int(d[5:])) / 2.0)

param_cols = [c for c in summary.columns if c.startswith('param_')]
if not param_cols:
    sys.exit("ERROR: no param_* columns found in summary.csv.")

# ---------------------------------------------------------------------------
# Identify donor decades
# ---------------------------------------------------------------------------

donors = summary[
    (summary['pct_data'] >= args.min_pct) &
    (summary['KGE']      >= args.min_kge)
].copy()

if donors.empty:
    sys.exit(
        f"No donor decades meet thresholds "
        f"(pct_data >= {args.min_pct:.0f}%, KGE >= {args.min_kge:.2f}). "
        f"Lower thresholds or run more decades first."
    )

print(f"Donor decades (pct_data >= {args.min_pct:.0f}%, KGE >= {args.min_kge:.2f}):")
for _, d in donors.iterrows():
    print(f"  {d['decade']}  KGE={d['KGE']:.3f}  data={d['pct_data']:.0f}%")

# ---------------------------------------------------------------------------
# Update initial: values
# ---------------------------------------------------------------------------

def _set_initial(lines, param_name, value):
    """Replace `initial:` for param_name in a list of lines (in-place style)."""
    in_block = False
    result = []
    for line in lines:
        stripped = line.rstrip()
        if stripped == f'  {param_name}:':
            in_block = True
        elif in_block and re.match(r'  \S', line) and stripped != f'  {param_name}:':
            in_block = False
        if in_block and re.match(r'\s+initial:', line):
            line = f'    initial: {round(value, 7)}\n'
        result.append(line)
    return result


DECADES_DIR = Path(args.decades_dir)
n_updated = 0

for _, row in summary.iterrows():
    decade = row['decade']
    params_path = DECADES_DIR / decade / 'params.yml'
    if not params_path.exists():
        print(f"  {decade}: params.yml not found, skipping")
        continue

    # Find nearest donor (by mid-year distance)
    dists = (donors['_mid'] - row['_mid']).abs()
    nearest = donors.loc[dists.idxmin()]

    if nearest['decade'] == decade:
        print(f"  {decade}: already a donor, no change")
        continue

    # Check for NaN in donor params (decade had penalty / no metrics)
    donor_vals = {col[len('param_'):]: nearest[col]
                  for col in param_cols if pd.notna(nearest[col])}
    if not donor_vals:
        print(f"  {decade}: donor {nearest['decade']} has no valid parameters, skipping")
        continue

    if args.dry_run:
        print(f"  {decade}: would warm-start from {nearest['decade']} "
              f"(KGE={nearest['KGE']:.3f}, {nearest['pct_data']:.0f}% data)")
        continue

    lines = params_path.read_text().splitlines(keepends=True)
    for name, value in donor_vals.items():
        lines = _set_initial(lines, name, value)

    params_path.write_text(''.join(lines))
    print(f"  {decade}: warm-started from {nearest['decade']} "
          f"(KGE={nearest['KGE']:.3f}, {nearest['pct_data']:.0f}% data) "
          f"— updated {len(donor_vals)} initial values")
    n_updated += 1

if not args.dry_run:
    print(f"\nUpdated {n_updated} decade(s). Re-run with --overwrite to recalibrate.")
