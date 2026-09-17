from pathlib import Path

import pandas as pd

from port_queue.data import load_calls
from port_queue.detect import Closure, closures_from_calls, closures_from_tracks

EXAMPLES = Path(__file__).parent.parent / "src" / "port_queue" / "examples"
NAMED = {"IN-FA": "2021-07-25", "CHANTHU": "2021-09-13", "HINNAMNOR": "2022-09-04",
         "MUIFA": "2022-09-14", "BEBINCA": "2024-09-15"}


def covering(closures, day):
    day = pd.Timestamp(day)
    return [c for c in closures if c.start <= day <= c.end]


def test_adjacent_dead_days_merge_into_one_closure():
    idx = pd.date_range("2024-01-01", periods=60, freq="D")
    values = [30.0] * 60
    values[40] = 0.0
    values[41] = 2.0
    closures = closures_from_calls(pd.Series(values, index=idx))
    assert len(closures) == 1
    assert closures[0].days == 2
    assert closures[0].source == "calls"


def test_shanghai_calls_reveal_the_named_typhoons():
    closures = closures_from_calls(load_calls(EXAMPLES / "shanghai.csv"))
    for name, day in NAMED.items():
        assert covering(closures, day), name


def test_tracks_give_muifa_at_shanghai():
    storms = pd.read_csv(EXAMPLES / "storms.csv")
    closures = closures_from_tracks(storms, "shanghai")
    muifa = [c for c in closures if c.name == "MUIFA"][0]
    assert muifa.start == pd.Timestamp("2022-09-14")
    assert muifa.source == "ibtracs"


def test_both_detectors_agree_within_a_day():
    calls = closures_from_calls(load_calls(EXAMPLES / "shanghai.csv"))
    tracks = closures_from_tracks(pd.read_csv(EXAMPLES / "storms.csv"), "shanghai")
    for name in NAMED:
        storm = [c for c in tracks if c.name == name][0]
        window = (storm.start - pd.Timedelta(days=1), storm.end + pd.Timedelta(days=1))
        assert any(window[0] <= c.start <= window[1] or window[0] <= c.end <= window[1]
                   for c in calls), name


def test_closure_is_a_value_object():
    closure = Closure(pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-02"), "calls")
    assert closure.days == 2
    assert closure.name is None
