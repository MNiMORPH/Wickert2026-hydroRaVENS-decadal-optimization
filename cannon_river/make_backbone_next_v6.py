#!/usr/bin/env python3
"""
Create params_backbone_vX.Y.yml for the next v6.x backbone iteration.

Reads best-fit values from a completed backbone evaluations.dat and updates
log__recession_coeff_soil.fixed with the mean from completed per-decade
transient runs (via the summary YAML written by extract_ksoil_best.py).

The next version is the prior version with the minor digit incremented:
  6.0 → 6.1,  6.1 → 6.2, etc.

Usage:
    python make_backbone_next_v6.py \\
        --from-backbone backbone_runs/TIMESTAMP_backbone_v6.0/evaluations.dat \\
        --ksoil-summary ksoil_v6.0.yml \\
        --from-params params_backbone_v6.0.yml \\
        --out-version 6.1
"""

import argparse
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
    """'6.0' → '6.1',  '6.1' → '6.2', etc."""
    major, minor = version_str.split('.')
    return f"{major}.{int(minor) + 1}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--from-backbone', required=True,
                        help='Path to completed backbone evaluations.dat')
    parser.add_argument('--ksoil-summary', required=True,
                        help='YAML summary from extract_ksoil_best.py')
    parser.add_argument('--from-params', required=True,
                        help='Previous backbone params YAML (template)')
    parser.add_argument('--out-version', default=None,
                        help='Output version string (default: auto-increment minor)')
    args = parser.parse_args()

    # --- load inputs ---
    best, kge = load_backbone_best(args.from_backbone)

    with open(args.ksoil_summary) as f:
        ksoil_data = yaml.safe_load(f)
    mean_log_k  = float(ksoil_data['mean_log__recession_coeff_soil'])
    mean_tau    = float(ksoil_data['mean_tau_soil_days'])
    per_decade_k_soil = {
        decade: round(float(data['log__recession_coeff_soil']), 6)
        for decade, data in ksoil_data['decades'].items()
    }
    print(f"Transient mean log__recession_coeff_soil = {mean_log_k:.4f}  (τ = {mean_tau:.1f} d)")
    for dec, val in per_decade_k_soil.items():
        print(f"  {dec}: log_k={val:.4f}  τ={10**val:.1f} d")

    with open(args.from_params) as f:
        cfg = yaml.safe_load(f)

    # --- infer version numbers ---
    from_path = Path(args.from_params)
    stem      = from_path.stem  # params_backbone_v6.0
    prev_ver  = stem.split('_v')[-1] if '_v' in stem else '6.0'
    next_ver  = args.out_version or bump_minor(prev_ver)
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

    # --- update log__recession_coeff_soil fixed value (mean; per-decade in driver) ---
    if 'log__recession_coeff_soil' in params:
        old_k = params['log__recession_coeff_soil']['fixed']
        params['log__recession_coeff_soil']['fixed']   = round(mean_log_k, 6)
        params['log__recession_coeff_soil']['initial'] = round(mean_log_k, 6)
        print(f"log__recession_coeff_soil: {old_k:.4f} → {mean_log_k:.4f} "
              f"(mean; per-decade values in driver)")

    # --- embed per-decade k_soil in driver section ---
    cfg['driver']['per_decade_k_soil'] = per_decade_k_soil

    # --- write output ---
    out_path = Path(f'params_backbone_v{next_ver}.yml')
    with open(out_path, 'w') as f:
        f.write(f"# Backbone calibration v{next_ver} — soil-reservoir tile-drain architecture.\n")
        f.write(f"#\n")
        f.write(f"# Iteration from backbone_v{prev_ver} (mean KGE={kge:.4f}).\n")
        f.write(f"# log__recession_coeff_soil: per-decade from transient_v{prev_ver}"
                f" (mean={mean_log_k:.4f}, τ={mean_tau:.1f} d).\n")
        f.write(f"# Active param initials seeded from backbone_v{prev_ver} best-fit.\n")
        f.write(f"#\n")
        f.write(f"# Active (7 params): geologic (5) + snow (2).\n")
        f.write(f"# Fixed: b_soil=2 (Dupuit-Forchheimer); "
                f"log__recession_coeff_soil per decade (driver.per_decade_k_soil).\n")
        f.write(f"#\n")
        yaml.dump(cfg, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
    print(f"Written: {out_path}")


if __name__ == '__main__':
    main()
