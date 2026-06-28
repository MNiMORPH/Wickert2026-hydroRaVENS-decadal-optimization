#!/usr/bin/env python3
"""
Joint backbone Dakota driver v8.0: Wild Rice River with parallel sub-catchments.

Two zones in parallel:
  - till_uplands: 2-reservoir cascade (soil + deep till); soil has tile drains
    (constant-fraction f_tile path) representing engineered agricultural tile.
  - clay_lowlands: 2-reservoir cascade (soil + deep clay); soil has multipath
    (threshold-activated parallel drain) representing engineered ditch drainage.

Basin discharge Q = a_till·Q_till + a_clay·Q_clay. Area fractions are FIXED in
the config (from surficial geology); not calibrated parameters here.

Active params (joint across all valid decades): per-zone hydraulic + global snow.
  - PDD, log_FGI (FGI off in modules but param present)
  - log__k_till_soil, log__k_till_deep, f_exfil_till_soil
  - log__k_clay_soil, log__k_clay_deep, f_exfil_clay_soil
  - f_tile_till, log__tau_tile_till
  - log__H_thr_clay, log__tau_mp_clay

et_scale fixed at BLR D3 mean (0.755).
"""

import warnings
import yaml
import pandas as pd
import dakota.interfacing as di
import numpy as np
from mnished import run_and_score

warnings.filterwarnings('ignore', message=r"enforce_water_balance='none'", category=UserWarning)
warnings.filterwarnings('ignore', message=r"f_to_discharge of bottom water-storage layer", category=UserWarning)
warnings.filterwarnings('ignore', message=r"et_scale=", category=UserWarning)

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


def build_sub_catchments():
    """Build the per-zone arg list for run_and_score."""
    return [
        # 0: till_uplands  (config order)
        {
            'recession_coeff':  [10 ** get('log__k_till_soil'),
                                 10 ** get('log__k_till_deep')],
            'f_to_discharge':   [get('f_exfil_till_soil'), 1.0],
            'f_tile':           [get('f_tile_till'), 0.0],
            'tau_tile':         10 ** get('log__tau_tile_till'),
        },
        # 1: clay_lowlands
        {
            'recession_coeff':       [10 ** get('log__k_clay_soil'),
                                      10 ** get('log__k_clay_deep')],
            'f_to_discharge':        [get('f_exfil_clay_soil'), 1.0],
            'multipath_threshold':   [10 ** get('log__H_thr_clay'), None],
            'multipath_timescale':   [10 ** get('log__tau_mp_clay'), None],
        },
    ]


try:
    scores = []
    for _dec in _valid_decades:
        try:
            result = run_and_score(
                CONFIG_TEMPLATE,
                sub_catchments       = build_sub_catchments(),
                melt_factor          = get('PDD_melt_factor'),
                fdd_threshold        = 10 ** get('log__fdd_threshold'),
                snow_insulation_k    = get('snow_insulation_k'),
                direct_runoff_fraction = get('f_direct_runoff'),
                baseflow_Q           = get('baseflow_Q'),
                et_scale             = get('et_scale'),
                et_alpha             = None,
                routing_K            = None,
                routing_N            = ROUTING_N,
                enforce_water_balance = ENFORCE_WB,
                initial_states       = None,
                spin_up_cycles       = SPIN_UP_CYCLES,
                start                = _dec['start'],
                end                  = _dec['end'],
                metric               = METRIC,
                modules              = MODULES,
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
