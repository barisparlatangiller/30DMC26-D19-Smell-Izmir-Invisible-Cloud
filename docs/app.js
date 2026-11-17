import * as THREE from 'three';
import { MapControls } from 'three/addons/controls/MapControls.js';

// ---------- constants ----------
const SX = 33000, SY = 22800, RES = 30, NX = 1100, NY = 760;     // UTM 35N box: E 491700–524700, N 4243500–4266300
const OG = 100, ONX = 330, ONY = 228;                              // odour grid
const TR = document.documentElement.lang === 'tr';
const L = (en, tr) => TR ? tr : en;
const Q = new URLSearchParams(location.search);
const FILM = Q.has('film');
const LITE = Q.has('lite') || (!FILM && Math.min(innerWidth, innerHeight) < 700);
const STEP = LITE ? 2 : 1;
const BG = '#121a2a';
const MONTHS = TR ? ['Oca','Şub','Mar','Nis','May','Haz','Tem','Ağu','Eyl','Eki','Kas','Ara'] : ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
const ODOUR = [[0,'#f6f0b8'],[0.35,'#f0dc72'],[0.6,'#e3c44a'],[0.85,'#b39a36'],[1,'#7f6d2a']];   // pale lemon → sulfur → olive brown
const fmt = n => n.toLocaleString(TR ? 'tr-TR' : 'en-GB');

if (FILM) { let a = 19190721; Math.random = () => { a |= 0; a = a + 0x6D2B79F5 | 0; let t = Math.imul(a ^ a >>> 15, 1 | a); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
const S = { day: Q.get('day') || '07', scen: 'b', h: +(Q.get('h') || 15), play: false, ex: 1.6, op: 0.75, t: 0 };
window.S = S;

// ---------- helpers ----------
async function pixels(url) {
  const b = await (await fetch(url)).blob();
  const bm = await createImageBitmap(b, { colorSpaceConversion: 'none', premultiplyAlpha: 'none' });
  const c = new OffscreenCanvas(bm.width, bm.height), g = c.getContext('2d', { willReadFrequently: true });
  g.drawImage(bm, 0, 0);
  return { w: bm.width, h: bm.height, d: g.getImageData(0, 0, bm.width, bm.height).data };
}
const hex = h => new THREE.Color(h);
const v3 = c => `vec3(${c.r.toFixed(4)},${c.g.toFixed(4)},${c.b.toFixed(4)})`;
function rampGLSL(name, stops) {
  let s = `vec3 ${name}(float v){\n`;
  for (let i = 0; i < stops.length - 1; i++) {
    const [a, ca] = stops[i], [b, cb] = stops[i+1];
    s += ` if(v<${b.toFixed(3)}) return mix(${v3(hex(ca))},${v3(hex(cb))},clamp((v-(${a.toFixed(3)}))/${(b-a).toFixed(3)},0.,1.));\n`;
  }
  return s + ` return ${v3(hex(stops[stops.length-1][1]))};\n}\n`;
}
function rampJS(v) {
  for (let i = 0; i < ODOUR.length - 1; i++) { const [a, ca] = ODOUR[i], [b, cb] = ODOUR[i+1];
    if (v < b || i === ODOUR.length - 2) return hex(ca).lerp(hex(cb), Math.min(1, Math.max(0, (v-a)/(b-a)))); }
}
// local coords: lx = E − 491700 (east), ly = 4266300 − N (south); scene x = lx − SX/2, z = ly − SY/2
const W3 = (lx, ly, z) => new THREE.Vector3(lx - SX/2, z, ly - SY/2);
function flipRows(d, w, h) { const o = new Uint8Array(d.length), rb = w*4; for (let y = 0; y < h; y++) o.set(d.subarray((h-1-y)*rb, (h-y)*rb), y*rb); return o; }

// ---------- renderer / scene ----------
const canvas = document.getElementById('c');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, preserveDrawingBuffer: FILM });
renderer.setPixelRatio(FILM ? (+Q.get('dpr') || 1) : Math.min(devicePixelRatio, 2));
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.setClearColor(BG);
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(36, 1, 20, 250000);
const controls = new MapControls(camera, canvas);
controls.enableDamping = !FILM; controls.maxPolarAngle = 1.38; controls.minDistance = 200; controls.maxDistance = 70000;
function resize() { renderer.setSize(innerWidth, innerHeight, false); camera.aspect = innerWidth / innerHeight;
  if (!FILM && innerWidth > 760) camera.setViewOffset(innerWidth, innerHeight, -194, 30, innerWidth, innerHeight); else camera.clearViewOffset();
  camera.updateProjectionMatrix(); }
addEventListener('resize', resize); resize();
const world = new THREE.Group(); scene.add(world);
const LIGHT = new THREE.Vector3(-0.55, 0.62, -0.55).normalize();
const FOG = hex(BG), FOGD = 90000;

// ---------- data ----------
const [demP, terrP, ST, SRC, MAH, mahP] = await Promise.all([
  pixels('data/dem.png'), pixels('data/terr.png'), fetch('data/stats.json').then(r => r.json()), fetch('data/sources.json').then(r => r.json()),
  fetch('data/mah.json').then(r => r.json()), pixels('data/mah.png')]);
const DEM = new Float32Array(NX*NY), SEA = new Uint8Array(NX*NY);
for (let i = 0; i < NX*NY; i++) { DEM[i] = (demP.d[i*4]*256 + demP.d[i*4+1]) / 50 - 20; SEA[i] = terrP.d[i*4+2] > 127 ? 1 : 0; }
function demAt(lx, ly) {
  let fx = lx / RES - 0.5, fy = ly / RES - 0.5;
  fx = Math.max(0, Math.min(NX - 1.001, fx)); fy = Math.max(0, Math.min(NY - 1.001, fy));
  const x = fx | 0, y = fy | 0, u = fx - x, v = fy - y, i = y*NX + x;
  return DEM[i]*(1-u)*(1-v) + DEM[i+1]*u*(1-v) + DEM[i+NX]*(1-u)*v + DEM[i+NX+1]*u*v;
}
const groundAt = (lx, ly) => Math.max(0, demAt(lx, ly));
const seaAt = (lx, ly) => SEA[Math.min(NY-1, Math.max(0, (ly/RES)|0))*NX + Math.min(NX-1, Math.max(0, (lx/RES)|0))];
const mahAt = (lx, ly) => { const c = Math.min(ONX-1, Math.max(0, (lx/OG)|0)), r = Math.min(ONY-1, Math.max(0, (ly/OG)|0)), i = (r*ONX + c)*4; return mahP.d[i]*256 + mahP.d[i+1]; };

const texL = new THREE.TextureLoader();
const loadTex = (u, srgb = true) => new Promise(r => texL.load(u, t => { if (srgb) t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 8; r(t); }, undefined, () => r(null)));
const [baseT] = await Promise.all([loadTex('data/base.jpg')]);
const terrT = new THREE.DataTexture(flipRows(terrP.d, NX, NY), NX, NY, THREE.RGBAFormat); terrT.magFilter = terrT.minFilter = THREE.LinearFilter; terrT.needsUpdate = true;

// odour atlas (24 hours, 6 × 4 tiles), one per day and scenario
const odourT = new THREE.DataTexture(new Uint8Array(ONX*6*ONY*4*4), ONX*6, ONY*4, THREE.RGBAFormat);
odourT.magFilter = odourT.minFilter = THREE.LinearFilter;
let ATLAS = null, HOURS = null, WIND = null;
const cache = {};
async function loadDay(day, scen) {
  const k = day + scen;
  if (!cache[k]) cache[k] = Promise.all([pixels(`data/odour/${day}/${scen}.png`), pixels(`data/odour/${day}/${scen}_hours.png`), cache['w'+day] || (cache['w'+day] = fetch(`data/wind/${day}.json`).then(r => r.json()))]);
  const [a, hrs, w] = await cache[k];
  if (S.day !== day || S.scen !== scen) return;
  ATLAS = a; HOURS = hrs; WIND = w;
  odourT.image.data.set(flipRows(a.d, a.w, a.h)); odourT.needsUpdate = true;
  onDay();
}
// odour index at a point and hour, CPU side (sqrt-scaled PNG → index)
function odourAt(lx, ly, h) {
  if (!ATLAS) return 0;
  const c = Math.min(ONX-1, Math.max(0, (lx/OG)|0)), r = Math.min(ONY-1, Math.max(0, (ly/OG)|0));
  const hh = ((h|0) % 24 + 24) % 24, x = (hh % 6)*ONX + c, y = ((hh/6)|0)*ONY + r;
  const v = ATLAS.d[(y*ATLAS.w + x)*4] / 255; return v*v;
}
// wind at a point (500 m grid, linear in time)
function windAt(lx, ly, h) {
  if (!WIND) return [0, 0];
  const nx = WIND.nx, ny = WIND.ny, H = WIND[S.scen];
  let fx = lx/500 - 0.5, fy = ly/500 - 0.5; fx = Math.max(0, Math.min(nx-1.001, fx)); fy = Math.max(0, Math.min(ny-1.001, fy));
  const x = fx|0, y = fy|0, u = fx-x, v = fy-y, i = y*nx + x;
  const h0 = (Math.floor(h) % 24 + 24) % 24, h1 = (h0 + 1) % 24, f = h - Math.floor(h);
  const bil = a => a[i]*(1-u)*(1-v) + a[i+1]*u*(1-v) + a[i+nx]*(1-u)*v + a[i+nx+1]*u*v;
  return [bil(H[h0][0])*(1-f) + bil(H[h1][0])*f, bil(H[h0][1])*(1-f) + bil(H[h1][1])*f];
}

// ---------- shaders: common ----------
const ODOUR_GLSL = `uniform sampler2D odT; uniform float hour;
  float odTile(vec2 uv, float h){ float c=mod(h,6.), r=floor(h/6.);
    vec2 t=clamp(uv,vec2(0.5/${ONX}.,0.5/${ONY}.),vec2(1.-0.5/${ONX}.,1.-0.5/${ONY}.));
    vec2 a=vec2((c+t.x)/6., 1.-(r+1.-t.y)/4.); float v=texture2D(odT,a).r; return v*v; }
  float odour(vec2 uv){ float h0=floor(hour), f=hour-h0; return mix(odTile(uv,mod(h0,24.)),odTile(uv,mod(h0+1.,24.)),f); }
  ${rampGLSL('odRamp', ODOUR)}`;
const NOISE = `float h21(vec2 p){ return fract(sin(dot(p,vec2(127.1,311.7)))*43758.5453); }
  float vn(vec2 p){ vec2 i=floor(p),f=fract(p); f=f*f*(3.-2.*f); return mix(mix(h21(i),h21(i+vec2(1,0)),f.x),mix(h21(i+vec2(0,1)),h21(i+vec2(1,1)),f.x),f.y); }
  float fbm(vec2 p){ return 0.5*vn(p)+0.28*vn(p*2.03)+0.14*vn(p*4.1)+0.08*vn(p*8.3); }`;
const uniCommon = () => ({ ex: { value: S.ex }, light: { value: LIGHT }, fogC: { value: FOG }, fogD: { value: FOGD }, odT: { value: odourT }, hour: { value: S.h } });

// ---------- terrain ----------
function buildTerrain() {
  const nx = Math.floor(NX / STEP), ny = Math.floor(NY / STEP), cell = RES * STEP;
  const pos = new Float32Array(nx*ny*3), uv = new Float32Array(nx*ny*2);
  for (let r = 0; r < ny; r++) for (let c = 0; c < nx; c++) {
    const i = r*nx + c, lx = (c+0.5)*cell, ly = (r+0.5)*cell;
    pos[i*3] = lx - SX/2; pos[i*3+1] = demAt(lx, ly); pos[i*3+2] = ly - SY/2;
    uv[i*2] = lx/SX; uv[i*2+1] = 1 - ly/SY;
  }
  const idx = new Uint32Array((nx-1)*(ny-1)*6); let k = 0;
  for (let r = 0; r < ny-1; r++) for (let c = 0; c < nx-1; c++) { const a = r*nx+c, b = a+1, d = a+nx, e = d+1; idx[k++] = a; idx[k++] = d; idx[k++] = b; idx[k++] = b; idx[k++] = d; idx[k++] = e; }
  const g = new THREE.BufferGeometry();
  g.setAttribute('position', new THREE.BufferAttribute(pos, 3)); g.setAttribute('uv', new THREE.BufferAttribute(uv, 2));
  g.setIndex(new THREE.BufferAttribute(idx, 1)); g.computeVertexNormals();
  return { g, nx, ny };
}
const COMMON = `uniform float ex; varying vec3 vN; varying vec2 vUv; varying vec3 vW; varying float vD;`;
const terrainMat = new THREE.ShaderMaterial({
  uniforms: { ...uniCommon(), tex: { value: baseT }, terr: { value: terrT }, showSlope: { value: 0 }, tint: { value: 1 } },
  vertexShader: `${COMMON} void main(){ vUv=uv; vN=normalize(vec3(normal.x*ex,normal.y,normal.z*ex));
    vec4 w=modelMatrix*vec4(position,1.); vW=w.xyz; vec4 mv=viewMatrix*w; vD=-mv.z; gl_Position=projectionMatrix*mv; }`,
  fragmentShader: `${COMMON} uniform sampler2D tex,terr; uniform vec3 light,fogC; uniform float fogD,showSlope,tint; ${ODOUR_GLSL}
    void main(){
      vec3 n=normalize(vN); float lam=max(dot(n,light),0.);
      vec4 tr=texture2D(terr,vUv); float hs=tr.r, sl=tr.g*45., sea=tr.b;
      vec3 col=texture2D(tex,vUv).rgb;
      if(sea<0.5) col*=mix(0.55,1.18,hs)*(0.85+0.22*lam);
      else col*=0.92+0.1*lam;
      if(showSlope>0.5 && sea<0.5){ float s=smoothstep(4.,30.,sl); col=mix(col,mix(vec3(0.36,0.42,0.58),vec3(0.86,0.84,0.92),s),0.18+0.5*s); }
      float o=odour(vUv);
      col=mix(col,odRamp(o)*0.85,clamp(o*1.1,0.,0.55)*tint);
      col=mix(col,fogC,smoothstep(0.,1.,vD/fogD)*0.85);
      gl_FragColor=vec4(col,1.);
      #include <colorspace_fragment>
    }`
});
const TG = buildTerrain();
const terrain = new THREE.Mesh(TG.g, terrainMat); world.add(terrain);
// skirt: the box sits like a model on the dark table
{
  const P = TG.g.attributes.position.array, nx = TG.nx, ny = TG.ny, edge = [];
  for (let c = 0; c < nx; c++) edge.push(c);
  for (let r = 1; r < ny; r++) edge.push(r*nx + nx-1);
  for (let c = nx-2; c >= 0; c--) edge.push((ny-1)*nx + c);
  for (let r = ny-2; r > 0; r--) edge.push(r*nx);
  edge.push(0);
  const pos = [], col = [], lo = -60;
  for (let i = 0; i < edge.length-1; i++) {
    const a = edge[i], b = edge[i+1], ax = P[a*3], ay = P[a*3+1], az = P[a*3+2], bx = P[b*3], by = P[b*3+1], bz = P[b*3+2];
    pos.push(ax,ay,az, bx,by,bz, ax,lo,az,  bx,by,bz, bx,lo,bz, ax,lo,az);
    for (const y of [ay,by,lo,by,lo,lo]) { const t = y <= lo ? 0.08 : (y < 0.5 ? 0.16 : 0.2); col.push(t*0.95, t*1.05, t*1.35); }
  }
  const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3)); g.setAttribute('color', new THREE.Float32BufferAttribute(col, 3));
  world.add(new THREE.Mesh(g, new THREE.MeshBasicMaterial({ vertexColors: true, side: THREE.DoubleSide })));
}

// ---------- buildings: oriented boxes, tinted where the cloud sits ----------
const instMat = (vs, colorExpr) => new THREE.ShaderMaterial({
  uniforms: { ...uniCommon(), show: { value: 1 } },
  vertexShader: `${COMMON} ${ODOUR_GLSL} attribute vec4 a1; attribute vec4 a2; varying vec3 vC; varying float vO; varying vec3 vNo;
    void main(){ vec3 p=position; vec3 nn=normal; ${vs}
      vec4 w=modelMatrix*vec4(p,1.); vW=w.xyz; vec4 mv=viewMatrix*w; vD=-mv.z; gl_Position=projectionMatrix*mv; }`,
  fragmentShader: `${COMMON} uniform vec3 light,fogC; uniform float fogD; varying vec3 vC; varying float vO; varying vec3 vNo; ${rampGLSL('odR', ODOUR)}
    void main(){ vec3 n=normalize(vNo); float lam=max(dot(n,light),0.);
      vec3 c=vC*(0.5+0.62*lam); ${colorExpr}
      c=mix(c,fogC,smoothstep(0.,1.,vD/fogD)*0.85); gl_FragColor=vec4(c,1.);
      #include <colorspace_fragment>
    }` });
let bld = null;
const bldReady = (async () => {
  const q = new Uint16Array(await fetch('data/bld.bin').then(r => r.arrayBuffer())), n = q.length / 6;
  const box = new THREE.BoxGeometry(1, 1, 1); box.translate(0, 0.5, 0);
  const g = new THREE.InstancedBufferGeometry(); g.index = box.index; g.attributes.position = box.attributes.position; g.attributes.normal = box.attributes.normal;
  const a1 = new Float32Array(n*4), a2 = new Float32Array(n*4);
  for (let i = 0; i < n; i++) {
    const lx = q[i*6]/2, ly = q[i*6+1]/2;
    a1[i*4] = lx - SX/2; a1[i*4+1] = groundAt(lx, ly) - 1.5; a1[i*4+2] = ly - SY/2; a1[i*4+3] = q[i*6+4]/10000*Math.PI;
    a2[i*4] = Math.max(2.5, q[i*6+2]/10); a2[i*4+1] = Math.max(2.5, q[i*6+3]/10); a2[i*4+2] = q[i*6+5]/10 + 1.5; a2[i*4+3] = (lx/SX);
  }
  g.setAttribute('a1', new THREE.InstancedBufferAttribute(a1, 4)); g.setAttribute('a2', new THREE.InstancedBufferAttribute(a2, 4)); g.instanceCount = n;
  const m = instMat(`float ca=cos(a1.w), sa=sin(a1.w);
      vec2 lp=vec2(p.x*a2.x, p.z*a2.y); vec2 wp=vec2(lp.x*ca + lp.y*sa, -lp.x*sa + lp.y*ca);
      vec2 wn=vec2(nn.x*ca + nn.z*sa, -nn.x*sa + nn.z*ca);
      vNo=normalize(vec3(wn.x*ex, nn.y, wn.y*ex));
      vec2 uv=vec2((a1.x+${SX/2}.)/${SX}., 1.-(a1.z+${SY/2}.)/${SY}.);
      vO=odour(uv);
      float roof=step(0.99,p.y);
      vC=mix(vec3(0.80,0.75,0.66), vec3(0.88,0.84,0.76), roof);
      vC=mix(vC, odRamp(vO), clamp(vO*1.25,0.,0.85)*(0.55+0.45*roof));
      p=vec3(a1.x+wp.x, a1.y+p.y*a2.z, a1.z+wp.y);`, '');
  bld = new THREE.Mesh(g, m); bld.frustumCulled = false; bld.renderOrder = 1;
  bld.visible = document.getElementById('tBd').checked; world.add(bld);
})();

// ---------- trees ----------
let trees = null;
const treesReady = (async () => {
  const q = new Uint16Array(await fetch('data/trees.bin').then(r => r.arrayBuffer())), n0 = q.length / 4;
  const every = LITE ? 3 : 1, n = Math.floor(n0 / every);
  const cone = new THREE.ConeGeometry(1, 1, 7, 1, false); cone.translate(0, 0.5, 0);
  const g = new THREE.InstancedBufferGeometry(); g.index = cone.index; g.attributes.position = cone.attributes.position; g.attributes.normal = cone.attributes.normal;
  const a1 = new Float32Array(n*4), a2 = new Float32Array(n*4);
  for (let j = 0; j < n; j++) { const i = j*every, lx = q[i*4]/2, ly = q[i*4+1]/2, h = Math.max(3, q[i*4+2]/10), kind = q[i*4+3];
    a1[j*4] = lx - SX/2; a1[j*4+1] = groundAt(lx, ly) - 1; a1[j*4+2] = ly - SY/2; a1[j*4+3] = Math.random();
    a2[j*4] = h * (kind === 2 ? 0.36 : 0.42); a2[j*4+1] = h; a2[j*4+2] = kind; a2[j*4+3] = 0; }
  g.setAttribute('a1', new THREE.InstancedBufferAttribute(a1, 4)); g.setAttribute('a2', new THREE.InstancedBufferAttribute(a2, 4)); g.instanceCount = n;
  const m = instMat(`vNo=normalize(vec3(nn.x*ex,nn.y,nn.z*ex)); vO=0.;
      float t=0.75+0.3*p.y; vC=mix(vec3(0.17,0.33,0.22), vec3(0.24,0.42,0.27), a1.w)*t;
      p=vec3(a1.x+p.x*a2.x, a1.y+p.y*a2.y, a1.z+p.z*a2.x);`, '');
  trees = new THREE.Mesh(g, m); trees.frustumCulled = false; world.add(trees);
})();

// ---------- the cloud: three translucent sheets that rise and thicken with the odour ----------
const cloudMat = new THREE.ShaderMaterial({
  transparent: true, depthWrite: false, side: THREE.DoubleSide,
  uniforms: { ...uniCommon(), op: { value: S.op }, t: { value: 0 }, lift: { value: 0 }, layerA: { value: 1 }, drift: { value: new THREE.Vector2() }, camP: { value: new THREE.Vector3() } },
  vertexShader: `${COMMON} ${ODOUR_GLSL} uniform float lift; varying float vO;
    void main(){ vUv=uv; vO=odour(uv); vec3 p=position; p.y+=6.+lift*(0.25+vO*1.6)*1.0; vN=vec3(0.,1.,0.);
      vec4 w=modelMatrix*vec4(p,1.); vW=w.xyz; vec4 mv=viewMatrix*w; vD=-mv.z; gl_Position=projectionMatrix*mv; }`,
  fragmentShader: `${COMMON} uniform float op,t,fogD,layerA; uniform vec2 drift; uniform vec3 fogC; varying float vO; ${rampGLSL('odR', ODOUR)} ${NOISE}
    void main(){
      if(vO<0.012) discard;
      vec2 P=vec2(vW.x,vW.z)/420.;
      float m=fbm(P - drift*t*0.9 + layerA*3.1), m2=fbm(P*2.3 - drift*t*1.6 + 9.2);
      float d=smoothstep(0.012,0.5,vO);
      vec3 c=odR(clamp(vO*1.15,0.,1.))*(0.9+0.2*m);
      float a=op*layerA*d*(0.35+0.75*m*m2*1.6);
      c=mix(c,fogC,smoothstep(0.,1.,vD/fogD)*0.8);
      gl_FragColor=vec4(c,clamp(a,0.,0.85));
      #include <colorspace_fragment>
    }`
});
function buildCloud() {
  const nx = ONX + 1, ny = ONY + 1, pos = new Float32Array(nx*ny*3), uv = new Float32Array(nx*ny*2);
  for (let r = 0; r < ny; r++) for (let c = 0; c < nx; c++) {
    const i = r*nx + c, lx = Math.min(SX, c*OG), ly = Math.min(SY, r*OG);
    let z = 0; for (const [dx, dy] of [[0,0],[-60,0],[60,0],[0,-60],[0,60]]) z = Math.max(z, groundAt(lx+dx, ly+dy));
    pos[i*3] = lx - SX/2; pos[i*3+1] = z; pos[i*3+2] = ly - SY/2; uv[i*2] = lx/SX; uv[i*2+1] = 1 - ly/SY;
  }
  const idx = []; for (let r = 0; r < ny-1; r++) for (let c = 0; c < nx-1; c++) { const a = r*nx+c, b = a+1, d = a+nx, e = d+1; idx.push(a, d, b, b, d, e); }
  const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.BufferAttribute(pos, 3)); g.setAttribute('uv', new THREE.BufferAttribute(uv, 2)); g.setIndex(idx);
  return g;
}
const cloudG = buildCloud(), cloud = new THREE.Group();
[[8, 0.55], [28, 0.42], [55, 0.3]].forEach(([lift, a], i) => {
  const m = cloudMat.clone(); m.uniforms = THREE.UniformsUtils.clone(cloudMat.uniforms); m.uniforms.odT.value = odourT;
  m.uniforms.lift.value = lift; m.uniforms.layerA.value = a; const mesh = new THREE.Mesh(cloudG, m); mesh.renderOrder = 3 + i; cloud.add(mesh);
});
world.add(cloud);
const cloudMats = cloud.children.map(c => c.material);

// ---------- drift: comet particles from the sources, carried by this hour's wind ----------
const NP = FILM ? 5200 : (LITE ? 1800 : 4200), TRAIL = 16, TIMESCALE = 240;
const SP = [];      // [lx, ly, r, cumulative weight]
let wsum = 0;
for (const s of SRC) { wsum += s.w; SP.push([s.x - 491700, 4266300 - s.y, s.r, wsum, 1]); }
const GULF = ST.gulfpts;
let gulfW = 0;
function spawn(p) {
  const tot = wsum + gulfW;
  const r = Math.random() * tot;
  if (r > wsum) { const g = GULF[(Math.random()*GULF.length)|0]; p.x = g[0] + (Math.random()-0.5)*60; p.y = g[1] + (Math.random()-0.5)*60; p.g = 1; }
  else { const s = SP.find(s => s[3] >= r); const a = Math.random()*6.283, d = s[2]*Math.sqrt(Math.random()); p.x = s[0] + Math.cos(a)*d; p.y = s[1] + Math.sin(a)*d; p.g = 0; }
  p.age = 0; p.life = 4 + Math.random()*5; p.tr = [];
}
const parts = Array.from({ length: NP }, () => { const p = {}; spawn(p); p.age = Math.random()*p.life; return p; });
const NV = NP*TRAIL;
const pPos = new Float32Array(NV*3), pCol = new Float32Array(NV*4), pSize = new Float32Array(NV);
const pGeo = new THREE.BufferGeometry();
pGeo.setAttribute('position', new THREE.BufferAttribute(pPos, 3).setUsage(THREE.DynamicDrawUsage));
pGeo.setAttribute('color', new THREE.BufferAttribute(pCol, 4).setUsage(THREE.DynamicDrawUsage));
pGeo.setAttribute('size', new THREE.BufferAttribute(pSize, 1).setUsage(THREE.DynamicDrawUsage));
const pMat = new THREE.ShaderMaterial({ transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, uniforms: { scale: { value: 1 } },
  vertexShader: `attribute vec4 color; attribute float size; uniform float scale; varying vec4 vC;
    void main(){ vC=color; vec4 mv=modelViewMatrix*vec4(position,1.); gl_PointSize=clamp(size*scale/-mv.z,1.5,7.); gl_Position=projectionMatrix*mv; }`,
  fragmentShader: `varying vec4 vC; void main(){ vec2 d=gl_PointCoord-0.5; float r=length(d); if(r>0.5) discard; gl_FragColor=vec4(vC.rgb*vC.a*smoothstep(0.5,0.15,r),1.);
    #include <colorspace_fragment>
  }` });
const pts = new THREE.Points(pGeo, pMat); pts.frustumCulled = false; pts.renderOrder = 7; world.add(pts);
const PC = hex('#f2dc6e'), PG = hex('#9fd3c8');
function stepParticles(dt) {
  for (let j = 0; j < NP; j++) {
    const p = parts[j]; p.age += dt;
    if (p.age > p.life || p.x < 0 || p.x > SX || p.y < 0 || p.y > SY) { spawn(p); continue; }
    const [u, v] = windAt(p.x, p.y, S.h);
    const tb = 0.6 + 0.3*Math.hypot(u, v);
    p.x += (u*TIMESCALE + (Math.random()-0.5)*tb*TIMESCALE*0.9)*dt; p.y += (-v*TIMESCALE + (Math.random()-0.5)*tb*TIMESCALE*0.9)*dt;
    p.tr.unshift([p.x, p.y, groundAt(p.x, p.y)]);
    if (p.tr.length > TRAIL) p.tr.pop();
  }
  let o = 0;
  for (let j = 0; j < NP; j++) {
    const p = parts[j], fade = Math.min(1, p.age/0.7, (p.life - p.age)/1.2);
    const c = p.g ? PG : PC;
    for (let s = 0; s < TRAIL; s++, o++) {
      const a = p.tr[s];
      if (!a) { pCol[o*4+3] = 0; pSize[o] = 0; continue; }
      pPos[o*3] = a[0] - SX/2; pPos[o*3+1] = a[2] + 34; pPos[o*3+2] = a[1] - SY/2;
      const tt = 1 - s/TRAIL;
      pCol[o*4] = c.r; pCol[o*4+1] = c.g; pCol[o*4+2] = c.b; pCol[o*4+3] = fade*tt*(p.g ? 0.38 : 0.62);
      pSize[o] = 70*(0.35 + 0.65*tt);
    }
  }
  pGeo.attributes.position.needsUpdate = true; pGeo.attributes.color.needsUpdate = true; pGeo.attributes.size.needsUpdate = true;
}

// ---------- labels ----------
const SHORT = { 'Çiğli Atıksu Arıtma Tesisi': L('Çiğli wastewater plant', 'Çiğli Atıksu Arıtma'), 'Harmandalı Katı Atık Depolama Alanı': L('Harmandalı landfill', 'Harmandalı Çöplüğü'),
  'Karşıyaka Katı Atık Transfer İstasyonu': L('Transfer station', 'Transfer istasyonu'), 'Meles Deresi ağzı': L('Meles mouth', 'Meles ağzı') };
const LABELS = ST.labels.map(([t, lx, ly, cls]) => ({ t: cls === 'water' && !TR ? (t === 'İzmir Körfezi' ? 'Gulf of İzmir' : 'Inner gulf') : t, lx, ly, cls, z: 40 }));
for (const s of SRC) if (s.w >= 0.3) LABELS.push({ t: SHORT[s.name] || s.name.replace(' ağzı', ''), lx: s.x - 491700, ly: 4266300 - s.y, cls: 'src', z: 20, src: 1, minor: !SHORT[s.name] });
const lblBox = document.getElementById('labels');
for (const l of LABELS) { l.d = document.createElement('div'); l.d.className = 'lbl ' + l.cls; l.d.textContent = l.t; lblBox.appendChild(l.d); }
const _v = new THREE.Vector3();
let showSrc = true;
function placeLabels() {
  const w = innerWidth, h = innerHeight, dist = camera.position.distanceTo(controls.target);
  for (const l of LABELS) {
    _v.set(l.lx - SX/2, (groundAt(l.lx, l.ly) + l.z) * S.ex, l.ly - SY/2).project(camera);
    const vis = _v.z < 1 && Math.abs(_v.x) < 1.05 && Math.abs(_v.y) < 1.05 && (!l.src || showSrc) && !(l.minor && dist > 26000);
    l.d.style.display = vis ? '' : 'none';
    if (vis) l.d.style.transform = `translate(${l.src ? '0' : '-50%'},-50%) translate(${(_v.x*0.5+0.5)*w}px,${(-_v.y*0.5+0.5)*h}px)`;
  }
}

// ---------- legend ----------
function roseSVG() {
  const f = ST.rose.freq, mx = Math.max(...f), R = 34;
  let s = `<svg class="rose" width="96" height="96" viewBox="-48 -48 96 96"><circle r="${R}" fill="none" stroke="#3a4562"/><circle r="${R/2}" fill="none" stroke="#2c3650"/>`;
  f.forEach((v, i) => { const a0 = (i*22.5 - 9 - 90)*Math.PI/180, a1 = (i*22.5 + 9 - 90)*Math.PI/180, r = R*v/mx;
    s += `<path d="M0 0 L${(Math.cos(a0)*r).toFixed(1)} ${(Math.sin(a0)*r).toFixed(1)} A${r} ${r} 0 0 1 ${(Math.cos(a1)*r).toFixed(1)} ${(Math.sin(a1)*r).toFixed(1)}Z" fill="#5fb3b8" opacity=".8"/>`; });
  return s + `<text y="-${R+5}" text-anchor="middle" font-size="9" fill="#aab0be">N</text></svg>`;
}
document.getElementById('legend').innerHTML = `
  <h4>${L('Odour index (scenario)', 'Koku indeksi (senaryo)')}</h4>
  <div class="ramp"></div>
  <div class="tick mono"><span>${L('faint', 'hafif')}</span><span>${L('noticeable', 'belirgin')}</span><span>${L('strong', 'güçlü')}</span></div>
  <div class="lg-row"><i class="dot" style="background:#e3c44a"></i>${L('Candidate odour source', 'Olası koku kaynağı')}</div>
  <div class="lg-row"><i class="sw" style="background:#d6cdbb"></i>${L('Buildings · tinted inside the cloud', 'Binalar · bulut içindeyse renklenir')}</div>
  <div class="lg-row"><i class="sw" style="background:#2f5a3c"></i>${L('Trees', 'Ağaçlar')}</div>
  <div class="lg-row"><i class="sw" style="background:#0f3a44"></i>${L('Gulf', 'Körfez')}</div>
  <h4 style="margin-top:10px">${L('Where the wind comes from · year', 'Rüzgârın geldiği yön · yıl')}</h4>${roseSVG()}`;

// ---------- camera ----------
const VIEWS = {
  all: { p: W3(14500, 47500, 17500), t: W3(17000, 10500, 0) },
  cigli: { p: W3(6600, 15200, 3800), t: W3(10200, 8600, 0) },
  konak: { p: W3(14500, 21000, 3300), t: W3(16200, 14300, 30) },
  bornova: { p: W3(24000, 19000, 4200), t: W3(25600, 10600, 40) },
};
function setView(v, dur = 1.6) {
  if (FILM || dur === 0) { camera.position.copy(v.p); controls.target.copy(v.t); controls.update(); return; }
  const p0 = camera.position.clone(), t0 = controls.target.clone(), st = performance.now();
  (function an() { const u = Math.min(1, (performance.now()-st)/(dur*1000)), e = u<.5 ? 4*u*u*u : 1-Math.pow(-2*u+2, 3)/2;
    camera.position.lerpVectors(p0, v.p, e); controls.target.lerpVectors(t0, v.t, e); if (u < 1) requestAnimationFrame(an); })();
}
function flyTo(lx, ly) { const z = groundAt(lx, ly); setView({ p: W3(lx - 1200, ly + 3800, z + 2600), t: W3(lx, ly, z) }); }
setView(VIEWS.all, 0);

// ---------- UI ----------
const $ = id => document.getElementById(id);
const allMats = () => [terrainMat, ...cloudMats, bld && bld.material, trees && trees.material].filter(Boolean);
function applyEx() { world.scale.y = S.ex; for (const m of allMats()) m.uniforms.ex.value = S.ex; $('exv').textContent = S.ex.toFixed(1)+'×'; }
const COMPASS = TR ? ['K','KD','D','GD','G','GB','B','KB'] : ['N','NE','E','SE','S','SW','W','NW'];
const fromDir = d => COMPASS[Math.round(((d % 360) + 360) % 360 / 45) % 8];
function setHour(h) {
  S.h = ((h % 24) + 24) % 24;
  for (const m of allMats()) if (m.uniforms.hour) m.uniforms.hour.value = S.h;
  const hh = Math.floor(S.h), mm = Math.floor((S.h - hh)*60/10)*10;
  $('tClock').textContent = `${String(hh).padStart(2,'0')}:${String(mm).padStart(2,'0')}`;
  if (+$('rHour').value !== S.h) $('rHour').value = S.h;
  if (WIND) { const i = hh, ws = WIND.ws[i], wd = WIND.wd[i];
    $('tWind').textContent = `${L('wind', 'rüzgâr')} ${ws.toLocaleString(TR ? 'tr-TR' : 'en-GB')} m/s ${L('from', '')} ${fromDir(wd)}${TR ? ' yönünden' : ''} · ${Math.round(WIND.T[i])} °C`; }
  const dv = new THREE.Vector2(); if (WIND) { const th = WIND.wd[hh]*Math.PI/180, ws = WIND.ws[hh]; dv.set(-Math.sin(th)*ws*0.05, Math.cos(th)*ws*0.05); }
  for (const m of cloudMats) m.uniforms.drift.value.copy(dv);
  drawChart();
}
applyEx();
// day chips
const DAYS = ST.days_order;
$('days').innerHTML = DAYS.map(m => `<button data-d="${m}" class="${m === S.day ? 'on' : ''}" role="tab">21 ${MONTHS[+m-1]}</button>`).join('');
$('days').querySelectorAll('button').forEach(b => b.onclick = () => { S.day = b.dataset.d; $('days').querySelectorAll('button').forEach(x => x.classList.toggle('on', x === b)); loadDay(S.day, S.scen); });
document.querySelectorAll('#scenSeg button').forEach(b => b.onclick = () => {
  document.querySelectorAll('#scenSeg button').forEach(x => x.classList.toggle('on', x === b)); S.scen = b.dataset.s; loadDay(S.day, S.scen); });
$('rHour').oninput = e => setHour(+e.target.value);
$('bPlay').onclick = () => { S.play = !S.play; $('bPlay').textContent = S.play ? '❚❚' : '▶'; $('bPlay').setAttribute('aria-label', S.play ? L('Pause', 'Durdur') : L('Play', 'Oynat')); };
$('tOd').onchange = e => { cloud.visible = e.target.checked; terrainMat.uniforms.tint.value = e.target.checked ? 1 : 0; };
$('tPa').onchange = e => pts.visible = e.target.checked;
$('tBd').onchange = e => { if (bld) bld.visible = e.target.checked; };
$('tTr').onchange = e => { if (trees) trees.visible = e.target.checked; };
$('tSl').onchange = e => terrainMat.uniforms.showSlope.value = e.target.checked ? 1 : 0;
$('tSo').onchange = e => showSrc = e.target.checked;
$('rOp').oninput = e => { S.op = +e.target.value; for (const m of cloudMats) m.uniforms.op.value = S.op; $('opO').textContent = Math.round(S.op*100)+'%'; };
$('rEx').oninput = e => { S.ex = +e.target.value; applyEx(); };
document.querySelectorAll('.mapbar [data-v]').forEach(b => b.onclick = () => setView(VIEWS[b.dataset.v]));

// chart: land under the cloud by hour, both scenarios
function drawChart() {
  const c = $('chart'), g = c.getContext('2d'), Wc = c.width, Hc = c.height, pad = [34, 10, 22, 16];
  const d = ST.days[S.day]; if (!d) return;
  const A = d[S.scen].land_km2_by_hour, B = d[S.scen === 'b' ? 'o' : 'b'].land_km2_by_hour;
  const mx = Math.max(10, ...ST.days_order.flatMap(m => ST.days[m].b.land_km2_by_hour)) * 1.05;
  const X = i => pad[0] + (Wc - pad[0] - pad[1]) * i / 23, Y = v => Hc - pad[2] - (Hc - pad[2] - pad[3]) * v / mx;
  g.clearRect(0, 0, Wc, Hc);
  g.font = '19px "DM Mono"'; g.fillStyle = '#7c8496'; g.strokeStyle = '#2c3650'; g.lineWidth = 1;
  for (const v of [0, Math.round(mx/2/10)*10, Math.floor(mx/10)*10]) { g.beginPath(); g.moveTo(pad[0], Y(v)); g.lineTo(Wc - pad[1], Y(v)); g.stroke(); g.fillText(v, 0, Y(v) + 6); }
  for (const h of [0, 6, 12, 18, 23]) g.fillText(String(h).padStart(2, '0'), X(h) - 10, Hc - 2);
  g.beginPath(); B.forEach((v, i) => g.lineTo(X(i), Y(v))); g.strokeStyle = 'rgba(170,176,190,.45)'; g.setLineDash([5, 5]); g.lineWidth = 2; g.stroke(); g.setLineDash([]);
  g.beginPath(); g.moveTo(X(0), Y(0)); A.forEach((v, i) => g.lineTo(X(i), Y(v))); g.lineTo(X(23), Y(0));
  const gr = g.createLinearGradient(0, Y(mx), 0, Y(0)); gr.addColorStop(0, 'rgba(227,196,74,.55)'); gr.addColorStop(1, 'rgba(227,196,74,.05)'); g.fillStyle = gr; g.fill();
  g.beginPath(); A.forEach((v, i) => g.lineTo(X(i), Y(v))); g.strokeStyle = '#e3c44a'; g.lineWidth = 3; g.stroke();
  const hx = X(Math.min(23, S.h)); g.strokeStyle = '#ece6d6'; g.lineWidth = 2; g.beginPath(); g.moveTo(hx, pad[3]); g.lineTo(hx, Hc - pad[2]); g.stroke();
  const i0 = Math.min(23, Math.round(S.h)); g.fillStyle = '#ece6d6'; g.font = '20px "DM Mono"';
  const lbl = `${A[i0].toLocaleString(TR ? 'tr-TR' : 'en-GB')} km²`; g.fillText(lbl, Math.min(hx + 8, Wc - pad[1] - g.measureText(lbl).width), pad[3] + 16);
}
// ranking
{
  const top = ST.top_mahalle, mx = top[0].h;
  $('rank').innerHTML = top.map((m, i) => `<li data-i="${i}"><span>${m.n.replace(' Mahallesi', '')}<small>${m.d || ''}${m.d ? ' · ' : ''}${fmt(m.b)} ${L('buildings', 'bina')}</small></span><i class="bar" style="width:${(m.h/mx*100).toFixed(0)}%"></i><b class="mono">${m.h.toLocaleString(TR ? 'tr-TR' : 'en-GB', { maximumFractionDigits: 1 })} ${L('h', 'sa')}</b></li>`).join('');
  $('rank').querySelectorAll('li').forEach(li => li.onclick = () => { const m = top[+li.dataset.i]; const k = MAH.find(x => x.n === m.n && x.c[0] === m.c[0]) || m; flyTo(k.c[0], k.c[1]); });
}

// click: what the scenario says about this place
const ray = new THREE.Raycaster();
function pick(ev) {
  const r = canvas.getBoundingClientRect(), m = new THREE.Vector2(((ev.clientX-r.left)/r.width)*2-1, -((ev.clientY-r.top)/r.height)*2+1);
  ray.setFromCamera(m, camera); const hit = ray.intersectObject(terrain)[0]; if (!hit) return null;
  const p = world.worldToLocal(hit.point.clone()); return { lx: p.x + SX/2, ly: p.z + SY/2 };
}
const WORD = v => v < 0.03 ? L('no smell', 'koku yok') : v < 0.15 ? L('faint', 'hafif') : v < 0.4 ? L('noticeable', 'belirgin') : L('strong', 'güçlü');
let lastPick = null;
function showDetail(p) {
  lastPick = p; if (!p || !ATLAS) return;
  const id = mahAt(p.lx, p.ly), m = id ? MAH[id-1] : null, sea = seaAt(p.lx, p.ly);
  const now = odourAt(p.lx, p.ly, S.h), strip = Array.from({ length: 24 }, (_, h) => odourAt(p.lx, p.ly, h));
  const hrs = strip.filter(v => v >= ST.grid.threshold).length;
  const [u, v] = windAt(p.lx, p.ly, S.h), ws = Math.hypot(u, v), toward = Math.atan2(u, v)*180/Math.PI;
  let best = null, bd = 1e9; for (const s of SRC) { const d = Math.hypot(s.x - 491700 - p.lx, 4266300 - s.y - p.ly); if (d < bd) { bd = d; best = s; } }
  const title = sea ? L('Over the gulf', 'Körfezin üzerinde') : m ? m.n : L('Outside the mapped neighbourhoods', 'Haritalanan mahallelerin dışında');
  $('detail').hidden = false;
  $('detail').innerHTML = `<h3>${title}</h3><p class="sub">${m && m.d ? m.d + ' · ' : ''}21 ${MONTHS[+S.day-1]} · ${S.scen === 'b' ? L('with buildings', 'binalarla') : L('bare terrain', 'çıplak arazi')}</p>
    <div class="row"><span>${L('Odour now', 'Şu an koku')} (${$('tClock').textContent})</span><b>${WORD(now)} · ${now.toFixed(2).replace('.', TR ? ',' : '.')}</b></div>
    <div class="row"><span>${L('Odour hours this day', 'Bu gün koku saati')}</span><b class="mono">${hrs} / 24</b></div>
    <div class="strip">${strip.map(v => `<i style="background:${v < 0.03 ? 'rgba(255,255,255,.06)' : '#' + rampJS(Math.min(1, v*1.15)).getHexString()}"></i>`).join('')}</div>
    <div class="sk mono"><span>00</span><span>06</span><span>12</span><span>18</span><span>23</span></div>
    <div class="row"><span>${L('Wind here now', 'Burada rüzgâr')}</span><b class="mono">${ws.toFixed(1)} m/s → ${COMPASS[Math.round(((toward%360)+360)%360/45)%8]}</b></div>
    <div class="row"><span>${L('Ground', 'Zemin')}</span><b class="mono">${Math.round(groundAt(p.lx, p.ly))} m</b></div>
    ${m && m.b ? `<div class="row"><span>${L('Neighbourhood, 12-day average', 'Mahalle, 12 gün ortalaması')}</span><b class="mono">${m.h.toFixed(1)} ${L('h/day', 'sa/gün')}</b></div>` : ''}
    <div class="row"><span>${L('Nearest source', 'En yakın kaynak')}</span><b>${SHORT[best.name] || best.name} · ${(bd/1000).toFixed(1)} km</b></div>`;
}
let downAt = null;
canvas.addEventListener('pointerdown', e => downAt = [e.clientX, e.clientY]);
canvas.addEventListener('pointerup', e => { if (!downAt || Math.hypot(e.clientX-downAt[0], e.clientY-downAt[1]) > 5) return; const p = pick(e); if (p) showDetail(p); });
function onDay() { setHour(S.h); if (lastPick) showDetail(lastPick); }

// ---------- loop ----------
let lastDetail = 0;
function frame(dt) {
  S.t += dt;
  if (S.play) { setHour(S.h + dt*0.75); if (S.t - lastDetail > 0.5 && lastPick) { lastDetail = S.t; showDetail(lastPick); } }
  for (const m of cloudMats) { m.uniforms.t.value = S.t; }
  pMat.uniforms.scale.value = innerHeight * (FILM ? 1.6 : 1.0);
  if (pts.visible) stepParticles(Math.min(dt, 0.05));
  controls.update(); renderer.render(scene, camera); placeLabels();
}
await loadDay(S.day, S.scen);
setHour(S.h);
let last = performance.now();
if (!FILM) (function loop(now) { const dt = (now-last)/1000; last = now; frame(dt); requestAnimationFrame(loop); })(last);
else { document.body.classList.add('film'); $('film').hidden = false; }
$('load').classList.add('gone');
Promise.all([bldReady, treesReady]).then(applyEx);

// ---------- film API ----------
window.Film = {
  ready: true, bldReady, treesReady, THREE, camera, controls, W3, groundAt, S, VIEWS, ST,
  async day(d, s = 'b') { S.day = d; S.scen = s; await loadDay(d, s); },
  set(o) {
    if (o.h !== undefined) setHour(o.h);
    if (o.op !== undefined) for (const m of cloudMats) m.uniforms.op.value = o.op;
    if (o.ex !== undefined) { S.ex = o.ex; applyEx(); }
    if (o.labels !== undefined) lblBox.style.opacity = o.labels;
    if (o.src !== undefined) showSrc = !!o.src;
    if (o.cam) { camera.position.copy(o.cam.p); controls.target.copy(o.cam.t); camera.lookAt(o.cam.t); }
  },
  warm(sec) { for (let t = 0; t < sec; t += 1/30) stepParticles(1/30); },
  step(dt) { frame(dt); }
};
