# status

ROADMAP  ██████████████░░  8/8 done
 [x] 1. Head/CSS/DOM + config + seeded RNG (xorshift32) + voxel map core
 [x] 2. Terrain/pond builders (heightmap, zen raked sand, gravel/dirt, bowl + water)
 [x] 3. Pagoda (5 tiers), torii, trees, bamboo, rocks, lanterns, bench, hedges, bridge
 [x] 4. InstancedMesh per material (opaque / emissive / water / koi) + dispose on regen
 [x] 5. Lighting: PCFSoft 2048 sun, hemi, ambient, 10 warm point lights, day/night palette
 [x] 6. Particles: 1400 petals (instanced), 160 fireflies, dawn mist, 1400 stars
 [x] 7. UI: glass panel, sliders/toggles/presets/seed/reset/help, readouts, keyboard
 [x] 8. Verification harnesses (count + real-three smoke)

VERIFIED
 - voxel count 16,263-16,446 over 16 seeds (target 16,500, range 15k-18k), 0 cross-field dupes
 - `node --check` on the extracted module: clean
 - smoke run with REAL three r160 + real OrbitControls (fake GL/DOM): module body + 10 frames, no throw
 - not GPU-rendered here; GLSL (water ripple + firefly/mist/star shaders) untested by a browser

WHY SLOW
 - one 1,339-line file written in 4 parts, then concatenated; two verification passes added time

NEXT
 - open pagoda.html in a browser; if any shader fails to compile, the custom ShaderMaterials are the suspects

NOTES
 - pagoda.html is the deliverable; parts live in %TEMP%\opencode
 - assembly is buildGarden(seed) with numbered sub-sections (3.1 terrain ... 3.7 props), not separate top-level fns
 - pure voxel section delimited by //<<PURE>> .. //<<//PURE>> so node can count without a browser
