function setupRuntime(garden) {
  let G = garden;

  const clamp01 = v => (v < 0 ? 0 : v > 1 ? 1 : v);

  const SKY_NIGHT = new THREE.Color(0x0e2140);
  const SKY_DAY = new THREE.Color(0x8ab6e8);
  const SKY_DAWN = new THREE.Color(0xe08a52);
  const SUN_LOW = new THREE.Color(0xff7a30);
  const SUN_HIGH = new THREE.Color(0xfff3e0);
  const WATER_DAY = new THREE.Color(0x2e7d9c);
  const WATER_NIGHT = new THREE.Color(0x14314d);

  const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: 'high-performance' });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setSize(window.innerWidth, window.innerHeight);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.1;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  document.getElementById('app').appendChild(renderer.domElement);

  const scene = new THREE.Scene();
  const skyCol = new THREE.Color(0x0e2140);
  scene.background = skyCol;
  scene.fog = new THREE.Fog(0x0e2140, 140, 330);
  const fogCol = scene.fog.color;

  const camera = new THREE.PerspectiveCamera(55, window.innerWidth / window.innerHeight, 0.1, 900);
  camera.position.set(60, 45, 60);

  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.06;
  controls.minDistance = 8;
  controls.maxDistance = 220;
  controls.maxPolarAngle = Math.PI / 2 - 0.05;
  controls.target.set(0, 2, 0);
  controls.autoRotateSpeed = 0.6;

  const sun = new THREE.DirectionalLight(0xfff3e0, 2.4);
  sun.castShadow = true;
  sun.shadow.mapSize.set(2048, 2048);
  sun.shadow.camera.left = -60;
  sun.shadow.camera.right = 60;
  sun.shadow.camera.top = 60;
  sun.shadow.camera.bottom = -60;
  sun.shadow.camera.near = 10;
  sun.shadow.camera.far = 320;
  sun.shadow.bias = -0.0006;
  sun.shadow.normalBias = 0.5;
  scene.add(sun);
  sun.target.position.set(0, 0, 0);
  scene.add(sun.target);

  const hemi = new THREE.HemisphereLight(0xbfd9ff, 0x3a4a3a, 0.5);
  scene.add(hemi);
  const amb = new THREE.AmbientLight(0xffffff, 0.12);
  scene.add(amb);

  const moon = new THREE.DirectionalLight(0x8fa8ff, 0);
  moon.position.set(30, 80, -20);
  scene.add(moon);

  const dummy = new THREE.Object3D();

  let lastBuilt = null;
  let voxelCount = 0;
  let allMaterials = [];
  let pointLights = [];
  let waterMesh = null;
  let waterBase = null;
  let waterMat = null;
  let mistMesh = null;
  let mistMat = null;
  let koi = [];
  let starPoints = null;
  let starMat = null;
  let firePoints = null;
  let fireMat = null;
  let fireBase = null;

  const PETAL_MAX = 1500;
  const petalGeo = new THREE.PlaneGeometry(0.28, 0.2);
  const petalMat = new THREE.MeshStandardMaterial({ color: 0xffc0d3, side: THREE.DoubleSide, roughness: 0.8 });
  const petals = new THREE.InstancedMesh(petalGeo, petalMat, PETAL_MAX);
  petals.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
  petals.frustumCulled = false;
  const pbx = new Float32Array(PETAL_MAX);
  const pbz = new Float32Array(PETAL_MAX);
  const py = new Float32Array(PETAL_MAX);
  const pPhase = new Float32Array(PETAL_MAX);
  const pFall = new Float32Array(PETAL_MAX);
  const pSway = new Float32Array(PETAL_MAX);
  const pRot = new Float32Array(PETAL_MAX);
  const pRot2 = new Float32Array(PETAL_MAX);
  const petalShades = [0xffc0d3, 0xf59ab8, 0xffe3ec, 0xffffff, 0xffd9e2];
  const tmpColor = new THREE.Color();
  let petalCount = 1200;
  petals.count = petalCount;

  function randomizePetal(i, high) {
    py[i] = high ? 12 + Math.random() * 10 : 0.6 + Math.random() * 7;
    pbx[i] = -40 + Math.random() * 80;
    pbz[i] = -40 + Math.random() * 80;
    pPhase[i] = Math.random() * Math.PI * 2;
    pFall[i] = 0.9 + Math.random() * 1.1;
    pSway[i] = 0.5 + Math.random() * 1.1;
    pRot[i] = 1 + Math.random() * 2.5;
    pRot2[i] = 1 + Math.random() * 2.5;
  }

  for (let i = 0; i < PETAL_MAX; i++) {
    randomizePetal(i, false);
    tmpColor.setHex(petalShades[(Math.random() * petalShades.length) | 0]);
    tmpColor.offsetHSL(0, 0, (Math.random() - 0.5) * 0.08);
    petals.setColorAt(i, tmpColor);
  }
  if (petals.instanceColor) petals.instanceColor.needsUpdate = true;
  scene.add(petals);

  const FLY_N = 160;
  const firePos = new Float32Array(FLY_N * 3);
  fireBase = new Float32Array(FLY_N * 3);
  for (let i = 0; i < FLY_N; i++) {
    fireBase[i * 3] = -38 + Math.random() * 76;
    fireBase[i * 3 + 1] = 1 + Math.random() * 5;
    fireBase[i * 3 + 2] = -38 + Math.random() * 76;
  }
  firePos.set(fireBase);
  const fireGeo = new THREE.BufferGeometry();
  fireGeo.setAttribute('position', new THREE.BufferAttribute(firePos, 3).setUsage(THREE.DynamicDrawUsage));
  fireMat = new THREE.PointsMaterial({
    color: 0xd9ff7a, size: 0.3, transparent: true, opacity: 0,
    depthWrite: false, blending: THREE.AdditiveBlending, sizeAttenuation: true
  });
  firePoints = new THREE.Points(fireGeo, fireMat);
  firePoints.frustumCulled = false;
  scene.add(firePoints);

  const STAR_N = 1250;
  const starPos = new Float32Array(STAR_N * 3);
  const starCol = new Float32Array(STAR_N * 3);
  const cA = new THREE.Color(0xffffff);
  const cB = new THREE.Color(0xbcd0ff);
  const cT = new THREE.Color();
  for (let i = 0; i < STAR_N; i++) {
    const th = Math.random() * Math.PI * 2;
    const ph = Math.acos(2 * Math.random() - 1);
    const r = 300;
    starPos[i * 3] = r * Math.sin(ph) * Math.cos(th);
    starPos[i * 3 + 1] = Math.abs(r * Math.cos(ph)) * 0.9 + 4;
    starPos[i * 3 + 2] = r * Math.sin(ph) * Math.sin(th);
    cT.copy(cA).lerp(cB, Math.random());
    starCol[i * 3] = cT.r;
    starCol[i * 3 + 1] = cT.g;
    starCol[i * 3 + 2] = cT.b;
  }
  const starGeo = new THREE.BufferGeometry();
  starGeo.setAttribute('position', new THREE.BufferAttribute(starPos, 3));
  starGeo.setAttribute('color', new THREE.BufferAttribute(starCol, 3));
  starMat = new THREE.PointsMaterial({
    size: 2.5, sizeAttenuation: false, transparent: true,
    opacity: 0, depthWrite: false, blending: THREE.AdditiveBlending, fog: false, vertexColors: true
  });
  starPoints = new THREE.Points(starGeo, starMat);
  starPoints.frustumCulled = false;
  scene.add(starPoints);

  function collectMaterials() {
    allMaterials.length = 0;
    const seen = new Set();
    scene.traverse(o => {
      const m = o.material;
      if (m) {
        const arr = Array.isArray(m) ? m : [m];
        for (const mm of arr) {
          if (!seen.has(mm)) { seen.add(mm); allMaterials.push(mm); }
        }
      }
    });
  }

  function buildPointLights() {
    for (const l of pointLights) scene.remove(l);
    pointLights.length = 0;
    const wins = (G.pagoda && G.pagoda.windows) || [];
    for (const w of wins) {
      const pl = new THREE.PointLight(0xffc86b, 1.2, 14, 2);
      pl.position.set(w.x, w.y, w.z);
      pl.userData.base = 1.2;
      scene.add(pl);
      pointLights.push(pl);
    }
    const lants = G.lights || [];
    for (const l of lants) {
      const pl = new THREE.PointLight(0xffd27a, 1.0, 12, 2);
      pl.position.set(l.x, l.y, l.z);
      pl.userData.base = 1.0;
      scene.add(pl);
      pointLights.push(pl);
    }
  }

  function buildWater() {
    if (waterMesh) {
      scene.remove(waterMesh);
      waterMesh.geometry.dispose();
      waterMesh.material.dispose();
    }
    const pond = G.pond;
    const w = Math.max(4, pond.rx * 2 - 2);
    const d = Math.max(4, pond.rz * 2 - 2);
    const geo = new THREE.PlaneGeometry(w, d, 18, 12);
    geo.rotateX(-Math.PI / 2);
    waterBase = geo.attributes.position.array.slice();
    waterMat = new THREE.MeshStandardMaterial({
      color: 0x2e7d9c, transparent: true, opacity: 0.75, roughness: 0.15, metalness: 0.05
    });
    waterMesh = new THREE.Mesh(geo, waterMat);
    waterMesh.position.set(pond.cx, pond.waterY, pond.cz);
    waterMesh.receiveShadow = true;
    scene.add(waterMesh);
  }

  function flattenWater() {
    if (!waterMesh) return;
    const arr = waterMesh.geometry.attributes.position.array;
    for (let i = 0; i < arr.length; i += 3) arr[i + 1] = 0;
    waterMesh.geometry.attributes.position.needsUpdate = true;
  }

  function buildMist() {
    if (mistMesh) {
      scene.remove(mistMesh);
      mistMesh.geometry.dispose();
      mistMesh.material.dispose();
    }
    const pond = G.pond;
    const geo = new THREE.PlaneGeometry(pond.rx * 2 - 1, pond.rz * 2 - 1, 1, 1);
    geo.rotateX(-Math.PI / 2);
    mistMat = new THREE.MeshBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0, depthWrite: false });
    mistMesh = new THREE.Mesh(geo, mistMat);
    mistMesh.position.set(pond.cx, pond.waterY + 0.5, pond.cz);
    scene.add(mistMesh);
  }

  function buildKoi() {
    for (const k of koi) {
      scene.remove(k.g);
      k.bodyGeo.dispose();
      k.tailGeo.dispose();
      k.mat.dispose();
    }
    koi.length = 0;
    const pond = G.pond;
    const defs = [
      { cx: 0, cz: 0, rx: 5, rz: 3, speed: 0.35, phase: 0 },
      { cx: -3, cz: 2, rx: 3.5, rz: 2.2, speed: -0.5, phase: 2.1 },
      { cx: 4, cz: -2, rx: 6.5, rz: 4, speed: 0.28, phase: 4.2 }
    ];
    const cols = [0xe8641f, 0xf2ede4, 0xe8641f];
    defs.forEach((d, i) => {
      const g = new THREE.Group();
      const mat = new THREE.MeshStandardMaterial({ color: cols[i], roughness: 0.55 });
      const bodyGeo = new THREE.BoxGeometry(0.9, 0.28, 0.42);
      const tailGeo = new THREE.BoxGeometry(0.45, 0.18, 0.34);
      const body = new THREE.Mesh(bodyGeo, mat);
      const tail = new THREE.Mesh(tailGeo, mat);
      tail.position.set(-0.65, 0, 0);
      g.add(body);
      g.add(tail);
      g.traverse(o => { if (o.isMesh) o.castShadow = true; });
      scene.add(g);
      koi.push({ g, tail, mat, bodyGeo, tailGeo, cx: d.cx, cz: d.cz, rx: d.rx, rz: d.rz, speed: d.speed, phase: d.phase, y: pond.waterY - 0.4 });
    });
  }

  let lastVoxelMeshes = null;
  function mountVoxels() {
    if (lastVoxelMeshes) {
      scene.remove(lastVoxelMeshes.opaque);
      if (lastVoxelMeshes.emissive) scene.remove(lastVoxelMeshes.emissive);
      lastVoxelMeshes.opaque.geometry.dispose();
      lastVoxelMeshes.opaque.material.dispose();
      if (lastVoxelMeshes.emissive) {
        lastVoxelMeshes.emissive.geometry.dispose();
        lastVoxelMeshes.emissive.material.dispose();
      }
    }
    const built = G.S.build();
    voxelCount = built.count;
    scene.add(built.opaque);
    if (built.emissive) scene.add(built.emissive);
    lastVoxelMeshes = built;
  }

  const presets = {
    Overview: { pos: new THREE.Vector3(60, 45, 60), tgt: new THREE.Vector3(0, 2, 0) },
    Pagoda: { pos: new THREE.Vector3(36, 24, 12), tgt: null },
    Pond: { pos: new THREE.Vector3(-4, 27, 31), tgt: new THREE.Vector3(-14, 1, 10) },
    Torii: { pos: new THREE.Vector3(0, 8, 19), tgt: new THREE.Vector3(0, 5, 35) },
    Blossoms: { pos: new THREE.Vector3(-4, 20, 22), tgt: new THREE.Vector3(-17, 4, 8) }
  };
  function pagodaTgt() {
    const p = G.pagoda || { x: 14, z: -14, baseY: 8 };
    return new THREE.Vector3(p.x, p.baseY + 9, p.z);
  }

  const tween = {
    active: false, t: 0, dur: 1.4,
    fromPos: new THREE.Vector3(), toPos: new THREE.Vector3(),
    fromTgt: new THREE.Vector3(), toTgt: new THREE.Vector3()
  };

  let time = 10;
  let playing = true;
  let speed = 0.15;
  let wind = 0.8;
  let waterAnim = true;
  let dayF = 1, nightF = 0, dawnF = 0;
  let fpsSmooth = 60;
  const clock = new THREE.Clock();
  let elapsed = 0;

  function updateSky() {
    const e = Math.sin(Math.PI * (time - 6) / 12);
    dayF = clamp01(e * 2.2 + 0.18);
    nightF = clamp01(-e * 2.0 + 0.12);
    dawnF = clamp01(1 - Math.abs(e) * 2.4);
    skyCol.copy(SKY_NIGHT).lerp(SKY_DAY, dayF).lerp(SKY_DAWN, dawnF * 0.5);
    fogCol.copy(skyCol);
    scene.fog.near = 140 - nightF * 70;
    scene.fog.far = 330 - nightF * 180;
    const a = Math.PI * (time - 6) / 12;
    sun.position.set(Math.cos(a) * 90, Math.sin(a) * 110, 28);
    sun.intensity = Math.max(0, e) * 2.6;
    sun.color.copy(SUN_LOW).lerp(SUN_HIGH, clamp01(e * 1.7));
    hemi.intensity = 0.14 + dayF * 0.55 + nightF * 0.3;
    amb.intensity = 0.1 + dayF * 0.14 + nightF * 0.14;
    moon.intensity = nightF * 0.45;
    for (const pl of pointLights) pl.intensity = pl.userData.base * (0.3 + nightF * 2.2);
    if (waterMat) {
      waterMat.color.copy(WATER_DAY).lerp(WATER_NIGHT, nightF);
      waterMat.opacity = 0.72 + dawnF * 0.06;
    }
    if (starMat) starMat.opacity = nightF * 0.9;
    if (starPoints) starPoints.rotation.y = elapsed * 0.004;
  }

  function updateWater(t) {
    if (!waterMesh) return;
    const posAttr = waterMesh.geometry.attributes.position;
    const arr = posAttr.array;
    const n = posAttr.count;
    for (let i = 0; i < n; i++) {
      const x = waterBase[i * 3];
      const z = waterBase[i * 3 + 2];
      arr[i * 3 + 1] = Math.sin(x * 0.9 + t * 1.4) * 0.07 + Math.cos(z * 1.1 + t * 1.1) * 0.07;
    }
    posAttr.needsUpdate = true;
  }

  function updateKoi(t) {
    const pond = G.pond;
    for (let i = 0; i < koi.length; i++) {
      const k = koi[i];
      const a = k.phase + t * k.speed;
      const x = pond.cx + k.cx + Math.cos(a) * k.rx;
      const z = pond.cz + k.cz + Math.sin(a) * k.rz;
      const dx = -Math.sin(a) * k.rx * Math.sign(k.speed);
      const dz = Math.cos(a) * k.rz * Math.sign(k.speed);
      k.g.position.set(x, k.y + Math.sin(t * 2 + i * 1.7) * 0.08, z);
      k.g.rotation.y = Math.atan2(-dz, dx);
      k.tail.rotation.y = Math.sin(t * 6 + i) * 0.3;
    }
  }

  function updatePetals(dt, t) {
    const n = petalCount;
    const w = wind;
    for (let i = 0; i < n; i++) {
      py[i] -= pFall[i] * dt;
      pbx[i] += (w * 0.9 + Math.sin(t * 1.3 + pPhase[i]) * pSway[i]) * dt;
      pbz[i] += Math.cos(t * 1.1 + pPhase[i]) * pSway[i] * 0.6 * dt;
      if (py[i] < 0.6) randomizePetal(i, true);
      if (pbx[i] > 42) pbx[i] = -42; else if (pbx[i] < -42) pbx[i] = 42;
      if (pbz[i] > 42) pbz[i] = -42; else if (pbz[i] < -42) pbz[i] = 42;
      dummy.position.set(pbx[i] + Math.sin(t * 2 + pPhase[i]) * 0.35, py[i], pbz[i]);
      dummy.rotation.set(t * pRot[i], pPhase[i] * 6.283, t * pRot2[i]);
      dummy.updateMatrix();
      petals.setMatrixAt(i, dummy.matrix);
    }
    petals.instanceMatrix.needsUpdate = true;
  }

  function updateFireflies(t) {
    if (!firePoints) return;
    if (nightF <= 0.03) {
      firePoints.visible = false;
      return;
    }
    firePoints.visible = true;
    const pulse = 0.5 + 0.5 * Math.sin(t * 3);
    for (let i = 0; i < FLY_N; i++) {
      firePos[i * 3] = fireBase[i * 3] + Math.sin(t * 0.7 + i * 1.3) * 1.2;
      firePos[i * 3 + 1] = fireBase[i * 3 + 1] + Math.sin(t * 0.9 + i * 2.1) * 0.8;
      firePos[i * 3 + 2] = fireBase[i * 3 + 2] + Math.cos(t * 0.6 + i) * 1.2;
    }
    firePoints.geometry.attributes.position.needsUpdate = true;
    fireMat.opacity = nightF * (0.45 + 0.55 * pulse);
    fireMat.size = 0.22 + 0.16 * (0.5 + 0.5 * Math.sin(t * 2.2));
  }

  function updateMist(t) {
    if (!mistMesh) return;
    const mistF = clamp01(1 - Math.abs(time - 7) / 2.4);
    mistMat.opacity = mistF * (0.13 + 0.05 * Math.sin(t * 0.6));
  }

  function updateTween(dt) {
    if (!tween.active) return;
    tween.t += dt / tween.dur;
    const t = tween.t >= 1 ? 1 : tween.t;
    const k = t * t * (3 - 2 * t);
    camera.position.lerpVectors(tween.fromPos, tween.toPos, k);
    controls.target.lerpVectors(tween.fromTgt, tween.toTgt, k);
    if (tween.t >= 1) tween.active = false;
  }

  mountVoxels();
  buildPointLights();
  buildWater();
  buildMist();
  buildKoi();
  collectMaterials();
  console.log('Voxel count:', voxelCount);

  const loadingEl = document.getElementById('loading');
  if (loadingEl) loadingEl.classList.add('hide');

  window.addEventListener('resize', () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
  });

  function animate() {
    requestAnimationFrame(animate);
    const delta = Math.min(clock.getDelta(), 0.05);
    elapsed += delta;
    if (delta > 0) fpsSmooth = fpsSmooth * 0.95 + (1 / delta) * 0.05;
    if (playing) time = (time + speed * delta) % 24;
    updateSky();
    if (waterAnim) updateWater(elapsed);
    updateKoi(elapsed);
    updatePetals(delta, elapsed);
    updateFireflies(elapsed);
    updateMist(elapsed);
    updateTween(delta);
    controls.update();
    renderer.render(scene, camera);
  }
  animate();

  return {
    setTime(h) { time = ((h % 24) + 24) % 24; },
    getTime() { return time; },
    setPlaying(v) { playing = !!v; },
    setSpeed(x) { speed = Math.max(0, x); },
    setPetalDensity(n) {
      petalCount = Math.max(0, Math.min(PETAL_MAX, n | 0));
      petals.count = petalCount;
    },
    setWind(x) { wind = Math.max(0, Math.min(3, x)); },
    setAutoRotate(v) { controls.autoRotate = !!v; },
    toggleAutoRotate() { controls.autoRotate = !controls.autoRotate; return controls.autoRotate; },
    setShadows(v) {
      renderer.shadowMap.enabled = !!v;
      sun.castShadow = !!v;
      for (const m of allMaterials) m.needsUpdate = true;
    },
    setFireflies(v) { firePoints.visible = !!v; },
    setWaterAnim(v) {
      waterAnim = !!v;
      if (!waterAnim) flattenWater();
    },
    setWireframe(v) {
      for (const m of allMaterials) m.wireframe = !!v;
    },
    toggleNight() {
      const isNight = time >= 18 || time < 6;
      time = isNight ? 12 : 23;
    },
    goPreset(name) {
      const p = presets[name];
      if (!p) return;
      tween.fromPos.copy(camera.position);
      tween.fromTgt.copy(controls.target);
      if (name === 'Pagoda') {
        const t = pagodaTgt();
        tween.toPos.copy(p.pos);
        tween.toTgt.copy(t);
      } else {
        tween.toPos.copy(p.pos);
        tween.toTgt.copy(p.tgt);
      }
      tween.t = 0;
      tween.active = true;
    },
    resetView() {
      const p = presets.Overview;
      tween.fromPos.copy(camera.position);
      tween.fromTgt.copy(controls.target);
      tween.toPos.copy(p.pos);
      tween.toTgt.copy(p.tgt);
      tween.t = 0;
      tween.active = true;
    },
    regenerate(newSeed) {
      const oldS = G.S;
      G = G.buildAll(newSeed);
      oldS.dispose();
      mountVoxels();
      buildPointLights();
      buildWater();
      buildMist();
      buildKoi();
      collectMaterials();
      console.log('Voxel count:', voxelCount);
    },
    stats() {
      return { voxels: voxelCount, fps: Math.round(fpsSmooth), time: time };
    }
  };
}
