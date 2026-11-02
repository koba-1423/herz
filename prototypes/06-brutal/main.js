import { PRESETS, bpm, cover, escapeHtml, searchVibes } from "../shared/api.js";

const results = document.querySelector("#results");
async function run(text) {
  const tracks = await searchVibes(text, 8);
  results.innerHTML = tracks
    .map(
      (track, index) => `
      <article class="border-r-4 border-b-4 border-black bg-white">
        <div class="font-grotesk flex aspect-[4/3] items-start justify-between border-b-4 border-black p-4 text-5xl font-bold text-white" style="background:${cover(track)}">
          <span>${String(index + 1).padStart(2, "0")}</span>
        </div>
        <div class="p-4">
          <h3 class="truncate text-lg font-black">${escapeHtml(track.title)}</h3>
          <p class="truncate text-sm">${escapeHtml(track.artist)}</p>
          <p class="font-grotesk mt-3 inline-block bg-black px-2 text-xs font-bold text-[#e8ff3a]">${bpm(track) || "—"}</p>
        </div>
      </article>`,
    )
    .join("");
}
const presets = document.querySelector("#presets");
presets.innerHTML = ["ゴリゴリのメタル", ...PRESETS.slice(0, 4)]
  .map((preset) => `<button class="border-r-4 border-black px-5 py-3 text-sm font-bold hover:bg-[#e8ff3a]">${preset}</button>`)
  .join("");
presets.addEventListener("click", (event) => {
  if (event.target.tagName === "BUTTON") run(event.target.textContent);
});
document.querySelector("#form").addEventListener("submit", (event) => {
  event.preventDefault();
  run(document.querySelector("#query").value || "heavy metal");
});
run("heavy metal");
