#!/usr/bin/env python3
"""
Per-decade transient Dakota driver v5.0: 1-reservoir till+tile, free b (Blue Earth River).

Active params (3): log__recession_coeff_till, recession_b_till, et_scale.
Fixed params: backbone (PDD_melt_factor, log__fdd_threshold), H0 (chained ICs).

No Hmax: v5 removes the storage ceiling. The recession exponent b_till is calibrated
  per-decade, representing changing till+tile drainage nonlinearity as tile density
  expanded (pre-tile b≈2 Dupuit-Forchheimer; tile-dominated system may shift b→1).

Single reservoir: till+tile system. enforce_water_balance='none': et_scale carries
  the water-balance responsibility.
"""

import warnings
import yaml
import pandas as pd
import dakota.interfacing as di
import numpy as np
from mnished import run_and_score

warnings.filterwarnings('ignore', message=r"enforce_water_balance='none'",
                        category=UserWarning)
warnings.filterwarnings('ignore', message=r"f_to_discharge of bottom water-storage layer",
                        category=UserWarning)
warnings.filterwarnings('ignore', message=r"et_scale=",
                        category=UserWarning)

with open('params.yml') as f:
    _cfg = yaml.safe_load(f)

_driver         = _cfg['driver']
_param_cfg      = _cfg['parameters']
MODULES         = _cfg.get('modules', {})
CONFIG_TEMPLATE = _driver['config_template']
METRIC          = _driver.get('metric', 'KGE_logKGE')
SPIN_UP_CYCLES  = _driver.get('spin_up_cycles', 0)
ROUTING_N       = _driver.get('routing_N', 2)
RESERVOIR_ORDER = _driver.get('reservoir_order', ['till'])
ENFORCE_WB      = _driver.get('enforce_water_balance', 'none')
DECADE_START    = _driver.get('decade_start')
DECADE_END      = _driver.get('decade_end')

PENALTY = 10.0

params, results = di.read_parameters_file()


def get(name):
    p = _param_cfg[name]
    return params[name] if p['active'] else p['fixed']


def _recession_exponents():
    exps = []
    for l in RESERVOIR_ORDER:
        key = f'recession_b_{l}'
        if key in _param_cfg:
            exps.append(get(key))
        else:
            exps.append(1.0)
    return exps if any(e != 1.0 for e in exps) else None


def _h0_states():
    names = [f'log__H0_{l}' for l in RESERVOIR_ORDER]
    if not any(n in _param_cfg for n in names):
        return None
    vals = []
    for n in names:
        vals.append(10 ** float(_param_cfg[n]['fixed']) if n in _param_cfg else None)
    snowpack        = float(_param_cfg['H0_snowpack']['fixed'])      if 'H0_snowpack'      in _param_cfg else None
    fgi             = float(_param_cfg['H0_fgi']['fixed'])           if 'H0_fgi'           in _param_cfg else None
    H_deficit_carry = float(_param_cfg['H0_deficit_carry']['fixed']) if 'H0_deficit_carry' in _param_cfg else 0.0
    state = {'reservoirs': vals}
    if snowpack is not None:
        state['snowpack'] = snowpack
    if fgi is not None:
        state['fgi'] = fgi
    state['H_deficit_carry'] = H_deficit_carry
    return state


try:
    _rec_exp = _recession_exponents()
    _h0      = _h0_states()

    et_scale_val     = get('et_scale') if 'et_scale' in _param_cfg else None
    _recession_coeff = [10 ** get(f'log__recession_coeff_{l}') for l in RESERVOIR_ORDER]

    if SPIN_UP_CYCLES == 0 and _h0 is not None:
        _initial_states     = _h0
        _post_spinup_states = None
    else:
        _initial_states     = None
        _post_spinup_states = None

    result = run_and_score(
        CONFIG_TEMPLATE,
        recession_coeff                = _recession_coeff,
        f_to_discharge                 = None,
        leakance_R                     = None,
        leakance_R_calibrated          = 0,
        H_threshold                    = None,
        H_threshold_calibrated         = 0,
        recession_exponents            = _rec_exp,
        recession_exponents_calibrated = 0,
        Hmax                           = [1e9],
        f_tile                         = None,
        tau_tile                       = None,
        melt_factor                    = get('PDD_melt_factor'),
        fdd_threshold                  = 10 ** get('log__fdd_threshold'),
        snow_insulation_k              = get('snow_insulation_k'),
        direct_runoff_fraction         = get('f_direct_runoff'),
        baseflow_Q                     = get('baseflow_Q'),
        et_scale                       = et_scale_val,
        et_alpha                       = None,
        routing_K                      = None,
        routing_N                      = ROUTING_N,
        enforce_water_balance          = ENFORCE_WB,
        initial_states                 = _initial_states,
        post_spinup_states             = _post_spinup_states,
        post_spinup_k                  = 0,
        spin_up_cycles                 = SPIN_UP_CYCLES,
        start                          = DECADE_START,
        end                            = DECADE_END,
        metric                         = METRIC,
        modules                        = MODULES,
    )
    neg_score = 1.0 - result.score if np.isfinite(result.score) else PENALTY

except (KeyError, AttributeError, FileNotFoundError, ImportError, TypeError):
    raise
except Exception:
    neg_score = PENALTY

results['neg_kge'].function = neg_score
results.write()
