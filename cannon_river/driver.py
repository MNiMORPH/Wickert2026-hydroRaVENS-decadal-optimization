#!/usr/bin/env python3
"""
Dakota driver for decade-by-decade hydroRaVENS calibration.

Returns (1 - KGE) so Dakota minimization is equivalent to KGE maximization.
Set DECADE_START / DECADE_END to the scoring window; spin-up always runs
the full record so the initial storage state reflects long-run climatology.
"""

import dakota.interfacing as di
import numpy as np
from hydroravens import run_and_score

DECADE_START = None   # None = full record; set e.g. '1990-01-01' for a decade
DECADE_END   = None
METRIC       = 'KGE'

PENALTY = 2.0   # returned on model failure; safely above any real 1-KGE

params, results = di.read_parameters_file()

try:
    score, aic, _ = run_and_score(
        'cannon_cfg_template.yml',
        t_efold        = [10 ** params['log__t_efold_shallow'],
                          10 ** params['log__t_efold_deep']],
        f_to_discharge = [params['f_exfiltration_shallow']],
        melt_factor    =  params['PDD_melt_factor'],
        start=DECADE_START,
        end=DECADE_END,
        metric=METRIC,
    )
    neg_kge = 1.0 - score if np.isfinite(score) else PENALTY

except Exception:
    neg_kge = PENALTY

results['neg_kge'].function = neg_kge
results.write()
