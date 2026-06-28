# Handoff — run Crow Wing with the new MNiShed lake support

*Written 2026-06-25. Bridges the MNiShed-side lake feature (now on `master`) into
this calibration repo. You build the config and wire the driver; this doc gives
the exact config shape, how to calibrate, the gotchas, and — most important — the
**validation target**, which is not KGE alone. Grounded in the current
`crow_wing_config_v6.yml` (single-reservoir multipath, K = 1, area 2334.8 km²).*

> **UPDATE (2026-06-25): `f_route_lake > 0` is now implemented on `master`.**
> This doc describes the v1 controlled-experiment step (`f_route_lake = 0`,
> below), which the calibration session has already run — and which confirmed
> `Q_gw` alone is necessary but not sufficient (v2: KGE 0.626, τ_matrix sprang
> back to 974 d). The **next step is channelized routing** (`f_route_lake > 0`):
> set it per the config below and follow the `f_route_lake ∈ {0, 0.5, 0.9, 1}`
> validation plan in **`HANDOFF_f_route_lake.md`** (MNiShed root). `f_route_lake`
> is data-derived (lake position on the main stem), never calibrated.

See `DESIGN_lakes.md` in the MNiShed source tree for the full derivation, and
`HANDOFF_lake_support.md` (MNiShed root) for the original science case that
motivated this.

## TL;DR

Crow Wing is lake-rich (~30 % lake area: Park Rapids lakes + the "11 Crow Wing
Lakes" chain). The v6 single-cascade model force-fits that lake behaviour by
**stretching substrate timescales far past physical norms** — matrix τ ≈ 956 d,
multipath τ at its upper bound (98 d vs 13–23 d in pure-till basins), H_thr 3×
typical — even after freeing `et_scale` (which recovered KGE from −0.55 to 0.60
and landed *lower*, 0.56, confirming lake-ET is not the lever).

MNiShed now supports **lake (open-water) sub-catchments**: a single open-water
store with a threshold power-law outlet, fed by direct *P − E*, coupled to the
land subsurface by a **bidirectional groundwater exchange `Q_gw`** that reuses
the land reservoir's own recession law (no new calibrated parameter) and flips
sign with the head difference — the seasonal store-in-spring / release-in-summer
buffering. Convert Crow Wing to a land zone (the current cascade) + a lake zone
and re-run.

## What this first run tests (and what it deliberately does *not*)

**v1 holds the lake hydrologically disconnected from channelized river inflow
(`f_route_lake = 0`).** The lake is fed only by direct *P − E* on its surface and
by `Q_gw` with the land subsurface. This is deliberately incomplete — a real
lake's mass is dominated by routed upstream inflow — but it makes the first run a
**clean controlled test of the `Q_gw` mechanism alone**:

- If KGE recovers **and** the stretched matrix/multipath τ relax toward
  till-basin values → the groundwater capacitor is doing real physical work.
- If KGE barely moves → the action is in channelized routing (lake on the main
  stem), which is the *next* piece of work (lake network position from terrain +
  drainage-density / Ksat priors; MNiShed issue #19), not the `Q_gw` coupling.

Either outcome is informative. **The validation target is the τ relaxation, not
KGE by itself** — a KGE bump with τ still pinned at the bounds would mean the
lake only added flexibility, not the right physics.

## Config: convert v6 (K=1) → land + lake sub-catchments

Replace the top-level `reservoirs` / `initial_conditions` blocks with a
`sub_catchments` list. The **land zone is the current v6 cascade verbatim**; add
a **lake zone**. Land + lake `area_fraction` must sum to 1.

```yaml
# (timeseries, catchment, general, snowmelt, modules unchanged from v6)

sub_catchments:
  - name: land
    area_fraction: 0.70                 # = 1 - lake fraction (set from NHD; see below)
    reservoirs:                         # <- the v6 cascade, unchanged
      recession_coefficients:   [100]
      exfiltration_fractions:   [1.0]
      maximum_effective_depths__mm: [1000000.0]
      multipath_thresholds__mm: [50.0]
      multipath_timescales__days: [5.0]
      recession_exponents:      [1.0]
    initial_conditions:
      water_reservoir_effective_depths__mm: [50.0]

  - name: lake
    kind: lake
    area_fraction: 0.30                 # set from actual lake cover, NOT calibrated
    lake:
      outflow_coefficient: 0.05         # a;  Q_out = a*(H - H_sill)^b
      sill_storage__mm:    200.0        # H_sill (conceptual storage units)
      outflow_exponent:    1.6667       # b = 5/3 (fixed; don't calibrate)
      gw_partner:          land         # Q_gw partner (auto-resolves with one land zone)
      f_route_lake:        0.0          # 0 = controlled v1 step; set 0.5-0.9 next (data-derived)
    initial_conditions:
      lake_storage__mm:    250.0
```

**`area_fraction` comes from data, not calibration.** Use the actual open-water
fraction of the basin above Nimrod (NHD waterbodies / MN DNR lake inventory
clipped to the delineated basin). ~0.30 is the working estimate from the science
case; pin it to the measured value.

## Calibration

Lake parameters calibrate through the existing **`sub_catchments` override** of
`run_and_score` (one dict per sub-catchment, in config order). The lake outlet is
calibrated as its reservoir's `recession_coeff` and `H_threshold`:

```python
run_and_score(
    cfg,
    et_scale=<free>,                    # keep free; Crow Wing wants ~0.56
    sub_catchments=[
        {'recession_coeff': [<land_tau>],            # land cascade as before
         'multipath_threshold': [<H_thr>],
         'multipath_timescale': [<tau_mp>]},
        {'recession_coeff': [1.0 / a],               # lake outlet: a -> 1/a
         'H_threshold':     [H_sill]},               # lake sill
    ],
    ...,
)
```

Parameter budget for the lake: **two new calibrated values — `a` and `H_sill`**.
Notes:

- **`a` is calibrated as `recession_coeff = 1/a`.** Small `a` (slow outlet) =
  large `recession_coeff`. Set bounds in `recession_coeff` space accordingly
  (e.g. `a ∈ [0.005, 0.5]` → `recession_coeff ∈ [2, 200]`).
- **`b = 5/3` is fixed** (the override leaves the exponent untouched). Don't add
  it as a free parameter.
- **`Q_gw` adds no parameter** — it reuses the land reservoir's calibrated
  `recession_coeff` / `recession_exponent`, so it automatically tracks the
  substrate you're already fitting. (When the land cascade has several
  reservoirs, `Q_gw` uses the *deepest* one as the aquifer head `h_s`.)
- **`a`, `H_sill` are effective parameters.** Because MNiShed storages are
  conceptual depths (not surveyed stages), `a` absorbs the storage→stage/area
  translation — its fitted value is not a physical Manning coefficient. Only `b`
  and the evaporation scale carry direct physical meaning.

## Gotchas

1. **State structure goes nested at K > 1.** Converting from one cascade to
   land+lake makes `run_and_score`'s `final_states` / `initial_states` the
   **nested per-sub-catchment form** (`{'sub_catchments': [ {...}, {...} ]}`)
   instead of the flat K=1 form. Your decade-chaining driver (`warm_start.py` /
   the `driver_backbone_v6.0.py` chain) must read/write the nested shape. This is
   the *same* migration the Wild Rice sub-catchments handoff describes — see
   `wild_rice_river/HANDOFF_subcatchments_migration.md` for the exact reshaping.
   The lake zone's entry has a one-element `reservoirs` list (its store) and
   null/zero snowpack & FGI.
2. **Keep `et_scale` free.** The lake reuses the basin ET (global `et_scale`);
   there is no separate lake-ET knob (Penman would be collinear with
   Thornthwaite at this forcing resolution — see the MNiShed handoff's "ET is not
   the lever"). Crow Wing's `et_scale ≈ 0.56` is partly a 47°N climate
   correction, independent of lakes; let it float.
3. **The lake store is in the flattened `reservoirs`.** Analytical steady-state
   initialization, `store_depths` columns, and AIC k-counting all see the lake
   reservoir. Initialize `lake_storage__mm` somewhere above the sill so the
   outlet is active from the start.
4. **No ice / snow-on-lake in v1.** Winter precipitation on the lake is treated
   as liquid *P − E*, not snow accumulating on ice. For Crow Wing's snowy winters
   this slightly mistimes the lake's cold-season balance; it is a deferred
   feature (the MNiShed handoff suggests a monthly-residual-vs-DNR-ice-climatology
   test before building it). Flag it if the spring residuals look off.
5. **JIT.** Lakes run on both the pure-Python and Numba JIT loops (verified
   identical). If your local numba is broken by a NumPy ≥ 2.3 upgrade, runs fall
   back to pure-Python (~100× slower) with a one-time warning — pin `numpy<2.3`
   in the run environment to keep the JIT.

## Interpreting the result

| Outcome | Reading |
|---|---|
| KGE up **and** matrix/multipath τ relax to till-basin values | `Q_gw` groundwater-capacitor is the right physics; lake support works. |
| KGE up but τ still pinned at bounds | Lake only added flexibility; suspect the missing **channelized routing** (lake on main stem). |
| KGE ~flat | The disconnected lake can't buffer enough via groundwater alone → the basin's lake signal is dominated by routed surface inflow → **this is the observed v2 outcome; move to `f_route_lake > 0`** (now implemented — see `HANDOFF_f_route_lake.md`). |

The relaxation of the substrate timescales is the headline diagnostic. Record the
calibrated matrix τ and multipath τ alongside KGE for each run.

## MNiShed-side reference

Lake support is implemented on MNiShed `master` (commits: lake sub-catchment kind
`c130cbe`, `Q_gw` exchange `2f4e70c`, calibration wiring `65d51f2`, JIT mirror
`89d52fa`, docs `f1d39bd`; design doc `2c389ba`; generalization issue #19). Update
your MNiShed install to a `master` that includes these before running.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
