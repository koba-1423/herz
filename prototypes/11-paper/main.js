import { PRESETS, bpm, escapeHtml, libraryStats, searchVibes } from "../shared/api.js";

async function run(text) {
  const tracks = await searchVibes(text, 8);
  document.querySelector("#results").innerHTML = tracks
    .map(
      (track, index) => `
      <li class="flex items-baseline gap-6 border-t border-stone-200 py-5">
        <span class="font-display w-6 text-stone-400">${index + 1}</span>
        <span class="min-w-0 flex-1"><span class="block truncate text-stone-900">${escapeHtml(track.title)}</span><span class="block truncate text-sm text-stone-500">${escapeHtml(track.artist)}</span></span>
        <span class="text-xs text-stone-400">${bpm(track)}</span>
      </li>`,
    )
    .join("");
}

const presets = document.querySelector("#presets");
presets.innerHTML = PRESETS.map((preset) => `<button class="hover:text-stone-900">${preset}</button>`).join("<span>·</span>");
presets.addEventListener("click", (event) => event.target.tagName === "BUTTON" && run(event.target.textContent));
document.querySelector("#form").addEventListener("submit", (event) => {
  event.preventDefault();
  run(document.querySelector("#query").value || PRESETS[0]);
});
libraryStats().then((stats) => (document.querySelector("#count").textContent = `${stats.total_tracks.toLocaleString()}曲`));
run(PRESETS[0]);
