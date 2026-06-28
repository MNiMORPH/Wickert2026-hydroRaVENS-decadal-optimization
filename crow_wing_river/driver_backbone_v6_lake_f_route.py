#!/usr/bin/env python3
"""
Backbone driver — Crow Wing v6 LAKE with f_route_lake AS A FREE CALIBRATED
parameter.

Since the run_and_score sub_catchments override does not currently accept
f_route_lake, this driver patches the YAML config in the per-eval working
directory each iteration. 6 active params (PDD, et_scale, log τ_matrix,
log recession_coeff_lake, log H_sill_lake, f_route_lake).

Multipath disabled at the config level (consistent with v2 no_mp baseline).
"""

import warnings
import yaml
from copy import deepcopy
import dakota.interfacing as di
import numpy as np
import pandas as pd
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
    _base_model_cfg = yaml.safe_load(_f)
_datafile = _base_model_cfg['timeseries']['datafile']
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


def make_temp_cfg(f_route_value):
    """Patch f_route_lake into the lake sub-catchment of the base config.
    Writes to the per-evaluation cwd (out/run.N/) for isolation."""
    cfg = deepcopy(_base_model_cfg)
    for sc in cfg['sub_catchments']:
        if sc.get('kind') == 'lake':
            sc.setdefault('lake', {})['f_route_lake'] = float(f_route_value)
    path = 'tmp_lake_cfg.yml'
    with open(path, 'w') as f:
        yaml.dump(cfg, f)
    return path


try:
    _land_overrides = {
        'recession_coeff': [10 ** get('log__recession_coeff_till')],
    }
    _lake_overrides = {
        'recession_coeff': [10 ** get('log__recession_coeff_lake')],
        'H_threshold':     [10 ** get('log__H_sill_lake')],
    }
    _f_route = get('f_route_lake')
    _temp_cfg_path = make_temp_cfg(_f_route)

    scores = []
    for _dec in _valid_decades:
        try:
            result = run_and_score(
                _temp_cfg_path,
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
