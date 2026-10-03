// Flow Oto-Devam: Google Flow ajan modunda her part bitince otomatik onay verir.
// Sayfanin sag altinda kucuk bir durum paneli acar (Durdur dugmesiyle).
// Tarayicinin icinde calisir; Claude/API kullanmaz.
(() => {
  if (window.__flowOto) { window.__flowOto.stop("Yeniden başlatıldı"); window.__flowOto.panel?.remove(); }

  const CFG = {
    devamMesaji: "Onaylıyorum, sıradaki partı oluştur. Her görselin adı Görsel #numara olsun. Partı bitirince yine onayımı bekle.",
    tekrarMesaji: "Bu partta başarısız olan görsel(ler) var. Başarısız olanları aynı numara ve aynı adla (Görsel #numara) yeniden üret, sonra onayımı bekle.",
    kontrolAraligiMs: 5000,   // her 5 saniyede bir bak
    sakinKontrol: 3,          // ajan 3 kontrol ust uste bostaysa (15 sn) part bitmis say
    partBasinaMaxTekrar: 2,   // bir partta en fazla 2 kez "basarisizlari yeniden uret" de
    maxHataTekrar: 3,         // ajan "Bir hata oluştu" derse ust uste en fazla 3 kez "Tekrar dene"ye bas
    maxMesaj: 60,             // guvenlik: toplamda en fazla bu kadar mesaj gonder
    // Flow video uretiminden once "X kredi karsiliginda ... Onayla / Reddet" diye sorar.
    // false: durup kullanicinin "Onayla"ya basmasini bekler (kullanici basinca devam eder).
    // true : "Onayla"ya kendisi basar (kredi harcar).
    krediOnayiOtomatik: false,
    maxKrediOnayi: 10,        // otomatik modda en fazla bu kadar kredi onayi ver
  };
  // Video asamasi gibi farkli kullanimlar icin mesajlar disaridan degistirilebilir:
  //   window.FLOW_OTO_CFG = { devamMesaji: "...", tekrarMesaji: "..." }
  Object.assign(CFG, window.FLOW_OTO_CFG || {});

  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const sleep = ms => new Promise(r => setTimeout(r, ms));

  // ---- durum paneli ----
  const panel = document.createElement("div");
  panel.style.cssText = "position:fixed;left:16px;bottom:16px;z-index:2147483647;background:#1f1f1f;color:#eee;" +
    "font:13px/1.4 system-ui,sans-serif;padding:10px 12px;border-radius:10px;border:1px solid #444;max-width:340px;box-shadow:0 4px 18px #0008";
  // Flow, TrustedHTML zorunlu kildigi icin innerHTML kullanilamaz; ogeler tek tek olusturulur.
  const el = (tag, css, text) => { const e = document.createElement(tag); if (css) e.style.cssText = css; if (text) e.textContent = text; return e; };
  const title = el("b", "", "Flow Oto-Devam ");
  const dot = el("span", "", "●");
  const msgEl = el("div", "margin:6px 0", "Başlıyor…");
  const infoEl = el("div", "color:#aaa;font-size:12px");
  const stopBtn = el("button", "margin-top:8px;background:#b3261e;color:#fff;border:0;border-radius:6px;padding:4px 10px;cursor:pointer", "Durdur");
  panel.append(title, dot, msgEl, infoEl, stopBtn);
  document.body.appendChild(panel);
  const setMsg = (t, color = "#4caf50") => { msgEl.textContent = t; dot.style.color = color; };
  const setInfo = t => { infoEl.textContent = t; };

  // ---- sayfa durumunu okuma ----
  const rows = () => $$(".messages-list .message-row");
  const lastRow = () => rows().at(-1);
  const sendBtn = () => $('button[aria-label="Oluşturmaya başla"]');
  const editor = () => $$(".ProseMirror").find(e => e.offsetParent);
  const mainText = () => ($("main")?.innerText || "");

  const failedCount = () => (mainText().match(/Maalesef bu \S+ üretilemedi/g) || []).length; // görüntü / video
  // Politika reddi (ör. "tanınmış kişilerle ilgili içerik") yeniden denenmez; sadece bildirilir.
  const policyCount = () => (mainText().match(/politikalarımızı ihlal/g) || []).length;
  // Sadece gorsel kartlarinin etiketleri ("Görsel #12" yazan tek basina ogeler) sayilir;
  // sohbetteki "Görsel #8–#21" gibi metinler sayilmaz. Flow ekran disindaki kartlari
  // sayfadan kaldirdigi (sanal kaydirma) icin gorulen numaralar zamanla biriktirilir;
  // bu sayi yaklasiktir, kesin kontrol indirmeden sonra check_assets.py ile yapilir.
  const seen = new Set();
  const imageNumbers = () => {
    for (const e of $$("main *")) {
      if (e.children.length) continue;
      const m = (e.textContent || "").trim().match(/^Görsel #(\d+)$/);
      if (m) seen.add(+m[1]);
    }
    return seen;
  };

  function isBusy() {
    const btn = sendBtn();
    if (!btn) return true;                                    // gonder dugmesi yoksa (yeniden ciziliyor) bekle
    if (/stop/.test(btn.innerText)) return true;              // ajan calisiyor: dugme "durdur" simgesinde
    if (/Düşünüyorum/.test(mainText())) return true;
    if ($$("main *").some(e => e.children.length === 0 && /^%\s?\d{1,3}$|^\d{1,3}\s?%$/.test((e.textContent || "").trim()))) return true; // uretim yuzdesi
    const last = lastRow();
    if (!last || !last.classList.contains("agent-row")) return true; // son mesaj ajanin degilse cevap bekleniyor
    return false;
  }

  async function send(text) {
    const before = rows().length;
    const ed = editor();
    if (!ed) return false;
    ed.focus();
    document.execCommand("selectAll");
    document.execCommand("insertText", false, text);
    for (let i = 0; i < 10 && rows().length === before; i++) {
      await sleep(700);
      if (rows().length > before) break;                     // mesaj zaten gitti
      const btn = sendBtn();
      if (btn && !btn.disabled && i === 1) btn.click();
    }
    return rows().length > before;
  }

  // ---- ana dongu ----
  let errorRetries = 0, creditApprovals = 0;
  let running = true, calm = 0, sent = 0, retriesThisPart = 0, failedBaseline = failedCount(), parts = 0;
  const api = window.__flowOto = {
    panel,
    stop(reason = "Durduruldu") { running = false; setMsg(reason, "#e53935"); stopBtn.textContent = "Kapat"; stopBtn.onclick = () => panel.remove(); },
  };
  stopBtn.onclick = () => api.stop();

  (async () => {
    while (running) {
      const nums = imageNumbers();
      const max = nums.size ? Math.max(...nums) : 0;
      const pol = policyCount();
      setInfo(`Görülen görsel: ${nums.size} (en büyük #${max}) • gönderilen onay: ${sent}` +
              (pol ? ` • ⚠️ politika nedeniyle reddedilen: ${pol}` : ""));

      if (isBusy()) { calm = 0; setMsg("Ajan çalışıyor, bekleniyor…", "#fbc02d"); await sleep(CFG.kontrolAraligiMs); continue; }
      calm++;
      if (calm < CFG.sakinKontrol) { setMsg(`Ajan durdu, emin olunuyor (${calm}/${CFG.sakinKontrol})…`, "#fbc02d"); await sleep(CFG.kontrolAraligiMs); continue; }

      const lastText = lastRow().innerText;
      const failedNow = failedCount();

      // Kredi onayi: son ajan mesajinda "Onayla" dugmesi varsa yaziyla cevap verilmez
      // (Flow'da bu secenekler <button> degil, role="radio" olan .option-row ogeleri)
      const approveBtn = $$('[role="radio"], button', lastRow()).find(b => /^\s*(check\s*)?Onayla\s*$/.test(b.innerText));
      if (approveBtn) {
        const soru = lastText.split("\n")[0].slice(0, 120);
        if (CFG.krediOnayiOtomatik && creditApprovals < CFG.maxKrediOnayi) {
          setMsg(`Kredi onayı veriliyor: ${soru}`, "#fb8c00");
          approveBtn.click(); creditApprovals++;
        } else {
          setMsg(`Kredi onayı bekleniyor — Flow'da "Onayla"ya sen bas, sonra devam ederim. (${soru})`, "#42a5f5");
          calm = 0; await sleep(CFG.kontrolAraligiMs); continue;
        }
      } else if (/Bir hata oluştu/.test(lastText)) {
        // Flow ajaninin kendi hatasi: mesajin altindaki "Tekrar dene" dugmesine bas
        const retryBtn = $$("button", lastRow()).find(b => /Tekrar dene/.test(b.innerText));
        if (errorRetries < CFG.maxHataTekrar && retryBtn) {
          setMsg(`Flow hata verdi, tekrar deneniyor (${errorRetries + 1}/${CFG.maxHataTekrar})…`, "#fb8c00");
          retryBtn.click(); errorRetries++;
        } else if (errorRetries < CFG.maxHataTekrar && await send(CFG.devamMesaji)) {
          setMsg("Flow hata verdi, devam mesajı yeniden gönderildi…", "#fb8c00"); errorRetries++; sent++;
        } else {
          api.stop("Flow üst üste hata verdi. Sayfayı kontrol et."); break;
        }
      } else if (failedNow > failedBaseline && retriesThisPart < CFG.partBasinaMaxTekrar) {
        setMsg("Başarısız görsel var, yeniden ürettiriliyor…", "#fb8c00");
        if (await send(CFG.tekrarMesaji)) { sent++; retriesThisPart++; failedBaseline = failedNow; }
      } else if (/onay|bekliyorum|devam edeyim|devam etmemi|geçeyim|geçmemi|ister misiniz/i.test(lastText)) {
        setMsg("Part bitti, onay veriliyor…");
        if (await send(CFG.devamMesaji)) { sent++; parts++; retriesThisPart = 0; errorRetries = 0; failedBaseline = failedCount(); }
      } else {
        api.stop(`Bitti: ajan artık onay istemiyor. En büyük görsel #${max}. ` +
                 (pol ? `⚠️ ${pol} üretim Flow politikası nedeniyle reddedildi, bunları elle yenilemen gerekir. ` : "") +
                 "İndirip kontrol etmeyi unutma.");
        break;
      }
      if (sent >= CFG.maxMesaj) { api.stop("Güvenlik sınırına ulaşıldı (çok fazla mesaj). Kontrol et."); break; }
      calm = 0;
      await sleep(CFG.kontrolAraligiMs * 2);
    }
  })();
})();
