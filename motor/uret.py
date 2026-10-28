#!/usr/bin/env python3
"""İçerik dosyasından (icerikler/*.json) yayına hazır dikey video üretir.

Kullanım:
  python3 motor/uret.py icerikler/001-saskin-gercekler.json
  python3 motor/uret.py icerikler/001-saskin-gercekler.json --kareler   # sadece kontrol kareleri
Çıktı: cikti/<id>/video.mp4, kapak.jpg, paylasim.md, yayin.json
"""
import argparse
import json
import os
import subprocess
import sys

import numpy as np
import soundfile as sf

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import muzik  # noqa: E402
import ses  # noqa: E402

KOK = ses.KOK
SR = ses.SR
FPS = 30

ILK_BOSLUK = 0.30     # videonun başında ilk kelimeden önce
CUMLE_ARASI = 0.20
SAHNE_SONU = 0.38
SAHNE_GIRIS = 0.14    # kesmeden sonra görüntü sesten biraz önce gelir
MIN_SURE = {"hook": 2.6, "madde": 3.5, "kapanis": 3.2}


def calistir(komut):
    sonuc = subprocess.run(komut, capture_output=True, text=True)
    if sonuc.returncode != 0:
        raise SystemExit(f"Komut başarısız: {' '.join(komut)}\n{sonuc.stderr[-2000:]}")
    return sonuc


def altyaziya_bol(kelimeler):
    """Kelimeleri ekranda birlikte görünecek 1-3 kelimelik gruplara ayırır."""
    gruplar, grup = [], []
    for k in kelimeler:
        if grup and len(" ".join(x["g"] for x in grup + [k])) > 18:
            gruplar.append(grup)
            grup = []
        grup.append(k)
        if k["durak"] > 0 or len(grup) >= 3:
            gruplar.append(grup)
            grup = []
    if grup:
        gruplar.append(grup)
    sonuc = []
    for i, g in enumerate(gruplar):
        bas = g[0]["b"] - 0.04
        son = g[-1]["s"] + 0.25
        if i + 1 < len(gruplar):
            son = min(son if g[-1]["durak"] else 99, gruplar[i + 1][0]["b"] - 0.02)
            son = max(son, g[-1]["s"])
        sonuc.append({"b": round(bas, 3), "s": round(son, 3),
                      "k": [{"g": k["g"], "b": round(k["b"], 3), "s": round(k["s"], 3)} for k in g]})
    return sonuc


def zaman_cizelgesi(icerik, motor):
    """Seslendirir ve her sahnenin/kelimenin zamanını hesaplar."""
    t = ILK_BOSLUK
    sahneler, ses_parcalari, olaylar, tum_kelimeler = [], [], [], []
    toplam_madde = sum(1 for s in icerik["sahneler"] if s["tur"] == "madde")
    madde_no = 0
    for sahne in icerik["sahneler"]:
        if sahneler:
            bas = t
            t += SAHNE_GIRIS
        else:
            bas = 0.0
        cumle_baslari = []
        for cumle in ses.cumlelere_bol(sahne["anlatim"]):
            kelimeler = ses.kelimelere_bol(cumle)
            okunacak = " ".join(k["soyle"] for k in kelimeler)
            x = ses.kirp(ses.sentezle_onbellekli(motor, okunacak))
            for k, (kb, ks) in zip(kelimeler, ses.kelime_zamanlari(kelimeler, x)):
                k["b"], k["s"] = t + kb, t + ks
            cumle_baslari.append(t)
            ses_parcalari.append((t, x))
            tum_kelimeler.extend(kelimeler)
            t += len(x) / SR + CUMLE_ARASI
        t += SAHNE_SONU - CUMLE_ARASI
        t = max(t, bas + MIN_SURE[sahne["tur"]])
        kayit = {k: v for k, v in sahne.items() if k not in ("anlatim",)}
        kayit.update({"bas": round(bas, 3), "sure": round(t - bas, 3)})
        if sahne["tur"] == "madde":
            kayit["no"], kayit["toplam"] = madde_no, toplam_madde
            madde_no += 1
            gorseller = sahne.get("gorseller") or [{"cumle": 0, "emoji": sahne.get("emoji", "✨")}]
            for g in gorseller:
                ci = min(g.get("cumle", 0), len(cumle_baslari) - 1)
                g["b"] = round(max(bas, cumle_baslari[ci] - 0.12) - bas, 3)
                olaylar.append({"tur": "pop", "t": bas + g["b"] + 0.05})
            kayit["gorseller"] = gorseller
        if bas > 0:
            olaylar.append({"tur": "whoosh", "t": bas - 0.32})
        if sahne["tur"] == "kapanis":
            olaylar.append({"tur": "zil", "t": bas + 0.15})
        sahneler.append(kayit)
    olaylar.append({"tur": "darbe", "t": 0.02})
    sure = round(t + 0.25, 3)
    return {"fps": FPS, "sure": sure, "seri": icerik.get("seri", ""),
            "kullanici": icerik.get("kullanici", ""), "sahneler": sahneler,
            "altyazi": altyaziya_bol(tum_kelimeler)}, ses_parcalari, olaylar


def ses_miksi(cizelge, ses_parcalari, olaylar, icerik, klasor):
    sure = cizelge["sure"]
    n = int(sure * SR)
    konusma = np.zeros(n, dtype=np.float32)
    for t, x in ses_parcalari:
        i = int(t * SR)
        konusma[i:i + len(x)] += x[: n - i]
    ham = os.path.join(klasor, "konusma_ham.wav")
    islenmis = os.path.join(klasor, "konusma.wav")
    sf.write(ham, konusma / (np.abs(konusma).max() + 1e-9) * 0.7, SR)
    # Konuşma zinciri: uğultu kesme, sıcaklık, netlik, sibilans kontrolü, sıkıştırma.
    calistir(["ffmpeg", "-y", "-loglevel", "error", "-i", ham, "-af",
              "highpass=f=75,equalizer=f=200:t=q:w=1.2:g=1.5,equalizer=f=3200:t=q:w=1.0:g=2.5,"
              "equalizer=f=7000:t=q:w=1.5:g=1.5,deesser=i=0.35,"
              "acompressor=threshold=-20dB:ratio=3:attack=4:release=70:makeup=3,alimiter=limit=0.95",
              "-ar", str(SR), "-ac", "1", islenmis])
    konusma, _ = sf.read(islenmis, dtype="float32")
    konusma = np.pad(konusma, (0, max(0, n - len(konusma))))[:n]
    konusma *= 0.125 / (np.sqrt(np.mean(konusma[np.abs(konusma) > 0.01] ** 2)) + 1e-9)

    # Konuşma varken müziği kıs (ducking).
    pencere = int(0.02 * SR)
    m = n // pencere
    rms = np.sqrt(np.mean(konusma[: m * pencere].reshape(m, pencere) ** 2, axis=1) + 1e-12)
    aktif = np.clip((20 * np.log10(rms) + 50) / 20, 0, 1)
    duz = np.zeros_like(aktif)
    for i in range(m):
        onceki = duz[i - 1] if i else 0
        katsayi = 0.6 if aktif[i] > onceki else 0.06
        duz[i] = onceki + katsayi * (aktif[i] - onceki)
    kazanc = np.interp(np.arange(n), np.arange(m) * pencere + pencere / 2, 1 - 0.62 * duz)

    fon = muzik.fon_muzigi(sure, icerik.get("muzik", {}).get("ruh_hali", "merak"),
                           icerik.get("muzik", {}).get("bpm", 88))
    fon *= icerik.get("muzik", {}).get("seviye", 1.0)
    efekt = muzik.efekt_izi(olaylar, sure)
    mix = konusma[:, None] + fon * kazanc[:, None] + efekt
    mix = np.tanh(mix * 1.1) / 1.1
    karisik = os.path.join(klasor, "mix.wav")
    sf.write(karisik, mix, SR, subtype="FLOAT")

    # Platformların beklediği ses yüksekliği: -14 LUFS, tepe -1.5 dBTP (iki geçişli).
    olcum = calistir(["ffmpeg", "-hide_banner", "-i", karisik, "-af",
                      "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"]).stderr
    o = json.loads(olcum[olcum.rindex("{"):olcum.rindex("}") + 1])
    son = os.path.join(klasor, "ses.wav")
    calistir(["ffmpeg", "-y", "-loglevel", "error", "-i", karisik, "-af",
              f"loudnorm=I=-14:TP=-1.5:LRA=11:measured_I={o['input_i']}:measured_TP={o['input_tp']}:"
              f"measured_LRA={o['input_lra']}:measured_thresh={o['input_thresh']}:"
              f"offset={o['target_offset']}:linear=true",
              "-ar", str(SR), "-ac", "2", son])
    for gecici in (ham, islenmis, karisik):
        os.remove(gecici)
    return son


def render(cizelge_yolu, cikti, *ek):
    calistir(["node", os.path.join(KOK, "motor", "render.js"), cizelge_yolu, cikti, *ek])


def paylasim_metinleri(icerik, klasor):
    p = icerik["paylasim"]
    etiket = " ".join(p.get("etiketler", []))
    kaynak = ""
    if icerik.get("kaynaklar"):
        kaynak = "\n\nKaynaklar: " + "; ".join(icerik["kaynaklar"])
    yayin = {
        "youtube": {"baslik": p["youtube_baslik"],
                    "aciklama": p["aciklama"] + kaynak + "\n\n" + etiket + " #shorts",
                    "etiketler": [e.lstrip("#") for e in p.get("etiketler", [])]},
        "instagram": {"aciklama": p["aciklama"] + "\n\n" + etiket},
        "tiktok": {"aciklama": p.get("tiktok_aciklama", p["aciklama"]) + "\n\n" + etiket},
    }
    with open(os.path.join(klasor, "yayin.json"), "w", encoding="utf-8") as f:
        json.dump(yayin, f, ensure_ascii=False, indent=2)
    with open(os.path.join(klasor, "paylasim.md"), "w", encoding="utf-8") as f:
        f.write(f"# {icerik['id']}\n\n## YouTube Shorts\n**Başlık:** {yayin['youtube']['baslik']}\n\n"
                f"**Açıklama:**\n{yayin['youtube']['aciklama']}\n\n## Instagram Reels\n"
                f"{yayin['instagram']['aciklama']}\n\n## TikTok\n{yayin['tiktok']['aciklama']}\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("icerik")
    ap.add_argument("--kareler", action="store_true", help="video yerine kontrol kareleri üret")
    a = ap.parse_args()
    with open(a.icerik, encoding="utf-8") as f:
        icerik = json.load(f)
    klasor = os.path.join(KOK, "cikti", icerik["id"])
    os.makedirs(klasor, exist_ok=True)

    print("1/5 Seslendirme ve zamanlama...")
    motor = ses.motor_sec(icerik.get("ses"))
    cizelge, ses_parcalari, olaylar = zaman_cizelgesi(icerik, motor)
    cizelge_yolu = os.path.join(klasor, "cizelge.json")
    with open(cizelge_yolu, "w", encoding="utf-8") as f:
        json.dump(cizelge, f, ensure_ascii=False, indent=1)
    print(f"    süre: {cizelge['sure']:.1f} sn, {len(cizelge['altyazi'])} altyazı grubu")

    if a.kareler:
        zamanlar = [str(round(s["bas"] + min(s["sure"] - 0.4, 2.2), 2)) for s in cizelge["sahneler"]]
        render(cizelge_yolu, os.path.join(klasor, "kare"), "--kareler", *zamanlar)
        print("Kontrol kareleri:", klasor)
        return

    print("2/5 Müzik, efekt ve miks (-14 LUFS)...")
    ses_yolu = ses_miksi(cizelge, ses_parcalari, olaylar, icerik, klasor)
    print("3/5 Görüntü render (1080x1920, 30 fps)...")
    sessiz = os.path.join(klasor, "goruntu.mp4")
    render(cizelge_yolu, sessiz)
    print("4/5 Birleştirme...")
    video = os.path.join(klasor, "video.mp4")
    calistir(["ffmpeg", "-y", "-loglevel", "error", "-i", sessiz, "-i", ses_yolu, "-map", "0:v", "-map", "1:a",
              "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", str(SR), "-shortest",
              "-movflags", "+faststart", video])
    os.remove(sessiz)
    os.remove(ses_yolu)
    print("5/5 Kapak ve paylaşım metinleri...")
    kapak_t = cizelge["sahneler"][0]["bas"] + min(1.6, cizelge["sahneler"][0]["sure"] - 0.4)
    render(cizelge_yolu, os.path.join(klasor, "kapak"), "--kareler", str(round(kapak_t, 2)))
    os.replace(os.path.join(klasor, f"kapak-{round(kapak_t, 2)}.jpg"), os.path.join(klasor, "kapak.jpg"))
    paylasim_metinleri(icerik, klasor)
    print("Hazır:", video)


if __name__ == "__main__":
    main()
