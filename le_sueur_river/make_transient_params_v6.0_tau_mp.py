#!/usr/bin/env python3
"""
Generate per-decade params_transient_v6.0_tau_mp.yml for Le Sueur River.

Mirrors BLR's per-decade τ_multipath diagnostic. Tests whether τ_mp
shows a monotonic trend over decades when other params held at LSR
v6 (1941-2020) best-fit.

Active per decade (1): log__multipath_timescale_till.
Fixed at LSR v6 1941 best-fit: PDD, log_κ, log_H_thr.
"""

import yaml
from pathlib import Path

# LSR v6 1941-2020 best-fit (KGE = 0.7792)
LSR = {
    'PDD_melt_factor':                 6.6797,
    'log__recession_coeff_till':       2.6572,
    'log__multipath_threshold_till':   2.0282,
    'log__multipath_timescale_till':   1.1596,
}

VALID_DECADES = [
    ('1941-01-01', '1950-12-31'),
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
            'frozen_ground':     False,
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
            'config_template':       'le_sueur_config_v6.yml',
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
            'log__multipath_timescale_till': {
                'description': 'log10 multipath τ — only per-decade active (tile-rate test)',
                'lower': 0.0, 'upper': 2.0,
                'initial': LSR['log__multipath_timescale_till'],
                'fixed':   LSR['log__multipath_timescale_till'],
                'active': True,
            },
            'PDD_melt_factor': {
                'description': 'PDD — LSR v6 fixed',
                'lower': 0.1, 'upper': 10.0,
                'initial': LSR['PDD_melt_factor'],
                'fixed':   LSR['PDD_melt_factor'],
                'active': False,
            },
            'log__recession_coeff_till': {
                'description': 'log10 matrix τ — LSR v6 fixed (global)',
                'lower': 0.5, 'upper': 4.0,
                'initial': LSR['log__recession_coeff_till'],
                'fixed':   LSR['log__recession_coeff_till'],
                'active': False,
            },
            'log__multipath_threshold_till': {
                'description': 'log10 multipath H_thr — LSR v6 fixed (global)',
                'lower': 0.5, 'upper': 3.0,
                'initial': LSR['log__multipath_threshold_till'],
                'fixed':   LSR['log__multipath_threshold_till'],
                'active': False,
            },
            'log__fdd_threshold': {
                'description': 'FGI threshold — inactive',
                'lower': 0.0, 'upper': 4.0, 'initial': 4.0, 'fixed': 4.0, 'active': False,
            },
            'recession_b_till': {
                'description': 'b — linear (1.0)',
                'lower': 1.0, 'upper': 4.5, 'initial': 1.0, 'fixed': 1.0, 'active': False,
            },
            'et_scale': {
                'description': 'ET scale — BLR D3 mean',
                'lower': 0.3, 'upper': 2.0, 'initial': 0.755, 'fixed': 0.755, 'active': False,
            },
            'snow_insulation_k': {
                'description': 'inactive', 'lower': 0.0, 'upper': 0.5, 'initial': 0.0, 'fixed': 0.0, 'active': False,
            },
            'f_direct_runoff': {
                'description': 'inactive', 'lower': 0.0, 'upper': 0.5, 'initial': 0.0, 'fixed': 0.0, 'active': False,
            },
            'baseflow_Q': {
                'description': 'inactive', 'lower': 0.0, 'upper': 0.5, 'initial': 0.0, 'fixed': 0.0, 'active': False,
            },
            'log__routing_K': {
                'description': 'inactive', 'lower': -1.0, 'upper': 1.0, 'initial': 0.0, 'fixed': 0.0, 'active': False,
            },
            'et_alpha': {
                'description': 'fixed', 'lower': 0.01, 'upper': 0.99, 'initial': 1.0, 'fixed': 1.0, 'active': False,
            },
            'log__H0_till': {
                'description': 'log10 initial H — IC chain',
                'lower': 0.0, 'upper': 5.0, 'initial': 2.0, 'fixed': 2.0, 'active': False,
            },
            'H0_snowpack': {
                'description': 'IC chain', 'lower': 0.0, 'upper': 500.0, 'initial': 0.0, 'fixed': 0.0, 'active': False,
            },
            'H0_fgi': {
                'description': 'inactive (FGI off)',
                'lower': 0.0, 'upper': 500.0, 'initial': 0.0, 'fixed': 0.0, 'active': False,
            },
            'H0_deficit_carry': {
                'description': 'IC chain',
                'lower': -1e6, 'upper': 1e6, 'initial': 0.0, 'fixed': 0.0, 'active': False,
            },
        },
    }


def main():
    valid_names = set()
    # Decades are explicit so we don't need to enumerate dirs strictly — we'll use the explicit list
    first = True
    for start, end in VALID_DECADES:
        y0 = int(start[:4])
        dec_name = f'{y0}-{y0+9}'
        d = Path('decades') / dec_name
        d.mkdir(parents=True, exist_ok=True)
        p = make_params(start, end, is_first=first)
        out = d / 'params_transient_v6.0_tau_mp.yml'
        with open(out, 'w') as f:
            f.write(f"# {dec_name}: LSR v6 per-decade τ_mp calibration.\n")
            f.write(f"# Active (1): log__multipath_timescale_till.\n")
            f.write(f"# Fixed: PDD + log_κ + log_H_thr at LSR v6 1941 best-fit.\n\n")
            yaml.dump(p, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
        print(f"Written: {out}")
        first = False


if __name__ == '__main__':
    main()
