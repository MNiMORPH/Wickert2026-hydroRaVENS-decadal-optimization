#!/usr/bin/env python3
"""
Generate params_transient_v6.0_H_thr.yml in each calibrated decade dir.

v6 per-decade experiment #2: H_threshold (multipath activation depth) per decade.
Tests whether effective tile-drain depth changed across decades — a parallel
test to the τ_multipath experiment. Together they complete the tile-expansion
investigation in the multipath architecture.

Active per decade (1): log__multipath_threshold_till.
Fixed (v6.1 best-fit, plus FGI off per v6.2 sanity check):
  PDD, log__recession_coeff_till, log__multipath_timescale_till.
"""

import yaml
from pathlib import Path

V61 = {
    'PDD_melt_factor':                 6.0457,
    'log__fdd_threshold':              1.1861,   # irrelevant — FGI module off
    'log__recession_coeff_till':       2.7184,
    'log__multipath_threshold_till':   2.1068,
    'log__multipath_timescale_till':   1.3678,
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
            'frozen_ground':     False,   # v6.2 confirmed FGI redundant
            'rain_on_snow':      True,
            'direct_runoff':     False,
            'dtr_fgi_decay':     False,
            'et_water_stress':   False,
            'et_reservoir_draw': True,
        },
        'dakota': {
            'ego_initial_samples':      80,
            'ego_seed':                 42,
            'ps_max_evaluations':       250,
            'ps_convergence_tolerance': 1.0e-5,
            'evaluation_concurrency':   8,
        },
        'driver': {
            'config_template':       'blue_earth_config_v6.yml',
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
            'log__multipath_threshold_till': {
                'description': 'log10 multipath H_thr — only per-decade active (tile-depth test)',
                'lower': 0.5, 'upper': 3.0,
                'initial': V61['log__multipath_threshold_till'],
                'fixed':   V61['log__multipath_threshold_till'],
                'active': True,
            },
            'PDD_melt_factor': {
                'description': 'degree-day snowmelt rate — v6.1 fixed',
                'lower': 0.1, 'upper': 10.0,
                'initial': V61['PDD_melt_factor'],
                'fixed':   V61['PDD_melt_factor'],
                'active': False,
            },
            'log__recession_coeff_till': {
                'description': 'log10 matrix τ — v6.1 fixed (global)',
                'lower': 0.5, 'upper': 4.0,
                'initial': V61['log__recession_coeff_till'],
                'fixed':   V61['log__recession_coeff_till'],
                'active': False,
            },
            'log__multipath_timescale_till': {
                'description': 'log10 multipath τ_mp — v6.1 fixed (global)',
                'lower': 0.0, 'upper': 2.0,
                'initial': V61['log__multipath_timescale_till'],
                'fixed':   V61['log__multipath_timescale_till'],
                'active': False,
            },
            'log__fdd_threshold': {
                'description': 'FGI threshold — inactive (frozen_ground off per v6.2)',
                'lower': 0.0, 'upper': 4.0,
                'initial': V61['log__fdd_threshold'],
                'fixed':   V61['log__fdd_threshold'],
                'active': False,
            },
            'recession_b_till': {
                'description': 'b — linear matrix (v6 default)',
                'lower': 1.0, 'upper': 4.5, 'initial': 1.0, 'fixed': 1.0, 'active': False,
            },
            'et_scale': {
                'description': 'Thornthwaite ET scaling — D3 mean fixed (0.755)',
                'lower': 0.3, 'upper': 2.0, 'initial': 0.755, 'fixed': 0.755, 'active': False,
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
                'lower': 0.0, 'upper': 5.0, 'initial': 2.0, 'fixed': 2.0, 'active': False,
            },
            'H0_snowpack': {
                'description': 'initial snowpack SWE [mm] — set by IC chain',
                'lower': 0.0, 'upper': 500.0, 'initial': 0.0, 'fixed': 0.0, 'active': False,
            },
            'H0_fgi': {
                'description': 'initial frozen ground index — irrelevant (FGI off)',
                'lower': 0.0, 'upper': 500.0, 'initial': 0.0, 'fixed': 0.0, 'active': False,
            },
            'H0_deficit_carry': {
                'description': 'initial ET deficit carry [mm]',
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
        out = d / 'params_transient_v6.0_H_thr.yml'
        with open(out, 'w') as f:
            f.write(f"# {d.name}: v6.0 per-decade H_threshold calibration.\n")
            f.write(f"# Active (1): log__multipath_threshold_till.\n")
            f.write(f"# Fixed: all snow + matrix τ + τ_mp at v6.1 best-fit; FGI off.\n\n")
            yaml.dump(p, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
        print(f"Written: {out}")
        first = False


if __name__ == '__main__':
    main()
