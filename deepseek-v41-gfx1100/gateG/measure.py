"""Gate G speed measurement for one running DeepSeek config.

Sends the same prompts to the OpenAI-compatible server (streaming, temperature 0) and records per answer: time to first token
(TTFT), decode tokens/s, and while it runs: graphics memory in use (Windows GPU counter, RX 7900 XT), RAM available (lowest),
and reads from E: (PhysicalDrive0) in MB/s.  Appends one JSON line per answer to the results file and prints a summary.

usage: python measure.py LABEL [port] [runs]
"""
import json, os, statistics, subprocess, sys, threading, time, urllib.request

import psutil

LABEL = sys.argv[1]
PORT = int(sys.argv[2]) if len(sys.argv) > 2 else 8091
RUNS = int(sys.argv[3]) if len(sys.argv) > 3 else 3
OUT = r"E:\strata-dsv41\gateG\results.jsonl"
GPU = r"\GPU Adapter Memory(luid_0x00000000_0x000117ce_phys_0)\Dedicated Usage"
DISK = "PhysicalDrive0"   # E:
PROMPTS = [
    "Write a Python function that returns the n-th Fibonacci number iteratively, with a short docstring.",
    "Explain in three sentences what a mixture-of-experts language model is.",
    "List five practical tips for keeping a Git history clean.",
]
MAX_TOKENS = 256


class Sampler(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.stop, self.vram, self.ram = False, [], []

    def run(self):
        while not self.stop:
            try:
                out = subprocess.run(["powershell", "-NoProfile", "-Command", f"(Get-Counter '{GPU}').CounterSamples[0].CookedValue"],
                                     capture_output=True, text=True, timeout=10).stdout.strip()
                self.vram.append(float(out))
            except Exception:
                pass
            self.ram.append(psutil.virtual_memory().available)
            time.sleep(1)


def ask(prompt):
    body = json.dumps({"model": "deepseek", "messages": [{"role": "user", "content": prompt}], "max_tokens": MAX_TOKENS,
                       "temperature": 0, "stream": True, "stream_options": {"include_usage": True}}).encode()
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}/v1/chat/completions", data=body, headers={"Content-Type": "application/json"})
    t0 = time.time()
    first = last = None
    chunks, text, usage = 0, [], None
    with urllib.request.urlopen(req, timeout=1800) as r:
        for raw in r:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:") or line == "data: [DONE]":
                continue
            ev = json.loads(line[5:])
            usage = ev.get("usage") or usage
            for ch in ev.get("choices") or []:
                d = ch.get("delta") or {}
                piece = (d.get("reasoning_content") or "") + (d.get("content") or "")
                if piece:
                    now = time.time()
                    first = first or now
                    last = now
                    chunks += 1
                    text.append(piece)
    toks = (usage or {}).get("completion_tokens") or chunks
    return {"ttft_s": round(first - t0, 2) if first else None,
            "decode_tok_s": round((toks - 1) / (last - first), 2) if first and last and last > first else None,
            "completion_tokens": toks, "prompt_tokens": (usage or {}).get("prompt_tokens"), "wall_s": round(time.time() - t0, 1),
            "text_head": "".join(text)[:300], "text": "".join(text)}


def main():
    rows = []
    for i in range(RUNS):
        prompt = PROMPTS[i % len(PROMPTS)]
        s = Sampler()
        d0 = psutil.disk_io_counters(perdisk=True)[DISK].read_bytes
        s.start()
        t0 = time.time()
        res = ask(prompt)
        el = time.time() - t0
        s.stop = True
        s.join(12)
        d1 = psutil.disk_io_counters(perdisk=True)[DISK].read_bytes
        res.update({"label": LABEL, "run": i + 1, "prompt": prompt[:60], "time": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "vram_peak_GB": round(max(s.vram) / 1e9, 2) if s.vram else None,
                    "ram_avail_min_GB": round(min(s.ram) / 1e9, 2) if s.ram else None,
                    "disk_E_read_MBps": round((d1 - d0) / el / 1e6, 1), "disk_E_read_GB": round((d1 - d0) / 1e9, 2)})
        rows.append(res)
        with open(OUT, "a", encoding="utf-8") as f:
            f.write(json.dumps(res) + "\n")
        print(json.dumps({k: v for k, v in res.items() if k not in ("text_head", "text")}), flush=True)
        print("   text:", res["text_head"][:160].replace("\n", " "), flush=True)
    dec = [r["decode_tok_s"] for r in rows if r["decode_tok_s"]]
    ttft = [r["ttft_s"] for r in rows if r["ttft_s"]]
    print(f"SUMMARY {LABEL}: decode median {statistics.median(dec) if dec else None} tok/s (runs {dec}), "
          f"TTFT median {statistics.median(ttft) if ttft else None} s, VRAM peak {max(r['vram_peak_GB'] or 0 for r in rows)} GB, "
          f"RAM avail min {min(r['ram_avail_min_GB'] or 1e9 for r in rows)} GB, E: read {[r['disk_E_read_MBps'] for r in rows]} MB/s", flush=True)


if __name__ == "__main__":
    main()
