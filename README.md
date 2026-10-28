# İçerik Fabrikası

Her gün otomatik olarak Türkçe bilgi videosu (YouTube Shorts / Instagram Reels / TikTok)
üreten ve zamanlayan sistem. CapCut'ta elle yapılan her adım burada kodla yapılır:

| Adım | Ne yapıyor |
|---|---|
| Senaryo | Claude konuyu araştırır, her bilgiyi en az iki kaynakla doğrular |
| Seslendirme | Türkçe sinir ağı sesi (ücretsiz Piper; istenirse Azure / ElevenLabs) |
| Altyazı | Kelime kelime parlayan, CapCut tarzı kalın altyazılar |
| Görsel | Hareketli arka plan, emoji animasyonları, sayaç ve karşılaştırma grafikleri |
| Müzik | Her video için kodla bestelenen telifsiz fon müziği, konuşmada otomatik kısılır |
| Efekt | Geçişlerde whoosh, emoji girişlerinde pop, açılışta darbe sesi |
| Miks | Platform standardı ses seviyesi (-14 LUFS), 1080x1920, 30 fps, H.264 |
| Paylaşım | Postiz ile üç platforma başlık, açıklama ve etiketlerle zamanlı paylaşım |

## Klasörler
- `icerikler/` her videonun senaryo ve sahne dosyası (JSON)
- `motor/` video motoru: `uret.py` (ana betik), `ses.py`, `muzik.py`, `sahne.html`, `render.js`
- `yayin/` Postiz paylaşım betiği ve platform ayarları
- `takvim/konular.md` sıradaki konular
- `OTOMASYON.md` günlük otomatik görevin adım adım talimatı
- `cikti/` üretilen videolar (git'e girmez)

## Kullanım
```bash
./kurulum.sh
python3 motor/uret.py icerikler/001-saskin-gercekler.json            # video üret
python3 motor/uret.py icerikler/001-saskin-gercekler.json --kareler  # hızlı önizleme kareleri
python3 yayin/yayinla.py --kontrol                                   # Postiz bağlantısını kontrol et
python3 yayin/yayinla.py cikti/001-saskin-gercekler --saat 19:00     # bugün 19:00'a zamanla
```

## Otomatik paylaşım için yapılacaklar (bir kerelik)
1. **Postiz hesabı** aç (postiz.com) ve YouTube kanalını, Instagram profesyonel hesabını
   (İçerik Üreticisi veya İşletme) ve TikTok hesabını bağla.
2. Postiz → Settings → **Public API** bölümünden API anahtarını oluştur.
3. Claude ortam ayarlarında (oturum başlığındaki bulut ortam menüsü → **Edit**):
   - **Ağ erişimi**: izinli alan adlarına `api.postiz.com` ekle (ya da erişimi "Full" yap).
     Video yükleme ve paylaşım bu tek adres üzerinden yapılır.
   - **Ortam değişkeni / secret**: `POSTIZ_API_KEY` = Postiz anahtarı.
4. Daha doğal ses için (isteğe bağlı): Azure Speech ücretsiz katmanı (`AZURE_SPEECH_KEY`,
   `AZURE_SPEECH_REGION`, ağ: `<bölge>.tts.speech.microsoft.com`) veya ElevenLabs
   (`ELEVENLABS_API_KEY`, ağ: `api.elevenlabs.io`). İçerik dosyasında
   `"ses": {"motor": "azure", "konusmaci": "tr-TR-AhmetNeural"}` yazman yeterli.

## Para kazanma hakkında gerçekçi notlar
- YouTube Partner Programı: 1.000 abone + 90 günde 10 milyon Shorts izlenmesi
  (veya 12 ayda 4.000 saat uzun video izlenmesi).
- YouTube "özgün olmayan içerik" politikası seri üretilmiş, tekrarlayan videoları
  para kazanmaya kapatıyor. Bu yüzden her video özgün araştırma, kaynak ve özel
  grafiklerle üretilir; aynı şablon birebir tekrarlanmaz.
- TikTok ve Instagram'ın doğrudan ödeme programları Türkiye'de ya yok ya da çok
  sınırlı. Bu iki platform daha çok kitle büyütmek ve marka iş birlikleri için.
