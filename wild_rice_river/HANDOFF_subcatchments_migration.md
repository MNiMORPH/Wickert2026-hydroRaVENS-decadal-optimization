# Handoff — migrate Wild Rice to parallel sub-catchments

*Written 2026-06-24. Bridges the MNiShed-side feature (parallel sub-catchments,
now merged to `master`) into this calibration repo. You build the config and
wire the driver; this doc gives the exact shapes and the gotchas, grounded in
the current v7 setup (`wild_rice_config_v7_2res.yml`,
`params_backbone_v7_wildrice_joint.yml`, `driver_backbone_v7.0.py`,
`extract_end_state.py`).*

See `DESIGN_sub_catchments.md` for the original design rationale.

## TL;DR

The current model treats the whole basin as one lake-clay 2-reservoir cascade
(soil + deep, multipath ditch on soil). The **pre-tile decades fit badly**
(joint comment notes KGE ≈ 0.12) because a single cascade conflates two
spatially distinct zones. MNiShed now supports **parallel sub-catchments**, so
you can split the basin into:

- **Till uplands** — tiled agricultural land; more-permeable glacial till;
  engineered **tile drainage** = constant-fraction fast path (`f_tile` /
  `tau_tile`).
- **Clay lowlands** — lake clay; low-k; **ditch drainage** = threshold-activated
  **multipath**; very slow deep-clay baseflow (≈ the current v7 model).

Basin discharge `Q = a_till·Q_till + a_clay·Q_clay`. A single sub-catchment of
`area_fraction: 1.0` reproduces the current model exactly, so this is additive.

## 1. Install the sub-catchments code (it is unreleased)

Sub-catchments are on MNiShed `master` but **not on PyPI** — PyPI is still
`mnished` 3.0.0 (no sub-catchments). Install from the local clone (already on
`master` at `~/models/MNiShed`):

```bash
pip install -e ~/models/MNiShed          # editable; tracks the repo
# or, pinned to the remote:
# pip install "git+https://github.com/MNiMORPH/MNiShed.git@master"
python -c "from mnished import SubCatchment; print('sub-catchments available')"
```

For the production/paper run, cut **MNiShed v3.1.0** once the two-zone structure
is validated, then pin to it for reproducibility.

## 2. Config change: `reservoirs:` → `sub_catchments:`

Keep `timeseries`, `catchment` (area 2419 km²), `snowmelt`, water year, and
`general`. Replace the top-level `reservoirs:` block (and the reservoir part of
`initial_conditions:`) with a `sub_catchments:` list. Each zone mirrors the
single-cascade form. Starter skeleton (params are placeholders to calibrate;
**area fractions come from the surficial-geology / till-vs-lacustrine map**):

```yaml
sub_catchments:
  - name: till_uplands
    area_fraction: 0.55          # PLACEHOLDER — set from GIS (sums to 1)
    reservoirs:
      recession_timescales__days:   [40, 800]   # till soil, deep till
      exfiltration_fractions:       [0.4, 1.0]
      maximum_effective_depths__mm: [1.0e6, .inf]
      tile_fractions:               [0.4, 0.0]   # engineered tile on soil
      tile_residence_times__days:   [7.0, null]  # ~1 week ag tile
      recession_exponents:          [1.0, 1.0]
    initial_conditions:
      water_reservoir_effective_depths__mm: [50, 400]
      snowpack__mm_SWE: 0
  - name: clay_lowlands
    area_fraction: 0.45          # PLACEHOLDER
    reservoirs:
      recession_timescales__days:   [100, 2000]  # clay soil, slow deep clay
      exfiltration_fractions:       [0.5, 1.0]
      maximum_effective_depths__mm: [1.0e6, .inf]
      multipath_thresholds__mm:     [50.0, null] # ditch (threshold-activated)
      multipath_timescales__days:   [5.0, null]
      recession_exponents:          [1.0, 1.0]
    initial_conditions:
      water_reservoir_effective_depths__mm: [50, 500]
```

Validation enforced by MNiShed: area fractions sum to 1 (±1e-6), unique names,
≥1 reservoir each. (`recession_timescales__days` is the YAML key your templates
already use; it maps to `recession_coefficients`. Reminder: for `b > 1` the
coefficient is **not** a timescale.)

## 3. Driver change: flat args → `sub_catchments=[…]`

Your driver builds flat per-reservoir lists from the Dakota params, e.g.
`recession_coeff = [10**get('log__recession_coeff_soil'),
10**get('log__recession_coeff_deep')]`, then calls `run_and_score(config,
recession_coeff=…, multipath_threshold=…, …)`. The two-zone call passes a
`sub_catchments` list instead — one dict per zone, **in config order**:

```python
result = run_and_score(
    config,                              # config now declares 2 sub_catchments
    sub_catchments = [
        {   # 0: till_uplands
            'recession_coeff': [k_till_soil, k_till_deep],
            'f_to_discharge':  [f_till_soil, 1.0],
            'f_tile':          [f_tile_till, 0.0],
            'tau_tile':        tau_tile_till,          # scalar
        },
        {   # 1: clay_lowlands
            'recession_coeff':     [k_clay_soil, k_clay_deep],
            'f_to_discharge':      [f_clay_soil, 1.0],
            'multipath_threshold': [thr_clay, None],
            'multipath_timescale': [tau_mp_clay, None],
        },
    ],
    # area_fraction omitted from the dicts -> taken from config (fixed, from GIS).
    # Snow + ET stay BASIN-LEVEL (one set, shared across zones):
    melt_factor = PDD, et_scale = 0.755,
    start = decade_start, end = decade_end,
    metric = 'KGE_logKGE', spin_up_cycles = 1, routing_N = 2,
    enforce_water_balance = 'none',
)
```

Notes:
- `sub_catchments=` is **mutually exclusive** with the flat per-reservoir args
  (`recession_coeff`, `multipath_threshold`, `f_tile`, …) — passing both raises.
- ET draw is **local per zone** (each zone draws ET from its own soil reservoir
  via `et_alpha`); `et_scale`/`et_alpha`/snow stay basin-level by design.
- AIC: the `sub_catchments` path **auto-counts** each overridden value as one
  free parameter (plus `n_sub − 1` if you calibrate area fractions), rather than
  using your explicit `*_calibrated` counts. If you compare AIC against the
  single-cascade models, reconcile the bookkeeping.

## 4. ⚠ Migration gotcha: `final_states` is nested at K>1 (decadal chaining)

This is the one that will silently break chaining. `extract_end_state.py`
currently reads the **flat** form:

```python
fs = result.final_states
out = {'reservoirs': {res_order[i]: float(fs['reservoirs'][i]) ...},
       'snowpack': float(fs['snowpack']),
       'fgi': float(fs['fgi'])}
```

With two sub-catchments, `final_states` nests one level deeper:

```python
# K = 1 (today):   {'reservoirs': [...], 'snowpack': float, 'fgi': float,
#                   'H_deficit_carry': float}
# K > 1 (two zones):
{'sub_catchments': [
    {'reservoirs': [H_soil, H_deep], 'snowpack': ..., 'fgi': ...,
     'H_deficit_carry': ...},   # till
    {'reservoirs': [H_soil, H_deep], 'snowpack': ..., 'fgi': ...,
     'H_deficit_carry': ...},   # clay
]}
```

So `fs['reservoirs']` is **absent** at K>1 — update both the capture
(`extract_end_state.py`) and the `initial_states` injection to handle the
`'sub_catchments'` key. Pattern:

```python
fs = result.final_states
if 'sub_catchments' in fs:                       # two zones
    zones = fs['sub_catchments']                 # list, config order
    # persist zones[k]['reservoirs'/'snowpack'/'fgi'/'H_deficit_carry'] per zone
else:                                            # single cascade (legacy)
    ...  # existing flat handling
```

And to inject chained ICs at K>1, build the nested dict:

```python
initial_states = {'sub_catchments': [
    {'reservoirs': [Hs_till, Hd_till], 'snowpack': s_till, 'fgi': f_till,
     'H_deficit_carry': 0.0},
    {'reservoirs': [Hs_clay, Hd_clay], 'snowpack': s_clay, 'fgi': f_clay,
     'H_deficit_carry': 0.0},
]}
```

`run_and_score` reads either form (flat for K=1, nested for K>1).
`post_spinup_states` follows the same shape; a `None` reservoir entry keeps that
reservoir at its spin-up value. A chained two-window K=2 run reproduces a single
continuous run to ~1e-9 (verified in the MNiShed test suite), so the machinery
is sound — the only work is teaching your extract/inject code the nested shape.

## 5. Calibration-design decisions to make (before wiring Dakota)

- **Area split** `a_till`/`a_clay`: get from the till-vs-lacustrine surficial
  map and **fix it** — it's mappable, so don't spend a DOF unless it's genuinely
  uncertain. (It *can* be a calibrated parameter via the dict's `area_fraction`,
  but default to fixing.)
- **Parameter vector grows.** Each zone now has its own soil/deep recession and
  exfiltration, plus its fast path (till: `f_tile` + `tau_tile`; clay: multipath
  `thr` + `τ`). That roughly doubles the hydraulic DOF over the single cascade —
  watch identifiability across the 9 joint decades. Consider whether any param
  is physically shared (probably not: till-deep ≠ clay-deep), and which to hold
  fixed initially.
- **Shared vs per-zone forcing — a real caveat.** Forcing (P, ET, T) is
  currently **basin-shared** across zones; per-zone forcing is a deferred
  `NotImplementedError` hook. Fine if till and clay see the same met forcing; a
  limitation if you intended zone-specific inputs.
- **Snow/FGI state is per-zone** (each zone carries its own), but driven by the
  same shared forcing, so they evolve identically until per-zone forcing lands.

## 6. Suggested first step (prototype before Dakota)

1. Hand-build the two-zone config with the placeholder params above.
2. Run **one good post-tile decade** (e.g. 2001–2010) with
   `run_and_score(sub_catchments=…)`, fixed params — confirm it runs, mass
   balances, and Q looks sane (`result.buckets.check_mass_balance()` ≈ 0;
   `result.score` finite).
3. Run a **pre-tile decade** (e.g. 1909–1917) — the historically bad fit — and
   see whether the till/clay split *and* turning the till tile path off pre-tile
   (set `f_tile: [0, 0]` for till in that era) recovers skill. That hypothesis —
   tiling changed the upland response — is the whole physical reason for the
   split.
4. Once it behaves, update `extract_end_state.py` for nested states (§4), then
   wire the per-zone params into `generate_dakota_in.py` /
   `params_backbone_*.yml` and run the joint calibration.

## Out of scope here / staying in your court

Building the actual config, choosing area fractions, setting bounds, and running
Dakota are all this-repo work. The MNiShed side (the feature, both time loops,
`run_and_score`, chaining, docs) is done and merged; ping if the model API needs
a tweak the calibration exposes.
