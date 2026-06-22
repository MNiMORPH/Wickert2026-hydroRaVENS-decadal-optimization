#!/usr/bin/env python3
"""
Summarize decade-by-decade calibration results.

Scans every decades/<label>/runs/ subdirectory, finds the best run for each
decade (lowest neg_kge in evaluations.dat), and writes one row per decade to
summary.csv.

Columns
-------
decade            : directory label (e.g. 1911-1920)
decade_start      : actual start date used in calibration
decade_end        : nominal end date (data clipped to forcing availability)
data_start        : first date with non-NaN observed discharge in window
data_end          : last  date with non-NaN observed discharge in window
n_days_window     : calendar days in [decade_start, min(decade_end, data_end)]
n_days_data       : days with non-NaN observed discharge
pct_data          : n_days_data / n_days_window * 100
best_run          : name of the archived run directory used
n_evaluations     : number of Dakota function evaluations
neg_kge           : objective value at best evaluation
logKGE, NSE, KGE, KGE_logFDC, AIC, BFI_obs, BFI_mod : metrics
<all active + fixed parameters>

Usage (from WATERSHED_NAME/):
    python summarize.py                       # writes summary.csv
    python summarize.py --decades-dir decades --out summary.csv
"""

import argparse
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

warnings.filterwarnings('ignore')

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

parser = argparse.ArgumentParser()
parser.add_argument('--decades-dir', default='decades',
                    help='Path to decades/ directory (default: decades)')
parser.add_argument('--out', default='summary.csv',
                    help='Output CSV path (default: summary.csv)')
args = parser.parse_args()

DECADES_DIR = Path(args.decades_dir)
OUT_PATH    = Path(args.out)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_params(params_path):
    with open(params_path) as f:
        return yaml.safe_load(f)


def find_best_run(decade_dir):
    """Return (run_dir, evaluations_df) for the best archived run, or None."""
    runs_dir = decade_dir / 'runs'
    if not runs_dir.exists():
        return None, None
    candidates = sorted(runs_dir.iterdir())
    # Most recent run is last alphabetically (timestamp prefix); prefer it,
    # but actually take the run with the lowest neg_kge across all runs.
    best_dir  = None
    best_val  = np.inf
    best_df   = None
    for run_dir in candidates:
        evals_path = run_dir / 'evaluations.dat'
        if not evals_path.exists():
            continue
        df = pd.read_csv(evals_path, sep=r'\s+')
        df = df.rename(columns={'%eval_id': 'eval_id'})
        for col in df.columns:
            if col != 'interface':
                df[col] = pd.to_numeric(df[col], errors='coerce')
        val = df['neg_kge'].min()
        if val < best_val:
            best_val = val
            best_dir = run_dir
            best_df  = df
    return best_dir, best_df


def data_completeness(cfg, decade_start, decade_end_nominal):
    """
    Return (data_start, data_end, n_days_window, n_days_data, pct_data)
    for the observed discharge column within the decade window.
    """
    tmpl_path = Path(cfg['driver']['config_template'])
    with open(tmpl_path) as f:
        model_cfg = yaml.safe_load(f)
    datafile = model_cfg['timeseries']['datafile']
    df = pd.read_csv(datafile, parse_dates=['Date'])

    t0 = pd.Timestamp(decade_start)
    t1 = pd.Timestamp(decade_end_nominal)
    # Clip to actual data availability
    t1_actual = min(t1, df['Date'].max())

    window = df[(df['Date'] >= t0) & (df['Date'] <= t1_actual)].copy()
    if window.empty:
        return None, None, 0, 0, 0.0

    q_col = 'Discharge [m^3/s]'
    if q_col not in window.columns:
        # Fall back: count any non-NaN row
        valid = window.dropna(how='all')
    else:
        valid = window[window[q_col].notna()]

    n_window = len(window)
    n_data   = len(valid)
    pct      = 100.0 * n_data / n_window if n_window > 0 else 0.0
    data_start = valid['Date'].min() if not valid.empty else None
    data_end   = valid['Date'].max() if not valid.empty else None
    return data_start, data_end, n_window, n_data, pct


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

rows = []

decade_dirs = sorted(p for p in DECADES_DIR.iterdir()
                     if p.is_dir() and (p / 'params.yml').exists())

for decade_dir in decade_dirs:
    label = decade_dir.name
    params_path = decade_dir / 'params.yml'
    cfg = load_params(params_path)
    drv = cfg['driver']

    decade_start       = drv.get('decade_start')
    decade_end_nominal = drv.get('decade_end')

    # --- data completeness ---
    try:
        data_start, data_end, n_window, n_data, pct = data_completeness(
            cfg, decade_start, decade_end_nominal)
    except Exception as e:
        print(f"  Warning: could not compute data completeness for {label}: {e}")
        data_start = data_end = None
        n_window = n_data = 0
        pct = float('nan')

    # --- best run ---
    best_dir, evals_df = find_best_run(decade_dir)
    if best_dir is None:
        print(f"  {label}: no runs found, skipping metrics")
        row = {
            'decade': label,
            'decade_start': decade_start,
            'decade_end': decade_end_nominal,
            'data_start': data_start,
            'data_end': data_end,
            'n_days_window': n_window,
            'n_days_data': n_data,
            'pct_data': round(pct, 1) if not np.isnan(pct) else float('nan'),
        }
        rows.append(row)
        continue

    best_row = evals_df.loc[evals_df['neg_kge'].idxmin()]
    n_evals  = len(evals_df)

    # --- re-run best to get full metrics ---
    # Import here so summarize.py works even without hydroravens on PATH.
    try:
        from mnished import HydrographSeparation, run_and_score
        from mnished.calibration import _nse, _kge, _log_kge

        param_cfg = cfg['parameters']
        modules   = cfg.get('modules', {})
        _MODULE_PARAMS = {
            'snowpack':      ['PDD_melt_factor'],
            'frozen_ground': ['log__fdd_threshold', 'snow_insulation_k'],
            'direct_runoff': ['f_direct_runoff'],
            'rain_on_snow':  [],
        }
        for mod, names in _MODULE_PARAMS.items():
            if not modules.get(mod, True):
                for name in names:
                    if name in param_cfg:
                        param_cfg[name]['active'] = False

        reservoir_order = drv.get('reservoir_order',
                                  ['shallow', 'soil', 'intermediate'])
        enforce_wb      = drv.get('enforce_water_balance', 'water-year')
        spin_up         = drv.get('spin_up_cycles', 0)
        routing_N       = drv.get('routing_N', 2)

        def _get(name):
            p = param_cfg[name]
            if p['active'] and name in best_row.index:
                return float(best_row[name])
            return float(p['fixed'])

        def _rec_exp():
            exponents = []
            for lbl in reservoir_order:
                key = f'recession_b_{lbl}'
                if lbl == 'shallow':
                    exponents.append(1.0)
                elif 'recession_b' in param_cfg:
                    exponents.append(_get('recession_b'))
                elif key in param_cfg:
                    exponents.append(_get(key))
                else:
                    exponents.append(1.0)
            return None if all(e == 1.0 for e in exponents) else exponents

        config_tmpl = drv['config_template']
        with open(config_tmpl) as f:
            mcfg = yaml.safe_load(f)
        area_km2 = mcfg['catchment']['drainage_basin_area__km2']
        datafile  = mcfg['timeseries']['datafile']
        df_raw    = pd.read_csv(datafile, parse_dates=['Date'])
        Q_spec    = df_raw['Discharge [m^3/s]'].values * 86400.0 / (area_km2 * 1e3)
        precip    = df_raw['Precipitation [mm/day]'].values
        hs = HydrographSeparation(Q_spec, n_reservoirs=len(reservoir_order),
                                  precip=precip)
        hs.fit()
        init_states = {'reservoirs': hs.get_initial_conditions()['H0']}

        result = run_and_score(
            config_tmpl,
            t_recession      = [10 ** _get(f'log__t_recession_{l}')
                                 for l in reservoir_order],
            f_to_discharge   = [_get(f'f_exfiltration_{l}')
                                 for l in reservoir_order[:-1]],
            melt_factor      =  _get('PDD_melt_factor'),
            fdd_threshold    =  10 ** _get('log__fdd_threshold'),
            snow_insulation_k=  _get('snow_insulation_k'),
            direct_runoff_fraction = _get('f_direct_runoff'),
            baseflow_Q       =  _get('baseflow_Q'),
            recession_exponents    =  _rec_exp(),
            routing_K        =  10 ** _get('log__routing_K'),
            routing_N        =  routing_N,
            modules          =  modules,
            enforce_water_balance = enforce_wb,
            spin_up_cycles   =  spin_up,
            initial_states   =  init_states,
            start            =  decade_start,
            end              =  decade_end_nominal,
            metric           =  drv['metric'],
        )
        b    = result.buckets
        mask = (b.hydrodata['Specific Discharge (modeled) [mm/day]'].notna()
                & b.hydrodata['Specific Discharge [mm/day]'].notna())
        if decade_start:
            mask &= b.hydrodata['Date'] >= pd.Timestamp(decade_start)
        if decade_end_nominal:
            mask &= b.hydrodata['Date'] <= pd.Timestamp(decade_end_nominal)
        m    = b.hydrodata.loc[mask, 'Specific Discharge (modeled) [mm/day]'].values
        o    = b.hydrodata.loc[mask, 'Specific Discharge [mm/day]'].values

        metrics = {
            'neg_kge':    float(best_row['neg_kge']),
            'logKGE':     float(_log_kge(m, o)),
            'NSE':        float(_nse(m, o)),
            'KGE':        float(_kge(m, o)),
            'KGE_logFDC': float(result.kge_logfdc),
            'AIC':        float(result.aic),
            'BFI_obs':    float(result.bfi_obs),
            'BFI_mod':    float(result.bfi_mod),
        }
        have_metrics = True
    except Exception as e:
        print(f"  Warning: could not re-run best fit for {label}: {e}")
        metrics = {}
        have_metrics = False

    # --- parameter values at best ---
    param_vals = {}
    for name, p in cfg['parameters'].items():
        if p['active'] and name in best_row.index:
            param_vals[name] = float(best_row[name])
        else:
            param_vals[name] = float(p['fixed'])

    row = {
        'decade':         label,
        'decade_start':   decade_start,
        'decade_end':     decade_end_nominal,
        'data_start':     data_start,
        'data_end':       data_end,
        'n_days_window':  n_window,
        'n_days_data':    n_data,
        'pct_data':       round(pct, 1) if not np.isnan(pct) else float('nan'),
        'best_run':       best_dir.name,
        'n_evaluations':  n_evals,
        **metrics,
        **{f'param_{k}': v for k, v in param_vals.items()},
    }
    rows.append(row)
    status = f"  {label}: pct_data={pct:.1f}%"
    if have_metrics:
        status += f", KGE={metrics['KGE']:.3f}, AIC={metrics['AIC']:.0f}"
    print(status)

summary = pd.DataFrame(rows)
summary.to_csv(OUT_PATH, index=False, float_format='%.6g')
print(f"\nWrote {len(summary)} rows → {OUT_PATH}")
