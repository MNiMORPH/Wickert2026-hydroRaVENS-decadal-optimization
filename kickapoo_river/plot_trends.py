#!/usr/bin/env python3
"""
Plot calibrated parameter trends across decades.

Reads summary.csv and produces a multi-panel figure showing how each
calibrated parameter (and key fit metrics) varies decade to decade.
Decades with insufficient data (pct_data < PCT_MIN or KGE < KGE_MIN)
are shown as open symbols and excluded from trend lines.

Usage (from kickapoo_river/):
    python plot_trends.py
    python plot_trends.py --summary summary.csv --out trends.png
    python plot_trends.py --min-pct 50 --min-kge 0.3
"""

import argparse
import warnings
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker

warnings.filterwarnings('ignore')

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

parser = argparse.ArgumentParser()
parser.add_argument('--summary',  default='summary.csv')
parser.add_argument('--out',      default='trends.png')
parser.add_argument('--min-pct',  type=float, default=50.0,
                    help='Min pct_data to treat a decade as reliable (default 50)')
parser.add_argument('--min-kge',  type=float, default=0.0,
                    help='Min KGE to treat a decade as reliable (default 0)')
args = parser.parse_args()

df = pd.read_csv(args.summary)

# Decade mid-point year for x-axis
def _midpoint(label):
    parts = str(label).split('-')
    return (int(parts[0]) + int(parts[1])) / 2.0

df['mid_year'] = df['decade'].apply(_midpoint)
df = df.sort_values('mid_year').reset_index(drop=True)

# Reliable mask: enough data AND good fit
reliable = (df['pct_data'].fillna(0) >= args.min_pct)
if 'KGE' in df.columns:
    reliable &= (df['KGE'].fillna(-9) >= args.min_kge)

# ---------------------------------------------------------------------------
# Derived columns: mean residence time MRT = τ^(1/b) at Q_ref = 1 mm/day
#
# Exact form: MRT = τ^(1/b) / Q_ref^(1 - 1/b)
# At Q_ref = 1 mm/day this simplifies to τ^(1/b), a parameter-only
# composite that collapses the τ/b degeneracy without external data.
# For b = 1 (linear) MRT = τ exactly.
# ---------------------------------------------------------------------------

def _mrt(tau_col, b_col, b_fixed=None):
    tau = 10 ** df[tau_col].astype(float)
    b   = (df[b_col].astype(float) if b_col in df.columns
           else pd.Series(b_fixed, index=df.index))
    return tau ** (1.0 / b)

if 'param_log__t_recession_soil' in df.columns:
    b_col = ('param_recession_b_soil'
             if 'param_recession_b_soil' in df.columns else None)
    b_fix = 1.0 if b_col is None else None
    df['mrt_soil'] = _mrt('param_log__t_recession_soil', b_col or '', b_fixed=b_fix)

if 'param_log__t_recession_intermediate' in df.columns:
    b_col = ('param_recession_b_intermediate'
             if 'param_recession_b_intermediate' in df.columns else None)
    b_fix = 2.203 if b_col is None else None   # Brutsaert-Nieber fixed value
    df['mrt_intermediate'] = _mrt('param_log__t_recession_intermediate',
                                  b_col or '', b_fixed=b_fix)

if 'param_log__t_recession_deep' in df.columns:
    b_col = ('param_recession_b_deep'
             if 'param_recession_b_deep' in df.columns else None)
    b_fix = 1.0 if b_col is None else None
    df['mrt_deep'] = _mrt('param_log__t_recession_deep', b_col or '', b_fixed=b_fix)

# ---------------------------------------------------------------------------
# Panel definitions
# ---------------------------------------------------------------------------

# (column, label, transform, y_label, note)
PANELS = [
    # --- fit quality ---
    ('KGE',       'KGE',          None,           'KGE [ ]',            None),
    ('pct_data',  'Data coverage', None,            'Coverage [%]',       None),

    # --- mean residence times (nonlinearity-corrected) ---
    ('mrt_soil',
     'MRT soil',
     None,
     'MRT soil [days]',
     'τ_soil^(1/b_soil)  — soil-zone residence time'),

    ('mrt_intermediate',
     'MRT intermediate',
     None,
     'MRT intermediate [days]',
     'τ_int^(1/b_int)  — tile-drain signal'),

    ('mrt_deep',
     'MRT deep',
     None,
     'MRT deep [days]',
     'τ_deep^(1/b_deep)  — deep groundwater'),

    # --- recession exponents ---
    ('param_recession_b_soil',
     'Recession b (soil)',
     None,
     'Recession exponent b [ ]',
     'nonlinearity of soil drainage'),

    # --- exfiltration fractions ---
    ('param_f_exfiltration_soil',
     'f exfilt. soil',
     None,
     'f exfilt. soil [ ]',
     'fraction of soil drainage to stream'),

    ('param_f_exfiltration_intermediate',
     'f exfilt. intermediate',
     None,
     'f exfilt. intermediate [ ]',
     'fraction of intermediate drainage to stream — tile-drain signal'),

    # --- snowpack / frozen ground ---
    ('param_PDD_melt_factor',
     'PDD melt factor',
     None,
     'Melt factor [mm/°C/day]',
     None),

    ('param_log__fdd_threshold',
     'FDD threshold',
     lambda x: 10**x,
     'FDD threshold [°C·day]',
     'frozen-ground infiltration block'),
]

# Keep only panels whose column exists in the CSV
PANELS = [(col, lbl, tr, yl, note) for col, lbl, tr, yl, note in PANELS
          if col in df.columns]

# ---------------------------------------------------------------------------
# Figure
# ---------------------------------------------------------------------------

ncols = 2
nrows = int(np.ceil(len(PANELS) / ncols))
fig, axes = plt.subplots(nrows, ncols,
                         figsize=(13, 3.2 * nrows),
                         sharex=True)
axes = axes.flatten()

x     = df['mid_year'].values
x_rel = x[reliable.values]

for ax, (col, lbl, transform, ylabel, note) in zip(axes, PANELS):
    raw = df[col].values.astype(float)
    y   = transform(raw) if transform is not None else raw

    y_rel   = y[reliable.values]
    y_unrel = y[~reliable.values]
    x_unrel = x[~reliable.values]

    # Reliable decades: filled circles + trend line
    ax.plot(x_rel, y_rel, 'o', color='steelblue', ms=7, zorder=3,
            label='reliable')
    if len(x_rel) >= 2:
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', np.RankWarning)
            p = np.polyfit(x_rel, y_rel, 1)
        ax.plot(x_rel, np.polyval(p, x_rel), '-', color='steelblue',
                lw=1.5, alpha=0.6)

    # Unreliable decades: open circles, no trend
    if len(x_unrel):
        ax.plot(x_unrel, y_unrel, 'o', mfc='none', mec='gray',
                ms=7, zorder=2, label='low data / poor fit')

    ax.set_ylabel(ylabel, fontsize=9)
    ax.set_title(lbl, fontsize=10, fontweight='bold')
    if note:
        ax.set_title(f'{lbl}\n{note}', fontsize=9, fontweight='bold')
    ax.xaxis.set_major_locator(ticker.MultipleLocator(20))
    ax.xaxis.set_minor_locator(ticker.MultipleLocator(10))
    ax.grid(True, which='major', alpha=0.3)
    ax.grid(True, which='minor', alpha=0.1)

# Shared x-label on bottom row
for ax in axes[-ncols:]:
    ax.set_xlabel('Decade mid-year', fontsize=9)

# Legend on first axis
handles = [
    plt.Line2D([0], [0], marker='o', color='steelblue', lw=0, ms=7),
    plt.Line2D([0], [0], marker='o', color='gray', lw=0, ms=7,
               mfc='none', mec='gray'),
]
axes[0].legend(handles, ['reliable', 'low data / poor fit'],
               fontsize=8, loc='best')

# Hide unused axes
for ax in axes[len(PANELS):]:
    ax.set_visible(False)

fig.suptitle('Kickapoo River — decade-by-decade calibration trends',
             fontsize=13, fontweight='bold', y=1.01)
plt.tight_layout()
plt.savefig(args.out, dpi=150, bbox_inches='tight')
print(f'Saved {args.out}')
