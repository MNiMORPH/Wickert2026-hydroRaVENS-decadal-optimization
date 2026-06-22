#!/usr/bin/env python3
"""
Generate per-decade params_transient_v7.0_ksoil.yml for Wild Rice River.

Cannon's strongest per-decade signal was log_κ_soil (matrix τ). For Wild
Rice, the pre-tile decade fits very poorly under joint static; this test
asks whether matrix τ alone can absorb that mismatch (pre-tile → very
slow matrix; post-tile → faster matrix as tiles+ditches develop).

Active per decade (1): log__recession_coeff_soil.
Fixed at Wild Rice v7-2res best-fit: PDD, log_H_thr_soil, log_τ_mp_soil,
       f_exfil_soil, log_κ_deep.
"""

import yaml
from pathlib import Path

# Wild Rice v7-2res joint best-fit (KGE = 0.6299)
WR = {
    'PDD_melt_factor':                 4.4638,
    'log__recession_coeff_soil':       2.5519,
    'log__multipath_threshold_soil':   1.8415,
    'log__multipath_timescale_soil':   1.6060,
    'f_exfiltration_soil':             0.7144,
    'log__recession_coeff_deep':       2.2061,
}

# Decade name → (start, end). 1910-1917 is the continuous span; others are standard.
DECADES = [
    ('1910-1917', '1909-07-01', '1917-09-29'),  # pre-tile reference (continuous span)
    ('1931-1940', '1931-01-01', '1940-12-31'),
    ('1941-1950', '1941-01-01', '1950-12-31'),
    ('1951-1960', '1951-01-01', '1960-12-31'),
    ('1961-1970', '1961-01-01', '1970-12-31'),
    ('1971-1980', '1971-01-01', '1980-12-31'),
    ('1991-2000', '1991-01-01', '2000-12-31'),
    ('2001-2010', '2001-01-01', '2010-12-31'),
    ('2011-2020', '2011-01-01', '2020-12-31'),
]


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
            'config_template':       'wild_rice_config_v7_2res.yml',
            'metric':                'KGE_logKGE',
            'spin_up_cycles':        1 if is_first else 0,
            'routing_N':             2,
            'n_reservoirs':          2,
            'reservoir_order':       ['soil', 'deep'],
            'decade_start':          start,
            'decade_end':            end,
            'enforce_water_balance': 'none',
        },
        'parameters': {
            'log__recession_coeff_soil': {
                'description': 'log10 soil matrix τ — per-decade active (pre-tile vs post-tile test)',
                'lower': 0.5, 'upper': 4.5,
                'initial': WR['log__recession_coeff_soil'],
                'fixed':   WR['log__recession_coeff_soil'],
                'active': True,
            },
            'PDD_melt_factor': {
                'description': 'PDD — Wild Rice v7-2res fixed',
                'lower': 0.1, 'upper': 10.0,
                'initial': WR['PDD_melt_factor'],
                'fixed':   WR['PDD_melt_factor'],
                'active': False,
            },
            'log__multipath_threshold_soil': {
                'description': 'log10 multipath H_thr — Wild Rice v7-2res fixed',
                'lower': 0.5, 'upper': 3.0,
                'initial': WR['log__multipath_threshold_soil'],
                'fixed':   WR['log__multipath_threshold_soil'],
                'active': False,
            },
            'log__multipath_timescale_soil': {
                'description': 'log10 multipath τ — Wild Rice v7-2res fixed',
                'lower': 0.0, 'upper': 2.0,
                'initial': WR['log__multipath_timescale_soil'],
                'fixed':   WR['log__multipath_timescale_soil'],
                'active': False,
            },
            'f_exfiltration_soil': {
                'description': 'soil matrix outflow fraction — Wild Rice v7-2res fixed',
                'lower': 0.0, 'upper': 1.0,
                'initial': WR['f_exfiltration_soil'],
                'fixed':   WR['f_exfiltration_soil'],
                'active': False,
            },
            'log__recession_coeff_deep': {
                'description': 'log10 deep clay τ — Wild Rice v7-2res fixed',
                'lower': 1.0, 'upper': 5.0,
                'initial': WR['log__recession_coeff_deep'],
                'fixed':   WR['log__recession_coeff_deep'],
                'active': False,
            },
            'f_exfiltration_deep': {
                'description': 'deep — all to stream',
                'lower': 0.0, 'upper': 1.0, 'initial': 1.0, 'fixed': 1.0, 'active': False,
            },
            'recession_b_soil': {
                'description': 'b — linear', 'lower': 1.0, 'upper': 4.5, 'initial': 1.0, 'fixed': 1.0, 'active': False,
            },
            'recession_b_deep': {
                'description': 'b — linear', 'lower': 1.0, 'upper': 4.5, 'initial': 1.0, 'fixed': 1.0, 'active': False,
            },
            'et_scale': {
                'description': 'ET scale — BLR D3 mean',
                'lower': 0.3, 'upper': 2.0, 'initial': 0.755, 'fixed': 0.755, 'active': False,
            },
            'log__fdd_threshold': {
                'description': 'inactive', 'lower': 0.0, 'upper': 4.0, 'initial': 4.0, 'fixed': 4.0, 'active': False,
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
            'log__H0_soil': {
                'description': 'log10 initial soil H — IC chain',
                'lower': 0.0, 'upper': 5.0, 'initial': 2.0, 'fixed': 2.0, 'active': False,
            },
            'log__H0_deep': {
                'description': 'log10 initial deep H — IC chain',
                'lower': 0.0, 'upper': 5.0, 'initial': 2.5, 'fixed': 2.5, 'active': False,
            },
            'H0_snowpack': {
                'description': 'IC chain', 'lower': 0.0, 'upper': 500.0, 'initial': 0.0, 'fixed': 0.0, 'active': False,
            },
            'H0_fgi': {
                'description': 'inactive', 'lower': 0.0, 'upper': 500.0, 'initial': 0.0, 'fixed': 0.0, 'active': False,
            },
            'H0_deficit_carry': {
                'description': 'IC chain',
                'lower': -1e6, 'upper': 1e6, 'initial': 0.0, 'fixed': 0.0, 'active': False,
            },
        },
    }


def main():
    first = True
    for dec_name, start, end in DECADES:
        d = Path('decades') / dec_name
        d.mkdir(parents=True, exist_ok=True)
        p = make_params(start, end, is_first=first)
        out = d / 'params_transient_v7.0_ksoil.yml'
        with open(out, 'w') as f:
            f.write(f"# {dec_name}: Wild Rice v7-2res per-decade log_κ_soil test.\n")
            f.write(f"# Period: {start} to {end}\n")
            if dec_name == '1910-1917':
                f.write(f"# [PRE-TILE REFERENCE — continuous 3013-day span before drainage system]\n")
            f.write(f"# Active (1): log__recession_coeff_soil.\n\n")
            yaml.dump(p, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
        print(f"Written: {out}")
        first = False


if __name__ == '__main__':
    main()
