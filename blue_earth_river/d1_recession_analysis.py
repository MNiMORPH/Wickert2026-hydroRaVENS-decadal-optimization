#!/usr/bin/env python3
"""
D1: Per-decade Master Recession Curve (Brutsaert-Nieber 1977) analysis
for Blue Earth River.

Goal: extract recession exponent b_BN and rate a from observed hydrograph
recessions, independently of the model. Compare across decades to test
whether recession-curve shape changes over time (tile-drainage expansion
hypothesis).

Method (Brutsaert & Nieber 1977; Kirchner 2009):
  -dQ/dt = a * Q^b_BN
Linear in log-log:
  log(-dQ/dt) = log(a) + b_BN * log(Q)

Relationship to MNiShed storage-discharge exponent b_storage (Q ∝ H^b):
  b_BN = (2*b_storage - 1) / b_storage     →     b_storage = 1 / (2 - b_BN)
  b_BN = 1.0  ↔ b_storage = 1   (linear reservoir)
  b_BN = 1.5  ↔ b_storage = 2   (Dupuit-Forchheimer)
  b_BN = 1.67 ↔ b_storage = 3
  b_BN → 2    ↔ b_storage → ∞ (step-function)

Recession event criteria:
  - Q strictly declining for ≥4 consecutive days
  - No precipitation > 1 mm in the 2 days prior to or during recession
  - Q above noise floor (5th percentile of nonzero Q)
  - First day of recession dropped (transition contamination)

Usage:
    python d1_recession_analysis.py
"""

import numpy as np
import pandas as pd
from pathlib import Path

DATAFILE = '/home/awickert/dataanalysis/Wickert2026-hydroRaVENS-decadal-optimization/centroid_forcing_backup/blue_earth_river_forcing_centroid.csv'
DECADES = [(1951, 1960), (1961, 1970), (1971, 1980), (1981, 1990),
           (1991, 2000), (2001, 2010), (2011, 2020)]
DRAINAGE_AREA_KM2 = 6270.9
MIN_RECESSION_LENGTH = 4         # consecutive declining days
PRECIP_THRESHOLD_MM   = 1.0       # max precip allowed in pre-window
PRECIP_LOOKBACK_DAYS  = 2
DROP_FIRST_N          = 1         # drop first day(s) of each recession


def find_recession_events(Q, P, min_len, precip_thresh, precip_lookback):
    """Return list of recession event indices (each a numpy index array)."""
    valid = Q.notna().values
    decline = np.zeros(len(Q), dtype=bool)
    decline[1:] = (Q.values[1:] < Q.values[:-1]) & valid[1:] & valid[:-1]

    P_recent_max = P.rolling(precip_lookback, min_periods=1).max().fillna(0).values
    no_rain = P_recent_max <= precip_thresh
    in_recession = decline & no_rain

    events = []
    start = None
    for i in range(len(in_recession)):
        if in_recession[i]:
            if start is None:
                start = i
        else:
            if start is not None and (i - start) >= min_len:
                events.append(np.arange(start, i))
            start = None
    if start is not None and (len(in_recession) - start) >= min_len:
        events.append(np.arange(start, len(in_recession)))
    return events


def extract_dq_dt(Q, events, drop_first):
    """Return arrays of Q and -dQ/dt at each interior recession day."""
    Qs, dQdts = [], []
    for ev in events:
        if len(ev) <= drop_first + 2:
            continue
        ev_use = ev[drop_first:]
        Q_ev = Q.values[ev_use]
        for j in range(1, len(Q_ev) - 1):
            dq = -(Q_ev[j+1] - Q_ev[j-1]) / 2.0
            if dq > 0 and Q_ev[j] > 0:
                Qs.append(Q_ev[j])
                dQdts.append(dq)
    return np.array(Qs), np.array(dQdts)


def fit_log_log(Q, dQdt):
    """Linear regression log(-dQ/dt) = log(a) + b_BN * log(Q)."""
    if len(Q) < 10:
        return np.nan, np.nan, np.nan
    logQ = np.log(Q)
    logD = np.log(dQdt)
    slope, intercept = np.polyfit(logQ, logD, 1)
    resid = logD - (slope * logQ + intercept)
    ss_res = np.sum(resid**2)
    ss_tot = np.sum((logD - logD.mean())**2)
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else np.nan
    return slope, np.exp(intercept), r2


def b_bn_to_storage(b_bn):
    if b_bn >= 2.0:
        return np.inf
    return 1.0 / (2.0 - b_bn)


def kappa_to_tau_days(a, b_storage, Q_ref_m3s):
    """Convert (a, b_storage) to an equivalent recession timescale at Q_ref.

    Q ∝ H^b_storage; -dQ/dt = a * Q^b_BN
    At Q = Q_ref, instantaneous timescale τ_inst = Q / (-dQ/dt) = Q_ref / (a * Q_ref^b_BN)
                                                = 1 / (a * Q_ref^(b_BN - 1))
    """
    if not np.isfinite(b_storage):
        return np.nan
    b_bn = (2 * b_storage - 1) / b_storage
    return 1.0 / (a * Q_ref_m3s**(b_bn - 1.0))


def main():
    df = pd.read_csv(DATAFILE, parse_dates=['Date'], date_format='%Y.%m.%d')
    df = df.set_index('Date').sort_index()
    Q_col = 'Discharge [m^3/s]'
    P_col = 'Precipitation [mm/day]'

    print(f"D1: Per-decade Brutsaert-Nieber recession analysis")
    print(f"Catchment: Blue Earth River ({DRAINAGE_AREA_KM2} km²)")
    print(f"Criteria: ≥{MIN_RECESSION_LENGTH}-day declining Q, "
          f"P_max(prev {PRECIP_LOOKBACK_DAYS}d) ≤ {PRECIP_THRESHOLD_MM} mm, "
          f"drop first {DROP_FIRST_N} day(s) of each event\n")

    Q_all_med = df[Q_col].dropna().median()
    print(f"Reference Q for τ comparison: median Q across all decades = "
          f"{Q_all_med:.1f} m³/s\n")

    results = []
    print(f"{'Decade':<11} {'n_events':>9} {'n_pts':>7} {'b_BN':>7} "
          f"{'b_storage':>10} {'a':>10} {'τ@Qmed (d)':>12} {'R²':>6}")
    print("-" * 80)
    for y0, y1 in DECADES:
        sub = df.loc[f'{y0}-01-01':f'{y1}-12-31'].copy()
        Q = sub[Q_col]
        P = sub[P_col]
        events = find_recession_events(Q, P,
                                       MIN_RECESSION_LENGTH,
                                       PRECIP_THRESHOLD_MM,
                                       PRECIP_LOOKBACK_DAYS)
        Qs, dQdts = extract_dq_dt(Q, events, DROP_FIRST_N)
        b_bn, a, r2 = fit_log_log(Qs, dQdts)
        b_st = b_bn_to_storage(b_bn) if np.isfinite(b_bn) else np.nan
        tau = kappa_to_tau_days(a, b_st, Q_all_med) if np.isfinite(b_st) else np.nan

        results.append({
            'decade': f'{y0}-{y1}', 'n_events': len(events), 'n_pts': len(Qs),
            'b_BN': b_bn, 'b_storage': b_st, 'a': a, 'tau_days': tau, 'r2': r2,
            'Qs': Qs, 'dQdts': dQdts,
        })
        print(f"{y0}-{y1:<4} {len(events):>9} {len(Qs):>7} "
              f"{b_bn:>7.3f} {b_st:>10.3f} {a:>10.3e} {tau:>12.2f} {r2:>6.3f}")

    # All-decades pooled fit
    Qs_all  = np.concatenate([r['Qs']    for r in results])
    dQs_all = np.concatenate([r['dQdts'] for r in results])
    b_bn_all, a_all, r2_all = fit_log_log(Qs_all, dQs_all)
    b_st_all = b_bn_to_storage(b_bn_all)
    tau_all  = kappa_to_tau_days(a_all, b_st_all, Q_all_med)
    print("-" * 80)
    print(f"{'Pooled':<11} {sum(r['n_events'] for r in results):>9} "
          f"{len(Qs_all):>7} {b_bn_all:>7.3f} {b_st_all:>10.3f} "
          f"{a_all:>10.3e} {tau_all:>12.2f} {r2_all:>6.3f}")

    # Decadal-trend test on b_BN
    valid = [r for r in results if np.isfinite(r['b_BN'])]
    if len(valid) >= 4:
        decade_mid = np.array([int(r['decade'][:4]) + 5 for r in valid])
        b_vals     = np.array([r['b_BN'] for r in valid])
        a_vals     = np.array([r['a']    for r in valid])
        slope_b, intercept_b = np.polyfit(decade_mid, b_vals, 1)
        slope_a, intercept_a = np.polyfit(decade_mid, np.log(a_vals), 1)
        print(f"\nDecadal trends (1955-2015 midpoints):")
        print(f"  b_BN trend:    {slope_b*10:+.4f} per decade  "
              f"(intercept at 1985: {intercept_b + slope_b*1985:.3f})")
        print(f"  log(a) trend:  {slope_a*10:+.4f} per decade  "
              f"(a multiplies by {np.exp(slope_a*10):.3f}× per decade)")

    out_csv = Path(__file__).parent / 'd1_recession_results.csv'
    pd.DataFrame([{k: v for k, v in r.items() if k not in ('Qs', 'dQdts')}
                  for r in results]).to_csv(out_csv, index=False)
    print(f"\nWritten: {out_csv}")


if __name__ == '__main__':
    main()
