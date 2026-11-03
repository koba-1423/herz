import { bpm, cover, escapeHtml, searchVibes } from "../shared/api.js";
import { MOODS } from "../shared/moods.js";

async function run(label, text) {
  document.querySelector("#title").textContent = label;
  for (const button of document.querySelectorAll("#moods button")) {
    button.classList.toggle("text-neutral-900", button.textContent === label);
  }
  const tracks = await searchVibes(text, 10);
  document.querySelector("#results").innerHTML = tracks
    .map(
      (track) => `
      <li>
        <span class="block aspect-square rounded-md" style="background:${cover(track)}"></span>
        <span class="mt-3 block truncate text-sm font-semibold">${escapeHtml(track.title)}</span>
        <span class="block truncate text-xs text-neutral-500">${escapeHtml(track.artist)} · ${bpm(track)}</span>
      </li>`,
    )
    .join("");
}

const moods = document.querySelector("#moods");
moods.innerHTML = MOODS.map((mood, index) => `<button data-index="${index}" class="hover:text-neutral-900">${mood.ja}</button>`).join("");
moods.addEventListener("click", (event) => {
  const button = event.target.closest("button");
  if (!button) return;
  const mood = MOODS[Number(button.dataset.index)];
  run(mood.ja, mood.query);
});
document.querySelector("#form").addEventListener("submit", (event) => {
  event.preventDefault();
  const text = document.querySelector("#query").value;
  if (text) run(`「${text}」`, text);
});
run(MOODS[0].ja, MOODS[0].query);
