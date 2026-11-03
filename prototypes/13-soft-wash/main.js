import { bpm, cover, escapeHtml, searchVibes } from "../shared/api.js";
import { MOODS } from "../shared/moods.js";

const wash = document.querySelector("#wash");

async function choose(mood) {
  wash.style.setProperty("--a", `${mood.colors[0]}66`);
  wash.style.setProperty("--c", mood.colors[2]);
  document.querySelector("#en").textContent = mood.en;
  document.querySelector("#title").textContent = mood.ja;
  await run(mood.query);
}

async function run(text) {
  const tracks = await searchVibes(text, 8);
  document.querySelector("#results").innerHTML = tracks
    .map(
      (track) => `
      <li class="flex items-center gap-4 rounded-2xl bg-white/80 p-3 shadow-sm">
        <span class="size-12 shrink-0 rounded-xl" style="background:${cover(track)}"></span>
        <span class="min-w-0 flex-1"><span class="block truncate font-bold">${escapeHtml(track.title)}</span><span class="block truncate text-sm text-neutral-500">${escapeHtml(track.artist)}</span></span>
        <span class="text-xs text-neutral-400">${bpm(track)}</span>
      </li>`,
    )
    .join("");
}

const moods = document.querySelector("#moods");
moods.innerHTML = MOODS.map(
  (mood, index) => `<button data-index="${index}" class="flex items-center gap-2 rounded-full bg-white/70 px-4 py-2 text-sm hover:bg-white"><span class="size-3 rounded-full" style="background:${mood.colors[0]}"></span>${mood.ja}</button>`,
).join("");
moods.addEventListener("click", (event) => {
  const button = event.target.closest("button");
  if (button) choose(MOODS[Number(button.dataset.index)]);
});
document.querySelector("#form").addEventListener("submit", (event) => {
  event.preventDefault();
  const text = document.querySelector("#query").value;
  if (text) run(text);
});
choose(MOODS[0]);
