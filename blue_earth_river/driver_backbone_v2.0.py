#!/usr/bin/env python3
"""
Joint backbone Dakota driver v2.0: 3-reservoir soil/shallow_till/deep_till (Blue Earth River).

Active params (4): shallow_till recession, deep_till recession, PDD_melt_factor, log__fdd_threshold.
Fixed params: b_soil=2 (Dupuit-Forchheimer); log__recession_coeff_soil fixed
  (iterated with transient, where it is calibrated per decade);
  f_exfiltration_shallow_till=0.5 (backbone fixed).

3-reservoir structure:
  soil (b=2, Dupuit-Forchheimer, Hmax=∞ in backbone)
    → shallow till (b=1 linear, f_exfil=0.5)
    → deep till (b=1 linear, all to stream)

Per-decade log__recession_coeff_soil values embedded by make_backbone_next_v2.py.
Absent in v2.0 first run; present from v2.1 onward.
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
SPIN_UP_CYCLES  = _driver.get('spin_up_cycles', 1)
ROUTING_N       = _driver.get('routing_N', 2)
RESERVOIR_ORDER = _driver.get('reservoir_order', ['soil', 'shallow_till', 'deep_till'])
ENFORCE_WB      = _driver.get('enforce_water_balance', 'global')
MIN_OBS         = _driver.get('min_obs', 3000)
DECADES         = _driver['decades']

with open(CONFIG_TEMPLATE) as _f:
    _model_cfg = yaml.safe_load(_f)
_datafile = _model_cfg['timeseries']['datafile']
_df       = pd.read_csv(_datafile, parse_dates=['Date'])

_valid_decades = []
for _dec in DECADES:
    _s = pd.Timestamp(_dec['start'])
    _e = pd.Timestamp(_dec['end'])
    _n = int((_df['Date'].between(_s, _e) & _df['Discharge [m^3/s]'].notna()).sum())
    if _n >= MIN_OBS:
        _valid_decades.append(_dec)

_PER_DECADE_K_SOIL = _driver.get('per_decade_k_soil', None)

PENALTY = 10.0

params, results = di.read_parameters_file()


def get(name):
    p = _param_cfg[name]
    return params[name] if p['active'] else p['fixed']


def _f_discharge():
    vals = []
    for l in RESERVOIR_ORDER:
        key = f'f_exfiltration_{l}'
        if key in _param_cfg and _param_cfg[key].get('active', True):
            vals.append(get(key))
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


def _leakance_R():
    vals = [None] * len(RESERVOIR_ORDER)
    k = 0
    for i, l in enumerate(RESERVOIR_ORDER):
        key = f'log__leakance_R_{l}'
        if key in _param_cfg:
            vals[i] = 10 ** get(key)
            if _param_cfg[key].get('active', False):
                k += 1
    return (vals, k) if any(v is not None for v in vals) else (None, 0)


def _H_threshold():
    vals = [None] * len(RESERVOIR_ORDER)
    k = 0
    for i, l in enumerate(RESERVOIR_ORDER):
        key = f'log__H_threshold_{l}'
        if key in _param_cfg:
            vals[i] = 10 ** get(key)
            if _param_cfg[key].get('active', False):
                k += 1
    return (vals, k) if any(v is not None for v in vals) else (None, 0)


def _Hmax():
    if not any(f'log__Hmax_{l}' in _param_cfg for l in RESERVOIR_ORDER):
        return None
    return [10 ** get(f'log__Hmax_{l}') if f'log__Hmax_{l}' in _param_cfg else np.inf
            for l in RESERVOIR_ORDER]


try:
    _lr, _lr_k  = _leakance_R()
    _ht, _ht_k  = _H_threshold()
    _rec_exp    = _recession_exponents()
    _f_dis      = _f_discharge()
    _hmax       = _Hmax()

    scores = []
    for _dec in _valid_decades:
        if _PER_DECADE_K_SOIL:
            _decade_key = _dec['start'][:4] + '-' + _dec['end'][:4]
            _k_soil = float(_PER_DECADE_K_SOIL.get(_decade_key,
                                                     get('log__recession_coeff_soil')))
        else:
            _k_soil = get('log__recession_coeff_soil')

        _recession_coeff = [
            10 ** (_k_soil if l == 'soil' else get(f'log__recession_coeff_{l}'))
            for l in RESERVOIR_ORDER
        ]

        try:
            result = run_and_score(
                CONFIG_TEMPLATE,
                recession_coeff                = _recession_coeff,
                f_to_discharge                 = _f_dis,
                leakance_R                     = _lr,
                leakance_R_calibrated          = _lr_k,
                H_threshold                    = _ht,
                H_threshold_calibrated         = _ht_k,
                recession_exponents            = _rec_exp,
                recession_exponents_calibrated = 0,
                Hmax                           = _hmax,
                f_tile                         = None,
                tau_tile                       = None,
                melt_factor                    = get('PDD_melt_factor'),
                fdd_threshold                  = 10 ** get('log__fdd_threshold'),
                snow_insulation_k              = get('snow_insulation_k'),
                direct_runoff_fraction         = get('f_direct_runoff'),
                baseflow_Q                     = get('baseflow_Q'),
                et_scale                       = None,
                et_alpha                       = None,
                routing_K                      = None,
                routing_N                      = ROUTING_N,
                enforce_water_balance          = ENFORCE_WB,
                initial_states                 = None,
                spin_up_cycles                 = SPIN_UP_CYCLES,
                start                          = _dec['start'],
                end                            = _dec['end'],
                metric                         = METRIC,
                modules                        = MODULES,
            )
            s = result.score
            scores.append(s if np.isfinite(s) else -PENALTY)
        except (KeyError, AttributeError, FileNotFoundError, ImportError, TypeError):
            raise
        except Exception:
            scores.append(-PENALTY)

    mean_score = float(np.mean(scores)) if scores else -PENALTY
    neg_score  = 1.0 - mean_score if np.isfinite(mean_score) else PENALTY

except (KeyError, AttributeError, FileNotFoundError, ImportError, TypeError):
    raise
except Exception:
    neg_score = PENALTY

results['neg_kge'].function = neg_score
results.write()
