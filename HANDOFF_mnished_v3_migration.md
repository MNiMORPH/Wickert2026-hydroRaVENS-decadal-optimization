# Handoff: MNiShed v3.0.0 migration (calibration project)

*Written 2026-06-23 from a MNiShed library-side session. This was a read-only
look at this project — no scripts or configs here were modified. The fixes
below are yours to apply and run.*

## TL;DR

The MNiShed v3.0.0 audit corrected a **misspelling in the
`evapotranspiration_method` value**: the library now accepts only
`datafile` or **`ThornthwaiteChang2019`** (previously it only accepted the
misspelled `ThorntwaiteChang2019`). Many configs in this project still carry
the old spelling and **will raise `ValueError` on any Thornthwaite-mode run
against the updated library** until renamed. That is the one hard, must-do
item here. The session also renamed several BMI variables, but this project
does **not** use the BMI, so those changes do not affect you.

## 1. REQUIRED — rename the ET method value (hard break)

MNiShed now validates the method string and raises:

    ValueError: evapotranspiration_method must be "datafile" or
    "ThornthwaiteChang2019".

so every config with `evapotranspiration_method: ThorntwaiteChang2019`
(missing the second *h*) fails until fixed. Only the value changes —
behaviour is identical.

Affected catchments (active configs) as of this writing: **wild_rice,
cannon, le_sueur, blue_earth, root, cottonwood, trempealeau, redwood.**
List the exact files first:

```bash
grep -rlI 'ThorntwaiteChang2019' --include='*.yml' --include='*.yaml' .
```

Then rename in place:

```bash
grep -rlI 'ThorntwaiteChang2019' --include='*.yml' --include='*.yaml' . \
  | xargs sed -i 's/ThorntwaiteChang2019/ThornthwaiteChang2019/g'
```

Note: several matches are **frozen run snapshots** under
`*/archive*/` (e.g. `cannon_river/archive_global-full-record-ET/...`).
Those are historical records of completed runs; rename them only if you
intend to re-run them. To skip archives:

```bash
grep -rlI 'ThorntwaiteChang2019' --include='*.yml' --include='*.yaml' . \
  | grep -v '/archive' \
  | xargs sed -i 's/ThorntwaiteChang2019/ThornthwaiteChang2019/g'
```

## 2. Not applicable — BMI variable names

The session reviewed the BMI input/output names against current CSDMS
Standard Names and renamed five: air temperature →
`atmosphere_bottom_air__temperature`; daily extremes →
`atmosphere_bottom_air__time_min_of_temperature` /
`…__time_max_of_temperature`; discharge →
`channel_exit_water_x-section__volume_flow_rate`; and the ET forcing input →
`land_surface_water__uncorrected_evapotranspiration_volume_flux`. **This
project drives MNiShed through `run_and_score` / Dakota, not the BMI**
(confirmed: no `BmiMNiShed` / `BmiHydroRaVENS` usage), so none of these
require any change here. You can ignore the BMI section of the v3.0.0 notes.

## 3. The recession key + MRT science live in the companion handoff

`HANDOFF_Href_MRT_correction.md` covers the `recession_coefficients`
config-key rename (from `recession_timescales*` /
`e_folding_residence_times__days`) and the H_ref / MRT decadal-trend
correction. That remains the larger migration and is **not** duplicated
here. (You noted Cannon + Blue Earth were already migrated; the remaining
catchments' configs still carry the old key — `grep -rl
'recession_timescales\|e_folding_residence_times__days' .` to find them.)

## 4. Do NOT change these (false positives the grep will surface)

- **`log__t_recession_*`** in `*/decades/*/params.yml`, `summarize.py`,
  and `plot_best.py` are *your Dakota parameter labels*, not MNiShed keys.
  MNiShed's constructor-arg rename (`t_efold` / `t_recession` →
  `recession_coeff`) does **not** require renaming these — your driver
  already maps them into `run_and_score(recession_coeff=…)`. What matters is
  their *meaning*: for `b > 1` the value is a drainage coefficient
  (`day·mm^(b-1)`), not a timescale — see the companion handoff.
- **`db.out.hydroravens`** in `setup_watershed.py` is a GRASS GIS addon
  module name, unrelated to the Python-package rename. Leave it.
- The `# … hydroravens and dakota.interfacing …` comments in the
  `run_driver.sh` scripts are informational; the active imports already use
  `from mnished import …`.

## 5. Verify after migration

- Pick one Thornthwaite-mode catchment (e.g. `wild_rice_river`) and confirm
  a forward/score run no longer raises the ET-method `ValueError`.
- Active imports already use `from mnished import …` (no live `hydroravens`
  imports remain), so a clean run also confirms the package migration.

## Action items

- [ ] Rename `ThorntwaiteChang2019` → `ThornthwaiteChang2019` in the active
      configs (§1).
- [ ] Decide whether to also update the archived run snapshots (§1).
- [ ] Finish the `recession_coefficients` key migration for the remaining
      catchments (companion handoff, §3).
- [ ] Sanity-run one Thornthwaite catchment to confirm (§5).
