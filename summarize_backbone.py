#!/usr/bin/env python3
"""
Summarize backbone Dakota calibration runs into a per-watershed
backbone_summary.csv.

For each <watershed>/backbone_runs/<run>/ this reads the Dakota
evaluations.dat (whose '%'-prefixed header carries the column names) plus
the run's params.yml, finds the best evaluation (minimum objective; the
response column is named neg_kge for every metric), and writes one row per
backbone version: run name, metric, config template, evaluation count, best
eval_id, best objective/score, and the best-fit value of every calibrated
parameter.

The Dakota objective is neg_kge = 1 - mean_score, where mean_score is the
mean of the chosen metric (e.g. KGE_logKGE; higher is better, max 1) over
the calibration decades.  best_score = 1 - best_objective recovers that mean
metric value (higher is better); best_objective is the raw minimized value.  The union of parameter columns is taken across a watershed's
versions (NaN where a parameter was not active in that version).

This is the backbone analog of summarize.py/summary.csv: it preserves the
canonical results so the per-run Dakota archives under backbone_runs/ (large,
machine-generated) can be left untracked.

Usage (from repo root):
    python summarize_backbone.py                 # all watersheds
    python summarize_backbone.py cannon_river    # one or more watersheds
"""

import sys
import glob
import os
import warnings
import numpy as np
import pandas as pd
import yaml

warnings.filterwarnings('ignore')

META_COLS = ['run', 'metric', 'config_template', 'n_evaluations',
             'best_eval_id', 'best_objective', 'best_score']


def _read_eval(run_dir):
    """Return (DataFrame, objective_col_name) for a run's evaluations.dat."""
    fpath = os.path.join(run_dir, 'evaluations.dat')
    with open(fpath) as f:
        header = f.readline().lstrip('%').split()
    df = pd.read_csv(fpath, sep=r'\s+', comment='%', names=header)
    return df, header[-1]


def _params_meta(run_dir):
    """Return (metric, config_template) from the run's params.yml."""
    pyml = os.path.join(run_dir, 'params.yml')
    if not os.path.exists(pyml):
        return None, None
    with open(pyml) as f:
        p = yaml.safe_load(f) or {}
    drv = p.get('driver', {})
    return drv.get('metric'), drv.get('config_template')


def summarize_watershed(ws):
    run_dirs = sorted(glob.glob(os.path.join(ws, 'backbone_runs', '*')))
    rows = []
    for rd in run_dirs:
        if not os.path.isfile(os.path.join(rd, 'evaluations.dat')):
            continue
        df, obj_col = _read_eval(rd)
        if df.empty:
            continue
        best = df.loc[df[obj_col].idxmin()]
        metric, config = _params_meta(rd)
        # Parameter columns = everything except the bookkeeping/objective cols
        param_cols = [c for c in df.columns
                      if c not in ('eval_id', 'interface', obj_col)]
        row = {
            'run':             os.path.basename(rd),
            'metric':          metric,
            'config_template': config,
            'n_evaluations':   len(df),
            'best_eval_id':    int(best['eval_id']),
            'best_objective':  float(best[obj_col]),         # minimized neg_kge
            'best_score':      1.0 - float(best[obj_col]),   # mean metric, higher better
        }
        for c in param_cols:
            row[c] = float(best[c])
        rows.append(row)
    if not rows:
        return None
    out = pd.DataFrame(rows)
    param_cols = sorted(c for c in out.columns if c not in META_COLS)
    out = out[META_COLS + param_cols]
    return out


def main(argv):
    if argv:
        watersheds = argv
    else:
        watersheds = sorted(os.path.dirname(p) for p in
                            glob.glob('*/backbone_runs'))
    any_written = False
    for ws in watersheds:
        out = summarize_watershed(ws)
        if out is None:
            print(f"  {ws}: no backbone runs with evaluations.dat — skipped")
            continue
        dest = os.path.join(ws, 'backbone_summary.csv')
        out.to_csv(dest, index=False)
        any_written = True
        print(f"Wrote {dest}  ({len(out)} backbone versions)")
    if not any_written:
        print("No backbone summaries written.")
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
