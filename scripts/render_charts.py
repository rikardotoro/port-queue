"""Regenerate the README charts from the committed data so they can never drift.

Hand-rolled SVG (no plotting library); light and dark variants; palette
validated for GitHub's surfaces. Blue = the closure (what gets booked),
orange = the queue (what it costs).
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from port_queue.data import load_calls
from port_queue.detect import closures_from_calls, closures_from_tracks
from port_queue.rates import measure
from port_queue.report import find_closure, what_if_second_storm
from port_queue.sim import drain_closed_form, run_many
from port_queue.validate import compare

ROOT = Path(__file__).parent.parent
EXAMPLES = ROOT / "src" / "port_queue" / "examples"
OUT = ROOT / "docs" / "charts"
FONT = "system-ui, -apple-system, Segoe UI, sans-serif"
SEED = 0
TOKENS = {
    "light": {"closure": "#2a78d6", "queue": "#eb6834", "ink": "#0b0b0b", "ink2": "#52514e",
              "muted": "#898781", "grid": "#e1e0d9", "axis": "#c3c2b7", "real": "#b8b6ad",
              "band": "#fbe3d9"},
    "dark": {"closure": "#3987e5", "queue": "#d95926", "ink": "#ffffff", "ink2": "#c3c2b7",
             "muted": "#898781", "grid": "#2c2c2a", "axis": "#383835", "real": "#4a4945",
             "band": "#3d2a22"},
}


def _text(x, y, s, size, fill, anchor="start", weight="normal"):
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-family="{FONT}" font-size="{size}" '
            f'fill="{fill}" text-anchor="{anchor}" font-weight="{weight}">{s}</text>')


def _line(x1, y1, x2, y2, stroke, width=1.0, dash=None):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return (f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
            f'stroke="{stroke}" stroke-width="{width}"{d}/>')


def _path(points, color, width=2.0, dash=None):
    d = " L ".join(f"{x:.1f} {y:.1f}" for x, y in points)
    dd = f' stroke-dasharray="{dash}"' if dash else ""
    return (f'<path d="M {d}" fill="none" stroke="{color}" stroke-width="{width}" '
            f'stroke-linejoin="round"{dd}/>')


def _rect(x, y, w, h, fill, opacity=1.0):
    return f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" fill="{fill}" opacity="{opacity}"/>'


def _svg(width, height, body):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}" role="img">\n' + "\n".join(body) + "\n</svg>\n")


# ---------------------------------------------------------------- chart 1: surge
def chart_surge(check, closure, rates, storm, mode):
    T = TOKENS[mode]
    W, H = 760, 450
    L, R, top1, h1, top2, h2 = 56, 24, 64, 150, 300, 100
    frame = check.frame[check.frame["offset"].between(-3, 11)].reset_index(drop=True)
    n = len(frame)
    x = lambda i: L + (i + 0.5) * (W - L - R) / n
    bw = (W - L - R) / n * 0.62
    body = [_text(L, 24, f"Two days closed, a week of catching up — {storm.split()[-1]}, Shanghai, {closure.start:%b %Y}",
                  15, T["ink"], weight="bold"),
            _text(L, 44, "Daily container calls as a ratio to the trailing-28-day median. Real PortWatch calls in grey; "
                  "the two models are lines.", 11, T["muted"])]
    ymax = 1.5
    y1 = lambda v: top1 + h1 - min(v, ymax) / ymax * h1
    for v in (0.5, 1.0, 1.5):
        body.append(_line(L, y1(v), W - R, y1(v), T["grid"]))
        body.append(_text(L - 8, y1(v) + 4, f"{v:.1f}×", 10, T["muted"], anchor="end"))
    shut = frame[frame["offset"].between(0, closure.days - 1)]
    body.append(_rect(x(shut.index[0]) - bw, top1 - 6, x(shut.index[-1]) - x(shut.index[0]) + 2 * bw, h1 + 6, T["closure"], 0.10))
    body.append(_text(x(shut.index[0]) - bw + 4, top1 + 8, "port closed", 10, T["closure"], weight="bold"))
    for i, row in frame.iterrows():
        if pd.notna(row["real_ratio"]):
            body.append(_rect(x(i) - bw / 2, y1(row["real_ratio"]), bw, y1(0) - y1(row["real_ratio"]), T["real"]))
    body.append(_path([(x(i), y1(v)) for i, v in enumerate(frame["textbook_ratio"])], T["closure"], 2.2, dash="5 4"))
    body.append(_path([(x(i), y1(v)) for i, v in enumerate(frame["calibrated_ratio"])], T["queue"], 2.6))
    for i, row in frame.iterrows():
        body.append(_text(x(i), top1 + h1 + 14, f"{int(row['offset']):+d}", 10, T["muted"], anchor="middle"))
    body.append(_text(W - R, top1 + h1 + 14, "days", 10, T["muted"], anchor="start"))
    muifa = frame.index[frame["offset"] == 9]
    if len(muifa):
        i = muifa[0]
        body.append(_text(x(i) + bw / 2 + 2, y1(0.5) - 4, "Muifa arrives", 10, T["closure"], weight="bold"))
    lx, ly = L, top1 + h1 + 36
    body.append(_rect(lx, ly - 9, 12, 10, T["real"]))
    body.append(_text(lx + 18, ly, "real calls", 11, T["ink2"]))
    body.append(_line(lx + 90, ly - 4, lx + 116, ly - 4, T["closure"], 2.2, "5 4"))
    body.append(_text(lx + 122, ly, "textbook: every ship keeps coming", 11, T["ink2"]))
    body.append(_line(lx + 340, ly - 4, lx + 366, ly - 4, T["queue"], 2.6))
    body.append(_text(lx + 372, ly, f"calibrated: {check.recovered:.0%} keep coming, measured from the surge", 11, T["ink2"]))
    # panel 2: the queue
    q = check.calibrated
    start = 30 - 3
    qm = q.queue_mean[start:start + n]; qp = q.queue_p90[start:start + n]
    qmax = max(float(qp.max()), 1.0)
    y2 = lambda v: top2 + h2 - v / qmax * h2
    body.append(_text(L, top2 - 14, "Ships waiting at anchor — calibrated model, mean and 90th percentile of 200 runs", 11, T["muted"]))
    for v in (0, qmax / 2, qmax):
        body.append(_line(L, y2(v), W - R, y2(v), T["grid"]))
        body.append(_text(L - 8, y2(v) + 4, f"{v:.0f}", 10, T["muted"], anchor="end"))
    band = [(x(i), y2(v)) for i, v in enumerate(qp)] + [(x(i), y2(0)) for i in range(n - 1, -1, -1)]
    body.append(f'<path d="M {" L ".join(f"{a:.1f} {b:.1f}" for a, b in band)} Z" fill="{T["band"]}"/>')
    body.append(_path([(x(i), y2(v)) for i, v in enumerate(qm)], T["queue"], 2.6))
    drain = q.drain_days_mean
    body.append(_text(x(n - 1), y2(qmax * 0.55), f"clears {drain:.0f} days after reopening (closed form: {drain_closed_form(closure.days, rates.rho) * check.recovered:.0f})",
                      11, T["queue"], anchor="end", weight="bold"))
    for i, row in frame.iterrows():
        body.append(_text(x(i), top2 + h2 + 14, f"{int(row['offset']):+d}", 10, T["muted"], anchor="middle"))
    body.append(_text(L, H - 10, "Source: IMF PortWatch daily port calls (AIS-derived); NOAA IBTrACS for the storm; simulation in SimPy.", 10, T["muted"]))
    return _svg(W, H, body)


# ---------------------------------------------------------------- chart 2: multiplier
def chart_multiplier(points, rho_demo, mode):
    T = TOKENS[mode]
    W, H = 760, 340
    L, R, top, h = 56, 24, 56, 220
    rhos = np.linspace(0.5, 0.95, 91)
    ymax = 20
    x = lambda r: L + (r - 0.5) / 0.45 * (W - L - R)
    y = lambda v: top + h - min(v, ymax) / ymax * h
    body = [_text(L, 24, "Every closure day costs ρ ÷ (1 − ρ) queue days", 15, T["ink"], weight="bold"),
            _text(L, 44, "Days to clear per closed day against utilisation ρ = arrivals ÷ capacity. Line: closed form. Dots: SimPy, random arrivals.", 11, T["muted"])]
    for v in (0, 5, 10, 15, 20):
        body.append(_line(L, y(v), W - R, y(v), T["grid"]))
        body.append(_text(L - 8, y(v) + 4, f"{v}", 10, T["muted"], anchor="end"))
    for r in (0.5, 0.6, 0.7, 0.8, 0.9):
        body.append(_text(x(r), top + h + 16, f"{r:.0%}", 10, T["muted"], anchor="middle"))
    body.append(_text(W - R, top + h + 32, "utilisation before the storm", 10, T["muted"], anchor="end"))
    body.append(_path([(x(r), y(r / (1 - r))) for r in rhos], T["closure"], 2.2))
    for r, v in points:
        body.append(f'<circle cx="{x(r):.1f}" cy="{y(v):.1f}" r="5" fill="{T["queue"]}"/>')
    body.append(_line(x(rho_demo), top, x(rho_demo), top + h, T["queue"], 1.2, "4 3"))
    body.append(_text(x(rho_demo) - 6, top + h - 10, f"Shanghai before Hinnamnor: {rho_demo:.0%} → ×{rho_demo / (1 - rho_demo):.1f}", 11, T["queue"], anchor="end", weight="bold"))
    body.append(_text(L + 6, top + 14, "A closed day costs 1.5 queue days at 60% utilisation, 4 at 80%, 9 at 90%.", 11, T["closure"]))
    return _svg(W, H, body)


# ---------------------------------------------------------------- chart 3: double
def chart_double(gaps, ship_days, single, mode):
    T = TOKENS[mode]
    W, H = 760, 320
    L, R, top, h = 56, 24, 56, 200
    step = 150
    ymax = (int(max(max(ship_days), 2 * single) * 1.1 / step) + 1) * step
    x = lambda g: L + g / max(gaps) * (W - L - R)
    y = lambda v: top + h - v / ymax * h
    body = [_text(L, 24, "The same storm twice: what the gap between them does", 15, T["ink"], weight="bold"),
            _text(L, 44, "Ship-days spent waiting after two closures, against the days between them. Calibrated model, Shanghai rates.", 11, T["muted"])]
    for v in range(0, ymax + 1, step):
        body.append(_line(L, y(v), W - R, y(v), T["grid"]))
        body.append(_text(L - 8, y(v) + 4, f"{v}", 10, T["muted"], anchor="end"))
    for g in gaps:
        if g % 2 == 0:
            body.append(_text(x(g), top + h + 16, f"{g}", 10, T["muted"], anchor="middle"))
    body.append(_text(W - R, top + h + 32, "days between the two storms", 10, T["muted"], anchor="end"))
    body.append(_line(L, y(2 * single), W - R, y(2 * single), T["closure"], 1.6, "5 4"))
    body.append(_text(W - R, y(2 * single) - 6, f"two separate storms: {2 * single:.0f} ship-days", 11, T["closure"], anchor="end"))
    body.append(_line(L, y(single), W - R, y(single), T["axis"], 1.2, "2 3"))
    body.append(_text(W - R, y(single) - 6, f"one storm: {single:.0f}", 11, T["muted"], anchor="end"))
    body.append(_text(x(3.5), y(single) + 30, "from three days apart, the lull before the second storm", 11, T["queue"]))
    body.append(_text(x(3.5), y(single) + 44, "drains the first queue: cheaper than two separate storms", 11, T["queue"]))
    body.append(_path([(x(g), y(v)) for g, v in zip(gaps, ship_days)], T["queue"], 2.6))
    for g, v in zip(gaps, ship_days):
        body.append(f'<circle cx="{x(g):.1f}" cy="{y(v):.1f}" r="3.5" fill="{T["queue"]}"/>')
    worst = int(np.argmax(ship_days))
    body.append(_text(x(gaps[worst]) + 8, y(ship_days[worst]) - 8, f"back-to-back: {ship_days[worst]:.0f}", 11, T["queue"], weight="bold"))
    return _svg(W, H, body)


# ---------------------------------------------------------------- chart 4: atlas
def chart_atlas(series_by_port, storms, mode):
    T = TOKENS[mode]
    W = 760
    rows = list(series_by_port.items())
    row_h, top, L, R = 104, 76, 92, 24
    H = top + row_h * len(rows) + 40
    LABEL = {"LEKIMA": 0, "IN-FA": -1, "CHANTHU": 1, "HINNAMNOR": -1, "MUIFA": 1, "BEBINCA": 0}
    body = [_text(L, 24, "Every closure since 2019, three ports, one detector", 15, T["ink"], weight="bold"),
            _text(L, 44, "Container calls as a ratio to the trailing median. Orange: days at or below 25% of baseline.", 11, T["muted"]),
            _text(L, 60, "Blue marks: storms whose 34-kt wind field reached the port (NOAA IBTrACS); the named ones are in the README.", 11, T["muted"])]
    t0, t1 = pd.Timestamp("2019-01-01"), pd.Timestamp("2024-12-31")
    x = lambda t: L + (t - t0).days / (t1 - t0).days * (W - L - R)
    for k, (port, s) in enumerate(rows):
        y0 = top + k * row_h
        base = s.rolling(28, min_periods=14).median().shift(1)
        ratio = (s / base).clip(upper=1.6)
        yy = lambda v: y0 + 70 - v / 1.6 * 60
        body.append(_text(L - 8, y0 + 40, port, 12, T["ink"], anchor="end", weight="bold"))
        body.append(_line(L, yy(1.0), W - R, yy(1.0), T["grid"]))
        pts = [(x(t), yy(v)) for t, v in ratio.dropna().items()]
        body.append(_path(pts, T["real"], 0.9))
        for c in closures_from_calls(s):
            body.append(_rect(x(c.start) - 1, yy(1.6), max(2.0, x(c.end) - x(c.start) + 2), yy(0) - yy(1.6), T["queue"], 0.9))
        for st in closures_from_tracks(storms, port.split()[0].lower()):
            wind = float(storms[(storms["name"] == st.name) & (storms["port"] == port.split()[0].lower())]["max_wind"].max())
            body.append(f'<path d="M {x(st.start):.1f} {y0 + 6:.1f} l -4 -7 l 8 0 z" fill="{T["closure"]}"/>')
            if st.name in LABEL:
                side = LABEL[st.name]
                anchor = {0: "middle", -1: "end", 1: "start"}[side]
                body.append(_text(x(st.start) + 6 * side, y0 - 4, st.name.title(), 9, T["closure"], anchor=anchor))
        if k == len(rows) - 1:
            for yr in range(2019, 2025):
                body.append(_text(x(pd.Timestamp(f"{yr}-07-01")), y0 + row_h - 2, str(yr), 10, T["muted"], anchor="middle"))
    body.append(_text(L, H - 8, "Not every closure is a storm: fog, holidays and the 2022 lockdown show up too. The detector marks days, the storm file names them.", 10, T["muted"]))
    return _svg(W, H, body)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    storms = pd.read_csv(EXAMPLES / "storms.csv")
    shanghai = load_calls(EXAMPLES / "shanghai.csv")
    closure = find_closure(shanghai, pd.Timestamp("2022-09-04"), None)
    rates = measure(shanghai, closure.start, closures=[closure])
    check = compare(shanghai, closure, rates, runs=200, seed=SEED)
    points = []
    for rho in (0.6, 0.7, 0.8, 0.85, 0.9, 0.93):
        summary = run_many(rho * 40.0, 40.0, [(30, 31)], days=260, runs=100, seed=SEED)
        points.append((rho, summary.drain_days_mean / 2))
    gaps = list(range(0, 15))
    doubles = [what_if_second_storm(rates, closure, g, check.recovered, runs=100, seed=SEED) for g in gaps]
    ship_days = [d.double_ship_days for d in doubles]
    single = doubles[0].single_ship_days
    ports = {"Shanghai": shanghai, "Yangshan": load_calls(EXAMPLES / "yangshan.csv"),
             "Ningbo": load_calls(EXAMPLES / "ningbo.csv")}
    for mode in ("light", "dark"):
        (OUT / f"surge-{mode}.svg").write_text(chart_surge(check, closure, rates, "Typhoon Hinnamnor", mode))
        (OUT / f"multiplier-{mode}.svg").write_text(chart_multiplier(points, rates.rho, mode))
        (OUT / f"double-{mode}.svg").write_text(chart_double(gaps, ship_days, single, mode))
        (OUT / f"atlas-{mode}.svg").write_text(chart_atlas(ports, storms, mode))
        print(f"wrote {mode} charts")
    return 0


if __name__ == "__main__":
    sys.exit(main())
