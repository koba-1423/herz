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

const FAVORITES_KEY = "herz.favorites";
const MIN_FAVORITES_FOR_ANALYSIS = 3;

const ICON_PLAY = '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M4 2.5v11l9-5.5z"/></svg>';
const ICON_HEART =
  '<svg viewBox="0 0 16 16" aria-hidden="true"><path d="M8 14s-5.5-3.4-5.5-7.2A3 3 0 0 1 8 4.6a3 3 0 0 1 5.5 2.2C13.5 10.6 8 14 8 14z"/></svg>';
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
  tabs: [$("#tab-search"), $("#tab-taste")],
  seed: $("#seed"),
  seedLabel: $("#seed-label"),
  seedClear: $("#seed-clear"),
  favoriteCount: $("#favorite-count"),
  catalogForm: $("#catalog-form"),
  catalogTerm: $("#catalog-term"),
  catalogStatus: $("#catalog-status"),
  catalog: $("#catalog"),
  favorites: $("#favorites"),
  favoritesSummary: $("#favorites-summary"),
  analyzeButton: $("#analyze-button"),
  tasteStatus: $("#taste-status"),
  profile: $("#profile"),
  profileWords: $("#profile-words"),
  profileAvoided: $("#profile-avoided"),
  profileFeatures: $("#profile-features"),
  recommendations: $("#recommendations"),
};

const state = {
  stats: null,
  playingId: null,
  seed: null, // 「この曲みたいな曲」の基準にしている曲
  favorites: loadFavorites(), // [{ id, title, artist, artwork_url }]
};

// ---- favorites (このブラウザだけに保存) ----

function loadFavorites() {
  try {
    const saved = JSON.parse(localStorage.getItem(FAVORITES_KEY) || "[]");
    return Array.isArray(saved) ? saved : [];
  } catch {
    return [];
  }
}

function saveFavorites() {
  try {
    localStorage.setItem(FAVORITES_KEY, JSON.stringify(state.favorites));
  } catch {
    // 保存できなくても、このページを開いている間は使える
  }
}

function isFavorite(trackId) {
  return state.favorites.some((favorite) => favorite.id === trackId);
}

function toggleFavorite(track) {
  if (isFavorite(track.id)) {
    state.favorites = state.favorites.filter((favorite) => favorite.id !== track.id);
  } else {
    const { id, title, artist, artwork_url = null } = track;
    state.favorites = [...state.favorites, { id, title, artist, artwork_url }];
  }
  saveFavorites();
  renderFavorites();
  syncFavoriteButtons();
}

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
  if (state.seed) query.seed_track_ids = [state.seed.id];

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
  return Object.keys(query).filter((name) => !["limit", "text", "seed_track_ids"].includes(name)).length;
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

  const ordering = query.text || query.seed_track_ids ? "雰囲気が近い順" : "アーティスト名順";
  const count = tracks.length >= query.limit ? `上位${tracks.length}曲` : `${tracks.length}曲`;
  setStatus(elements.searchStatus, `${count}（${ordering}）`);
  elements.results.replaceChildren(...tracks.map((track) => renderTrack(track)));
  syncPlayingState();
}

function searchSimilarTo(track) {
  state.seed = { id: track.id, title: track.title, artist: track.artist };
  elements.seedLabel.textContent = `「${track.title}」（${track.artist}）に雰囲気が近い曲`;
  elements.seed.hidden = false;
  showTab("search");
  window.scrollTo({ top: 0, behavior: "smooth" });
  runSearch();
}

function clearSeed() {
  state.seed = null;
  elements.seed.hidden = true;
  runSearch();
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

  const favorite = el("button", {
    type: "button",
    className: "icon-button favorite-button",
    "aria-pressed": String(isFavorite(track.id)),
    "aria-label": `${track.title} を好きな曲に追加`,
    title: "好きな曲に追加",
  });
  favorite.innerHTML = ICON_HEART;
  favorite.addEventListener("click", () => toggleFavorite(track));

  const similar = el("button", { type: "button", className: "link-button", text: "似た曲" });
  similar.addEventListener("click", () => searchSimilarTo(track));

  return el("li", { className: "track", "data-id": track.id }, [
    play,
    el("div", { className: "meta" }, [
      el("div", { className: "track-title", text: track.title }),
      el("div", { className: "track-artist", text: track.artist }),
    ]),
    score,
    el("div", { className: "facts" }, [
      favorite,
      similar,
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
  for (const item of document.querySelectorAll(".track")) {
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

// ---- tabs ----

function showTab(name) {
  for (const tab of elements.tabs) {
    const selected = tab.id === `tab-${name}`;
    tab.setAttribute("aria-selected", String(selected));
    document.getElementById(tab.getAttribute("aria-controls")).hidden = !selected;
  }
}

// ---- taste ----

function syncFavoriteButtons() {
  for (const item of document.querySelectorAll(".track")) {
    const button = item.querySelector(".favorite-button");
    if (button) button.setAttribute("aria-pressed", String(isFavorite(item.dataset.id)));
  }
}

function artwork(url) {
  return url
    ? el("img", { className: "artwork", src: url, alt: "", loading: "lazy", width: "40", height: "40" })
    : el("span", { className: "artwork", "aria-hidden": "true" });
}

function renderFavorites() {
  const count = state.favorites.length;
  elements.favoriteCount.textContent = count ? String(count) : "";
  elements.favoritesSummary.textContent = count ? `${count}曲` : "";
  elements.analyzeButton.disabled = count < MIN_FAVORITES_FOR_ANALYSIS;

  if (!count) {
    elements.favorites.replaceChildren(
      el("li", { className: "empty", text: "まだありません。上で曲を探して追加してください。" }),
    );
    return;
  }
  elements.favorites.replaceChildren(
    ...state.favorites.map((favorite) => {
      const remove = el("button", {
        type: "button",
        className: "button ghost",
        text: "外す",
        "aria-label": `${favorite.title} を好きな曲から外す`,
      });
      remove.addEventListener("click", () => toggleFavorite(favorite));
      return el("li", { className: "song-row" }, [
        artwork(favorite.artwork_url),
        el("div", { className: "meta" }, [
          el("div", { className: "track-title", text: favorite.title }),
          el("div", { className: "track-artist", text: favorite.artist }),
        ]),
        remove,
      ]);
    }),
  );
}

async function runCatalogSearch(event) {
  event.preventDefault();
  const term = elements.catalogTerm.value.trim();
  if (!term) return;

  setStatus(elements.catalogStatus, "探しています…", { busy: true });
  try {
    const songs = await api(`/catalog/search?${new URLSearchParams({ term, limit: "8" })}`);
    setStatus(elements.catalogStatus, songs.length ? "" : "見つかりませんでした。");
    elements.catalog.replaceChildren(...songs.map(renderCatalogSong));
  } catch (error) {
    setStatus(elements.catalogStatus, `検索に失敗しました: ${error.message}`, { error: true });
  }
}

function renderCatalogSong(song) {
  const add = el("button", { type: "button", className: "button", text: "追加" });
  const added = () => {
    add.textContent = "追加済み";
    add.disabled = true;
  };
  if (song.track_id && isFavorite(song.track_id)) added();

  add.addEventListener("click", async () => {
    add.disabled = true;
    add.textContent = song.track_id ? "追加中…" : "解析中…";
    try {
      // ライブラリに無い曲はここで取り込む（プレビューの解析に数秒かかる）
      const track = await api("/library/tracks", {
        method: "POST",
        body: { source_track_id: song.source_track_id },
      });
      if (!isFavorite(track.id)) toggleFavorite({ ...track, artwork_url: song.artwork_url });
      added();
    } catch (error) {
      add.disabled = false;
      add.textContent = "追加";
      setStatus(elements.catalogStatus, `追加できませんでした: ${error.message}`, { error: true });
    }
  });

  return el("li", { className: "song-row" }, [
    artwork(song.artwork_url),
    el("div", { className: "meta" }, [
      el("div", { className: "track-title", text: song.title }),
      el("div", { className: "track-artist", text: [song.artist, song.genre].filter(Boolean).join(" ・ ") }),
    ]),
    add,
  ]);
}

function describePercentile(percentile) {
  if (percentile >= 50) return `上位${Math.max(1, Math.round(100 - percentile))}%`;
  return `下位${Math.max(1, Math.round(percentile))}%`;
}

function formatFeatureValue(feature) {
  if (feature.name === "tempo_bpm") return `平均 ${Math.round(feature.value)} BPM`;
  if (feature.name === "loudness_db") return `平均 ${feature.value.toFixed(1)} dB`;
  return `平均 ${feature.value.toFixed(2)}`;
}

async function runTasteAnalysis() {
  setStatus(elements.tasteStatus, "分析しています…", { busy: true });
  try {
    const profile = await withBusyButton(elements.analyzeButton, () =>
      api("/taste", {
        method: "POST",
        body: { track_ids: state.favorites.map((favorite) => favorite.id), recommendation_limit: 20 },
      }),
    );
    setStatus(elements.tasteStatus, `${profile.track_count}曲から分析しました`);
    renderProfile(profile);
  } catch (error) {
    elements.profile.hidden = true;
    setStatus(elements.tasteStatus, `分析に失敗しました: ${error.message}`, { error: true });
  }
}

function renderProfile(profile) {
  const strongest = profile.descriptors[0]?.score || 1;
  elements.profileWords.replaceChildren(
    ...profile.descriptors.map((descriptor) => {
      // 一番強い言葉を基準に、文字の大きさで強さを表す
      const weight = Math.max(0.35, descriptor.score / strongest);
      const word = el("li", { className: "word", text: descriptor.label, title: descriptor.prompt });
      word.style.setProperty("--weight", weight.toFixed(2));
      return word;
    }),
  );
  elements.profileAvoided.textContent = profile.avoided.length
    ? `逆に少なめなのは「${profile.avoided.map((d) => d.label).join("」「")}」。`
    : "";

  const features = profile.features.map((feature) => {
    const bar = el("span", { className: "meter-bar wide", "aria-hidden": "true" }, el("span"));
    bar.firstChild.style.width = `${Math.round(feature.percentile)}%`;
    return el("li", { className: "insight" }, [
      el("span", { className: "insight-label", text: feature.label }),
      bar,
      el("span", { className: "insight-value", text: `${describePercentile(feature.percentile)}・${formatFeatureValue(feature)}` }),
    ]);
  });
  if (profile.major_ratio !== null) {
    const major = Math.round(profile.major_ratio * 100);
    features.push(
      el("li", { className: "insight" }, [
        el("span", { className: "insight-label", text: "曲調" }),
        el("span", { className: "insight-value", text: `長調（明るめ）${major}% ・ 短調（暗め）${100 - major}%` }),
      ]),
    );
  }
  elements.profileFeatures.replaceChildren(...features);

  elements.recommendations.replaceChildren(...profile.recommendations.map((track) => renderTrack(track)));
  elements.profile.hidden = false;
  syncPlayingState();
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

  elements.seedClear.addEventListener("click", clearSeed);
  for (const tab of elements.tabs) {
    tab.addEventListener("click", () => showTab(tab.id.replace("tab-", "")));
  }
  elements.catalogForm.addEventListener("submit", runCatalogSearch);
  elements.analyzeButton.addEventListener("click", runTasteAnalysis);
  renderFavorites();

  elements.ingestForm.addEventListener("submit", runIngest);
  elements.backfillButton.addEventListener("click", runBackfill);

  for (const eventName of ["play", "pause", "ended"]) {
    elements.player.addEventListener(eventName, syncPlayingState);
  }

  refreshStats().then(runSearch);
}

init();
