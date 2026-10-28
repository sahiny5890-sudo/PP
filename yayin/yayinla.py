#!/usr/bin/env python3
"""Hazır videoyu Postiz üzerinden YouTube Shorts, Instagram Reels ve TikTok'a zamanlar.

Kullanım:
  python3 yayin/yayinla.py --kontrol
      Postiz girişini, bağlı hesapları ve her platformun güncel kurallarını gösterir.
  python3 yayin/yayinla.py cikti/001-saskin-gercekler --saat 19:00 [--gun 2026-10-29] [--taslak]
      Videoyu yükler ve seçilen gün/saatte (Türkiye saati) üç platforma birden zamanlar.
      --taslak: yayınlamaz, Postiz'de onayını bekleyen taslak oluşturur.

Gerekenler: `postiz` CLI (kurulum.sh kurar), POSTIZ_API_KEY ortam değişkeni ve
Postiz panelinde bağlanmış YouTube / Instagram / TikTok hesapları.
Platforma özel ayarlar yayin/ayarlar.json dosyasından okunur.
"""
import argparse
import datetime as dt
import json
import os
import subprocess
import sys
from zoneinfo import ZoneInfo

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TR = ZoneInfo("Europe/Istanbul")
PLATFORM_KIMLIKLERI = {
    "youtube": ("youtube",),
    "instagram": ("instagram", "instagram-standalone"),
    "tiktok": ("tiktok",),
}


def postiz(*arg):
    sonuc = subprocess.run(["postiz", *arg], capture_output=True, text=True)
    if sonuc.returncode != 0:
        raise SystemExit(f"postiz {' '.join(arg[:2])} başarısız:\n{sonuc.stdout}\n{sonuc.stderr}")
    cikti = sonuc.stdout
    # CLI bazen JSON'dan önce bir başlık satırı yazar.
    bas = min([i for i in (cikti.find("["), cikti.find("{")) if i >= 0], default=-1)
    return json.loads(cikti[bas:]) if bas >= 0 else cikti


def hesaplar():
    bulunan = {}
    for h in postiz("integrations:list"):
        for platform, kimlikler in PLATFORM_KIMLIKLERI.items():
            if h.get("identifier") in kimlikler and not h.get("disabled") and platform not in bulunan:
                bulunan[platform] = h
    return bulunan


def kontrol():
    print(subprocess.run(["postiz", "auth:status"], capture_output=True, text=True).stdout)
    for platform, h in hesaplar().items():
        print(f"\n=== {platform}: {h.get('name')} ({h['id']})")
        ayar = postiz("integrations:settings", h["id"])
        cikti = ayar.get("output", ayar) if isinstance(ayar, dict) else ayar
        print("Kurallar:", json.dumps(cikti.get("rules"), ensure_ascii=False, indent=1) if isinstance(cikti, dict) else cikti)
        if isinstance(cikti, dict):
            print("Ayar şeması:", json.dumps(cikti.get("settings"), ensure_ascii=False)[:3000])
    eksik = set(PLATFORM_KIMLIKLERI) - set(hesaplar())
    if eksik:
        print("\nPostiz'de bağlı olmayan platformlar:", ", ".join(sorted(eksik)))


def zamanla(klasor, gun, saat, taslak, platformlar):
    with open(os.path.join(klasor, "yayin.json"), encoding="utf-8") as f:
        metin = json.load(f)
    with open(os.path.join(KOK, "yayin", "ayarlar.json"), encoding="utf-8") as f:
        ayarlar = json.load(f)
    yerel = dt.datetime.fromisoformat(f"{gun}T{saat}").replace(tzinfo=TR)
    if yerel < dt.datetime.now(TR) + dt.timedelta(minutes=10):
        raise SystemExit(f"Yayın zamanı geçmişte ya da çok yakın: {yerel}")
    utc = yerel.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    bagli = hesaplar()
    yuklenen = postiz("upload", os.path.join(klasor, "video.mp4"))["path"]
    gunluk = []
    for platform in platformlar:
        if platform not in bagli:
            print(f"! {platform} Postiz'de bağlı değil, atlandı.")
            continue
        ayar = dict(ayarlar.get(platform, {}))
        if platform == "youtube":
            ayar["title"] = metin["youtube"]["baslik"][:100]
            ayar["tags"] = [{"value": e, "label": e} for e in metin["youtube"]["etiketler"][:15]]
        icerik = metin[platform]["aciklama"]
        arg = ["posts:create", "-c", icerik, "-s", utc, "-m", yuklenen,
               "--settings", json.dumps(ayar, ensure_ascii=False), "-i", bagli[platform]["id"]]
        if taslak:
            arg += ["-t", "draft"]
        sonuc = postiz(*arg)
        print(f"✓ {platform}: {'taslak' if taslak else 'zamanlandı'} → {yerel:%d.%m.%Y %H:%M} (TR)")
        gunluk.append({"platform": platform, "zaman": utc, "taslak": taslak, "sonuc": sonuc})
    with open(os.path.join(KOK, "yayin", "gunluk.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps({"video": os.path.basename(klasor.rstrip("/")), "kayitlar": gunluk},
                           ensure_ascii=False) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("klasor", nargs="?")
    ap.add_argument("--kontrol", action="store_true")
    ap.add_argument("--gun", default=dt.datetime.now(TR).strftime("%Y-%m-%d"))
    ap.add_argument("--saat", default="19:00")
    ap.add_argument("--taslak", action="store_true")
    ap.add_argument("--platformlar", default="youtube,instagram,tiktok")
    a = ap.parse_args()
    if not os.environ.get("POSTIZ_API_KEY") and not os.path.exists(os.path.expanduser("~/.postiz/credentials.json")):
        sys.exit("POSTIZ_API_KEY tanımlı değil. README'deki 'Kurulum' adımlarına bak.")
    if a.kontrol:
        return kontrol()
    if not a.klasor:
        ap.error("video klasörü gerekli")
    zamanla(a.klasor, a.gun, a.saat, a.taslak, a.platformlar.split(","))


if __name__ == "__main__":
    main()
