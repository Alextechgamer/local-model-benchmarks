// world.js — terrain, pond, gate, plants and furniture for the Voxel Pagoda Garden.
// Uses from core: L, groundY. Uses from core VoxelScene API: S.set / S.box / S.fillRect.
// Uses passed rng (mulberry32) for all randomness. All coords kept inside x,z in [-40,39].

function worldPondTest(x, z) {
  var dx = (x + 0.5 - L.POND.cx) / L.POND.rx;
  var dz = (z + 0.5 - L.POND.cz) / L.POND.rz;
  var d = Math.sqrt(dx * dx + dz * dz);
  if (d === 0) return true;
  var th = Math.atan2(dz, dx);
  var t = 1 + 0.13 * Math.sin(3 * th + 1.7) + 0.09 * Math.sin(5 * th + 0.6) + 0.05 * Math.sin(8 * th + 2.3);
  return d < t;
}

function buildTerrain(S, rng) {
  var GRASS_A = 0x63b04f;
  var GRASS_B = 0x58a447;
  var GRASS_C = 0x6cba55;
  var DIRT = 0x7a5a3a;
  var DIRT_D = 0x6e4f33;
  var GRAVEL = 0x9a9a92;
  var PATCH = 0x8a6a45;
  var SAND = 0xe8d8a8;
  var SAND_LINE = 0xd3bd85;
  var STONE_A = 0xb8b8b0;
  var STONE_B = 0xa3a39b;
  var x, z;
  for (x = -40; x <= 39; x++) {
    for (z = -40; z <= 39; z++) {
      if (worldPondTest(x, z)) continue; // carved for the pond, built by buildPond
      var g = groundY(x, z);
      var top = GRASS_A;
      var r = rng();
      if (r < 0.05) top = GRAVEL;
      else if (r < 0.12) top = PATCH;
      else if (r < 0.45) top = GRASS_B;
      else if (r < 0.7) top = GRASS_C;
      var inSand = (x >= L.SAND.x0 && x <= L.SAND.x1 && z >= L.SAND.z0 && z <= L.SAND.z1);
      var onPathV = ((x === 0 || x === 1) && z >= -13 && z <= 35);
      var onPathH = ((z === -14 || z === -13) && x >= 0 && x <= 14);
      if (inSand) {
        top = ((x % 4) === 0) ? SAND_LINE : SAND;
      } else if (onPathV || onPathH) {
        top = (((x + z) % 2) === 0) ? STONE_A : STONE_B;
      }
      S.set(x, g, z, top);
      // Single dirt layer beneath the surface (replaces, never stacks: keeps the
      // column budget at surface + 1 so the whole garden lands near its target).
      S.set(x, g - 1, z, (r < 0.2) ? DIRT_D : DIRT);
    }
  }
}

function buildPond(S, rng) {
  var cx = L.POND.cx;
  var cz = L.POND.cz;
  var rx = L.POND.rx;
  var rz = L.POND.rz;
  var waterY = L.WATER_Y;
  function inside(x, z) { return worldPondTest(x, z); }

  var MUD = 0x4a3f30;
  var POND_SAND = 0xc9b98a;
  var x, z, k;
  // Pond floor: one layer at y = 0 (below the water surface).
  for (x = cx - rx - 2; x <= cx + rx + 2; x++) {
    if (x < -40 || x > 39) continue;
    for (z = cz - rz - 2; z <= cz + rz + 2; z++) {
      if (z < -40 || z > 39) continue;
      if (!inside(x, z)) continue;
      S.set(x, 0, z, (rng() < 0.45) ? POND_SAND : MUD);
    }
  }
  // Stone edging rim: cells just outside the waterline get stones stacked up to
  // just above the water surface so the raised water plane looks contained.
  var STONE_A = 0x8f8f88;
  var STONE_B = 0x7d7d76;
  var dirs = [[1, 0], [-1, 0], [0, 1], [0, -1]];
  for (x = cx - rx - 3; x <= cx + rx + 3; x++) {
    if (x < -40 || x > 39) continue;
    for (z = cz - rz - 3; z <= cz + rz + 3; z++) {
      if (z < -40 || z > 39) continue;
      if (inside(x, z)) continue;
      var shore = false;
      for (k = 0; k < 4; k++) {
        if (inside(x + dirs[k][0], z + dirs[k][1])) { shore = true; break; }
      }
      if (!shore) continue;
      var g = groundY(x, z);
      var topY = 3; // water surface is 2.6, rim sits just above it
      for (var y = g + 1; y <= topY; y++) {
        S.set(x, y, z, (((x + z) % 2) === 0) ? STONE_A : STONE_B);
      }
    }
  }
  // Lily pads floating just above the water surface.
  var PAD = 0x3e9e4f;
  var PAD_D = 0x2f7d3e;
  var BLOOM = 0xffb7d5;
  var placed = 0;
  var guard = 0;
  while (placed < 10 && guard < 200) {
    guard++;
    var px = cx + Math.floor((rng() * 2 - 1) * (rx - 1));
    var pz = cz + Math.floor((rng() * 2 - 1) * (rz - 1));
    if (px < -40 || px > 39 || pz < -40 || pz > 39) continue;
    if (!inside(px, pz)) continue;
    if (S.get(px, 3, pz) !== undefined) continue;
    S.set(px, 3, pz, (placed % 3 === 0) ? PAD_D : PAD);
    if (placed === 2) S.set(px, 4, pz, BLOOM);
    placed++;
  }
  // Arched wooden bridge across the pond along z at x = cx..cx+1.
  var bx0 = cx, bx1 = cx + 1;
  var bz0 = 0, bz1 = 20;
  var DECK = 0x8a5a30;
  var RAIL = 0x6e4525;
  var n = bz1 - bz0;
  for (var i = 0; i <= n; i++) {
    var bz = bz0 + i;
    var lift = Math.round(2 * Math.sin(Math.PI * (i / n)));
    var dy = 3 + lift;
    S.set(bx0, dy, bz, DECK);
    S.set(bx1, dy, bz, DECK);
    // Rail posts on both outer sides.
    S.set(bx0 - 1, dy + 1, bz, RAIL);
    S.set(bx1 + 1, dy + 1, bz, RAIL);
    // Continuous top rail every step.
    S.set(bx0 - 1, dy + 2, bz, RAIL);
    S.set(bx1 + 1, dy + 2, bz, RAIL);
    // Support pillars down to the pond floor every 5 steps.
    if (i % 5 === 2) {
      for (var sy = 1; sy < dy; sy++) {
        if (S.get(bx0, sy, bz) === undefined) S.set(bx0, sy, bz, RAIL);
      }
    }
  }
  // Steps onto both ends of the bridge.
  S.set(bx0, 1, bz0 - 1, STONE_A);
  S.set(bx0, 2, bz0 - 1, STONE_A);
  S.set(bx1, 1, bz1 + 1, STONE_A);
  S.set(bx1, 2, bz1 + 1, STONE_A);

  return {
    cx: cx, cz: cz, rx: rx, rz: rz, waterY: waterY,
    inside: inside,
    bridge: { x0: bx0, z0: bz0, x1: bx1, z1: bz1 }
  };
}

function buildTorii(S) {
  var VERMILION = 0xc8321e;
  var BLACK = 0x15151a;
  var STONE = 0x8f8f88;
  var x = L.TORII.x;
  var z = L.TORII.z;
  var px0 = x - 2, px1 = x + 2;
  var g0 = groundY(px0, z);
  var g1 = groundY(px1, z);
  var gb = (g0 < g1) ? g0 : g1;
  var i, y;
  // Stone bases (one block above the ground each).
  S.set(px0, g0 + 1, z, STONE);
  S.set(px1, g1 + 1, z, STONE);
  // Two vermilion pillars, 6 tall.
  for (i = 0; i < 6; i++) {
    S.set(px0, g0 + 2 + i, z, VERMILION);
    S.set(px1, g1 + 2 + i, z, VERMILION);
  }
  var topP = gb + 7;
  // Lower cross beam (nuki) spanning the pillars.
  S.box(px0 - 1, topP, z, px1 + 1, topP, z, VERMILION);
  // Black kasagi top beam, wider than the pillars.
  S.box(px0 - 2, topP + 2, z, px1 + 2, topP + 2, z, BLACK);
  // Small kasagi cap layer.
  S.box(px0 - 1, topP + 3, z, px1 + 1, topP + 3, z, BLACK);
  // Centre plaque.
  S.set(x, topP + 1, z, BLACK);
}

function buildLantern(S, x, z) {
  var STONE = 0x9aa0a3;
  var STONE_D = 0x84898d;
  var GLOW = 0xffd27a;
  var ROOF = 0x6f7478;
  if (x < -40) x = -40;
  if (x > 39) x = 39;
  if (z < -40) z = -40;
  if (z > 39) z = 39;
  var g = groundY(x, z);
  S.set(x, g + 1, z, STONE_D);          // base
  S.set(x, g + 2, z, STONE);            // shaft
  S.box(x - 1, g + 3, z - 1, x + 1, g + 3, z + 1, STONE); // firebox platform
  S.set(x, g + 3, z, GLOW, true);       // glowing interior (overwrites centre)
  S.box(x - 1, g + 4, z - 1, x + 1, g + 4, z + 1, ROOF);  // roof slab
  S.set(x, g + 5, z, STONE);            // jewel
  return { x: x, y: g + 3, z: z };
}

function buildBamboo(S, rng) {
  var STALK = 0x58a34c;
  var JOINT = 0x7cc47a;
  var LEAF = 0x3e8f3e;
  var LEAF_D = 0x2f7a2f;
  var N = 16;
  for (var i = 0; i < N; i++) {
    var bx = -30 + Math.round((rng() * 2 - 1) * 7);
    var bz = 20 + Math.round((rng() * 2 - 1) * 7);
    if (bx < -40) bx = -40;
    if (bx > 39) bx = 39;
    if (bz < -40) bz = -40;
    if (bz > 39) bz = 39;
    if (worldPondTest(bx, bz)) continue;
    var g = groundY(bx, bz);
    var h = 6 + Math.floor(rng() * 7); // 6..12 tall
    for (var k = 1; k <= h; k++) {
      if (S.get(bx, g + k, bz) !== undefined) continue;
      S.set(bx, g + k, bz, (k % 3 === 0) ? JOINT : STALK);
    }
    var ty = g + h;
    // Small leaf tuft around the top.
    var offs = [[1, 0, 0], [-1, 0, 0], [0, 0, 1], [0, 0, -1], [0, 1, 0], [1, 1, 1]];
    for (var l = 0; l < offs.length; l++) {
      var lx = bx + offs[l][0], ly = ty + offs[l][1], lz = bz + offs[l][2];
      if (lx < -40 || lx > 39 || lz < -40 || lz > 39) continue;
      if (S.get(lx, ly, lz) !== undefined) continue;
      S.set(lx, ly, lz, (l % 2 === 0) ? LEAF : LEAF_D);
    }
  }
}

function buildRocks(S, rng) {
  var GREY = 0x8a8d90;
  var GREY_D = 0x74777b;
  var MOSS = 0x6aa84f;
  var spots = [[-8, -28], [24, 18], [-32, -2], [8, 8], [28, -30]];
  for (var i = 0; i < spots.length; i++) {
    var jx = (i === 4) ? 0 : Math.floor(rng() * 3) - 1;
    var jz = (i === 4) ? 0 : Math.floor(rng() * 3) - 1;
    var rx0 = spots[i][0] + jx;
    var rz0 = spots[i][1] + jz;
    if (rx0 < -38) rx0 = -38;
    if (rx0 > 37) rx0 = 37;
    if (rz0 < -38) rz0 = -38;
    if (rz0 > 37) rz0 = 37;
    if (worldPondTest(rx0, rz0)) continue;
    // Keep rocks off the walking path.
    var onPathV = ((rx0 === 0 || rx0 === 1) && rz0 >= -13 && rz0 <= 35);
    var onPathH = ((rz0 === -14 || rz0 === -13) && rx0 >= 0 && rx0 <= 14);
    if (onPathV || onPathH) continue;
    var g = groundY(rx0, rz0);
    var r = 2 + Math.floor(rng() * 2); // radius 2..3
    for (var dx = -r; dx <= r; dx++) {
      for (var dz = -r; dz <= r; dz++) {
        for (var dy = 0; dy <= r; dy++) {
          if (dx * dx + dy * dy + dz * dz > r * r) continue;
          var vx = rx0 + dx, vy = g + 1 + dy, vz = rz0 + dz;
          if (vx < -40 || vx > 39 || vz < -40 || vz > 39) continue;
          var isTop = (dx * dx + (dy + 1) * (dy + 1) + dz * dz > r * r);
          S.set(vx, vy, vz, isTop ? MOSS : (((dx + dz) % 2 === 0) ? GREY : GREY_D));
        }
      }
    }
  }
}

function buildBench(S) {
  var WOOD = 0x8a6238;
  var WOOD_D = 0x6e4e2c;
  var bx = 6, bz = 24;
  var g = groundY(bx, bz);
  // Legs.
  S.set(bx - 1, g + 1, bz, WOOD_D);
  S.set(bx + 1, g + 1, bz, WOOD_D);
  // Seat, 3 wide.
  S.box(bx - 1, g + 2, bz, bx + 1, g + 2, bz, WOOD);
  // Backrest posts + slat (one behind the seat).
  S.set(bx - 1, g + 3, bz + 1, WOOD_D);
  S.set(bx + 1, g + 3, bz + 1, WOOD_D);
  S.box(bx - 1, g + 4, bz + 1, bx + 1, g + 4, bz + 1, WOOD);
}

function buildHedges(S, rng) {
  var HEDGE = 0x3f7d33;
  var HEDGE_L = 0x4c8f3a;
  function hedgeRow(x0, z0, x1, z1) {
    var dx = (x1 > x0) ? 1 : ((x1 < x0) ? -1 : 0);
    var dz = (z1 > z0) ? 1 : ((z1 < z0) ? -1 : 0);
    var x = x0, z = z0;
    var guard = 0;
    while (guard < 200) {
      guard++;
      if (rng() > 0.1) { // occasional gap for a natural look
        var g = groundY(x, z);
        var c = (rng() < 0.4) ? HEDGE_L : HEDGE;
        if (S.get(x, g + 1, z) === undefined) S.set(x, g + 1, z, c);
        if (S.get(x, g + 2, z) === undefined) S.set(x, g + 2, z, c);
      }
      if (x === x1 && z === z1) break;
      if (x !== x1) x += dx;
      else if (z !== z1) z += dz;
    }
  }
  hedgeRow(-39, -5, -39, 25);   // west border
  hedgeRow(-8, -39, 30, -39);   // north border
  hedgeRow(39, -25, 39, 15);    // east border
}
