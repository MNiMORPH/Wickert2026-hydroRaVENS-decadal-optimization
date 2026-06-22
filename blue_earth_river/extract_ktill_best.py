#!/usr/bin/env python3
"""
Extract best-fit log__recession_coeff_till and log__Hmax_till per decade from
completed v3.x transient runs.

Blue Earth River: 7 full-coverage decades (1951-2020).

Usage:
    python extract_ktill_best.py --desc transient_v3.0 --save ktill_v3.0.yml
"""

import argparse
import yaml
from pathlib import Path

VALID_DECADES = [
    '1951-1960', '1961-1970', '1971-1980', '1981-1990',
    '1991-2000', '2001-2010', '2011-2020',
]


def load_best(eval_path):
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
        return None
    return min(valid, key=lambda r: r['neg_kge']), len(valid)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--desc', default='transient_v3.0',
                        help='Substring that must appear in the run directory name')
    parser.add_argument('--save', default=None,
                        help='Write summary to this YAML file (e.g. ktill_v3.0.yml)')
    args = parser.parse_args()

    results = {}
    for decade in VALID_DECADES:
        runs_dir = Path('decades') / decade / 'runs'
        if not runs_dir.exists():
            print(f"{decade}: no runs/ directory")
            continue

        matching = sorted(d for d in runs_dir.iterdir()
                          if d.is_dir() and args.desc in d.name)
        if not matching:
            print(f"{decade}: no run matching '{args.desc}'")
            continue

        run_dir   = matching[-1]
        eval_path = run_dir / 'evaluations.dat'
        if not eval_path.exists():
            print(f"{decade}: {run_dir.name} has no evaluations.dat")
            continue

        result = load_best(eval_path)
        if result is None:
            print(f"{decade}: no valid evaluations in {run_dir.name}")
            continue
        best, n_valid = result

        log_k   = best.get('log__recession_coeff_till')
        log_hmax = best.get('log__Hmax_till')
        kge     = 1.0 - best['neg_kge']

        if log_k is None:
            print(f"{decade}: log__recession_coeff_till not found in {run_dir.name}")
            continue

        results[decade] = {
            'log__recession_coeff_till': round(float(log_k), 6),
            'kappa_till_days':           round(10 ** float(log_k), 2),
            'log__Hmax_till':            round(float(log_hmax), 6) if log_hmax is not None else None,
            'Hmax_till_mm':              round(10 ** float(log_hmax), 1) if log_hmax is not None else None,
            'kge':                       round(float(kge), 4),
            'n_valid':                   n_valid,
            'run':                       run_dir.name,
        }
        hmax_str = f"  Hmax={10**float(log_hmax):.0f} mm" if log_hmax is not None else ""
        print(f"{decade}: log_k={log_k:.4f}  κ={10**float(log_k):.1f} d"
              f"{hmax_str}  KGE={kge:.4f}  ({n_valid} valid evals)  [{run_dir.name}]")

    if not results:
        print("No results found.")
        return

    log_k_vals  = [v['log__recession_coeff_till'] for v in results.values()]
    log_hm_vals = [v['log__Hmax_till'] for v in results.values() if v['log__Hmax_till'] is not None]
    kge_vals    = [v['kge'] for v in results.values()]
    mean_log_k  = sum(log_k_vals) / len(log_k_vals)
    mean_log_hm = sum(log_hm_vals) / len(log_hm_vals) if log_hm_vals else None
    mean_kge    = sum(kge_vals) / len(kge_vals)
    print(f"\nDecades with results           : {len(results)}/{len(VALID_DECADES)}")
    print(f"Mean log__recession_coeff_till : {mean_log_k:.4f}  (κ = {10**mean_log_k:.1f} d)")
    if mean_log_hm is not None:
        print(f"Mean log__Hmax_till            : {mean_log_hm:.4f}  (Hmax = {10**mean_log_hm:.0f} mm)")
    print(f"Mean KGE                       : {mean_kge:.4f}")

    if args.save:
        summary = {
            'desc':                          args.desc,
            'mean_log__recession_coeff_till': round(mean_log_k, 6),
            'mean_kappa_till_days':           round(10 ** mean_log_k, 2),
            'mean_log__Hmax_till':            round(mean_log_hm, 6) if mean_log_hm is not None else None,
            'mean_Hmax_till_mm':              round(10 ** mean_log_hm, 1) if mean_log_hm is not None else None,
            'mean_kge':                       round(mean_kge, 4),
            'decades':                        results,
        }
        with open(args.save, 'w') as f:
            yaml.dump(summary, f, default_flow_style=False, sort_keys=True,
                      allow_unicode=True)
        print(f"Saved: {args.save}")


if __name__ == '__main__':
    main()
