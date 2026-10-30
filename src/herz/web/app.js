// Herz フロントエンド。ビルド不要の素のES Moduleで、同一オリジンのAPIを呼ぶ。

const KEY_NAMES = ["C", "C♯", "D", "E♭", "E", "F", "F♯", "G", "A♭", "A", "B♭", "B"];

const PRESETS = [
  "relaxing soft piano for a rainy night",
  "dusty chill beats to study to",
  "energetic dance music with big synth drops",
  "warm acoustic guitar and gentle singing",
  "dramatic strings like a film score",
  "aggressive heavy guitars",
];

const RANGE_FIELDS = ["tempo_bpm", "energy", "acousticness"];

const ICON_PLAY = '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M4 2.5v11l9-5.5z"/></svg>';
const ICON_PAUSE =
  '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3.5 2.5h3v11h-3zM9.5 2.5h3v11h-3z"/></svg>';

const $ = (selector) => document.querySelector(selector);

const elements = {
  stats: $("#stats"),
  searchForm: $("#search-form"),
  text: $("#text"),
  textHint: $("#text-hint"),
  presets: $("#presets"),
  key: $("#key"),
  filterCount: $("#filter-count"),
  resetFilters: $("#reset-filters"),
  searchStatus: $("#search-status"),
  results: $("#results"),
  ingestForm: $("#ingest-form"),
  ingestStatus: $("#ingest-status"),
  backfill: $("#backfill"),
  backfillNote: $("#backfill-note"),
  backfillButton: $("#backfill-button"),
  player: $("#player"),
};

const state = {
  stats: null,
  playingId: null,
};

// ---- API ----

async function api(path, { method = "GET", body } = {}) {
  const response = await fetch(path, {
    method,
    headers: body ? { "content-type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const detail = payload?.detail;
    const message = Array.isArray(detail)
      ? detail.map((d) => d.msg).join(" / ")
      : detail || `${response.status} ${response.statusText}`;
    throw new Error(message);
  }
  return payload;
}

// ---- DOM helpers ----

function el(tag, attrs = {}, children = []) {
  const node = document.createElement(tag);
  for (const [name, value] of Object.entries(attrs)) {
    if (value === undefined || value === null || value === false) continue;
    if (name === "className") node.className = value;
    else if (name === "text") node.textContent = value;
    else node.setAttribute(name, value === true ? "" : value);
  }
  for (const child of [children].flat()) {
    if (child !== null && child !== undefined) node.append(child);
  }
  return node;
}

function setStatus(target, message, { error = false, busy = false } = {}) {
  target.classList.toggle("error", error);
  target.replaceChildren();
  if (busy) target.append(el("span", { className: "spinner", "aria-hidden": "true" }));
  if (message) target.append(message);
}

async function withBusyButton(button, task) {
  button.disabled = true;
  try {
    return await task();
  } finally {
    button.disabled = false;
  }
}

// ---- library stats ----

async function refreshStats() {
  try {
    state.stats = await api("/library/stats");
  } catch (error) {
    elements.stats.textContent = `状態を取得できませんでした: ${error.message}`;
    return;
  }

  const { total_tracks, embedded_tracks, text_search_available } = state.stats;
  elements.stats.textContent = text_search_available
    ? `ライブラリ ${total_tracks}曲 ・ 雰囲気検索の対象 ${embedded_tracks}曲`
    : `ライブラリ ${total_tracks}曲`;

  if (!text_search_available) {
    elements.text.disabled = true;
    elements.text.placeholder = "自然文検索は無効です";
    elements.presets.hidden = true;
    elements.textHint.textContent =
      "自然文検索 (CLAP) が無効になっています。`uv sync --extra clap` で有効にできます。条件での絞り込みは使えます。";
    elements.textHint.classList.add("warning");
  }

  const missing = total_tracks - embedded_tracks;
  elements.backfill.hidden = !(text_search_available && missing > 0);
  elements.backfillNote.textContent = `${missing}曲がまだ雰囲気検索の対象になっていません（埋め込み未計算）。`;
}

// ---- search ----

function buildQuery() {
  const data = new FormData(elements.searchForm);
  const query = { limit: 30 };

  const text = String(data.get("text") || "").trim();
  if (text && !elements.text.disabled) query.text = text;

  for (const field of RANGE_FIELDS) {
    for (const bound of ["min", "max"]) {
      const raw = String(data.get(`${field}_${bound}`) || "").trim();
      if (raw !== "") query[`${field}_${bound}`] = Number(raw);
    }
  }

  const mode = data.get("mode");
  if (mode !== null && mode !== "") query.mode = Number(mode);

  const key = data.get("key");
  if (key !== null && key !== "") query.key = Number(key);

  const genres = String(data.get("genres") || "")
    .split(/[,、]/)
    .map((g) => g.trim())
    .filter(Boolean);
  if (genres.length) query.genres = genres;

  return query;
}

function countActiveFilters(query) {
  return Object.keys(query).filter((name) => !["limit", "text"].includes(name)).length;
}

function updateFilterCount() {
  const count = countActiveFilters(buildQuery());
  elements.filterCount.textContent = count ? String(count) : "";
}

async function runSearch() {
  const query = buildQuery();
  const submit = elements.searchForm.querySelector('button[type="submit"]');

  setStatus(elements.searchStatus, "検索しています…", { busy: true });
  try {
    const tracks = await withBusyButton(submit, () => api("/search", { method: "POST", body: query }));
    renderResults(tracks, query);
  } catch (error) {
    elements.results.replaceChildren();
    setStatus(elements.searchStatus, `検索に失敗しました: ${error.message}`, { error: true });
  }
}

function renderResults(tracks, query) {
  if (!tracks.length) {
    const libraryEmpty = state.stats && state.stats.total_tracks === 0;
    setStatus(elements.searchStatus, "");
    elements.results.replaceChildren(
      el("li", {
        className: "empty",
        text: libraryEmpty
          ? "まだ曲がありません。右の「ライブラリに曲を追加」から取り込んでください。"
          : "条件に合う曲が見つかりませんでした。条件をゆるめてみてください。",
      }),
    );
    return;
  }

  const ordering = query.text ? "雰囲気が近い順" : "アーティスト名順";
  const count = tracks.length >= query.limit ? `上位${tracks.length}曲` : `${tracks.length}曲`;
  setStatus(elements.searchStatus, `${count}（${ordering}）`);
  elements.results.replaceChildren(...tracks.map(renderTrack));
  syncPlayingState();
}

function formatKey(features) {
  if (features.key === null || features.key < 0) return null;
  const mode = features.mode === 1 ? "メジャー" : features.mode === 0 ? "マイナー" : "";
  return `${KEY_NAMES[features.key]} ${mode}`.trim();
}

function meter(label, value) {
  if (value === null || value === undefined) return null;
  const percent = Math.round(value * 100);
  const bar = el("span", { className: "meter-bar", "aria-hidden": "true" }, el("span"));
  bar.firstChild.style.width = `${percent}%`;
  return el("span", { className: "meter", title: `${label} ${value.toFixed(2)}` }, [
    `${label}`,
    bar,
    el("span", { className: "visually-hidden", text: `${percent}%` }),
  ]);
}

function renderTrack(track) {
  const { features } = track;
  const playable = Boolean(track.preview_url);

  const play = el("button", {
    type: "button",
    className: "play",
    "aria-label": `${track.title} を試聴`,
    disabled: !playable,
  });
  play.innerHTML = ICON_PLAY;
  play.addEventListener("click", () => togglePlay(track));

  const tags = [
    features.tempo_bpm ? el("span", { className: "tag", text: `${Math.round(features.tempo_bpm)} BPM` }) : null,
    formatKey(features) ? el("span", { className: "tag", text: formatKey(features) }) : null,
    ...track.genres.map((genre) => el("span", { className: "tag", text: genre })),
  ];

  const score =
    track.similarity === null || track.similarity === undefined
      ? null
      : el("div", { className: "score", title: "文と曲のコサイン類似度" }, [
          el("strong", { text: track.similarity.toFixed(2) }),
          "一致度",
        ]);

  return el("li", { className: "track", "data-id": track.id }, [
    play,
    el("div", { className: "meta" }, [
      el("div", { className: "track-title", text: track.title }),
      el("div", { className: "track-artist", text: track.artist }),
    ]),
    score,
    el("div", { className: "facts" }, [
      ...tags,
      meter("エネルギー", features.energy),
      meter("アコースティック", features.acousticness),
      track.external_url
        ? el("a", {
            className: "external",
            href: track.external_url,
            target: "_blank",
            rel: "noopener noreferrer",
            text: "Apple Musicで開く ↗",
          })
        : null,
    ]),
  ]);
}

// ---- preview player ----

function togglePlay(track) {
  const { player } = elements;
  if (state.playingId === track.id && !player.paused) {
    player.pause();
    return;
  }
  if (state.playingId !== track.id) {
    player.src = track.preview_url;
    state.playingId = track.id;
  }
  player.play().catch((error) => {
    setStatus(elements.searchStatus, `再生できませんでした: ${error.message}`, { error: true });
  });
}

function syncPlayingState() {
  const playing = !elements.player.paused;
  for (const item of elements.results.querySelectorAll(".track")) {
    const active = item.dataset.id === state.playingId && playing;
    item.classList.toggle("playing", active);
    const button = item.querySelector(".play");
    if (!button.disabled) {
      button.innerHTML = active ? ICON_PAUSE : ICON_PLAY;
      const title = item.querySelector(".track-title").textContent;
      button.setAttribute("aria-label", active ? `${title} を一時停止` : `${title} を試聴`);
    }
  }
}

// ---- ingest ----

async function runIngest(event) {
  event.preventDefault();
  const data = new FormData(elements.ingestForm);
  const term = String(data.get("term") || "").trim();
  const limit = Number(data.get("limit"));
  if (!term) return;

  const submit = elements.ingestForm.querySelector('button[type="submit"]');
  setStatus(elements.ingestStatus, `「${term}」を取り込んでいます。1曲あたり数秒かかります…`, { busy: true });

  try {
    const result = await withBusyButton(submit, () =>
      api("/ingest", { method: "POST", body: { term, limit } }),
    );
    const lines = [
      `${result.ingested.length}曲を追加しました`,
      result.skipped_track_ids.length ? `${result.skipped_track_ids.length}曲は取り込み済みでした` : null,
      result.failed.length ? `${result.failed.length}曲は解析できませんでした` : null,
    ].filter(Boolean);
    setStatus(elements.ingestStatus, "");
    elements.ingestStatus.append(
      el(
        "ul",
        { className: "ingest-summary" },
        lines.map((line) => el("li", { text: line })),
      ),
    );
    await refreshStats();
    await runSearch();
  } catch (error) {
    setStatus(elements.ingestStatus, `取り込みに失敗しました: ${error.message}`, { error: true });
  }
}

async function runBackfill() {
  setStatus(elements.ingestStatus, "埋め込みを計算しています…", { busy: true });
  try {
    const result = await withBusyButton(elements.backfillButton, () =>
      api("/ingest/embeddings", { method: "POST", body: { limit: 50 } }),
    );
    const failed = result.failed.length ? `（${result.failed.length}曲は失敗）` : "";
    setStatus(elements.ingestStatus, `${result.embedded_track_ids.length}曲の埋め込みを計算しました${failed}`);
    await refreshStats();
  } catch (error) {
    setStatus(elements.ingestStatus, `計算に失敗しました: ${error.message}`, { error: true });
  }
}

// ---- wiring ----

function init() {
  for (const [index, name] of KEY_NAMES.entries()) {
    elements.key.append(el("option", { value: String(index), text: name }));
  }

  for (const preset of PRESETS) {
    const chip = el("button", { type: "button", className: "chip", text: preset });
    chip.addEventListener("click", () => {
      elements.text.value = preset;
      runSearch();
    });
    elements.presets.append(chip);
  }

  elements.searchForm.addEventListener("submit", (event) => {
    event.preventDefault();
    runSearch();
  });
  elements.searchForm.addEventListener("input", updateFilterCount);
  elements.resetFilters.addEventListener("click", () => {
    const text = elements.text.value;
    elements.searchForm.reset();
    elements.text.value = text;
    updateFilterCount();
  });

  elements.ingestForm.addEventListener("submit", runIngest);
  elements.backfillButton.addEventListener("click", runBackfill);

  for (const eventName of ["play", "pause", "ended"]) {
    elements.player.addEventListener(eventName, syncPlayingState);
  }

  refreshStats().then(runSearch);
}

init();
