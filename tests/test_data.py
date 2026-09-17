from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from port_queue.data import load_calls
from port_queue.errors import InvalidDataError, MissingColumnError

EXAMPLES = Path(__file__).parent.parent / "src" / "port_queue" / "examples"


def write(tmp_path, text):
    path = tmp_path / "calls.csv"
    path.write_text(text)
    return path


def test_canonical_columns(tmp_path):
    series = load_calls(write(tmp_path, "date,calls\n2024-01-01,10\n2024-01-02,12\n"))
    assert list(series.values) == [10, 12]
    assert isinstance(series.index, pd.DatetimeIndex)


def test_portwatch_aliases_are_detected(tmp_path):
    series = load_calls(write(tmp_path, "Date,portcalls_container\n2024-01-01,10\n"))
    assert series.iloc[0] == 10


def test_missing_days_become_nan_not_zero(tmp_path):
    series = load_calls(write(tmp_path, "date,calls\n2024-01-01,10\n2024-01-03,12\n"))
    assert len(series) == 3
    assert np.isnan(series.loc["2024-01-02"])


def test_missing_calls_column_names_the_options(tmp_path):
    with pytest.raises(MissingColumnError, match="calls"):
        load_calls(write(tmp_path, "date,ships\n2024-01-01,10\n"))


def test_bad_value_names_the_row(tmp_path):
    with pytest.raises(InvalidDataError, match="row 2"):
        load_calls(write(tmp_path, "date,calls\n2024-01-01,10\n2024-01-02,many\n"))


def test_port_filter_on_multi_port_file(tmp_path):
    text = ("date,portname,calls\n2024-01-01,Shanghai,10\n2024-01-01,Ningbo,7\n")
    assert load_calls(write(tmp_path, text), port="ningbo").iloc[0] == 7
    with pytest.raises(InvalidDataError, match="several ports"):
        load_calls(write(tmp_path, text))


def test_demo_file_loads_daily():
    series = load_calls(EXAMPLES / "shanghai.csv")
    assert len(series) == 2192
    assert series.index.freq == "D"
