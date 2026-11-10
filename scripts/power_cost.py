"""Electricity and purchase cost of running coding models locally, compared with cloud API runs.

usage: python power_cost.py            prints the tables and writes results/hardware-power-cost.json

Every input is listed below with where it came from. Measured numbers come from this repo's own
local runs (results/local-power.json); the other machines use published figures, which are
ranges because nobody measured them on this exact workload.
"""
import json
import os

RATE = 0.104             # $/kWh, Washington residential average, April 2026 (US EIA via voltflow.net)
RATE_HIGH = 0.15         # sensitivity case for a pricier utility or plan
REST_OF_PC_W = 60        # motherboard, RAM, SSD, fans: an estimate, not measured
PSU_EFFICIENCY = 0.90    # an estimate for a typical Gold-rated supply at ~450 W

# Measured: GPU board + CPU package, from results/local-power.json
MEASURED_RUNS = {
    "Flash-Next IQ1_M, claude-code run 2": {"minutes": 20.2, "gpu_wh": 92, "cpu_wh": 37},
    "Qwen 3.8 27B IQ4_XS, opencode": {"minutes": 62.5, "gpu_wh": 288, "cpu_wh": 75},
}

# API cost per working page, from results/token-cost-table.json
API_PAGES = {"DeepSeek V4.1 Flash (API)": 0.095, "GPT-6 Luna #3 (API)": 0.043}

# Machines: watts under sustained LLM load (low, high) and purchase price.
MACHINES = [
    {"machine": "Current PC (RX 7900 XT + Ryzen 9 5900X)", "price": 0,
     "w": ((273 + 109), (273 + 109 + REST_OF_PC_W) / PSU_EFFICIENCY),
     "basis": "measured GPU+CPU during run 2 (low); plus estimated rest-of-PC and PSU loss (high)"},
    {"machine": "Strix Halo 128 GB (BOSGAME M5 / Ryzen AI Halo class)", "price": 3599,
     "w": (140, 170), "basis": "ServeTheHome Framework Desktop review, same chip: 140-170 W under load"},
    {"machine": "Mac Studio M3 Ultra 256 GB", "price": 7999 + 79,
     "w": (190, 270), "basis": "reported under 200 W running DeepSeek R1 (Dave2D via TechRadar); Apple's max 270 W"},
    {"machine": "Mac Studio M5 Ultra 256 GB", "price": 9499,
     "w": (200, 385), "basis": "no measured LLM figure found; Apple's max 385 W (512 GB config)"},
]


def money(x, places=2):
    return f"${x:,.{places}f}"


def main():
    out = {"rate_per_kwh": RATE, "rate_high_per_kwh": RATE_HIGH,
           "assumptions": {"rest_of_pc_w": REST_OF_PC_W, "psu_efficiency": PSU_EFFICIENCY},
           "per_page": [], "per_machine": []}

    print(f"Per working page on the current PC, at ${RATE}/kWh")
    for name, r in MEASURED_RUNS.items():
        comp_wh = r["gpu_wh"] + r["cpu_wh"]
        wall_wh = comp_wh + REST_OF_PC_W * r["minutes"] / 60
        wall_wh /= PSU_EFFICIENCY
        row = {"run": name, "minutes": r["minutes"], "gpu_cpu_wh": comp_wh, "wall_wh_est": round(wall_wh),
               "cost_gpu_cpu": round(comp_wh / 1000 * RATE, 4), "cost_wall_est": round(wall_wh / 1000 * RATE, 4),
               "cost_wall_est_high_rate": round(wall_wh / 1000 * RATE_HIGH, 4)}
        out["per_page"].append(row)
        print(f"  {name}: {comp_wh} Wh GPU+CPU, ~{wall_wh:.0f} Wh at the wall -> "
              f"{money(row['cost_gpu_cpu'], 3)}-{money(row['cost_wall_est'], 3)} ({money(row['cost_wall_est_high_rate'], 3)} at ${RATE_HIGH})")
    for name, cost in API_PAGES.items():
        print(f"  {name}: {money(cost, 3)} per page")

    print("\nRunning an agent 8 h a night for 30 nights, and 24/7 for 30 days")
    for m in MACHINES:
        lo, hi = m["w"]
        night = [w * 8 * 30 / 1000 * RATE for w in (lo, hi)]
        always = [w * 24 * 30 / 1000 * RATE for w in (lo, hi)]
        pages = {k: round(m["price"] / v) for k, v in API_PAGES.items()} if m["price"] else {}
        row = {"machine": m["machine"], "price": m["price"], "watts_low": round(lo), "watts_high": round(hi),
               "basis": m["basis"], "month_8h_nightly": [round(x, 2) for x in night],
               "month_24_7": [round(x, 2) for x in always], "api_pages_for_purchase_price": pages}
        out["per_machine"].append(row)
        print(f"  {m['machine']}: {lo:.0f}-{hi:.0f} W -> {money(night[0])}-{money(night[1])}/month nightly, "
              f"{money(always[0])}-{money(always[1])}/month 24/7"
              + (f"; price = {pages}" if pages else ""))

    path = os.path.join(os.path.dirname(__file__), "..", "results", "hardware-power-cost.json")
    with open(path, "w") as f:
        json.dump(out, f, indent=1)
    print(f"\nwrote {os.path.normpath(path)}")


if __name__ == "__main__":
    main()
