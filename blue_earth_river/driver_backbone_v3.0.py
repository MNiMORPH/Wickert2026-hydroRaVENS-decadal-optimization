#!/usr/bin/env python3
"""
Joint backbone Dakota driver v3.0: 1-reservoir till+tile architecture (Blue Earth River).

Active params (2): PDD_melt_factor, log__fdd_threshold (snow-only backbone).
Fixed params: recession_b_till=2 (Dupuit-Forchheimer); log__recession_coeff_till and
  log__Hmax_till fixed at v2.0 transient means (per-decade in transient).

Physical basis: single till+tile reservoir — b=2 because both vertical and lateral
  flow through till see the same ksat (Dupuit-Forchheimer geometry).

Per-decade log__recession_coeff_till values embedded by make_backbone_next_v3.py
from v3.x onward.
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
RESERVOIR_ORDER = _driver.get('reservoir_order', ['till'])
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

_PER_DECADE_K_TILL = _driver.get('per_decade_k_till', None)

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


def _Hmax():
    if not any(f'log__Hmax_{l}' in _param_cfg for l in RESERVOIR_ORDER):
        return None
    return [10 ** get(f'log__Hmax_{l}') if f'log__Hmax_{l}' in _param_cfg else np.inf
            for l in RESERVOIR_ORDER]


try:
    _rec_exp = _recession_exponents()
    _hmax    = _Hmax()

    scores = []
    for _dec in _valid_decades:
        if _PER_DECADE_K_TILL:
            _decade_key = _dec['start'][:4] + '-' + _dec['end'][:4]
            _k_till = float(_PER_DECADE_K_TILL.get(_decade_key,
                                                     get('log__recession_coeff_till')))
        else:
            _k_till = get('log__recession_coeff_till')

        _recession_coeff = [10 ** _k_till]

        try:
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
