#!/usr/bin/env python3
"""
Find the best-fit parameters from a completed Dakota calibration run,
re-run hydroRaVENS with those parameters, and produce a diagnostic plot.

Figure layout
-------------
Left column  : precipitation (top, inverted) + observed/modelled discharge
Right column : flow duration curve (log scale) with observed BFI annotated

Usage (from cannon_river/):
    python plot_best.py                      # uses dakota.dat, saves best_fit.png
    python plot_best.py --dat dakota_test.dat --save test_fit.png
"""

import argparse
import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from hydroravens import run_and_score
from hydroravens.calibration import _nse

CFG_TEMPLATE  = 'cannon_cfg_template.yml'
OBJECTIVE_COL = 'neg_kge'
METRIC        = 'NSE'
ROUTING_N     = 2      # Nash-cascade shape; must match driver.py ROUTING_N


def read_best_params(dat_file):
    try:
        df = pd.read_csv(dat_file, sep=r'\s+')
    except FileNotFoundError:
        sys.exit(f'Error: {dat_file} not found. Run Dakota first.')
    df = df.rename(columns={'%eval_id': 'eval_id'})
    for col in df.columns:
        if col != 'interface':
            df[col] = pd.to_numeric(df[col], errors='coerce')
    return df.loc[df[OBJECTIVE_COL].idxmin()]


def run_model(params):
    return run_and_score(
        CFG_TEMPLATE,
        t_efold        = [10 ** params['log__t_efold_shallow'],
                          10 ** params['log__t_efold_deep']],
        f_to_discharge = [params['f_exfiltration_shallow']],
        melt_factor    =  params['PDD_melt_factor'],
        Hmax           = [10 ** params['log__Hmax_shallow']],
        routing_K      =  10 ** params['log__routing_K'],
        routing_N      =  ROUTING_N,
        metric         =  METRIC,
    )


def make_plot(result, params, save_path, metric=METRIC):
    b     = result.buckets
    score = result.score
    aic   = result.aic

    mask  = (b.hydrodata['Specific Discharge (modeled) [mm/day]'].notna()
             & b.hydrodata['Specific Discharge [mm/day]'].notna())
    m_all = np.asarray(b.hydrodata.loc[mask, 'Specific Discharge (modeled) [mm/day]'])
    o_all = np.asarray(b.hydrodata.loc[mask, 'Specific Discharge [mm/day]'])
    nse   = _nse(m_all, o_all)   # always shown for reference

    dates = b.hydrodata['Date']

    # --- Figure layout: left column (time series) + right column (FDC) ---
    fig = plt.figure(figsize=(14, 7))
    gs  = fig.add_gridspec(2, 2, width_ratios=[3, 1], height_ratios=[1, 2.5],
                           hspace=0.05, wspace=0.25)
    ax_p   = fig.add_subplot(gs[0, 0])
    ax_q   = fig.add_subplot(gs[1, 0], sharex=ax_p)
    ax_fdc = fig.add_subplot(gs[:, 1])

    # --- Precipitation (inverted) ---
    ax_p.bar(dates, b.hydrodata['Precipitation [mm/day]'],
             width=1, color='steelblue', alpha=0.7)
    ax_p.set_ylabel('Precip.\n[mm/day]')
    ax_p.invert_yaxis()
    ax_p.yaxis.set_label_position('right')
    ax_p.yaxis.tick_right()
    plt.setp(ax_p.get_xticklabels(), visible=False)

    # --- Discharge time series ---
    ax_q.plot(dates, b.hydrodata['Specific Discharge [mm/day]'],
              color='royalblue', lw=1.5, label='Observed')
    ax_q.plot(dates, b.hydrodata['Specific Discharge (modeled) [mm/day]'],
              color='k', lw=1.5, label='Modelled')
    ax_q.set_ylabel('Specific discharge [mm/day]')
    ax_q.set_xlabel('Date')
    ax_q.set_ylim(bottom=0)
    ax_q.legend(loc='upper right', fontsize=9)
    ax_q.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    plt.setp(ax_q.get_xticklabels(), rotation=30, ha='right')

    # Annotation box
    t_shallow = 10 ** params['log__t_efold_shallow']
    t_deep    = 10 ** params['log__t_efold_deep']
    routing_K = 10 ** params['log__routing_K']
    score_str = f'{metric} = {score:.3f}'
    if metric != 'NSE':
        score_str += f'   NSE = {nse:.3f}'
    ann = (
        f'{score_str}   AIC = {aic:.1f}\n'
        f'BFI: obs = {result.bfi_obs:.3f},  mod = {result.bfi_mod:.3f}\n'
        f'$\\tau_{{shallow}}$ = {t_shallow:.1f} d,  '
        f'$\\tau_{{deep}}$ = {t_deep:.0f} d\n'
        f'$f_{{exfilt}}$ = {params["f_exfiltration_shallow"]:.3f},  '
        f'PDD = {params["PDD_melt_factor"]:.2f} mm °C$^{{-1}}$ d$^{{-1}}$\n'
        f'$H_{{max}}$ = {10**params["log__Hmax_shallow"]:.0f} mm,  '
        f'$K_{{route}}$ = {routing_K:.2f} d  (N={ROUTING_N})'
    )
    ax_q.text(0.02, 0.97, ann, transform=ax_q.transAxes,
              va='top', fontsize=8.5,
              bbox=dict(boxstyle='round', facecolor='white', alpha=0.85))

    # --- Flow duration curve ---
    ax_fdc.semilogy(result.fdc_obs.index, result.fdc_obs.values,
                    color='royalblue', lw=1.5, label='Observed')
    ax_fdc.semilogy(result.fdc_mod.index, result.fdc_mod.values,
                    color='k', lw=1.5, label='Modelled')
    ax_fdc.set_xlabel('Exceedance probability [%]')
    ax_fdc.set_ylabel('Specific discharge [mm/day]')
    ax_fdc.set_xlim(0, 100)
    ax_fdc.legend(fontsize=9)
    ax_fdc.set_title('Flow duration curve', fontsize=10)
    ax_fdc.grid(True, which='both', alpha=0.3)

    fig.suptitle('hydroRaVENS – Cannon River best-fit calibration', fontsize=13)

    plt.savefig(save_path, dpi=150, bbox_inches='tight')
    print(f'Figure saved to {save_path}')
    plt.show()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--dat',  default='dakota.dat',   help='Dakota tabular data file')
    parser.add_argument('--save', default='best_fit.png', help='Output figure path')
    args = parser.parse_args()

    best = read_best_params(args.dat)

    t_shallow = 10 ** best['log__t_efold_shallow']
    t_deep    = 10 ** best['log__t_efold_deep']
    routing_K = 10 ** best['log__routing_K']
    print(f'\nBest evaluation: {int(best["eval_id"])}')
    print(f'  {METRIC:<14}  = {1 - best[OBJECTIVE_COL]:.4f}')
    print(f'  t_efold_shallow = {t_shallow:.1f} days')
    print(f'  t_efold_deep    = {t_deep:.0f} days')
    print(f'  f_exfiltration  = {best["f_exfiltration_shallow"]:.4f}')
    print(f'  PDD_melt_factor = {best["PDD_melt_factor"]:.4f} mm/°C/day')
    print(f'  Hmax_shallow    = {10**best["log__Hmax_shallow"]:.1f} mm')
    print(f'  routing_K       = {routing_K:.3f} days  (N={ROUTING_N},'
          f' mean travel time = {ROUTING_N * routing_K:.2f} days)')

    result = run_model(best)
    print(f'  AIC             = {result.aic:.2f}')
    print(f'  BFI obs         = {result.bfi_obs:.4f}')
    print(f'  BFI mod         = {result.bfi_mod:.4f}')

    make_plot(result, best, save_path=args.save, metric=METRIC)
