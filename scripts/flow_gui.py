#!/usr/bin/env python3
# MapCut Studio — Copyright (c) 2026 yusufsametkarlidag. PolyForm Noncommercial 1.0.0 lisanslıdır: ticari kullanım yasaktır. Ayrıntı: LICENSE.md
"""
"Flow Asistanı" penceresi: Google Flow'da görsel/video üretim akışını
uygulamanın içinden yürütmek için.

  1) Kaynak klasörü seç (ör. Videolar/vid12 — içinde TIMELINE_MAP*.md olan klasör)
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
import settings
import story_tools
from platform_tools import IS_MAC, IS_WINDOWS

MOD = "Cmd" if IS_MAC else "Ctrl"
CONSOLE_KEY = "Cmd+Option+J" if IS_MAC else "Ctrl+Shift+J"


def shlex_quote(s):
    import shlex
    return shlex.quote(s)


class SettingsDialog(tk.Toplevel):
    """ayarlar.json düzenleyici (kullanıcıya özel: klasör, claude.ai sohbeti, mesajlar, HeyGen)."""
    FIELDS = [
        ("ana_klasor", "Ana klasör (vid1, vid2 …)"),
        ("claude_sohbet_url", "claude.ai sohbet linki"),
        ("fikir_mesaji", "Fikir mesajı"),
        ("harita_mesaji", "Harita mesajı ({DK} {SN} {TOPLAM_SN})"),
        ("heygen.avatar", "HeyGen avatar adı"),
        ("heygen.ses", "HeyGen ses adı"),
    ]

    def __init__(self, parent):
        super().__init__(parent)
        self.title("Ayarlar")
        self.data = settings.load()
        self.vars = {}
        for r, (key, label) in enumerate(self.FIELDS):
            ttk.Label(self, text=label).grid(row=r, column=0, sticky="w", padx=8, pady=3)
            v = tk.StringVar(value=self._get(key))
            ttk.Entry(self, textvariable=v, width=70).grid(row=r, column=1, sticky="we", padx=8, pady=3)
            self.vars[key] = v
        ttk.Button(self, text="Seç…", command=self._pick_dir).grid(row=0, column=2, padx=4)
        r = len(self.FIELDS)
        ttk.Label(self, text="Motion Engine").grid(row=r, column=0, sticky="w", padx=8, pady=3)
        self.engine = tk.StringVar(value=self.data["heygen"]["motion_engine"])
        ttk.Combobox(self, textvariable=self.engine, values=["Avatar III", "Avatar IV", "Avatar V"],
                     width=14, state="readonly").grid(row=r, column=1, sticky="w", padx=8)
        self.auto = tk.BooleanVar(value=bool(self.data["heygen"]["otomatik_submit"]))
        ttk.Checkbutton(self, text="HeyGen'de Submit'e otomasyon bassın (Avatar III kredi harcamıyor)",
                        variable=self.auto).grid(row=r + 1, column=1, sticky="w", padx=8, pady=3)
        ttk.Button(self, text="Kaydet", command=self._save).grid(row=r + 2, column=1, sticky="e", padx=8, pady=8)
        self.columnconfigure(1, weight=1)

    def _get(self, key):
        d = self.data
        for k in key.split("."):
            d = d[k]
        return d

    def _set(self, key, value):
        d = self.data
        *path, last = key.split(".")
        for k in path:
            d = d[k]
        d[last] = value

    def _pick_dir(self):
        d = filedialog.askdirectory(title="Ana klasörü seç", parent=self)
        if d:
            self.vars["ana_klasor"].set(d)

    def _save(self):
        for key, v in self.vars.items():
            self._set(key, v.get().strip())
        self.data["heygen"]["motion_engine"] = self.engine.get()
        self.data["heygen"]["otomatik_submit"] = self.auto.get()
        settings.save(self.data)
        messagebox.showinfo("Ayarlar", f"Kaydedildi: {settings.SETTINGS_FILE}", parent=self)
        self.destroy()


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

        top = ttk.LabelFrame(self, text="Kaynak klasör (ör. Videolar/vid12)")
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
        ttk.Label(fin, text="Ana pencerede proje klasörü (render proje klasörü) seçili olmalı",
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
        initial = settings.base_dir() if settings.base_dir().exists() else Path.home()
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
        info = ("Claude Code + Chrome ile: claude.ai sohbetinden 3 fikir → senin seçimin → paket ve script → "
                "HeyGen avatarı → harita → kontrol. Ayarlar kullanıcıya özeldir (sohbet linki, avatar, klasör).")
        ttk.Label(tab, text=info, foreground="#888", wraplength=700, justify="left")\
            .grid(row=0, column=0, columnspan=2, sticky="w", padx=8, pady=(8, 4))
        rows = [
            ("Claude Code ile hikâye üret (/hikaye)", self.launch_claude_code,
             "Claude aboneliğinle çalışır; API ücreti yok (opsiyonel)"),
            ("Ayarlar…", self.open_settings, "Ana klasör, claude.ai sohbeti, mesajlar, HeyGen avatarı"),
            ("Avatar videosunu seç (elle)", self.choose_avatar_video, "HeyGen'den indirdiğin video → avatar.mp4"),
            ("Haritayı kontrol et", self.check_map, "Süre avatarla tutuyor mu, eksik prompt var mı"),
        ]
        for i, (text, cmd, hint) in enumerate(rows, start=1):
            ttk.Button(tab, text=text, command=cmd).grid(row=i, column=0, sticky="w", padx=8, pady=3)
            ttk.Label(tab, text=hint, foreground="#888").grid(row=i, column=1, sticky="w", padx=4)
        tab.columnconfigure(1, weight=1)

    def launch_claude_code(self):
        import shutil
        import subprocess
        app_dir = str(settings.APP_DIR)
        claude = shutil.which("claude")
        if claude and IS_MAC:
            cmd = f"cd {shlex_quote(app_dir)} && claude '/hikaye'"
            subprocess.run(["osascript", "-e", f'tell application "Terminal" to do script "{cmd}"',
                            "-e", 'tell application "Terminal" to activate'])
            self.log("Claude Code Terminal'de /hikaye ile başlatıldı. Chrome bağlı değilse orada /chrome yaz.")
        elif claude and IS_WINDOWS:
            subprocess.Popen(["cmd", "/c", "start", "cmd", "/k", f'cd /d "{app_dir}" && claude "/hikaye"'])
            self.log("Claude Code yeni pencerede /hikaye ile başlatıldı.")
        else:
            self._to_clipboard("/hikaye", "/hikaye komutu")
            messagebox.showinfo(
                "Claude Code",
                "Claude Code'u bu klasörde aç:\n\n" + app_dir +
                "\n\nSonra sohbete /hikaye yaz (panoya kopyalandı). VS Code eklentisinde Chrome için "
                "mesaja @browser ekle.\n\nClaude Code kurulu değilse: claude.com/claude-code", parent=self)

    def open_settings(self):
        SettingsDialog(self)

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

    def check_map(self):
        if not self._need_dir():
            return
        try:
            md = flow_tools.find_map(self.vid_dir)
        except FileNotFoundError as e:
            messagebox.showwarning("Harita yok", str(e), parent=self)
            return
        summary, problems = story_tools.validate_map(md, story_tools.avatar_seconds(self.vid_dir))
        if summary:
            self.log(f"Harita ({md.name}): {summary}")
        if problems:
            for pr in problems:
                self.log(f"❌ {pr}")
            messagebox.showwarning("Haritada sorun var", "\n\n".join("• " + x for x in problems), parent=self)
        else:
            self.log("✅ Harita hazır — Flow sekmesine geçebilirsin.")

    def send_to_project(self):
        if not self._need_dir():
            return
        if self.app.project_dir is None:
            messagebox.showwarning("Proje seçilmedi", "Ana pencerede önce render proje klasörünü (render proje klasörü) seç.",
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
