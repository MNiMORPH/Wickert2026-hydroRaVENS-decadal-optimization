#!/usr/bin/env python3
"""
Joint backbone Dakota driver v5.0: 1-reservoir till+tile, free b (Blue Earth River).

Active params (2): PDD_melt_factor, log__fdd_threshold (snow-only backbone).
Fixed params: log__recession_coeff_till and recession_b_till fixed at global means
  from final v3.x transient; updated per iteration via make_backbone_next_v5.py.

No Hmax: v5 removes Hmax; b_till per-decade (from transient) represents tile
  drainage nonlinearity — pre-tile b≈2 (Dupuit-Forchheimer), tile-dominated → b→1.

Per-decade κ_till and b_till embedded by make_backbone_next_v5.py from v5.x onward.
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
_PER_DECADE_B_TILL = _driver.get('per_decade_b_till', None)

PENALTY = 10.0

params, results = di.read_parameters_file()


def get(name):
    p = _param_cfg[name]
    return params[name] if p['active'] else p['fixed']


try:
    scores = []
    for _dec in _valid_decades:
        _decade_key = _dec['start'][:4] + '-' + _dec['end'][:4]

        if _PER_DECADE_K_TILL:
            _k_till = float(_PER_DECADE_K_TILL.get(_decade_key,
                                                     get('log__recession_coeff_till')))
        else:
            _k_till = get('log__recession_coeff_till')

        if _PER_DECADE_B_TILL:
            _b_till = float(_PER_DECADE_B_TILL.get(_decade_key,
                                                     get('recession_b_till')))
        else:
            _b_till = get('recession_b_till')

        _recession_coeff = [10 ** _k_till]
        _rec_exp = [_b_till] if _b_till != 1.0 else None

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
                Hmax                           = [1e9],
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
