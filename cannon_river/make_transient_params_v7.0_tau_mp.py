#!/usr/bin/env python3
"""
Generate params_transient_v7.0_tau_mp.yml in each calibrated decade dir.

Cannon v7 per-decade experiment #1: τ_multipath_soil per decade.
Tests whether decadal variability in Cannon can be captured by the multipath
timescale alone, mirroring the Blue Earth experiment.

Active per decade (1): log__multipath_timescale_soil.
Fixed at v7.0 best-fit (FGI on, 7 active static): PDD, log_FGI, log_κ_soil,
       log_H_thr_soil, f_exfil_soil, et_scale, and intermediate/deep geology.
"""

import yaml
from pathlib import Path

V70 = {
    'PDD_melt_factor':                       7.2571,
    'log__fdd_threshold':                    2.6506,
    'log__recession_coeff_soil':             2.4416,
    'log__multipath_threshold_soil':         2.0980,
    'log__multipath_timescale_soil':         1.3555,
    'f_exfiltration_soil':                   0.7094,
    'et_scale':                              0.6913,
    # Fixed at Cannon v6.3 backbone (then carried through v7):
    'log__recession_coeff_intermediate':     4.2016,
    'log__recession_coeff_deep':             3.0962,
    'f_exfiltration_deep':                   0.5857,
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


def make_params(start, end, is_first):
    return {
        'modules': {
            'snowpack':          True,
            'frozen_ground':     True,    # v7.1 showed small but nonzero FGI signal in Cannon
            'rain_on_snow':      True,
            'direct_runoff':     False,
            'dtr_fgi_decay':     True,
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
            'config_template':       'cannon_config_v7.yml',
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
            'log__multipath_timescale_soil': {
                'description': 'log10 multipath τ — only per-decade active (tile rate test)',
                'lower': 0.0, 'upper': 2.0,
                'initial': V70['log__multipath_timescale_soil'],
                'fixed':   V70['log__multipath_timescale_soil'],
                'active': True,
            },
            'PDD_melt_factor': {
                'description': 'degree-day snowmelt rate — v7.0 fixed',
                'lower': 0.1, 'upper': 10.0,
                'initial': V70['PDD_melt_factor'],
                'fixed':   V70['PDD_melt_factor'],
                'active': False,
            },
            'log__fdd_threshold': {
                'description': 'log10 FGI threshold — v7.0 fixed',
                'lower': 0.0, 'upper': 4.0,
                'initial': V70['log__fdd_threshold'],
                'fixed':   V70['log__fdd_threshold'],
                'active': False,
            },
            'log__recession_coeff_soil': {
                'description': 'log10 soil matrix τ — v7.0 fixed (global)',
                'lower': 0.5, 'upper': 4.0,
                'initial': V70['log__recession_coeff_soil'],
                'fixed':   V70['log__recession_coeff_soil'],
                'active': False,
            },
            'log__multipath_threshold_soil': {
                'description': 'log10 multipath H_thr — v7.0 fixed (global)',
                'lower': 0.5, 'upper': 3.0,
                'initial': V70['log__multipath_threshold_soil'],
                'fixed':   V70['log__multipath_threshold_soil'],
                'active': False,
            },
            'f_exfiltration_soil': {
                'description': 'soil-reservoir matrix outflow fraction — v7.0 fixed',
                'lower': 0.0, 'upper': 1.0,
                'initial': V70['f_exfiltration_soil'],
                'fixed':   V70['f_exfiltration_soil'],
                'active': False,
            },
            'et_scale': {
                'description': 'Thornthwaite ET scaling — v7.0 fixed',
                'lower': 0.3, 'upper': 2.0,
                'initial': V70['et_scale'],
                'fixed':   V70['et_scale'],
                'active': False,
            },
            'log__recession_coeff_intermediate': {
                'description': 'log10 intermediate τ — v6.3 fixed',
                'lower': 0.5, 'upper': 5.0,
                'initial': V70['log__recession_coeff_intermediate'],
                'fixed':   V70['log__recession_coeff_intermediate'],
                'active': False,
            },
            'log__recession_coeff_deep': {
                'description': 'log10 deep τ — v6.3 fixed',
                'lower': 0.5, 'upper': 5.0,
                'initial': V70['log__recession_coeff_deep'],
                'fixed':   V70['log__recession_coeff_deep'],
                'active': False,
            },
            'f_exfiltration_deep': {
                'description': 'deep-reservoir f_exfil — v6.3 fixed',
                'lower': 0.0, 'upper': 1.0,
                'initial': V70['f_exfiltration_deep'],
                'fixed':   V70['f_exfiltration_deep'],
                'active': False,
            },
            'recession_b_soil': {
                'description': 'b_soil — fixed at 1.0 (linear; multipath carries shape)',
                'lower': 1.0, 'upper': 4.5, 'initial': 1.0, 'fixed': 1.0, 'active': False,
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
            'log__H0_soil': {
                'description': 'log10 initial soil H [mm] — set by IC chain',
                'lower': 0.0, 'upper': 5.0, 'initial': 2.0, 'fixed': 2.0, 'active': False,
            },
            'log__H0_intermediate': {
                'description': 'log10 initial intermediate H [mm] — set by IC chain',
                'lower': 0.0, 'upper': 5.0, 'initial': 2.0, 'fixed': 2.0, 'active': False,
            },
            'log__H0_deep': {
                'description': 'log10 initial deep H [mm] — set by IC chain',
                'lower': 0.0, 'upper': 5.0, 'initial': 3.0, 'fixed': 3.0, 'active': False,
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
        out = d / 'params_transient_v7.0_tau_mp.yml'
        with open(out, 'w') as f:
            f.write(f"# {d.name}: Cannon v7.0 per-decade τ_multipath calibration.\n")
            f.write(f"# Active (1): log__multipath_timescale_soil.\n")
            f.write(f"# Fixed: snow + soil matrix τ + H_thr + f_exfil + et_scale at v7.0 best-fit.\n\n")
            yaml.dump(p, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
        print(f"Written: {out}")
        first = False


if __name__ == '__main__':
    main()
