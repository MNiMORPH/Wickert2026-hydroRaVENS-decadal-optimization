#!/bin/bash
exec grass ~/grassdata/CannonRiver/PERMANENT --exec bash "$(dirname "$0")/forcing/cannon_river/cannon_river_pipeline_compute.sh"
