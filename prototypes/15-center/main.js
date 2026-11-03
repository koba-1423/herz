import { PRESETS, bpm, cover, escapeHtml, searchVibes } from "../shared/api.js";

async function run(text) {
  const tracks = await searchVibes(text, 6);
  document.querySelector("#results").innerHTML = tracks
    .map(
      (track) => `
      <li class="flex items-center gap-4 rounded-xl p-3 hover:bg-neutral-50">
        <span class="size-11 shrink-0 rounded-lg" style="background:${cover(track)}"></span>
        <span class="min-w-0 flex-1"><span class="block truncate font-medium">${escapeHtml(track.title)}</span><span class="block truncate text-sm text-neutral-500">${escapeHtml(track.artist)}</span></span>
        <span class="text-xs text-neutral-400">${bpm(track)}</span>
      </li>`,
    )
    .join("");
}

const presets = document.querySelector("#presets");
presets.innerHTML = PRESETS.map((preset) => `<button class="rounded-full bg-neutral-100 px-3 py-1 text-neutral-600 hover:bg-neutral-200">${preset}</button>`).join("");
presets.addEventListener("click", (event) => {
  if (event.target.tagName !== "BUTTON") return;
  document.querySelector("#query").value = event.target.textContent;
  run(event.target.textContent);
});
document.querySelector("#form").addEventListener("submit", (event) => {
  event.preventDefault();
  run(document.querySelector("#query").value || PRESETS[0]);
});
document.querySelector("#query").value = PRESETS[0];
run(PRESETS[0]);
