# Design: Parallel sub-catchments for MNiShed

Status: draft for review (June 2026). Motivated by Wild Rice River
calibration; intended as the basis for a future MNiShed PR. Same
stewardship approach as the multipath PR (#14): design and review first,
implement only after agreement.

## Motivation

The Wild Rice River basin spans two spatially distinct hydraulic zones:
till uplands (with tile drainage) in the upper basin, lake clay lowlands
(with ditch drainage) in the lower basin. They are connected only at the
river — water from each zone discharges into the channel in *parallel*,
not in a vertical cascade. The current MNiShed architecture cascades
reservoirs sequentially (water from r=0 flows into r=1, etc.), which
conflates the spatially parallel structure into a serial one that can
only partially represent it.

This addition adds support for *parallel sub-catchments*, each of which
is internally a serial reservoir cascade (as MNiShed already supports).
Sub-catchments contribute to streamflow weighted by their basin-area
fractions and otherwise operate independently.

## Goals (this design)

1. Support N parallel sub-catchments, each with its own M-reservoir
   vertical cascade (M can differ per sub-catchment).
2. Each sub-catchment has its own multipath, exfiltration, junction,
   recession parameters at the reservoir level.
3. Each sub-catchment has a basin-area fraction (sums to 1 across
   sub-catchments).
4. Backwards compatibility: existing YAMLs and existing `run_and_score`
   calls must continue to work without modification (single sub-catchment
   covering the whole basin is the implicit default).
5. JIT path supports the new structure with flat arrays and index ranges
   (Numba-friendly).

## Non-goals (deferred to future PRs)

These items are designed in to the API now (so future implementation
won't break interfaces) but are *not* implemented in this PR:

- Per-sub-catchment forcing time series (precipitation, ET,
  temperature). The initial implementation shares basin-level forcing
  across all sub-catchments. The YAML schema reserves a `forcing:` key
  per sub-catchment that is parsed but not yet used.
- Per-sub-catchment snowpack and FGI state. Initially the basin-level
  snowpack and FGI are shared. The internal data structure stores
  per-sub-catchment snowpack/FGI state to allow this to diverge in
  the future without API changes.
- Inter-sub-catchment exchange (e.g., regional groundwater between
  sub-catchments). Out of scope.

## Conceptual model

Let the basin be partitioned into K sub-catchments, each with area
fraction `a_k`. Each sub-catchment has its own vertical cascade of
M_k reservoirs with their own dynamics.

For each timestep:
1. Compute basin-level snowpack and FGI updates (or per-sub-catchment if
   that's enabled — deferred).
2. For each sub-catchment k = 1..K:
   - Apply the recharge, cascade through reservoirs, compute exfiltrated
     water → produce `Q_k` (per-unit-area discharge in mm/day).
3. Basin discharge `Q_basin = Σ a_k · Q_k` (area-weighted mean).

This preserves area-weighted mass balance for water leaving the basin.
Storage volumes within each sub-catchment are per-unit-area; total
basin storage is `Σ a_k · H_k`.

## Data model

### `SubCatchment` (new class)

```python
class SubCatchment:
    """A parallel hydraulic compartment of the basin with its own
    reservoir cascade and (optionally) its own forcing."""

    def __init__(self, name, area_fraction, reservoirs, *,
                 snowpack=None, fgi_init=0.0, forcing=None):
        self.name             = name          # str, label only
        self.area_fraction    = area_fraction  # float, [0, 1]; basin shares sum to 1
        self.reservoirs       = reservoirs    # list[Reservoir], vertical cascade
        self.snowpack         = snowpack      # Snowpack or None (use basin-shared)
        self.fgi              = fgi_init      # float, frozen-ground index state
        self.forcing          = forcing       # dict or None (use basin-level forcing)
        # Other state (deficit_carry, etc.) is per-sub-catchment too.
```

`forcing` (when supplied) would have its own `{datafile, ...}` block. In
this PR it is parsed if present but a `NotImplementedError` is raised on
construction so users know the support is forthcoming.

### `Buckets` changes

```python
class Buckets:
    # Existing attributes preserved.
    # New attribute:
    self.sub_catchments  # list[SubCatchment], length ≥ 1

    @property
    def reservoirs(self):
        # Backward compat: flat list across all sub-catchments.
        # When a single sub-catchment exists, equivalent to the old
        # self.reservoirs.
        return [r for sc in self.sub_catchments for r in sc.reservoirs]

    @property
    def n_sub_catchments(self):
        return len(self.sub_catchments)
```

When the YAML lacks a `sub_catchments:` block, `Buckets.initialize`
constructs a single SubCatchment with `area_fraction = 1.0` containing
all the reservoirs defined under the legacy `reservoirs:` block.
**Existing user code continues to work unchanged.**

## YAML API

### Legacy (unchanged)

```yaml
reservoirs:
  recession_timescales__days: [200]
  ...
```

Becomes one SubCatchment with `area_fraction=1.0`.

### New multi-sub-catchment

```yaml
sub_catchments:
  - name: till_uplands
    area_fraction: 0.55
    # optional: own forcing (parsed but not yet implemented)
    # forcing:
    #   datafile: /path/to/till_forcing.csv
    # (snowpack and FGI shared from basin-level unless specified)
    reservoirs:
      recession_timescales__days: [200]      # one reservoir
      exfiltration_fractions:    [1.0]
      maximum_effective_depths__mm: [1.0e6]
      multipath_thresholds__mm:  [100.0]
      multipath_timescales__days: [10.0]
      recession_exponents:       [1.0]
      # any other per-reservoir lists ...
  - name: clay_lowlands
    area_fraction: 0.45
    reservoirs:
      recession_timescales__days: [1500]
      exfiltration_fractions:    [1.0]
      maximum_effective_depths__mm: [1.0e6]
      multipath_thresholds__mm:  [50.0]
      multipath_timescales__days: [30.0]
      recession_exponents:       [1.0]
```

Multi-reservoir cascade within a sub-catchment is fully supported:

```yaml
sub_catchments:
  - name: till_uplands
    area_fraction: 0.55
    reservoirs:
      recession_timescales__days: [50, 500]   # two reservoirs in cascade
      exfiltration_fractions:    [0.6, 1.0]
      ...
```

Inside a sub-catchment, the reservoirs cascade just as they always have.

Validation:
- `area_fraction` values must sum to 1.0 (± 1e-6 tolerance) across all
  sub-catchments.
- Each sub-catchment must have at least one reservoir.
- `name` is required and must be unique.
- `forcing:` block is parsed but raises `NotImplementedError` on
  construction in this PR.

## Python API: `run_and_score`

### Legacy call (backward compat)

```python
run_and_score(cfg, recession_coeff=[200], multipath_threshold=[100],
              multipath_timescale=[10], ...)
```

Lists are length n_reservoirs (single sub-catchment).

### New call with sub-catchments

Two options considered; recommend **Option B (structured dict)** for
clarity at the call site:

**Option A: lists of lists, keyed implicitly by sub-catchment order**

```python
run_and_score(cfg,
              area_fractions=[0.55, 0.45],
              recession_coeff=[[200], [1500]],
              multipath_threshold=[[100], [50]],
              multipath_timescale=[[10], [30]],
              ...)
```

Pro: minimal change. Con: lots of nested-list bookkeeping; easy to
get the indices wrong.

**Option B: structured dict (recommended)**

```python
run_and_score(cfg,
              sub_catchments=[
                  {'area_fraction': 0.55,
                   'recession_coeff':       [200],
                   'multipath_threshold':   [100],
                   'multipath_timescale':   [10],
                   ...},
                  {'area_fraction': 0.45,
                   'recession_coeff':       [1500],
                   'multipath_threshold':   [50],
                   'multipath_timescale':   [30],
                   ...},
              ],
              # snow + ET params remain at basin level for now
              melt_factor=5.0, et_scale=0.755, ...)
```

Backward compat: if `sub_catchments=None`, fall back to flat per-reservoir
lists as today.

Recommendation: implement **Option B**. The call site is more verbose but
self-documenting; lists of lists invite subtle index bugs.

## JIT loop architecture

The JIT-compiled `_jit_run` must remain Numba-friendly (no Python dicts,
no nested ragged lists). Use flat arrays with index ranges:

```python
@_numba.jit(nopython=True, cache=True)
def _jit_run(P_arr, ET_arr, T_arr, T_min_arr, T_max_arr,
             # NEW: sub-catchment indexing
             sc_start_idx,        # int64[n_sub]  — start index in reservoir arrays
             sc_end_idx,          # int64[n_sub]  — end (exclusive)
             sc_area_fractions,   # float64[n_sub]
             # Per-sub-catchment state (initial values, shape [n_sub])
             H_snow_init_per_sc,  # float64[n_sub]
             fgi_init_per_sc,     # float64[n_sub]
             H_deficit_carry_init_per_sc,  # float64[n_sub]
             # Reservoir state (flat across all sub-catchments, length sum_k M_k)
             H_init,
             # Per-reservoir parameters (flat, length sum_k M_k) — already exist
             tau_arr, b_arr, H_ref_arr, f_dis_in, junction_arr,
             leakance_R_arr, H_threshold_arr, Hmax_arr,
             f_tile_arr, tau_tile_arr, H_tile_init,
             multipath_thr_arr, multipath_tau_arr,
             # Snow + ET + flags
             melt_factor, ..., dt, has_snowpack, ...,):
    ...
```

Inside the time loop:

```python
for step in range(n_steps):
    # Read forcing (basin-shared in this PR)
    P_t  = P_arr[step]; ET_t = ET_arr[step]; T_t = T_arr[step]
    ...

    qi_basin = 0.0
    H_sub_total = 0.0

    # Update snowpack/FGI per sub-catchment (initially identical updates)
    for sc in range(n_sub):
        # Existing snow/FGI logic but operating on per-sc state
        # H_snow_per_sc[sc], fgi_per_sc[sc], etc.
        # (When forcing is shared, all sub-catchments produce identical
        #  state updates — slight redundancy but correct architecture.)
        ...
        # Then cascade the reservoirs of this sub-catchment:
        r_start = sc_start_idx[sc]
        r_end   = sc_end_idx[sc]
        qi_sc = 0.0
        for r_local in range(r_end - r_start):
            r = r_start + r_local
            # Existing cascade code; r is the flat-array index
            ...
            qi_sc += H_discharge
        # Tile, multipath blocks: as today, indexed by r
        ...

        # Sum into basin-mean discharge weighted by area
        qi_basin   += sc_area_fractions[sc] * qi_sc
        H_sub_total += sc_area_fractions[sc] * (Σ H_res[r] for r in [r_start, r_end))

    Q_out[step]   = qi_basin
    ...
```

Result: existing single-sub-catchment behavior is preserved exactly
(K=1, area_fractions=[1.0]). Multi-sub-catchment behavior emerges
naturally from the loop.

Snowpack and FGI use per-sub-catchment state arrays in the JIT signature
even though initially they evolve identically. This is the forward-compat
hook for per-sub-catchment forcing.

## Backwards compatibility

Critical: all existing test cases and YAML configs must work unchanged.

Specifically:
- Legacy `reservoirs:` YAML block → internally promoted to a single
  sub-catchment with `area_fraction=1.0`.
- Legacy `run_and_score(cfg, recession_coeff=[...], ...)` → flat lists
  interpreted as single sub-catchment.
- `Buckets.reservoirs` continues to return a flat list of all reservoirs
  (across all sub-catchments). For single-sub-catchment case, identical
  to today.
- Existing `_jit_run` signature has new arguments; non-sub-catchment call
  paths get `sc_start_idx=[0]`, `sc_end_idx=[n_res]`,
  `sc_area_fractions=[1.0]`, `*_per_sc` = arrays of length 1.

All existing tests should pass unchanged.

## Testing plan

Add `tests/test_sub_catchments.py` covering:

1. **Legacy YAML still works** — `reservoirs:` block creates a single
   SubCatchment with area_fraction=1.0; identical output to pre-PR.
2. **Two-sub-catchment YAML loads correctly** — areas sum to 1; each
   has its own reservoir list; `Buckets.n_sub_catchments == 2`.
3. **Validation:** area_fractions not summing to 1 → ValueError;
   duplicate names → ValueError; empty reservoirs → ValueError.
4. **Mass balance:** synthetic constant precipitation, no losses → total
   basin discharge equals integrated precipitation × area weighted sum.
5. **Two identical sub-catchments equal one large one:** for two sub-
   catchments with identical reservoir params, area_fractions = (0.6,
   0.4), the basin discharge should equal a single-sub-catchment run
   with the same params. Tests the area-weighted aggregation.
6. **Parallel cascade ≠ serial cascade:** two reservoirs in cascade
   (single sub-catchment) produce a different hydrograph than two
   reservoirs as parallel sub-catchments (with same individual
   parameters). Confirms the architectural distinction.
7. **Multipath in sub-catchment:** sub-catchments with different
   multipath thresholds produce different responses; verify against
   analytic formula.
8. **Per-sub-catchment forcing parses but raises `NotImplementedError`**
   when forcing block is present.

## Implementation scope (this PR)

What's IN:
- `SubCatchment` class
- `Buckets` parses `sub_catchments:` YAML, constructs the structure
- Legacy `reservoirs:` YAML still works (auto-wrapped)
- `_jit_run` extended with sub-catchment indexing + area weighting
- `run_and_score` accepts `sub_catchments=[...]` structured arg
- Tests as above
- Documentation in `configuration.rst` and `model_description.rst`

What's OUT (deferred):
- Per-sub-catchment forcing (parser is wired up, but raises on use)
- Inter-sub-catchment exchange terms
- Visualization tools for sub-catchment outputs

## Estimated effort

Comparable to the multipath PR (#14): ~6 granular commits, ~250–400
lines net code change, plus tests and docs. Two main complexity items:
the JIT-loop refactor (flat-index handling), and the YAML+run_and_score
API. Tests will be straightforward.

## Open design questions

Two questions worth resolving before code:

**Q1.** Should snowpack and FGI be per-sub-catchment from day 1, or
basin-shared with the forward-compat hook?

   Answer (recommended): per-sub-catchment state from day 1, with
   identical updates under shared forcing. Slight memory/compute
   overhead, big payoff in forward-compat cleanness. No public-API
   change later when per-sub-catchment forcing is added.

**Q2.** What if a sub-catchment has zero reservoirs (e.g., "direct
runoff only")?

   Answer (recommended): disallow in this PR; require ≥ 1 reservoir per
   sub-catchment. Could relax later for a "pure direct-runoff zone"
   pattern, but YAGNI for now.

---

## What I want from you before I touch code

- Confirm "sub_catchments" as the term (vs. "compartments," "zones")
- Confirm Option B (structured dict in `run_and_score`)
- Confirm answer to Q1 (per-sub-catchment snowpack/FGI from day 1)
- Confirm answer to Q2 (require ≥ 1 reservoir per sub-catchment)
- Any naming or API tweaks before I start

Once aligned, I'll write the PR on a feature branch in MNiShed (same
process as multipath PR #14) — design committed first, then granular
commits, full test suite green, then ready for review.
