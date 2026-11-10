const CFG = { SEED: 20240501, TARGET: 16500 };
const L = {
  POND: { cx: -14, cz: 10, rx: 11, rz: 8 },
  PAGODA: { cx: 14, cz: -14 },
  TORII: { x: 0, z: 35 },
  WATER_Y: 2.6,
  SAND: { x0: -38, z0: -30, x1: -14, z1: -8 }
};

function mulberry32(seed) {
  let a = seed >>> 0;
  return function () {
    a |= 0;
    a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function coreHash2(ix, iz) {
  let h = (Math.imul(ix, 374761393) + Math.imul(iz, 668265263)) | 0;
  h = Math.imul(h ^ (h >>> 13), 1274126177);
  h ^= (h >>> 16);
  return (h >>> 0) / 4294967295;
}

function coreValueNoise(x, z) {
  const xi = Math.floor(x);
  const zi = Math.floor(z);
  const xf = x - xi;
  const zf = z - zi;
  const u = xf * xf * (3 - 2 * xf);
  const v = zf * zf * (3 - 2 * zf);
  const a = coreHash2(xi, zi);
  const b = coreHash2(xi + 1, zi);
  const c = coreHash2(xi, zi + 1);
  const d = coreHash2(xi + 1, zi + 1);
  return a + (b - a) * u + (c - a) * v + (a - b - c + d) * u * v;
}

function groundY(x, z) {
  x = Math.round(x);
  z = Math.round(z);
  const dxp = (x - L.POND.cx) / (L.POND.rx + 2);
  const dzp = (z - L.POND.cz) / (L.POND.rz + 2);
  const pd = dxp * dxp + dzp * dzp;
  if (pd < 1) return 1;
  const n = coreValueNoise(x * 0.09, z * 0.09) * 0.65 + coreValueNoise(x * 0.23 + 7.3, z * 0.23 + 3.1) * 0.35;
  let g = 1 + Math.floor(n * 2.999);
  if (g < 1) g = 1;
  if (g > 3) g = 3;
  const d = Math.hypot(x - L.PAGODA.cx, z - L.PAGODA.cz);
  if (d < 5) return 4;
  if (d < 8) return g > 3 ? g : 3;
  if (d < 11) return g > 2 ? g : 2;
  if (pd < 1.44) return g < 2 ? g : 2;
  return g;
}

function corePosHash(x, y, z) {
  let h = (Math.imul(x, 374761393) + Math.imul(y, 668265263) + Math.imul(z, 1440662683)) | 0;
  h = Math.imul(h ^ (h >>> 13), 1274126177);
  h ^= (h >>> 16);
  return ((h >>> 0) % 10000) / 10000;
}

class VoxelScene {
  constructor() {
    this.map = new Map();
    this._built = null;
  }
  _key(x, y, z) {
    return (x + 64) * 65536 + (z + 64) * 256 + (y + 64);
  }
  set(x, y, z, hex, glow = false) {
    x = Math.round(x);
    y = Math.round(y);
    z = Math.round(z);
    this.map.set(this._key(x, y, z), { x, y, z, hex, glow: !!glow });
  }
  get(x, y, z) {
    x = Math.round(x);
    y = Math.round(y);
    z = Math.round(z);
    const e = this.map.get(this._key(x, y, z));
    return e ? e.hex : undefined;
  }
  box(x0, y0, z0, x1, y1, z1, hex, glow = false) {
    const xa = Math.round(Math.min(x0, x1));
    const xb = Math.round(Math.max(x0, x1));
    const ya = Math.round(Math.min(y0, y1));
    const yb = Math.round(Math.max(y0, y1));
    const za = Math.round(Math.min(z0, z1));
    const zb = Math.round(Math.max(z0, z1));
    for (let x = xa; x <= xb; x++) {
      for (let y = ya; y <= yb; y++) {
        for (let z = za; z <= zb; z++) {
          this.set(x, y, z, hex, glow);
        }
      }
    }
  }
  fillRect(x0, z0, x1, z1, y, hex) {
    const xa = Math.round(Math.min(x0, x1));
    const xb = Math.round(Math.max(x0, x1));
    const za = Math.round(Math.min(z0, z1));
    const zb = Math.round(Math.max(z0, z1));
    y = Math.round(y);
    for (let x = xa; x <= xb; x++) {
      for (let z = za; z <= zb; z++) {
        this.set(x, y, z, hex, false);
      }
    }
  }
  cylinder(cx, cz, y0, y1, r, hex, glow = false) {
    cx = Math.round(cx);
    cz = Math.round(cz);
    const ya = Math.round(Math.min(y0, y1));
    const yb = Math.round(Math.max(y0, y1));
    const rr = r * r + 1e-6;
    const ri = Math.ceil(r);
    for (let y = ya; y <= yb; y++) {
      for (let dx = -ri; dx <= ri; dx++) {
        for (let dz = -ri; dz <= ri; dz++) {
          if (dx * dx + dz * dz <= rr) {
            this.set(cx + dx, y, cz + dz, hex, glow);
          }
        }
      }
    }
  }
  sphere(cx, cy, cz, r, hex, glow = false) {
    cx = Math.round(cx);
    cy = Math.round(cy);
    cz = Math.round(cz);
    const rr = r * r + 1e-6;
    const ri = Math.ceil(r);
    for (let dx = -ri; dx <= ri; dx++) {
      for (let dy = -ri; dy <= ri; dy++) {
        for (let dz = -ri; dz <= ri; dz++) {
          if (dx * dx + dy * dy + dz * dz <= rr) {
            this.set(cx + dx, cy + dy, cz + dz, hex, glow);
          }
        }
      }
    }
  }
  roofTier(cx, cz, y, halfW, halfD, hex) {
    cx = Math.round(cx);
    cz = Math.round(cz);
    y = Math.round(y);
    halfW = Math.round(halfW);
    halfD = Math.round(halfD);
    this.fillRect(cx - halfW, cz - halfD, cx + halfW, cz + halfD, y, hex);
    this.set(cx - halfW - 1, y, cz - halfD - 1, hex, false);
    this.set(cx + halfW + 1, y, cz - halfD - 1, hex, false);
    this.set(cx - halfW - 1, y, cz + halfD + 1, hex, false);
    this.set(cx + halfW + 1, y, cz + halfD + 1, hex, false);
  }
  count() {
    return this.map.size;
  }
  build() {
    const opaqueList = [];
    const emissiveList = [];
    for (const e of this.map.values()) {
      if (e.glow) emissiveList.push(e);
      else opaqueList.push(e);
    }
    const geos = [];
    const mats = [];
    const m = new THREE.Matrix4();
    const c = new THREE.Color();
    let opaque = null;
    let emissive = null;
    if (opaqueList.length > 0) {
      const geo = new THREE.BoxGeometry(1, 1, 1);
      geos.push(geo);
      const mat = new THREE.MeshStandardMaterial({ flatShading: true });
      mats.push(mat);
      opaque = new THREE.InstancedMesh(geo, mat, opaqueList.length);
      opaque.instanceMatrix.setUsage(THREE.StaticDrawUsage);
      for (let i = 0; i < opaqueList.length; i++) {
        const e = opaqueList[i];
        m.makeTranslation(e.x, e.y, e.z);
        opaque.setMatrixAt(i, m);
        c.set(e.hex);
        c.offsetHSL(0, 0, (corePosHash(e.x, e.y, e.z) - 0.5) * 0.08);
        opaque.setColorAt(i, c);
      }
      opaque.instanceMatrix.needsUpdate = true;
      if (opaque.instanceColor) opaque.instanceColor.needsUpdate = true;
      opaque.castShadow = true;
      opaque.receiveShadow = true;
    }
    if (emissiveList.length > 0) {
      let geo2;
      if (opaque) {
        geo2 = geos[0];
      } else {
        geo2 = new THREE.BoxGeometry(1, 1, 1);
        geos.push(geo2);
      }
      const mat2 = new THREE.MeshBasicMaterial({ toneMapped: false });
      mats.push(mat2);
      emissive = new THREE.InstancedMesh(geo2, mat2, emissiveList.length);
      emissive.instanceMatrix.setUsage(THREE.StaticDrawUsage);
      for (let i = 0; i < emissiveList.length; i++) {
        const e = emissiveList[i];
        m.makeTranslation(e.x, e.y, e.z);
        emissive.setMatrixAt(i, m);
        c.set(e.hex);
        c.offsetHSL(0, 0, (corePosHash(e.x, e.y, e.z) - 0.5) * 0.08);
        emissive.setColorAt(i, c);
      }
      emissive.instanceMatrix.needsUpdate = true;
      if (emissive.instanceColor) emissive.instanceColor.needsUpdate = true;
    }
    this._built = { geos, mats };
    return { opaque, emissive, count: this.map.size };
  }
  dispose() {
    if (this._built) {
      for (const g of this._built.geos) {
        if (g && typeof g.dispose === "function") g.dispose();
      }
      for (const mt of this._built.mats) {
        if (mt && typeof mt.dispose === "function") mt.dispose();
      }
      this._built = null;
    }
  }
}
