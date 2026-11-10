"""Energy (Wh) over a time window from the power logs in power/.

GPU: <session>-gpu.csv from gpu_power.py: unix time, ..., s73 = board power in W (identified in Phase 0).
CPU: <session>-cpu.csv from typeperf: local time with the UTC offset in the header ("(420)" = UTC-7), package power
     in mW from the RAPL counter.
Energy = trapezoid integral of each series over [t0, t1], in Wh. Other parts of the PC (RAM, disks, fans, the power
supply's own loss) are not measured.
"""
from __future__ import annotations

import csv, datetime, functools, pathlib, re

P = pathlib.Path(r"E:\strata-tests\coding-bench\power")


@functools.lru_cache(maxsize=None)
def gpu_series(session: str):
    out = []
    with open(P / f"{session}-gpu.csv") as f:
        for r in csv.DictReader(f):
            try:
                out.append((float(r["time"]), float(r["s73"])))
            except (KeyError, ValueError):
                pass
    return out


@functools.lru_cache(maxsize=None)
def cpu_series(session: str):
    out = []
    path = P / f"{session}-cpu.csv"
    with open(path, encoding="utf-8", errors="replace") as f:
        rows = list(csv.reader(f))
    m = re.search(r"\((-?\d+)\)\s*$", rows[0][0])
    offset_min = int(m.group(1)) if m else 420            # minutes behind UTC, as Windows reports it
    for r in rows[1:]:
        try:
            local = datetime.datetime.strptime(r[0], "%m/%d/%Y %H:%M:%S.%f")
            unix = (local + datetime.timedelta(minutes=offset_min)).replace(tzinfo=datetime.timezone.utc).timestamp()
            out.append((unix, float(r[1]) / 1000.0))
        except (ValueError, IndexError):
            pass
    return out


def integrate(series, t0: float, t1: float):
    """Wh over [t0, t1] by the trapezoid rule; None if the log does not cover the window."""
    pts = [(t, w) for t, w in series if t0 - 5 <= t <= t1 + 5]
    if len(pts) < 2 or pts[0][0] > t0 + 10 or pts[-1][0] < t1 - 10:
        return None
    joules = 0.0
    for (ta, wa), (tb, wb) in zip(pts, pts[1:]):
        a, b = max(ta, t0), min(tb, t1)
        if b > a:
            joules += (wa + wb) / 2 * (b - a)
    return joules / 3600.0


def mean_w(series, t0, t1):
    pts = [w for t, w in series if t0 <= t <= t1]
    return sum(pts) / len(pts) if pts else None


def sessions():
    return sorted({p.name[:-8] for p in P.glob("*-gpu.csv")})


def find_session(t0: float, t1: float) -> str | None:
    for s in sessions():
        g = gpu_series(s)
        if g and g[0][0] <= t0 + 10 and g[-1][0] >= t1 - 10:
            return s
    return None


def window(t0: float, t1: float, session: str | None = None) -> dict:
    s = session or find_session(t0, t1)
    if s is None:
        return {"session": None, "gpu_wh": None, "cpu_wh": None, "total_wh": None}
    g, c = integrate(gpu_series(s), t0, t1), integrate(cpu_series(s), t0, t1)
    return {"session": s, "gpu_wh": g, "cpu_wh": c, "total_wh": (g or 0) + (c or 0) if g is not None else None,
            "gpu_mean_w": mean_w(gpu_series(s), t0, t1), "cpu_mean_w": mean_w(cpu_series(s), t0, t1)}


if __name__ == "__main__":
    for s in sessions():
        g, c = gpu_series(s), cpu_series(s)
        if g:
            print(s, f"{(g[-1][0] - g[0][0]) / 60:.1f} min", f"GPU {integrate(g, g[0][0], g[-1][0]) or 0:.1f} Wh",
                  f"CPU {integrate(c, g[0][0], g[-1][0]) or 0:.1f} Wh" if c else "CPU -")
