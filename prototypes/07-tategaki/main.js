import { PRESETS, cover, escapeHtml, searchVibes } from "../shared/api.js";

const list = document.querySelector("#results");
async function run(text) {
  const tracks = await searchVibes(text, 7);
  list.innerHTML = tracks
    .map(
      (track) => `<li><span class="dot" style="background:${cover(track)}"></span><div><b>${escapeHtml(track.title)}</b><span>${escapeHtml(track.artist)}</span></div></li>`,
    )
    .join("");
}
const presets = document.querySelector("#presets");
presets.innerHTML = PRESETS.map((preset) => `<button type="button">${preset}</button>`).join("");
presets.addEventListener("click", (event) => {
  if (event.target.tagName === "BUTTON") run(event.target.textContent);
});
document.querySelector("#form").addEventListener("submit", (event) => {
  event.preventDefault();
  run(document.querySelector("#query").value || PRESETS[0]);
});
run(PRESETS[0]);
