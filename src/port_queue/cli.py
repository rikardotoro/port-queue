import json
from pathlib import Path
from typing import Annotated

import pandas as pd
import typer
from rich.console import Console

from port_queue.data import load_calls
from port_queue.errors import PortQueueError
from port_queue.report import EXAMPLES, analyse, render, to_dict

app = typer.Typer(add_completion=False,
                  help="A port closure is short. The queue after it is not.")
console = Console(soft_wrap=True)
DEMO_EVENT = "2022-09-04"


@app.command()
def main(
    data: Annotated[Path | None, typer.Option(help="Daily port-calls CSV.")] = None,
    demo: Annotated[bool, typer.Option(help="Use the bundled real Shanghai data.")] = False,
    port: Annotated[str | None, typer.Option(help="Port name to filter (multi-port files).")] = None,
    event: Annotated[str | None, typer.Option(help="A date inside the closure to analyse.")] = None,
    closures: Annotated[str | None, typer.Option(help="Explicit closure days, comma-separated.")] = None,
    storms: Annotated[Path | None, typer.Option(help="IBTrACS hits CSV to name the storm.")] = None,
    capacity_quantile: Annotated[float, typer.Option(help="Quantile of daily calls taken as capacity.")] = 0.98,
    runs: Annotated[int, typer.Option(help="Monte Carlo runs per model.")] = 200,
    seed: Annotated[int, typer.Option()] = 0,
    second_storm_after: Annotated[int, typer.Option(help="Gap for the what-if second storm; 0 disables.")] = 4,
    map_: Annotated[list[str] | None, typer.Option("--map", help="canonical=column")] = None,
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    if demo:
        data = data or EXAMPLES / "shanghai.csv"
        storms = storms or EXAMPLES / "storms.csv"
        port = port or "shanghai"
        event = event or DEMO_EVENT
    if data is None:
        raise typer.BadParameter("provide --data or --demo")
    overrides = dict(item.split("=", 1) for item in (map_ or []))
    try:
        series = load_calls(data, overrides or None, port=port)
        explicit = [pd.Timestamp(d.strip()) for d in closures.split(",")] if closures else None
        result = analyse(
            series, port or data.stem, event=pd.Timestamp(event) if event else None,
            explicit=explicit, storms=pd.read_csv(storms) if storms else None,
            quantile=capacity_quantile, runs=runs, seed=seed,
            second_storm_after=second_storm_after or None,
        )
    except PortQueueError as error:
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(code=1) from error
    if as_json:
        print(json.dumps(to_dict(result), indent=2))
    else:
        render(result, console)


if __name__ == "__main__":
    app()
