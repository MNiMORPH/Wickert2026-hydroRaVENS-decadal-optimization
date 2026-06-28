#!/usr/bin/env python3
"""In-process SCE-UA calibration of Crow Wing (v6 two-layer land + FROZEN GROUND
+ lake), via SPOTPY. Mirrors the Dakota driver's run_and_score call and
objective (mean KGE_logKGE), but in-process (warm JIT, ~100x faster than the
Dakota fork). Adapted from spotpy_2layer/run_sceua.py: PDM disabled, the FGI
fdd_threshold is now a calibrated parameter.

    conda activate mnished-jit   # numba JIT + spotpy
    python run_sceua.py [repetitions]
"""
import sys
import time

import numpy as np
import yaml
import spotpy

from mnished import ParameterSet, ScoringModel

_PARAMS_FILE = sys.argv[2] if len(sys.argv) > 2 else 'params.yml'
with open(_PARAMS_FILE) as f:
    _CFG = yaml.safe_load(f)
P, DRV, MOD = _CFG['parameters'], _CFG['driver'], _CFG.get('modules', {})
with open(DRV['config_template']) as f:
    _BASE = yaml.safe_load(f)
DECADES = DRV['decades']
METRIC = DRV.get('metric', 'KGE_logKGE')
SPIN = DRV.get('spin_up_cycles', 1)
RN = DRV.get('routing_N', 2)
WB = DRV.get('enforce_water_balance', 'none')
PENALTY = 10.0
PSET = ParameterSet.from_params_yml(P)
NAMES = PSET.names
CFG_TEMPLATE = DRV['config_template']
# Build the model ONCE (reads CSV + constructs cascade + base ET); score() reuses it.
SM = ScoringModel(CFG_TEMPLATE, enforce_water_balance=WB)


class CrowWingFrozen:
    def __init__(self):
        self.params = [spotpy.parameter.Uniform(p.name, p.lower, p.upper,
                                                optguess=p.value) for p in PSET]
        self.evals = 0

    def parameters(self):
        return spotpy.parameter.generate(self.params)

    def simulation(self, vector):
        self.evals += 1
        th = dict(zip(NAMES, vector))
        g = lambda n: th.get(n, P[n]['fixed'])     # noqa: E731
        try:
            land = {'recession_coeff': [10 ** g('log__recession_coeff_soil'),
                                        10 ** g('log__recession_coeff_gw')],
                    'f_to_discharge': [g('f_exfil_soil'), 1.0],
                    'pdm_H0': [None, None]}          # PDM off; frozen ground is the fast path
            lake = {'recession_coeff': [10 ** g('log__recession_coeff_lake')],
                    'H_threshold': [10 ** g('log__H_sill_lake')],
                    'f_route_lake': float(g('f_route_lake'))}   # now an override key (no per-eval YAML patch)
            scores = []
            for d in DECADES:
                try:
                    r = SM.score(                              # build-once model, reused
                        sub_catchments=[land, land, lake],   # direct, lake_basin, lake
                        melt_factor=g('PDD_melt_factor'),
                        fdd_threshold=10 ** g('log__fdd_threshold'),   # FGI threshold (calibrated)
                        snow_insulation_k=0.0,                         # fixed for this test
                        direct_runoff_fraction=0.0, baseflow_Q=0.0,
                        et_scale=g('et_scale'), et_alpha=None,
                        routing_K=None, routing_N=RN,
                        initial_states=None,
                        spin_up_cycles=SPIN, start=d['start'], end=d['end'],
                        metric=METRIC, modules=MOD)
                    s = r.score
                    scores.append(s if np.isfinite(s) else -PENALTY)
                except Exception:
                    scores.append(-PENALTY)
            return [float(np.mean(scores)) if scores else -PENALTY]
        except Exception:
            return [-PENALTY]

    def evaluation(self):
        return [1.0]

    def objectivefunction(self, simulation, evaluation):
        return 1.0 - simulation[0]                 # minimise 1 - mean score


def main():
    reps = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    setup = CrowWingFrozen()
    t0 = time.time()
    sampler = spotpy.algorithms.sceua(setup, dbname='crowwing_frozen_sceua',
                                      dbformat='ram')
    sampler.sample(reps)
    dt = time.time() - t0
    print(f"\nSCE-UA in-process: {setup.evals} evals, wall={dt:.1f}s "
          f"({dt / max(setup.evals, 1) * 1000:.0f} ms/eval)")
    print(f"best mean {METRIC} = {1.0 - sampler.status.objectivefunction_min:.4f}")
    best = spotpy.analyser.get_best_parameterset(sampler.getdata(),
                                                 maximize=False)[0]
    print("best params:")
    for nm in best.dtype.names:
        print(f"  {nm}: {float(best[nm]):.4f}")


if __name__ == '__main__':
    main()
