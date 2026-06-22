# Handoff: H_ref / MRT correction in the decadal residence-time analysis

*Written 2026-06-22 from a MNiShed library-side audit session. This was a
read-only analysis — no calibration files were modified. The fix is yours to
apply in this (calibration) project.*

## TL;DR

`plot_trends.py` reports `MRT = τ^(1/b)` (labelled "[days]"). That formula
omits the gauge factor `H_ref^((b−1)/b)`. The calibrations ran through
`run_and_score`, which anchored `recession_H_ref = [50, 100, 1000]` mm, so the
calibrated recession coefficient τ is **not** in the `H_ref = 1` gauge that the
`plot_trends` formula assumes. The reported MRTs are therefore too short, and
the **soil-reservoir MRT *trend* across decades is distorted** (not merely
offset), because `recession_b_soil` is calibrated per decade.

## The math

Power-law recession is `Q = (H/τ)·(H/H_ref)^(b−1) = H^b / τ_eff`, with
`τ_eff = τ·H_ref^(b−1)`. Only `τ_eff` is identifiable from data — `H_ref` is a
redundant gauge that rescales τ. The recession coefficient τ is therefore
**not a timescale** for `b > 1`. The physical mean residence time is

```
MRT = τ_eff^(1/b) / Q_ref^(1−1/b)
    = τ^(1/b) · H_ref^((b−1)/b) / Q_ref^(1−1/b)
```

`plot_trends.py` drops the `H_ref^((b−1)/b)` factor.

## What is and isn't affected

- **Fits, KGE/AIC scores, discharge, calibrated coefficients: CORRECT.** H_ref
  was applied consistently during calibration. No re-fit is needed for these.
- **`forward_analysis.py`: CORRECT.** It sets `H_REFS = [50, 100, 1000]` and
  re-anchors τ to local mean storage; it is fully gauge-aware.
- **`plot_trends.py` MRT columns: the error.** Per reservoir (mapping from
  `forward_analysis.py`):
  - **Soil** — reservoir 0, `H_ref = 50`, `b` **calibrated per decade**
    (`recession_b_soil: active: true`, bounds 1.5–6.0). Too short by
    `50^((b−1)/b)`, which ranges ~3.7× (b=1.5) to ~24.5× (b=6). Because b
    varies decade-to-decade, **the trend shape is distorted, not just
    rescaled.** This is the scientifically consequential one.
  - **Intermediate** — reservoir 1, `H_ref = 100`, `b = 2.203` **fixed**. Too
    short by a constant ~12.4×. Absolute values wrong; **trend shape
    preserved**.
  - **Deep** — reservoir 2, **linear (`b = 1`)**. `H_ref` is irrelevant for a
    linear reservoir, so **deep MRT is correct** (despite `H_ref = 1000`).

## The MNiShed-side change (already on `master`)

Commit `598d8b0` ("Standardize recession_H_ref at 1.0; make MRT gauge-correct"):
`run_and_score` no longer sets the `[50,100,1000]` anchor (H_ref stays at the
Reservoir default 1.0), and `Reservoir.mean_residence_time()` now uses `τ_eff`
so it is correct for any H_ref. **With H_ref = 1, the calibrated τ *is* τ_eff.**

## Two ways to fix (pick one)

1. **Re-run the decade calibrations against the updated MNiShed** (H_ref = 1).
   Then `plot_trends`'s `τ^(1/b)` becomes the correct gauge-invariant MRT
   composite as written — no `plot_trends` change needed. Cleanest, but it is a
   full recompute of every decade × catchment.

2. **Correct in place without re-running.** In `plot_trends.py`, multiply each
   reservoir's plotted MRT by `H_ref^((b−1)/b)` using the per-decade calibrated
   b and the per-reservoir H_ref (`soil=50, intermediate=100, deep=1000` — deep
   is unaffected since b=1). Apply wherever the `mrt_*` columns are built, and
   re-make any paper figures from them. **Note the soil trend will change
   shape**, not just scale.

## Action items

- [ ] Decide: re-run (option 1) vs in-place correction (option 2).
- [ ] Recompute **soil** MRT trends before they enter the Wickert-2026 paper.
- [ ] Sanity check after the fix: deep MRT unchanged; intermediate MRT rescaled
      by ~12.4×; soil MRT trend re-shaped (per-decade factor 3.7–24.5×).
- [ ] (Recommended) Make `plot_trends._mrt` gauge-correct (multiply by
      `H_ref^((b−1)/b)`) so it is right regardless of which MNiShed version
      produced the runs — and ideally read the physical timescale from
      `mnished`'s `mean_residence_time()` rather than recomputing it.

## Also required if you re-run (option 1): config-key rename

The updated MNiShed renamed the YAML key `recession_timescales__days` →
`recession_timescales` (the `__days` suffix was dropped because the recession
coefficient is not in days for `b > 1`). Before re-running any calibration
against the updated library, rename this key in every `params.yml` / config in
this project (the coefficient *values* do not change — only the key name):

```bash
grep -rl 'recession_timescales__days' . \
  | xargs sed -i 's/recession_timescales__days/recession_timescales/g'
```

This is in addition to the broader hydroRaVENS → mnished v3 migration (package
import, `BmiHydroRaVENS` → `BmiMNiShed`, etc.).

## Reminder for the fix session

The recession coefficient (`recession_coeff` / `log__t_recession_*`) is **not a
timescale** when `b > 1`; its units are `day·mm^(b−1)`. Use
`mean_residence_time(Q_ref)` for a physically comparable timescale, or the
`τ^(1/b)·H_ref^((b−1)/b)` composite. Do not treat `10**log__t_recession_*`
directly as days for the nonlinear reservoirs.
