"""Read the Radeon's power sensors through AMD's driver library (atiadlxx.dll, the PMLog interface).

usage: python gpu_power.py dump            print every supported sensor once
       python gpu_power.py log <csv> [s]   append time, sensor values every s seconds (default 2) until killed
"""
import ctypes, sys, time

MAX = 256
NAMES = {1: "gfx_clk_mhz", 2: "mem_clk_mhz", 8: "temp_edge_c", 14: "fan_rpm", 15: "fan_pct", 16: "soc_mv", 17: "soc_power_w",
         18: "soc_current_a", 19: "gpu_activity_pct", 20: "mem_activity_pct", 21: "gfx_mv", 23: "asic_power_w",
         27: "temp_hotspot_c", 30: "gfx_power_w", 31: "gfx_current_a", 33: "cpu_power_w"}


class Sensor(ctypes.Structure):
    _fields_ = [("supported", ctypes.c_int), ("value", ctypes.c_int)]


class PMLog(ctypes.Structure):
    _fields_ = [("size", ctypes.c_int), ("sensors", Sensor * MAX)]


ALLOC = ctypes.CFUNCTYPE(ctypes.c_void_p, ctypes.c_int)
_keep = []


def _alloc(n):
    buf = ctypes.create_string_buffer(n); _keep.append(buf)
    return ctypes.addressof(buf)


def open_adl():
    adl = ctypes.WinDLL("atiadlxx.dll")
    ctx = ctypes.c_void_p()
    cb = ALLOC(_alloc); _keep.append(cb)
    rc = adl.ADL2_Main_Control_Create(cb, 1, ctypes.byref(ctx))
    if rc != 0:
        raise SystemExit(f"ADL2_Main_Control_Create failed: {rc}")
    adl.ADL2_New_QueryPMLogData_Get.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(PMLog)]
    n = ctypes.c_int()
    adl.ADL2_Adapter_NumberOfAdapters_Get(ctx, ctypes.byref(n))
    for i in range(max(n.value, 8)):                 # the first adapter index that answers with sensors
        d = PMLog()
        if adl.ADL2_New_QueryPMLogData_Get(ctx, i, ctypes.byref(d)) == 0 and any(s.supported for s in d.sensors):
            return adl, ctx, i
    raise SystemExit("no adapter answered the PMLog query")


def read(adl, ctx, idx) -> dict[int, int]:
    d = PMLog()
    adl.ADL2_New_QueryPMLogData_Get(ctx, idx, ctypes.byref(d))
    return {i: s.value for i, s in enumerate(d.sensors) if s.supported}


if __name__ == "__main__":
    adl, ctx, idx = open_adl()
    if sys.argv[1] == "dump":
        print("adapter index", idx)
        for i, v in read(adl, ctx, idx).items():
            print(f"  {i:3d} {NAMES.get(i, '?'):18s} {v}")
    else:
        step = float(sys.argv[3]) if len(sys.argv) > 3 else 2.0
        keys = sorted(read(adl, ctx, idx))
        with open(sys.argv[2], "a", encoding="utf-8") as f:
            f.write("time," + ",".join(NAMES.get(k, f"s{k}") for k in keys) + "\n")
            while True:
                r = read(adl, ctx, idx)
                f.write(f"{time.time():.1f}," + ",".join(str(r.get(k, "")) for k in keys) + "\n"); f.flush()
                time.sleep(step)
