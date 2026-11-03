import { PRESETS, escapeHtml, libraryStats, searchVibes } from "../shared/api.js";

async function run(text) {
  const tracks = await searchVibes(text, 10);
  document.querySelector("#results").innerHTML = tracks
    .map(
      (track, index) => `
      <tr class="border-t border-neutral-200">
        <td class="py-3 text-neutral-400">${String(index + 1).padStart(2, "0")}</td>
        <td class="max-w-0 truncate pr-4">${escapeHtml(track.title)}</td>
        <td class="max-w-0 truncate pr-4 text-neutral-500">${escapeHtml(track.artist)}</td>
        <td class="text-right text-neutral-500">${Math.round(track.features?.tempo_bpm ?? 0) || "-"}</td>
        <td class="text-right">${track.similarity ? track.similarity.toFixed(2) : "-"}</td>
      </tr>`,
    )
    .join("");
}

const presets = document.querySelector("#presets");
presets.innerHTML = PRESETS.map((preset) => `<button class="border border-black px-2 py-1 hover:bg-black hover:text-white">${preset}</button>`).join("");
presets.addEventListener("click", (event) => {
  if (event.target.tagName !== "BUTTON") return;
  document.querySelector("#query").value = event.target.textContent;
  run(event.target.textContent);
});
document.querySelector("#form").addEventListener("submit", (event) => {
  event.preventDefault();
  run(document.querySelector("#query").value || PRESETS[0]);
});
libraryStats().then((stats) => (document.querySelector("#count").textContent = `${stats.total_tracks} tracks indexed`));
run(PRESETS[0]);
