function buildPagoda(S) {
  var cx = L.PAGODA.cx;
  var cz = L.PAGODA.cz;
  var gy = groundY(cx, cz);
  var baseY = gy;
  var STONE = 0x8f8f8c;
  var STONE_D = 0x70706e;
  var RED = 0x7a1f1f;
  var WHITE = 0xf2efe6;
  var ROOF = 0x2b2f3a;
  var GOLD = 0xd9a521;
  var WIN = 0xffc86b;
  var WOOD = 0x4a3220;
  var windows = [];

  function win(wx, wy, wz) {
    S.set(wx, wy, wz, WIN, true);
    windows.push({ x: wx, y: wy, z: wz });
  }

  // Stone platform (13x13, 3 tall) + cap slab
  S.box(cx - 6, baseY, cz - 6, cx + 6, baseY + 2, cz + 6, STONE);
  S.box(cx - 5, baseY + 3, cz - 5, cx + 5, baseY + 3, cz + 5, STONE_D);

  // Stairs on the south side (+z, facing the torii), stepping down outward
  S.box(cx - 1, baseY + 2, cz + 6, cx + 1, baseY + 2, cz + 8, STONE_D);
  S.box(cx - 1, baseY + 1, cz + 6, cx + 1, baseY + 1, cz + 9, STONE);
  S.box(cx - 1, baseY, cz + 6, cx + 1, baseY, cz + 10, STONE_D);

  // Wooden railing posts + rails around the platform edge (gap at the stairs)
  var px, pz;
  for (px = cx - 5; px <= cx + 5; px += 2) {
    S.set(px, baseY + 4, cz - 5, WOOD);
    if (px < cx - 2 || px > cx + 2) S.set(px, baseY + 4, cz + 5, WOOD);
  }
  for (pz = cz - 5; pz <= cz + 5; pz += 2) {
    S.set(cx - 5, baseY + 4, pz, WOOD);
    S.set(cx + 5, baseY + 4, pz, WOOD);
  }
  for (px = cx - 5; px <= cx + 5; px++) {
    S.set(px, baseY + 5, cz - 5, WOOD);
    if (px < cx - 2 || px > cx + 2) S.set(px, baseY + 5, cz + 5, WOOD);
  }
  for (pz = cz - 5; pz <= cz + 5; pz++) {
    S.set(cx - 5, baseY + 5, pz, WOOD);
    S.set(cx + 5, baseY + 5, pz, WOOD);
  }

  // Five tiers: solid white walls, red pillars + beam ring, wood eave plate, flared roof
  var halves = [4, 3, 3, 2, 2];
  var roofs = [7, 6, 5, 4, 3];
  var y = baseY + 4;
  var t, dy, bx, bz;
  for (t = 0; t < 5; t++) {
    var h = halves[t];
    var rh = roofs[t];
    // Walls
    S.box(cx - h, y, cz - h, cx + h, y + 2, cz + h, WHITE);
    // Corner + mid-edge pillars (overwrite wall cells)
    for (dy = y; dy <= y + 2; dy++) {
      S.set(cx - h, dy, cz - h, RED);
      S.set(cx + h, dy, cz - h, RED);
      S.set(cx - h, dy, cz + h, RED);
      S.set(cx + h, dy, cz + h, RED);
      S.set(cx, dy, cz - h, RED);
      S.set(cx, dy, cz + h, RED);
      S.set(cx - h, dy, cz, RED);
      S.set(cx + h, dy, cz, RED);
    }
    // Top beam ring (overwrite top wall layer perimeter)
    for (bx = cx - h; bx <= cx + h; bx++) {
      S.set(bx, y + 2, cz - h, RED);
      S.set(bx, y + 2, cz + h, RED);
    }
    for (bz = cz - h; bz <= cz + h; bz++) {
      S.set(cx - h, y + 2, bz, RED);
      S.set(cx + h, y + 2, bz, RED);
    }
    // Wooden door on the ground floor, south face
    if (t === 0) {
      S.set(cx, y, cz + h, WOOD);
      S.set(cx, y + 1, cz + h, WOOD);
      S.set(cx + 1, y, cz + h, WOOD);
      S.set(cx + 1, y + 1, cz + h, WOOD);
    }
    // Glowing windows spread over the tiers (7 total)
    if (t === 0) {
      win(cx - 2, y + 1, cz + h);
      win(cx + h, y + 1, cz - 1);
    } else if (t === 1) {
      win(cx, y + 1, cz - h);
    } else if (t === 2) {
      win(cx - h, y + 1, cz + 1);
      win(cx + 1, y + 1, cz + h);
    } else if (t === 3) {
      win(cx + h, y + 1, cz);
    } else {
      win(cx, y + 1, cz - h);
    }
    // Wooden eave plate under the roof (bracket layer)
    S.box(cx - rh + 1, y + 3, cz - rh + 1, cx + rh - 1, y + 3, cz + rh - 1, WOOD);
    // Flared roof tier
    S.roofTier(cx, cz, y + 4, rh, rh, ROOF);
    y += 5;
  }

  // Golden finial (sorin): stacked plate + short column + orb
  S.box(cx - 1, y, cz - 1, cx + 1, y, cz + 1, GOLD);
  S.cylinder(cx, cz, y + 1, y + 2, 1, GOLD);
  S.sphere(cx, y + 3, cz, 1, GOLD);
  var topY = y + 4;

  return { x: cx, z: cz, baseY: baseY, topY: topY, windows: windows };
}

function buildTree(S, rng, x, z) {
  var gy = groundY(x, z);
  var TRUNK = 0x6b4a32;
  var cols = [0xffc0d3, 0xf59ab8, 0xffe3ec, 0xffffff];
  function pick() {
    return cols[Math.floor(rng() * cols.length)];
  }
  // Trunk 4-6 tall, rooted at the ground (overwrites the grass top cell)
  var h = 4 + Math.floor(rng() * 3);
  var i;
  for (i = 0; i <= h; i++) S.set(x, gy + i, z, TRUNK);
  var topY = gy + h;
  // 2-3 branches with a blossom puff at each tip
  var dirs = [[1, 0], [-1, 0], [0, 1], [0, -1]];
  var nb = 2 + Math.floor(rng() * 2);
  var b, s;
  for (b = 0; b < nb; b++) {
    var d = dirs[Math.floor(rng() * dirs.length)];
    var by = topY - 1 - Math.floor(rng() * 2);
    var len = 2 + Math.floor(rng() * 2);
    var qx = x, qz = z;
    for (s = 0; s < len; s++) {
      qx += d[0];
      qz += d[1];
      S.set(qx, by, qz, TRUNK);
      if (s === len - 1) S.sphere(qx, by + 1, qz, 1, pick());
    }
  }
  // Blossom canopy: one big sphere + three satellite spheres + pale crown
  var sx = rng() < 0.5 ? -1 : 1;
  var sz = rng() < 0.5 ? -1 : 1;
  S.sphere(x, topY + 2, z, 3, pick());
  S.sphere(x + 2 * sx, topY + 1, z + 1 * sz, 2, pick());
  S.sphere(x - 2 * sx, topY + 1, z - 1 * sz, 2, pick());
  S.sphere(x + 1 * sx, topY + 1, z - 2 * sz, 2, pick());
  S.sphere(x - 1 * sx, topY + 3, z + 2 * sz, 2, pick());
  S.sphere(x, topY + 4, z, 2, 0xffffff);
  return { x: x, z: z, topY: topY + 6 };
}

function buildTrees(S, rng, pond) {
  // 4 trees ringing the pond + 3 along the path from the torii to the pagoda
  var spots = [
    [-28, 14],
    [-20, 0],
    [-6, 4],
    [-10, 20],
    [6, 27],
    [11, 12],
    [15, -3]
  ];
  var out = [];
  var k;
  for (k = 0; k < spots.length; k++) {
    var x = spots[k][0] + (Math.floor(rng() * 3) - 1);
    var z = spots[k][1] + (Math.floor(rng() * 3) - 1);
    // Stay out of the pond (and off the bridge, if the pond reports one)
    var guard = 0;
    while (pond.inside(x, z) && guard < 8) {
      x += 4;
      guard++;
    }
    if (pond.bridge) {
      var br = pond.bridge;
      var bx0 = Math.min(br.x0, br.x1) - 1, bx1 = Math.max(br.x0, br.x1) + 1;
      var bz0 = Math.min(br.z0, br.z1) - 1, bz1 = Math.max(br.z0, br.z1) + 1;
      if (x >= bx0 && x <= bx1 && z >= bz0 && z <= bz1) x = bx1 + 2;
    }
    // Keep clear of the pagoda mound and inside the garden with canopy margin
    var pdx = x - L.PAGODA.cx, pdz = z - L.PAGODA.cz;
    if (pdx * pdx + pdz * pdz < 100) x -= 8;
    if (x < -34) x = -34;
    if (x > 33) x = 33;
    if (z < -34) z = -34;
    if (z > 33) z = 33;
    // Keep out of the raked-sand area
    if (x >= L.SAND.x0 && x <= L.SAND.x1 && z >= L.SAND.z0 && z <= L.SAND.z1) {
      z = L.SAND.z1 + 3;
    }
    out.push(buildTree(S, rng, x, z));
  }
  return out;
}
