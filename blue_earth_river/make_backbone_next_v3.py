#!/usr/bin/env python3
"""
Create params_backbone_vX.Y.yml for the next v3.x backbone iteration (Blue Earth River).

Reads best-fit PDD+FGI from a completed backbone evaluations.dat and updates
log__recession_coeff_till.fixed with the mean from completed per-decade transient runs.

The only coupling between backbone and transient in v3 is:
  - Backbone → transient: PDD, FGI threshold (fixed in transient)
  - Transient → backbone: per-decade κ_till (embedded as per_decade_k_till in driver)

Usage:
    python make_backbone_next_v3.py \\
        --from-backbone backbone_runs/TIMESTAMP_backbone_v3.0/evaluations.dat \\
        --ktill-summary ktill_v3.0.yml \\
        --from-params params_backbone_v3.0.yml
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
    major, minor = version_str.split('.')
    return f"{major}.{int(minor) + 1}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--from-backbone', required=True,
                        help='Path to completed backbone evaluations.dat')
    parser.add_argument('--ktill-summary', required=True,
                        help='YAML summary from extract_ktill_best.py')
    parser.add_argument('--from-params', required=True,
                        help='Previous backbone params YAML (template)')
    parser.add_argument('--out-version', default=None,
                        help='Output version string (default: auto-increment minor)')
    args = parser.parse_args()

    best, kge = load_backbone_best(args.from_backbone)

    with open(args.ktill_summary) as f:
        ktill_data = yaml.safe_load(f)
    mean_log_k  = float(ktill_data['mean_log__recession_coeff_till'])
    mean_kappa  = float(ktill_data['mean_kappa_till_days'])
    per_decade_k_till = {
        decade: round(float(data['log__recession_coeff_till']), 6)
        for decade, data in ktill_data['decades'].items()
    }
    print(f"Transient mean log__recession_coeff_till = {mean_log_k:.4f}  (κ = {mean_kappa:.1f} d)")
    for dec, val in per_decade_k_till.items():
        print(f"  {dec}: log_k={val:.4f}  κ={10**val:.1f} d")

    with open(args.from_params) as f:
        cfg = yaml.safe_load(f)

    from_path = Path(args.from_params)
    stem      = from_path.stem
    prev_ver  = stem.split('_v')[-1] if '_v' in stem else '3.0'
    next_ver  = args.out_version or bump_minor(prev_ver)
    print(f"Version: {prev_ver} → {next_ver}")

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

    if 'log__recession_coeff_till' in params:
        old_k = params['log__recession_coeff_till']['fixed']
        params['log__recession_coeff_till']['fixed']   = round(mean_log_k, 6)
        params['log__recession_coeff_till']['initial'] = round(mean_log_k, 6)
        print(f"log__recession_coeff_till: {old_k:.4f} → {mean_log_k:.4f} "
              f"(mean; per-decade values in driver)")

    if 'log__Hmax_till' in params:
        mean_log_hmax = float(ktill_data.get('mean_log__Hmax_till', params['log__Hmax_till']['fixed']))
        params['log__Hmax_till']['fixed']   = round(mean_log_hmax, 6)
        params['log__Hmax_till']['initial'] = round(mean_log_hmax, 6)

    cfg['driver']['per_decade_k_till'] = per_decade_k_till

    out_path = Path(f'params_backbone_v{next_ver}.yml')
    with open(out_path, 'w') as f:
        f.write(f"# Backbone calibration v{next_ver} — 1-reservoir till+tile (Blue Earth River).\n")
        f.write(f"#\n")
        f.write(f"# Iteration from backbone_v{prev_ver} (mean KGE={kge:.4f}).\n")
        f.write(f"# log__recession_coeff_till: per-decade from transient_v{prev_ver}"
                f" (mean={mean_log_k:.4f}, κ={mean_kappa:.1f} d).\n")
        f.write(f"# Active param initials (PDD, FGI) seeded from backbone_v{prev_ver} best-fit.\n")
        f.write(f"#\n")
        f.write(f"# Active (2 params): PDD_melt_factor, log__fdd_threshold (snow-only).\n")
        f.write(f"# Fixed: recession_b_till=2; κ_till per decade (driver.per_decade_k_till).\n")
        f.write(f"#\n")
        yaml.dump(cfg, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
    print(f"Written: {out_path}")


if __name__ == '__main__':
    main()
