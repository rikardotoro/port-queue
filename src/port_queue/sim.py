from dataclasses import dataclass

import numpy as np
import simpy

SETTLED_DAYS = 3


@dataclass(frozen=True)
class SimResult:
    queue: np.ndarray
    berthings: np.ndarray
    arrivals: np.ndarray
    waits: np.ndarray
    threshold: float
    first_start: int | None
    last_end: int | None
    drain_days: int
    congested_days: int
    extra_ship_days: float
    max_wait: float


@dataclass(frozen=True)
class Summary:
    queue_mean: np.ndarray
    queue_p90: np.ndarray
    berthings_mean: np.ndarray
    drain_days_mean: float
    drain_days_p90: float
    congested_days_mean: float
    extra_ship_days_mean: float
    max_wait_mean: float
    runs: int


def drain_closed_form(closure_days: float, rho: float) -> float:
    return closure_days * rho / (1.0 - rho)


def _closed_set(closures: list[tuple[int, int]]) -> set[int]:
    days: set[int] = set()
    for start, end in closures:
        days.update(range(start, end + 1))
    return days


def simulate(lam: float, mu: float, closures: list[tuple[int, int]], days: int,
             seed: int = 0, deterministic: bool = False,
             berths: int | None = None) -> SimResult:
    rng = np.random.default_rng(seed)
    capacity = berths or max(1, int(round(mu)))
    service = capacity / mu
    closed = _closed_set(closures)
    env = simpy.Environment()
    berth = simpy.Resource(env, capacity=capacity)
    state = {"open": True, "reopened": env.event(), "waiting": 0}
    queue = np.zeros(days)
    berthings = np.zeros(days)
    arrivals = np.zeros(days)
    waits: list[float] = []

    def ship():
        arrived = env.now
        state["waiting"] += 1
        while True:
            while not state["open"]:
                yield state["reopened"]
            request = berth.request()
            yield request
            if state["open"]:
                break
            berth.release(request)
        state["waiting"] -= 1
        waits.append(env.now - arrived)
        day = int(env.now)
        if day < days:
            berthings[day] += 1
        yield env.timeout(service)
        berth.release(request)

    def source():
        while True:
            gap = 1.0 / lam if deterministic else rng.exponential(1.0 / lam)
            yield env.timeout(gap)
            day = int(env.now)
            if day < days:
                arrivals[day] += 1
            env.process(ship())

    def gate():
        for day in range(days):
            should_open = day not in closed
            if should_open and not state["open"]:
                state["open"] = True
                state["reopened"].succeed()
                state["reopened"] = env.event()
            elif not should_open and state["open"]:
                state["open"] = False
            yield env.timeout(1.0)

    def clock():
        for day in range(days):
            yield env.timeout(1.0)
            queue[day] = state["waiting"]

    env.process(source())
    env.process(gate())
    env.process(clock())
    env.run(until=days + 1e-9)

    starts = [s for s, _ in closures]
    ends = [e for _, e in closures]
    first_start = min(starts) if starts else None
    last_end = max(ends) if ends else None
    if first_start is not None and first_start > 0:
        threshold = max(1.0, float(np.quantile(queue[:first_start], 0.95)))
    else:
        threshold = 1.0
    drain_days = congested_days = 0
    if last_end is not None:
        cleared = days
        for day in range(last_end + 1, days - SETTLED_DAYS + 1):
            if (queue[day:day + SETTLED_DAYS] <= threshold).all():
                cleared = day
                break
        drain_days = cleared - (last_end + 1)
        congested_days = cleared - first_start
    waits_array = np.array(waits) if waits else np.zeros(0)
    return SimResult(
        queue=queue, berthings=berthings, arrivals=arrivals, waits=waits_array,
        threshold=threshold, first_start=first_start, last_end=last_end,
        drain_days=int(drain_days), congested_days=int(congested_days),
        extra_ship_days=float(waits_array.sum()),
        max_wait=float(waits_array.max()) if len(waits_array) else 0.0,
    )


def run_many(lam: float, mu: float, closures: list[tuple[int, int]], days: int,
             runs: int = 200, seed: int = 0) -> Summary:
    results = [simulate(lam, mu, closures, days, seed=seed + i) for i in range(runs)]
    queues = np.stack([r.queue for r in results])
    berthings = np.stack([r.berthings for r in results])
    drains = np.array([r.drain_days for r in results], dtype=float)
    return Summary(
        queue_mean=queues.mean(axis=0),
        queue_p90=np.quantile(queues, 0.9, axis=0),
        berthings_mean=berthings.mean(axis=0),
        drain_days_mean=float(drains.mean()),
        drain_days_p90=float(np.quantile(drains, 0.9)),
        congested_days_mean=float(np.mean([r.congested_days for r in results])),
        extra_ship_days_mean=float(np.mean([r.extra_ship_days for r in results])),
        max_wait_mean=float(np.mean([r.max_wait for r in results])),
        runs=runs,
    )
