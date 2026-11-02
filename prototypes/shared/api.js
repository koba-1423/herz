// プロトタイプ共通: Herz の API を呼ぶ（サーバーが落ちていても見た目を確認できるよう見本データに切り替える）

const SAMPLE = [
  { title: "Underneath The Moon", artist: "Taisei Iwasaki", genres: ["Soundtrack"], features: { tempo_bpm: 72, energy: 0.4, acousticness: 0.95, key: 5, mode: 1 } },
  { title: "Europa", artist: "Gato Barbieri", genres: ["Jazz"], features: { tempo_bpm: 64, energy: 0.55, acousticness: 0.7, key: 7, mode: 0 } },
  { title: "夜に駆ける", artist: "YOASOBI", genres: ["J-Pop"], features: { tempo_bpm: 130, energy: 0.85, acousticness: 0.1, key: 3, mode: 1 } },
  { title: "Plastic Love", artist: "竹内まりや", genres: ["J-Pop"], features: { tempo_bpm: 104, energy: 0.6, acousticness: 0.3, key: 9, mode: 0 } },
  { title: "Midnight City", artist: "M83", genres: ["Electronic"], features: { tempo_bpm: 105, energy: 0.75, acousticness: 0.05, key: 11, mode: 1 } },
  { title: "Clair de Lune", artist: "Claude Debussy", genres: ["Classical"], features: { tempo_bpm: 60, energy: 0.15, acousticness: 0.99, key: 1, mode: 1 } },
];

export const PRESETS = [
  "雨の日に聴きたい静かなピアノ",
  "夜のドライブ、シティポップ",
  "落ち着いたジャズ、サックス",
  "朝のカフェ、アコースティック",
  "踊れるEDM",
  "壮大なオーケストラ",
];

export async function searchVibes(text, limit = 8) {
  try {
    const response = await fetch("/search", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ text, limit }),
    });
    if (!response.ok) throw new Error(response.statusText);
    return await response.json();
  } catch {
    return SAMPLE.slice(0, limit);
  }
}

export async function libraryStats() {
  try {
    const response = await fetch("/library/stats");
    return await response.json();
  } catch {
    return { total_tracks: 200000 };
  }
}

// ジャケット画像の代わりに、曲の特徴から決まる色を返す（キー→色相、エネルギー→彩度、アコースティック→明るさ）
export function vibeColors(track) {
  const f = track.features ?? {};
  const hue = ((f.key ?? hash(track.title) % 12) * 30 + (f.mode === 0 ? 200 : 0)) % 360;
  const saturation = 35 + Math.round((f.energy ?? 0.5) * 55);
  const lightness = 35 + Math.round((f.acousticness ?? 0.5) * 30);
  return [`hsl(${hue} ${saturation}% ${lightness}%)`, `hsl(${(hue + 40) % 360} ${saturation}% ${lightness - 15}%)`];
}

export function cover(track) {
  const [a, b] = vibeColors(track);
  return `linear-gradient(135deg, ${a}, ${b})`;
}

export function bpm(track) {
  const tempo = track.features?.tempo_bpm;
  return tempo ? `${Math.round(tempo)} BPM` : "";
}

function hash(text) {
  let value = 0;
  for (const char of text) value = (value * 31 + char.charCodeAt(0)) >>> 0;
  return value;
}

export function escapeHtml(text) {
  return String(text).replace(/[&<>"']/g, (char) => `&#${char.charCodeAt(0)};`);
}
