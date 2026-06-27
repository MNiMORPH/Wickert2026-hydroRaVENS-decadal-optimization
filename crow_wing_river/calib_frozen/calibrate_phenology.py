#!/usr/bin/env python3
"""Crow Wing multi-window SCE-UA WITH a leaf-out ET phenology kludge.

Monkeypatches Buckets.compute_ET to multiply the model ET by a monthly
northern-mixed-forest leaf-out / LAI factor (April suppressed, May ramp, full
canopy summer, senescing fall), then re-calibrates all 9 params (incl. et_scale)
against the 8-decade mean KGE_logKGE. Compare best vs. baseline 0.704.

    conda activate mnished-jit; python calibrate_phenology.py [reps]
"""
import sys
import time
import warnings

import numpy as np
import pandas as pd
import spotpy

warnings.filterwarnings('ignore')
from mnished import Calibrator, Buckets

# Northern mixed-forest leaf-out / LAI factor on ET (kludge; leaf-out ~mid-May).
PHEN = {1: .2, 2: .2, 3: .2, 4: .35, 5: .7, 6: 1., 7: 1., 8: 1.,
        9: .9, 10: .6, 11: .3, 12: .3}
_orig = Buckets.compute_ET


def _patched(self, *a, **k):
    _orig(self, *a, **k)
    mon = pd.to_datetime(self.hydrodata['Date']).dt.month.values
    et = pd.to_numeric(self.hydrodata['ET for model [mm/day]'],
                       errors='coerce').values
    self.hydrodata['ET for model [mm/day]'] = et * np.array([PHEN[m] for m in mon])


Buckets.compute_ET = _patched

CAL = Calibrator.from_yaml('params.yml')
NAMES = CAL.names
WINDOWS = CAL.windows


class Setup:
    def __init__(self):
        self.params = [spotpy.parameter.Uniform(p.name, p.lower, p.upper,
                                                optguess=p.value)
                       for p in CAL.parameter_set]
        self.evals = 0

    def parameters(self):
        return spotpy.parameter.generate(self.params)

    def simulation(self, vector):
        self.evals += 1
        try:
            res = CAL.score_windows(dict(zip(NAMES, vector)))
        except Exception:
            return [-10.0]
        return [float(np.mean([r.score if np.isfinite(r.score) else -10.0
                               for r in res]))]

    def evaluation(self):
        return [1.0]

    def objectivefunction(self, simulation, evaluation):
        return 1.0 - simulation[0]


def main():
    reps = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    setup = Setup()
    t0 = time.time()
    sampler = spotpy.algorithms.sceua(setup, dbname='ph_sceua', dbformat='ram')
    sampler.sample(reps)
    print(f"\nevals={setup.evals} wall={time.time() - t0:.0f}s  "
          f"best mean KGE_logKGE = {1.0 - sampler.status.objectivefunction_min:.4f}"
          f"  (baseline no-kludge = 0.704)")
    best = spotpy.analyser.get_best_parameterset(sampler.getdata(),
                                                 maximize=False)[0]
    for nm in best.dtype.names:
        print(f"  {nm}: {float(best[nm]):.4f}")


if __name__ == '__main__':
    main()
