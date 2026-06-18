#!/usr/bin/env python3
"""
Create params_backbone_vX.Y.yml for the next backbone iteration.

Reads best-fit values from a completed backbone evaluations.dat and updates
f_tile_soil.fixed with the mean from completed per-decade transient runs
(via the summary YAML written by extract_ftile_best.py).

The next version is the prior version with the minor digit incremented:
  5.0 → 5.1,  5.1 → 5.2, etc.

Usage:
    python make_backbone_next.py \\
        --from-backbone backbone_runs/TIMESTAMP_backbone_v5.0/evaluations.dat \\
        --ftile-summary ftile_v5.0.yml \\
        --from-params params_backbone_v5.0.yml \\
        --out-version 5.1
"""

import argparse
import copy
import yaml
from pathlib import Path


def load_backbone_best(eval_path):
    rows = []
    with open(eval_path) as f:
        header = f.readline().lstrip('%').split()
        for line in f:
            parts = line.split()
            if len(parts) < len(header):
                continue
            try:
                row = {header[i]: (parts[i] if i == 1 else float(parts[i]))
                       for i in range(len(header))}
                rows.append(row)
            except (ValueError, IndexError):
                pass
    valid = [r for r in rows if r['neg_kge'] < 9.0]
    if not valid:
        raise RuntimeError(f"No valid evaluations in {eval_path}")
    best = min(valid, key=lambda r: r['neg_kge'])
    kge  = 1.0 - best['neg_kge']
    print(f"Backbone best: mean KGE = {kge:.4f}")
    return best, kge


def bump_minor(version_str):
    """'5.0' → '5.1',  '5.1' → '5.2', etc."""
    major, minor = version_str.split('.')
    return f"{major}.{int(minor) + 1}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--from-backbone', required=True,
                        help='Path to completed backbone evaluations.dat')
    parser.add_argument('--ftile-summary', required=True,
                        help='YAML summary from extract_ftile_best.py')
    parser.add_argument('--from-params', required=True,
                        help='Previous backbone params YAML (template)')
    parser.add_argument('--out-version', default=None,
                        help='Output version string (default: auto-increment minor)')
    args = parser.parse_args()

    # --- load inputs ---
    best, kge = load_backbone_best(args.from_backbone)

    with open(args.ftile_summary) as f:
        ftile_data = yaml.safe_load(f)
    mean_ftile = float(ftile_data['mean_f_tile_soil'])
    per_decade_ftile = {
        decade: round(float(data['f_tile_soil']), 6)
        for decade, data in ftile_data['decades'].items()
    }
    print(f"Transient mean f_tile_soil = {mean_ftile:.4f}")
    for dec, val in per_decade_ftile.items():
        print(f"  {dec}: {val:.4f}")

    with open(args.from_params) as f:
        raw = f.read()
    cfg = yaml.safe_load(raw)

    # --- infer version numbers ---
    from_path  = Path(args.from_params)
    # e.g. params_backbone_v5.0.yml → '5.0'
    stem = from_path.stem  # params_backbone_v5.0
    prev_ver = stem.split('_v')[-1] if '_v' in stem else '5.0'
    next_ver = args.out_version or bump_minor(prev_ver)
    print(f"Version: {prev_ver} → {next_ver}")

    # --- update active backbone params: set initial to best-fit ---
    params = cfg['parameters']
    n_updated = 0
    for name, pdef in params.items():
        if not pdef.get('active', False):
            continue
        if name in best:
            pdef['initial'] = round(float(best[name]), 6)
            pdef['fixed']   = pdef['initial']
            n_updated += 1
    print(f"Updated {n_updated} active backbone param initials from best-fit")

    # --- update f_tile_soil fixed value (mean; used as fallback in driver) ---
    if 'f_tile_soil' in params:
        old_ftile = params['f_tile_soil']['fixed']
        params['f_tile_soil']['fixed']   = round(mean_ftile, 6)
        params['f_tile_soil']['initial'] = round(mean_ftile, 6)
        print(f"f_tile_soil: {old_ftile:.4f} → {mean_ftile:.4f} (mean; per-decade values in driver)")

    # --- embed per-decade f_tile in driver section ---
    cfg['driver']['per_decade_f_tile'] = per_decade_ftile

    # --- write output ---
    out_path = Path(f'params_backbone_v{next_ver}.yml')
    with open(out_path, 'w') as f:
        f.write(f"# Backbone calibration v{next_ver} — explicit tile-drain architecture.\n")
        f.write(f"#\n")
        f.write(f"# Iteration from backbone_v{prev_ver} (mean KGE={kge:.4f}).\n")
        f.write(f"# f_tile_soil: per-decade values from transient_v{prev_ver} (mean={mean_ftile:.4f}).\n")
        f.write(f"# Active param initials seeded from backbone_v{prev_ver} best-fit.\n")
        f.write(f"#\n")
        f.write(f"# Active (8 params): geologic + snow backbone + tau_tile.\n")
        f.write(f"# Fixed:  b_soil=2 (Dupuit-Forchheimer); f_tile per decade (driver.per_decade_f_tile).\n")
        f.write(f"#\n")
        yaml.dump(cfg, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
    print(f"Written: {out_path}")


if __name__ == '__main__':
    main()
