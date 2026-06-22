#!/usr/bin/env python3
"""
Dakota driver for decade-by-decade MNiShed calibration.

Returns (1 - score) so Dakota minimisation is equivalent to metric maximisation.
Set DECADE_START / DECADE_END to the scoring window.  For chained decades,
pass initial_states from the previous decade and set SPIN_UP_CYCLES = 0.
"""

import dakota.interfacing as di
import numpy as np
from mnished import run_and_score

DECADE_START   = None   # None = full record; set e.g. '1990-01-01' for a decade
DECADE_END     = None
METRIC         = 'KGE_logKGE'  # 0.5*KGE + 0.5*logKGE; balances peak and
                               # low-flow sensitivity (Yilmaz et al. 2008)
SPIN_UP_CYCLES = 3
INITIAL_STATES = None   # dict from a prior CalibResult.final_states, or None
ROUTING_N      = 2      # Nash-cascade shape (fixed; increase to calibrate)

PENALTY = 2.0   # returned on model failure; safely above any real 1 - score

params, results = di.read_parameters_file()

try:
    result = run_and_score(
        'cannon_cfg_template.yml',
        t_efold        = [10 ** params['log__t_efold_shallow'],
                          10 ** params['log__t_efold_soil'],
                          10 ** params['log__t_efold_karst']],
        f_to_discharge = [params['f_exfiltration_shallow'],
                          params['f_exfiltration_soil']],
        melt_factor    =  params['PDD_melt_factor'],
        fdd_threshold  =  10 ** params['log__fdd_threshold'],
        Hmax           = [10 ** params['log__Hmax_shallow']],
        routing_K      =  10 ** params['log__routing_K'],
        routing_N      =  ROUTING_N,
        initial_states = INITIAL_STATES,
        start          = DECADE_START,
        end            = DECADE_END,
        spin_up_cycles = SPIN_UP_CYCLES,
        metric         = METRIC,
    )
    neg_score = 1.0 - result.score if np.isfinite(result.score) else PENALTY

except Exception:
    neg_score = PENALTY

results['neg_kge'].function = neg_score
results.write()
