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
from platform_tools import IS_MAC

MOD = "Cmd" if IS_MAC else "Ctrl"
CONSOLE_KEY = "Cmd+Option+J" if IS_MAC else "Ctrl+Shift+J"
PRINCE_DIR = Path.home() / "Desktop" / "PRİNCE"


class FlowAssistant(tk.Toplevel):
    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.title("Flow Asistanı")
        self.geometry("720x640")
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
        ttk.Button(top, text="Klasör Seç", command=self.choose_dir).grid(row=0, column=1, padx=8, pady=6)
        self.map_label = ttk.Label(top, text="", foreground="#2a6")
        self.map_label.grid(row=1, column=0, columnspan=2, sticky="w", padx=8, pady=(0, 6))

        for kind, title in (("gorsel", "1) Görseller"), ("video", "2) Videolar")):
            f = ttk.LabelFrame(self, text=title)
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

        fin = ttk.LabelFrame(self, text="3) Render")
        fin.pack(fill="x", **pad)
        ttk.Button(fin, text="Görselleri + videoları render projesine aktar",
                   command=self.send_to_project).grid(row=0, column=0, sticky="w", padx=8, pady=6)
        ttk.Label(fin, text="Ana pencerede proje klasörü (ör. prince_edit) seçili olmalı",
                  foreground="#888").grid(row=0, column=1, sticky="w", padx=4)

        tip = ("İpucu: Konsola ilk kez yapıştırırken Chrome bir uyarı gösterir; "
               "konsola  allow pasting  yazıp Enter'a bas, sonra tekrar yapıştır. "
               "Flow'da sol altta 'Flow Oto-Devam' paneli çıkar; 'Bitti' deyince ③'e geç.")
        ttk.Label(self, text=tip, foreground="#888", wraplength=680, justify="left").pack(fill="x", padx=12, pady=(2, 4))

        logf = ttk.LabelFrame(self, text="Günlük")
        logf.pack(fill="both", expand=True, **pad)
        self.log_text = tk.Text(logf, height=10, wrap="word")
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
        d = Path(d)
        try:
            md = flow_tools.find_map(d)
            s = parse_timeline.build_edl(md)["summary"]
        except Exception as e:
            messagebox.showerror("Harita okunamadı", str(e), parent=self)
            return
        self.vid_dir = d
        self.dir_label.config(text=str(d), foreground="")
        self.map_label.config(text=f"{md.name}: {s['total_images']} görsel, {s['video_segments']} video, "
                                   f"{s['avatar_segments']} avatar bloğu")
        self.log(f"Kaynak klasör: {d}")

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

    def send_to_project(self):
        if not self._need_dir():
            return
        if self.app.project_dir is None:
            messagebox.showwarning("Proje seçilmedi", "Ana pencerede önce render proje klasörünü (ör. prince_edit) seç.",
                                   parent=self)
            return
        md = flow_tools.find_map(self.vid_dir)
        self.app.load_md(md)
        self.app.choose_images(folder=flow_tools.images_dir(self.vid_dir),
                               on_done=lambda: self.app.choose_videos(folder=flow_tools.videos_dir(self.vid_dir)))
        self.log("Ana pencereye aktarıldı: harita + görseller + videolar. Avatarı seçip render'ı başlatabilirsin.")
