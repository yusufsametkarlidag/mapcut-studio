#!/usr/bin/env python3
"""
"Flow Asistanı" penceresi: Google Flow'da görsel/video üretim akışını
uygulamanın içinden yürütmek için.

  1) Kaynak klasörü seç (ör. PRİNCE/vid12 — içinde TIMELINE_MAP*.md olan klasör)
  2) Görseller:  mesajı kopyala → oto-devam kodunu kopyala → indirilenleri al
  3) Videolar:   mesajı kopyala → oto-devam kodunu kopyala → indirilenleri al
  4) Render projesine aktar (ana penceredeki görsel/video seçimini otomatik yapar)
"""
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import check_assets
import flow_tools
import parse_timeline
import story_tools
from platform_tools import IS_MAC, IS_WINDOWS

MOD = "Cmd" if IS_MAC else "Ctrl"
CONSOLE_KEY = "Cmd+Option+J" if IS_MAC else "Ctrl+Shift+J"
PRINCE_DIR = Path.home() / "Desktop" / "PRİNCE"


class FlowAssistant(tk.Toplevel):
    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.title("Video Asistanı")
        self.geometry("760x760")
        self.vid_dir: Path | None = None
        self.busy = False
        self.auto_credit_var = tk.BooleanVar(value=True)
        self._build()

    # ---------------------------------------------------------------- UI ---
    def _build(self):
        pad = dict(padx=8, pady=4)

        top = ttk.LabelFrame(self, text="Kaynak klasör (ör. PRİNCE/vid12)")
        top.pack(fill="x", **pad)
        self.dir_label = ttk.Label(top, text="(seçilmedi)", foreground="#888")
        self.dir_label.grid(row=0, column=0, sticky="w", padx=8, pady=6)
        ttk.Button(top, text="Klasör Seç", command=self.choose_dir).grid(row=0, column=1, padx=4, pady=6)
        ttk.Button(top, text="Yeni video klasörü (vidN)", command=self.new_vid_dir).grid(row=0, column=2, padx=4, pady=6)
        self.map_label = ttk.Label(top, text="", foreground="#2a6")
        self.map_label.grid(row=1, column=0, columnspan=2, sticky="w", padx=8, pady=(0, 6))

        nb = ttk.Notebook(self)
        nb.pack(fill="x", **pad)
        story_tab = ttk.Frame(nb)
        flow_tab = ttk.Frame(nb)
        nb.add(story_tab, text="  Hikâye & Harita  ")
        nb.add(flow_tab, text="  Flow (Görsel / Video)  ")
        self._build_story_tab(story_tab)

        for kind, title in (("gorsel", "1) Görseller"), ("video", "2) Videolar")):
            f = ttk.LabelFrame(flow_tab, text=title)
            f.pack(fill="x", **pad)
            noun = "görsel" if kind == "gorsel" else "video"
            ttk.Button(f, text=f"① {noun.capitalize()} mesajını kopyala",
                       command=lambda k=kind: self.copy_message(k)).grid(row=0, column=0, sticky="w", padx=8, pady=3)
            ttk.Label(f, text=f"Flow'da Yeni proje aç → mesaj kutusuna {MOD}+V → gönder",
                      foreground="#888").grid(row=0, column=1, sticky="w", padx=4)
            ttk.Button(f, text="② Oto-devam kodunu kopyala",
                       command=lambda k=kind: self.copy_script(k)).grid(row=1, column=0, sticky="w", padx=8, pady=3)
            ttk.Label(f, text=f"Flow sekmesinde {CONSOLE_KEY} → konsola {MOD}+V → Enter",
                      foreground="#888").grid(row=1, column=1, sticky="w", padx=4)
            ttk.Button(f, text=f"③ İndirilenleri al → {('görseller' if kind == 'gorsel' else 'videolar')}",
                       command=lambda k=kind: self.import_downloads(k)).grid(row=2, column=0, sticky="w", padx=8, pady=3)
            ttk.Label(f, text="Hepsini sürükleyerek seç → sağ tık → İndir; zip inince bas",
                      foreground="#888").grid(row=2, column=1, sticky="w", padx=4)
            if kind == "video":
                ttk.Checkbutton(f, text="Kredi onaylarını kod otomatik versin (en fazla 10)",
                                variable=self.auto_credit_var).grid(row=3, column=0, columnspan=2, sticky="w", padx=8, pady=(0, 4))

        fin = ttk.LabelFrame(flow_tab, text="3) Render")
        fin.pack(fill="x", **pad)
        ttk.Button(fin, text="Görselleri + videoları render projesine aktar",
                   command=self.send_to_project).grid(row=0, column=0, sticky="w", padx=8, pady=6)
        ttk.Label(fin, text="Ana pencerede proje klasörü (ör. prince_edit) seçili olmalı",
                  foreground="#888").grid(row=0, column=1, sticky="w", padx=4)

        tip = ("İpucu: Konsola ilk kez yapıştırırken Chrome bir uyarı gösterir; "
               "konsola  allow pasting  yazıp Enter'a bas, sonra tekrar yapıştır. "
               "Flow'da sol altta 'Flow Oto-Devam' paneli çıkar; 'Bitti' deyince ③'e geç.")
        ttk.Label(flow_tab, text=tip, foreground="#888", wraplength=700, justify="left").pack(fill="x", padx=12, pady=(2, 4))

        logf = ttk.LabelFrame(self, text="Günlük")
        logf.pack(fill="both", expand=True, **pad)
        self.log_text = tk.Text(logf, height=8, wrap="word")
        self.log_text.pack(fill="both", expand=True)

    # ------------------------------------------------------------ helpers ---
    def log(self, msg):
        def _do():
            self.log_text.insert("end", msg + "\n")
            self.log_text.see("end")
        self.after(0, _do)

    def _need_dir(self) -> bool:
        if self.vid_dir is None:
            messagebox.showwarning("Klasör seçilmedi", "Önce kaynak klasörü (içinde TIMELINE_MAP olan) seç.", parent=self)
            return False
        return True

    def _to_clipboard(self, text: str, what: str):
        self.clipboard_clear()
        self.clipboard_append(text)
        self.update()
        self.log(f"📋 {what} panoya kopyalandı ({len(text):,} karakter).")

    # ------------------------------------------------------------ actions ---
    def choose_dir(self):
        initial = PRINCE_DIR if PRINCE_DIR.exists() else Path.home()
        d = filedialog.askdirectory(title="Kaynak klasörü seç (içinde TIMELINE_MAP olan)",
                                    initialdir=str(initial), parent=self)
        if not d:
            return
        self.set_dir(Path(d))

    def new_vid_dir(self):
        d = story_tools.next_vid_dir()
        self.log(f"Yeni klasör oluşturuldu: {d}")
        self.set_dir(d)

    def set_dir(self, d: Path):
        self.vid_dir = d
        self.dir_label.config(text=str(d), foreground="")
        self.log(f"Kaynak klasör: {d}")
        self.refresh_status()

    def refresh_status(self):
        """Klasördeki harita/avatar/script durumunu üstte gösterir."""
        if self.vid_dir is None:
            return
        parts = []
        try:
            md = flow_tools.find_map(self.vid_dir)
            s = parse_timeline.build_edl(md)["summary"]
            parts.append(f"{md.name}: {s['total_images']} görsel, {s['video_segments']} video, "
                         f"{s['avatar_segments']} avatar bloğu")
        except FileNotFoundError:
            parts.append("harita yok")
        except Exception as e:
            parts.append(f"harita okunamadı ({e})")
        secs = story_tools.avatar_seconds(self.vid_dir)
        parts.append(f"avatar {story_tools.fmt_mmss(secs)}" if secs else "avatar yok")
        parts.append("script ✓" if (self.vid_dir / story_tools.SCRIPT_FILE).exists() else "script yok")
        self.map_label.config(text="  •  ".join(parts))

    def copy_message(self, kind):
        if not self._need_dir():
            return
        try:
            text = flow_tools.image_message(self.vid_dir) if kind == "gorsel" else flow_tools.video_message(self.vid_dir)
        except Exception as e:
            messagebox.showerror("Mesaj hazırlanamadı", str(e), parent=self)
            return
        self._to_clipboard(text, "Görsel mesajı" if kind == "gorsel" else "Video mesajı")

    def copy_script(self, kind):
        auto = kind == "video" and self.auto_credit_var.get()
        self._to_clipboard(flow_tools.oto_devam_script(kind, kredi_onayi_otomatik=auto),
                           "Oto-devam kodu (" + ("görsel" if kind == "gorsel" else
                                                 "video, kredi onayı " + ("otomatik" if auto else "sende")) + ")")

    def import_downloads(self, kind):
        if not self._need_dir() or self.busy:
            return
        srcs = flow_tools.recent_downloads()
        if not srcs:
            files = filedialog.askopenfilenames(title="Flow'dan indirilen zip/dosyaları seç",
                                                initialdir=str(flow_tools.DOWNLOADS), parent=self)
            if not files:
                return
            srcs = [Path(f) for f in files]
        self.log(f"İçe aktarılıyor: {', '.join(p.name for p in srcs[:4])}{' …' if len(srcs) > 4 else ''}")
        self.busy = True

        def work():
            try:
                _, problems = flow_tools.import_downloads(kind, self.vid_dir, srcs, log=self.log)
                if problems:
                    self.after(0, lambda: messagebox.showwarning(
                        "Eksik/sorunlu dosyalar", "\n\n".join("• " + p for p in problems), parent=self))
            except Exception as e:
                self.log(f"HATA: {e}")
            finally:
                self.busy = False
        threading.Thread(target=work, daemon=True).start()

    # ------------------------------------------------------- hikâye & harita ---
    def _build_story_tab(self, tab):
        step = lambda r, text, cmd, hint: (
            ttk.Button(tab, text=text, command=cmd).grid(row=r, column=0, sticky="w", padx=8, pady=3),
            ttk.Label(tab, text=hint, foreground="#888").grid(row=r, column=1, sticky="w", padx=4))
        ttk.Label(tab, text="Konu / fikir:").grid(row=0, column=0, sticky="nw", padx=8, pady=(8, 2))
        self.topic_text = tk.Text(tab, height=3, width=60, wrap="word")
        self.topic_text.grid(row=0, column=1, sticky="we", padx=4, pady=(8, 2))
        step(1, "① Paket mesajını kopyala", self.copy_package_message,
             f"claude.ai'ye {MOD}+V → gönder")
        step(2, "② Paketi kaydet (panodan)", self.save_package,
             "Claude'un cevabını kopyala, sonra bas → PAKET.md")
        step(3, "③ Scripti kaydet (panodan)", self.save_script,
             "Sadece script kısmını kopyala, sonra bas → SCRIPT.txt")
        step(4, "④ HeyGen avatar videosunu seç", self.choose_avatar_video,
             "HeyGen'den indirdiğin video → avatar.mp4 (süre otomatik ölçülür)")
        step(5, "⑤ Harita mesajını kopyala", self.copy_map_message,
             f"Script + avatar süresi + örnek harita → claude.ai'ye {MOD}+V")
        step(6, "⑥ Haritayı kaydet ve kontrol et", self.save_map,
             "Claude'un haritasını kopyala, sonra bas → TIMELINE_MAP.md")
        ttk.Button(tab, text="Şablonları düzenle…", command=self.open_templates)\
            .grid(row=7, column=0, sticky="w", padx=8, pady=(8, 6))
        ttk.Label(tab, text="Claude'a verdiğin kendi mesajlarını sablonlar/ klasöründeki dosyalara yapıştırabilirsin.",
                  foreground="#888").grid(row=7, column=1, sticky="w", padx=4)
        tab.columnconfigure(1, weight=1)

    def _clipboard_text(self):
        try:
            return self.clipboard_get()
        except tk.TclError:
            return ""

    def copy_package_message(self):
        topic = self.topic_text.get("1.0", "end").strip()
        if not topic:
            messagebox.showwarning("Konu boş", "Önce konu / fikir kutusuna bir şey yaz.", parent=self)
            return
        self._to_clipboard(story_tools.package_message(topic), "Paket mesajı")

    def _save_from_clipboard(self, name, what, min_len=50):
        if not self._need_dir():
            return None
        text = self._clipboard_text()
        if len(text.strip()) < min_len:
            messagebox.showwarning("Pano boş", f"Önce Claude'un cevabından {what.lower()} kısmını kopyala.", parent=self)
            return None
        p = self.vid_dir / name
        if p.exists() and not messagebox.askyesno("Üzerine yazılsın mı?", f"{name} zaten var. Değiştirilsin mi?", parent=self):
            return None
        story_tools.save_text(self.vid_dir, name, text)
        self.log(f"💾 {what} kaydedildi: {p.name} ({len(text):,} karakter)")
        self.refresh_status()
        return p

    def save_package(self):
        self._save_from_clipboard(story_tools.PACKAGE_FILE, "Paket")

    def save_script(self):
        self._save_from_clipboard(story_tools.SCRIPT_FILE, "Script", min_len=200)

    def choose_avatar_video(self):
        if not self._need_dir() or self.busy:
            return
        f = filedialog.askopenfilename(title="HeyGen'den indirdiğin avatar videosunu seç",
                                       initialdir=str(flow_tools.DOWNLOADS),
                                       filetypes=[("Video", "*.mp4 *.mov"), ("Tüm dosyalar", "*.*")], parent=self)
        if not f:
            return
        self.busy = True
        self.log(f"Avatar kopyalanıyor: {Path(f).name} …")

        def work():
            try:
                secs = story_tools.import_avatar(self.vid_dir, Path(f))
                self.log(f"🎙️ avatar.mp4 hazır — süre {story_tools.fmt_mmss(secs)} ({secs} sn)")
                self.after(0, self.refresh_status)
            except Exception as e:
                self.log(f"HATA: {e}")
            finally:
                self.busy = False
        threading.Thread(target=work, daemon=True).start()

    def copy_map_message(self):
        if not self._need_dir():
            return
        try:
            text = story_tools.map_message(self.vid_dir)
        except Exception as e:
            messagebox.showwarning("Eksik adım", str(e), parent=self)
            return
        self._to_clipboard(text, "Harita mesajı")

    def save_map(self):
        if not self._need_dir():
            return
        others = [m for m in self.vid_dir.glob("TIMELINE_MAP*.md") if m.name != story_tools.MAP_FILE]
        p = self._save_from_clipboard(story_tools.MAP_FILE, "Harita", min_len=500)
        if p is None:
            return
        if others:
            self.log(f"⚠️ Klasörde başka harita da var ({', '.join(m.name for m in others)}); "
                     "karışmasın diye onları taşı ya da sil.")
        summary, problems = story_tools.validate_map(p, story_tools.avatar_seconds(self.vid_dir))
        if summary:
            self.log(f"Harita: {summary}")
        if problems:
            for pr in problems:
                self.log(f"❌ {pr}")
            messagebox.showwarning("Haritada sorun var",
                                   "\n\n".join("• " + x for x in problems) +
                                   "\n\nBu hataları Claude'a yazıp haritayı düzelttir, sonra tekrar kaydet.", parent=self)
        else:
            self.log("✅ Harita hazır — Flow sekmesine geçebilirsin.")
        self.refresh_status()

    def open_templates(self):
        story_tools.TEMPLATES_DIR.mkdir(exist_ok=True)
        import subprocess
        if IS_MAC:
            subprocess.run(["open", str(story_tools.TEMPLATES_DIR)])
        elif IS_WINDOWS:
            subprocess.run(["explorer", str(story_tools.TEMPLATES_DIR)])
        else:
            subprocess.run(["xdg-open", str(story_tools.TEMPLATES_DIR)])

    def send_to_project(self):
        if not self._need_dir():
            return
        if self.app.project_dir is None:
            messagebox.showwarning("Proje seçilmedi", "Ana pencerede önce render proje klasörünü (ör. prince_edit) seç.",
                                   parent=self)
            return
        md = flow_tools.find_map(self.vid_dir)
        self.app.load_md(md)
        avatar = self.vid_dir / story_tools.AVATAR_FILE
        videos = lambda: self.app.choose_videos(folder=flow_tools.videos_dir(self.vid_dir))
        images = lambda: self.app.choose_images(folder=flow_tools.images_dir(self.vid_dir), on_done=videos)
        if avatar.exists():
            self.app.choose_avatar(path=str(avatar), on_done=images)
        else:
            images()
        self.log("Ana pencereye aktarılıyor: harita + avatar + görseller + videolar. Bitince render'ı başlatabilirsin.")
