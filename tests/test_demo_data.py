from pathlib import Path

import pandas as pd

EXAMPLES = Path(__file__).parent.parent / "src" / "port_queue" / "examples"


def test_three_ports_have_six_years_of_days():
    for slug in ["shanghai", "yangshan", "ningbo"]:
        frame = pd.read_csv(EXAMPLES / f"{slug}.csv")
        assert len(frame) >= 2000
        assert set(frame.columns) >= {"date", "portcalls_container"}


def test_examples_stay_small():
    total = sum(p.stat().st_size for p in EXAMPLES.iterdir())
    assert total < 1_000_000


def test_storms_include_the_named_typhoons():
    storms = pd.read_csv(EXAMPLES / "storms.csv")
    shanghai = set(storms[storms["port"] == "shanghai"]["name"])
    assert {"MUIFA", "BEBINCA", "IN-FA"} <= shanghai
