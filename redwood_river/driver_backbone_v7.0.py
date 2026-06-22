#!/usr/bin/env python3
"""
Joint backbone Dakota driver v7.0: Cannon River with multipath on soil reservoir.

Architecture: same 3-reservoir geology as v6 (soil + intermediate/PdC + deep/Wonewoc),
but the soil reservoir gets the A3 multipath treatment:
  - b_soil = 1 (linear matrix)
  - matrix path Q_M = H_soil / τ_soil → split by f_exfil to stream / intermediate
  - threshold-activated parallel path Q_mp = max(0, H − H_thr)/τ_mp → direct to stream
  - no Hmax cap

Intermediate and deep reservoirs fixed at v6.3 backbone best-fit:
  log_k_int = 4.20, log_R_int = 0.99 (leakance junction)
  log_k_deep = 3.10, log_H_thr_deep = 1.16, f_exfil_deep = 0.586 (threshold junction)

All hydraulic params static (no per-decade embedding) — this is the multipath
analog of Blue Earth v6.0. Test against Cannon v6.3 transient mean (KGE = 0.737).

Active params (7): PDD, log_FGI, log_k_soil_matrix, log_multipath_threshold_soil,
                   log_multipath_timescale_soil, f_exfiltration_soil, et_scale.
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
RESERVOIR_ORDER = _driver.get('reservoir_order', ['soil', 'intermediate', 'deep'])
ENFORCE_WB      = _driver.get('enforce_water_balance', 'none')
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

PENALTY = 10.0

params, results = di.read_parameters_file()


def get(name):
    p = _param_cfg[name]
    return params[name] if p['active'] else p['fixed']


def _multipath_lists():
    thrs = [None] * len(RESERVOIR_ORDER)
    taus = [None] * len(RESERVOIR_ORDER)
    for i, l in enumerate(RESERVOIR_ORDER):
        thr_key = f'log__multipath_threshold_{l}'
        tau_key = f'log__multipath_timescale_{l}'
        if thr_key in _param_cfg and tau_key in _param_cfg:
            thrs[i] = 10 ** get(thr_key)
            taus[i] = 10 ** get(tau_key)
    return thrs, taus


def _f_discharge():
    vals = []
    for l in RESERVOIR_ORDER:
        key = f'f_exfiltration_{l}'
        if key in _param_cfg:
            vals.append(get(key))
        else:
            vals.append(None)
    return vals if any(v is not None for v in vals) else None


try:
    _f_dis  = _f_discharge()
    _mp_thr, _mp_tau = _multipath_lists()
    _et = float(get('et_scale'))

    scores = []
    for _dec in _valid_decades:
        _recession_coeff = [
            10 ** get(f'log__recession_coeff_{l}') for l in RESERVOIR_ORDER
        ]

        try:
            result = run_and_score(
                CONFIG_TEMPLATE,
                recession_coeff                = _recession_coeff,
                f_to_discharge                 = _f_dis,
                leakance_R                     = None,   # use config
                leakance_R_calibrated          = 0,
                H_threshold                    = None,   # use config
                H_threshold_calibrated         = 0,
                recession_exponents            = None,   # all b=1
                recession_exponents_calibrated = 0,
                Hmax                           = None,   # use config
                f_tile                         = None,
                tau_tile                       = None,
                multipath_threshold            = _mp_thr,
                multipath_timescale            = _mp_tau,
                multipath_calibrated           = 2,      # H_thr + τ_mp active
                melt_factor                    = get('PDD_melt_factor'),
                fdd_threshold                  = 10 ** get('log__fdd_threshold'),
                snow_insulation_k              = get('snow_insulation_k'),
                direct_runoff_fraction         = get('f_direct_runoff'),
                baseflow_Q                     = get('baseflow_Q'),
                et_scale                       = _et,
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
