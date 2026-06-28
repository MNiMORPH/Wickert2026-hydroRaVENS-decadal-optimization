#!/usr/bin/env python3
"""
Backbone driver — Crow Wing v6 LAKE, TWO-LAND-ZONE structure.

The land is split into two sub-catchments with independent matrix τ:
  - direct_land     (config sub_catchment 0): fast τ, drains to gauge
  - lake_basin_land (config sub_catchment 1): slow τ, drains through the lake
  - lake            (config sub_catchment 2): open water, gw_partner=lake_basin_land,
                    f_route_lake=1.0 (set in config — routing is structural).

6 active params: PDD, et_scale, log τ_direct, log τ_routed,
log recession_coeff_lake, log H_sill_lake.

Unlike the f_route driver, f_route_lake is FIXED (1.0) in the config, so no
per-eval YAML patching is needed — the config path is passed directly.
Multipath disabled at the config level on both land zones.
"""

import warnings
import yaml
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


try:
    # Positional overrides — one per sub_catchment, in config order:
    #   [0] direct_land, [1] lake_basin_land, [2] lake
    _direct_overrides = {
        'recession_coeff': [10 ** get('log__recession_coeff_direct')],
    }
    _routed_overrides = {
        'recession_coeff': [10 ** get('log__recession_coeff_routed')],
    }
    _lake_overrides = {
        'recession_coeff': [10 ** get('log__recession_coeff_lake')],
        'H_threshold':     [10 ** get('log__H_sill_lake')],
    }

    scores = []
    for _dec in _valid_decades:
        try:
            result = run_and_score(
                CONFIG_TEMPLATE,
                sub_catchments         = [_direct_overrides, _routed_overrides, _lake_overrides],
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
