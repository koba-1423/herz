import { PRESETS, bpm, escapeHtml, libraryStats, searchVibes, vibeColors } from "../shared/api.js";

async function run(text) {
  const tracks = await searchVibes(text, 10);
  document.querySelector("#results").innerHTML = tracks
    .map(
      (track, index) => `
      <li class="flex items-center gap-5 border-b border-neutral-900 py-4">
        <span class="w-6 text-sm tabular-nums text-neutral-600">${String(index + 1).padStart(2, "0")}</span>
        <span class="size-2.5 shrink-0 rounded-full" style="background:${vibeColors(track)[0]};box-shadow:0 0 12px ${vibeColors(track)[0]}"></span>
        <span class="min-w-0 flex-1"><span class="block truncate font-semibold">${escapeHtml(track.title)}</span><span class="block truncate text-sm text-neutral-500">${escapeHtml(track.artist)}</span></span>
        <span class="text-xs tabular-nums text-neutral-600">${bpm(track)}</span>
      </li>`,
    )
    .join("");
}

const presets = document.querySelector("#presets");
presets.innerHTML = PRESETS.map((preset) => `<button class="hover:text-white">${preset}</button>`).join("");
presets.addEventListener("click", (event) => event.target.tagName === "BUTTON" && run(event.target.textContent));
document.querySelector("#form").addEventListener("submit", (event) => {
  event.preventDefault();
  run(document.querySelector("#query").value || PRESETS[1]);
});
libraryStats().then((stats) => (document.querySelector("#count").textContent = `${stats.total_tracks.toLocaleString()} 曲`));
run(PRESETS[1]);
