# Status — Voxel Pagoda Garden (pagoda.html)

## Checklist
- [x] Spec parsed; voxel layout zones planned (80x80, 1-unit voxels)
- [x] Data module: seeded buildGarden (mulberry32, seed 1337) — terrain, pond+neck+islet, pagoda on hill, torii, 6 lanterns, 8 trees, rocks, hedges, bench, lily pads, koi paths, lights, emissives
- [x] App module: voxel InstancedMesh + emissive instances, water fan mesh w/ ripples, koi dynamic instances, petals/fireflies/stars/mist (shader points), day/night cycle, shadows, ACES/sRGB
- [x] UI: glass panel, presets (5, lerp tween), sliders, toggles, reset, help, readouts (voxels/FPS/time), loading fade, resize
- [x] Keys: Space (rotate), 1-5 (presets), N (night toggle)
- [x] Regenerate: new seed, full dispose + rebuild (~16k voxels re-verified)
- [x] Verification: node --check on both modules; headless smoke test (900+ frames, all UI paths, regen seed 1762890857 -> 16,051 voxels) PASSED
- [x] Scratch files removed; deliverable is single pagoda.html (52.8 KB)
- [ ] Optional: real-browser visual check (open pagoda.html) — not possible headless here

## Notes
- three 0.160.0 via importmap (jsdelivr CDN)
- Voxel count seed 1337 = 16,001 (range across seeds 15,963–16,051, within 15k–18k target)
- Point-light intensity x8 for r155+ physical lighting (useLegacyLights=false default)
- GLSL uses uTime/uPx uniforms; stars = 700 pts upper hemisphere r=320; fireflies 150, night-only
- Water: center+ring fan, 3-octave ripple, 90-segment ring, transparent Phong
