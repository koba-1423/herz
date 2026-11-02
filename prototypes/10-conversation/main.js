import { HeartPulse, Send, createIcons } from "lucide";
import { PRESETS, cover, escapeHtml, searchVibes } from "../shared/api.js";

const log = document.querySelector("#log");

function say(html, who) {
  log.insertAdjacentHTML("beforeend", `<div class="bubble ${who}">${html}</div>`);
}

async function ask(text) {
  say(escapeHtml(text), "me");
  const tracks = await searchVibes(text, 4);
  const songs = tracks
    .map(
      (track) => `<div class="song"><i style="background:${cover(track)}"></i><div><b>${escapeHtml(track.title)}</b><span>${escapeHtml(track.artist)}</span></div></div>`,
    )
    .join("");
  say(`「${escapeHtml(text)}」ですね。こんな曲はどうでしょう？<div class="songs">${songs}</div>もう少し明るい方がよければ、そう伝えてください。`, "bot");
}

const presets = document.querySelector("#presets");
presets.innerHTML = PRESETS.slice(0, 4).map((preset) => `<button type="button">${preset}</button>`).join("");
presets.addEventListener("click", (event) => {
  if (event.target.tagName === "BUTTON") ask(event.target.textContent);
});
document.querySelector("#form").addEventListener("submit", (event) => {
  event.preventDefault();
  const input = document.querySelector("#query");
  if (input.value) ask(input.value);
  input.value = "";
});

createIcons({ icons: { HeartPulse, Send } });
say("こんばんは。今日はどんな気分ですか？", "bot");
ask("仕事に集中したい、歌詞なしで");
