# Günlük üretim talimatı

Bu dosya, her sabah çalışan otomatik görevin (Claude) adım adım ne yapacağını tanımlar.
Amaç: her gün **bir** kaliteli, doğruluğu kontrol edilmiş, 35-55 saniyelik Türkçe bilgi videosu.

## 1. Hazırlık
```bash
cd PP && git pull && ./kurulum.sh
```

## 2. Konu ve araştırma
- `takvim/konular.md` içindeki ilk işaretsiz konuyu al.
- Her bilgi için **en az iki güvenilir kaynak** bul (NASA, NOAA, USGS, üniversiteler,
  Smithsonian, National Geographic, hakemli makaleler). Kaynaklar çelişiyorsa o bilgiyi kullanma
  ya da çekinceli ifade et ("yaklaşık", "-ı geçebilir").
- Tıklama tuzağı yalan yok: başlıkta vaat edilen şey videoda gerçekten olmalı.
- Aynı bilgiyi önceki videolarda kullanmadığını `icerikler/` klasöründen kontrol et.

## 3. İçerik dosyası
`icerikler/NNN-kisa-ad.json` dosyasını `001-saskin-gercekler.json` biçiminde yaz:
- 1 kanca (`hook`) + 4-5 madde + 1 kapanış. Toplam 35-45 sn, `"hiz": 1.12`.
- **Kanca**: ilk cümle listedeki en çarpıcı bilgiyi söyler ("Bir bulut yaklaşık yüz fil kadar ağır
  olabilir!"), karşılığı videonun sonunda verilir; izleyici sonuna kadar kalır. Kanca görseli olarak
  `denklem` (["☁️", "=", "🐘", "×100"]) ve `emojiler` kullan, üstte `rozet` ("5 ŞAŞIRTICI GERÇEK").
- **Döngü**: `"dongu": true`. Kapanışın son cümlesi kancanın ilk cümlesine bağlansın
  ("... ve unutma:" → "Bir bulut, yüz fil kadar ağır olabilir!"). Kapanış rengi = kanca rengi.
- Her maddenin ilk cümlesi başlığı söylesin; dolgu kelimeleri at, cümleler kısa olsun.
- `kapak` alanını doldur: `baslik` (ör. "5 *ŞAŞIRTICI* GERÇEK"), `alt` (kancadaki merak sorusu), `emojiler`.
- Her maddeye görsel ritim ekle: cümle başına bir `gorseller` adımı (emoji, `sayac`,
  `karsilastirma`, `gezegen`). Sayısal bilgilerde sayaç/karşılaştırma kullan.
- Ekranda farklı, okunuşta farklı ifadeler için `{25 cm|yirmi beş santimetre}` kullan.
- Başlıkta vurgu: `*kelime*`. Sayılar otomatik vurgulanır.
- Her sahneye konuya uygun koyu + canlı renk çifti (`renk`).
- `kaynaklar` ve `paylasim` alanlarını doldur. YouTube başlığı ≤ 90 karakter, sonunda `#shorts`.
- Seriler arasında çeşitlilik: format, renk paleti, müzik ruh hali (`merak`, `umut`, `gizem`).

## 4. Üretim ve kalite kontrol
```bash
python3 motor/uret.py icerikler/NNN-kisa-ad.json --kareler   # sahne kareleri
```
Kareleri incele: taşan/çakışan yazı, okunmayan altyazı, yanlış emoji varsa düzelt. Sonra:
```bash
python3 motor/uret.py icerikler/NNN-kisa-ad.json
```
Kontrol: süre 30-59 sn, `ffprobe` ile 1080x1920 / 30 fps / AAC, ses -14 LUFS civarı.
`kapak.jpg` dosyasına da bak: başlık okunuyor mu, emojiler doğru mu.

## 5. Yayın
- İlk yayında `python3 yayin/yayinla.py --kontrol` çıktısındaki kuralları oku; TikTok şemasında
  yapay zekâ etiketi alanı varsa (ör. `is_aigc`) `yayin/ayarlar.json` içinde `true` yap
  (seslendirme sentetik olduğu için).
- `POSTIZ_API_KEY` tanımlıysa:
  `python3 yayin/yayinla.py cikti/NNN-kisa-ad --saat 19:00` (onay modu açıksa `--taslak` ekle).
- Tanımlı değilse: videoyu ve `paylasim.md` metnini kullanıcıya gönder; kullanıcı elle paylaşır.

## 6. Kayıt
- `takvim/konular.md` içinde konuyu `[x]` ile işaretle, numarasını yaz.
- `git add icerikler takvim yayin/gunluk.jsonl && git commit && git push`.
- Kullanıcıya kısa bir özet gönder: başlık, yayın saati, platformlar ve video.

## Haftalık (pazartesi)
- Postiz analitiği (`postiz analytics:platform <id> -d 7`) ile en çok izlenen ve en hızlı
  terk edilen videolara bak; kanca, süre ve konu seçimini buna göre ayarla.
