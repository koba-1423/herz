// Herz フロントエンド。ビルド不要の素のES Moduleで、同一オリジンのAPIを呼ぶ。

const KEY_NAMES = ["C", "C♯", "D", "E♭", "E", "F", "F♯", "G", "A♭", "A", "B♭", "B"];

// 気分のタイル。選ぶと検索文が入り、背景がその色になる
const MOODS = [
  { ja: "雨の午後", en: "Rainy afternoon", desc: "窓の外の雨音に溶けるような、静かなピアノとやわらかな弦。", query: "雨の日に聴きたい静かなピアノ", colors: ["#5b7ea4", "#2f4a6b", "#1c2838"] },
  { ja: "真夜中の街", en: "Midnight city", desc: "ネオンが滲む高速道路を走る、シンセとベースのグルーヴ。", query: "夜のドライブに合うシティポップ", colors: ["#9b3fd1", "#ff4f8b", "#120b2b"] },
  { ja: "夏の海辺", en: "Summer shore", desc: "まぶしい光と潮風。軽やかなギターと跳ねるリズム。", query: "夏の海辺で聴きたい明るいギターの曲", colors: ["#e8963a", "#2fb3ad", "#123f52"] },
  { ja: "森の朝", en: "Forest morning", desc: "鳥の声と木漏れ日。アコースティックで澄んだ響き。", query: "朝のカフェ、アコースティック", colors: ["#7fa95c", "#3f7d4f", "#16301f"] },
  { ja: "燃える夜", en: "Burning night", desc: "全身で浴びたい、歪んだギターと叩きつけるドラム。", query: "疾走感のある激しいロック", colors: ["#e8402f", "#c9681a", "#2a0a06"] },
  { ja: "星を見上げて", en: "Under the stars", desc: "広がっていくアンビエントと、遠くで鳴るシンセ。", query: "宇宙を感じる幻想的なアンビエント", colors: ["#5a67e0", "#8a76d6", "#0a0c24"] },
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
  moods: $("#moods"),
  moodEn: $("#mood-en"),
  moodTitle: $("#mood-title"),
  moodDesc: $("#mood-desc"),
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
  mood: null, // 選んでいる気分のタイル（自分で書いた検索文なら null）
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

async function api(path, { method = "GET", body, withHeaders = false } = {}) {
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
  return withHeaders ? { payload, headers: response.headers } : payload;
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
    ? `${embedded_tracks.toLocaleString()}曲から探せます`
    : `ライブラリ ${total_tracks.toLocaleString()}曲`;

  if (!text_search_available) {
    elements.text.disabled = true;
    elements.text.placeholder = "自然文検索は無効です";
    elements.moods.hidden = true;
    elements.textHint.textContent =
      "自然文検索 (CLAP) が無効になっています。`uv sync --extra clap` で有効にできます。条件での絞り込みは使えます。";
    elements.textHint.classList.add("warning");
  }

  const missing = total_tracks - embedded_tracks;
  elements.backfill.hidden = !(text_search_available && missing > 0);
  elements.backfillNote.textContent = `${missing}曲がまだ雰囲気検索の対象になっていません（埋め込み未計算）。`;
}

// ---- mood (見出しと背景の色) ----

function paint([a, b, c]) {
  const root = document.documentElement.style;
  root.setProperty("--a", a);
  root.setProperty("--b", b);
  root.setProperty("--c", c);
}

function setHeading(en, title, desc) {
  elements.moodEn.textContent = en;
  elements.moodTitle.textContent = title;
  // 自分で書いた長い検索文は、見出しを小さめにする
  elements.moodTitle.classList.toggle("small", title.length > 10);
  elements.moodDesc.textContent = desc;
}

function chooseMood(mood) {
  state.mood = mood;
  elements.text.value = mood.query;
  setHeading(mood.en, mood.ja, mood.desc);
  paint(mood.colors);
  syncMoodButtons();
  runSearch();
}

function syncMoodButtons() {
  for (const button of elements.moods.children) {
    button.setAttribute("aria-pressed", String(state.mood?.ja === button.textContent));
  }
}

// 気分のタイル以外で検索したときは、上位の曲の色で背景を塗る
function paintFromTracks(tracks) {
  if (!tracks.length) return;
  const [a, b] = vibeColors(tracks[0]);
  paint([a, vibeColors(tracks[Math.min(2, tracks.length - 1)])[1] ?? b, "#10141f"]);
}

// ジャケット画像の代わりに、曲の特徴から決まる色を返す（キー→色相、エネルギー→彩度、アコースティック→明るさ）
function vibeColors(track) {
  const features = track.features ?? {};
  const key = features.key ?? -1;
  const hue = (key >= 0 ? key * 30 : 210) + (features.mode === 0 ? 200 : 0);
  const saturation = 35 + Math.round((features.energy ?? 0.5) * 55);
  const lightness = 35 + Math.round((features.acousticness ?? 0.5) * 30);
  return [`hsl(${hue % 360} ${saturation}% ${lightness}%)`, `hsl(${(hue + 40) % 360} ${saturation}% ${lightness - 15}%)`];
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

const isLink = (text) => /^\s*https?:\/\//.test(text);

// Apple Music / Spotify / YouTube のURLから曲を特定し、ライブラリに取り込んで返す
async function trackFromLink(url) {
  const { payload: songs, headers } = await api(`/catalog/search?${new URLSearchParams({ term: url, limit: "5" })}`, {
    withHeaders: true,
  });
  const detected = headers.get("x-herz-detected");
  if (!songs.length) {
    const what = detected ? `「${decodeURIComponent(detected)}」` : "このURLの曲";
    throw new Error(`${what}がiTunesで見つかりませんでした`);
  }
  const track = await api("/library/tracks", {
    method: "POST",
    body: { source_track_id: songs[0].source_track_id },
  });
  return { ...track, artwork_url: songs[0].artwork_url };
}

async function runSearch() {
  const text = elements.text.value.trim();
  if (isLink(text)) {
    // URLが貼られたら、その曲に雰囲気が近い曲を探す
    setStatus(elements.searchStatus, "URLの曲を探しています…", { busy: true });
    try {
      const track = await trackFromLink(text);
      elements.text.value = "";
      searchSimilarTo(track);
    } catch (error) {
      setStatus(elements.searchStatus, `URLの曲を特定できませんでした: ${error.message}`, { error: true });
    }
    return;
  }

  const query = buildQuery();
  const submit = elements.searchForm.querySelector('button[type="submit"]');

  setStatus(elements.searchStatus, "検索しています…", { busy: true });
  try {
    const { payload: tracks, headers } = await withBusyButton(submit, () =>
      api("/search", { method: "POST", body: query, withHeaders: true }),
    );
    // 日本語の検索文は英語に変換してから検索される。どう解釈したかを見せる
    const english = headers.get("x-herz-query");
    const interpreted = english ? decodeURIComponent(english) : null;
    renderResults(tracks, query, interpreted !== query.text ? interpreted : null);
    describeSearch(query, interpreted, tracks);
  } catch (error) {
    elements.results.replaceChildren();
    setStatus(elements.searchStatus, `検索に失敗しました: ${error.message}`, { error: true });
  }
}

function describeSearch(query, interpreted, tracks) {
  if (state.seed) {
    setHeading("Similar to", "この曲に似た曲", `「${state.seed.title}」（${state.seed.artist}）と雰囲気が近い順に並べています。`);
  } else if (!state.mood && query.text) {
    setHeading("Your words", `「${query.text}」`, interpreted ? `“${interpreted}” として探しました。` : "あなたの言葉に近い順に並べています。");
  } else if (!state.mood) {
    setHeading("Library", "ライブラリの曲", "気分を選ぶか、言葉で書くと、雰囲気の近い順に並びます。");
  }
  if (state.seed || !state.mood) paintFromTracks(tracks);
}

function renderResults(tracks, query, interpreted = null) {
  if (!tracks.length) {
    const libraryEmpty = state.stats && state.stats.total_tracks === 0;
    setStatus(elements.searchStatus, "");
    elements.results.replaceChildren(
      el("li", {
        className: "empty",
        text: libraryEmpty
          ? "まだ曲がありません。ページ下の「ライブラリに曲を追加」から取り込んでください。"
          : "条件に合う曲が見つかりませんでした。条件をゆるめてみてください。",
      }),
    );
    return;
  }

  const ordering = query.text || query.seed_track_ids ? "雰囲気が近い順" : "アーティスト名順";
  const count = tracks.length >= query.limit ? `上位${tracks.length}曲` : `${tracks.length}曲`;
  setStatus(
    elements.searchStatus,
    interpreted ? `${count}（${ordering}）・「${interpreted}」として検索` : `${count}（${ordering}）`,
  );
  elements.results.replaceChildren(...tracks.map((track, index) => renderTrack(track, index)));
  syncPlayingState();
}

function searchSimilarTo(track) {
  state.seed = { id: track.id, title: track.title, artist: track.artist };
  state.mood = null;
  syncMoodButtons();
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

function renderTrack(track, index = 0) {
  const { features } = track;
  const playable = Boolean(track.preview_url);

  const play = el("button", {
    type: "button",
    className: "play",
    "aria-label": `${track.title} を試聴`,
    disabled: !playable,
  });
  play.innerHTML = ICON_PLAY;
  play.style.setProperty("--dot", vibeColors(track)[0]);
  play.addEventListener("click", () => togglePlay(track));

  const tags = [
    features.tempo_bpm ? el("span", { className: "tag", text: `${Math.round(features.tempo_bpm)} BPM` }) : null,
    formatKey(features) ? el("span", { className: "tag", text: formatKey(features) }) : null,
    ...track.genres.map((genre) => el("span", { className: "tag", text: genre })),
  ];

  const score =
    track.similarity === null || track.similarity === undefined
      ? null
      : el("div", { className: "score", title: "検索した雰囲気と曲のコサイン類似度" }, [
          el("strong", { text: track.similarity.toFixed(2) }),
          "近さ",
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

  const item = el("li", { className: "track", "data-id": track.id }, [
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
      track.external_url
        ? el("a", {
            className: "external",
            href: track.external_url,
            target: "_blank",
            rel: "noopener noreferrer",
            text: "Apple Music ↗",
            title: "Apple Musicで開く",
          })
        : null,
    ]),
  ]);
  item.style.setProperty("--i", String(index));
  return item;
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

  setStatus(elements.catalogStatus, isLink(term) ? "URLの曲を探しています…" : "探しています…", { busy: true });
  try {
    const { payload: songs, headers } = await api(
      `/catalog/search?${new URLSearchParams({ term, limit: "8" })}`,
      { withHeaders: true },
    );
    const detected = headers.get("x-herz-detected");
    const found = detected ? `「${decodeURIComponent(detected)}」の候補です。` : "";
    setStatus(elements.catalogStatus, songs.length ? found : `${found}見つかりませんでした。`);
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

  elements.recommendations.replaceChildren(...profile.recommendations.map((track, index) => renderTrack(track, index)));
  elements.profile.hidden = false;
  syncPlayingState();
}

// ---- wiring ----

function init() {
  for (const [index, name] of KEY_NAMES.entries()) {
    elements.key.append(el("option", { value: String(index), text: name }));
  }

  for (const mood of MOODS) {
    const tile = el("button", { type: "button", className: "mood", text: mood.ja, "aria-pressed": "false" });
    tile.style.background = `linear-gradient(135deg, ${mood.colors[0]}, ${mood.colors[1]})`;
    tile.addEventListener("click", () => chooseMood(mood));
    elements.moods.append(tile);
  }

  elements.searchForm.addEventListener("submit", (event) => {
    event.preventDefault();
    // 自分で書き換えた検索文は、気分のタイルとは別の検索として扱う
    if (state.mood && elements.text.value.trim() !== state.mood.query) {
      state.mood = null;
      syncMoodButtons();
    }
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

  refreshStats().then(() => chooseMood(MOODS[0]));
}

init();
