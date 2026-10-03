#!/usr/bin/env python3
"""
Hikâye & harita aşaması (claude.ai ile, API'siz):
  - PRİNCE altında sıradaki vidN klasörünü oluşturur
  - şablonlardan (sablonlar/*.md) Claude'a verilecek mesajları hazırlar
  - HeyGen'den indirilen avatar videosunu vidN/avatar.mp4 olarak alır ve süresini ölçer
  - Claude'un yazdığı haritayı kaydeder ve render/Flow'a geçmeden kontrol eder

Şablon yer tutucuları: {KONU} {SCRIPT} {SURE_MMSS} {SURE_SN} {ORNEK_HARITA}
"""
import re
import shutil
import subprocess
import sys
import unicodedata
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))
import flow_tools  # noqa: E402
import parse_timeline  # noqa: E402
from platform_tools import NO_WINDOW, TEXT_KW, ffprobe_bin  # noqa: E402

APP_DIR = SCRIPTS_DIR.parent
TEMPLATES_DIR = APP_DIR / "sablonlar"
PACKAGE_TEMPLATE = TEMPLATES_DIR / "paket_mesaji.md"
MAP_TEMPLATE = TEMPLATES_DIR / "harita_mesaji.md"
PRINCE_DIR = Path.home() / "Desktop" / "PRİNCE"

PACKAGE_FILE = "PAKET.md"
SCRIPT_FILE = "SCRIPT.txt"
MAP_FILE = "TIMELINE_MAP.md"
AVATAR_FILE = "avatar.mp4"


# ------------------------------------------------------------ klasör
def _vid_number(p: Path):
    m = re.fullmatch(r"vid(\d+)", unicodedata.normalize("NFC", p.name).casefold().replace("i̇", "i"))
    return int(m.group(1)) if m else None


def next_vid_dir(base: Path = PRINCE_DIR) -> Path:
    """PRİNCE altındaki en büyük vidN'den sonrakini oluşturur (görseller/ ve videolar/ ile)."""
    base.mkdir(parents=True, exist_ok=True)
    nums = [n for p in base.iterdir() if p.is_dir() and (n := _vid_number(p)) is not None]
    d = base / f"vid{max(nums, default=0) + 1}"
    (d / "görseller").mkdir(parents=True, exist_ok=True)
    (d / "videolar").mkdir(exist_ok=True)
    return d


# ------------------------------------------------------------ avatar
def media_duration(path: Path) -> float:
    r = subprocess.run([ffprobe_bin(), "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=NO_WINDOW, **TEXT_KW)
    return float(r.stdout.strip())


def fmt_mmss(seconds: int) -> str:
    return f"{seconds // 60}:{seconds % 60:02d}"


def import_avatar(vid_dir: Path, src: Path) -> int:
    """Avatar videosunu vidN/avatar.mp4 olarak kopyalar, tam saniye cinsinden süresini döndürür."""
    dest = vid_dir / AVATAR_FILE
    if src.resolve() != dest.resolve():
        shutil.copy2(src, dest)
    return round(media_duration(dest))


def avatar_seconds(vid_dir: Path):
    p = vid_dir / AVATAR_FILE
    return round(media_duration(p)) if p.exists() else None


# ------------------------------------------------------------ mesajlar
def _example_map(vid_dir: Path):
    """Format örneği olarak, bu klasör dışındaki en yeni haritayı kullanır."""
    maps = [m for m in PRINCE_DIR.glob("*/TIMELINE_MAP*.md") if m.parent.resolve() != vid_dir.resolve()]
    return max(maps, key=lambda m: m.stat().st_mtime) if maps else None


def package_message(topic: str) -> str:
    return PACKAGE_TEMPLATE.read_text(encoding="utf-8").replace("{KONU}", topic.strip())


def map_message(vid_dir: Path) -> str:
    script_path = vid_dir / SCRIPT_FILE
    if not script_path.exists():
        raise FileNotFoundError("Önce scripti kaydet (③).")
    secs = avatar_seconds(vid_dir)
    if secs is None:
        raise FileNotFoundError("Önce HeyGen avatar videosunu seç (④).")
    ex = _example_map(vid_dir)
    example = ex.read_text(encoding="utf-8") if ex else "(örnek harita bulunamadı)"
    return (MAP_TEMPLATE.read_text(encoding="utf-8")
            .replace("{SCRIPT}", script_path.read_text(encoding="utf-8").strip())
            .replace("{SURE_MMSS}", fmt_mmss(secs))
            .replace("{SURE_SN}", str(secs))
            .replace("{ORNEK_HARITA}", example))


def save_text(vid_dir: Path, name: str, text: str) -> Path:
    p = vid_dir / name
    p.write_text(text.strip() + "\n", encoding="utf-8")
    return p


# ------------------------------------------------------------ harita kontrolü
def validate_map(map_path: Path, expected_seconds=None):
    """(özet, sorunlar) döndürür. Sorun listesi boşsa harita Flow'a ve render'a hazırdır."""
    problems = []
    try:
        edl = parse_timeline.build_edl(map_path)
    except Exception as e:
        return None, [f"Zaman tablosu okunamadı: {e}"]

    s = edl["summary"]
    total = edl["total_duration_seconds"]
    if expected_seconds is not None and abs(total - expected_seconds) > 1:
        problems.append(f"Haritanın toplam süresi {fmt_mmss(total)} ({total} sn), avatar ise "
                        f"{fmt_mmss(expected_seconds)} ({expected_seconds} sn). Fark: {total - expected_seconds:+d} sn.")

    # Tablodaki görsel numaraları 1..N kesintisiz olmalı
    nums = [img["index"] for e in edl["entries"] if e["type"] == "image_block" for img in e["images"]]
    if nums != list(range(1, len(nums) + 1)):
        problems.append("Tablodaki görsel numaraları 1'den başlayıp kesintisiz artmıyor.")

    md = map_path.read_text(encoding="utf-8")
    # Bölüm 3: her görselin promptu olmalı
    try:
        sec3 = flow_tools._section(md, 3)
        prompt_nums = {int(n) for n in re.findall(r"^\s*-\s*#(\d+)\s*:", sec3, flags=re.M)}
        missing = sorted(set(range(1, s["total_images"] + 1)) - prompt_nums)
        if missing:
            problems.append(f"Görsel promptu eksik: #{', #'.join(map(str, missing[:15]))}"
                            + (" …" if len(missing) > 15 else ""))
    except ValueError as e:
        problems.append(str(e))
    # Bölüm 2: tablodaki her V için prompt olmalı
    try:
        sec2 = flow_tools._section(md, 2)
        v_defined = {f"V{n}" for n in re.findall(r"^\*\*V(\d+)\b", sec2, flags=re.M)}
        v_missing = [v for v in s["video_ids"] if v not in v_defined]
        if v_missing:
            problems.append(f"Video promptu eksik: {', '.join(v_missing)}")
    except ValueError as e:
        problems.append(str(e))

    summary = (f"{fmt_mmss(total)} ({total} sn) • {s['total_images']} görsel • "
               f"{s['video_segments']} video • {s['avatar_segments']} avatar bloğu")
    return summary, problems


if __name__ == "__main__":
    # Hızlı kontrol: python3 story_tools.py <harita.md> [beklenen_saniye]
    path = Path(sys.argv[1])
    exp = int(sys.argv[2]) if len(sys.argv) > 2 else None
    summ, probs = validate_map(path, exp)
    print(summ)
    for p in probs:
        print("❌", p)
    if not probs:
        print("✅ Harita hazır.")
