#!/bin/bash
# Clean previous Dakota output, then run the calibration.
# Run from cannon_river/: bash run.sh

DAKOTA=/home/awickert/anaconda3/envs/dakota-env/bin/dakota

rm -rf out dakota.dat dakota.out dakota.rst fort.13 LHS_*.out

$DAKOTA -i dakota.in -o dakota.out
