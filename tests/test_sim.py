import numpy as np
import pytest

from port_queue.sim import drain_closed_form, run_many, simulate

LAM, MU = 30.0, 40.0          # rho 0.75, multiplier 3


def test_closed_form_multiplier():
    assert drain_closed_form(2, 0.75) == pytest.approx(6.0)
    assert drain_closed_form(2, 0.9) == pytest.approx(18.0)
    assert drain_closed_form(1, 0.5) == pytest.approx(1.0)


def test_no_closure_means_no_queue():
    result = simulate(LAM, MU, [], days=120, seed=1)
    assert result.queue[30:].mean() < 1.0
    assert abs(result.berthings[30:].sum() - result.arrivals[30:].sum()) < 0.05 * result.arrivals[30:].sum()
    assert result.drain_days == 0


def test_deterministic_closure_reproduces_the_closed_form():
    result = simulate(LAM, MU, [(50, 51)], days=120, deterministic=True)
    assert result.berthings[50] == 0 and result.berthings[51] == 0
    assert abs(result.drain_days - drain_closed_form(2, LAM / MU)) <= 1
    assert result.congested_days >= result.drain_days + 2


def test_multiplier_exceeds_one_when_busy():
    busy = simulate(LAM, 33.0, [(50, 51)], days=200, deterministic=True)   # rho 0.91
    calm = simulate(LAM, 60.0, [(50, 51)], days=200, deterministic=True)   # rho 0.5
    assert busy.drain_days > 2 * 2
    assert calm.drain_days <= 2


def test_poisson_mode_is_seeded_and_reproducible():
    a = simulate(LAM, MU, [(50, 51)], days=120, seed=7)
    b = simulate(LAM, MU, [(50, 51)], days=120, seed=7)
    c = simulate(LAM, MU, [(50, 51)], days=120, seed=8)
    assert np.array_equal(a.queue, b.queue)
    assert not np.array_equal(a.queue, c.queue)


def test_second_storm_inside_the_drain_window_hurts_ships_not_the_calendar():
    single = simulate(LAM, MU, [(50, 51)], days=200, deterministic=True)
    inside = simulate(LAM, MU, [(50, 51), (54, 55)], days=200, deterministic=True)
    apart = simulate(LAM, MU, [(50, 51), (120, 121)], days=200, deterministic=True)
    assert inside.extra_ship_days > 2 * single.extra_ship_days * 1.2
    assert inside.max_wait > single.max_wait * 1.5
    assert abs(apart.extra_ship_days - 2 * single.extra_ship_days) < 0.1 * single.extra_ship_days
    gap_days = 2
    expected = 2 * drain_closed_form(2, LAM / MU) - gap_days
    assert abs(inside.drain_days - expected) <= 1


def test_run_many_summarises_the_runs():
    summary = run_many(LAM, MU, [(50, 51)], days=120, runs=20, seed=3)
    assert summary.queue_mean.shape == (120,)
    assert summary.queue_p90[52] >= summary.queue_mean[52]
    assert summary.drain_days_mean > 2
    assert summary.runs == 20
