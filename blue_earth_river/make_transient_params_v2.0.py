#!/usr/bin/env python3
"""
Generate params_transient_v2.0.yml (and later) for every calibrated decade directory.

v2.0 architecture (Blue Earth River):
  - 3 reservoirs: soil (b=2 Dupuit-Forchheimer, Hmax calibrated) → shallow till (b=1 linear)
                  → deep till (b=1 linear)
  - backbone fixed: shallow+deep till recession (2) + snow/FGI (2) + f_exfil_shallow_till (1),
                    from backbone_v2.x evaluations.dat
  - 4 active per-decade params: log__recession_coeff_soil, f_exfiltration_soil,
                                log__Hmax_soil, et_scale

Usage:
    python make_transient_params_v2.0.py --backbone backbone_runs/<run_dir>/evaluations.dat
    python make_transient_params_v2.0.py --backbone ... --version 2.1
"""

import argparse
import yaml
from pathlib import Path

BACKBONE_DEFAULTS = {
    'log__recession_coeff_shallow_till': 3.5,
    'log__recession_coeff_deep_till':    4.5,
    'PDD_melt_factor':                   5.0,
    'log__fdd_threshold':                2.5,
    'f_exfiltration_shallow_till':       0.5,
    # fixed physics
    'snow_insulation_k':                 0.0,
    'f_direct_runoff':                   0.0,
    'baseflow_Q':                        0.0,
    'log__routing_K':                    0.0,
    'et_alpha':                          1.0,
}

VALID_DECADES = [
    ('1951-01-01', '1960-12-31'),
    ('1961-01-01', '1970-12-31'),
    ('1971-01-01', '1980-12-31'),
    ('1981-01-01', '1990-12-31'),
    ('1991-01-01', '2000-12-31'),
    ('2001-01-01', '2010-12-31'),
    ('2011-01-01', '2020-12-31'),
]
DECADE_DIRS = sorted(Path('decades').glob('????-????'))


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
        raise RuntimeError(f"No valid evals in {eval_path}")
    best = min(valid, key=lambda r: r['neg_kge'])
    kge  = 1.0 - best['neg_kge']
    print(f"Backbone best: mean KGE = {kge:.4f}")
    return best, kge


def make_params(decade_dir, backbone, start, end, is_first, ver):
    return {
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
            'config_template':       'blue_earth_config_v2.yml',
            'metric':                'KGE_logKGE',
            'spin_up_cycles':        1 if is_first else 0,
            'routing_N':             2,
            'n_reservoirs':          3,
            'reservoir_order':       ['soil', 'shallow_till', 'deep_till'],
            'decade_start':          start,
            'decade_end':            end,
            'enforce_water_balance': 'none',
        },
        'parameters': {
            # ---- PER-DECADE ACTIVE (4) ----
            'log__recession_coeff_soil': {
                'description': 'log10 soil recession coefficient κ [days] — per-decade tile-drain efficiency proxy',
                'lower': 1.0, 'upper': 4.5, 'initial': 1.782, 'fixed': 1.782,
                'active': True,
            },
            'f_exfiltration_soil': {
                'description': 'fraction of soil drainage to stream (remainder recharges shallow till) — per-decade',
                'lower': 0.01, 'upper': 0.99, 'initial': 0.70, 'fixed': 0.70,
                'active': True,
            },
            'et_scale': {
                'description': 'Thornthwaite ET multiplier (land cover / decade)',
                'lower': 0.3, 'upper': 2.0, 'initial': 1.0, 'fixed': 1.0,
                'active': True,
            },
            'log__Hmax_soil': {
                'description': 'log10 soil reservoir max storage [mm] — tile-drain ceiling; '
                               'large=undrained, small=heavily drained',
                'lower': 1.0, 'upper': 3.0, 'initial': 2.0, 'fixed': 2.0,
                'active': True,
            },
            # ---- BACKBONE FIXED ----
            'log__recession_coeff_shallow_till': {
                'description': f'log10 shallow till recession τ [days] — backbone_v{ver} fixed',
                'lower': 1.0, 'upper': 5.0,
                'initial': backbone['log__recession_coeff_shallow_till'],
                'fixed':   backbone['log__recession_coeff_shallow_till'],
                'active': False,
            },
            'log__recession_coeff_deep_till': {
                'description': f'log10 deep/dense till recession τ [days] — backbone_v{ver} fixed',
                'lower': 2.5, 'upper': 5.5,
                'initial': backbone['log__recession_coeff_deep_till'],
                'fixed':   backbone['log__recession_coeff_deep_till'],
                'active': False,
            },
            'PDD_melt_factor': {
                'description': f'degree-day snowmelt rate — backbone_v{ver} fixed',
                'lower': 0.1, 'upper': 10.0,
                'initial': backbone['PDD_melt_factor'],
                'fixed':   backbone['PDD_melt_factor'],
                'active': False,
            },
            'log__fdd_threshold': {
                'description': f'log10 FGI threshold [degC·day] — backbone_v{ver} fixed',
                'lower': 0.0, 'upper': 3.0,
                'initial': backbone['log__fdd_threshold'],
                'fixed':   backbone['log__fdd_threshold'],
                'active': False,
            },
            'f_exfiltration_shallow_till': {
                'description': f'fraction of shallow till drainage to stream — backbone_v{ver} fixed',
                'lower': 0.01, 'upper': 0.99,
                'initial': backbone['f_exfiltration_shallow_till'],
                'fixed':   backbone['f_exfiltration_shallow_till'],
                'active': False,
            },
            # ---- FIXED PHYSICS ----
            'recession_b_soil': {
                'description': 'soil recession exponent — fixed at 2 (Dupuit-Forchheimer)',
                'lower': 1.5, 'upper': 6.0, 'initial': 2.0, 'fixed': 2.0,
                'active': False,
            },
            'snow_insulation_k': {
                'description': 'snow insulation — inactive',
                'lower': 0.0, 'upper': 0.5,
                'initial': backbone['snow_insulation_k'],
                'fixed':   backbone['snow_insulation_k'],
                'active': False,
            },
            'f_direct_runoff': {
                'description': 'fast-bypass fraction — inactive',
                'lower': 0.0, 'upper': 0.5,
                'initial': backbone['f_direct_runoff'],
                'fixed':   backbone['f_direct_runoff'],
                'active': False,
            },
            'baseflow_Q': {
                'description': 'regional GW import — inactive',
                'lower': 0.0, 'upper': 0.5,
                'initial': backbone['baseflow_Q'],
                'fixed':   backbone['baseflow_Q'],
                'active': False,
            },
            'log__routing_K': {
                'description': 'Nash-cascade K — inactive',
                'lower': -1.0, 'upper': 1.0,
                'initial': backbone['log__routing_K'],
                'fixed':   backbone['log__routing_K'],
                'active': False,
            },
            'et_alpha': {
                'description': 'ET partition fraction — fixed',
                'lower': 0.01, 'upper': 0.99,
                'initial': backbone['et_alpha'],
                'fixed':   backbone['et_alpha'],
                'active': False,
            },
            # ---- CHAINED INITIAL CONDITIONS ----
            'log__H0_soil': {
                'description': 'log10 initial soil H [mm] — set by IC chain',
                'lower': 0.0, 'upper': 4.0, 'initial': 1.7, 'fixed': 1.7,
                'active': False,
            },
            'log__H0_shallow_till': {
                'description': 'log10 initial shallow till H [mm] — set by IC chain',
                'lower': 0.0, 'upper': 5.0, 'initial': 2.7, 'fixed': 2.7,
                'active': False,
            },
            'log__H0_deep_till': {
                'description': 'log10 initial deep till H [mm] — set by IC chain',
                'lower': 0.0, 'upper': 6.0, 'initial': 3.3, 'fixed': 3.3,
                'active': False,
            },
            'H0_snowpack': {
                'description': 'initial snowpack SWE [mm] — set by IC chain',
                'lower': 0.0, 'upper': 500.0, 'initial': 0.0, 'fixed': 0.0,
                'active': False,
            },
            'H0_fgi': {
                'description': 'initial frozen ground index [degC·day] — set by IC chain',
                'lower': 0.0, 'upper': 500.0, 'initial': 0.0, 'fixed': 0.0,
                'active': False,
            },
            'H0_deficit_carry': {
                'description': 'initial ET deficit carry [mm] — 0 for first decade',
                'lower': -1e6, 'upper': 1e6, 'initial': 0.0, 'fixed': 0.0,
                'active': False,
            },
        },
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--backbone', default=None,
                        help='Path to backbone evaluations.dat')
    parser.add_argument('--version', default='2.0',
                        help='Version label for output filenames (default: 2.0)')
    args = parser.parse_args()
    ver = args.version

    if args.backbone:
        best, _ = load_backbone_best(args.backbone)
        backbone = {k: best.get(k, BACKBONE_DEFAULTS[k]) for k in BACKBONE_DEFAULTS}
    else:
        print("No backbone run provided; using default initial values.")
        backbone = BACKBONE_DEFAULTS.copy()

    valid_decade_names = {s[:4] + '-' + str(int(s[:4]) + 9) for s, e in VALID_DECADES}

    first_decade = True
    for decade_dir in DECADE_DIRS:
        if decade_dir.name not in valid_decade_names:
            continue
        year_start = int(decade_dir.name[:4])
        start = f'{year_start}-01-01'
        end   = f'{year_start + 9}-12-31'

        p = make_params(decade_dir, backbone, start, end, is_first=first_decade, ver=ver)
        out_path = decade_dir / f'params_transient_v{ver}.yml'

        with open(out_path, 'w') as f:
            f.write(f"# {decade_dir.name}: transient calibration v{ver}.\n")
            f.write(f"# Backbone fixed (backbone_v{ver}); 4 active: "
                    f"log__recession_coeff_soil, f_exfiltration_soil, et_scale, log__Hmax_soil.\n")
            f.write(f"# b_soil=2 fixed; 3-reservoir soil/shallow_till/deep_till architecture.\n")
            if first_decade:
                f.write(f"# spin_up_cycles=1 (first decade, analytical SS start).\n\n")
            else:
                f.write(f"# spin_up_cycles=0 (chained from prior decade).\n\n")
            yaml.dump(p, f, default_flow_style=False, sort_keys=False,
                      allow_unicode=True)
        print(f"Written: {out_path}")
        first_decade = False


if __name__ == '__main__':
    main()
