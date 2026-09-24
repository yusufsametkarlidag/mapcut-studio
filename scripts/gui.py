#!/usr/bin/env python3
"""
Video Edit Studio - masaustu arayuz.

Herhangi bir "video projesi" klasoru (avatar/, videolar/, gorseller/,
assets/, output/, TIMELINE_MAP.md) uzerinde calisir. Yeni bir video
yaparken kod duzenlemene gerek kalmadan:
  1) Proje klasoru sec/olustur
  2) TIMELINE_MAP.md sec
  3) avatar.mp4 sec
  4) B-roll videolarinin oldugu klasoru sec (isimdeki numaraya gore siralanip
     otomatik V1.mp4...Vn.mp4 olarak kopyalanir)
  5) Gorsellerin oldugu klasoru sec (isme gore siralanip otomatik
     gorsel_001... olarak kopyalanir)
  6) Efekt/crossfade ayarlarini sec
  7) Test Render / Tam Render butonuna bas, ilerlemeyi izle

Calistirma:
  python3 gui.py
"""
import queue
import re
import shutil
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS_DIR))
import parse_timeline  # noqa: E402
import render as render_mod  # noqa: E402

IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".PNG", ".JPG", ".JPEG")
VIDEO_EXTS = (".mp4", ".mov", ".MP4", ".MOV")
SUBFOLDERS = ["avatar", "videolar", "gorseller", "assets", "output"]

PROGRESS_RE = re.compile(r"\[(\d+)/(\d+)\]")
REPORT_LINE_RE = re.compile(r"^(Çıktı dosyası|Hedef süre|Gerçek süre|Fark|Klip sayısı)\s*:\s*(.+)$")
STAGE_RE = re.compile(r"^\[Aşama [^\]]+\]|^\s*Tur \d+:.*")
_NUM_SPLIT_RE = re.compile(r"(\d+)")


def natural_key(p: Path):
    # "Görsel_#10" alfabetik siralamada "#100"den sonra geliyordu; sayilari
    # sayi olarak karsilastir (1, 2, ... 9, 10, 11 ... 100).
    return [int(t) if t.isdigit() else t.lower() for t in _NUM_SPLIT_RE.split(p.name)]


class VideoEditStudio(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Video Edit Studio")
        self.geometry("880x720")

        self.project_dir: Path | None = None
        self.edl: dict | None = None
        self.log_queue: queue.Queue = queue.Queue()
        self.busy = False
        self.last_report: dict = {}

        self._build_widgets()
        self.after(100, self._poll_queue)

    # ---------------------------------------------------------------- UI ---
    def _build_widgets(self):
        pad = dict(padx=8, pady=4)

        proj = ttk.LabelFrame(self, text="1) Proje")
        proj.pack(fill="x", **pad)
        self.project_label = ttk.Label(proj, text="(proje seçilmedi)", foreground="#888")
        self.project_label.grid(row=0, column=0, sticky="w", padx=8, pady=6)
        ttk.Button(proj, text="Proje Klasörü Seç / Oluştur", command=self.choose_project)\
            .grid(row=0, column=1, padx=8, pady=6)

        self.md_label = ttk.Label(proj, text="TIMELINE_MAP.md: -")
        self.md_label.grid(row=1, column=0, sticky="w", padx=8, pady=2)
        ttk.Button(proj, text="TIMELINE_MAP.md Seç", command=self.choose_md)\
            .grid(row=1, column=1, padx=8, pady=2)

        self.summary_label = ttk.Label(proj, text="", foreground="#2a6")
        self.summary_label.grid(row=2, column=0, columnspan=2, sticky="w", padx=8, pady=(2, 8))

        src = ttk.LabelFrame(self, text="2) Kaynaklar")
        src.pack(fill="x", **pad)

        self.avatar_label = ttk.Label(src, text="avatar.mp4: -")
        self.avatar_label.grid(row=0, column=0, sticky="w", padx=8, pady=4)
        ttk.Button(src, text="avatar.mp4 Seç", command=self.choose_avatar)\
            .grid(row=0, column=1, padx=8, pady=4)

        self.video_label = ttk.Label(src, text="B-roll videolar: -")
        self.video_label.grid(row=1, column=0, sticky="w", padx=8, pady=4)
        ttk.Button(src, text="Video Klasörü Seç", command=self.choose_videos)\
            .grid(row=1, column=1, padx=8, pady=4)

        self.image_label = ttk.Label(src, text="Görseller: -")
        self.image_label.grid(row=2, column=0, sticky="w", padx=8, pady=4)
        ttk.Button(src, text="Görsel Klasörü Seç", command=self.choose_images)\
            .grid(row=2, column=1, padx=8, pady=4)

        cfg = ttk.LabelFrame(self, text="3) Ayarlar")
        cfg.pack(fill="x", **pad)

        ttk.Label(cfg, text="Crossfade süresi (sn):").grid(row=0, column=0, sticky="w", padx=8, pady=4)
        self.crossfade_var = tk.DoubleVar(value=0.5)
        self.crossfade_scale = ttk.Scale(cfg, from_=0.1, to=1.0, variable=self.crossfade_var,
                                          orient="horizontal", length=200,
                                          command=lambda v: self.crossfade_value_label.config(
                                              text=f"{float(v):.2f}s"))
        self.crossfade_scale.grid(row=0, column=1, padx=8, pady=4)
        self.crossfade_value_label = ttk.Label(cfg, text="0.50s")
        self.crossfade_value_label.grid(row=0, column=2, sticky="w", padx=4)

        self.effects_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(cfg, text="Efektler açık", variable=self.effects_var)\
            .grid(row=1, column=0, sticky="w", padx=8, pady=4)

        self.intensity_var = tk.StringVar(value="medium")
        intensity_frame = ttk.Frame(cfg)
        intensity_frame.grid(row=1, column=1, columnspan=2, sticky="w")
        for val, txt in [("light", "Hafif"), ("medium", "Orta"), ("strong", "Güçlü")]:
            ttk.Radiobutton(intensity_frame, text=txt, value=val, variable=self.intensity_var)\
                .pack(side="left", padx=4)

        ttk.Label(cfg, text="Görünüm:").grid(row=2, column=0, sticky="w", padx=8, pady=4)
        self.style_var = tk.StringVar(value="vintage1")
        style_frame = ttk.Frame(cfg)
        style_frame.grid(row=2, column=1, columnspan=2, sticky="w")
        for val, txt in [("modern", "Modern (sallanmasız, sade)"),
                          ("vintage1", "Vintage 1 (çok hafif, yavaş hareket)"),
                          ("vintage2", "Vintage 2 (biraz daha belirgin)")]:
            ttk.Radiobutton(style_frame, text=txt, value=val, variable=self.style_var)\
                .pack(side="left", padx=4)

        self.warmgrade_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(cfg, text="Sıcak/sepia renk tonu", variable=self.warmgrade_var)\
            .grid(row=3, column=0, sticky="w", padx=8, pady=4)
        self.kenburns_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(cfg, text="Ken Burns zoom (görsellerde)", variable=self.kenburns_var)\
            .grid(row=3, column=1, sticky="w", padx=8, pady=4)
        self.loudnorm_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(cfg, text="Ses normalizasyonu (loudnorm)", variable=self.loudnorm_var)\
            .grid(row=3, column=2, sticky="w", padx=8, pady=4)
        self.vignette_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(cfg, text="Vinyet (köşeler koyulaşsın)", variable=self.vignette_var)\
            .grid(row=4, column=0, sticky="w", padx=8, pady=4)
        self.transition_variety_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(cfg, text="Geçiş çeşitliliği (ara sıra hafif kaydırma)",
                         variable=self.transition_variety_var)\
            .grid(row=4, column=1, sticky="w", padx=8, pady=4)
        self.letterbox_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(cfg, text="Sinematik letterbox (üst/alt siyah bant)",
                         variable=self.letterbox_var)\
            .grid(row=4, column=2, sticky="w", padx=8, pady=4)

        cap = ttk.LabelFrame(self, text="4) Otomatik Altyazı")
        cap.pack(fill="x", **pad)
        self.captions_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(cap, text="Altyazı ekle (kelime kelime vurgulu, Whisper ile)",
                         variable=self.captions_var).grid(row=0, column=0, sticky="w", padx=8, pady=4)
        ttk.Label(cap, text="Model:").grid(row=0, column=1, sticky="e", padx=(16, 4))
        self.caption_model_var = tk.StringVar(value="small.en")
        ttk.Combobox(cap, textvariable=self.caption_model_var, width=10, state="readonly",
                     values=["tiny.en", "base.en", "small.en", "medium.en"])\
            .grid(row=0, column=2, sticky="w", padx=4)
        ttk.Label(cap, text="Dil:").grid(row=0, column=3, sticky="e", padx=(16, 4))
        self.caption_lang_var = tk.StringVar(value="en")
        ttk.Entry(cap, textvariable=self.caption_lang_var, width=6)\
            .grid(row=0, column=4, sticky="w", padx=4)
        ttk.Label(cap, text="(model ne kadar büyükse doğruluk artar, hız düşer; "
                             "ilk kullanımda model otomatik indirilir)",
                  foreground="#888").grid(row=1, column=0, columnspan=5, sticky="w", padx=8)

        run = ttk.LabelFrame(self, text="5) Render")
        run.pack(fill="x", **pad)

        ttk.Label(run, text="Test uzunluğu (sn):").grid(row=0, column=0, sticky="w", padx=8, pady=6)
        self.test_seconds_var = tk.IntVar(value=150)
        ttk.Spinbox(run, from_=10, to=3600, increment=10, width=6,
                    textvariable=self.test_seconds_var).grid(row=0, column=1, sticky="w", padx=(0, 8))
        ttk.Label(run, text="(TIMELINE_MAP.md'nin başından itibaren; satır sayısına değil, "
                             "süreye göre kesilir — her yapıda çalışır)",
                  foreground="#888").grid(row=0, column=2, columnspan=2, sticky="w", padx=4)

        self.test_btn = ttk.Button(run, text="Test Render", command=self.run_test_render)
        self.test_btn.grid(row=1, column=0, padx=8, pady=6)
        self.full_btn = ttk.Button(run, text="Tam Render", command=self.run_full_render)
        self.full_btn.grid(row=1, column=1, padx=8, pady=6)
        self.reveal_btn = ttk.Button(run, text="Çıktıyı Finder'da Göster",
                                      command=self.reveal_output, state="disabled")
        self.reveal_btn.grid(row=1, column=2, padx=8, pady=6)

        self.progress = ttk.Progressbar(run, orient="horizontal", mode="determinate", length=500)
        self.progress.grid(row=2, column=0, columnspan=4, sticky="we", padx=8, pady=4)
        self.progress_label = ttk.Label(run, text="")
        self.progress_label.grid(row=3, column=0, columnspan=4, sticky="w", padx=8)

        log_frame = ttk.LabelFrame(self, text="Günlük")
        log_frame.pack(fill="both", expand=True, **pad)
        self.log_text = tk.Text(log_frame, height=16, font=("Menlo", 11), wrap="word")
        self.log_text.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        scroll.pack(side="right", fill="y")
        self.log_text.configure(yscrollcommand=scroll.set)

    # ------------------------------------------------------------ helpers ---
    def _log(self, msg: str):
        self.log_text.insert("end", msg + "\n")
        self.log_text.see("end")

    def _require_project(self) -> bool:
        if self.project_dir is None:
            messagebox.showwarning("Proje seçilmedi", "Önce bir proje klasörü seç.")
            return False
        return True

    def _set_controls_enabled(self, enabled: bool):
        state = "normal" if enabled else "disabled"
        for w in (self.test_btn, self.full_btn):
            w.configure(state=state)

    # ------------------------------------------------------------ project ---
    def choose_project(self):
        path = filedialog.askdirectory(title="Proje klasörünü seç (yeni klasör de oluşturabilirsin)")
        if not path:
            return
        self.project_dir = Path(path)
        for sub in SUBFOLDERS:
            (self.project_dir / sub).mkdir(parents=True, exist_ok=True)
        self.project_label.config(text=str(self.project_dir), foreground="black")
        self._log(f"Proje klasörü: {self.project_dir}")

        md_path = self.project_dir / "TIMELINE_MAP.md"
        if md_path.exists():
            self.md_label.config(text=f"TIMELINE_MAP.md: {md_path.name} ✓")
            self._reparse_edl()
        else:
            self.md_label.config(text="TIMELINE_MAP.md: bulunamadı — seçmelisin")
            self.edl = None

        self._refresh_source_labels()

    def choose_md(self):
        if not self._require_project():
            return
        path = filedialog.askopenfilename(title="TIMELINE_MAP.md dosyasını seç",
                                           filetypes=[("Markdown", "*.md"), ("Tüm dosyalar", "*.*")])
        if not path:
            return
        dest = self.project_dir / "TIMELINE_MAP.md"
        try:
            if Path(path).resolve() != dest.resolve():
                shutil.copy(path, dest)
                self._log(f"TIMELINE_MAP.md kopyalandı: {path} -> {dest}")
            else:
                self._log(f"TIMELINE_MAP.md zaten proje klasöründe: {dest}")
        except OSError as e:
            messagebox.showerror("Kopyalama hatası", f"TIMELINE_MAP.md kopyalanamadı:\n{e}")
            return
        self.md_label.config(text=f"TIMELINE_MAP.md: {Path(path).name} ✓")
        self._reparse_edl()

    def _reparse_edl(self):
        md_path = self.project_dir / "TIMELINE_MAP.md"
        try:
            self.edl = parse_timeline.build_edl(md_path)
        except Exception as e:
            self.edl = None
            messagebox.showerror("Parse hatası", f"TIMELINE_MAP.md okunamadı:\n{e}")
            self.summary_label.config(text="")
            return

        out_path = self.project_dir / "edl.json"
        import json
        out_path.write_text(json.dumps(self.edl, ensure_ascii=False, indent=2), encoding="utf-8")

        s = self.edl["summary"]
        total = self.edl["total_duration_seconds"]
        mm, ss = divmod(total, 60)
        self.summary_label.config(
            text=(f"Toplam süre: {mm}:{ss:02d} ({total}s)  |  Avatar: {s['avatar_segments']}  |  "
                  f"Video: {s['video_segments']} ({', '.join(s['video_ids'])})  |  "
                  f"Görsel: {s['total_images']} ({s['image_blocks']} blok)"))
        self._log(f"EDL parse edildi: {total}s, {s['total_images']} görsel, "
                   f"{s['video_segments']} video, {s['avatar_segments']} avatar bloğu")

    # ------------------------------------------------------------ sources ---
    def choose_avatar(self):
        if not self._require_project():
            return
        path = filedialog.askopenfilename(title="avatar.mp4 dosyasını seç",
                                           filetypes=[("Video", "*.mp4 *.mov"), ("Tüm dosyalar", "*.*")])
        if not path:
            return
        dest = self.project_dir / "avatar" / "avatar.mp4"
        self._log(f"avatar.mp4 kopyalanıyor... ({path})")
        self._run_bg(lambda: shutil.copy(path, dest), on_done=lambda _: self._after_avatar_copied(dest))

    def _after_avatar_copied(self, dest):
        self.avatar_label.config(text=f"avatar.mp4: {dest.name} ✓")
        self._log(f"avatar.mp4 hazır: {dest}")

    def choose_videos(self):
        if not self._require_project():
            return
        folder = filedialog.askdirectory(title="B-roll videolarının olduğu klasörü seç")
        if not folder:
            return
        files = sorted(
            [p for p in Path(folder).iterdir() if p.suffix in VIDEO_EXTS],
            key=natural_key,
        )
        if not files:
            messagebox.showwarning("Video bulunamadı", "Seçilen klasörde .mp4/.mov dosyası yok.")
            return

        expected = self.edl["summary"]["video_segments"] if self.edl else None
        if expected is not None and len(files) != expected:
            if not messagebox.askyesno(
                "Sayı uyuşmuyor",
                f"TIMELINE_MAP.md'ye göre {expected} adet B-roll video bekleniyor, "
                f"ama seçilen klasörde {len(files)} dosya var.\nYine de devam edilsin mi?"
            ):
                return

        dest_dir = self.project_dir / "videolar"
        for old in dest_dir.glob("V*.mp4"):
            old.unlink()

        def do_copy():
            for i, f in enumerate(files, start=1):
                dest = dest_dir / f"V{i}.mp4"
                shutil.copy(f, dest)
        self._log(f"{len(files)} video kopyalanıyor (sıra: dosya adındaki numaraya göre)...")
        self._run_bg(do_copy, on_done=lambda _: self._after_videos_copied(files))

    def _after_videos_copied(self, files):
        self.video_label.config(text=f"B-roll videolar: {len(files)} dosya (V1..V{len(files)}) ✓")
        self._log(f"Videolar hazır: V1.mp4 .. V{len(files)}.mp4")
        for i, f in enumerate(files, start=1):
            self._log(f"    V{i}.mp4  <-  {f.name}")

    def choose_images(self):
        if not self._require_project():
            return
        folder = filedialog.askdirectory(title="Görsellerin olduğu klasörü seç")
        if not folder:
            return
        files = sorted(
            [p for p in Path(folder).iterdir() if p.suffix in IMAGE_EXTS],
            key=natural_key,
        )
        if not files:
            messagebox.showwarning("Görsel bulunamadı", "Seçilen klasörde .png/.jpg dosyası yok.")
            return

        expected = self.edl["summary"]["total_images"] if self.edl else None
        if expected is not None and len(files) != expected:
            if not messagebox.askyesno(
                "Sayı uyuşmuyor",
                f"TIMELINE_MAP.md'ye göre {expected} adet görsel bekleniyor, "
                f"ama seçilen klasörde {len(files)} dosya var.\nYine de devam edilsin mi?"
            ):
                return

        dest_dir = self.project_dir / "gorseller"
        for old in list(dest_dir.glob("gorsel_*.png")) + list(dest_dir.glob("gorsel_*.jpg")) + \
                list(dest_dir.glob("gorsel_*.jpeg")):
            old.unlink()

        def do_copy():
            for i, f in enumerate(files, start=1):
                ext = f.suffix.lower()
                dest = dest_dir / f"gorsel_{i:03d}{ext}"
                shutil.copy(f, dest)
        self._log(f"{len(files)} görsel kopyalanıyor (sıra: dosya adındaki numaraya göre)...")
        self._run_bg(do_copy, on_done=lambda _: self._after_images_copied(files))

    def _after_images_copied(self, files):
        self.image_label.config(text=f"Görseller: {len(files)} dosya (gorsel_001..{len(files):03d}) ✓")
        self._log(f"Görseller hazır: gorsel_001 .. gorsel_{len(files):03d}")

    def _refresh_source_labels(self):
        avatar_path = self.project_dir / "avatar" / "avatar.mp4"
        self.avatar_label.config(text=f"avatar.mp4: {'✓ mevcut' if avatar_path.exists() else '-'}")
        n_videos = len(list((self.project_dir / "videolar").glob("V*.mp4")))
        self.video_label.config(text=f"B-roll videolar: {n_videos} dosya" if n_videos else "B-roll videolar: -")
        n_images = len(list((self.project_dir / "gorseller").glob("gorsel_*.*")))
        self.image_label.config(text=f"Görseller: {n_images} dosya" if n_images else "Görseller: -")

    # ------------------------------------------------------------- render ---
    def run_test_render(self):
        seconds = self.test_seconds_var.get()
        self._start_render(until_seconds=seconds, out_name="test_render.mp4")

    def run_full_render(self):
        self._start_render(until_seconds=None, out_name="final_render.mp4")

    def _check_missing_assets(self, until_seconds) -> str | None:
        """Render'i baslatmadan once eksik dosyalari kontrol eder, varsa
        kullaniciya net bir Turkce ozet dondurur (None ise her sey tamam).
        Satir numarasina degil sureye gore secim yapar; boylece her
        TIMELINE_MAP.md yapisinda (avatar/video/gorsel sirasi ne olursa
        olsun) dogru calisir."""
        entries = render_mod.select_entries(self.edl, until_seconds=until_seconds)
        clips = render_mod.flatten_clips(entries, self.project_dir)
        missing = render_mod.find_missing_assets(clips, self.project_dir)
        if not missing:
            return None

        by_kind = {"avatar": [], "video": [], "image": []}
        for kind, path in missing:
            by_kind[kind].append(path)

        lines = ["Render başlamadan önce şu dosyalar eksik:\n"]
        if by_kind["avatar"]:
            lines.append("• avatar.mp4 seçilmemiş — \"avatar.mp4 Seç\" butonuna bas.")
        if by_kind["video"]:
            names = ", ".join(Path(p).name for p in by_kind["video"][:5])
            more = f" (+{len(by_kind['video']) - 5} tane daha)" if len(by_kind["video"]) > 5 else ""
            lines.append(f"• B-roll video eksik: {names}{more} — \"Video Klasörü Seç\" ile ekle.")
        if by_kind["image"]:
            names = ", ".join(Path(p).name for p in by_kind["image"][:5])
            more = f" (+{len(by_kind['image']) - 5} tane daha)" if len(by_kind["image"]) > 5 else ""
            lines.append(f"• Görsel eksik: {names}{more} — \"Görsel Klasörü Seç\" ile ekle.")
        return "\n".join(lines)

    def _start_render(self, until_seconds, out_name):
        if not self._require_project():
            return
        if self.busy:
            return
        if self.edl is None:
            messagebox.showwarning("EDL yok", "Önce TIMELINE_MAP.md seçip parse edilmesini bekle.")
            return

        missing_msg = self._check_missing_assets(until_seconds)
        if missing_msg:
            messagebox.showwarning("Eksik dosyalar var", missing_msg)
            return

        cmd = [
            sys.executable, str(SCRIPTS_DIR / "render.py"),
            "--project-dir", str(self.project_dir),
            "--crossfade", f"{self.crossfade_var.get():.2f}",
            "--style", self.style_var.get(),
            "--effect-intensity", self.intensity_var.get(),
            "--caption-model", self.caption_model_var.get(),
            "--caption-lang", self.caption_lang_var.get(),
            "--out", out_name,
        ]
        cmd += ["--effects"] if self.effects_var.get() else ["--no-effects"]
        cmd += ["--warmgrade"] if self.warmgrade_var.get() else ["--no-warmgrade"]
        cmd += ["--vignette"] if self.vignette_var.get() else ["--no-vignette"]
        cmd += ["--transition-variety"] if self.transition_variety_var.get() else ["--no-transition-variety"]
        cmd += ["--letterbox"] if self.letterbox_var.get() else ["--no-letterbox"]
        cmd += ["--kenburns"] if self.kenburns_var.get() else ["--no-kenburns"]
        cmd += ["--loudnorm"] if self.loudnorm_var.get() else ["--no-loudnorm"]
        cmd += ["--captions"] if self.captions_var.get() else ["--no-captions"]
        if until_seconds is not None:
            cmd += ["--until-seconds", str(until_seconds)]

        self.busy = True
        self._set_controls_enabled(False)
        self.reveal_btn.configure(state="disabled")
        if str(self.progress["mode"]) == "indeterminate":
            self.progress.stop()
        self.progress.config(mode="determinate")
        self.progress["value"] = 0
        self.progress_label.config(text="Başlatılıyor...")
        self._log("\n" + "=" * 60)
        self._log("RENDER BAŞLIYOR: " + " ".join(cmd))
        self._log("=" * 60)

        threading.Thread(target=self._render_worker, args=(cmd,), daemon=True).start()

    def _render_worker(self, cmd):
        report_lines = {}
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                     text=True, bufsize=1)
            for line in proc.stdout:
                line = line.rstrip("\n")
                self.log_queue.put(("log", line))
                m = PROGRESS_RE.search(line)
                if m:
                    self.log_queue.put(("progress", int(m.group(1)), int(m.group(2))))
                elif STAGE_RE.match(line.strip()):
                    self.log_queue.put(("stage", line.strip()))
                rm = REPORT_LINE_RE.match(line.strip())
                if rm:
                    report_lines[rm.group(1)] = rm.group(2).strip()
            code = proc.wait()
            self.log_queue.put(("render_done", code, report_lines))
        except Exception as e:
            self.log_queue.put(("render_done", -1, {"Hata": str(e)}))

    def reveal_output(self):
        path = self.last_report.get("out_path")
        if path and Path(path).exists():
            subprocess.run(["open", "-R", str(path)])

    # --------------------------------------------------------------- loop ---
    def _poll_queue(self):
        try:
            while True:
                item = self.log_queue.get_nowait()
                kind = item[0]
                if kind == "log":
                    self._log(item[1])
                elif kind == "progress":
                    cur, total = item[1], item[2]
                    if str(self.progress["mode"]) == "indeterminate":
                        self.progress.stop()
                        self.progress.config(mode="determinate")
                    self.progress["maximum"] = total
                    self.progress["value"] = cur
                    self.progress_label.config(text=f"Segment {cur}/{total}")
                elif kind == "stage":
                    # Aşama B/C tek satırlık ffmpeg çağrıları yapıyor, segment
                    # bazlı ilerleme yok — çubuğu "hâlâ çalışıyor" göstermesi
                    # için animasyonlu (indeterminate) moda alıyoruz.
                    if str(self.progress["mode"]) != "indeterminate":
                        self.progress.config(mode="indeterminate")
                        self.progress.start(15)
                    self.progress_label.config(text=item[1])
                elif kind == "render_done":
                    code, report_lines = item[1], item[2]
                    self._on_render_done(code, report_lines)
                elif kind == "bg_done":
                    result, on_done, error = item[1], item[2], item[3]
                    self.busy = False
                    if error:
                        messagebox.showerror("Hata", str(error))
                    elif on_done:
                        on_done(result)
        except queue.Empty:
            pass
        self.after(100, self._poll_queue)

    def _run_bg(self, fn, on_done=None):
        if self.busy:
            return
        self.busy = True

        def target():
            try:
                result = fn()
                self.log_queue.put(("bg_done", result, on_done, None))
            except Exception as e:
                self.log_queue.put(("bg_done", None, on_done, e))

        threading.Thread(target=target, daemon=True).start()

    def _on_render_done(self, code, report_lines):
        self.busy = False
        self._set_controls_enabled(True)
        if str(self.progress["mode"]) == "indeterminate":
            self.progress.stop()
            self.progress.config(mode="determinate")
        if code == 0:
            self.progress_label.config(text="Tamamlandı ✓")
            out_path = report_lines.get("Çıktı dosyası")
            self.last_report = {"out_path": out_path, **report_lines}
            if out_path:
                self.reveal_btn.configure(state="normal")
            summary = "\n".join(f"{k}: {v}" for k, v in report_lines.items())
            messagebox.showinfo("Render tamamlandı", summary or "Render tamamlandı.")
        else:
            self.progress_label.config(text="HATA ⚠️ (günlüğe bak)")
            messagebox.showerror("Render başarısız", "Render sırasında hata oluştu. Günlük paneline bak.")


if __name__ == "__main__":
    app = VideoEditStudio()
    app.mainloop()
