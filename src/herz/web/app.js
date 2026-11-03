// Herz フロントエンド。ビルド不要の素のES Moduleで、同一オリジンのAPIを呼ぶ。

const KEY_NAMES = ["C", "C♯", "D", "E♭", "E", "F", "F♯", "G", "A♭", "A", "B♭", "B"];

// 最初に並べておく検索。雰囲気・曲名・リンクと、探し方がいろいろあることを見せる
const DEFAULT_SEARCHES = [
  { id: "rain", kind: "vibe", name: "雨の午後", query: "雨の日に聴きたい静かなピアノ", desc: "窓の外の雨音に溶けるような、静かなピアノとやわらかな弦。", colors: ["#5b7ea4", "#2f4a6b"] },
  { id: "night", kind: "vibe", name: "真夜中の街", query: "夜のドライブに合うシティポップ", desc: "ネオンが滲む高速道路を走る、シンセとベースのグルーヴ。", colors: ["#9b3fd1", "#ff4f8b"] },
  { id: "fire", kind: "vibe", name: "燃える夜", query: "疾走感のある激しいロック", desc: "全身で浴びたい、歪んだギターと叩きつけるドラム。", colors: ["#e8402f", "#c9681a"] },
  { id: "plastic-love", kind: "song", name: "プラスティック・ラブ みたいな曲", query: "Plastic Love 竹内まりや" },
  { id: "apple-music", kind: "link", name: "Apple Music のリンクから", query: "https://music.apple.com/jp/album/pretender/1459216693?i=1459216694" },
  { id: "spotify", kind: "link", name: "Spotify のリンクから", query: "https://open.spotify.com/track/3GtvQ0cNCR6koB8Od7laEU" },
  { id: "youtube", kind: "link", name: "YouTube のリンクから", query: "https://www.youtube.com/watch?v=x8VYWazR5mE" },
];

const KIND_LABELS = { vibe: "雰囲気", song: "曲名", link: "リンク" };

const RANGE_FIELDS = ["tempo_bpm", "energy", "acousticness"];

const FAVORITES_KEY = "herz.favorites";
// 左の検索の一覧（並び・名前の変更や削除も含めて、このブラウザだけに保存）
const SEARCHES_KEY = "herz.searches";
const MAX_SEARCHES = 30;
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
  resetSearches: $("#reset-searches"),
  backdrop: $("#backdrop"),
  backdropArt: $("#backdrop-art"),
  backdropCover: $("#backdrop-cover"),
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
  current: null, // 左の一覧で選んでいる検索（結果の「似た曲」から探しているときは null）
  searches: loadSearches(), // [{ id, kind, name, query, desc?, colors?, artwork? }]
  beforeSeed: null, // 結果の「似た曲」を押す前に選んでいた検索
  favorites: loadFavorites(), // [{ id, title, artist, artwork_url }]
};

// ---- このブラウザだけに保存するもの ----

function loadSearches() {
  try {
    const saved = JSON.parse(localStorage.getItem(SEARCHES_KEY) || "null");
    if (Array.isArray(saved)) return saved.filter((item) => item?.id && item.query && KIND_LABELS[item.kind]);
  } catch {
    // 読めなければ最初の一覧を使う
  }
  return structuredClone(DEFAULT_SEARCHES);
}

function saveSearches() {
  try {
    localStorage.setItem(SEARCHES_KEY, JSON.stringify(state.searches));
  } catch {
    // 保存できなくても、このページを開いている間は使える
  }
}

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
    elements.resetSearches.hidden = true;
    elements.textHint.textContent =
      "自然文検索 (CLAP) が無効になっています。`uv sync --extra clap` で有効にできます。条件での絞り込みは使えます。";
    elements.textHint.classList.add("warning");
  }

  const missing = total_tracks - embedded_tracks;
  elements.backfill.hidden = !(text_search_available && missing > 0);
  elements.backfillNote.textContent = `${missing}曲がまだ雰囲気検索の対象になっていません（埋め込み未計算）。`;
}

// ---- 左の検索の一覧と、背景・上の線の色 ----

function paint([a, b]) {
  const root = document.documentElement.style;
  root.setProperty("--a", a);
  root.setProperty("--b", b);
}

// 背景: 雰囲気の検索ならその色をうすく、曲から探すならジャケット写真をぼかして敷く
function showBackdrop({ colors = null, artwork = null }) {
  if (colors) paint(colors);
  elements.backdrop.classList.toggle("art", Boolean(artwork));
  if (artwork) {
    const image = `url("${largeArtwork(artwork)}")`;
    elements.backdropArt.style.backgroundImage = image;
    elements.backdropCover.style.backgroundImage = image;
  }
}

// iTunes のジャケット画像は URL の寸法を書き換えると大きい画像が取れる
function largeArtwork(url) {
  return url.replace(/\/\d+x\d+bb\./, "/1200x1200bb.");
}

function setHeading(title, desc) {
  elements.moodTitle.textContent = title;
  elements.moodDesc.textContent = desc;
}

function selectedKind() {
  return elements.searchForm.querySelector('input[name="kind"]:checked')?.value ?? "vibe";
}

function setKind(kind) {
  const radio = elements.searchForm.querySelector(`input[name="kind"][value="${kind === "song" ? "song" : "vibe"}"]`);
  if (radio) radio.checked = true;
  syncPlaceholder();
}

function syncPlaceholder() {
  elements.text.placeholder =
    selectedKind() === "song" ? "曲名・アーティスト名、または曲のURL" : "雰囲気を言葉で書く、または曲のURL";
}

function searchButton(item) {
  const marker = item.artwork
    ? el("img", { className: "dot art", src: item.artwork, alt: "", width: "18", height: "18" })
    : el("span", { className: "dot", "aria-hidden": "true" });
  const button = el("button", { type: "button", className: "mood", "aria-pressed": "false", "data-id": item.id, title: item.query }, [
    marker,
    el("span", { className: "mood-name", text: item.name }),
    el("span", { className: "kind", text: KIND_LABELS[item.kind] }),
  ]);
  button.style.setProperty("--dot", item.colors?.[0] ?? "#86868b");
  button.addEventListener("click", () => runItem(item));
  return button;
}

function renderSearches() {
  const items = state.searches.map((item) => {
    const rename = el("button", { type: "button", className: "mood-action", text: "✎", "aria-label": `「${item.name}」の名前を変える`, title: "名前を変える" });
    rename.addEventListener("click", () => startRename(item));
    const remove = el("button", { type: "button", className: "mood-action", text: "×", "aria-label": `「${item.name}」を一覧から消す`, title: "一覧から消す" });
    remove.addEventListener("click", () => removeSearch(item));
    return el("li", { className: "mood-item", "data-id": item.id }, [searchButton(item), rename, remove]);
  });
  if (!items.length) items.push(el("li", { className: "moods-empty", text: "一覧は空です。下で探すと、ここに加わります。" }));
  elements.moods.replaceChildren(...items);
  syncSearchButtons();
}

function syncSearchButtons() {
  for (const button of elements.moods.querySelectorAll(".mood")) {
    button.setAttribute("aria-pressed", String(state.current?.id === button.dataset.id));
  }
}

function startRename(item) {
  const row = elements.moods.querySelector(`.mood-item[data-id="${CSS.escape(item.id)}"]`);
  if (!row) return;
  const input = el("input", { type: "text", className: "rename", value: item.name, maxlength: "60", "aria-label": "新しい名前" });
  let done = false;
  const finish = (save) => {
    if (done) return;
    done = true;
    const name = input.value.trim();
    if (save && name) updateSearch(item, { name });
    renderSearches();
    if (state.current?.id === item.id) elements.moodTitle.textContent = item.name;
  };
  input.addEventListener("keydown", (event) => {
    if (event.isComposing) return;
    if (event.key === "Enter") finish(true);
    if (event.key === "Escape") finish(false);
  });
  input.addEventListener("blur", () => finish(true));
  row.replaceChildren(input);
  input.focus();
  input.select();
}

function updateSearch(item, changes) {
  Object.assign(item, changes);
  if (state.searches.includes(item)) {
    saveSearches();
    renderSearches();
  }
}

function addSearch(item) {
  state.searches = [...state.searches, item].slice(-MAX_SEARCHES);
  saveSearches();
  renderSearches();
}

function removeSearch(item) {
  state.searches = state.searches.filter((saved) => saved.id !== item.id);
  saveSearches();
  if (state.current?.id === item.id) state.current = null;
  renderSearches();
}

function resetSearches() {
  state.searches = structuredClone(DEFAULT_SEARCHES);
  saveSearches();
  state.current = null;
  renderSearches();
}

// 検索窓の内容から、一覧にある検索か、新しい検索を作る
function itemFromInput(text) {
  const kind = isLink(text) ? "link" : selectedKind();
  const existing = state.searches.find((item) => item.kind === kind && item.query === text);
  if (existing) return { item: existing, isNew: false };
  return { item: { id: `my-${Date.now().toString(36)}`, kind, name: text, query: text }, isNew: true };
}

async function runItem(item, { isNew = false } = {}) {
  state.current = item;
  state.seed = null;
  state.beforeSeed = null;
  elements.seed.hidden = true;
  elements.text.value = item.query;
  setKind(item.kind);
  syncSearchButtons();

  if (item.kind === "vibe") {
    showBackdrop({ colors: item.colors });
    setHeading(item.name, item.desc ?? "書いた言葉に、雰囲気が近い順です。");
    const result = await runSearch();
    if (!result || state.current !== item) return;
    if (result.interpreted && !item.desc) setHeading(item.name, `“${result.interpreted}” として探しました。`);
    if (!item.colors && result.tracks.length) {
      // 一覧の点と上の線の色は、上位の曲の色から決める
      item.colors = colorsFromTracks(result.tracks);
      showBackdrop({ colors: item.colors });
    }
    if (isNew && result.tracks.length) addSearch(item);
    else updateSearch(item, {});
    return;
  }

  setStatus(elements.searchStatus, item.kind === "link" ? "リンクの曲を探しています…" : "曲を探しています…", { busy: true });
  let found;
  try {
    found = await findSong(item.query);
  } catch (error) {
    setStatus(elements.searchStatus, `曲を特定できませんでした: ${error.message}`, { error: true });
    return;
  }
  if (state.current !== item) return;
  const { track, artwork } = found;
  if (isNew) item.name = item.kind === "link" ? `${serviceName(item.query)}：${track.title}` : `${track.title} みたいな曲`;
  item.artwork = artwork ?? item.artwork;
  const result = await searchFromTrack(track, item.artwork, item.name);
  if (state.current !== item) return;
  if (result?.tracks.length) item.colors = colorsFromTracks(result.tracks);
  if (isNew) addSearch(item);
  else updateSearch(item, {});
}

function serviceName(url) {
  const host = new URL(url).hostname;
  if (host.includes("spotify")) return "Spotify";
  if (host.includes("youtube") || host.includes("youtu.be")) return "YouTube";
  if (host.includes("apple")) return "Apple Music";
  return "リンク";
}

function colorsFromTracks(tracks) {
  const [a] = vibeColors(tracks[0]);
  const [, b] = vibeColors(tracks[Math.min(2, tracks.length - 1)]);
  return [a, b];
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
  // 曲から探すときは曲だけを基準にし、検索窓の文（曲名やURL）は雰囲気として使わない
  if (state.seed) query.seed_track_ids = [state.seed.id];
  else if (text && !elements.text.disabled) query.text = text;

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

// 曲名や Apple Music / Spotify / YouTube のURLから曲を特定し、ライブラリに取り込んで返す
async function findSong(term) {
  const { payload: songs, headers } = await api(`/catalog/search?${new URLSearchParams({ term, limit: "5" })}`, {
    withHeaders: true,
  });
  const detected = headers.get("x-herz-detected");
  if (!songs.length) {
    const what = detected ? `「${decodeURIComponent(detected)}」` : `「${term}」`;
    throw new Error(`${what}がiTunesで見つかりませんでした`);
  }
  // ライブラリに取り込み済みの曲があれば、解析を待たずに済むのでそれを優先する
  const song = songs.find((candidate) => candidate.track_id) ?? songs[0];
  const track = await api("/library/tracks", {
    method: "POST",
    body: { source_track_id: song.source_track_id },
  });
  return { track: { ...track, artwork_url: song.artwork_url }, artwork: song.artwork_url };
}

// 曲名・アーティスト名からジャケット写真を探す（見つからなくても検索は続ける）
async function findArtwork(track) {
  try {
    const songs = await api(`/catalog/search?${new URLSearchParams({ term: `${track.title} ${track.artist}`, limit: "1" })}`);
    return songs[0]?.artwork_url ?? null;
  } catch {
    return null;
  }
}

// 検索結果を表示して { tracks, interpreted } を返す（失敗したら null）
async function runSearch() {
  const query = buildQuery();
  const submit = elements.searchForm.querySelector('button[type="submit"]');

  setStatus(elements.searchStatus, "検索しています…", { busy: true });
  try {
    const { payload: tracks, headers } = await withBusyButton(submit, () =>
      api("/search", { method: "POST", body: query, withHeaders: true }),
    );
    // 日本語の検索文は英語に変換してから検索される。どう解釈したかを見せる
    const english = headers.get("x-herz-query");
    const decoded = english ? decodeURIComponent(english) : null;
    const interpreted = decoded !== query.text ? decoded : null;
    renderResults(tracks, query, interpreted);
    if (!query.text && !query.seed_track_ids) {
      setHeading("ライブラリの曲", "雰囲気や曲名で探すと、近い順に並びます。");
    }
    return { tracks, interpreted };
  } catch (error) {
    elements.results.replaceChildren();
    setStatus(elements.searchStatus, `検索に失敗しました: ${error.message}`, { error: true });
    return null;
  }
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

// 曲を基準に、雰囲気の近い曲を探す。背景はその曲のジャケット写真にする
async function searchFromTrack(track, artwork, title) {
  state.seed = { id: track.id, title: track.title, artist: track.artist };
  elements.seedLabel.textContent = `「${track.title}」（${track.artist}）に雰囲気が近い曲`;
  elements.seed.hidden = false;
  setHeading(title, `「${track.title}」（${track.artist}）と雰囲気が近い順です。`);
  if (artwork) showBackdrop({ artwork });
  const result = await runSearch();
  if (result?.tracks.length && state.seed?.id === track.id) paint(colorsFromTracks(result.tracks));
  return result;
}

// 結果の「似た曲」から探す。やめたら元の検索に戻す
async function searchSimilarTo(track) {
  state.beforeSeed = state.current ?? state.beforeSeed;
  state.current = null;
  syncSearchButtons();
  showTab("search");
  window.scrollTo({ top: 0, behavior: "smooth" });
  const artwork = track.artwork_url ?? null;
  const search = searchFromTrack(track, artwork, "この曲に似た曲");
  if (!artwork) {
    const found = await findArtwork(track);
    if (found && state.seed?.id === track.id) showBackdrop({ artwork: found });
  }
  await search;
}

function clearSeed() {
  const previous = state.beforeSeed;
  state.seed = null;
  state.beforeSeed = null;
  elements.seed.hidden = true;
  if (previous) runItem(previous);
  else {
    showBackdrop({});
    runSearch();
  }
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
  item.style.setProperty("--dot", vibeColors(track)[0]);
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

  renderSearches();
  elements.resetSearches.addEventListener("click", resetSearches);
  for (const radio of elements.searchForm.querySelectorAll('input[name="kind"]')) {
    radio.addEventListener("change", syncPlaceholder);
  }

  elements.searchForm.addEventListener("submit", (event) => {
    event.preventDefault();
    const text = elements.text.value.trim();
    if (!text) return;
    const { item, isNew } = itemFromInput(text);
    runItem(item, { isNew });
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

  refreshStats().then(() => {
    const first = state.searches.find((item) => item.kind === "vibe") ?? state.searches[0];
    if (first) runItem(first);
    else runSearch();
  });
}

init();
