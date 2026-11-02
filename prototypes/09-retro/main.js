import { animate, stagger } from "animejs";
import { PRESETS, escapeHtml, libraryStats, searchVibes } from "../shared/api.js";

animate(".reel", { rotate: "1turn", duration: 2400, loop: true, ease: "linear" });

const list = document.querySelector("#results");
async function run(text) {
  const tracks = await searchVibes(text, 10);
  list.innerHTML = tracks
    .map(
      (track, index) => `<li><span class="n">${String(index + 1).padStart(2, "0")}.</span><span class="t">${escapeHtml(track.title)}</span><span class="a">${escapeHtml(track.artist)}</span></li>`,
    )
    .join("");
  animate(".tracks li", { opacity: [0, 1], translateX: [-12, 0], delay: stagger(60), duration: 300 });
}
const presets = document.querySelector("#presets");
presets.innerHTML = ["なつの うみべ", "よるの ドライブ", "80年代 シティポップ", "ゲームの BGM"]
  .map((preset) => `<button type="button">${preset}</button>`)
  .join("");
presets.addEventListener("click", (event) => {
  if (event.target.tagName === "BUTTON") run(event.target.textContent);
});
document.querySelector("#form").addEventListener("submit", (event) => {
  event.preventDefault();
  run(document.querySelector("#query").value || "1980s japanese city pop");
});
libraryStats().then((stats) => (document.querySelector("#count").textContent = stats.total_tracks));
run("1980s japanese city pop");
