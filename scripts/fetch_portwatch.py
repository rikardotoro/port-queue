"""Fetch daily container port calls from IMF PortWatch into the package examples.

Source: IMF PortWatch (https://portwatch.imf.org/), Daily Port Activity layer,
free ArcGIS REST, no key. The server clamps pages to 1000 rows.
"""
import csv
import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

EXAMPLES = Path(__file__).parent.parent / "src" / "port_queue" / "examples"
ENDPOINT = ("https://services9.arcgis.com/weJ1QsnbMYJlCHdG/ArcGIS/rest/services/"
            "Daily_Ports_Data/FeatureServer/0/query")
PORTS = {"shanghai": "port1188", "yangshan": "port2027", "ningbo": "port824"}
SPAN = ("2019-01-01", "2024-12-31")
PAGE = 1000


def fetch(portid: str) -> list[dict]:
    rows: list[dict] = []
    offset = 0
    while True:
        params = {
            "where": (f"portid='{portid}' AND date >= DATE '{SPAN[0]}' "
                      f"AND date <= DATE '{SPAN[1]}'"),
            "outFields": "date,portname,portcalls_container,portcalls",
            "orderByFields": "date",
            "resultOffset": offset,
            "resultRecordCount": PAGE,
            "f": "json",
        }
        with urlopen(ENDPOINT + "?" + urlencode(params)) as response:
            payload = json.load(response)
        features = payload.get("features", [])
        rows.extend(f["attributes"] for f in features)
        if len(features) < PAGE:
            return rows
        offset += PAGE


def main() -> int:
    EXAMPLES.mkdir(parents=True, exist_ok=True)
    for slug, portid in PORTS.items():
        rows = fetch(portid)
        path = EXAMPLES / f"{slug}.csv"
        with path.open("w", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["date", "portname", "portcalls_container", "portcalls"])
            for row in rows:
                writer.writerow([row["date"][:10], row["portname"],
                                 row["portcalls_container"], row["portcalls"]])
        print(f"{path.name}: {len(rows)} days")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
