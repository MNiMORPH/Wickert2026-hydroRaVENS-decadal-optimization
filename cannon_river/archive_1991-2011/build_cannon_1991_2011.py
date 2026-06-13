#!/usr/bin/env python3
"""
Build Cannon1991-2011Input.csv for hydroRaVENS 20-year calibration.

Sources
-------
Climate (P, T_max, T_min) : Dropbox/River_hydroclimate_1915_2018/cannon.csv
ET                         : Dropbox/CannonLivneh_Date_P_ET__version20210809_fixed.csv
Discharge                  : Dropbox/Papers/Submitted/ChannelWidth/DataComparisons/Cannon_Q_1991onwards.csv
Photoperiod                : computed via Forsythe et al. (1995), lat=44.0 N

Output columns match CannonTestInput.csv exactly.
Missing discharge days are left as NaN (hydroRaVENS skips them for scoring).
"""

import numpy as np
import pandas as pd
from pathlib import Path

# ── paths ────────────────────────────────────────────────────────────────────
DROPBOX = Path.home() / "Dropbox"
CLIMATE_FILE  = DROPBOX / "River_hydroclimate_1915_2018/cannon.csv"
ET_FILE       = DROPBOX / "CannonLivneh_Date_P_ET__version20210809_fixed.csv"
DISCHARGE_FILE = DROPBOX / "Papers/Submitted/ChannelWidth/DataComparisons/Cannon_Q_1991onwards.csv"
OUT_FILE = Path(__file__).parent / "Cannon1991-2011Input.csv"

START, END = "1991-10-01", "2011-12-31"
LAT = 44.0  # degrees N, centroid of Cannon River basin


# ── Forsythe et al. (1995) photoperiod ──────────────────────────────────────
def photoperiod_forsythe(doy, lat_deg):
    """Day-length [hr] after Forsythe et al. (1995), Ecological Modelling 80:87-95."""
    lat = np.radians(lat_deg)
    theta = 0.2163108 + 2.0 * np.arctan(0.9671396 * np.tan(0.00860 * (doy - 186.0)))
    delta = np.arcsin(0.39795 * np.cos(theta))
    arg = (np.sin(np.radians(0.8333)) + np.sin(lat) * np.sin(delta)) / (
        np.cos(lat) * np.cos(delta)
    )
    arg = np.clip(arg, -1.0, 1.0)
    return 24.0 - (24.0 / np.pi) * np.arccos(arg)


# ── load climate ─────────────────────────────────────────────────────────────
clim = pd.read_csv(CLIMATE_FILE, parse_dates=["Date"], index_col="Date")
clim = clim.loc[START:END, [
    "Precipitation [mm/day]",
    "Maximum temperature [degC]",
    "Minimum temperature [degC]",
]].copy()
clim["Mean Temperature [C]"]    = (clim["Maximum temperature [degC]"] +
                                    clim["Minimum temperature [degC]"]) / 2.0
clim["Minimum Temperature [C]"] = clim["Minimum temperature [degC]"]
clim["Maximum Temperature [C]"] = clim["Maximum temperature [degC]"]
clim.drop(columns=["Maximum temperature [degC]", "Minimum temperature [degC]"],
          inplace=True)
clim.rename(columns={"Precipitation [mm/day]": "Precipitation [mm/day]"},
            inplace=True)

# ── load ET ──────────────────────────────────────────────────────────────────
et = pd.read_csv(ET_FILE, parse_dates=["Date"], index_col="Date")
et = et.loc[START:END, ["Evapotranspiration [mm/day]"]].copy()

# ── load discharge ────────────────────────────────────────────────────────────
q_raw = pd.read_csv(DISCHARGE_FILE, parse_dates=["Timestamp"])
q_raw.index = pd.DatetimeIndex(q_raw["Timestamp"])
q_raw = q_raw.loc[START:END, ["Discharge [cfs]"]].copy()
q_raw["Discharge [m^3/s]"] = q_raw["Discharge [cfs]"] * 0.0283168
q = q_raw[["Discharge [m^3/s]"]]

# ── photoperiod ───────────────────────────────────────────────────────────────
dates = pd.date_range(START, END, freq="D")
doy = dates.day_of_year.values.astype(float)
photo = pd.Series(photoperiod_forsythe(doy, LAT), index=dates, name="Photoperiod [hr]")

# ── merge on full daily index ─────────────────────────────────────────────────
df = pd.DataFrame(index=dates)
df = df.join(clim).join(et).join(q).join(photo)

# check alignment
n_missing_q = df["Discharge [m^3/s]"].isna().sum()
print(f"Rows: {len(df)}  |  Missing discharge: {n_missing_q}")

# ── reorder columns ───────────────────────────────────────────────────────────
df = df[[
    "Precipitation [mm/day]",
    "Discharge [m^3/s]",
    "Mean Temperature [C]",
    "Minimum Temperature [C]",
    "Maximum Temperature [C]",
    "Photoperiod [hr]",
    "Evapotranspiration [mm/day]",
]]

# ── write with YYYY.MM.DD date column ─────────────────────────────────────────
df.index.name = "Date"
df.index = df.index.strftime("%Y.%m.%d")
df.to_csv(OUT_FILE)
print(f"Wrote {OUT_FILE}")
