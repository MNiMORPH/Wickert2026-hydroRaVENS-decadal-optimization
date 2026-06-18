#!/usr/bin/env python3
"""
Generate params_transient_v5.0.yml for every calibrated decade directory.

v5.0 architecture:
  - backbone fixed: geology + snow + tau_tile (from backbone_v5.0 evaluations.dat)
  - b_soil = 2 fixed (Dupuit-Forchheimer)
  - 4 active per-decade params: log__recession_coeff_soil, f_tile_soil,
                                 f_exfiltration_soil, et_scale

Usage:
    python make_transient_params_v5.0.py --backbone backbone_runs/<run_dir>/evaluations.dat
    python make_transient_params_v5.0.py  # uses hardcoded defaults
"""

import argparse
import yaml
from pathlib import Path

# ---------------------------------------------------------------------------
# Backbone defaults: update after backbone_v5.0 completes.
# ---------------------------------------------------------------------------
BACKBONE_DEFAULTS = {
    'log__recession_coeff_intermediate': 3.0,
    'log__recession_coeff_deep':         4.3,
    'log__leakance_R_intermediate':      3.75,
    'f_exfiltration_deep':               0.40,
    'log__H_threshold_deep':             2.1,
    'PDD_melt_factor':                   8.0,
    'log__fdd_threshold':                2.37,
    'log__tau_tile':                     1.0,   # 10 days; update from backbone_v5.0
    # fixed physics (not from backbone optimizer)
    'recession_b_intermediate':          2.203,
    'f_exfiltration_intermediate':       0.012,
    'snow_insulation_k':                 0.0,
    'f_direct_runoff':                   0.0,
    'baseflow_Q':                        0.0,
    'log__routing_K':                    0.0,
    'et_alpha':                          1.0,
}

VALID_DECADES = [
    ('1931-01-01', '1940-12-31'),
    ('1941-01-01', '1950-12-31'),
    ('1951-01-01', '1960-12-31'),
    ('1961-01-01', '1970-12-31'),
    ('1991-01-01', '2000-12-31'),
    ('2001-01-01', '2010-12-31'),
    ('2011-01-01', '2020-12-31'),
]
DECADE_DIRS = sorted(Path('decades').glob('????-????'))


def load_backbone_best(eval_path):
    """Extract best-fit backbone values from evaluations.dat."""
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
    print(f"Backbone_v5.0 best: mean KGE = {kge:.4f}")
    return best, kge


def make_params(decade_dir, backbone, start, end, is_first):
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
            'config_template':       'cannon_config_1893_2024.yml',
            'metric':                'KGE_logKGE',
            'spin_up_cycles':        1 if is_first else 0,
            'routing_N':             2,
            'n_reservoirs':          3,
            'reservoir_order':       ['soil', 'intermediate', 'deep'],
            'decade_start':          start,
            'decade_end':            end,
            'enforce_water_balance': 'none',
        },
        'parameters': {
            # ---- PER-DECADE ACTIVE (4) ----
            'log__recession_coeff_soil': {
                'description': 'log10 soil recession coefficient κ [days; e-folding time iff b=1]',
                'lower': 1.0, 'upper': 4.5, 'initial': 3.5, 'fixed': 3.5,
                'active': True,
            },
            'f_tile_soil': {
                'description': 'fraction of soil H_to_next to tile-drain sub-reservoir (per-decade)',
                'lower': 0.0, 'upper': 0.99, 'initial': 0.3, 'fixed': 0.3,
                'active': True,
            },
            'f_exfiltration_soil': {
                'description': 'fraction of soil drainage to stream',
                'lower': 0.01, 'upper': 0.99, 'initial': 0.53, 'fixed': 0.53,
                'active': True,
            },
            'et_scale': {
                'description': 'Thornthwaite ET multiplier (land cover / decade)',
                'lower': 0.3, 'upper': 2.0, 'initial': 1.0, 'fixed': 1.0,
                'active': True,
            },
            # ---- BACKBONE FIXED ----
            'log__recession_coeff_intermediate': {
                'description': 'log10 PdC recession coefficient κ [days; e-folding time iff b=1] — backbone_v5.0 fixed',
                'lower': 1.0, 'upper': 5.0,
                'initial': backbone['log__recession_coeff_intermediate'],
                'fixed':   backbone['log__recession_coeff_intermediate'],
                'active': False,
            },
            'log__recession_coeff_deep': {
                'description': 'log10 Wonewoc recession coefficient κ [days; e-folding time iff b=1] — backbone_v5.0 fixed',
                'lower': 3.0, 'upper': 5.5,
                'initial': backbone['log__recession_coeff_deep'],
                'fixed':   backbone['log__recession_coeff_deep'],
                'active': False,
            },
            'log__leakance_R_intermediate': {
                'description': 'log10 St. Lawrence shale leakance resistance [days] — backbone_v5.0 fixed',
                'lower': 0.5, 'upper': 5.0,
                'initial': backbone['log__leakance_R_intermediate'],
                'fixed':   backbone['log__leakance_R_intermediate'],
                'active': False,
            },
            'f_exfiltration_deep': {
                'description': 'Wonewoc fraction to stream — backbone_v5.0 fixed',
                'lower': 0.01, 'upper': 0.99,
                'initial': backbone['f_exfiltration_deep'],
                'fixed':   backbone['f_exfiltration_deep'],
                'active': False,
            },
            'log__H_threshold_deep': {
                'description': 'log10 Wonewoc spring sill [mm] — backbone_v5.0 fixed',
                'lower': 0.0, 'upper': 3.5,
                'initial': backbone['log__H_threshold_deep'],
                'fixed':   backbone['log__H_threshold_deep'],
                'active': False,
            },
            'PDD_melt_factor': {
                'description': 'degree-day snowmelt rate — backbone_v5.0 fixed',
                'lower': 0.1, 'upper': 10.0,
                'initial': backbone['PDD_melt_factor'],
                'fixed':   backbone['PDD_melt_factor'],
                'active': False,
            },
            'log__fdd_threshold': {
                'description': 'log10 FGI threshold [degC·day] — backbone_v5.0 fixed',
                'lower': 0.0, 'upper': 3.0,
                'initial': backbone['log__fdd_threshold'],
                'fixed':   backbone['log__fdd_threshold'],
                'active': False,
            },
            'log__tau_tile': {
                'description': 'log10 tile-drain e-folding time [days] — backbone_v5.0 fixed',
                'lower': 0.0, 'upper': 2.0,
                'initial': backbone['log__tau_tile'],
                'fixed':   backbone['log__tau_tile'],
                'active': False,
            },
            # ---- FIXED PHYSICS ----
            'recession_b_soil': {
                'description': 'soil recession exponent — fixed at 2 (Dupuit-Forchheimer)',
                'lower': 1.5, 'upper': 6.0, 'initial': 2.0, 'fixed': 2.0,
                'active': False,
            },
            'recession_b_intermediate': {
                'description': 'PdC recession exponent — Brutsaert-Nieber fixed',
                'lower': 1.0, 'upper': 6.0,
                'initial': backbone['recession_b_intermediate'],
                'fixed':   backbone['recession_b_intermediate'],
                'active': False,
            },
            'f_exfiltration_intermediate': {
                'description': 'dead param under leakance junction',
                'lower': 0.01, 'upper': 0.99,
                'initial': backbone['f_exfiltration_intermediate'],
                'fixed':   backbone['f_exfiltration_intermediate'],
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
            # ---- CHAINED INITIAL CONDITIONS (updated by run_transient.sh) ----
            'log__H0_soil': {
                'description': 'log10 initial soil H [mm] — set by IC chain',
                'lower': 0.0, 'upper': 4.0, 'initial': 1.7, 'fixed': 1.7,
                'active': False,
            },
            'log__H0_intermediate': {
                'description': 'log10 initial PdC H [mm] — set by IC chain',
                'lower': 0.0, 'upper': 5.0, 'initial': 2.0, 'fixed': 2.0,
                'active': False,
            },
            'log__H0_deep': {
                'description': 'log10 initial Wonewoc H [mm] — set by IC chain',
                'lower': 0.0, 'upper': 5.0, 'initial': 2.5, 'fixed': 2.5,
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
    parser.add_argument('--version', default='5.0',
                        help='Version label written into output filenames and headers (default: 5.0)')
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

        params = make_params(decade_dir, backbone, start, end, is_first=first_decade)
        out_path = decade_dir / f'params_transient_v{ver}.yml'

        with open(out_path, 'w') as f:
            f.write(f"# {decade_dir.name}: transient calibration v{ver}.\n")
            f.write(f"# Backbone fixed (backbone_v{ver}); 4 active: "
                    f"log__recession_coeff_soil, f_tile_soil, f_exfiltration_soil, et_scale.\n")
            f.write(f"# b_soil=2 fixed (Dupuit-Forchheimer); tau_tile fixed from backbone_v{ver}.\n")
            if first_decade:
                f.write(f"# spin_up_cycles=1 (first decade, analytical SS start).\n\n")
            else:
                f.write(f"# spin_up_cycles=0 (chained from prior decade).\n\n")
            yaml.dump(params, f, default_flow_style=False, sort_keys=False,
                      allow_unicode=True)
        print(f"Written: {out_path}")
        first_decade = False


if __name__ == '__main__':
    main()
