from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
from rich.console import Console
from rich.table import Table

from port_queue.detect import Closure, closures_from_calls, closures_from_tracks
from port_queue.errors import InvalidDataError
from port_queue.rates import Rates, measure
from port_queue.sim import Summary, drain_closed_form, run_many
from port_queue.validate import POST_DAYS, PRE_DAYS, Check, compare

EXAMPLES = Path(__file__).parent / "examples"


@dataclass(frozen=True)
class DoubleStorm:
    gap_days: int
    single_drain: float
    double_drain: float
    single_ship_days: float
    double_ship_days: float
    single_max_wait: float
    double_max_wait: float


@dataclass(frozen=True)
class Result:
    port: str
    closure: Closure
    storm: str | None
    rates: Rates
    closed_form: float
    check: Check
    double: DoubleStorm | None
    runs: int
    notes: list[str] = field(default_factory=list)


def find_closure(series: pd.Series, event: pd.Timestamp | None,
                 explicit: list[pd.Timestamp] | None) -> Closure:
    if explicit:
        return Closure(min(explicit), max(explicit), "given")
    closures = closures_from_calls(series)
    if not closures:
        raise InvalidDataError("no closure days found in this history")
    if event is None:
        return max(closures, key=lambda c: (c.days, c.start))
    hits = [c for c in closures if c.start - pd.Timedelta(days=1) <= event <= c.end + pd.Timedelta(days=1)]
    if not hits:
        nearest = min(closures, key=lambda c: abs((c.start - event).days))
        raise InvalidDataError(
            f"no closure around {event.date()}; nearest is {nearest.start.date()} "
            f"({nearest.days} day{'s' if nearest.days > 1 else ''})"
        )
    return hits[0]


def storm_name(closure: Closure, storms: pd.DataFrame | None, port: str) -> str | None:
    if storms is None:
        return None
    for track in closures_from_tracks(storms, port):
        if track.start - pd.Timedelta(days=1) <= closure.start <= track.end + pd.Timedelta(days=1):
            return track.name
    return None


def what_if_second_storm(rates: Rates, closure: Closure, gap_days: int,
                         arrival_factor: float, runs: int, seed: int) -> DoubleStorm:
    first = (PRE_DAYS, PRE_DAYS + closure.days - 1)
    second_start = first[1] + 1 + gap_days
    second = (second_start, second_start + closure.days - 1)
    days = second[1] + 1 + 2 * POST_DAYS + 20
    single = run_many(rates.lam, rates.mu, [first], days, runs=runs, seed=seed,
                      arrival_factor=arrival_factor)
    double = run_many(rates.lam, rates.mu, [first, second], days, runs=runs, seed=seed,
                      arrival_factor=arrival_factor)
    return DoubleStorm(gap_days, single.drain_days_mean, double.drain_days_mean,
                       single.extra_ship_days_mean, double.extra_ship_days_mean,
                       single.max_wait_mean, double.max_wait_mean)


def analyse(series: pd.Series, port: str, event: pd.Timestamp | None = None,
            explicit: list[pd.Timestamp] | None = None, storms: pd.DataFrame | None = None,
            quantile: float = 0.98, runs: int = 200, seed: int = 0,
            second_storm_after: int | None = 4) -> Result:
    closure = find_closure(series, event, explicit)
    rates = measure(series, closure.start, quantile=quantile, closures=[closure])
    check = compare(series, closure, rates, runs=runs, seed=seed)
    double = None
    if second_storm_after is not None:
        double = what_if_second_storm(rates, closure, second_storm_after,
                                      check.recovered, runs, seed)
    return Result(port, closure, storm_name(closure, storms, port), rates,
                  drain_closed_form(closure.days, rates.rho), check, double, runs)


def to_dict(result: Result) -> dict:
    c, r, k = result.closure, result.rates, result.check
    out = {
        "port": result.port,
        "storm": result.storm,
        "closure": {"start": c.start.date().isoformat(), "end": c.end.date().isoformat(),
                    "days": c.days, "source": c.source},
        "arrivals_per_day": round(r.lam, 2),
        "capacity_per_day": round(r.mu, 2),
        "utilisation": round(r.rho, 3),
        "multiplier": round(r.rho / (1 - r.rho), 2),
        "closed_form_drain_days": round(result.closed_form, 1),
        "textbook": {"drain_days_mean": round(k.textbook.drain_days_mean, 1),
                     "drain_days_p90": round(k.textbook.drain_days_p90, 1),
                     "rmse": round(k.rmse_textbook, 3)},
        "recovered_fraction": round(k.recovered, 3),
        "dip_deficit_ships": round(k.dip_deficit, 1),
        "surge_excess_ships": round(k.surge_excess, 1),
        "calibrated": {"drain_days_mean": round(k.calibrated.drain_days_mean, 1),
                       "drain_days_p90": round(k.calibrated.drain_days_p90, 1),
                       "rmse": round(k.rmse_calibrated, 3),
                       "max_wait_days": round(k.calibrated.max_wait_mean, 2),
                       "extra_ship_days": round(k.calibrated.extra_ship_days_mean, 1)},
        "runs": result.runs,
    }
    if result.double:
        d = result.double
        out["double_storm"] = {
            "gap_days": d.gap_days,
            "single_drain_days": round(d.single_drain, 1),
            "double_drain_days": round(d.double_drain, 1),
            "single_ship_days": round(d.single_ship_days, 1),
            "double_ship_days": round(d.double_ship_days, 1),
            "single_max_wait": round(d.single_max_wait, 2),
            "double_max_wait": round(d.double_max_wait, 2),
            "ship_days_ratio": round(d.double_ship_days / max(d.single_ship_days, 1e-9), 2),
        }
    return out


def render(result: Result, console: Console | None = None) -> None:
    console = console or Console()
    c, r, k = result.closure, result.rates, result.check
    storm = f"  ·  typhoon {result.storm.title()}" if result.storm else ""
    console.print(f"[bold]port-queue[/bold] — {result.port.title()}, closed "
                  f"{c.start.date()} → {c.end.date()} ({c.days} day{'s' if c.days > 1 else ''}){storm}")
    console.print(f"Before the storm: {r.lam:.1f} ships/day arriving, {r.mu:.1f}/day capacity "
                  f"→ utilisation {r.rho:.0%}.")
    console.print()
    console.print(f"[bold]The closure is {c.days} day{'s' if c.days > 1 else ''}. "
                  f"The queue is not.[/bold]")
    console.print(f"  Closed form: {result.closed_form:.1f} days to clear "
                  f"(every closure day costs {r.rho / (1 - r.rho):.1f} queue days at {r.rho:.0%}).")
    console.print(f"  Simulated, ships keep arriving: {k.textbook.drain_days_mean:.1f} days "
                  f"(P90 {k.textbook.drain_days_p90:.0f}, {result.runs} runs).")
    console.print()
    console.print("[bold]Checked against the port[/bold]")
    console.print(f"  {k.dip_deficit:.0f} ship-calls went missing around the closure; "
                  f"{k.surge_excess:.0f} came back as a surge within {POST_DAYS} days "
                  f"→ recovered {k.recovered:.0%}.")
    console.print(f"  Calibrated (only {k.recovered:.0%} keep coming): "
                  f"{k.calibrated.drain_days_mean:.1f} days to clear, longest wait "
                  f"{k.calibrated.max_wait_mean:.1f} days, fit {k.rmse_calibrated:.2f} "
                  f"vs textbook {k.rmse_textbook:.2f} (RMSE of the ratio to baseline).")
    table = Table(show_header=True, header_style="bold", box=None, pad_edge=False)
    table.add_column("day"); table.add_column("real", justify="right")
    table.add_column("textbook", justify="right"); table.add_column("calibrated", justify="right")
    window = k.frame[k.frame["offset"].between(-1, 8)]
    for _, row in window.iterrows():
        real = "—" if pd.isna(row["real_ratio"]) else f"{row['real_ratio']:.2f}"
        table.add_row(f"{int(row['offset']):+d}", real, f"{row['textbook_ratio']:.2f}",
                      f"{row['calibrated_ratio']:.2f}")
    console.print(table)
    if result.double:
        d = result.double
        console.print()
        console.print(f"[bold]What if the same storm came back {d.gap_days} days later[/bold]")
        ratio = d.double_ship_days / max(d.single_ship_days, 1e-9)
        console.print(f"  Queue after the second storm: {d.double_drain:.1f} days to clear "
                      f"(one storm: {d.single_drain:.1f}).")
        console.print(f"  Ships: {d.double_ship_days:.0f} ship-days waiting vs {d.single_ship_days:.0f} "
                      f"for one storm — ×{ratio:.1f}, {'more' if ratio > 2 else 'less'} than two "
                      f"separate storms; longest wait {d.double_max_wait:.1f} vs {d.single_max_wait:.1f} days.")
    console.print()
    console.print("[italic]The storm is the closure. The cost is the queue.[/italic]")
