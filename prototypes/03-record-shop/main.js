import { PRESETS, bpm, cover, escapeHtml, libraryStats, searchVibes } from "../shared/api.js";

const results = document.querySelector("#results");
const NOTES = ["店主イチオシ", "夜に合う", "B面も良い", "針を落として", "隠れた名盤", "雨の日に"];

async function run(text) {
  document.querySelector("#label").textContent = `—「${text}」`;
  const tracks = await searchVibes(text, 8);
  results.innerHTML = tracks
    .map(
      (track, index) => `
      <article class="sleeve" style="--tilt:${(index % 3) - 1}deg">
        <div class="art" style="background:${cover(track)}">${escapeHtml(track.title.slice(0, 14))}</div>
        <h3>${escapeHtml(track.title)}</h3>
        <p>${escapeHtml(track.artist)} · ${bpm(track)}</p>
        <span class="pop">${NOTES[index % NOTES.length]}</span>
      </article>`,
    )
    .join("");
}

const presets = document.querySelector("#presets");
presets.innerHTML = PRESETS.map((preset) => `<button>${preset}</button>`).join("");
presets.addEventListener("click", (event) => {
  if (event.target.tagName === "BUTTON") run(event.target.textContent);
});
document.querySelector("#form").addEventListener("submit", (event) => {
  event.preventDefault();
  run(document.querySelector("#query").value || PRESETS[2]);
});
libraryStats().then((stats) => {
  document.querySelector("#count").textContent = stats.total_tracks.toLocaleString();
});
run(PRESETS[2]);
