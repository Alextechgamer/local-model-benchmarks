# Shared contract: Voxel Pagoda Garden (Three.js r160)

You are one of five engineers building ONE module of a single-file Three.js voxel garden. A lead engineer will
concatenate all modules, in the order core -> world -> structures -> runtime, into ONE `<script type="module">`
that already contains:

    import * as THREE from 'three';
    import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

So: all modules share ONE scope. Do NOT write `import`/`export`, do NOT redeclare names owned by another module,
and do NOT write HTML (except the UI module's fragment). Plain JavaScript only, no TypeScript, no markdown fences
inside the file. Use only the names listed below from other modules, exactly as spelled.

## World conventions
- 1 voxel = 1 unit. x and z run from -40 to 39, y is up, ground surface is y = groundY(x,z) (an integer, 1..4).
- Colours are hex numbers (0xRRGGBB). Voxels are NEVER meshes; they go through `VoxelScene`.
- Fixed layout constants (object `L`, owned by core):
  `L.POND = {cx:-14, cz:10, rx:11, rz:8}`, `L.PAGODA = {cx:14, cz:-14}`, `L.TORII = {x:0, z:35}`,
  `L.WATER_Y = 2.6` (water surface height), `L.SAND = {x0:-38, z0:-30, x1:-14, z1:-8}` (raked sand area).
- Total voxels across the whole garden should land at about 16,500 (15,000-18,000).

## core (owner of: CFG, L, mulberry32, groundY, VoxelScene)
```
const CFG = { SEED: 20240501, TARGET: 16500 };
const L = { ...as above... };
function mulberry32(seed)            // returns () => float in [0,1)
function groundY(x, z)               // integer ground height, gently rolling, raised hill (+4) around L.PAGODA, ~1 near pond
class VoxelScene {
  constructor()
  set(x, y, z, hex, glow = false)    // integer coords; later set() on the same cell overwrites; glow=true -> emissive group
  get(x, y, z)                       // returns hex or undefined
  box(x0, y0, z0, x1, y1, z1, hex, glow = false)   // inclusive corners, any order
  fillRect(x0, z0, x1, z1, y, hex)   // flat layer at height y, inclusive, any order
  cylinder(cx, cz, y0, y1, r, hex, glow = false)   // filled vertical cylinder, inclusive y range
  sphere(cx, cy, cz, r, hex, glow = false)         // filled sphere
  roofTier(cx, cz, y, halfW, halfD, hex)           // one roof layer: filled rectangle at height y, plus the four corners flared out by 1
  count()                            // number of distinct voxels
  build()                            // returns { opaque: THREE.InstancedMesh, emissive: THREE.InstancedMesh | null, count }
                                     // one shared BoxGeometry(1,1,1), per-instance colour via setColorAt, deterministic
                                     // +-4% lightness jitter per voxel (hash of position, NOT Math.random),
                                     // MeshStandardMaterial for opaque (flatShading true), MeshBasicMaterial-like glow for emissive,
                                     // castShadow = receiveShadow = true on opaque, matrices set once (static)
  dispose()                          // dispose geometry + materials of the last build()
}
```

## world (owner of: buildTerrain, buildPond, buildTorii, buildLantern, buildBamboo, buildRocks, buildBench, buildHedges)
```
buildTerrain(S, rng)   // ground columns over the whole 80x80: grass top, dirt below (2 layers), gravel and dirt patches,
                       // raked-sand zen area inside L.SAND (sand colour with raked-line stripes), stone path (flat stones)
                       // from L.TORII to the pagoda base. Skip the pond interior (see pond) - carve it down so the water shows.
buildPond(S, rng)      // irregular pond centred on L.POND (noise on the radius), carved into the terrain, stone edging, lily pads,
                       // arched wooden bridge across it. Returns:
                       // { cx, cz, rx, rz, waterY: L.WATER_Y, inside(x,z) -> bool, bridge: {x0,z0,x1,z1} }
buildTorii(S)          // vermilion (0xc8321e) two-pillar gate at L.TORII, black (0x15151a) kasagi top beam, stone bases
buildLantern(S, x, z)  // stone toro on the ground at (x,z) with a glowing (glow=true, warm 0xffd27a) interior; returns {x, y, z} of the light
buildBamboo(S, rng)    // a bamboo grove cluster (green stalks 6-12 tall) somewhere around (-30, 20)
buildRocks(S, rng)     // 4-6 large mossy rocks (grey + moss green on top)
buildBench(S)          // a wooden bench near (6, 24)
buildHedges(S, rng)    // low hedges (height 2) along a few borders, away from the path
```
Call order (done by the lead): buildTerrain, buildPond, buildTorii, buildBamboo, buildRocks, buildBench, buildHedges, then
lanterns. Every builder must place voxels only inside x,z in [-40,39] and must read heights with groundY().

## structures (owner of: buildPagoda, buildTree, buildTrees)
```
buildPagoda(S)         // five-tier pagoda centred on L.PAGODA, standing on its hill: stone base (grey), dark-red (0x7a1f1f) pillars,
                       // white (0xf2efe6) walls, five roof tiers that step inward (use S.roofTier, dark 0x2b2f3a) and flare at the corners,
                       // golden finial (sorin, 0xd9a521) on top. Window voxels with glow=true (0xffc86b). Returns:
                       // { x: cx, z: cz, baseY, topY, windows: [{x,y,z}, ...] }   (windows = 4-8 light positions spread over the tiers)
buildTree(S, rng, x, z) // one cherry tree rooted at (x,z): brown (0x6b4a32) trunk + a few branches, blossom canopy in 3-4 shades
                       // (0xffc0d3, 0xf59ab8, 0xffe3ec, 0xffffff) made of spheres; returns { x, z, topY }
buildTrees(S, rng, pond) // plants 7 trees around the pond (use pond.inside(x,z) to stay out of it) and along the path; returns array of buildTree results
```

## runtime (owner of: setupRuntime)
```
setupRuntime(garden)   // garden = { S, seed, pond, pagoda, lights: [{x,y,z}], buildAll(seed) -> garden-like object }  (lead writes buildAll)
                       // Creates renderer on document.getElementById('app') (full window, ACESFilmicToneMapping, SRGBColorSpace,
                       // PCFSoftShadowMap), scene, PerspectiveCamera, OrbitControls (damping, min/max distance, polarAngle < PI/2 - 0.05),
                       // adds garden.S.build() meshes, sun DirectionalLight (shadow map 2048, camera bounds to the 80x80 garden),
                       // HemisphereLight + low AmbientLight, warm PointLights at garden.pagoda.windows and garden.lights (intensity follows time of day),
                       // a water mesh (PlaneGeometry segmented, slightly transparent, vertex ripple + colour shift, at pond waterY, clipped by building it
                       // only over the pond bounding box; per-frame updates must not allocate),
                       // 2-3 koi (small orange/white voxel-style meshes) swimming slow loops inside the pond,
                       // 800-1500 falling petals (THREE.Points or InstancedMesh) with wind sway, respawn at top,
                       // 100-200 pulsing fireflies visible only at night, a faint mist plane over the pond at dawn,
                       // star Points on a sky sphere visible at night, day/night cycle driven by time of day 0-24 (sun position and colour,
                       // sky/background/fog colour and density, sunrise/sunset orange, deep-blue night),
                       // a requestAnimationFrame loop with THREE.Clock delta, window resize handling.
                       // Returns the api object below. It must also hide the element #loading (class 'hide') once built.
api = {
  setTime(h), getTime(), setPlaying(bool), setSpeed(x /*hours per second*/), setPetalDensity(n /*0..1500*/), setWind(x /*0..3*/),
  setAutoRotate(bool), toggleAutoRotate(), setShadows(bool), setFireflies(bool), setWaterAnim(bool), setWireframe(bool),
  toggleNight(),                       // jump between 12 and 23
  goPreset(name),                      // 'Overview'|'Pagoda'|'Pond'|'Torii'|'Blossoms' - smooth lerp tween of camera AND target, no tween library
  resetView(),
  regenerate(newSeed),                 // rebuild voxels (disposing old geometry), keep pagoda/pond/torii layout
  stats()                              // { voxels, fps, time }
}
```
The runtime also prints `console.log('Voxel count:', n)` after the build.

## ui (owner of: ui.html fragment + bindUI)
Two files. `ui.html` is an HTML FRAGMENT (no html/head/body tags) containing a `<style>` block and the markup; `ui.js` defines `bindUI(api)`.
Required element ids in ui.html (exact):
`loading` (full-screen overlay "Building the garden...", fades out when it gets class `hide`), `title` (top-right: 桜の庭 – Voxel Pagoda Garden),
`panel` (glass-style, semi-transparent, top-left, collapsible via button `panel-toggle`), `time` (range 0-24 step 0.1), `play` (button), `speed` (range),
`petals` (range 0-1500), `wind` (range 0-3 step 0.1), checkboxes `autorotate`, `shadows`, `fireflies`, `water`, `wireframe`,
buttons with `data-preset="Overview|Pagoda|Pond|Torii|Blossoms"` (class `preset`), `regen` ("Regenerate seed"), `reset` ("Reset view"),
`help` (a "?" button whose tooltip `help-tip` lists the keyboard shortcuts), readouts `r-voxels`, `r-fps`, `r-time`.
Do NOT create the `#app` canvas container (the lead adds `<div id="app"></div>`). Page body background is dark; the canvas sits behind the UI.
`bindUI(api)` wires every control to the api, updates the readouts ~4 times per second from `api.stats()`, keeps the time slider in sync while
playing, and registers keyboard shortcuts: Space = toggleAutoRotate, 1-5 = presets in the order above, N = toggleNight (ignore keys while typing in inputs,
preventDefault on Space). regen calls `api.regenerate(Math.floor(Math.random()*1e9))`.
