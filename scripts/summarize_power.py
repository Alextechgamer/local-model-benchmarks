"""Summarise the power logs written by gpu_power.py (GPU) and Windows typeperf (CPU RAPL counter).

usage: python summarize_power.py <log_dir> [<run_name> <t0_epoch> <t1_epoch>] ...

<log_dir> holds gpu.csv (from `gpu_power.py log`) and cpu.csv (from
`typeperf "\\Energy Meter(rapl_package0_pkg)\\Power" -si 2 -o cpu.csv`).
Prints idle/busy medians for every GPU sensor column, the CPU package power, and the
energy (Wh) used between each run's start and end time.

Column s73 is the 7900 XT's board power in watts on this driver (idle ~12 W, busy ~277 W,
max ~324 W); the RAPL counter is read as milliwatts. The log's UTC offset for cpu.csv
timestamps is set by TZ_HOURS below (the logs here were taken in Pacific Daylight Time).
"""
import bisect
import csv
import datetime
import statistics as st
import sys

TZ_HOURS = -7
GPU_POWER_COL = "s73"


def load(log_dir):
    gpu = list(csv.DictReader(open(f"{log_dir}/gpu.csv")))
    tz = datetime.timezone(datetime.timedelta(hours=TZ_HOURS))
    cpu = []
    for row in list(csv.reader(open(f"{log_dir}/cpu.csv")))[1:]:
        try:
            ts = datetime.datetime.strptime(row[0], "%m/%d/%Y %H:%M:%S.%f").replace(tzinfo=tz).timestamp()
            cpu.append((ts, float(row[1]) / 1000))  # mW -> W
        except (ValueError, IndexError):
            pass
    return gpu, cpu


def energy_wh(samples):
    return sum((samples[k + 1][0] - samples[k][0]) * samples[k][1] for k in range(len(samples) - 1)) / 3600


def main():
    log_dir, rest = sys.argv[1], sys.argv[2:]
    gpu, cpu = load(log_dir)
    t = [float(r["time"]) for r in gpu]
    act = [float(r["gpu_activity_pct"]) for r in gpu]
    print(f"{log_dir}: {len(gpu)} samples over {(t[-1] - t[0]) / 60:.1f} min, mean GPU activity {st.mean(act):.1f}%")
    for col in [c for c in gpu[0] if c.startswith("s")]:
        v = [float(r[col]) for r in gpu]
        busy = [x for x, a in zip(v, act) if a >= 50]
        idle = [x for x, a in zip(v, act) if a < 5]
        if max(v) > 0:
            print(f"  {col}: idle median {st.median(idle) if idle else 'n/a'}, busy median {st.median(busy) if busy else 'n/a'}, max {max(v)}")
    p = sorted(w for _, w in cpu)
    print(f"  CPU package: median {st.median(p):.1f} W, p10 {p[len(p) // 10]:.1f}, p90 {p[9 * len(p) // 10]:.1f}, max {p[-1]:.1f}")

    gw = [float(r[GPU_POWER_COL]) for r in gpu]
    for i in range(0, len(rest), 3):
        name, a, b = rest[i], float(rest[i + 1]), float(rest[i + 2])
        lo, hi = bisect.bisect_left(t, a), bisect.bisect_right(t, b)
        if hi - lo < 10:
            print(f"  {name}: not covered by this log")
            continue
        g = list(zip(t[lo:hi], gw[lo:hi]))
        c = [(ts, w) for ts, w in cpu if a <= ts <= b]
        print(f"  {name}: {(b - a) / 60:.1f} min, coverage {(t[hi - 1] - t[lo]) / (b - a):.2f}, "
              f"GPU mean {st.mean(gw[lo:hi]):.0f} W, activity {st.mean(act[lo:hi]):.0f}%, "
              f"CPU mean {st.mean(w for _, w in c):.0f} W, GPU {energy_wh(g):.0f} Wh, CPU {energy_wh(c):.0f} Wh")


if __name__ == "__main__":
    main()
