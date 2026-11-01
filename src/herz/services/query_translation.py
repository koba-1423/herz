"""日本語の検索文を、CLAP（英語で学習されている）が理解できる英語に変換する。

汎用の機械翻訳は「エモい」「疾走感」「ゴリゴリ」のような音楽の言い回しをほぼ訳せず、
「雨の日に聴きたい切ないピアノ」も "I want to play a piano on a rainy day." のように
肝心の雰囲気が落ちる。そこで音楽の言葉の辞書で英語のキーワード列に置き換えるのを基本にし、
辞書の言葉を1つも含まない文だけを機械翻訳に回す。
"""

import re
import threading
import unicodedata
from typing import Any, Protocol

# (日本語, 英語)。長い語から順に照合するので「ハードロック」は「ロック」より優先される。
# 照合前に NFKC 正規化と小文字化をするので、全角・半角や大文字小文字の違いは気にしなくてよい。
# 英語の言い回しは herz.evaluate で精度を見ながら選んでいる（例: 歌謡曲は "kayokyoku" より
# "1960s japanese pop" のほうがCLAPに伝わる）
GLOSSARY: tuple[tuple[str, str], ...] = (
    # 気分・雰囲気
    ("切な", "sad melancholic"),
    ("悲し", "sad"),
    ("寂し", "lonely"),
    ("さみし", "lonely"),
    ("泣け", "emotional tearjerker"),
    ("泣き", "emotional tearjerker"),
    ("エモ", "emotional nostalgic"),
    ("明る", "bright happy"),
    ("楽し", "fun cheerful"),
    ("ハッピー", "happy"),
    ("元気", "energetic upbeat"),
    ("爽やか", "fresh breezy refreshing"),
    ("さわやか", "fresh breezy refreshing"),
    ("癒し", "healing soothing"),
    ("癒や", "healing soothing"),
    ("穏やか", "calm peaceful"),
    ("落ち着", "calm mellow"),
    ("まったり", "laid back relaxed"),
    ("リラックス", "relaxing"),
    ("優し", "gentle soft"),
    ("やさし", "gentle soft"),
    ("静か", "quiet"),
    ("激し", "intense aggressive"),
    ("熱い", "passionate intense"),
    ("アツい", "passionate intense"),
    ("盛り上が", "hype exciting"),
    ("アゲ", "hype party"),
    ("ノリノリ", "groovy upbeat"),
    ("ノれる", "groovy upbeat"),
    ("踊れ", "danceable"),
    ("疾走感", "fast driving energetic"),
    ("疾走", "fast driving"),
    ("爆音", "loud"),
    ("ダーク", "dark"),
    ("暗い", "dark gloomy"),
    ("怖い", "scary eerie"),
    ("不穏", "ominous"),
    ("幻想的", "dreamy ethereal fantasy"),
    ("神秘的", "mysterious mystical"),
    ("浮遊感", "floating dreamy ambient"),
    ("ふわふわ", "dreamy airy"),
    ("透明感", "clear airy crystalline"),
    ("壮大", "epic cinematic"),
    ("感動", "moving emotional"),
    ("ロマンチック", "romantic"),
    ("ロマンティック", "romantic"),
    ("甘い", "sweet"),
    ("セクシー", "sexy sensual"),
    ("おしゃれ", "stylish sophisticated"),
    ("お洒落", "stylish sophisticated"),
    ("オシャレ", "stylish sophisticated"),
    ("都会的", "urban"),
    ("懐かし", "nostalgic retro"),
    ("ノスタルジ", "nostalgic"),
    ("レトロ", "retro vintage"),
    ("渋い", "mature bluesy"),
    ("かっこい", "cool"),
    ("カッコい", "cool"),
    ("かっこよ", "cool"),
    ("かわいい", "cute"),
    ("可愛", "cute"),
    ("カワイイ", "cute"),
    ("中毒性", "catchy addictive"),
    ("キャッチー", "catchy"),
    ("前向き", "positive uplifting"),
    ("ポジティブ", "positive uplifting"),
    ("勇気", "inspiring uplifting"),
    ("青春", "youthful"),
    ("ゴリゴリ", "heavy"),
    ("バキバキ", "hard heavy"),
    ("ズンズン", "pounding bass"),
    ("ゆったり", "slow relaxed"),
    ("しっとり", "mellow tender"),
    ("ゆるい", "loose laid back"),
    ("アップテンポ", "upbeat fast tempo"),
    ("ミドルテンポ", "mid tempo"),
    ("スロー", "slow"),
    ("ゆっくり", "slow"),
    ("速い", "fast"),
    ("速め", "fast"),
    ("遅い", "slow"),
    ("ファンキー", "funky"),
    ("グルーヴ", "groovy"),
    ("グルーブ", "groovy"),
    ("チル", "chill"),
    # 場面・季節
    ("夏", "summer"),
    ("冬", "winter"),
    ("春", "spring"),
    ("秋", "autumn"),
    ("雨", "rainy"),
    ("深夜", "late night"),
    ("夜", "night"),
    ("朝", "morning"),
    ("夕暮れ", "sunset evening"),
    ("夕方", "sunset evening"),
    ("海", "beach ocean"),
    ("ドライブ", "driving road trip"),
    ("作業", "focus background"),
    ("勉強", "study focus"),
    ("睡眠", "sleep"),
    ("眠", "sleep"),
    ("カフェ", "cafe"),
    ("パーティ", "party"),
    ("失恋", "heartbreak"),
    ("恋", "love"),
    ("クリスマス", "christmas"),
    # 楽器
    ("ピアノ", "piano"),
    ("アコースティックギター", "acoustic guitar"),
    ("アコギ", "acoustic guitar"),
    ("エレキ", "electric guitar"),
    ("ギター", "guitar"),
    ("歪", "distorted"),
    ("ベース", "bass"),
    ("ドラム", "drums"),
    ("シンセ", "synthesizer"),
    ("ストリングス", "strings"),
    ("弦楽", "strings"),
    ("バイオリン", "violin"),
    ("ヴァイオリン", "violin"),
    ("チェロ", "cello"),
    ("オーケストラ", "orchestral"),
    ("ブラス", "brass horns"),
    ("ホーン", "brass horns"),
    ("管楽器", "brass woodwinds"),
    ("サックス", "saxophone"),
    ("トランペット", "trumpet"),
    ("フルート", "flute"),
    ("三味線", "shamisen"),
    ("和楽器", "traditional japanese instruments"),
    ("和風", "traditional japanese"),
    ("琴", "koto"),
    ("オルゴール", "music box"),
    ("口笛", "whistling"),
    ("ハーモニカ", "harmonica"),
    # 声
    ("女性ボーカル", "female vocals"),
    ("女性", "female vocals"),
    ("女声", "female vocals"),
    ("男性ボーカル", "male vocals"),
    ("男性", "male vocals"),
    ("男声", "male vocals"),
    ("ハスキー", "husky raspy voice"),
    ("ハイトーン", "high pitched vocals"),
    ("ウィスパー", "whispering vocals"),
    ("囁", "whispering vocals"),
    ("ささや", "whispering vocals"),
    ("力強い", "powerful"),
    ("ラップ", "rap"),
    ("コーラス", "vocal harmonies"),
    ("ハモ", "vocal harmonies"),
    ("合唱", "choir"),
    ("インスト", "instrumental"),
    ("歌なし", "instrumental"),
    ("歌無し", "instrumental"),
    ("ボカロ", "vocaloid"),
    ("初音ミク", "vocaloid"),
    ("ボーカル", "vocals"),
    ("歌声", "vocals"),
    # ジャンル
    ("ハードロック", "hard rock"),
    ("ポストロック", "post-rock"),
    ("ヘビメタ", "heavy metal"),
    ("デスメタル", "death metal"),
    ("メタル", "heavy metal"),
    ("パンク", "punk"),
    ("グランジ", "grunge"),
    ("オルタナ", "alternative rock"),
    ("シューゲ", "shoegaze"),
    ("ミクスチャー", "rap rock"),
    ("ロック", "rock"),
    ("シティポップ", "city pop"),
    ("ドリームポップ", "dream pop"),
    ("ポップ", "pop"),
    ("ジャジー", "jazzy"),
    ("ジャズ", "jazz"),
    ("ブルース", "blues"),
    ("ファンク", "funk"),
    ("ネオソウル", "neo soul"),
    ("ソウル", "soul"),
    ("ヒップホップ", "hip hop"),
    ("ヒップポップ", "hip hop"),
    ("トラップ", "trap"),
    ("レゲエ", "reggae"),
    ("edm", "edm"),
    ("テクノ", "techno"),
    ("ハウス", "house music"),
    ("トランス", "trance"),
    ("ダブステップ", "dubstep"),
    ("ドラムンベース", "drum and bass"),
    ("フューチャーベース", "future bass"),
    ("ディスコ", "disco"),
    ("ローファイ", "lo-fi"),
    ("アンビエント", "ambient"),
    ("クラシック", "classical"),
    ("フォーク", "folk"),
    ("カントリー", "country"),
    ("ボサノバ", "bossa nova"),
    ("ラテン", "latin"),
    ("サンバ", "samba"),
    ("歌謡曲", "1960s japanese pop"),
    ("昭和", "1960s japanese pop"),
    ("演歌", "enka"),
    ("アイドル", "idol pop"),
    ("アニソン", "anime song"),
    ("アニメ", "anime song"),
    ("ゲーム音楽", "video game music"),
    ("チップチューン", "chiptune 8-bit"),
    ("8bit", "chiptune 8-bit"),
    ("サントラ", "film score soundtrack"),
    ("映画音楽", "film score soundtrack"),
    ("ゴスペル", "gospel"),
    ("バラード", "ballad"),
    ("弾き語り", "acoustic singer-songwriter"),
    ("ライブ", "live"),
    ("k-pop", "k-pop"),
    ("j-pop", "j-pop"),
)

_JAPANESE = re.compile(r"[぀-ヿ㐀-鿿]")
_ENTRIES = sorted(
    ((unicodedata.normalize("NFKC", ja).lower(), en) for ja, en in GLOSSARY),
    key=lambda entry: len(entry[0]),
    reverse=True,
)


class MachineTranslator(Protocol):
    def translate(self, text: str) -> str: ...


def glossary_keywords(text: str) -> list[str]:
    """文中に出てくる音楽の言葉を、出てきた順に英語のキーワードにする（重複は除く）。"""
    normalized = unicodedata.normalize("NFKC", text).lower()
    taken = [False] * len(normalized)
    found: list[tuple[int, str]] = []
    for ja, en in _ENTRIES:
        for match in re.finditer(re.escape(ja), normalized):
            span = range(match.start(), match.end())
            if any(taken[i] for i in span):
                continue
            for i in span:
                taken[i] = True
            found.append((match.start(), en))
    return list(dict.fromkeys(en for _, en in sorted(found)))


class QueryTranslator:
    def __init__(self, fallback: MachineTranslator | None = None) -> None:
        self.fallback = fallback

    def to_english(self, text: str) -> str:
        """日本語を含まない文はそのまま返す。"""
        if not _JAPANESE.search(text):
            return text
        if keywords := glossary_keywords(text):
            # 辞書に無い英単語（"lo-fi" 等）が混ざっていれば残す
            words = " ".join(keywords).split()
            words += re.findall(r"[A-Za-z][A-Za-z0-9'&-]*", text)
            words = list(dict.fromkeys(w.lower() for w in words))
            # キーワードを並べるより "a ... song" の形にしたほうがCLAPの精度が高い
            # （herz.evaluate の日本語の例で precision@20 が 35% → 50%）
            return f"a {' '.join(w for w in words if w != 'song')} song"
        if self.fallback is not None:
            return self.fallback.translate(text)
        return text


class NllbTranslator:
    """Meta の NLLB による日本語→英語の機械翻訳（辞書で拾えなかった文の予備）。初回利用時に読み込む。"""

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self._lock = threading.Lock()
        self._model: Any = None
        self._tokenizer: Any = None

    def warm_up(self) -> None:
        self._load()

    def _load(self) -> None:
        with self._lock:
            if self._model is not None:
                return
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

            self._tokenizer = AutoTokenizer.from_pretrained(self.model_name, src_lang="jpn_Jpan")
            self._model = AutoModelForSeq2SeqLM.from_pretrained(self.model_name).eval()

    def translate(self, text: str) -> str:
        self._load()
        assert self._model is not None and self._tokenizer is not None
        with self._lock:
            inputs = self._tokenizer([text], return_tensors="pt")
            output = self._model.generate(
                **inputs,
                forced_bos_token_id=self._tokenizer.convert_tokens_to_ids("eng_Latn"),
                max_new_tokens=60,
                num_beams=4,
            )
            return str(self._tokenizer.decode(output[0], skip_special_tokens=True))
