from pathlib import Path

import pandas as pd

from port_queue.errors import InvalidDataError, MissingColumnError

ALIASES = {
    "date": ["date", "day", "time", "arrival_date"],
    "calls": ["calls", "portcalls_container", "portcalls", "arrivals", "vessels", "ships"],
}
PORT_COLUMNS = ["portname", "port", "port_name"]


def _find(columns: list[str], canonical: str, overrides: dict[str, str] | None) -> str:
    if overrides and canonical in overrides:
        return overrides[canonical]
    lowered = {c.lower(): c for c in columns}
    for alias in ALIASES[canonical]:
        if alias in lowered:
            return lowered[alias]
    raise MissingColumnError(
        f"no '{canonical}' column found; tried {ALIASES[canonical]} "
        f"(use --map {canonical}=<your column>)"
    )


def load_calls(path: Path, overrides: dict[str, str] | None = None,
               port: str | None = None) -> pd.Series:
    frame = pd.read_csv(path)
    columns = list(frame.columns)
    date_col = _find(columns, "date", overrides)
    calls_col = _find(columns, "calls", overrides)
    port_col = next((c for c in columns if c.lower() in PORT_COLUMNS), None)
    if port_col is not None:
        names = frame[port_col].astype(str)
        if port is not None:
            frame = frame[names.str.lower().str.contains(port.lower())]
            if frame.empty:
                raise InvalidDataError(f"no rows for port '{port}' in {port_col}")
        elif names.nunique() > 1:
            raise InvalidDataError(
                f"file holds several ports ({', '.join(sorted(names.unique())[:5])}); "
                "pick one with --port"
            )
    dates = pd.to_datetime(frame[date_col], errors="coerce")
    calls = pd.to_numeric(frame[calls_col], errors="coerce")
    for kind, values in (("date", dates), ("calls", calls)):
        bad = values.isna() & frame[date_col if kind == "date" else calls_col].notna()
        if bad.any():
            row = int(frame.index[bad][0]) + 2
            raise InvalidDataError(f"unreadable {kind} at row {row}")
    if (calls < 0).any():
        row = int(frame.index[calls < 0][0]) + 2
        raise InvalidDataError(f"negative calls at row {row}")
    series = pd.Series(calls.values, index=dates.dt.normalize().values, name="calls")
    series = series.groupby(level=0).sum()
    full = pd.date_range(series.index.min(), series.index.max(), freq="D")
    return series.reindex(full).astype(float).rename_axis("date")
