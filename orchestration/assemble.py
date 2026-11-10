"""Assemble the modules of one orchestration round into index.html.
usage: python assemble.py <out.html> core=<dir> world=<dir> structures=<dir> runtime=<dir> ui=<dir>
Each <dir> is the folder that holds that module's files. Prints which parts were found."""
import sys, subprocess
from pathlib import Path

out = Path(sys.argv[1]); src = dict(a.split("=", 1) for a in sys.argv[2:])
need = {"core": "core.js", "world": "world.js", "structures": "structures.js", "runtime": "runtime.js"}
parts, missing = [], []
for m, f in need.items():
    p = Path(src[m]) / f
    if p.exists(): parts.append(f"// ===== {m} =====\n" + p.read_text(encoding="utf-8")); 
    else: missing.append(f"{m}/{f}")
ui_html = Path(src["ui"]) / "ui.html"; ui_js = Path(src["ui"]) / "ui.js"
for p in (ui_html, ui_js):
    if not p.exists(): missing.append(f"ui/{p.name}")
if missing:
    print("MISSING:", ", ".join(missing)); sys.exit(2)
glue = """
// ===== lead: assembly =====
const LANTERN_SPOTS = [[3, 30], [-3, 30], [9, 2], [-2, 14], [-26, -6], [22, -6]];
function buildAll(seed) {
  const S = new VoxelScene(), rng = mulberry32(seed);
  buildTerrain(S, rng);
  const pond = buildPond(S, rng);
  buildTorii(S); buildBamboo(S, rng); buildRocks(S, rng); buildBench(S); buildHedges(S, rng);
  const pagoda = buildPagoda(S);
  const trees = buildTrees(S, rng, pond);
  const lights = LANTERN_SPOTS.map(([x, z]) => buildLantern(S, x, z));
  return { S, seed, pond, pagoda, trees, lights, buildAll };
}
const garden = buildAll(CFG.SEED);
const api = setupRuntime(garden);
bindUI(api);
window.__api = api; window.__garden = garden;
"""
html = f"""<!DOCTYPE html>
<html lang="ja"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>桜の庭 – Voxel Pagoda Garden</title>
<style>html,body{{margin:0;height:100%;overflow:hidden;background:#0b1026}}#app{{position:fixed;inset:0}}#app canvas{{display:block}}</style>
<script type="importmap">{{"imports":{{"three":"https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js","three/addons/":"https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/"}}}}</script>
</head><body>
<div id="app"></div>
{ui_html.read_text(encoding="utf-8")}
<script type="module">
import * as THREE from 'three';
import {{ OrbitControls }} from 'three/addons/controls/OrbitControls.js';
{chr(10).join(parts)}
// ===== ui =====
{ui_js.read_text(encoding="utf-8")}
{glue}
</script></body></html>
"""
out.write_text(html, encoding="utf-8")
body = html.split('<script type="module">')[1].split("</script>")[0].replace("import * as THREE from 'three';", "").replace("import { OrbitControls } from 'three/addons/controls/OrbitControls.js';", "")
chk = out.with_suffix(".check.mjs"); chk.write_text("const THREE={},OrbitControls=class{};\n" + body, encoding="utf-8")
r = subprocess.run(["node", "--check", str(chk)], capture_output=True, text=True)
print("assembled", out, f"{out.stat().st_size/1024:.1f} KB;", "syntax OK" if r.returncode == 0 else "SYNTAX ERROR:\n" + r.stderr[:1500])
chk.unlink()
