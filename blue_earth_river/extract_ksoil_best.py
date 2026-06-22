#!/usr/bin/env python3
"""
Extract best-fit log__recession_coeff_soil per decade from completed transient runs.

Blue Earth River version: 7 full-coverage decades (1951-2020, including 1971-1990).

Usage:
    python extract_ksoil_best.py --desc transient_v1.0 --save ksoil_v1.0.yml
"""

import argparse
import yaml
from pathlib import Path

VALID_DECADES = [
    '1951-1960', '1961-1970', '1971-1980', '1981-1990',
    '1991-2000', '2001-2010', '2011-2020',
]


def load_best(eval_path, param_name='log__recession_coeff_soil'):
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
        return None, None, None
    best = min(valid, key=lambda r: r['neg_kge'])
    return best.get(param_name), 1.0 - best['neg_kge'], len(valid)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--desc', default='transient_v1.0',
                        help='Substring that must appear in the run directory name')
    parser.add_argument('--save', default=None,
                        help='Write summary to this YAML file (e.g. ksoil_v1.0.yml)')
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

        log_k, kge, n_valid = load_best(eval_path)
        if log_k is None:
            print(f"{decade}: no valid evaluations in {run_dir.name}")
            continue

        results[decade] = {
            'log__recession_coeff_soil': round(float(log_k), 6),
            'tau_soil_days':             round(10 ** float(log_k), 2),
            'kge':                       round(float(kge), 4),
            'n_valid':                   n_valid,
            'run':                       run_dir.name,
        }
        print(f"{decade}: log_k={log_k:.4f}  τ={10**float(log_k):.1f} d"
              f"  KGE={kge:.4f}  ({n_valid} valid evals)  [{run_dir.name}]")

    if not results:
        print("No results found.")
        return

    log_k_vals = [v['log__recession_coeff_soil'] for v in results.values()]
    kge_vals   = [v['kge'] for v in results.values()]
    mean_log_k = sum(log_k_vals) / len(log_k_vals)
    mean_kge   = sum(kge_vals) / len(kge_vals)
    print(f"\nDecades with results          : {len(results)}/{len(VALID_DECADES)}")
    print(f"Mean log__recession_coeff_soil: {mean_log_k:.4f}  (τ = {10**mean_log_k:.1f} d)")
    print(f"Mean KGE                      : {mean_kge:.4f}")

    if args.save:
        summary = {
            'desc':                           args.desc,
            'mean_log__recession_coeff_soil': round(mean_log_k, 6),
            'mean_tau_soil_days':             round(10 ** mean_log_k, 2),
            'mean_kge':                       round(mean_kge, 4),
            'decades':                        results,
        }
        with open(args.save, 'w') as f:
            yaml.dump(summary, f, default_flow_style=False, sort_keys=True,
                      allow_unicode=True)
        print(f"Saved: {args.save}")


if __name__ == '__main__':
    main()
