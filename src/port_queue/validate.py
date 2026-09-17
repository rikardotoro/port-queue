from dataclasses import dataclass

import numpy as np
import pandas as pd

from port_queue.detect import Closure
from port_queue.rates import RATE_WINDOW, Rates
from port_queue.sim import LEAD_DAYS, Summary, run_many

PRE_DAYS = 30
POST_DAYS = 14
FIT_WINDOW = (-1, 10)


@dataclass(frozen=True)
class Check:
    frame: pd.DataFrame
    baseline: float
    dip_deficit: float
    surge_excess: float
    recovered: float
    rmse_textbook: float
    rmse_calibrated: float
    textbook: Summary
    calibrated: Summary


def _ratio_window(summary: Summary, lam: float, closure_days: int) -> np.ndarray:
    start = PRE_DAYS - LEAD_DAYS - 2
    stop = PRE_DAYS + closure_days + POST_DAYS
    return summary.berthings_mean[start:stop] / lam


def recovered_fraction(series: pd.Series, closure: Closure, baseline: float,
                       post_days: int = POST_DAYS) -> tuple[float, float, float]:
    dip = series.loc[closure.start - pd.Timedelta(days=LEAD_DAYS): closure.end]
    surge = series.loc[closure.end + pd.Timedelta(days=1):
                       closure.end + pd.Timedelta(days=post_days)]
    deficit = float((baseline - dip).clip(lower=0).sum())
    excess = float((surge - baseline).clip(lower=0).sum())
    return deficit, excess, (excess / deficit if deficit else 0.0)


def compare(series: pd.Series, closure: Closure, rates: Rates, runs: int = 200,
            seed: int = 0) -> Check:
    baseline = float(series.loc[:closure.start - pd.Timedelta(days=1)]
                     .tail(RATE_WINDOW).median())
    deficit, excess, recovered = recovered_fraction(series, closure, baseline)
    closures = [(PRE_DAYS, PRE_DAYS + closure.days - 1)]
    days = PRE_DAYS + closure.days + POST_DAYS
    textbook = run_many(rates.lam, rates.mu, closures, days, runs=runs, seed=seed)
    calibrated = run_many(rates.lam, rates.mu, closures, days, runs=runs, seed=seed,
                          arrival_factor=recovered)
    offsets = np.arange(-LEAD_DAYS - 2, closure.days + POST_DAYS)
    dates = [closure.start + pd.Timedelta(days=int(o)) for o in offsets]
    real = series.reindex(dates).values / baseline
    frame = pd.DataFrame({
        "date": dates, "offset": offsets, "real_ratio": real,
        "textbook_ratio": _ratio_window(textbook, rates.lam, closure.days),
        "calibrated_ratio": _ratio_window(calibrated, rates.lam, closure.days),
    })
    fit = frame[frame["offset"].between(*FIT_WINDOW)].dropna()
    rmse = lambda column: float(np.sqrt(((fit[column] - fit["real_ratio"]) ** 2).mean()))
    return Check(frame, baseline, deficit, excess, recovered,
                 rmse("textbook_ratio"), rmse("calibrated_ratio"), textbook, calibrated)
