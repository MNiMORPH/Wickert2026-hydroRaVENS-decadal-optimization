#!/usr/bin/env python3
"""In-process SCE-UA calibration of Crow Wing (v6 two-layer / two-land-zone +
lake), mirroring backbone driver_backbone_v6_lake_2zone exactly — same
run_and_score call, same objective (mean KGE_logKGE over the configured
decades) — but in-process (warm JIT, ~100x faster than the Dakota fork).

Reads the same params.yml + config template as the Dakota run. Serial, so it
uses ~one core and can run alongside an active Dakota calibration.

    conda activate mnished-jit   # numba JIT + spotpy
    python run_sceua.py [repetitions]
"""
import sys
import time
from copy import deepcopy

import numpy as np
import yaml
import spotpy

from mnished import ParameterSet, run_and_score

with open('params.yml') as f:
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


def _make_temp_cfg(f_route):
    """Patch the free f_route_lake into the lake sub-catchment (per-eval)."""
    cfg = deepcopy(_BASE)
    for sc in cfg['sub_catchments']:
        if sc.get('kind') == 'lake':
            sc.setdefault('lake', {})['f_route_lake'] = float(f_route)
    path = 'tmp_sceua_cfg.yml'
    with open(path, 'w') as f:
        yaml.dump(cfg, f)
    return path


class CrowWing2Layer:
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
                    'pdm_H0': [10 ** g('log__pdm_H0'), None]}
            lake = {'recession_coeff': [10 ** g('log__recession_coeff_lake')],
                    'H_threshold': [10 ** g('log__H_sill_lake')]}
            cfg_path = _make_temp_cfg(g('f_route_lake'))
            scores = []
            for d in DECADES:
                try:
                    r = run_and_score(
                        cfg_path,
                        sub_catchments=[land, land, lake],   # direct, lake_basin, lake
                        melt_factor=g('PDD_melt_factor'),
                        fdd_threshold=1e4, snow_insulation_k=0.0,
                        direct_runoff_fraction=0.0, baseflow_Q=0.0,
                        et_scale=g('et_scale'), et_alpha=None,
                        routing_K=None, routing_N=RN,
                        enforce_water_balance=WB, initial_states=None,
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
    setup = CrowWing2Layer()
    t0 = time.time()
    sampler = spotpy.algorithms.sceua(setup, dbname='crowwing_sceua',
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
