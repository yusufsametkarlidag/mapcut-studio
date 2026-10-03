#!/usr/bin/env python3
"""
Google Flow ile gorsel/video uretim akisi icin yardimcilar:
  - TIMELINE_MAP.md'den Flow ajanina verilecek mesajlari hazirlar
    (gorsel promptlari = "## 3." bolumu, video promptlari = "## 2." bolumu)
  - Flow'dan indirilen zip/dosyalari kaynak klasorune (gorseller/ veya videolar/)
    dogru adlarla aktarir; videolarin sesini kaldirir
  - flow_oto_devam.js betigini gorsel/video ayarlariyla hazirlar

Komut satiri:
  python3 flow_tools.py mesaj gorsel  <vid_klasoru>
  python3 flow_tools.py mesaj video   <vid_klasoru>
  python3 flow_tools.py al gorsel <vid_klasoru> [zip_veya_dosya ...]
  python3 flow_tools.py al video  <vid_klasoru> [zip_veya_dosya ...]
"""
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unicodedata
import zipfile
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))
import check_assets  # noqa: E402
import parse_timeline  # noqa: E402
from platform_tools import NO_WINDOW, TEXT_KW, ffmpeg_bin  # noqa: E402

APP_DIR = SCRIPTS_DIR.parent
OTO_DEVAM_JS = APP_DIR / "flow" / "flow_oto_devam.js"
DOWNLOADS = Path.home() / "Downloads"

IMAGE_EXTS = check_assets.IMAGE_EXTS
VIDEO_EXTS = check_assets.VIDEO_EXTS

# Kullanicinin her videoda Flow ajanina verdigi baslangic mesaji (gorseller)
IMAGE_INTRO = (
    "Şimdi sana aşağıda vermiş olduğum görsel promptlarını, sana vermiş olduğum partlar eşliğinde "
    "part part oluşturmanı istiyorum. İlk partı oluştur, sonra benden onay al, devam et. "
    "Mesela ilk part: {ilk_part}. Bu şekilde sana verdiğim sıra ile devam et. "
    "Her parta geçerken benden onay almak zorundasın. "
    "Her görselin adı mutlaka \"Görsel #numara\" olacak (Görsel #1, Görsel #2, Görsel #3…); "
    "açıklayıcı başka bir ad verme. Görseller tamamen doğal olacak, asla yapaylık olmayacak."
)

VIDEO_INTRO = (
    "Aşağıda video promptları var (V1, V2, V3…). Hepsini sırayla doğrudan video olarak oluştur; "
    "önce görsel üretip sonra videolaştırma yapma. Bir promptta hem \"kaynak görsel\" hem \"hareket talimatı\" "
    "varsa ikisini birleştirip tek bir video promptu olarak kullan.\n"
    "Kurallar: Hiçbir videoda ses olmayacak (müzik, ses efekti, konuşma yok; tamamen sessiz). "
    "Her video 5 saniye ve 16:9 olacak. Videoların adı numarasıyla başlayacak: "
    "\"Vid1 — <başlık>\", \"Vid2 — <başlık>\"… (başlık, promptun başındaki V başlığı). "
    "Görüntüler tamamen doğal olacak, asla yapaylık olmayacak. Hepsini bitirince onayımı bekle."
)

OTO_CFG = {
    "gorsel": {
        "adKontrol": "^Görsel #\\d+",
        "devamMesaji": "Onaylıyorum, sıradaki partı oluştur. Her görselin adı Görsel #numara olsun. "
                       "Partı bitirince yine onayımı bekle.",
        "tekrarMesaji": "Bu partta başarısız olan görsel(ler) var. Başarısız olanları aynı numara ve aynı adla "
                        "(Görsel #numara) yeniden üret, sonra onayımı bekle.",
    },
    "video": {
        "devamMesaji": "Onaylıyorum, sıradaki adıma geç. Hiçbir videoda ses olmasın. Video adları "
                       "Vid<numara> — <başlık> şeklinde olsun. Bu adımı bitirince yine onayımı bekle.",
        "tekrarMesaji": "Bu adımda başarısız olan görsel/video var. Başarısız olanları aynı adla yeniden oluştur "
                        "(videolar sessiz, adları Vid<numara> — <başlık>), sonra onayımı bekle.",
    },
}


# ------------------------------------------------------------ klasor / harita
def find_map(vid_dir: Path) -> Path:
    maps = sorted(vid_dir.glob("TIMELINE_MAP*.md"))
    if not maps:
        raise FileNotFoundError(f"{vid_dir} içinde TIMELINE_MAP*.md bulunamadı.")
    return maps[0]


def _find_subdir(vid_dir: Path, names) -> Path:
    """'görseller' / 'GÖRSELLER' gibi farkli yazimlari bulur, yoksa ilkini olusturur."""
    wanted = {unicodedata.normalize("NFC", n).casefold() for n in names}
    for p in vid_dir.iterdir():
        if p.is_dir() and unicodedata.normalize("NFC", p.name).casefold() in wanted:
            return p
    d = vid_dir / names[0]
    d.mkdir(parents=True, exist_ok=True)
    return d


def images_dir(vid_dir: Path) -> Path:
    return _find_subdir(vid_dir, ["görseller", "GÖRSELLER", "gorseller"])


def videos_dir(vid_dir: Path) -> Path:
    return _find_subdir(vid_dir, ["videolar", "VİDEOLAR", "VIDEOLAR"])


def _section(md: str, num: int) -> str:
    """'## <num>.' basligindan bir sonraki '## ' basligina kadar olan bolum."""
    m = re.search(rf"^## {num}\..*?(?=^## \d+\.|\Z)", md, flags=re.M | re.S)
    if not m:
        raise ValueError(f"Haritada '## {num}.' bölümü bulunamadı.")
    return m.group(0).rstrip() + "\n"


# ------------------------------------------------------------ mesajlar
def image_message(vid_dir: Path) -> str:
    md = find_map(vid_dir).read_text(encoding="utf-8")
    sec = _section(md, 3)
    first = re.search(r"^### (Görsel #\d+\s*[–-]\s*#\d+.*)$", sec, flags=re.M)
    ilk_part = first.group(1).strip() if first else "ilk part"
    return IMAGE_INTRO.format(ilk_part=ilk_part) + "\n\n" + sec


def video_message(vid_dir: Path) -> str:
    md = find_map(vid_dir).read_text(encoding="utf-8")
    return VIDEO_INTRO + "\n\n" + _section(md, 2)


def oto_devam_script(kind: str, kredi_onayi_otomatik: bool = False) -> str:
    cfg = json.dumps({**OTO_CFG[kind], "krediOnayiOtomatik": kredi_onayi_otomatik}, ensure_ascii=False)
    return f"window.FLOW_OTO_CFG = {cfg};\n" + OTO_DEVAM_JS.read_text(encoding="utf-8")


# ------------------------------------------------------------ indirilenleri alma
def _zip_name(info: zipfile.ZipInfo) -> str:
    name = info.filename
    if not info.flag_bits & 0x800:
        # UTF-8 bayragi olmayan zip girdileri cp437 sanilarak okunur ("Görsel" -> "G+¦rsel")
        try:
            name = name.encode("cp437").decode("utf-8")
        except UnicodeError:
            pass
    return unicodedata.normalize("NFC", Path(name).name)


def recent_downloads(since_seconds=6 * 3600):
    """Son ~6 saatte Indirilenler'e gelen zip ve medya dosyalari (en yeni once)."""
    if not DOWNLOADS.exists():
        return []
    cutoff = time.time() - since_seconds
    exts = {".zip"} | IMAGE_EXTS | VIDEO_EXTS
    files = [p for p in DOWNLOADS.iterdir()
             if p.is_file() and p.suffix.lower() in exts and p.stat().st_mtime >= cutoff
             and not p.name.endswith(".crdownload")]
    return sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)


def _strip_audio(src: Path, dest: Path):
    cmd = [ffmpeg_bin(), "-y", "-nostdin", "-i", str(src), "-map", "0:v", "-c:v", "copy", "-an",
           "-movflags", "+faststart", str(dest)]
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                       creationflags=NO_WINDOW, **TEXT_KW)
    if r.returncode != 0:
        raise RuntimeError(f"Ses kaldırılamadı: {src.name}\n{r.stdout[-800:]}")


def import_downloads(kind: str, vid_dir: Path, sources, log=print):
    """sources: zip ve/veya tekil dosya yollari. Hedef klasore aktarir, sorun listesini dondurur."""
    is_video = kind == "video"
    exts = VIDEO_EXTS if is_video else IMAGE_EXTS
    dest_dir = videos_dir(vid_dir) if is_video else images_dir(vid_dir)
    added, skipped = [], []

    with tempfile.TemporaryDirectory() as tmp:
        staged = []
        # eskiden yeniye: ayni numara birden fazla kaynakta varsa en yenisi kalir
        for src in sorted(map(Path, sources), key=lambda p: p.stat().st_mtime):
            if src.suffix.lower() == ".zip":
                with zipfile.ZipFile(src) as z:
                    for info in z.infolist():
                        if info.is_dir():
                            continue
                        name = _zip_name(info)
                        out = Path(tmp) / f"{len(staged):04d}" / name
                        out.parent.mkdir(parents=True)
                        out.write_bytes(z.read(info))
                        staged.append(out)
            else:
                staged.append(src)

        for f in staged:
            name = unicodedata.normalize("NFC", f.name)
            if f.suffix.lower() not in exts:
                skipped.append(name)   # ör. video projesindeki "V1 kaynak" gorselleri
                continue
            if check_assets.file_number(Path(name)) is None:
                skipped.append(name)
                continue
            # Ayni numaranin eski kopyasi (baska zaman damgasiyla) varsa yenisiyle degistir
            num = check_assets.file_number(Path(name))
            for old in check_assets.list_media(dest_dir, exts):
                if check_assets.file_number(old) == num and old.name != name:
                    old.unlink()
            dest = dest_dir / name
            if is_video:
                _strip_audio(f, dest)
            else:
                shutil.copy2(f, dest)
            added.append(name)

    log(f"{len(added)} dosya → {dest_dir}" + (" (sesleri kaldırıldı)" if is_video and added else ""))
    if skipped:
        log(f"Atlanan {len(skipped)} dosya (tür/numara uymuyor): " + ", ".join(skipped[:6])
            + (" …" if len(skipped) > 6 else ""))

    summary = parse_timeline.build_edl(find_map(vid_dir))["summary"]
    expected = summary["video_segments" if is_video else "total_images"]
    files = check_assets.list_media(dest_dir, exts)
    problems = check_assets.check_numbering(files, expected)
    if problems:
        for p in problems:
            log(f"❌ {p}")
    else:
        log(f"✅ {len(files)}/{expected} {'video' if is_video else 'görsel'} tamam, hepsi numaralı, eksik/çift yok.")
    return dest_dir, problems


def main():
    if len(sys.argv) < 4 or sys.argv[1] not in ("mesaj", "al") or sys.argv[2] not in ("gorsel", "video"):
        print(__doc__)
        sys.exit(2)
    action, kind, vid_dir = sys.argv[1], sys.argv[2], Path(sys.argv[3])
    if action == "mesaj":
        print(image_message(vid_dir) if kind == "gorsel" else video_message(vid_dir))
        return
    sources = sys.argv[4:] or [str(p) for p in recent_downloads()]
    if not sources:
        print("İndirilenler'de yeni zip/dosya yok.")
        sys.exit(1)
    _, problems = import_downloads(kind, vid_dir, sources)
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
