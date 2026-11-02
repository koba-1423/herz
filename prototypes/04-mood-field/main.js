import { animate, stagger } from "motion";
import { bpm, escapeHtml, searchVibes, vibeColors } from "../shared/api.js";

const MOODS = [
  { ja: "雨の午後", en: "Rainy afternoon", desc: "窓の外の雨音に溶けるような、静かなピアノとやわらかな弦。", query: "rainy day quiet piano", colors: ["#5b7ea4", "#2f4a6b", "#1c2838"] },
  { ja: "真夜中の街", en: "Midnight city", desc: "ネオンが滲む高速道路を走る、シンセとベースのグルーヴ。", query: "night drive city pop synth", colors: ["#9b3fd1", "#ff4f8b", "#120b2b"] },
  { ja: "夏の海辺", en: "Summer shore", desc: "まぶしい光と潮風。軽やかなギターと跳ねるリズム。", query: "summer beach upbeat guitar", colors: ["#ffb347", "#3fd0c9", "#1e6f8f"] },
  { ja: "森の朝", en: "Forest morning", desc: "鳥の声と木漏れ日。アコースティックで澄んだ響き。", query: "morning acoustic folk", colors: ["#9bc472", "#3f7d4f", "#16301f"] },
  { ja: "燃える夜", en: "Burning night", desc: "全身で浴びたい、歪んだギターと叩きつけるドラム。", query: "heavy rock energetic", colors: ["#ff3d2e", "#ff9f1c", "#2a0a06"] },
  { ja: "星を見上げて", en: "Under the stars", desc: "広がっていくアンビエントと、遠くで鳴るシンセ。", query: "ambient space dreamy", colors: ["#6c7bff", "#b9a7ff", "#0a0c24"] },
];

const field = document.querySelector("#field");
const results = document.querySelector("#results");

function paint([a, b, c]) {
  field.style.setProperty("--a", a);
  field.style.setProperty("--b", b);
  field.style.setProperty("--c", c);
}

async function choose(mood) {
  paint(mood.colors);
  animate(field, { opacity: [0.4, 1] }, { duration: 1.2 });
  document.querySelector("#mood").textContent = mood.ja;
  document.querySelector("#mood-en").textContent = mood.en;
  document.querySelector("#mood-desc").textContent = mood.desc;
  animate("#mood, #mood-en, #mood-desc", { opacity: [0, 1], y: [12, 0] }, { delay: stagger(0.08) });
  await show(mood.query);
}

async function show(text) {
  const tracks = await searchVibes(text, 7);
  results.innerHTML = tracks
    .map((track) => {
      const [a] = vibeColors(track);
      return `
      <li class="row flex items-center gap-4 rounded-2xl bg-black/25 p-3 backdrop-blur-md">
        <span class="size-12 shrink-0 rounded-full" style="background:${a};box-shadow:0 0 24px ${a}"></span>
        <span class="min-w-0 flex-1"><span class="block truncate font-bold">${escapeHtml(track.title)}</span><span class="block truncate text-sm opacity-70">${escapeHtml(track.artist)}</span></span>
        <span class="text-xs opacity-60">${bpm(track)}</span>
      </li>`;
    })
    .join("");
  animate(".row", { opacity: [0, 1], x: [24, 0] }, { delay: stagger(0.05) });
}

const moods = document.querySelector("#moods");
moods.innerHTML = MOODS.map(
  (mood, index) => `
  <button data-index="${index}" class="h-16 rounded-xl text-left text-sm font-bold ring-white/70 hover:ring-2 px-3" style="background:linear-gradient(135deg,${mood.colors[0]},${mood.colors[1]})">${mood.ja}</button>`,
).join("");
moods.addEventListener("click", (event) => {
  const button = event.target.closest("button");
  if (button) choose(MOODS[Number(button.dataset.index)]);
});
document.querySelector("#form").addEventListener("submit", (event) => {
  event.preventDefault();
  const text = document.querySelector("#query").value;
  if (text) show(text);
});
choose(MOODS[0]);
