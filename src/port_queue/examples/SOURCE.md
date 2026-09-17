# Demo data sources

Nothing in this folder is synthetic.

- **`shanghai.csv`, `yangshan.csv`, `ningbo.csv` — real daily port calls.**
  IMF PortWatch, Daily Port Activity layer (https://portwatch.imf.org/), ports
  `port1188` Shanghai, `port2027` Shanghai (Yangshan), `port824` Ningbo,
  2019-01-01 → 2024-12-31, columns `date, portname, portcalls_container,
  portcalls`. Fetched by [`scripts/fetch_portwatch.py`](../../../scripts/fetch_portwatch.py)
  from the free ArcGIS REST endpoint (no key). PortWatch derives calls from
  AIS positions, so a "call" is a ship observed arriving at the port, not a
  terminal record; the tool treats container calls as ships served.
- **`storms.csv` — real storm tracks.** NOAA NCEI IBTrACS v04r01, West
  Pacific basin (US Government work, public domain), filtered by
  [`scripts/fetch_ibtracs.py`](../../../scripts/fetch_ibtracs.py) to the fixes
  where each demo port lay inside the storm's largest 34-kt wind radius (or
  within 100 km of the centre when radii are missing), seasons 2019 onward.
  One row per storm and port: first and last fix at the port, closest
  approach in km, peak wind in knots.
- **What is measured, what is modelled.** Arrival rate and capacity are
  measured from the calls. The queue itself is simulated; the README shows
  the simulated surge next to the real one so you can judge the fit.
