#!/usr/bin/env python3
"""
Per-decade Dakota driver — runs one decade per Dakota call.

Reads decade_start / decade_end from params.yml driver block. Uses the
modern MNiShed run_and_score API (recession_coeff naming, not t_recession).

Compatible with any reservoir_order. f_exfiltration_<last> is set to None
(MNiShed routes the last reservoir's discharge entirely to stream).
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

with open('params.yml') as f:
    _cfg = yaml.safe_load(f)

_driver         = _cfg['driver']
_param_cfg      = _cfg['parameters']
MODULES         = _cfg.get('modules', {})
CONFIG_TEMPLATE = _driver['config_template']
METRIC          = _driver.get('metric', 'KGE_logKGE')
SPIN_UP_CYCLES  = _driver.get('spin_up_cycles', 1)
ROUTING_N       = _driver.get('routing_N', 2)
RESERVOIR_ORDER = _driver['reservoir_order']
ENFORCE_WB      = _driver.get('enforce_water_balance', 'none')
DECADE_START    = _driver['decade_start']
DECADE_END      = _driver['decade_end']

PENALTY = 10.0

params, results = di.read_parameters_file()


def get(name):
    """Return calibrated value if active, else fixed; KeyError if absent."""
    p = _param_cfg[name]
    return params[name] if p['active'] else p['fixed']


def _f_discharge():
    """f_to_discharge per reservoir; None entry = use config default."""
    vals = []
    for l in RESERVOIR_ORDER:
        key = f'f_exfiltration_{l}'
        if key in _param_cfg and _param_cfg[key].get('active', True):
            vals.append(get(key))
        elif key in _param_cfg:
            vals.append(_param_cfg[key]['fixed'])
        else:
            vals.append(None)
    return vals if any(v is not None for v in vals) else None


def _recession_exponents():
    exps = []
    for l in RESERVOIR_ORDER:
        key = f'recession_b_{l}'
        if key in _param_cfg:
            exps.append(get(key))
        else:
            exps.append(1.0)
    return exps if any(e != 1.0 for e in exps) else None


try:
    _recession_coeff = [10 ** get(f'log__t_recession_{l}') for l in RESERVOIR_ORDER]
    _f_dis           = _f_discharge()
    _rec_exp         = _recession_exponents()

    result = run_and_score(
        CONFIG_TEMPLATE,
        recession_coeff                = _recession_coeff,
        f_to_discharge                 = _f_dis,
        leakance_R                     = None,
        leakance_R_calibrated          = 0,
        H_threshold                    = None,
        H_threshold_calibrated         = 0,
        recession_exponents            = _rec_exp,
        recession_exponents_calibrated = 0,
        Hmax                           = None,
        f_tile                         = None,
        tau_tile                       = None,
        melt_factor                    = get('PDD_melt_factor'),
        fdd_threshold                  = 10 ** get('log__fdd_threshold'),
        snow_insulation_k              = get('snow_insulation_k'),
        direct_runoff_fraction         = get('f_direct_runoff'),
        baseflow_Q                     = get('baseflow_Q'),
        et_scale                       = get('et_scale'),
        et_alpha                       = None,
        routing_K                      = None,
        routing_N                      = ROUTING_N,
        enforce_water_balance          = ENFORCE_WB,
        initial_states                 = None,
        spin_up_cycles                 = SPIN_UP_CYCLES,
        start                          = DECADE_START,
        end                            = DECADE_END,
        metric                         = METRIC,
        modules                        = MODULES,
    )
    s = result.score
    neg_score = 1.0 - s if np.isfinite(s) else PENALTY

except (KeyError, AttributeError, FileNotFoundError, ImportError, TypeError):
    raise
except Exception:
    neg_score = PENALTY

results['neg_kge'].function = neg_score
results.write()
