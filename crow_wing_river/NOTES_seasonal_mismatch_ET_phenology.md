# Crow Wing seasonal mismatch — an ET-phasing (forest phenology) problem

*2026-06-27. Diagnostic record + motivation for a phenology-aware ET module.*

## The mismatch

The frozen-ground / two-layer-land / lake model fits the multi-decade record
well overall (mean KGE_logKGE 0.704, beating the 0.597 no-lake baseline), but a
seasonal residual persists: **spring under-produces, fall over-produces**
(2001–2010, multi-decade best params):

| season | obs | mod | mod/obs |
|---|---:|---:|---:|
| DJF | 0.352 | 0.368 | 1.04 |
| MAM | 0.647 | 0.501 | **0.77** |
| JJA | 0.458 | 0.463 | 1.01 |
| SON | 0.430 | 0.520 | **1.21** |

## What the water balance shows

A seasonal water-balance + per-source decomposition (`calib_frozen/diagnostics/diag_seasonal_mass_balance.py`):

- **Not a summer-ET deficit.** Summer ET (3.07 mm/d) already *exceeds* P (2.85) —
  the model draws summer moisture down hard. (Earlier hypothesis refuted.)
- **The fall surplus is a flat groundwater baseflow.** The gw reservoir releases
  ~0.24 mm/d in *every* season (0.243 / 0.226 / 0.244 / 0.250) and never recedes;
  in fall, when observed flow drops, that flat baseflow overshoots. The lake is
  now minor (~0.04 mm/d).
- **The freshet is evaporated, and the timing is the tell.** The snowpack melts in
  **April**, but April ET (1.64) ≈ April P (1.68); May ET (2.36) consumes the May
  rain. The melt + early rain arrive exactly when ET is near-saturating.

## The diagnostic — seasonal mass-balance decomposition (reusable)

The test that distinguished "ET mis-phasing" from "lake routing / storage", and
the part most worth keeping for other basins. For any calibrated run, per season
tabulate the modeled basin-mean **P, ET, ΔStorage, and Q split by source** (fast
soil/overland, slow groundwater, lake outlet) against observed Q, plus monthly
SWE/ET for melt timing (`calib_frozen/diagnostics/diag_seasonal_mass_balance.py`; instruments
`_advance_sub_catchment` / `_advance_lake` for the per-source split). Reading the
patterns:

- summer **ET > P** but Q still over → surplus is **slow-store release**
  (baseflow not receding), not an ET deficit — here gw was flat ~0.24 mm/d all
  year;
- **freshet missing and spring ET ≈ P at melt** → ET is **consuming the melt**
  (the phasing signature — April ET 1.64 ≈ P 1.68);
- a per-source flow **flat across seasons** → that store is not responding
  seasonally (over-buffered lake / non-receding gw).

It turns "the seasonality is wrong" into "*which* flux / source / timing is
wrong." We first blamed lake routing; this decomposition showed it was ET.

## The cause: Thornthwaite ET is mis-phased vs. forest leaf-out

Thornthwaite ET is temperature-only — it ramps up with spring warmth **ignoring
vegetation phenology**. In a northern mixed forest the canopy has not leafed out
in April (leaf-out ~mid-May), so real early-spring ET is *lower* than Thornthwaite
gives. The model therefore over-evaporates the snowmelt / early rain (stealing the
freshet), and the low `et_scale` (0.65) it needs to balance the annual volume then
inflates the rest of the year — including the flat fall baseflow.

## Confirming kludge: leaf-out phenology factor on ET

A crude monthly LAI/leaf-out factor on ET (Jan–Apr 0.2–0.35, **May 0.7**, Jun–Aug
1.0, Sep–Oct 0.9–0.6, Nov–Dec 0.3), with `et_scale` re-raised to restore the
annual balance (`calib_frozen/diagnostics/diag_phenology_etsweep.py`):

| | KGE | DJF | MAM | JJA | SON |
|---|---:|---:|---:|---:|---:|
| baseline (Thornthwaite) | 0.727 | 1.04 | 0.77 | 1.01 | 1.21 |
| + leaf-out kludge (et=0.95) | **0.748** | 0.92 | 0.82 | 0.74 | **0.99** |

Concentrating ET into the growing season helps and raises KGE, confirming the
mechanism, but a *fixed-`et_scale`* sweep over-dries mid-summer — so the real
test is a full re-calibration with the factor active.

### Re-calibration with the kludge (all 9 params free, 8 decades)

`calib_frozen/calibrate_phenology.py` — best **mean KGE_logKGE 0.736 vs. 0.704
baseline** (+0.032); single-decade pure KGE 0.802, r 0.839, top-20 peaks 0.840
(best yet).

Best params: PDD 5.68, et_scale 0.78, τ_soil 51 d, τ_gw 1494 d, f_exfil 0.69,
τ_lake 18,700, H_sill 2049 mm, f_route 0.47, fdd_threshold 31.6 °C·day. Phenology
factor (monthly, on ET): Jan–Mar 0.2, Apr 0.35, May 0.7, Jun–Aug 1.0, Sep 0.9,
Oct 0.6, Nov–Dec 0.3. (NB: the phenology factor is a runtime monkeypatch in
`calibrate_phenology.py`, *not* a config option — it needs a real ET module to
become a reproducible config.)

Seasonal:

| season | obs | baseline | + phenology (recal) |
|---|---:|---:|---:|
| DJF | 0.352 | 1.04 | **1.38** |
| MAM | 0.647 | **0.77** | **1.01** |
| JJA | 0.458 | 1.01 | 0.98 |
| SON | 0.430 | 1.21 | 1.21 |

- **Spring freshet solved** (MAM 0.77→1.01; freshet *events* captured, top-20
  0.84). The main goal.
- **Summer stayed balanced** (0.98) — freeing all params avoided the over-drying
  the fixed-`et_scale` sweep showed.
- **PDD recalibrated to a sane, identifiable 5.7** (from the unconstrained ~3.3):
  with ET phasing right, melt timing reaches the gauge and PDD pins down. (5.7 is
  high-ish for dense forest — cross-check against the eventual land-cover DDF
  prior, #22.)
- **Did NOT fix fall** (SON 1.21 unchanged): confirms fall is a *separate* problem
  — the flat, non-receding **groundwater baseflow**, not ET phasing.
- **Introduced winter over-production** (DJF 1.04→1.38): the kludge cuts winter ET
  too hard (×0.2 on an already-tiny Thornthwaite winter ET). Refinement: leave
  winter near 1.0 (Thornthwaite already gives low winter ET).

**Verdict: the phenology mechanism is real and earns a proper module.** Two clear
follow-ups: (1) soften the curve — don't suppress winter; (2) the fall surplus is
a groundwater-recession problem, addressed separately.

### Leaf-out timing — verified for the region

Crow Wing is north-central Minnesota (~46–47°N). Sources put the *functional*
canopy leaf-out (when transpiration ramps) at **mid-to-late May**, full canopy
~early June; April shows only bud-break / aspen catkins, not a transpiring
canopy. Phenology runs ~9 days later up north — common lilac flowers ~May 12 in
the Twin Cities vs. ~May 21 in Itasca County (north-central) — which brackets the
Crow Wing window. So the kludge's April-suppressed / **May-ramp** / June-full
phasing is source-backed, not just a guess.

*Caveat for a real module:* leaf-out shifts ±1–2 weeks year-to-year (and is
trending earlier), so a fixed calendar curve is itself a kludge — an **NDVI /
green-up-driven** ET factor (the same remote-sensing input MNiMORPH/MNiShed#22
wants for the DDF prior) is the right long-term form. Sources: USA-NPN *Status of
Spring*; UMN Extension; Season Watch (UMN).

## Implications / TODO

- **Motivation for a phenology-aware ET module** (later work). A leaf-out /
  senescence curve — ideally driven by **NDVI / land cover** rather than
  temperature alone — would move ET out of early spring and shape the fall ramp.
  This is the *same* remote-sensing input the DDF-prior need wants
  (MNiMORPH/MNiShed#22) — one "priors/forcing from land cover" body of work.
- **Spring freshet is only partly an ET problem.** ET phasing helps spring a
  little; the rest is snowpack magnitude (modest ~25 mm peak SWE) and
  **frozen-ground thaw timing** — if the ground thaws before the April melt, the
  melt infiltrates instead of running off. Still to test.
- The flat, non-receding **groundwater baseflow** is a partly separate fall issue
  (the gw reservoir's recession shape).
