import json
from pathlib import Path

import pandas as pd
from typer.testing import CliRunner

from port_queue.cli import app

EXAMPLES = Path(__file__).parent.parent / "src" / "port_queue" / "examples"
runner = CliRunner()


def test_demo_runs_and_tells_the_story():
    result = runner.invoke(app, ["--demo", "--runs", "10"])
    assert result.exit_code == 0, result.output
    out = result.output.lower()
    assert "closed" in out and "queue" in out and "queue days" in out
    assert "hinnamnor" in out
    assert "the cost is the queue" in out


def test_json_has_the_numbers():
    result = runner.invoke(app, ["--demo", "--runs", "10", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["closure"]["days"] == 2
    assert 0 < payload["utilisation"] < 1
    assert payload["multiplier"] > 1
    assert payload["calibrated"]["rmse"] < payload["textbook"]["rmse"]
    assert payload["double_storm"]["double_ship_days"] > payload["double_storm"]["single_ship_days"]


def test_explicit_closures_are_honoured():
    result = runner.invoke(app, ["--data", str(EXAMPLES / "ningbo.csv"), "--closures",
                                 "2022-09-13,2022-09-14", "--runs", "5", "--json",
                                 "--second-storm-after", "0"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["closure"] == {"start": "2022-09-13", "end": "2022-09-14", "days": 2, "source": "given"}
    assert "double_storm" not in payload


def test_saturated_port_is_refused_with_the_joke(tmp_path):
    days = pd.date_range("2023-01-01", periods=400, freq="D")
    frame = pd.DataFrame({"date": days, "calls": 30})
    frame.loc[380:381, "calls"] = 0
    path = tmp_path / "flat.csv"
    frame.to_csv(path, index=False)
    result = runner.invoke(app, ["--data", str(path), "--event", "2024-01-16", "--runs", "5"])
    assert result.exit_code == 1
    assert "not congested, it is closed" in " ".join(result.output.split())


def test_unknown_event_names_the_nearest_closure():
    result = runner.invoke(app, ["--demo", "--event", "2022-06-01", "--runs", "5"])
    assert result.exit_code == 1
    assert "nearest is" in result.output
