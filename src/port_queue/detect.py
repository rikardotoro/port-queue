from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class Closure:
    start: pd.Timestamp
    end: pd.Timestamp
    source: str
    name: str | None = None

    @property
    def days(self) -> int:
        return int((self.end - self.start).days) + 1


def closures_from_calls(series: pd.Series, threshold: float = 0.25,
                        window: int = 28) -> list[Closure]:
    baseline = series.rolling(window, min_periods=window // 2).median().shift(1)
    dead = (series <= threshold * baseline) & baseline.notna() & series.notna()
    closures: list[Closure] = []
    start = prev = None
    for day, flag in dead.items():
        if flag and start is None:
            start = prev = day
        elif flag:
            prev = day
        elif start is not None:
            closures.append(Closure(start, prev, "calls"))
            start = None
    if start is not None:
        closures.append(Closure(start, prev, "calls"))
    return closures


def closures_from_tracks(storms: pd.DataFrame, port: str) -> list[Closure]:
    rows = storms[storms["port"].str.lower() == port.lower()]
    closures = []
    for _, row in rows.iterrows():
        first = pd.Timestamp(row["first"]).normalize()
        last = pd.Timestamp(row["last"]).normalize()
        closures.append(Closure(first, last, "ibtracs", str(row["name"])))
    return sorted(closures, key=lambda c: c.start)
