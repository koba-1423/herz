import { bpm, escapeHtml, searchVibes } from "../shared/api.js";
import { MOODS } from "../shared/moods.js";

async function choose(index) {
  const mood = MOODS[index];
  document.querySelector("#line").style.background = `linear-gradient(90deg, ${mood.colors[0]}, ${mood.colors[1]})`;
  document.querySelectorAll("#moods button").forEach((button, i) => {
    button.style.color = i === index ? mood.colors[0] : "";
    button.classList.toggle("font-bold", i === index);
  });
  const tracks = await searchVibes(mood.query, 8);
  document.querySelector("#results").innerHTML = tracks
    .map(
      (track) => `
      <li class="flex items-center gap-4 py-4">
        <span class="h-8 w-1 shrink-0 rounded-full" style="background:${mood.colors[0]}"></span>
        <span class="min-w-0 flex-1"><span class="block truncate font-bold">${escapeHtml(track.title)}</span><span class="block truncate text-sm text-neutral-500">${escapeHtml(track.artist)}</span></span>
        <span class="text-xs text-neutral-400">${bpm(track)}</span>
      </li>`,
    )
    .join("");
}

const moods = document.querySelector("#moods");
moods.innerHTML = MOODS.map(
  (mood, index) => `<li><button data-index="${index}" class="flex items-center gap-3 py-1 text-lg text-neutral-400 hover:text-neutral-900"><span class="size-2 rounded-full" style="background:${mood.colors[0]}"></span>${mood.ja}</button></li>`,
).join("");
moods.addEventListener("click", (event) => {
  const button = event.target.closest("button");
  if (button) choose(Number(button.dataset.index));
});
choose(2);
