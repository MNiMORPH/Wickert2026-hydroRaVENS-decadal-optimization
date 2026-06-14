#!/usr/bin/env python3
"""
Factory: create a new watershed calibration directory from a config YAML.

Usage (from Wickert2026-hydroRaVENS-decadal-optimization/):
    python setup_watershed.py --config watershed_configs/blue_earth_river.yml
    python setup_watershed.py --config watershed_configs/le_sueur_river.yml

Creates:
  {name}/                              study directory with all scripts
    decades/{label}/params.yml         one params.yml per calibration decade
  db.out.hydroravens/examples/{name}/  GRASS forcing-data pipeline script

The Cannon River directory is used as the script template source.
To add a new watershed: write a watershed_configs/<name>.yml and re-run.
"""

import argparse
import shutil
import stat
import yaml
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--config', required=True, help='Watershed config YAML')
parser.add_argument('--template-dir', default='templates',
                    help='Source directory for scripts (default: templates/)')
args = parser.parse_args()

with open(args.config) as f:
    cfg = yaml.safe_load(f)

name          = cfg['name']
title         = cfg['title']
gauge         = cfg['gauge']
config_name   = cfg['forcing']['config_name']
forcing_csv   = cfg['forcing']['csv_name']
forcing_start = cfg['forcing']['start']
forcing_end   = cfg['forcing']['end']
grass_loc     = cfg.get('grass_location', ''.join(w.title() for w in name.split('_')))
grass_epsg    = cfg.get('grass_epsg', 32615)
first_year    = int(cfg['decades']['first_year'])
last_year     = int(cfg['decades']['last_year'])
params0       = cfg['initial_params']

TEMPLATE_DIR = Path(args.template_dir)
STUDY_DIR    = Path(name)
EXAMPLES_DIR = Path('forcing') / name

# ---------------------------------------------------------------------------
# 1. Study directory + scripts
# ---------------------------------------------------------------------------

STUDY_DIR.mkdir(exist_ok=True)

# Scripts that need no changes at all
GENERIC_SCRIPTS = [
    'run.sh', 'run_all_decades.sh', 'archive_run.sh',
    'driver.py', 'run_driver.sh',
]
# Scripts that contain "Cannon River" in titles / docstrings
TITLE_SCRIPTS = [
    'plot_best.py', 'plot_trends.py', 'generate_dakota_in.py', 'summarize.py',
]

for fname in GENERIC_SCRIPTS:
    src = TEMPLATE_DIR / fname
    dst = STUDY_DIR / fname
    shutil.copy2(src, dst)
    dst.chmod(dst.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP)
    print(f'  copied  {fname}')

for fname in TITLE_SCRIPTS:
    src = TEMPLATE_DIR / fname
    text = src.read_text()
    text = text.replace('WATERSHED_TITLE', title)
    text = text.replace('WATERSHED_NAME', name)
    dst = STUDY_DIR / fname
    dst.write_text(text)
    dst.chmod(dst.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP)
    print(f'  adapted {fname}')

# ---------------------------------------------------------------------------
# 2. Decade directories + params.yml
# ---------------------------------------------------------------------------

PARAMS_TEMPLATE = """\
# {label}: independent calibration, {decade_start} to {decade_end}.
# A02 model structure: soil / intermediate / deep; frozen_ground enabled; k=8 active params.

modules:
  snowpack:          true
  frozen_ground:     true
  rain_on_snow:      true
  direct_runoff:     false
  dtr_fgi_decay:     true
  et_water_stress:   false
  et_reservoir_draw: true

dakota:
  ego_initial_samples:       300
  ego_seed:                  12345
  ps_max_evaluations:        200
  ps_convergence_tolerance:  1.0e-4
  evaluation_concurrency:    4

driver:
  config_template:       '{config_name}'
  metric:                'KGE_logKGE'
  spin_up_cycles:        1
  routing_N:             2
  n_reservoirs:          3
  reservoir_order:       ['soil', 'intermediate', 'deep']
  decade_start:          '{decade_start}'
  decade_end:            '{decade_end}'
  enforce_water_balance: 'global'

parameters:

  log__t_recession_soil:
    description: "log10 soil-zone recession time scale [days]"
    lower:   1.0
    upper:   4.5
    initial: {log__t_recession_soil}
    fixed:   {log__t_recession_soil}
    active:  true

  log__t_recession_intermediate:
    description: "log10 intermediate recession time scale [days]"
    lower:   1.0
    upper:   4.5
    initial: {log__t_recession_intermediate}
    fixed:   {log__t_recession_intermediate}
    active:  true

  log__t_recession_deep:
    description: "log10 deep groundwater recession time scale [days]"
    lower:   3.5
    upper:   5.0
    initial: {log__t_recession_deep}
    fixed:   {log__t_recession_deep}
    active:  true

  f_exfiltration_soil:
    description: "fraction of soil-zone drainage to stream (remainder recharges intermediate)"
    lower:   0.01
    upper:   0.99
    initial: {f_exfiltration_soil}
    fixed:   {f_exfiltration_soil}
    active:  true

  f_exfiltration_intermediate:
    description: "fraction of intermediate drainage to stream (remainder recharges deep)"
    lower:   0.01
    upper:   0.99
    initial: {f_exfiltration_intermediate}
    fixed:   {f_exfiltration_intermediate}
    active:  true

  PDD_melt_factor:
    description: "degree-day snowmelt rate [mm SWE / degC / day]"
    lower:   0.1
    upper:   10.0
    initial: {PDD_melt_factor}
    fixed:   {PDD_melt_factor}
    active:  true

  recession_b_soil:
    description: "power-law recession exponent for soil zone [dimensionless]"
    lower:   1.5
    upper:   6.0
    initial: {recession_b_soil}
    fixed:   {recession_b_soil}
    active:  true

  recession_b_intermediate:
    description: "intermediate recession exponent fixed at 2.203 (Brutsaert-Nieber lower envelope)"
    lower:   1.0
    upper:   6.0
    initial: 2.203
    fixed:   2.203
    active:  false

  log__fdd_threshold:
    description: "log10 frozen-ground-index threshold [degC·day]; blocks infiltration when exceeded"
    lower:   0.0
    upper:   3.0
    initial: {log__fdd_threshold}
    fixed:   {log__fdd_threshold}
    active:  true

  snow_insulation_k:
    description: "snow insulation decay constant [mm⁻¹ SWE] — fixed at 0 (no insulation)"
    lower:   0.0
    upper:   0.5
    initial: 0.0
    fixed:   0.0
    active:  false

  et_scale:
    description: "global ET multiplier — inactive (water balance enforced globally)"
    lower:   0.5
    upper:   2.0
    initial: 1.0
    fixed:   1.0
    active:  false

  et_alpha:
    description: "ET partition fraction — fixed at 1.0 (all ET from soil)"
    lower:   0.01
    upper:   0.99
    initial: 1.0
    fixed:   1.0
    active:  false

  f_direct_runoff:
    description: "fast-bypass fraction of daily recharge — inactive"
    lower:   0.0
    upper:   0.5
    initial: 0.05
    fixed:   0.0
    active:  false

  baseflow_Q:
    description: "constant regional groundwater import [mm/day] — inactive"
    lower:   0.0
    upper:   0.5
    initial: 0.0
    fixed:   0.0
    active:  false

  log__routing_K:
    description: "log10 Nash-cascade storage time constant [days] — inactive"
    lower:   -1.0
    upper:    1.0
    initial:  0.0
    fixed:    0.0
    active:  false
"""

decade_starts = range(first_year, last_year + 1, 10)
for y in decade_starts:
    label = f'{y}-{y+9}'
    decade_dir = STUDY_DIR / 'decades' / label
    decade_dir.mkdir(parents=True, exist_ok=True)
    content = PARAMS_TEMPLATE.format(
        label=label,
        decade_start=f'{y}-01-01',
        decade_end=f'{y+9}-12-31',
        config_name=config_name,
        **params0,
    )
    (decade_dir / 'params.yml').write_text(content)
    print(f'  created decades/{label}/params.yml')

# ---------------------------------------------------------------------------
# 3. GRASS forcing-data pipeline scripts
#
# Three scripts are generated:
#   {name}_pipeline_download.sh  -- internet-required (v.in.waterdata + v.in.ghcn)
#   {name}_pipeline_compute.sh   -- CPU-intensive, no internet (IDW + db.out + cp)
#   {name}_pipeline.sh           -- combined (calls download then compute)
#
# The split allows the compute phase to run on HPC nodes (e.g. MSI SLURM)
# that have no outbound internet access.
# ---------------------------------------------------------------------------

EXAMPLES_DIR.mkdir(parents=True, exist_ok=True)

study_dir_abs    = STUDY_DIR.resolve()
examples_dir_abs = EXAMPLES_DIR.resolve()

# ── shared header ─────────────────────────────────────────────────────────────
_header_vars = f"""\
set -e
export GRASS_OVERWRITE=1

GAUGE={gauge}
START={forcing_start}
END={forcing_end}
OUTDIR="{examples_dir_abs}"
STUDY_DIR="{study_dir_abs}"
"""

# ── download script (internet-required) ──────────────────────────────────────
dl_script = EXAMPLES_DIR / f'{name}_pipeline_download.sh'
dl_script.write_text(f"""\
#!/bin/bash
# {title} — forcing-data download (internet-required)
#
# Downloads USGS discharge + basin polygon and GHCN station data into the
# GRASS mapset.  Run this on any machine with outbound internet access
# BEFORE running {name}_pipeline_compute.sh.
#
# Gauge  : USGS {gauge}
# Period : {forcing_start} to {forcing_end}
#
# One-time GRASS location setup (EPSG:{grass_epsg}):
#   grass -c EPSG:{grass_epsg} ~/grassdata/{grass_loc}/PERMANENT
#
# Run:
#   grass ~/grassdata/{grass_loc}/PERMANENT \\
#       --exec bash {examples_dir_abs}/{name}_pipeline_download.sh
#
# Required GRASS addons: v.in.waterdata  v.in.ghcn

{_header_vars}
# ── 1. Discharge time series + upstream basin polygon ─────────────────────────
v.in.waterdata \\
    sites=$GAUGE \\
    output=discharge_${{GAUGE}} \\
    basins={name}_basin \\
    start_date=$START \\
    end_date=$END \\
    -t

# ── 2. Region = basin extent (with padding for station search) ─────────────────
g.region vector={name}_basin res=1000 -a

# ── 3. GHCN station import ────────────────────────────────────────────────────
# sample= ensures the bbox expands until the basin centroid falls inside the
# convex hull of stations for each element, guaranteeing true spatial enclosure.
v.in.ghcn \\
    output=ghcn_stations \\
    elements=PRCP,TMAX,TMIN \\
    start_date=$START \\
    end_date=$END \\
    min_coverage=0.1 \\
    domain={name}_basin

echo "Download complete. Transfer the GRASS mapset to MSI, then run:"
echo "  {name}_pipeline_compute.sh"
""")
dl_script.chmod(dl_script.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP)
print(f'  created {dl_script}')

# ── compute script (no internet; MSI-submittable) ─────────────────────────────
compute_script = EXAMPLES_DIR / f'{name}_pipeline_compute.sh'
compute_script.write_text(f"""\
#!/bin/bash
# {title} — forcing-data compute (no internet required)
#
# Interpolates GHCN station data to basin-mean time series and exports to
# hydroRaVENS CSV + config YML.  Requires the GRASS mapset to already
# contain discharge_$GAUGE, {name}_basin, and ghcn_stations (run the
# download script first).
#
# On MSI, submit via: sbatch slurm/pipeline_job.sh {name}
#
# Required GRASS addons: v.interp.timeseries  db.out.hydroravens
#
# PROJ_DATA: conda environments may shadow the system PROJ data directory.
# The line below resolves it from the active conda env, falling back to the
# system path so GRASS commands work correctly on both laptops and HPC nodes.
PROJ_DATA="${{PROJ_DATA:-${{CONDA_PREFIX:+$CONDA_PREFIX/share/proj}}}}"; \\
    PROJ_DATA="${{PROJ_DATA:-/usr/share/proj}}"
export PROJ_DATA PROJ_LIB="$PROJ_DATA"

{_header_vars}
# ── 2. Region = basin extent (ensure it is set after mapset transfer) ──────────
g.region vector={name}_basin res=1000 -a

# ── 4. Basin-mean interpolation (IDW, area-weighted, min 2 stations) ──────────
for ELEM in PRCP TMAX TMIN; do
    v.interp.timeseries \\
        input=ghcn_stations \\
        element=$ELEM \\
        method=idw \\
        min_stations=2 \\
        domain={name}_basin \\
        start_date=$START \\
        end_date=$END \\
        -f
done

# ── 5. Export to hydroRaVENS format ──────────────────────────────────────────
db.out.hydroravens \\
    basin={name}_basin \\
    discharge_table=discharge_${{GAUGE}}_timeseries \\
    output="${{OUTDIR}}/{forcing_csv}" \\
    config="${{OUTDIR}}/{name}_config.yml"

# ── 6. Copy config to study directory ─────────────────────────────────────────
cp "${{OUTDIR}}/{name}_config.yml" "${{STUDY_DIR}}/{config_name}"
echo "Config copied → ${{STUDY_DIR}}/{config_name}"

echo ""
echo "Done. Files written:"
echo "  ${{OUTDIR}}/{forcing_csv}"
echo "  ${{OUTDIR}}/{name}_config.yml"
echo "  ${{STUDY_DIR}}/{config_name}"
echo ""
echo "Next: cd ${{STUDY_DIR}} && nohup bash run_all_decades.sh >run_all.log 2>&1 &"
""")
compute_script.chmod(compute_script.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP)
print(f'  created {compute_script}')

# ── combined pipeline (local use: runs download then compute) ─────────────────
pipeline_script = EXAMPLES_DIR / f'{name}_pipeline.sh'
pipeline_script.write_text(f"""\
#!/bin/bash
# {title} — full forcing-data pipeline (download + compute)
#
# Convenience wrapper: runs the download script then the compute script
# in sequence.  For HPC use, run the two scripts separately.
#
# Gauge  : USGS {gauge}
# Period : {forcing_start} to {forcing_end}
#
# One-time GRASS location setup (EPSG:{grass_epsg}):
#   grass -c EPSG:{grass_epsg} ~/grassdata/{grass_loc}/PERMANENT
#
# Run:
#   grass ~/grassdata/{grass_loc}/PERMANENT \\
#       --exec bash {examples_dir_abs}/{name}_pipeline.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

bash "$SCRIPT_DIR/{name}_pipeline_download.sh"
bash "$SCRIPT_DIR/{name}_pipeline_compute.sh"
""")
pipeline_script.chmod(pipeline_script.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP)
print(f'  created {pipeline_script}')

print(f"""
Setup complete for {title}.

Steps to run:
  1. Create GRASS location (once):
       grass -c EPSG:{grass_epsg} ~/grassdata/{grass_loc}/PERMANENT

  2a. Run full pipeline locally (download + compute):
       grass ~/grassdata/{grass_loc}/PERMANENT \\
           --exec bash {pipeline_script}

  2b. Or on MSI — run download script locally first:
       grass ~/grassdata/{grass_loc}/PERMANENT \\
           --exec bash {dl_script}
      Transfer GRASS mapset to MSI, then submit:
       sbatch slurm/pipeline_job.sh {name}

  3. Start decade calibrations:
       cd {STUDY_DIR} && nohup bash run_all_decades.sh >run_all.log 2>&1 &
""")
