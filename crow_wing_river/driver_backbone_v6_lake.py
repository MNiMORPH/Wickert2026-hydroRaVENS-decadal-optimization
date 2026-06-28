#!/usr/bin/env python3
"""
Backbone driver — Crow Wing v6 LAKE variant.

One land sub-catchment (the v6 cascade unchanged) + one lake sub-catchment.
Calibrates land cascade params (matrix τ, multipath τ_mp, multipath H_thr) and
two new lake params (a → recession_coeff_lake = 1/a, H_sill → H_threshold_lake).
b = 5/3 fixed via config. Q_gw exchange adds no calibrated param (reuses land
deepest reservoir's recession law).

Per-decade loop with min_obs filter. Returns mean score across qualifying
decades. Mirrors driver_backbone_v6.0.py structure.
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
ENFORCE_WB      = _driver.get('enforce_water_balance', 'none')
MIN_OBS         = _driver.get('min_obs', 2000)
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


try:
    _land_overrides = {
        'recession_coeff':     [10 ** get('log__recession_coeff_till')],
        'multipath_threshold': [10 ** get('log__multipath_threshold_till')],
        'multipath_timescale': [10 ** get('log__multipath_timescale_till')],
    }
    _lake_overrides = {
        'recession_coeff': [10 ** get('log__recession_coeff_lake')],   # = 1/a
        'H_threshold':     [10 ** get('log__H_sill_lake')],            # = H_sill
    }

    scores = []
    for _dec in _valid_decades:
        try:
            result = run_and_score(
                CONFIG_TEMPLATE,
                sub_catchments         = [_land_overrides, _lake_overrides],
                melt_factor            = get('PDD_melt_factor'),
                fdd_threshold          = 1e4,
                snow_insulation_k      = 0.0,
                direct_runoff_fraction = 0.0,
                baseflow_Q             = 0.0,
                et_scale               = get('et_scale'),
                et_alpha               = None,
                routing_K              = None,
                routing_N              = ROUTING_N,
                enforce_water_balance  = ENFORCE_WB,
                initial_states         = None,
                spin_up_cycles         = SPIN_UP_CYCLES,
                start                  = _dec['start'],
                end                    = _dec['end'],
                metric                 = METRIC,
                modules                = MODULES,
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
