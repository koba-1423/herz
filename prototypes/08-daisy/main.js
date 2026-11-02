import { AudioLines, Disc3, Globe, Heart, Music2, Play, Search, Sparkles, Zap, createIcons } from "lucide";
import { PRESETS, bpm, cover, escapeHtml, libraryStats, searchVibes } from "../shared/api.js";

const icons = { AudioLines, Disc3, Globe, Heart, Music2, Play, Search, Sparkles, Zap };
const results = document.querySelector("#results");

async function run(text) {
  const tracks = await searchVibes(text, 8);
  results.innerHTML = tracks
    .map(
      (track) => `
      <div class="card bg-base-100 shadow-md transition hover:-translate-y-1 hover:shadow-xl">
        <figure class="relative aspect-square" style="background:${cover(track)}">
          <button class="btn btn-circle absolute right-3 bottom-3 border-0 bg-white/90"><i data-lucide="play" class="size-5 text-primary"></i></button>
        </figure>
        <div class="card-body gap-1 p-4">
          <h3 class="card-title truncate text-base">${escapeHtml(track.title)}</h3>
          <p class="truncate text-sm opacity-60">${escapeHtml(track.artist)}</p>
          <div class="mt-1 flex gap-1"><span class="badge badge-soft badge-primary badge-sm">${escapeHtml(track.genres?.[0] ?? "")}</span><span class="badge badge-ghost badge-sm">${bpm(track)}</span></div>
        </div>
      </div>`,
    )
    .join("");
  createIcons({ icons });
}

const presets = document.querySelector("#presets");
presets.innerHTML = PRESETS.map((preset) => `<button class="btn btn-sm rounded-full border-0 bg-white/20 text-white hover:bg-white/30">${preset}</button>`).join("");
presets.addEventListener("click", (event) => {
  if (event.target.tagName === "BUTTON") run(event.target.textContent);
});
document.querySelector("#form").addEventListener("submit", (event) => {
  event.preventDefault();
  run(document.querySelector("#query").value || PRESETS[3]);
});
libraryStats().then((stats) => (document.querySelector("#count").textContent = stats.total_tracks.toLocaleString()));
createIcons({ icons });
run(PRESETS[3]);
