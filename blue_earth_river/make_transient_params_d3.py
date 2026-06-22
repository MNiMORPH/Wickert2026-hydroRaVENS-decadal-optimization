#!/usr/bin/env python3
"""
Generate params_transient_d3.yml in each calibrated decade dir.

D3: ET-only per-decade calibration.
  - All hydraulic + snow params fixed at D2a best-fit (b=2 static).
  - Only et_scale active, [0.3, 2.0], per decade.
  - Chained ICs through log__H0_till + snowpack/FGI states.

Tests whether decadal variability is captured by ET (vs. genuine hydraulic change).
"""

import yaml
from pathlib import Path

# D2a best-fit (b=2, static, mean KGE=0.611)
D2A = {
    'PDD_melt_factor':           4.2145,
    'log__fdd_threshold':        0.9999,
    'log__recession_coeff_till': 2.4778,
    'log__Hmax_till':            3.3315,
    'recession_b_till':          2.0,
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


def make_params(start, end, is_first):
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
            'ego_initial_samples':      80,
            'ego_seed':                 42,
            'ps_max_evaluations':       200,
            'ps_convergence_tolerance': 1.0e-5,
            'evaluation_concurrency':   8,
        },
        'driver': {
            'config_template':       'blue_earth_config_v3.yml',
            'metric':                'KGE_logKGE',
            'spin_up_cycles':        1 if is_first else 0,
            'routing_N':             2,
            'n_reservoirs':          1,
            'reservoir_order':       ['till'],
            'decade_start':          start,
            'decade_end':            end,
            'enforce_water_balance': 'none',
        },
        'parameters': {
            'et_scale': {
                'description': 'Thornthwaite ET multiplier — only active per-decade param (D3)',
                'lower': 0.3, 'upper': 2.0,
                'initial': 1.0, 'fixed': 1.0,
                'active': True,
            },
            'PDD_melt_factor': {
                'description': 'degree-day snowmelt rate — D2a fixed',
                'lower': 0.1, 'upper': 10.0,
                'initial': D2A['PDD_melt_factor'],
                'fixed':   D2A['PDD_melt_factor'],
                'active': False,
            },
            'log__fdd_threshold': {
                'description': 'log10 FGI threshold — D2a fixed',
                'lower': 0.0, 'upper': 3.0,
                'initial': D2A['log__fdd_threshold'],
                'fixed':   D2A['log__fdd_threshold'],
                'active': False,
            },
            'log__recession_coeff_till': {
                'description': 'log10 till+tile κ [days] — D2a fixed (global)',
                'lower': 0.0, 'upper': 3.5,
                'initial': D2A['log__recession_coeff_till'],
                'fixed':   D2A['log__recession_coeff_till'],
                'active': False,
            },
            'log__Hmax_till': {
                'description': 'log10 Hmax_till [mm] — D2a fixed (global)',
                'lower': 1.0, 'upper': 3.5,
                'initial': D2A['log__Hmax_till'],
                'fixed':   D2A['log__Hmax_till'],
                'active': False,
            },
            'recession_b_till': {
                'description': 'till+tile b — Dupuit (D2a)',
                'lower': 1.0, 'upper': 4.5,
                'initial': D2A['recession_b_till'],
                'fixed':   D2A['recession_b_till'],
                'active': False,
            },
            'snow_insulation_k': {
                'description': 'snow insulation — inactive',
                'lower': 0.0, 'upper': 0.5, 'initial': 0.0, 'fixed': 0.0, 'active': False,
            },
            'f_direct_runoff': {
                'description': 'fast-bypass fraction — inactive',
                'lower': 0.0, 'upper': 0.5, 'initial': 0.0, 'fixed': 0.0, 'active': False,
            },
            'baseflow_Q': {
                'description': 'regional GW import — inactive',
                'lower': 0.0, 'upper': 0.5, 'initial': 0.0, 'fixed': 0.0, 'active': False,
            },
            'log__routing_K': {
                'description': 'Nash-cascade K — inactive',
                'lower': -1.0, 'upper': 1.0, 'initial': 0.0, 'fixed': 0.0, 'active': False,
            },
            'et_alpha': {
                'description': 'ET partition fraction — fixed',
                'lower': 0.01, 'upper': 0.99, 'initial': 1.0, 'fixed': 1.0, 'active': False,
            },
            'log__H0_till': {
                'description': 'log10 initial till+tile H [mm] — set by IC chain',
                'lower': 0.0, 'upper': 5.0, 'initial': 2.7, 'fixed': 2.7, 'active': False,
            },
            'H0_snowpack': {
                'description': 'initial snowpack SWE [mm] — set by IC chain',
                'lower': 0.0, 'upper': 500.0, 'initial': 0.0, 'fixed': 0.0, 'active': False,
            },
            'H0_fgi': {
                'description': 'initial frozen ground index [degC·day] — set by IC chain',
                'lower': 0.0, 'upper': 500.0, 'initial': 0.0, 'fixed': 0.0, 'active': False,
            },
            'H0_deficit_carry': {
                'description': 'initial ET deficit carry [mm] — 0 for first decade',
                'lower': -1e6, 'upper': 1e6, 'initial': 0.0, 'fixed': 0.0, 'active': False,
            },
        },
    }


def main():
    valid_names = {s[:4] + '-' + str(int(s[:4]) + 9) for s, _ in VALID_DECADES}
    first = True
    for d in DECADE_DIRS:
        if d.name not in valid_names:
            continue
        y0 = int(d.name[:4])
        start, end = f'{y0}-01-01', f'{y0+9}-12-31'
        p = make_params(start, end, is_first=first)
        out = d / 'params_transient_d3.yml'
        with open(out, 'w') as f:
            f.write(f"# {d.name}: D3 ET-only per-decade calibration.\n")
            f.write(f"# Active (1): et_scale.\n")
            f.write(f"# Fixed: all snow + hydraulic params at D2a static best-fit (b=2).\n\n")
            yaml.dump(p, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
        print(f"Written: {out}")
        first = False


if __name__ == '__main__':
    main()
