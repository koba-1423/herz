import * as THREE from "three";
import { cover, escapeHtml, libraryStats, searchVibes } from "../shared/api.js";

// 曲の雲: 実際の埋め込みではなく、ジャンルごとの星団に見えるよう乱数で配置した見本
const canvas = document.querySelector("#space");
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
const scene = new THREE.Scene();
scene.fog = new THREE.FogExp2(0x000000, 0.035);
const camera = new THREE.PerspectiveCamera(60, 1, 0.1, 100);
camera.position.set(0, 0, 16);

const COUNT = 20000;
const positions = new Float32Array(COUNT * 3);
const colors = new Float32Array(COUNT * 3);
const clusters = Array.from({ length: 12 }, (_, index) => ({
  center: new THREE.Vector3().randomDirection().multiplyScalar(4 + Math.random() * 5),
  color: new THREE.Color().setHSL(index / 12, 0.75, 0.6),
}));
for (let i = 0; i < COUNT; i++) {
  const cluster = clusters[i % clusters.length];
  const spread = new THREE.Vector3().randomDirection().multiplyScalar(Math.pow(Math.random(), 1.8) * 3.2);
  const point = cluster.center.clone().add(spread);
  positions.set([point.x, point.y, point.z], i * 3);
  colors.set([cluster.color.r, cluster.color.g, cluster.color.b], i * 3);
}
const geometry = new THREE.BufferGeometry();
geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
geometry.setAttribute("color", new THREE.BufferAttribute(colors, 3));
const stars = new THREE.Points(
  geometry,
  new THREE.PointsMaterial({ size: 0.06, vertexColors: true, transparent: true, opacity: 0.9, blending: THREE.AdditiveBlending }),
);
scene.add(stars);

function resize() {
  renderer.setSize(innerWidth, innerHeight, false);
  camera.aspect = innerWidth / innerHeight;
  camera.updateProjectionMatrix();
}
addEventListener("resize", resize);
resize();

let target = 0;
addEventListener("pointermove", (event) => (target = (event.clientX / innerWidth - 0.5) * 0.6));
renderer.setAnimationLoop((time) => {
  stars.rotation.y = time * 0.00004 + target;
  stars.rotation.x = Math.sin(time * 0.00007) * 0.2;
  renderer.render(scene, camera);
});

const results = document.querySelector("#results");
async function run(text) {
  const tracks = await searchVibes(text, 6);
  results.innerHTML = tracks
    .map(
      (track) => `
      <div class="flex w-44 shrink-0 items-center gap-3 rounded-xl border border-white/10 bg-white/5 p-2 backdrop-blur">
        <span class="size-10 shrink-0 rounded-full" style="background:${cover(track)}"></span>
        <span class="min-w-0 text-xs"><span class="block truncate font-bold">${escapeHtml(track.title)}</span><span class="block truncate text-white/50">${escapeHtml(track.artist)}</span></span>
      </div>`,
    )
    .join("");
}
document.querySelector("#form").addEventListener("submit", (event) => {
  event.preventDefault();
  run(document.querySelector("#query").value || "ambient space dreamy");
});
libraryStats().then((stats) => (document.querySelector("#count").textContent = stats.total_tracks.toLocaleString()));
run("ambient space dreamy");
