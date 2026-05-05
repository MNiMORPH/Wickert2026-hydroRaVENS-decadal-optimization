#!/usr/bin/env python3
"""
Find the best-fit parameters from a completed Dakota calibration run,
re-run hydroRaVENS with those parameters, and produce a diagnostic plot.

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

CFG_TEMPLATE = 'cannon_cfg_template.yml'


def read_best_params(dat_file):
    try:
        df = pd.read_csv(dat_file, sep=r'\s+')
    except FileNotFoundError:
        sys.exit(f'Error: {dat_file} not found. Run Dakota first.')
    df = df.rename(columns={'%eval_id': 'eval_id'})
    return df.loc[df['neg_nse'].idxmin()]


def run_model(params):
    _, b = run_and_score(
        CFG_TEMPLATE,
        t_efold        = [10 ** params['log__t_efold_shallow'],
                          10 ** params['log__t_efold_deep']],
        f_to_discharge = [params['f_exfiltration_shallow']],
        melt_factor    =  params['PDD_melt_factor'],
    )
    return b


def make_plot(b, params, save_path):
    nse = b.computeNSE(return_nse=True, verbose=False)

    fig, (ax_p, ax_q) = plt.subplots(
        2, 1, figsize=(12, 7), sharex=True,
        gridspec_kw={'height_ratios': [1, 2]}
    )

    dates = b.hydrodata['Date']

    # --- Precipitation (top, inverted so rain "falls" down) ---
    ax_p.bar(dates, b.hydrodata['Precipitation [mm/day]'],
             width=1, color='steelblue', alpha=0.7)
    ax_p.set_ylabel('Precipitation\n[mm/day]')
    ax_p.invert_yaxis()
    ax_p.yaxis.set_label_position('right')
    ax_p.yaxis.tick_right()

    # --- Discharge (bottom) ---
    ax_q.plot(dates, b.hydrodata['Specific Discharge [mm/day]'],
              color='royalblue', lw=1.5, label='Observed')
    ax_q.plot(dates, b.hydrodata['Specific Discharge (modeled) [mm/day]'],
              color='k', lw=1.5, label='Modeled')
    ax_q.set_ylabel('Specific discharge [mm/day]')
    ax_q.set_xlabel('Date')
    ax_q.set_ylim(bottom=0)
    ax_q.legend(loc='upper right')

    ax_q.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    plt.setp(ax_q.get_xticklabels(), rotation=30, ha='right')

    # Parameter + NSE annotation
    t_shallow = 10 ** params['log__t_efold_shallow']
    t_deep    = 10 ** params['log__t_efold_deep']
    ann = (
        f'NSE = {nse:.3f}\n'
        f'$\\tau_{{shallow}}$ = {t_shallow:.1f} d\n'
        f'$\\tau_{{deep}}$ = {t_deep:.0f} d\n'
        f'$f_{{exfilt}}$ = {params["f_exfiltration_shallow"]:.3f}\n'
        f'PDD factor = {params["PDD_melt_factor"]:.2f} mm °C$^{{-1}}$ d$^{{-1}}$'
    )
    ax_q.text(0.02, 0.97, ann, transform=ax_q.transAxes,
              va='top', fontsize=9,
              bbox=dict(boxstyle='round', facecolor='white', alpha=0.85))

    fig.suptitle('hydroRaVENS – Cannon River best-fit calibration', fontsize=13)
    plt.tight_layout()

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
    print(f'\nBest evaluation: {int(best["eval_id"])}')
    print(f'  NSE             = {1 - best["neg_nse"]:.4f}')
    print(f'  t_efold_shallow = {t_shallow:.1f} days')
    print(f'  t_efold_deep    = {t_deep:.0f} days')
    print(f'  f_exfiltration  = {best["f_exfiltration_shallow"]:.4f}')
    print(f'  PDD_melt_factor = {best["PDD_melt_factor"]:.4f} mm/°C/day')

    b = run_model(best)
    make_plot(b, best, save_path=args.save)
