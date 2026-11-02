import { PRESETS, bpm, cover, escapeHtml, libraryStats, searchVibes } from "../shared/api.js";

const results = document.querySelector("#results");

async function run(text) {
  document.querySelector("#label").textContent = text;
  const tracks = await searchVibes(text, 8);
  results.innerHTML = tracks
    .map(
      (track, index) => `
      <li class="grid grid-cols-[3rem_3rem_1fr_auto] items-center gap-6 py-4">
        <span class="text-sm tabular-nums text-neutral-300">${String(index + 1).padStart(2, "0")}</span>
        <span class="size-12" style="background:${cover(track)}"></span>
        <span><span class="block font-semibold">${escapeHtml(track.title)}</span><span class="text-sm text-neutral-500">${escapeHtml(track.artist)}</span></span>
        <span class="text-xs tabular-nums text-neutral-400">${bpm(track)}</span>
      </li>`,
    )
    .join("");
}

document.querySelector("#presets").innerHTML = PRESETS.map(
  (preset) => `<button class="hover:text-neutral-900">${preset}</button>`,
).join("");
document.querySelector("#presets").addEventListener("click", (event) => {
  if (event.target.tagName === "BUTTON") run(event.target.textContent);
});
document.querySelector("#form").addEventListener("submit", (event) => {
  event.preventDefault();
  run(document.querySelector("#query").value || PRESETS[0]);
});

libraryStats().then((stats) => {
  document.querySelector("#count").textContent = `${Math.floor(stats.total_tracks / 10000)}万`;
});
run(PRESETS[0]);
