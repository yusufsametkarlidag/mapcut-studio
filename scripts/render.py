#!/usr/bin/env python3
"""
edl.json -> output/*.mp4 render pipeline. Herhangi bir proje klasoru icin
calisir (--project-dir), proje klasorunde su alt klasorleri bekler:

  avatar/avatar.mp4
  videolar/V1.mp4 ... V{n}.mp4
  gorseller/gorsel_001.<ext> ... gorsel_{n:03d}.<ext>   (png/jpg/jpeg)
  output/   (render ciktisi buraya yazilir)

3 asama:
  A) Normalize  - her kaynak 1920x1080/30fps/h264(videotoolbox) tekil klip
                   haline getirilir. Crossfade'in "yediği" süreyi telafi
                   etmek icin son klip haric her klibin kuyruguna
                   +crossfade kadar ekstra kare eklenir.
  B) Concat     - klipler xfade filtresiyle zincirlenir (filter_complex_
                   script ile), toplam sure EDL toplamina esitlenir.
  C) Finalize   - (opsiyonel) film grain / vinyet / sahte kamera sallamasi
                   efektleri + avatar.mp4'un TAM ses parcasi mux edilerek
                   VideoToolbox ile son encode yapilir.

Kullanim:
  python3 render.py --project-dir /path/to/proje --test
  python3 render.py --project-dir /path/to/proje
  python3 render.py --project-dir /path/to/proje --no-effects
  python3 render.py --project-dir /path/to/proje --crossfade 0.3
"""
import argparse
import json
import random
import subprocess
import sys
import time
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))
import captions as captions_mod  # noqa: E402

# ffmpeg-full: standart 'ffmpeg' formulunde olmayan libass/freetype/zoompan/
# loudnorm/whisper destegi burada var. Tum pipeline bu ikiliyi kullanir.
FFMPEG_BIN = "/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg"
FFPROBE_BIN = "/opt/homebrew/opt/ffmpeg-full/bin/ffprobe"

WIDTH, HEIGHT, FPS = 1920, 1080, 30
SCALE_CROP_FPS = (
    f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,"
    f"crop={WIDTH}:{HEIGHT},setsar=1,fps={FPS},format=yuv420p"
)
SEG_BITRATE = "12M"
FINAL_BITRATE = "16M"
FINAL_MAXRATE = "20M"
FINAL_BUFSIZE = "30M"

# "Gorunum" stilleri: weave = cok yavas, zar zor hissedilen bir "nefes alma"
# hareketi (eskiden 3-6 Hz gibi hizli bir titremeydi, kullanici "asiri hizli"
# diye sikayet etti - artik 0.05-0.15 Hz, yani bir tam donguyu 7-20 saniyede
# tamamliyor). flicker ve vignette kaldirildi (kullanici "vinyet + isik
# yanip sonme" kombinasyonunu begenmedi) - vignette artik ayri, varsayilan
# KAPALI bir secenek (bkz. build_effects_vf'in vignette parametresi).
STYLE_PRESETS = {
    "modern": dict(weave_amp_x=0, weave_amp_y=0, weave_freqs=[], noise=5),
    "vintage1": dict(weave_amp_x=2, weave_amp_y=3, weave_freqs=[(0.07, 0.9), (0.13, 2.3)], noise=9),
    "vintage2": dict(weave_amp_x=3.5, weave_amp_y=5, weave_freqs=[(0.09, 1.1), (0.15, 2.9)], noise=14),
}
INTENSITY_SCALE = {"light": 0.7, "medium": 1.0, "strong": 1.4}

KENBURNS_MAX_ZOOM = 1.12

# Gecis cesitliligi: cogunlukla "fade" kalsin, ara sira bu paletten hafif bir
# kaydirma/yumusatma gecisi secilsin (jarring olanlar - pixelize, radial,
# circleopen vb. - bilinclerek disarida birakildi).
TRANSITION_PALETTE = ["smoothleft", "smoothright", "smoothup", "smoothdown", "slideleft", "slideright"]
TRANSITION_VARIETY_CHANCE = 0.22

LETTERBOX_HEIGHT_RATIO = 0.085  # ust+alt bant, her biri kare yuksekliginin bu orani
LETTERBOX_CAPTION_MARGIN_V = 260  # letterbox acikken altyazi bandin ustune otursun


def run(cmd, quiet=True):
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE if quiet else None,
        stderr=subprocess.STDOUT if quiet else None,
        text=True,
    )
    if result.returncode != 0:
        print(f"\nHATA: komut başarısız oldu:\n{' '.join(cmd)}\n", file=sys.stderr)
        if quiet and result.stdout:
            print(result.stdout[-4000:], file=sys.stderr)
        sys.exit(1)


def ffprobe_duration(path: Path) -> float:
    cmd = [
        FFPROBE_BIN, "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(path),
    ]
    out = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return float(out.stdout.strip())


def fmt_ts(seconds: float) -> str:
    m = int(seconds) // 60
    s = seconds - m * 60
    return f"{m}:{s:05.2f}"


def load_edl(path: Path):
    if not path.exists():
        print(f"HATA: {path} bulunamadı. Önce parse_timeline.py çalıştırın.", file=sys.stderr)
        sys.exit(1)
    return json.loads(path.read_text(encoding="utf-8"))


def select_entries(edl, until_row=None, until_seconds=None):
    entries = edl["entries"]
    if until_row is not None:
        entries = [e for e in entries if e["row"] <= until_row]
    if until_seconds is not None:
        entries = [e for e in entries if e["start"] < until_seconds]
    if not entries:
        print("HATA: seçilen aralıkta hiç satır yok.", file=sys.stderr)
        sys.exit(1)
    return entries


def find_image_file(image_dir: Path, index: int) -> Path:
    matches = sorted(image_dir.glob(f"gorsel_{index:03d}.*"))
    if not matches:
        return image_dir / f"gorsel_{index:03d}.png"  # yoksa hata check_assets_exist'te yakalanir
    return matches[0]


def flatten_clips(entries, project_dir: Path):
    video_dir = project_dir / "videolar"
    image_dir = project_dir / "gorseller"
    clips = []
    for e in entries:
        if e["type"] == "avatar":
            clips.append({
                "kind": "avatar",
                "label": e["clip_id"],
                "duration": e["duration"],
                "source_in": e["source_in"],
                "source_out": e["source_out"],
            })
        elif e["type"] == "video":
            clips.append({
                "kind": "video",
                "label": e["clip_id"],
                "duration": e["duration"],
                "path": video_dir / f"{e['clip_id']}.mp4",
            })
        elif e["type"] == "image_block":
            for img in e["images"]:
                clips.append({
                    "kind": "image",
                    "label": f"gorsel_{img['index']:03d}",
                    "duration": img["duration"],
                    "path": find_image_file(image_dir, img["index"]),
                })
    return clips


def find_missing_assets(clips, project_dir: Path):
    """Eksik kaynak dosyalari (kind, path) ciftleri olarak dondurur (sys.exit etmez)."""
    missing = []
    avatar_path = project_dir / "avatar" / "avatar.mp4"
    if any(c["kind"] == "avatar" for c in clips) and not avatar_path.exists():
        missing.append(("avatar", str(avatar_path)))
    for c in clips:
        if c["kind"] in ("video", "image") and not c["path"].exists():
            missing.append((c["kind"], str(c["path"])))
    return missing


def check_assets_exist(clips, project_dir: Path):
    missing = find_missing_assets(clips, project_dir)
    if missing:
        print("HATA: aşağıdaki kaynak dosyalar eksik:", file=sys.stderr)
        for _, m in missing[:20]:
            print(f"  - {m}", file=sys.stderr)
        if len(missing) > 20:
            print(f"  ... ve {len(missing) - 20} dosya daha", file=sys.stderr)
        sys.exit(1)


def _kenburns_vf(duration: float, variant: int) -> str:
    # Hafif "zoomlanmis + kayan" Ken Burns hissi, performansli sekilde.
    # zoompan ile gercek/surekli zoom denendi: 5.5sn'lik tek goruntu icin
    # ~80 saniye surdu (214 goruntu = ~4.7 saat, kullanilamaz - zoompan'in
    # bilinen bir performans sorunu). Bunun yerine goruntu bir kez sabit
    # oranda buyutulup, SABIT boyutlu bir crop penceresi bu buyutulmus
    # tuval uzerinde kayiyor (x/y degisiyor, w/h sabit) - per-frame yeniden
    # orneklemeyi gerektirmedigi icin ~100 kat daha hizli (klip basina <1sn).
    sw = int(round(WIDTH * KENBURNS_MAX_ZOOM / 2) * 2)
    sh = int(round(HEIGHT * KENBURNS_MAX_ZOOM / 2) * 2)
    ew = sw - WIDTH
    eh = sh - HEIGHT
    tn = f"(t/{max(duration, 0.01):.4f})"

    v = variant % 5
    if v == 0:  # sol -> sag kayma
        x, y = f"{ew}*{tn}", f"{eh}/2"
    elif v == 1:  # sag -> sol kayma
        x, y = f"{ew}-{ew}*{tn}", f"{eh}/2"
    elif v == 2:  # yukari -> asagi kayma
        x, y = f"{ew}/2", f"{eh}*{tn}"
    elif v == 3:  # asagi -> yukari kayma
        x, y = f"{ew}/2", f"{eh}-{eh}*{tn}"
    else:  # sakin: cok hafif organik surukleme
        x, y = f"{ew}/2+6*sin(2*PI*{tn})", f"{eh}/2+4*cos(2*PI*{tn})"

    return f"scale={sw}:{sh},crop={WIDTH}:{HEIGHT}:x='{x}':y='{y}',fps={FPS},format=yuv420p"


def stage_a_normalize(clips, crossfade, work_dir: Path, avatar_path: Path,
                       kenburns=True, progress_cb=None):
    work_dir.mkdir(parents=True, exist_ok=True)
    n = len(clips)
    seg_paths = []
    image_counter = 0
    avatar_total_dur = None
    if any(c["kind"] == "avatar" for c in clips):
        avatar_total_dur = ffprobe_duration(avatar_path)

    for i, clip in enumerate(clips):
        idx = i + 1
        is_last = (i == n - 1)
        ext = 0.0 if is_last else crossfade
        out_path = work_dir / f"seg_{idx:04d}.mp4"
        seg_paths.append((out_path, clip["duration"] + ext, i, i))

        msg = f"[{idx}/{n}] {clip['kind']:6s} {clip['label']:22s} ({clip['duration']:.2f}s)"
        print(f"  {msg} render ediliyor...", end="", flush=True)
        if progress_cb:
            progress_cb(idx, n, clip)
        t0 = time.time()

        if clip["kind"] == "avatar":
            wanted_out = clip["source_out"] + ext
            to_point = min(wanted_out, avatar_total_dur)
            pad_dur = wanted_out - to_point
            if pad_dur > 0.001:
                print(f"\n  ⚠️  avatar {clip['label']}: avatar.mp4 {avatar_total_dur:.2f}s'de "
                      f"bitiyor, {pad_dur:.2f}s son kare donarak tamamlanıyor.")
            vf = SCALE_CROP_FPS
            if pad_dur > 0.001:
                vf += f",tpad=stop_mode=clone:stop_duration={pad_dur}"
            cmd = [
                FFMPEG_BIN, "-y", "-nostdin",
                "-ss", str(clip["source_in"]),
                "-to", str(to_point),
                "-i", str(avatar_path),
                "-an", "-vf", vf,
                "-c:v", "h264_videotoolbox", "-b:v", SEG_BITRATE,
                str(out_path),
            ]
        elif clip["kind"] == "video":
            # Kaynak video, gereken sureden (clip suresi + xfade payi) kisa
            # olabilir (ör. 5sn gereken yerde 4sn'lik B-roll). Bu durumda
            # -t ile kirpma sessizce daha kisa bir segment uretir; bu da
            # Aşama B'deki xfade offset hesaplarini bozup TUM sonraki
            # goruntunun kaybolmasina yol acar (ses ayri kaynaktan geldigi
            # icin fark edilmez). Kaynagi olcup, eksik kalan kismi son
            # karayi dondurerek (tpad) tamamliyoruz - segment SUre
            # garantisi boylece asla bozulmuyor.
            src_dur = ffprobe_duration(clip["path"])
            trim_dur = min(clip["duration"], src_dur)
            pad_dur = (clip["duration"] + ext) - trim_dur
            if src_dur < clip["duration"]:
                print(f"\n  ⚠️  {clip['label']}: kaynak {src_dur:.2f}s, gereken "
                      f"{clip['duration']:.2f}s — {clip['duration'] - src_dur:.2f}s son kare "
                      f"donarak tamamlanıyor.")
            vf = SCALE_CROP_FPS
            if pad_dur > 0.001:
                vf += f",tpad=stop_mode=clone:stop_duration={pad_dur}"
            cmd = [
                FFMPEG_BIN, "-y", "-nostdin",
                # -t burada GIRIS secenegi olarak -i'den once duruyor (kaynagi
                # trim_dur ile sinirlar). -i'den SONRA olsaydi CIKIS secenegi
                # olurdu ve tpad'in eklecegi ekstra kareleri sessizce keserdi
                # (asil bug buydu - segment hep clip["duration"] ile sinirli
                # kaliyor, xfade payi hicbir zaman gercekten eklenmiyordu).
                "-t", str(trim_dur), "-i", str(clip["path"]),
                "-an", "-vf", vf,
                "-c:v", "h264_videotoolbox", "-b:v", SEG_BITRATE,
                str(out_path),
            ]
        elif clip["kind"] == "image":
            total_dur = clip["duration"] + ext
            if kenburns:
                vf = _kenburns_vf(total_dur, image_counter)
            else:
                vf = SCALE_CROP_FPS
            image_counter += 1
            cmd = [
                FFMPEG_BIN, "-y", "-nostdin",
                "-loop", "1", "-t", str(total_dur),
                "-i", str(clip["path"]),
                "-an", "-vf", vf,
                "-c:v", "h264_videotoolbox", "-b:v", SEG_BITRATE,
                str(out_path),
            ]
        else:
            raise ValueError(clip["kind"])

        run(cmd)
        print(f" tamam ({time.time() - t0:.1f}s)")

    return seg_paths


XFADE_BATCH_SIZE = 8  # tek ffmpeg cagrisinda ayni anda acilacak max dosya sayisi


def build_transition_types(n_clips: int, variety: bool, seed: int = 0):
    """N-1 gecis turu (her orijinal klip siniri icin bir tane) uretir.
    variety=False ise hepsi 'fade'. variety=True ise cogunlukla 'fade',
    ~%22 ihtimalle TRANSITION_PALETTE'ten hafif bir gecis secilir."""
    n_boundaries = max(0, n_clips - 1)
    if not variety:
        return ["fade"] * n_boundaries
    rng = random.Random(seed)
    return [
        rng.choice(TRANSITION_PALETTE) if rng.random() < TRANSITION_VARIETY_CHANCE else "fade"
        for _ in range(n_boundaries)
    ]


def _merge_batch(batch, crossfade, work_dir: Path, name: str, transition_types):
    """batch: [(path, duration, start_idx, end_idx), ...]. Tek ffmpeg cagrisiyla
    xfade zinciriyle birlestirir (en fazla XFADE_BATCH_SIZE dosya, fd limiti
    sorunu olmaz). transition_types: orijinal klip siniri -> gecis turu
    (bakınız build_transition_types); her item bir veya daha fazla orijinal
    klibi temsil edebilir (onceki turlarda birlesmis olabilir)."""
    n = len(batch)
    if n == 1:
        return batch[0]

    out_path = work_dir / f"{name}.mp4"
    inputs = []
    for p, _, _, _ in batch:
        inputs += ["-i", str(p)]

    filter_lines = []
    cumulative = batch[0][1]
    prev_label = "0:v"
    for i in range(1, n):
        _, dur_i, start_i, _ = batch[i]
        boundary = start_i - 1  # bu klibin hemen oncesindeki orijinal sinir
        transition = transition_types[boundary]
        offset = cumulative - crossfade
        out_label = f"xf{i}" if i < n - 1 else "vout"
        filter_lines.append(
            f"[{prev_label}][{i}:v]xfade=transition={transition}:duration={crossfade}:"
            f"offset={offset:.6f}[{out_label}]"
        )
        cumulative = cumulative + dur_i - crossfade
        prev_label = out_label

    cmd = [
        FFMPEG_BIN, "-y", "-nostdin",
        *inputs,
        "-filter_complex", ";".join(filter_lines),
        "-map", "[vout]",
        "-c:v", "h264_videotoolbox", "-b:v", SEG_BITRATE,
        str(out_path),
    ]
    run(cmd)
    return out_path, cumulative, batch[0][2], batch[-1][3]


def stage_b_concat_xfade(seg_paths, crossfade, work_dir: Path, transition_types):
    """Klipleri xfade ile birlestirir. Buyuk projelerde (200+ klip) tek bir
    ffmpeg cagrisinda hepsini ayni anda acmak, macOS'un varsayilan process
    basi dosya tanimlayici limitini (genelde 256) asip ffmpeg'in kilitlenmesine
    (0% CPU, ilerlemesiz donma) yol aciyordu. Bunun yerine kucuk gruplar
    halinde (XFADE_BATCH_SIZE) birlestirilip, tek parca kalana kadar
    kademeli olarak (agac seklinde) tekrar birlestiriliyor - hicbir ffmpeg
    cagrisi XFADE_BATCH_SIZE'dan fazla dosya acmiyor. Toplam crossfade
    sayisi (N-1) ve dolayisiyla toplam sure matematigi, tek zincirle
    birebir ayni sonucu verir (dogrulandi). Her orijinal klip siniri,
    hangi turda/grupta birlesirse birlessin, dogru gecis turunu (start_idx/
    end_idx takibiyle) korur."""
    current = list(seg_paths)
    round_num = 0
    while len(current) > 1:
        round_num += 1
        batches = [current[i:i + XFADE_BATCH_SIZE] for i in range(0, len(current), XFADE_BATCH_SIZE)]
        print(f"  Tur {round_num}: {len(current)} parça → {len(batches)} gruba birleştiriliyor "
              f"(grup başına en fazla {XFADE_BATCH_SIZE} dosya)...")
        t0 = time.time()
        next_round = []
        for bi, batch in enumerate(batches, start=1):
            next_round.append(_merge_batch(batch, crossfade, work_dir,
                                            f"merge_r{round_num}_{bi:03d}", transition_types))
        current = next_round
        print(f"  Tur {round_num} tamam ({time.time() - t0:.1f}s, {len(current)} parça kaldı)")

    final_path, final_duration, _, _ = current[0]
    return final_path, final_duration


def _weave_expr(amp: float, freqs) -> str:
    if amp <= 0 or not freqs:
        return "0"
    n = len(freqs)
    first_w = 0.6 if n > 1 else 1.0
    rest_w = (1.0 - first_w) / (n - 1) if n > 1 else 0.0
    terms = []
    for i, (hz, phase) in enumerate(freqs):
        w = first_w if i == 0 else rest_w
        terms.append(f"{amp * w:.3f}*sin(2*PI*t*{hz}+{phase})")
    return "(" + "+".join(terms) + ")"


def _escape_filter_path(path: str) -> str:
    return path.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")


def build_effects_vf(style: str, intensity: str, warmgrade: bool, vignette: bool) -> str:
    preset = STYLE_PRESETS[style]
    scale = INTENSITY_SCALE[intensity]
    amp_x = preset["weave_amp_x"] * scale
    amp_y = preset["weave_amp_y"] * scale

    filters = []
    if amp_x > 0 or amp_y > 0:
        pad = int(2 * max(amp_x, amp_y) + 10)
        pad += pad % 2
        x_expr = _weave_expr(amp_x, preset["weave_freqs"])
        y_freqs = [(hz * 0.83, ph + 1.7) for hz, ph in preset["weave_freqs"]]
        y_expr = _weave_expr(amp_y, y_freqs)
        filters.append(f"scale={WIDTH + pad}:{HEIGHT + pad}")
        filters.append(f"crop={WIDTH}:{HEIGHT}:x='{pad/2}+{x_expr}':y='{pad/2}+{y_expr}'")

    if warmgrade:
        filters.append("colorbalance=rs=0.07:gs=0.02:bs=-0.09:rm=0.04:bm=-0.05")

    if vignette:
        filters.append("vignette=PI/6")  # cok hafif, sabit (stiller arasi artik farklilasmiyor)

    filters.append(f"noise=alls={preset['noise'] * scale:.1f}:allf=t+u")

    return ",".join(filters)


def stage_c_finalize(concat_path: Path, total_duration: float, effects: bool,
                      style: str, intensity: str, warmgrade: bool, vignette: bool,
                      letterbox: bool, loudnorm: bool, captions_ass: Path,
                      avatar_path: Path, out_path: Path):
    vf = build_effects_vf(style, intensity, warmgrade, vignette) if effects else "null"
    if letterbox:
        r = LETTERBOX_HEIGHT_RATIO
        vf += (f",drawbox=x=0:y=0:w=iw:h=ih*{r}:color=black:t=fill"
               f",drawbox=x=0:y=ih-ih*{r}:w=iw:h=ih*{r}:color=black:t=fill")
    if captions_ass is not None:
        esc = _escape_filter_path(str(captions_ass))
        vf += f",subtitles=filename='{esc}'"

    af = "anull"
    if loudnorm:
        af = "loudnorm=I=-14:TP=-1.5:LRA=11"

    print(f"  Görünüm: {style if effects else 'kapalı'} ({intensity})"
          f"{' + sıcak ton' if (effects and warmgrade) else ''}"
          f"{' + vinyet' if (effects and vignette) else ''}"
          f"{' + letterbox' if letterbox else ''}"
          f"{' + altyazı' if captions_ass else ''}"
          f"{' + loudnorm' if loudnorm else ''}, "
          f"ses: avatar.mp4 0:00→{fmt_ts(total_duration)}")
    t0 = time.time()
    cmd = [
        FFMPEG_BIN, "-y", "-nostdin",
        "-i", str(concat_path),
        "-ss", "0", "-t", str(total_duration), "-i", str(avatar_path),
        "-filter_complex", f"[0:v]{vf}[v];[1:a]{af}[a]",
        "-map", "[v]", "-map", "[a]",
        "-c:v", "h264_videotoolbox", "-b:v", FINAL_BITRATE,
        "-maxrate", FINAL_MAXRATE, "-bufsize", FINAL_BUFSIZE,
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        str(out_path),
    ]
    run(cmd)
    print(f"  tamam ({time.time() - t0:.1f}s)")


def render(project_dir: Path, edl_path: Path = None, until_row=None, until_seconds=None,
           crossfade=0.5, effects=True, style="modern", effect_intensity="light",
           warmgrade=True, vignette=False, kenburns=True, loudnorm=True,
           transition_variety=True, letterbox=False,
           captions=False, caption_model="small.en", caption_lang="en",
           out_name=None, work_dir: Path = None, keep_work=False, progress_cb=None):
    """Programatik giris noktasi (GUI bunu dogrudan cagirir)."""
    edl_path = edl_path or (project_dir / "edl.json")
    edl = load_edl(edl_path)

    entries = select_entries(edl, until_row=until_row, until_seconds=until_seconds)
    target_duration = entries[-1]["end"]
    clips = flatten_clips(entries, project_dir)

    print(f"Render planı: {len(entries)} EDL satırı, {len(clips)} klip, "
          f"hedef süre {fmt_ts(target_duration)} ({target_duration:.2f}s)")
    check_assets_exist(clips, project_dir)

    avatar_path = project_dir / "avatar" / "avatar.mp4"
    work_dir = work_dir or (project_dir / "work")
    output_dir = project_dir / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    print("\n[Aşama A] Kaynaklar normalize ediliyor (1920x1080/30fps/h264 videotoolbox)...")
    seg_paths = stage_a_normalize(clips, crossfade, work_dir, avatar_path,
                                   kenburns=kenburns, progress_cb=progress_cb)

    transition_types = build_transition_types(len(clips), transition_variety)

    print("\n[Aşama B] Crossfade ile birleştiriliyor...")
    concat_path, _ = stage_b_concat_xfade(seg_paths, crossfade, work_dir, transition_types)

    captions_ass = None
    if captions:
        print("\n[Aşama C-ön] Otomatik altyazı oluşturuluyor (Whisper)...")
        margin_v = LETTERBOX_CAPTION_MARGIN_V if letterbox else 170
        captions_ass = captions_mod.generate_captions(
            avatar_path, 0.0, target_duration, work_dir,
            caption_model, caption_lang, FFMPEG_BIN,
            video_w=WIDTH, video_h=HEIGHT, margin_v=margin_v, log=print,
        )

    out_name = out_name or (f"render_{'test' if until_row or until_seconds else 'full'}.mp4")
    out_path = output_dir / out_name

    print("\n[Aşama C] Efekt + ses mux + final encode...")
    stage_c_finalize(concat_path, target_duration, effects, style, effect_intensity,
                      warmgrade, vignette, letterbox, loudnorm, captions_ass, avatar_path, out_path)

    actual = ffprobe_duration(out_path)
    diff = actual - target_duration
    status_ok = abs(diff) < 0.15

    print("\n" + "=" * 60)
    print("RENDER RAPORU")
    print("=" * 60)
    print(f"Çıktı dosyası     : {out_path}")
    print(f"Hedef süre        : {target_duration:.3f}s ({fmt_ts(target_duration)})")
    print(f"Gerçek süre       : {actual:.3f}s ({fmt_ts(actual)})")
    print(f"Fark              : {diff:+.3f}s [{'OK ✅' if status_ok else 'SAPMA VAR ⚠️'}]")
    print(f"Klip sayısı       : {len(clips)}")
    print(f"Crossfade süresi  : {crossfade}s")
    print(f"Görünüm           : {(style + ' (' + effect_intensity + ')') if effects else 'kapalı'}")
    print(f"Ken Burns         : {'açık' if kenburns else 'kapalı'}")
    print(f"Ses normalizasyonu: {'açık' if loudnorm else 'kapalı'}")
    print(f"Altyazı           : {'açık (' + caption_model + ')' if captions else 'kapalı'}")
    print("=" * 60)

    if not keep_work:
        import shutil
        shutil.rmtree(work_dir, ignore_errors=True)
        print(f"Ara dosyalar silindi ({work_dir}).")

    return {
        "out_path": out_path,
        "target_duration": target_duration,
        "actual_duration": actual,
        "diff": diff,
        "ok": status_ok,
        "clip_count": len(clips),
    }


def main():
    ap = argparse.ArgumentParser(description="EDL -> final video render pipeline")
    ap.add_argument("--project-dir", required=True)
    ap.add_argument("--edl", default=None)
    ap.add_argument("--test", action="store_true",
                     help="Sadece ilk --test-seconds kadarını render et (varsayılan 150s). "
                          "Satır sayısına değil, süreye dayanır; bu yüzden her TIMELINE_MAP.md "
                          "yapısında (avatar/video/görsel sırası ne olursa olsun) çalışır.")
    ap.add_argument("--test-seconds", type=float, default=150.0,
                     help="--test ile birlikte kullanılan test uzunluğu (sn), varsayılan 150")
    ap.add_argument("--until-row", type=int, default=None)
    ap.add_argument("--until-seconds", type=float, default=None)
    ap.add_argument("--crossfade", type=float, default=0.5)
    ap.add_argument("--effects", dest="effects", action="store_true", default=True)
    ap.add_argument("--no-effects", dest="effects", action="store_false")
    ap.add_argument("--style", choices=["modern", "vintage1", "vintage2"], default="modern")
    ap.add_argument("--effect-intensity", choices=["light", "medium", "strong"], default="light")
    ap.add_argument("--warmgrade", dest="warmgrade", action="store_true", default=True)
    ap.add_argument("--no-warmgrade", dest="warmgrade", action="store_false")
    ap.add_argument("--vignette", dest="vignette", action="store_true", default=False)
    ap.add_argument("--no-vignette", dest="vignette", action="store_false")
    ap.add_argument("--kenburns", dest="kenburns", action="store_true", default=True)
    ap.add_argument("--no-kenburns", dest="kenburns", action="store_false")
    ap.add_argument("--loudnorm", dest="loudnorm", action="store_true", default=True)
    ap.add_argument("--no-loudnorm", dest="loudnorm", action="store_false")
    ap.add_argument("--transition-variety", dest="transition_variety", action="store_true", default=True,
                     help="Çoğunlukla fade, ara sıra hafif kaydırma/yumuşatma geçişi (varsayılan açık)")
    ap.add_argument("--no-transition-variety", dest="transition_variety", action="store_false")
    ap.add_argument("--letterbox", dest="letterbox", action="store_true", default=False,
                     help="Üst/alt ince siyah bant (sinematik görünüm)")
    ap.add_argument("--no-letterbox", dest="letterbox", action="store_false")
    ap.add_argument("--captions", dest="captions", action="store_true", default=False)
    ap.add_argument("--no-captions", dest="captions", action="store_false")
    ap.add_argument("--caption-model", choices=["tiny.en", "base.en", "small.en", "medium.en"],
                     default="small.en")
    ap.add_argument("--caption-lang", default="en")
    ap.add_argument("--out", default=None)
    ap.add_argument("--work-dir", default=None)
    ap.add_argument("--keep-work", action="store_true")
    args = ap.parse_args()

    project_dir = Path(args.project_dir)
    until_seconds = args.until_seconds
    if args.test and args.until_row is None and until_seconds is None:
        until_seconds = args.test_seconds

    render(
        project_dir=project_dir,
        edl_path=Path(args.edl) if args.edl else None,
        until_row=args.until_row,
        until_seconds=until_seconds,
        crossfade=args.crossfade,
        effects=args.effects,
        style=args.style,
        effect_intensity=args.effect_intensity,
        warmgrade=args.warmgrade,
        vignette=args.vignette,
        kenburns=args.kenburns,
        loudnorm=args.loudnorm,
        transition_variety=args.transition_variety,
        letterbox=args.letterbox,
        captions=args.captions,
        caption_model=args.caption_model,
        caption_lang=args.caption_lang,
        out_name=args.out,
        work_dir=Path(args.work_dir) if args.work_dir else None,
        keep_work=args.keep_work,
    )


if __name__ == "__main__":
    main()
