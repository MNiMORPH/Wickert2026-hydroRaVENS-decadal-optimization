#!/usr/bin/env python3
"""
Status tracker for all watershed calibration directories.

Usage (from Wickert2026-MNiShed-decadal-optimization/):
    python status.py
    python status.py --verbose
"""

import argparse
from pathlib import Path
import yaml

parser = argparse.ArgumentParser()
parser.add_argument('--verbose', '-v', action='store_true')
args = parser.parse_args()

CONFIGS = sorted(Path('watershed_configs').glob('*.yml'))

STAGES = [
    'config',       # watershed_configs/*.yml exists
    'dir_setup',    # study dir + scripts + decades/ exist
    'forcing',      # forcing CSV exists
    'calib_started',# at least one decades/*/runs/ has a run
    'calib_done',   # summary.csv exists
]

STAGE_LABELS = {
    'config':         'config written',
    'dir_setup':      'dir set up',
    'forcing':        'forcing ready',
    'calib_started':  'calibration started',
    'calib_done':     'calibration complete',
}

ICONS = {True: '✓', False: '·'}

rows = []
for cfg_path in CONFIGS:
    with open(cfg_path) as f:
        cfg = yaml.safe_load(f)

    name         = cfg['name']
    title        = cfg['title']
    gauge        = cfg['gauge']
    config_name  = cfg['forcing']['config_name']
    csv_name     = cfg['forcing']['csv_name']
    forcing_dir  = Path('forcing') / name
    study_dir    = Path(name)

    status = {}

    # Stage 1: config exists (trivially true if we're reading it)
    status['config'] = cfg_path.exists()

    # Stage 2: study directory set up (has scripts + at least one decade params.yml)
    status['dir_setup'] = (
        (study_dir / 'run.sh').exists()
        and any((study_dir / 'decades').glob('*/params.yml'))
    )

    # Stage 3: config template present in study dir (copied there at end of pipeline).
    # The CSV path is absolute and embedded inside the config template.
    config_tmpl = study_dir / config_name
    status['forcing'] = config_tmpl.exists()

    # Stage 4: at least one completed run
    decade_dirs  = list((study_dir / 'decades').glob('*/')) if (study_dir / 'decades').exists() else []
    n_decades    = len(decade_dirs)
    n_with_runs  = sum(1 for d in decade_dirs if any((d / 'runs').glob('*/')))
    status['calib_started'] = n_with_runs > 0

    # Stage 5: summary.csv present
    status['calib_done'] = (study_dir / 'summary.csv').exists()

    rows.append((title, gauge, name, status, n_decades, n_with_runs))

# Determine column widths
title_w = max(len(r[0]) for r in rows) + 2
gauge_w = 12

print(f"\n{'Watershed':<{title_w}} {'Gauge':<{gauge_w}} "
      + "  ".join(f"{STAGE_LABELS[s]:<18}" for s in STAGES))
print('-' * (title_w + gauge_w + 2 + 18 * len(STAGES) + 2 * (len(STAGES) - 1)))

for title, gauge, name, status, n_decades, n_with_runs in rows:
    icons = "  ".join(
        f"{ICONS[status[s]]:<18}" for s in STAGES
    )
    print(f"{title:<{title_w}} {gauge:<{gauge_w}} {icons}")
    if args.verbose and status['dir_setup']:
        print(f"  {'':>{title_w}}  decades: {n_with_runs}/{n_decades} with runs")

print()

# Summary counts
ready_for_pipeline = [r for r in rows if r[3]['dir_setup'] and not r[3]['forcing']]
ready_for_calib    = [r for r in rows if r[3]['forcing']   and not r[3]['calib_done']]
complete           = [r for r in rows if r[3]['calib_done']]

if ready_for_pipeline:
    print("Needs forcing pipeline:")
    for title, gauge, name, status, *_ in ready_for_pipeline:
        if status['calib_done']:
            continue   # already finished; skip
        cfg = yaml.safe_load(open(f'watershed_configs/{name}.yml'))
        epsg = cfg.get('grass_epsg', 32615)
        loc  = cfg.get('grass_location', name)
        pipe = Path('forcing') / name / f'{name}_pipeline.sh'
        print(f"  PROJ_DATA=/usr/share/proj PROJ_LIB=/usr/share/proj \\")
        print(f"  grass -c EPSG:{epsg} ~/grassdata/{loc}/PERMANENT \\")
        print(f"      --exec bash {pipe}")

if ready_for_calib:
    print("\nReady to calibrate (forcing data present):")
    for title, gauge, name, *_ in ready_for_calib:
        print(f"  cd {name} && nohup bash run_all_decades.sh >run_all.log 2>&1 &")

if complete:
    print(f"\nCalibration complete ({len(complete)}):")
    for title, gauge, name, *_ in complete:
        print(f"  {title}  ({name}/summary.csv)")

print()
