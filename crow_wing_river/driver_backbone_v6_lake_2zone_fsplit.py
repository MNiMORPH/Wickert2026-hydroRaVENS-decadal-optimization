#!/usr/bin/env python3
"""
Backbone driver — Crow Wing v6 LAKE, TWO-LAND-ZONE with the AREA SPLIT
CALIBRATED (f_split as a free parameter).

Extends driver_backbone_v6_lake_2zone.py: the land/land area allocation is no
longer fixed in the config. Each evaluation patches `area_fraction` into a
per-eval copy of the config:

    f_split = fraction of the NON-LAKE land area assigned to direct_land.
    direct_land.area_fraction      = f_split       * (1 - lake_area)
    lake_basin_land.area_fraction  = (1 - f_split) * (1 - lake_area)
    lake.area_fraction             = lake_area      (FIXED, NHD open water)

The lake area is read from the base config (not hard-coded) and held fixed —
it is a measured quantity (NHD), the one area we should not fit.

7 active params: PDD, et_scale, log τ_direct, log τ_routed,
log recession_coeff_lake, log H_sill_lake, f_split.

Area injection requires per-eval YAML patching (area lives at the sub_catchment
level, which run_and_score's sub_catchments override does not reach). Multipath
disabled and f_route_lake=1.0 at the config level.
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

# Lake area is the fixed (NHD-measured) area; land area is everything else.
_LAKE_AREA = next(sc['area_fraction'] for sc in _base_model_cfg['sub_catchments']
                  if sc.get('kind') == 'lake')
_LAND_AREA = 1.0 - _LAKE_AREA

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


def make_temp_cfg(f_split):
    """Patch the land/land area split into a per-eval copy of the config.
    Lake area stays at its NHD value; direct + routed share the remainder."""
    cfg = deepcopy(_base_model_cfg)
    for sc in cfg['sub_catchments']:
        if sc['name'] == 'direct_land':
            sc['area_fraction'] = float(f_split * _LAND_AREA)
        elif sc['name'] == 'lake_basin_land':
            sc['area_fraction'] = float((1.0 - f_split) * _LAND_AREA)
        elif sc.get('kind') == 'lake':
            sc['area_fraction'] = float(_LAKE_AREA)
    path = 'tmp_2zone_cfg.yml'
    with open(path, 'w') as f:
        yaml.dump(cfg, f)
    return path


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
    _temp_cfg_path = make_temp_cfg(get('f_split'))

    scores = []
    for _dec in _valid_decades:
        try:
            result = run_and_score(
                _temp_cfg_path,
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
