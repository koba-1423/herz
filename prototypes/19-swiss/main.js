import { PRESETS, bpm, escapeHtml, searchVibes } from "../shared/api.js";

async function run(text) {
  const tracks = await searchVibes(text, 10);
  document.querySelector("#results").innerHTML = tracks
    .map(
      (track, index) => `
      <li class="grid grid-cols-[2.5rem_1fr_auto] items-baseline gap-3 border-t border-neutral-900 py-3">
        <span class="font-bold text-[#e3342f] tabular-nums">${String(index + 1).padStart(2, "0")}</span>
        <span class="min-w-0"><span class="block truncate font-bold">${escapeHtml(track.title)}</span><span class="block truncate text-sm text-neutral-500">${escapeHtml(track.artist)}</span></span>
        <span class="text-xs tabular-nums">${bpm(track)}</span>
      </li>`,
    )
    .join("");
}

const presets = document.querySelector("#presets");
presets.innerHTML = PRESETS.map((preset) => `<button class="underline decoration-neutral-300 underline-offset-4 hover:decoration-[#e3342f]">${preset}</button>`).join("");
presets.addEventListener("click", (event) => event.target.tagName === "BUTTON" && run(event.target.textContent));
document.querySelector("#form").addEventListener("submit", (event) => {
  event.preventDefault();
  run(document.querySelector("#query").value || PRESETS[2]);
});
run(PRESETS[2]);
