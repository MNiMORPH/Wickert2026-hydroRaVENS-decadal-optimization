#!/usr/bin/env python3
"""
Forward-run analysis: backbone vs. transient for all calibrated decades.
Runs each decade with store_depths=True; computes KGE, mean H, tau_local.

Backbone: backbone best-fit geology+snow + fixed soil, enforce_wb='global'
Transient: backbone best-fit + per-decade calibrated soil, enforce_wb='none'
"""

import sys
import os
import warnings
import numpy as np
import pandas as pd
import yaml

warnings.filterwarnings('ignore', message=r"enforce_water_balance='none'")
warnings.filterwarnings('ignore', message=r"f_to_discharge of bottom")
warnings.filterwarnings('ignore', message=r"et_scale=")

sys.path.insert(0, '/home/awickert/models/MNiShed')
from mnished.mnished import Buckets
from mnished.calibration import _kge_logkge as _calib_kge_logkge, _steady_state_depths

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
CONFIG = ('/home/awickert/dataanalysis/Wickert2026-hydroRaVENS-decadal-optimization'
          '/cannon_river/cannon_config_1893_2024.yml')
DECADES_DIR = ('/home/awickert/dataanalysis/Wickert2026-hydroRaVENS-decadal-optimization'
               '/cannon_river/decades')

MODULES = dict(snowpack=True, frozen_ground=True, rain_on_snow=True,
               direct_runoff=False, dtr_fgi_decay=True,
               et_water_stress=False, et_reservoir_draw=True)

# H_ref values per reservoir — must match calibration.py _H_REFS
H_REFS = [50.0, 100.0, 1000.0]

# Backbone best-fit params (eval_id=1597, backbone_v1)
BB = dict(
    log_tau_int   = 4.856558642,
    log_tau_deep  = 4.131880144,
    log_R_int     = 3.108478009,
    f_deep        = 0.4328203447,
    log_Ht_deep   = 2.798357124,
    melt_factor   = 5.61056713,
    log_fdd       = 2.904192387,
    # Soil fixed (backbone calibration)
    log_tau_soil  = 3.9,
    b_soil        = 5.0,
    f_soil        = 0.53,
    et_scale      = 1.0,
    b_int         = 2.203,   # Brutsaert-Nieber, fixed across all runs
)

# Calibrated decades: (decade_label, start, end, run_dir, spin_up_cycles)
# 1971-1980 and 1981-1990 have <10% discharge coverage — skipped in calibration
CALIBRATED = [
    ('1931-1940', '1931-01-01', '1940-12-31',
     f'{DECADES_DIR}/1931-1940/runs/2026-06-18_024454_spinup_fix', 1),
    ('1941-1950', '1941-01-01', '1950-12-31',
     f'{DECADES_DIR}/1941-1950/runs/2026-06-18_020401_transient_v2', 0),
    ('1951-1960', '1951-01-01', '1960-12-31',
     f'{DECADES_DIR}/1951-1960/runs/2026-06-18_020401_transient_v2', 0),
    ('1961-1970', '1961-01-01', '1970-12-31',
     f'{DECADES_DIR}/1961-1970/runs/2026-06-18_020401_transient_v2', 0),
    ('1991-2000', '1991-01-01', '2000-12-31',
     f'{DECADES_DIR}/1991-2000/runs/2026-06-18_020401_transient_v2', 0),
    ('2001-2010', '2001-01-01', '2010-12-31',
     f'{DECADES_DIR}/2001-2010/runs/2026-06-18_020401_transient_v2', 0),
    ('2011-2020', '2011-01-01', '2020-12-31',
     f'{DECADES_DIR}/2011-2020/runs/2026-06-18_020401_transient_v2', 0),
]

_MATTR = {
    'snowpack': 'use_snowpack', 'frozen_ground': 'use_frozen_ground',
    'rain_on_snow': 'use_rain_on_snow', 'direct_runoff': 'use_direct_runoff',
    'dtr_fgi_decay': 'use_dtr_fgi_decay', 'et_water_stress': 'use_et_water_stress',
    'et_reservoir_draw': 'use_et_reservoir_draw',
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def kge_logkge(mod, obs):
    mask = np.isfinite(mod) & np.isfinite(obs)
    m, o = mod[mask], obs[mask]
    if len(m) < 3:
        return np.nan
    return _calib_kge_logkge(m, o)


def make_buckets(enforce_wb):
    b = Buckets()
    b.initialize(CONFIG, enforce_water_balance=enforce_wb)
    for mod, val in MODULES.items():
        if mod in _MATTR:
            setattr(b, _MATTR[mod], val)
    if not b.use_snowpack:
        b.has_snowpack = False
    if not b.use_dtr_fgi_decay:
        b._has_trange = False
    if b.use_et_water_stress or b.use_et_reservoir_draw:
        b.compute_ET()
    return b


def set_backbone_params(b, log_tau_soil=None, b_soil=None, f_soil=None, et_scale=None):
    """Apply backbone + optional per-decade soil overrides to Buckets b."""
    _log_tau_soil = log_tau_soil if log_tau_soil is not None else BB['log_tau_soil']
    _b_soil       = b_soil       if b_soil       is not None else BB['b_soil']
    _f_soil       = f_soil       if f_soil       is not None else BB['f_soil']
    _et_scale     = et_scale     if et_scale     is not None else BB['et_scale']

    # Soil (nonlinear, fraction junction)
    b.reservoirs[0].recession_coeff    = 10 ** _log_tau_soil
    b.reservoirs[0].recession_exponent = _b_soil
    b.reservoirs[0].recession_H_ref    = H_REFS[0]
    b.reservoirs[0].f_to_discharge     = _f_soil
    b.reservoirs[0].junction_type      = 'fraction'

    # Intermediate (nonlinear, leakance junction)
    b.reservoirs[1].recession_coeff    = 10 ** BB['log_tau_int']
    b.reservoirs[1].recession_exponent = BB['b_int']
    b.reservoirs[1].recession_H_ref    = H_REFS[1]
    b.reservoirs[1].leakance_R         = 10 ** BB['log_R_int']
    b.reservoirs[1].junction_type      = 'leakance'

    # Deep (linear, threshold junction)
    b.reservoirs[2].recession_coeff    = 10 ** BB['log_tau_deep']
    b.reservoirs[2].recession_exponent = 1.0
    b.reservoirs[2].recession_H_ref    = H_REFS[2]
    b.reservoirs[2].H_threshold        = 10 ** BB['log_Ht_deep']
    b.reservoirs[2].f_to_discharge     = BB['f_deep']
    b.reservoirs[2].junction_type      = 'threshold'

    # Snow / FGI
    if b.has_snowpack:
        b.snowpack.melt_factor = BB['melt_factor']
        b.melt_factor = BB['melt_factor']
    b.fdd_threshold = 10 ** BB['log_fdd']

    # ET
    b.et_scale = _et_scale
    b.compute_ET()


def get_best_transient_params(run_dir):
    """Return dict of best calibrated soil params from evaluations file."""
    pyml = os.path.join(run_dir, 'params.yml')
    with open(pyml) as f:
        p = yaml.safe_load(f)
    active = [k for k, v in p['parameters'].items() if v.get('active', False)]

    # Try evaluations.dat first, then dakota.dat
    for fname in ('evaluations.dat', 'dakota.dat'):
        fpath = os.path.join(run_dir, fname)
        if os.path.exists(fpath):
            df = pd.read_csv(fpath, sep=r'\s+', comment='%',
                             names=['eval_id', 'interface'] + active + ['neg_kge'])
            best = df.loc[df['neg_kge'].idxmin()]
            return {n: float(best[n]) for n in active + ['neg_kge']}
    raise FileNotFoundError(f"No evaluations file found in {run_dir}")


def get_h0_from_params_yml(run_dir):
    """Read H0 initial states from params.yml for chained decades."""
    pyml = os.path.join(run_dir, 'params.yml')
    with open(pyml) as f:
        p = yaml.safe_load(f)
    params = p['parameters']
    return {
        'reservoirs': [
            10 ** float(params['log__H0_soil']['fixed']),
            10 ** float(params['log__H0_intermediate']['fixed']),
            10 ** float(params['log__H0_deep']['fixed']),
        ],
        'snowpack':        float(params.get('H0_snowpack', {}).get('fixed', 0.0)),
        'fgi':             float(params.get('H0_fgi', {}).get('fixed', 0.0)),
        'H_deficit_carry': float(params.get('H0_deficit_carry', {}).get('fixed', 0.0)),
    }


def apply_initial_states(b, states):
    for i, h in enumerate(states['reservoirs']):
        b.reservoirs[i].Hwater = h
    if b.has_snowpack:
        b.snowpack.Hwater = states.get('snowpack', 0.0)
    b._fgi = states.get('fgi', 0.0)
    b.H_deficit_carry = states.get('H_deficit_carry', 0.0)


def _set_ss_depths(b):
    """Set analytical steady-state depths (matching run_and_score behaviour)."""
    q_obs  = b.hydrodata['Specific Discharge [mm/day]'].dropna()
    mean_q = float(q_obs.mean())
    if np.isfinite(mean_q) and mean_q > 0:
        mean_q_eff = (mean_q - b.baseflow_Q) * (1.0 - b.direct_runoff_fraction)
        for res, h in zip(b.reservoirs, _steady_state_depths(b.reservoirs, mean_q_eff)):
            res.Hwater = h


def run_decade(b, start, end, spin_up_cycles):
    """Spin up and run one decade. Returns (score, mean_H_list, final_states)."""
    pre_end = (pd.Timestamp(start) - pd.Timedelta(days=1)).strftime('%Y-%m-%d')
    b.H_deficit_carry = 0.0
    for _ in range(spin_up_cycles):
        b.run(end=pre_end)
    b.run(start=start, end=end, store_depths=True)

    hd = b.hydrodata
    date_mask = (hd['Date'] >= pd.Timestamp(start)) & (hd['Date'] <= pd.Timestamp(end))
    q_mod = pd.to_numeric(hd.loc[date_mask, 'Specific Discharge (modeled) [mm/day]'],
                          errors='coerce')
    q_obs = pd.to_numeric(hd.loc[date_mask, 'Specific Discharge [mm/day]'], errors='coerce')
    valid = q_mod.notna() & q_obs.notna()
    score = kge_logkge(q_mod[valid].values, q_obs[valid].values) if valid.sum() >= 3 else np.nan

    mean_H = []
    for i in range(len(b.reservoirs)):
        col = f'H_reservoir_{i} (modeled) [mm]'
        vals = pd.to_numeric(hd.loc[date_mask, col], errors='coerce') if col in hd.columns \
               else pd.Series(dtype=float)
        mean_H.append(float(vals.dropna().mean()) if len(vals.dropna()) > 0 else np.nan)

    final_states = {
        'reservoirs':      [res.Hwater for res in b.reservoirs],
        'snowpack':        b.snowpack.Hwater if b.has_snowpack else 0.0,
        'fgi':             b._fgi,
        'H_deficit_carry': 0.0,
    }
    return score, mean_H, final_states


# ---------------------------------------------------------------------------
# Run backbone (shared params, enforce_wb='global')
# Run full record in one pass (matching backbone calibration approach), then
# score each decade window separately.  Avoids SS-init artifacts from the
# very long τ_soil (7943 d) — the full-record spin-up equilibrates slowly.
# ---------------------------------------------------------------------------
print("Running backbone forward pass (full record) …")
bb_rows = []

b = make_buckets('global')
set_backbone_params(b)
_set_ss_depths(b)
# One spin-up cycle over the full record, then run+store full record
b.H_deficit_carry = 0.0
b.run()
b.run(store_depths=True)

bb_hd = b.hydrodata.copy()
tau_raw_bb = b.reservoirs[0].recession_coeff
b_exp_bb   = b.reservoirs[0].recession_exponent
H_ref_bb   = b.reservoirs[0].recession_H_ref

for label, start, end, run_dir, _ in CALIBRATED:
    dm = (bb_hd['Date'] >= pd.Timestamp(start)) & (bb_hd['Date'] <= pd.Timestamp(end))
    qm = pd.to_numeric(bb_hd.loc[dm, 'Specific Discharge (modeled) [mm/day]'], errors='coerce')
    qo = pd.to_numeric(bb_hd.loc[dm, 'Specific Discharge [mm/day]'], errors='coerce')
    valid = qm.notna() & qo.notna()
    score = kge_logkge(qm[valid].values, qo[valid].values) if valid.sum() >= 3 else np.nan

    mean_H = []
    for i in range(3):
        col = f'H_reservoir_{i} (modeled) [mm]'
        vals = pd.to_numeric(bb_hd.loc[dm, col], errors='coerce')
        mean_H.append(float(vals.dropna().mean()) if len(vals.dropna()) > 0 else np.nan)

    tau_loc = tau_raw_bb * (H_ref_bb / mean_H[0]) ** (b_exp_bb - 1) \
              if mean_H[0] > 0 else np.nan

    bb_rows.append(dict(
        decade=label, run='backbone', KGE=score,
        log_tau_soil=BB['log_tau_soil'], b_soil=BB['b_soil'],
        f_soil=BB['f_soil'], et_scale=BB['et_scale'],
        mean_H_soil=mean_H[0], mean_H_int=mean_H[1], mean_H_deep=mean_H[2],
        tau_local=tau_loc,
    ))
    print(f"  {label}: KGE={score:.3f}  <H>_soil={mean_H[0]:.1f} mm  τ_local={tau_loc:.1f} d")

# ---------------------------------------------------------------------------
# Run transient (per-decade soil params, enforce_wb='none', stored H0 ICs)
# ---------------------------------------------------------------------------
print("\nRunning transient forward pass …")
tr_rows = []

for label, start, end, run_dir, suc in CALIBRATED:
    bp = get_best_transient_params(run_dir)

    b = make_buckets('none')
    set_backbone_params(b,
                        log_tau_soil=bp['log__recession_coeff_soil'],
                        b_soil=bp['recession_b_soil'],
                        f_soil=bp['f_exfiltration_soil'],
                        et_scale=bp['et_scale'])
    _set_ss_depths(b)   # analytical SS init before possible override

    # Chained decades: use H0 states stored in params.yml (set by run_transient.sh)
    if suc == 0:
        apply_initial_states(b, get_h0_from_params_yml(run_dir))

    score, mean_H, _ = run_decade(b, start, end, suc)

    tau_raw = b.reservoirs[0].recession_coeff
    b_exp   = b.reservoirs[0].recession_exponent
    H_ref   = b.reservoirs[0].recession_H_ref
    tau_loc = tau_raw * (H_ref / mean_H[0]) ** (b_exp - 1) if mean_H[0] > 0 else np.nan

    tr_rows.append(dict(
        decade=label, run='transient', KGE=score,
        log_tau_soil=bp['log__recession_coeff_soil'], b_soil=bp['recession_b_soil'],
        f_soil=bp['f_exfiltration_soil'], et_scale=bp['et_scale'],
        mean_H_soil=mean_H[0], mean_H_int=mean_H[1], mean_H_deep=mean_H[2],
        tau_local=tau_loc,
    ))
    print(f"  {label}: KGE={score:.3f}  log_τ={bp['log__recession_coeff_soil']:.2f}  "
          f"b={bp['recession_b_soil']:.2f}  f={bp['f_exfiltration_soil']:.3f}  "
          f"et={bp['et_scale']:.3f}  <H>_soil={mean_H[0]:.1f} mm  τ_local={tau_loc:.1f} d")

# ---------------------------------------------------------------------------
# Summary tables
# ---------------------------------------------------------------------------
df = pd.DataFrame(bb_rows + tr_rows)
W = 120

print()
print("=" * W)
print("BACKBONE (shared params: fixed soil log_τ=3.9, b=5.0, f=0.53; enforce_wb=global)")
print("=" * W)
print(f"{'Decade':<12} {'KGE':>6}  "
      f"{'<H>_soil':>9} {'<H>_int':>9} {'<H>_deep':>10}  "
      f"{'τ_local[d]':>11}")
print("-" * W)
for r in bb_rows:
    print(f"{r['decade']:<12} {r['KGE']:6.3f}  "
          f"{r['mean_H_soil']:9.1f} {r['mean_H_int']:9.1f} {r['mean_H_deep']:10.1f}  "
          f"{r['tau_local']:11.1f}")

print()
print("=" * W)
print("TRANSIENT (per-decade soil params; enforce_wb=none)")
print("=" * W)
print(f"{'Decade':<12} {'KGE':>6}  {'log_τ':>6} {'b':>5} {'f_soil':>7} {'et_scale':>9}  "
      f"{'<H>_soil':>9} {'<H>_int':>9} {'<H>_deep':>10}  {'τ_local[d]':>11}")
print("-" * W)
for r in tr_rows:
    print(f"{r['decade']:<12} {r['KGE']:6.3f}  "
          f"{r['log_tau_soil']:6.2f} {r['b_soil']:5.2f} {r['f_soil']:7.3f} {r['et_scale']:9.3f}  "
          f"{r['mean_H_soil']:9.1f} {r['mean_H_int']:9.1f} {r['mean_H_deep']:10.1f}  "
          f"{r['tau_local']:11.1f}")

print()
print("=" * W)
print("KGE COMPARISON: backbone vs. transient")
print("=" * W)
print(f"{'Decade':<12} {'KGE_bb':>8} {'KGE_tr':>8} {'ΔKGE':>7}")
print("-" * W)
for bb_r, tr_r in zip(bb_rows, tr_rows):
    delta = tr_r['KGE'] - bb_r['KGE']
    print(f"{bb_r['decade']:<12} {bb_r['KGE']:8.3f} {tr_r['KGE']:8.3f} {delta:+7.3f}")

print()
print(f"τ_local = τ_raw × (H_ref / <H>)^(b−1)  where H_ref = {H_REFS[0]} mm for soil")
print("All depths in mm, τ in days.")
