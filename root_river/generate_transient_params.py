"""
Generate per-decade params.yml files for Root River v6_2res transient runs.

R1–R3 (contaminated — et_scale per-decade is a closure cheat; kept for reference):
  1. transient_run1/  — et_scale per-decade only
  2. transient_run2/  — et_scale + f_exfil_soil per-decade
  3. transient_run3/  — run 2 + log t_recession_soil

R4–R5 (legitimate transient — et_scale pinned, follows Cannon precedent):
  4. transient_run4/  — f_exfil_soil per-decade only       (5 static, 1 free)
  5. transient_run5/  — log__t_recession_soil per-decade   (5 static, 1 free)

Backbone-best values (from v6_2res backbone calibration 2026-06-25_114546):
  PDD_melt_factor              = 5.7316
  log__t_recession_soil        = 1.2298   (τ_soil = 17 d)
  log__t_recession_karst       = 4.5047   (τ_karst = 31 950 d)
  f_exfiltration_soil          = 0.5585
  recession_b_karst            = 1.7936
  et_scale                     = 1.1128   (high — absorbs unmodeled karst export)

The per-decade driver.py uses log__t_recession_<l> naming (NOT log__recession_coeff_<l>).
"""
from pathlib import Path

ROOT = Path('/home/awickert/dataanalysis/Wickert2026-hydroRaVENS-decadal-optimization/root_river')
CONFIG = 'root_river_config_v6_2res.yml'

DECADES = [(y, y+9) for y in range(1911, 2020, 10)] + [(2011, 2020)]
DECADES = sorted(set(DECADES))

# Backbone-best static values
BEST = dict(
    PDD_melt_factor=5.7316,
    log__t_recession_soil=1.2298,
    log__t_recession_karst=4.5047,
    f_exfiltration_soil=0.5585,
    recession_b_soil=1.0,
    recession_b_karst=1.7936,
    et_scale=1.1128,
    # Disabled modules (driver.py requires these keys even when inactive)
    log__fdd_threshold=4.0,         # FGI off
    snow_insulation_k=0.0,
    f_direct_runoff=0.0,
    baseflow_Q=0.0,
    log__routing_K=-3.0,            # K = 10⁻³ d ≈ no routing
)

BOUNDS = dict(
    PDD_melt_factor=(0.1, 15.0),
    log__t_recession_soil=(0.5, 3.5),
    log__t_recession_karst=(1.0, 5.0),
    f_exfiltration_soil=(0.01, 0.99),
    recession_b_soil=(1.0, 4.5),
    recession_b_karst=(1.0, 4.5),
    et_scale=(0.3, 3.0),
    log__fdd_threshold=(0.0, 4.0),
    snow_insulation_k=(0.0, 0.5),
    f_direct_runoff=(0.0, 0.5),
    baseflow_Q=(0.0, 0.5),
    log__routing_K=(-3.0, 1.0),
)

DESCRIPTIONS = dict(
    PDD_melt_factor='degree-day snowmelt rate [mm SWE / degC / day]',
    log__t_recession_soil='log10 τ_soil [days] (loess + topsoil)',
    log__t_recession_karst='log10 τ_karst [days] (Galena-Decorah + Wonewoc)',
    f_exfiltration_soil='soil → stream vs recharge to karst',
    recession_b_soil='soil recession exponent (linear)',
    recession_b_karst='karst recession exponent (karst+sandstone composite)',
    et_scale='Thornthwaite ET multiplier',
    log__fdd_threshold='log10 FGI threshold (inactive — frozen_ground off)',
    snow_insulation_k='snow insulation (inactive)',
    f_direct_runoff='direct runoff fraction (inactive)',
    baseflow_Q='regional baseflow import (inactive)',
    log__routing_K='log10 Nash routing K (inactive — K=10⁻³ d)',
)

# Which params are FREE in each transient run
FREE = {
    'transient_run1': ['et_scale'],
    'transient_run2': ['et_scale', 'f_exfiltration_soil'],
    'transient_run3': ['et_scale', 'f_exfiltration_soil', 'log__t_recession_soil'],
    'transient_run4': ['f_exfiltration_soil'],
    'transient_run5': ['log__t_recession_soil'],
}

ALL_PARAMS = list(BEST.keys())

TEMPLATE = """\
# {label}: Root River v6_2res transient, run {run_number}.
# Free per-decade params: {free}

modules:
  snowpack:          true
  frozen_ground:     false
  rain_on_snow:      true
  direct_runoff:     false
  dtr_fgi_decay:     false
  et_water_stress:   false
  et_reservoir_draw: true

dakota:
  ego_initial_samples:       {ego_samples}
  ego_seed:                  42
  ps_max_evaluations:        {ps_max}
  ps_convergence_tolerance:  1.0e-5
  evaluation_concurrency:    4

driver:
  config_template:       '{config}'
  metric:                'KGE_logKGE'
  spin_up_cycles:        1
  routing_N:             2
  n_reservoirs:          2
  reservoir_order:       ['soil', 'karst']
  decade_start:          '{decade_start}'
  decade_end:            '{decade_end}'
  enforce_water_balance: 'none'

parameters:
"""

PARAM_BLOCK = """\
  {name}:
    description: '{desc}'
    lower:   {lower}
    upper:   {upper}
    initial: {initial}
    fixed:   {fixed}
    active:  {active}
"""

# Sample budgets (active params, ego, ps)
BUDGETS = {1: (50, 200), 2: (100, 400), 3: (150, 800)}

for run_name, free_params in FREE.items():
    run_dir = ROOT / run_name
    run_dir.mkdir(exist_ok=True)
    n_active = len(free_params)
    ego_samples, ps_max = BUDGETS[n_active]
    for y0, y1 in DECADES:
        label = f'{y0}-{y1}'
        dec_dir = run_dir / label
        dec_dir.mkdir(exist_ok=True)
        header = TEMPLATE.format(
            label=label,
            run_number=run_name[-1],
            free=', '.join(free_params),
            ego_samples=ego_samples,
            ps_max=ps_max,
            config=CONFIG,
            decade_start=f'{y0}-01-01',
            decade_end=f'{y1}-12-31',
        )
        body = []
        for name in ALL_PARAMS:
            lo, hi = BOUNDS[name]
            best = BEST[name]
            active = 'true' if name in free_params else 'false'
            body.append(PARAM_BLOCK.format(
                name=name,
                desc=DESCRIPTIONS[name],
                lower=lo,
                upper=hi,
                initial=best,
                fixed=best,
                active=active,
            ))
        (dec_dir / 'params.yml').write_text(header + '\n'.join(body))
    print(f'  created {run_name}/ ({len(DECADES)} decades, {n_active} free, '
          f'EGO {ego_samples} + PS {ps_max})')
print('Done.')
