"""Load a pagoda.html in headless Brave over the DevTools protocol and report what actually happens.

usage: python check_page.py <label> <path-to-html>
Writes shots/<label>-day.png, shots/<label>-night.png and shots/<label>.json (console errors, voxel count, UI, FPS).
"""
import asyncio, base64, json, os, subprocess, sys, tempfile, time, urllib.request
from pathlib import Path

import websockets

BRAVE = r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"
ROOT = Path(__file__).parent
PORT = 9333

PROBE = r"""
(() => {
  const txt = document.body ? document.body.innerText : '';
  const canv = [...document.querySelectorAll('canvas')].map(c => [c.width, c.height]);
  const m = txt.match(/voxels?\D{0,12}([\d,\.]{3,9})/i) || txt.match(/([\d,]{5,7})\s*voxels?/i);
  const fps = txt.match(/fps\D{0,6}(\d{1,3})/i) || txt.match(/(\d{1,3})\s*fps/i);
  return JSON.stringify({
    title: document.title, canvases: canv,
    sliders: document.querySelectorAll('input[type=range]').length,
    checkboxes: document.querySelectorAll('input[type=checkbox]').length,
    buttons: [...document.querySelectorAll('button')].map(b => b.innerText.trim()).filter(Boolean).slice(0, 40),
    voxelText: m ? m[0] : null, fpsText: fps ? fps[0] : null,
    hasJapaneseTitle: txt.includes('桜の庭'),
    loadingVisible: [...document.querySelectorAll('[id*=load i],[class*=load i]')].some(e => { const s = getComputedStyle(e); return s.display !== 'none' && s.visibility !== 'hidden' && +s.opacity > 0.05; }),
    text: txt.slice(0, 900)
  });
})()
"""
# press N (the prompt's day/night key), else push the first range slider (time of day) to its minimum
NIGHT = r"""
(() => {
  const s = [...document.querySelectorAll('input[type=range]')].find(e => +e.max >= 23 && +e.max <= 24);
  if (s) { s.value = 22.5; for (const t of ['input', 'change']) s.dispatchEvent(new Event(t, {bubbles: true})); return 'slider ' + s.value; }
  for (const type of ['keydown', 'keyup']) window.dispatchEvent(new KeyboardEvent(type, {key: 'n', code: 'KeyN', bubbles: true}));
  return 'key';
})()
"""


async def main(label: str, html: Path) -> None:
    prof = tempfile.mkdtemp(prefix="pagoda-check-")
    proc = subprocess.Popen([BRAVE, "--headless=new", f"--remote-debugging-port={PORT}", f"--user-data-dir={prof}",
                             "--no-first-run", "--disable-extensions", "--window-size=1600,900", "about:blank"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    out = {"label": label, "file_kb": round(html.stat().st_size / 1024, 1), "console_errors": [], "console_warnings": [],
           "exceptions": [], "logs": []}
    try:
        for _ in range(60):
            try:
                tabs = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json", timeout=2).read()); break
            except Exception:
                time.sleep(0.5)
        ws_url = next(t["webSocketDebuggerUrl"] for t in tabs if t.get("type") == "page")
        async with websockets.connect(ws_url, max_size=64 * 1024 * 1024) as ws:
            n = 0
            pending: dict[int, asyncio.Future] = {}

            async def pump() -> None:
                async for raw in ws:
                    m = json.loads(raw)
                    if "id" in m and m["id"] in pending:
                        pending.pop(m["id"]).set_result(m.get("result") or m.get("error"))
                    elif m.get("method") == "Runtime.consoleAPICalled":
                        p = m["params"]; text = " ".join(str(a.get("value", a.get("description", ""))) for a in p["args"])[:300]
                        {"error": out["console_errors"], "warning": out["console_warnings"]}.get(p["type"], out["logs"]).append(text)
                    elif m.get("method") == "Runtime.exceptionThrown":
                        d = m["params"]["exceptionDetails"]
                        out["exceptions"].append((d.get("exception", {}).get("description") or d.get("text") or "")[:400])
                    elif m.get("method") == "Log.entryAdded" and m["params"]["entry"]["level"] == "error":
                        out["console_errors"].append(m["params"]["entry"]["text"][:300])

            async def call(method: str, **params):
                nonlocal n
                n += 1; fut = asyncio.get_running_loop().create_future(); pending[n] = fut
                await ws.send(json.dumps({"id": n, "method": method, "params": params}))
                return await asyncio.wait_for(fut, 60)

            task = asyncio.create_task(pump())
            for dom in ("Runtime", "Log", "Page"):
                await call(f"{dom}.enable")
            await call("Emulation.setDeviceMetricsOverride", width=1600, height=900, deviceScaleFactor=1, mobile=False)
            await call("Page.navigate", url=html.resolve().as_uri())
            await asyncio.sleep(14)
            if os.environ.get("NOON"):       # a page that starts its cycle at night: move the time slider to noon first
                await call("Runtime.evaluate", expression=NIGHT.replace("22.5", "12"), returnByValue=True)
                await asyncio.sleep(3)
            r = await call("Runtime.evaluate", expression=PROBE, returnByValue=True)
            out["page"] = json.loads(r["result"]["value"]) if r.get("result", {}).get("value") else r
            shot = await call("Page.captureScreenshot", format="png")
            (ROOT / "shots" / f"{label}-day.png").write_bytes(base64.b64decode(shot["data"]))
            for preset in sys.argv[3:]:      # optional: click camera preset buttons by their text and shoot each
                await call("Runtime.evaluate", returnByValue=True, expression=
                           "(() => { const b = [...document.querySelectorAll('button')].find(b => b.innerText.trim() === "
                           + json.dumps(preset) + "); if (b) b.click(); return !!b; })()")
                await asyncio.sleep(4)
                shot = await call("Page.captureScreenshot", format="png")
                (ROOT / "shots" / f"{label}-{preset.lower()}.png").write_bytes(base64.b64decode(shot["data"]))
            await call("Runtime.evaluate", expression=NIGHT, returnByValue=True)
            await asyncio.sleep(5)
            shot = await call("Page.captureScreenshot", format="png")
            (ROOT / "shots" / f"{label}-night.png").write_bytes(base64.b64decode(shot["data"]))
            r = await call("Runtime.evaluate", returnByValue=True, awaitPromise=True, expression=
                           "new Promise(res => { let f = 0; const t0 = performance.now(); (function tick() { f++; "
                           "performance.now() - t0 < 3000 ? requestAnimationFrame(tick) : res(Math.round(f / 3)); })(); })")
            out["measured_fps_headless"] = r.get("result", {}).get("value")
            task.cancel()
    finally:
        proc.terminate()
    out["logs"] = out["logs"][:12]
    (ROOT / "shots" / f"{label}.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(out, indent=1)[:3500])


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1], Path(sys.argv[2])))
