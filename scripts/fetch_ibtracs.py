"""Filter NOAA IBTrACS best tracks to the storms that reached the demo ports.

Source: NOAA NCEI IBTrACS v04r01, West Pacific basin CSV (US Government work,
public domain). A storm is "at the port" on every fix where the port lies inside
the storm's largest 34-kt wind radius, or within 100 km of the centre when the
radii are missing.
"""
import io
from pathlib import Path
from urllib.request import urlopen

import numpy as np
import pandas as pd

RAW = Path(__file__).parent.parent / "data" / "raw" / "ibtracs.WP.list.v04r01.csv"
EXAMPLES = Path(__file__).parent.parent / "src" / "port_queue" / "examples"
URL = ("https://www.ncei.noaa.gov/data/international-best-track-archive-for-"
       "climate-stewardship-ibtracs/v04r01/access/csv/ibtracs.WP.list.v04r01.csv")
PORTS = {"shanghai": (31.23, 121.49), "yangshan": (30.63, 122.06), "ningbo": (29.93, 121.85)}
RADII = ["USA_R34_NE", "USA_R34_SE", "USA_R34_SW", "USA_R34_NW"]
NM_TO_KM = 1.852
FALLBACK_KM = 100.0
FIRST_SEASON = 2019


def haversine_km(lat, lon, lat0, lon0):
    lat, lon, lat0, lon0 = map(np.radians, (lat, lon, lat0, lon0))
    a = np.sin((lat - lat0) / 2) ** 2 + np.cos(lat0) * np.cos(lat) * np.sin((lon - lon0) / 2) ** 2
    return 2 * 6371.0 * np.arcsin(np.sqrt(a))


def load_tracks() -> pd.DataFrame:
    if not RAW.exists():
        RAW.parent.mkdir(parents=True, exist_ok=True)
        with urlopen(URL) as response:
            RAW.write_bytes(response.read())
    columns = ["SID", "SEASON", "NAME", "ISO_TIME", "LAT", "LON", "USA_WIND", *RADII]
    frame = pd.read_csv(RAW, skiprows=[1], usecols=columns, low_memory=False)
    frame = frame[frame["SEASON"].astype(int) >= FIRST_SEASON].copy()
    for column in ["LAT", "LON", "USA_WIND", *RADII]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame["time"] = pd.to_datetime(frame["ISO_TIME"])
    return frame


def hits_for(frame: pd.DataFrame, port: str, lat0: float, lon0: float) -> pd.DataFrame:
    distance = haversine_km(frame["LAT"], frame["LON"], lat0, lon0)
    radius = frame[RADII].max(axis=1) * NM_TO_KM
    inside = (distance <= radius.fillna(0)) | (distance <= FALLBACK_KM)
    hit = frame[inside].assign(dist_km=distance[inside])
    grouped = hit.groupby(["SID", "NAME", "SEASON"]).agg(
        first=("time", "min"), last=("time", "max"),
        min_km=("dist_km", "min"), max_wind=("USA_WIND", "max"),
    ).reset_index()
    grouped.insert(0, "port", port)
    return grouped


def main() -> int:
    frame = load_tracks()
    parts = [hits_for(frame, port, lat, lon) for port, (lat, lon) in PORTS.items()]
    storms = pd.concat(parts).sort_values(["port", "first"])
    storms.columns = [c.lower() for c in storms.columns]
    storms["first"] = storms["first"].dt.strftime("%Y-%m-%d %H:%M")
    storms["last"] = storms["last"].dt.strftime("%Y-%m-%d %H:%M")
    storms["min_km"] = storms["min_km"].round(1)
    out = EXAMPLES / "storms.csv"
    storms.to_csv(out, index=False)
    print(f"{out.name}: {len(storms)} port-storm hits")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
