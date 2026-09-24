#!/usr/bin/env python3
"""
Otomatik altyazi uretimi: ses -> whisper.cpp (kelime zaman damgali JSON)
-> kelime gruplari -> karaoke stilinde .ass altyazi dosyasi.

Kelime kelime vurgulu (CapCut/TikTok tarzi) altyazi: metin beyaz + kalin
siyah kontur, o an konusulan kelime sariya doner.

whisper.cpp (whisper-cli) ve ggml model dosyasi ffmpeg-full kurulumuyla
birlikte /opt/homebrew/opt/whisper-cpp altina kuruludur.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

WHISPER_BIN = Path("/opt/homebrew/opt/whisper-cpp/bin/whisper-cli")
MODEL_DIR = Path("/opt/homebrew/opt/whisper-cpp/share/whisper-cpp/models")
MODEL_URLS = {
    "tiny.en": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-tiny.en.bin",
    "base.en": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.en.bin",
    "small.en": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.en.bin",
    "medium.en": "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-medium.en.bin",
}

# Karaoke stili: beyaz metin, aktif kelime sari, kalin siyah kontur
FONT_NAME = "Arial Black"
FONT_SIZE = 78
COLOR_WHITE = "&H00FFFFFF"
COLOR_YELLOW = "&H0000FFFF"  # ASS format: &HAABBGGRR (BGR sirali)
COLOR_BLACK = "&H00000000"
MAX_WORDS_PER_CHUNK = 4
MAX_CHARS_PER_CHUNK = 26
PAUSE_BREAK_MS = 600  # bu kadar sessizlikten sonra yeni altyazi bloguna gec
WORD_TAIL_MS = 150  # son kelimenin ekranda kalma payi


def ensure_model(model_name: str, log=print) -> Path:
    model_path = MODEL_DIR / f"ggml-{model_name}.bin"
    if model_path.exists():
        return model_path
    if model_name not in MODEL_URLS:
        raise ValueError(f"Bilinmeyen model: {model_name}. Seçenekler: {list(MODEL_URLS)}")
    log(f"  Whisper modeli indiriliyor ({model_name}, ilk kullanımda bir kere)...")
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["curl", "-sL", "-o", str(model_path), MODEL_URLS[model_name]],
        check=True,
    )
    return model_path


def extract_audio_wav(source_video: Path, out_wav: Path, start: float, duration: float, ffmpeg_bin: str):
    cmd = [
        ffmpeg_bin, "-y", "-nostdin",
        "-ss", str(start), "-t", str(duration), "-i", str(source_video),
        "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le",
        str(out_wav),
    ]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True, text=True)


def transcribe_words(wav_path: Path, model_path: Path, language: str, work_dir: Path):
    if not WHISPER_BIN.exists():
        raise RuntimeError(
            f"whisper-cli bulunamadı: {WHISPER_BIN}\n"
            "Kurulum için: brew install ffmpeg-full"
        )
    out_stem = work_dir / "captions_raw"
    cmd = [
        str(WHISPER_BIN),
        "-m", str(model_path),
        "-f", str(wav_path),
        "-l", language,
        "-ml", "1", "-sow",
        "-oj", "-of", str(out_stem),
        "-np",
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"whisper-cli başarısız oldu:\n{result.stdout[-3000:]}")

    json_path = Path(str(out_stem) + ".json")
    data = json.loads(json_path.read_text(encoding="utf-8"))

    words = []
    for seg in data.get("transcription", []):
        text = seg["text"].strip()
        if not text:
            continue
        words.append({
            "text": text,
            "start_ms": seg["offsets"]["from"],
            "end_ms": seg["offsets"]["to"],
        })
    return words


def group_into_chunks(words):
    chunks = []
    current = []
    current_chars = 0
    for i, w in enumerate(words):
        will_add_chars = current_chars + len(w["text"]) + (1 if current else 0)
        gap_too_long = current and (w["start_ms"] - current[-1]["end_ms"] > PAUSE_BREAK_MS)
        too_many_words = len(current) >= MAX_WORDS_PER_CHUNK
        too_many_chars = will_add_chars > MAX_CHARS_PER_CHUNK
        ends_sentence = current and re.search(r"[.!?]\"?$", current[-1]["text"])

        if current and (gap_too_long or too_many_words or too_many_chars or ends_sentence):
            chunks.append(current)
            current = []
            current_chars = 0

        current.append(w)
        current_chars += len(w["text"]) + (1 if len(current) > 1 else 0)

    if current:
        chunks.append(current)
    return chunks


def _ass_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("{", "(").replace("}", ")")


def build_ass(chunks, ass_path: Path, video_w=1920, video_h=1080, margin_v=170):
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {video_w}
PlayResY: {video_h}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Caption,{FONT_NAME},{FONT_SIZE},{COLOR_WHITE},{COLOR_WHITE},{COLOR_BLACK},{COLOR_BLACK},-1,0,0,0,100,100,0,0,1,5,0,2,60,60,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    def ts(ms: float) -> str:
        ms = max(0, int(ms))
        h = ms // 3600000
        m = (ms % 3600000) // 60000
        s = (ms % 60000) // 1000
        cs = (ms % 1000) // 10
        return f"{h:d}:{m:02d}:{s:02d}.{cs:02d}"

    lines = [header]
    for c_idx, chunk in enumerate(chunks):
        for i, active in enumerate(chunk):
            start = active["start_ms"]
            if i + 1 < len(chunk):
                end = chunk[i + 1]["start_ms"]
            else:
                end = active["end_ms"] + WORD_TAIL_MS
                if c_idx + 1 < len(chunks):
                    # bir sonraki bloğun ilk kelimesinden önce bitmeli,
                    # yoksa iki altyazı satırı bir an için üst üste biner
                    end = min(end, chunks[c_idx + 1][0]["start_ms"])
            if end <= start:
                continue

            parts = []
            for j, w in enumerate(chunk):
                word_text = _ass_escape(w["text"])
                if j == i:
                    parts.append(f"{{\\c{COLOR_YELLOW}}}{word_text}{{\\c{COLOR_WHITE}}}")
                else:
                    parts.append(word_text)
            text = " ".join(parts)
            lines.append(f"Dialogue: 0,{ts(start)},{ts(end)},Caption,,0,0,0,,{text}\n")

    ass_path.write_text("".join(lines), encoding="utf-8")


def generate_captions(source_video: Path, start: float, duration: float, work_dir: Path,
                       model_name: str, language: str, ffmpeg_bin: str,
                       video_w=1920, video_h=1080, margin_v=170, log=print) -> Path:
    """Uctan uca: ses cikar -> transkribe et -> .ass altyazi uret. Yolunu dondurur."""
    work_dir.mkdir(parents=True, exist_ok=True)
    model_path = ensure_model(model_name, log=log)

    wav_path = work_dir / "captions_audio.wav"
    log("  Ses çıkarılıyor...")
    extract_audio_wav(source_video, wav_path, start, duration, ffmpeg_bin)

    log(f"  Whisper ile transkript ediliyor ({model_name}, kelime zaman damgalı)...")
    words = transcribe_words(wav_path, model_path, language, work_dir)
    log(f"  {len(words)} kelime tanındı.")

    chunks = group_into_chunks(words)
    ass_path = work_dir / "captions.ass"
    build_ass(chunks, ass_path, video_w=video_w, video_h=video_h, margin_v=margin_v)
    log(f"  Altyazı dosyası hazır: {ass_path} ({len(chunks)} blok)")
    return ass_path


if __name__ == "__main__":
    # hizli manuel test: python3 captions.py video.mp4 [start] [duration]
    src = Path(sys.argv[1])
    start = float(sys.argv[2]) if len(sys.argv) > 2 else 0.0
    duration = float(sys.argv[3]) if len(sys.argv) > 3 else 30.0
    out = generate_captions(src, start, duration, Path("./captions_test_work"),
                             "small.en", "en", "ffmpeg")
    print("ASS:", out)
