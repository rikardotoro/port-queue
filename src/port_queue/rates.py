from dataclasses import dataclass

import numpy as np
import pandas as pd

from port_queue.detect import Closure
from port_queue.errors import InsufficientDataError, SaturatedPortError

RATE_WINDOW = 28
CAPACITY_WINDOW = 365


@dataclass(frozen=True)
class Rates:
    lam: float
    mu: float

    @property
    def rho(self) -> float:
        return self.lam / self.mu


def _history(series: pd.Series, at: pd.Timestamp, window: int,
             closures: list[Closure] | None) -> pd.Series:
    history = series.loc[:at - pd.Timedelta(days=1)].tail(window).dropna()
    for closure in closures or []:
        history = history[(history.index < closure.start) | (history.index > closure.end)]
    if len(history) < window // 2:
        raise InsufficientDataError(
            f"only {len(history)} usable days before {at.date()}; need {window // 2}"
        )
    return history


def arrival_rate(series: pd.Series, at: pd.Timestamp, window: int = RATE_WINDOW,
                 closures: list[Closure] | None = None) -> float:
    return float(_history(series, at, window, closures).median())


def capacity(series: pd.Series, at: pd.Timestamp, quantile: float = 0.98,
             window: int = CAPACITY_WINDOW,
             closures: list[Closure] | None = None) -> float:
    return float(np.quantile(_history(series, at, window, closures).values, quantile))


def utilisation(lam: float, mu: float) -> float:
    if mu <= lam:
        raise SaturatedPortError(
            f"arrivals {lam:.1f}/day meet capacity {mu:.1f}/day: at that capacity "
            "your port is not congested, it is closed. Raise --capacity-quantile."
        )
    return lam / mu


def measure(series: pd.Series, at: pd.Timestamp, quantile: float = 0.98,
            closures: list[Closure] | None = None) -> Rates:
    lam = arrival_rate(series, at, closures=closures)
    mu = capacity(series, at, quantile=quantile, closures=closures)
    utilisation(lam, mu)
    return Rates(lam, mu)
