import { bpm, escapeHtml, searchVibes, vibeColors } from "../shared/api.js";
import { MOODS } from "../shared/moods.js";

async function choose(mood) {
  document.querySelector("#panel").style.background = `linear-gradient(160deg, ${mood.colors[0]}, ${mood.colors[1]})`;
  document.querySelector("#en").textContent = mood.en;
  document.querySelector("#title").textContent = mood.ja;
  for (const button of document.querySelectorAll("#moods button")) {
    button.classList.toggle("bg-white", button.textContent === mood.ja);
    button.classList.toggle("text-neutral-900", button.textContent === mood.ja);
  }
  await run(mood.query);
}

async function run(text) {
  const tracks = await searchVibes(text, 9);
  document.querySelector("#results").innerHTML = tracks
    .map(
      (track) => `
      <li class="flex items-center gap-4 py-4">
        <span class="size-3 shrink-0 rounded-full" style="background:${vibeColors(track)[0]}"></span>
        <span class="min-w-0 flex-1"><span class="block truncate font-bold">${escapeHtml(track.title)}</span><span class="block truncate text-sm text-neutral-500">${escapeHtml(track.artist)}</span></span>
        <span class="text-xs text-neutral-400">${bpm(track)}</span>
      </li>`,
    )
    .join("");
}

const moods = document.querySelector("#moods");
moods.innerHTML = MOODS.map((mood, index) => `<button data-index="${index}" class="rounded-full border border-white/60 px-4 py-1.5 text-sm">${mood.ja}</button>`).join("");
moods.addEventListener("click", (event) => {
  const button = event.target.closest("button");
  if (button) choose(MOODS[Number(button.dataset.index)]);
});
document.querySelector("#form").addEventListener("submit", (event) => {
  event.preventDefault();
  const text = document.querySelector("#query").value;
  if (text) run(text);
});
choose(MOODS[1]);
