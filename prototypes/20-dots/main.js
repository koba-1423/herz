import { bpm, escapeHtml, searchVibes, vibeColors } from "../shared/api.js";
import { MOODS } from "../shared/moods.js";

async function run(label, text, selected = -1) {
  document.querySelector("#title").textContent = label;
  document.querySelectorAll("#moods button").forEach((button, i) => {
    button.querySelector("span").style.transform = i === selected ? "scale(1.25)" : "";
    button.classList.toggle("text-neutral-900", i === selected);
  });
  const tracks = await searchVibes(text, 8);
  document.querySelector("#results").innerHTML = tracks
    .map((track) => {
      const [color] = vibeColors(track);
      return `
      <li class="flex items-center gap-4">
        <span class="size-10 shrink-0 rounded-full" style="background:${color}"></span>
        <span class="min-w-0 flex-1"><span class="block truncate font-bold">${escapeHtml(track.title)}</span><span class="block truncate text-sm text-neutral-500">${escapeHtml(track.artist)}</span></span>
        <span class="text-xs text-neutral-400">${bpm(track)}</span>
      </li>`;
    })
    .join("");
}

const moods = document.querySelector("#moods");
moods.innerHTML = MOODS.map(
  (mood, index) => `<button data-index="${index}" class="flex flex-col items-center gap-3 text-sm text-neutral-400"><span class="size-16 rounded-full transition-transform" style="background:linear-gradient(135deg,${mood.colors[0]},${mood.colors[1]})"></span>${mood.ja}</button>`,
).join("");
moods.addEventListener("click", (event) => {
  const button = event.target.closest("button");
  if (!button) return;
  const index = Number(button.dataset.index);
  run(MOODS[index].ja, MOODS[index].query, index);
});
document.querySelector("#form").addEventListener("submit", (event) => {
  event.preventDefault();
  const text = document.querySelector("#query").value;
  if (text) run(`「${text}」`, text);
});
run(MOODS[3].ja, MOODS[3].query, 3);
