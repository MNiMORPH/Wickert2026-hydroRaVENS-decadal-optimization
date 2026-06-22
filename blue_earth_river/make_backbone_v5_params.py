#!/usr/bin/env python3
"""
Create params_backbone_v5.0.yml from the final converged v3.x results.

Seeds:
  - PDD_melt_factor, log__fdd_threshold: best-fit from v3.x backbone evaluations.dat
  - log__recession_coeff_till, per_decade_k_till: from final v3.x transient ktill YAML
  - recession_b_till: 2.0 (Dupuit-Forchheimer starting point; refined by v5 transients)
  - per_decade_b_till: all 2.0 initially

Usage:
    python make_backbone_v5_params.py \\
        --from-backbone backbone_runs/TIMESTAMP_backbone_v3.X/evaluations.dat \\
        --ktill-summary ktill_v3.X.yml
"""

import argparse
import yaml
from pathlib import Path

DECADES = [
    {'start': '1951-01-01', 'end': '1960-12-31'},
    {'start': '1961-01-01', 'end': '1970-12-31'},
    {'start': '1971-01-01', 'end': '1980-12-31'},
    {'start': '1981-01-01', 'end': '1990-12-31'},
    {'start': '1991-01-01', 'end': '2000-12-31'},
    {'start': '2001-01-01', 'end': '2010-12-31'},
    {'start': '2011-01-01', 'end': '2020-12-31'},
]


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
    print(f"Source backbone best: mean KGE = {kge:.4f}")
    return best, kge


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--from-backbone', required=True,
                        help='Path to final v3.x backbone evaluations.dat')
    parser.add_argument('--ktill-summary', required=True,
                        help='YAML from extract_ktill_best.py for final v3.x transient')
    args = parser.parse_args()

    best, kge = load_backbone_best(args.from_backbone)
    pdd = round(float(best.get('PDD_melt_factor', 5.0)), 6)
    fgi = round(float(best.get('log__fdd_threshold', 2.5)), 6)
    print(f"PDD_melt_factor={pdd}  log__fdd_threshold={fgi}")

    with open(args.ktill_summary) as f:
        ktill = yaml.safe_load(f)
    mean_log_k = round(float(ktill['mean_log__recession_coeff_till']), 6)
    mean_kappa = round(float(ktill['mean_kappa_till_days']), 2)
    per_decade_k_till = {
        decade: round(float(data['log__recession_coeff_till']), 6)
        for decade, data in ktill['decades'].items()
    }
    per_decade_b_till = {
        decade: 2.0 for decade in ktill['decades']
    }
    print(f"mean log__recession_coeff_till = {mean_log_k:.4f}  (κ = {mean_kappa:.1f} d)")
    print(f"recession_b_till: all decades seeded at 2.0 (Dupuit-Forchheimer)")

    cfg = {
        'modules': {
            'snowpack':          True,
            'frozen_ground':     True,
            'rain_on_snow':      True,
            'direct_runoff':     False,
            'dtr_fgi_decay':     True,
            'et_water_stress':   False,
            'et_reservoir_draw': True,
        },
        'dakota': {
            'ego_initial_samples':      200,
            'ego_seed':                 42,
            'ps_max_evaluations':       500,
            'ps_convergence_tolerance': 1.0e-5,
            'evaluation_concurrency':   8,
        },
        'driver': {
            'config_template':       'blue_earth_config_v5.yml',
            'metric':                'KGE_logKGE',
            'spin_up_cycles':        1,
            'routing_N':             2,
            'n_reservoirs':          1,
            'reservoir_order':       ['till'],
            'enforce_water_balance': 'global',
            'min_obs':               3000,
            'decades':               DECADES,
            'per_decade_k_till':     per_decade_k_till,
            'per_decade_b_till':     per_decade_b_till,
        },
        'parameters': {
            'PDD_melt_factor': {
                'description': 'degree-day snowmelt rate [mm SWE / degC / day]',
                'lower': 0.1, 'upper': 10.0, 'initial': pdd, 'fixed': pdd,
                'active': True,
            },
            'log__fdd_threshold': {
                'description': 'log10 frozen-ground-index threshold [degC·day]',
                'lower': 0.0, 'upper': 3.0, 'initial': fgi, 'fixed': fgi,
                'active': True,
            },
            'log__recession_coeff_till': {
                'description': ('log10 till+tile recession coefficient κ [days] — '
                                'fixed at v3.x mean; per-decade in transient'),
                'lower': 1.0, 'upper': 4.5,
                'initial': mean_log_k, 'fixed': mean_log_k,
                'active': False,
            },
            'recession_b_till': {
                'description': ('till+tile recession exponent b — fixed at global mean; '
                                'per-decade in transient'),
                'lower': 1.0, 'upper': 4.5, 'initial': 2.0, 'fixed': 2.0,
                'active': False,
            },
            'snow_insulation_k': {
                'description': 'snow insulation — inactive',
                'lower': 0.0, 'upper': 0.5, 'initial': 0.0, 'fixed': 0.0,
                'active': False,
            },
            'et_scale': {
                'description': 'ET multiplier — inactive (global WB enforcement in backbone)',
                'lower': 0.5, 'upper': 2.0, 'initial': 1.0, 'fixed': 1.0,
                'active': False,
            },
            'et_alpha': {
                'description': 'ET partition fraction — fixed',
                'lower': 0.01, 'upper': 0.99, 'initial': 1.0, 'fixed': 1.0,
                'active': False,
            },
            'f_direct_runoff': {
                'description': 'fast-bypass fraction — inactive',
                'lower': 0.0, 'upper': 0.5, 'initial': 0.0, 'fixed': 0.0,
                'active': False,
            },
            'baseflow_Q': {
                'description': 'regional groundwater import — inactive',
                'lower': 0.0, 'upper': 0.5, 'initial': 0.0, 'fixed': 0.0,
                'active': False,
            },
            'log__routing_K': {
                'description': 'Nash-cascade K — inactive',
                'lower': -1.0, 'upper': 1.0, 'initial': 0.0, 'fixed': 0.0,
                'active': False,
            },
        },
    }

    out_path = Path('params_backbone_v5.0.yml')
    src_ver = Path(args.ktill_summary).stem.split('_v')[-1] if '_v' in args.ktill_summary else '3.x'
    with open(out_path, 'w') as f:
        f.write(f"# Backbone calibration v5.0 — 1-reservoir till+tile, free b (Blue Earth River).\n")
        f.write(f"#\n")
        f.write(f"# Seeded from final v3.x results (backbone KGE={kge:.4f}).\n")
        f.write(f"# log__recession_coeff_till: per-decade from {src_ver} transient"
                f" (mean={mean_log_k:.4f}, κ={mean_kappa:.1f} d).\n")
        f.write(f"# recession_b_till: seeded at 2.0 (Dupuit-Forchheimer); refined by v5 transient.\n")
        f.write(f"#\n")
        f.write(f"# Active (2 params): PDD_melt_factor, log__fdd_threshold (snow-only).\n")
        f.write(f"# Fixed: κ_till and b_till per decade (driver.per_decade_k_till / per_decade_b_till).\n")
        f.write(f"# No Hmax.\n")
        f.write(f"#\n")
        yaml.dump(cfg, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
    print(f"Written: {out_path}")


if __name__ == '__main__':
    main()
