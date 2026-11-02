import { gsap } from "gsap";
import { PRESETS, bpm, cover, escapeHtml, searchVibes } from "../shared/api.js";

// タブが裏にあって描画が飛んでも、アニメーションを途中で止めずに最後まで進める
gsap.ticker.lagSmoothing(0);

gsap.to(".blob", {
  x: () => gsap.utils.random(-150, 150),
  y: () => gsap.utils.random(-100, 100),
  scale: () => gsap.utils.random(0.8, 1.2),
  duration: 8,
  repeat: -1,
  yoyo: true,
  ease: "sine.inOut",
  stagger: 1.5,
});
gsap.from(".reveal", { y: 30, opacity: 0, duration: 1, stagger: 0.12, ease: "power3.out" });

const results = document.querySelector("#results");

async function run(text) {
  const tracks = await searchVibes(text, 8);
  results.innerHTML = tracks
    .map(
      (track) => `
      <article class="card glass overflow-hidden rounded-2xl">
        <div class="aspect-square" style="background:${cover(track)}"></div>
        <div class="p-4">
          <h3 class="truncate font-bold">${escapeHtml(track.title)}</h3>
          <p class="truncate text-sm text-white/55">${escapeHtml(track.artist)}</p>
          <p class="mt-3 text-xs text-fuchsia-300">${bpm(track)}</p>
        </div>
      </article>`,
    )
    .join("");
  gsap.from(".card", { y: 40, opacity: 0, duration: 0.7, stagger: 0.06, ease: "power2.out" });
}

const presets = document.querySelector("#presets");
presets.innerHTML = PRESETS.map(
  (preset) => `<button class="glass rounded-full px-4 py-1.5 text-sm text-white/75 hover:text-white">${preset}</button>`,
).join("");
presets.addEventListener("click", (event) => {
  if (event.target.tagName === "BUTTON") run(event.target.textContent);
});
document.querySelector("#form").addEventListener("submit", (event) => {
  event.preventDefault();
  run(document.querySelector("#query").value || PRESETS[1]);
});
run(PRESETS[1]);
