from pathlib import Path

import pandas as pd

from port_queue.data import load_calls
from port_queue.detect import closures_from_calls
from port_queue.rates import measure
from port_queue.validate import compare

EXAMPLES = Path(__file__).parent.parent / "src" / "port_queue" / "examples"


def hinnamnor():
    series = load_calls(EXAMPLES / "shanghai.csv")
    closure = [c for c in closures_from_calls(series)
               if c.start <= pd.Timestamp("2022-09-04") <= c.end][0]
    return series, closure


def test_hinnamnor_only_half_the_ships_came_back():
    series, closure = hinnamnor()
    check = compare(series, closure, measure(series, closure.start), runs=40, seed=1)
    assert 0.3 <= check.recovered <= 0.8
    assert check.dip_deficit > check.surge_excess > 0


def test_calibrated_model_fits_the_port_better_than_the_textbook():
    series, closure = hinnamnor()
    check = compare(series, closure, measure(series, closure.start), runs=40, seed=1)
    assert check.rmse_calibrated < check.rmse_textbook
    frame = check.frame
    assert {"date", "real_ratio", "textbook_ratio", "calibrated_ratio"} <= set(frame.columns)
    assert (frame.loc[frame["offset"].between(0, closure.days - 1), "real_ratio"] < 0.3).all()
