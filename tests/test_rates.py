from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from port_queue.data import load_calls
from port_queue.detect import Closure
from port_queue.errors import InsufficientDataError, SaturatedPortError
from port_queue.rates import arrival_rate, capacity, measure, utilisation

EXAMPLES = Path(__file__).parent.parent / "src" / "port_queue" / "examples"


def flat(value, days=400, start="2023-01-01"):
    return pd.Series(float(value), index=pd.date_range(start, periods=days, freq="D"))


def test_arrival_rate_is_the_trailing_median_before_the_day():
    series = flat(30)
    series.iloc[-1] = 300.0
    assert arrival_rate(series, series.index[-1]) == 30.0


def test_arrival_rate_skips_closure_days():
    series = flat(30)
    at = series.index[-1]
    series.iloc[-15:-1] = 0.0
    closure = Closure(series.index[-15], series.index[-2], "calls")
    assert arrival_rate(series, at, closures=[closure]) == 30.0
    assert arrival_rate(series, at) < 30.0


def test_capacity_is_a_high_quantile_of_the_prior_year():
    series = flat(30)
    series.iloc[-40:-1] = 40.0
    assert capacity(series, series.index[-1], quantile=0.95) == 40.0


def test_utilisation_refuses_a_saturated_port():
    assert utilisation(30, 40) == pytest.approx(0.75)
    with pytest.raises(SaturatedPortError, match="not congested, it is closed"):
        utilisation(40, 40)


def test_too_little_history_is_refused():
    with pytest.raises(InsufficientDataError):
        arrival_rate(flat(30, days=5), pd.Timestamp("2023-01-05"))


def test_shanghai_before_muifa_is_a_busy_but_not_saturated_port():
    rates = measure(load_calls(EXAMPLES / "shanghai.csv"), pd.Timestamp("2022-09-13"))
    assert 0.6 <= rates.rho <= 0.95
    assert rates.lam < rates.mu
