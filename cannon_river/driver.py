#!/usr/bin/env python3
"""
Dakota driver for hydroRaVENS Cannon River calibration.

Dakota minimizes the objective function; we return (1 - NSE) so that
minimizing the objective is equivalent to maximizing Nash-Sutcliffe Efficiency.

Calibration parameters (set in the Dakota input file):
  log__t_efold_shallow  log10 of shallow-reservoir e-folding time [days]
  log__t_efold_deep     log10 of deep-reservoir e-folding time [days]
  f_exfiltration_shallow  fraction of shallow-reservoir exfiltration to stream
  PDD_melt_factor         degree-day snowmelt factor [mm SWE / degC / day]
"""

import dakota.interfacing as di
import hydroravens
import numpy as np

SPIN_UP_CYCLES = 3
PENALTY = 2.0   # returned when the model fails; 1-NSE > 1 only for NSE < 0

params, results = di.read_parameters_file()

try:
    b = hydroravens.Buckets()
    # spin_up_cycles: 0 in template; we spin up below after setting parameters
    b.initialize('cannon_cfg_template.yml')

    # Override calibration parameters on the already-constructed reservoir objects
    b.reservoirs[0].t_efold       = 10 ** params['log__t_efold_shallow']
    b.reservoirs[1].t_efold       = 10 ** params['log__t_efold_deep']
    b.reservoirs[0].f_to_discharge = params['f_exfiltration_shallow']
    b.snowpack.melt_factor         = params['PDD_melt_factor']

    # Spin up with the calibrated parameters so initial storage is self-consistent
    for _ in range(SPIN_UP_CYCLES):
        b.run()
        b._timestep_i = b.hydrodata.index[0]

    # Final run whose output is used for NSE
    b.run()
    nse = b.computeNSE(return_nse=True, verbose=False)

    neg_nse = 1.0 - nse if np.isfinite(nse) else PENALTY

except Exception:
    neg_nse = PENALTY

results['neg_nse'].function = neg_nse
results.write()
