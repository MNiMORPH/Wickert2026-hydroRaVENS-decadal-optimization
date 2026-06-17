#!/usr/bin/env python3
"""
Re-run the best-fit evaluation from a completed transient run and write the
end-of-decade reservoir states to final_states.yml in that run directory.

Usage:
    python extract_end_state.py <run_dir>

Output:
    <run_dir>/final_states.yml  — H_soil, H_inter, H_deep, snowpack, fgi [mm or °C·day]
"""

import sys
import yaml
import numpy as np
import pandas as pd
from pathlib import Path
from mnished import run_and_score

def _parse_evals(run_dir):
    """Return the best-fit row as a dict from evaluations.dat."""
    p = Path(run_dir) / 'evaluations.dat'
    rows = []
    with open(p) as f:
        header = f.readline().lstrip('%').split()
        for line in f:
            parts = line.split()
            if len(parts) < len(header):
                continue
            try:
                row = {header[i]: (parts[i] if i == 1 else float(parts[i]))
                       for i in range(len(header))}
                rows.append(row)
            except (ValueError, IndexError):
                pass
    valid = [r for r in rows if r['neg_kge'] < 9.0]
    if not valid:
        raise RuntimeError(f"No valid evaluations found in {p}")
    return min(valid, key=lambda r: r['neg_kge'])


def main():
    run_dir = Path(sys.argv[1])
    params_path = run_dir / 'params.yml'

    with open(params_path) as f:
        cfg = yaml.safe_load(f)

    drv         = cfg['driver']
    param_cfg   = cfg['parameters']
    modules     = cfg.get('modules', {})
    res_order   = drv.get('reservoir_order', ['soil', 'intermediate', 'deep'])
    config_tmpl = drv['config_template']
    spin_up     = drv.get('spin_up_cycles', 0)
    decade_start= drv.get('decade_start')
    decade_end  = drv.get('decade_end')
    enforce_wb  = drv.get('enforce_water_balance', 'none')

    best = _parse_evals(run_dir)
    kge  = 1.0 - best['neg_kge']
    print(f"Best eval: KGE = {kge:.4f}")

    def get(name):
        p = param_cfg[name]
        return best[name] if p['active'] else float(p['fixed'])

    def _f_discharge():
        vals = []
        for l in res_order:
            key = f'f_exfiltration_{l}'
            if key in param_cfg and param_cfg[key].get('active', True):
                vals.append(get(key))
            else:
                vals.append(None)
        return vals if any(v is not None for v in vals) else None

    def _recession_exponents():
        exps = []
        for l in res_order:
            key = f'recession_b_{l}'
            if l == 'shallow':
                exps.append(1.0)
            elif key in param_cfg:
                exps.append(get(key))
            else:
                exps.append(1.0)
        return exps if any(e != 1.0 for e in exps) else None

    def _leakance_R():
        vals = [None] * len(res_order)
        for i, l in enumerate(res_order):
            key = f'log__leakance_R_{l}'
            if key in param_cfg:
                vals[i] = 10 ** get(key)
        return vals if any(v is not None for v in vals) else None

    def _H_threshold():
        vals = [None] * len(res_order)
        for i, l in enumerate(res_order):
            key = f'log__H_threshold_{l}'
            if key in param_cfg:
                vals[i] = 10 ** get(key)
        return vals if any(v is not None for v in vals) else None

    def _h0_states():
        names = [f'log__H0_{l}' for l in res_order]
        if not any(n in param_cfg for n in names):
            return None
        vals = [10 ** float(param_cfg[n]['fixed']) if n in param_cfg else None for n in names]
        state = {'reservoirs': vals}
        if 'H0_snowpack' in param_cfg:
            state['snowpack'] = float(param_cfg['H0_snowpack']['fixed'])
        if 'H0_fgi' in param_cfg:
            state['fgi'] = float(param_cfg['H0_fgi']['fixed'])
        return state

    h0 = _h0_states()
    if spin_up == 0 and h0 is not None:
        initial_states, post_spinup_states = h0, None
    else:
        initial_states, post_spinup_states = None, h0

    et_scale_val = get('et_scale') if 'et_scale' in param_cfg else None

    result = run_and_score(
        str(run_dir / config_tmpl),
        t_recession         = [10 ** get(f'log__t_recession_{l}') for l in res_order],
        f_to_discharge      = _f_discharge(),
        leakance_R          = _leakance_R(),
        H_threshold         = _H_threshold(),
        recession_exponents = _recession_exponents(),
        melt_factor         = get('PDD_melt_factor'),
        fdd_threshold       = 10 ** get('log__fdd_threshold'),
        snow_insulation_k   = get('snow_insulation_k'),
        direct_runoff_fraction = get('f_direct_runoff'),
        baseflow_Q          = get('baseflow_Q'),
        et_scale            = et_scale_val,
        routing_N           = drv.get('routing_N', 2),
        enforce_water_balance = enforce_wb,
        initial_states      = initial_states,
        post_spinup_states  = post_spinup_states,
        spin_up_cycles      = spin_up,
        start               = decade_start,
        end                 = decade_end,
        metric              = drv.get('metric', 'KGE_logKGE'),
        modules             = modules,
    )

    fs = result.final_states
    out = {
        'kge': float(kge),
        'reservoirs': {res_order[i]: float(fs['reservoirs'][i])
                       for i in range(len(res_order))},
        'snowpack': float(fs['snowpack']),
        'fgi':      float(fs['fgi']),
    }

    out_path = run_dir / 'final_states.yml'
    with open(out_path, 'w') as f:
        yaml.dump(out, f, default_flow_style=False, sort_keys=False)

    print(f"Written: {out_path}")
    for k, v in out['reservoirs'].items():
        print(f"  H_{k} = {v:.2f} mm")
    print(f"  snowpack = {out['snowpack']:.2f} mm SWE")
    print(f"  fgi      = {out['fgi']:.2f} °C·day")


if __name__ == '__main__':
    main()
