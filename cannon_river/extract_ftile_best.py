#!/usr/bin/env python3
"""
Extract best-fit f_tile_soil per decade from completed transient runs.

Scans each valid decade's runs/ directory for the most recent run whose
name contains DESC (default: 'transient_v5.0'), reads its evaluations.dat,
and reports the best f_tile_soil and KGE.

Usage:
    python extract_ftile_best.py
    python extract_ftile_best.py --desc transient_v5.1 --save ftile_v5.1.yml
"""

import argparse
import yaml
from pathlib import Path

VALID_DECADES = [
    '1931-1940', '1941-1950', '1951-1960', '1961-1970',
    '1991-2000', '2001-2010', '2011-2020',
]


def load_best(eval_path, param_name='f_tile_soil'):
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
    parser.add_argument('--desc', default='transient_v5.0',
                        help='Substring that must appear in the run directory name')
    parser.add_argument('--save', default=None,
                        help='Write summary to this YAML file')
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

        f_tile, kge, n_valid = load_best(eval_path)
        if f_tile is None:
            print(f"{decade}: no valid evaluations in {run_dir.name}")
            continue

        results[decade] = {
            'f_tile_soil': round(float(f_tile), 6),
            'kge':         round(float(kge),    4),
            'n_valid':     n_valid,
            'run':         run_dir.name,
        }
        print(f"{decade}: f_tile_soil={f_tile:.4f}  KGE={kge:.4f}"
              f"  ({n_valid} valid evals)  [{run_dir.name}]")

    if not results:
        print("No results found.")
        return

    f_vals = [v['f_tile_soil'] for v in results.values()]
    kge_vals = [v['kge'] for v in results.values()]
    mean_ftile = sum(f_vals) / len(f_vals)
    mean_kge   = sum(kge_vals) / len(kge_vals)
    print(f"\nDecades with results : {len(results)}/{len(VALID_DECADES)}")
    print(f"Mean f_tile_soil     : {mean_ftile:.4f}")
    print(f"Mean KGE             : {mean_kge:.4f}")

    if args.save:
        summary = {
            'desc':             args.desc,
            'mean_f_tile_soil': round(mean_ftile, 6),
            'mean_kge':         round(mean_kge, 4),
            'decades':          results,
        }
        with open(args.save, 'w') as f:
            yaml.dump(summary, f, default_flow_style=False, sort_keys=True,
                      allow_unicode=True)
        print(f"Saved: {args.save}")


if __name__ == '__main__':
    main()
