"""Seslendirme: metni sese çevirir, sesi temizler ve kelime zamanlamalarını çıkarır.

Desteklenen motorlar:
  piper       ücretsiz, çevrimdışı (fahrettin / fettah sesleri, CC0 lisanslı)
  azure       Microsoft Azure sinir ağı sesleri (AZURE_SPEECH_KEY gerekir)
  elevenlabs  ElevenLabs (ELEVENLABS_API_KEY gerekir)
"""
import hashlib
import io
import json
import os
import re
import urllib.request
from math import gcd

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_DIZINI = os.path.join(KOK, ".modeller")
ONBELLEK = os.path.join(KOK, ".onbellek", "ses")
SR = 48000


def yeniden_ornekle(x, sr_kaynak, sr_hedef=SR):
    if sr_kaynak == sr_hedef:
        return x.astype(np.float32)
    g = gcd(sr_kaynak, sr_hedef)
    return resample_poly(x, sr_hedef // g, sr_kaynak // g).astype(np.float32)


class PiperSes:
    def __init__(self, konusmaci="fahrettin", hiz=1.0):
        from piper import PiperVoice
        d = os.path.join(MODEL_DIZINI, f"vits-piper-tr_TR-{konusmaci}-medium")
        model = os.path.join(d, f"tr_TR-{konusmaci}-medium.onnx")
        if not os.path.exists(model):
            raise SystemExit(f"Ses modeli yok: {model}\nÖnce ./kurulum.sh çalıştır.")
        self.voice = PiperVoice.load(model, config_path=model + ".json")
        self.hiz = hiz
        self.ad = f"piper-{konusmaci}-{hiz}"

    def sentezle(self, metin):
        from piper import SynthesisConfig
        cfg = SynthesisConfig(length_scale=1.0 / self.hiz)
        parcalar = list(self.voice.synthesize(metin, cfg))
        x = np.concatenate([p.audio_float_array for p in parcalar])
        return x, parcalar[0].sample_rate


class AzureSes:
    def __init__(self, ses="tr-TR-AhmetNeural", hiz=1.0):
        self.anahtar = os.environ["AZURE_SPEECH_KEY"]
        self.bolge = os.environ.get("AZURE_SPEECH_REGION", "westeurope")
        self.ses, self.hiz = ses, hiz
        self.ad = f"azure-{ses}-{hiz}"

    def sentezle(self, metin):
        from xml.sax.saxutils import escape
        oran = f"{(self.hiz - 1) * 100:+.0f}%"
        ssml = (f"<speak version='1.0' xml:lang='tr-TR'><voice name='{self.ses}'>"
                f"<prosody rate='{oran}'>{escape(metin)}</prosody></voice></speak>")
        istek = urllib.request.Request(
            f"https://{self.bolge}.tts.speech.microsoft.com/cognitiveservices/v1",
            data=ssml.encode("utf-8"),
            headers={"Ocp-Apim-Subscription-Key": self.anahtar,
                     "Content-Type": "application/ssml+xml",
                     "X-Microsoft-OutputFormat": "riff-48khz-16bit-mono-pcm",
                     "User-Agent": "icerik-fabrikasi"})
        with urllib.request.urlopen(istek, timeout=60) as yanit:
            x, sr = sf.read(io.BytesIO(yanit.read()), dtype="float32")
        return x, sr


class ElevenLabsSes:
    def __init__(self, ses="pNInz6obpgDQGcFmaJgB", hiz=1.0):
        self.anahtar = os.environ["ELEVENLABS_API_KEY"]
        self.ses, self.hiz = ses, hiz
        self.ad = f"elevenlabs-{ses}-{hiz}"

    def sentezle(self, metin):
        govde = {"text": metin, "model_id": "eleven_multilingual_v2",
                 "voice_settings": {"stability": 0.45, "similarity_boost": 0.8,
                                    "style": 0.15, "speed": self.hiz}}
        istek = urllib.request.Request(
            f"https://api.elevenlabs.io/v1/text-to-speech/{self.ses}?output_format=pcm_44100",
            data=json.dumps(govde).encode("utf-8"),
            headers={"xi-api-key": self.anahtar, "Content-Type": "application/json"})
        with urllib.request.urlopen(istek, timeout=120) as yanit:
            x = np.frombuffer(yanit.read(), dtype="<i2").astype(np.float32) / 32768
        return x, 44100


def motor_sec(ayar):
    ayar = ayar or {}
    motor = ayar.get("motor", "piper")
    hiz = float(ayar.get("hiz", 1.0))
    if motor == "azure":
        return AzureSes(ayar.get("konusmaci", "tr-TR-AhmetNeural"), hiz)
    if motor == "elevenlabs":
        return ElevenLabsSes(ayar.get("konusmaci", "pNInz6obpgDQGcFmaJgB"), hiz)
    return PiperSes(ayar.get("konusmaci", "fahrettin"), hiz)


def sentezle_onbellekli(motor, metin):
    """Aynı cümle tekrar istenirse yeniden üretmez; 48 kHz mono float döner."""
    os.makedirs(ONBELLEK, exist_ok=True)
    anahtar = hashlib.sha1(f"{motor.ad}|{metin}".encode()).hexdigest()[:16]
    yol = os.path.join(ONBELLEK, anahtar + ".wav")
    if os.path.exists(yol):
        x, _ = sf.read(yol, dtype="float32")
        return x
    x, sr = motor.sentezle(metin)
    x = yeniden_ornekle(np.asarray(x, dtype=np.float32), sr)
    sf.write(yol, x, SR, subtype="FLOAT")
    return x


# --- Metin -> kelimeler ---------------------------------------------------
# "{25 cm'ye|yirmi beş santimetreye}" ekranda solu gösterir, sağı okutur.
TOKEN = re.compile(r"\{([^|}]+)\|([^}]+)\}|(\S+)")


def cumlelere_bol(metin):
    return [c.strip() for c in re.split(r"(?<=[.!?])\s+(?![^{]*\})", metin.strip()) if c.strip()]


def kelimelere_bol(cumle):
    kelimeler = []
    for m in TOKEN.finditer(cumle):
        goster, soyle = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(3))
        son = soyle.rstrip()[-1]
        durak = 2 if son in ".!?" else 1 if son in ",;:" else 0
        # Altyazıda virgül/nokta gösterilmez; soru ve ünlem kalır.
        temiz = re.sub(r"[.,;:]+$", "", goster.strip())
        kelimeler.append({"g": temiz, "soyle": soyle, "durak": durak})
    return kelimeler


_FONEMLEYICI = None


def kelime_agirligi(soyle):
    """Kelimenin söylenme süresine orantılı bir ağırlık (fonem sayısı)."""
    global _FONEMLEYICI
    if _FONEMLEYICI is None:
        try:
            d = os.path.join(MODEL_DIZINI, "vits-piper-tr_TR-fahrettin-medium")
            from piper import PiperVoice
            _FONEMLEYICI = PiperVoice.load(os.path.join(d, "tr_TR-fahrettin-medium.onnx"),
                                           config_path=os.path.join(d, "tr_TR-fahrettin-medium.onnx.json"))
        except Exception:
            _FONEMLEYICI = False
    if _FONEMLEYICI:
        fonemler = "".join("".join(c) for c in _FONEMLEYICI.phonemize(soyle))
        n = len(re.sub(r"[ˈˌː\s.,!?;:'\-]", "", fonemler))
    else:
        n = len(re.sub(r"\W", "", soyle))
    return max(1, n)


# --- Ses analizi ----------------------------------------------------------
def kirp(x, esik_db=-42, pay=0.03):
    """Baştaki ve sondaki sessizliği kırpar."""
    pencere = int(0.01 * SR)
    n = len(x) // pencere
    if n == 0:
        return x
    rms = np.sqrt(np.mean(x[: n * pencere].reshape(n, pencere) ** 2, axis=1) + 1e-12)
    db = 20 * np.log10(rms / (rms.max() + 1e-12))
    aktif = np.where(db > esik_db)[0]
    if len(aktif) == 0:
        return x
    bas = max(0, aktif[0] * pencere - int(pay * SR))
    son = min(len(x), (aktif[-1] + 1) * pencere + int(pay * SR))
    return x[bas:son]


def duraklari_bul(x, min_sure=0.09):
    pencere = int(0.01 * SR)
    n = len(x) // pencere
    rms = np.sqrt(np.mean(x[: n * pencere].reshape(n, pencere) ** 2, axis=1) + 1e-12)
    db = 20 * np.log10(rms + 1e-12)
    esik = np.percentile(db, 90) - 28
    sessiz = db < esik
    duraklar, i = [], 0
    while i < n:
        if sessiz[i]:
            j = i
            while j < n and sessiz[j]:
                j += 1
            if (j - i) * 0.01 >= min_sure and i > 0 and j < n:
                duraklar.append((i * 0.01, j * 0.01))
            i = j
        else:
            i += 1
    return duraklar


def kelime_zamanlari(kelimeler, x):
    """Cümle sesindeki her kelimenin (başlangıç, bitiş) süresini tahmin eder.

    Virgüllerdeki duraklamalar sesten bulunur ve çapa olarak kullanılır;
    aradaki kelimeler fonem sayılarına göre paylaştırılır.
    """
    T = len(x) / SR
    w = np.array([kelime_agirligi(k["soyle"]) for k in kelimeler], dtype=float)
    kum = np.cumsum(w) / w.sum()
    duraklar = duraklari_bul(x)
    kullanilan = set()
    # Çapalar: (kelime indeksi, bu kelimenin bitişi, sonraki kelimenin başlangıcı)
    capalar = []
    for i, k in enumerate(kelimeler[:-1]):
        if k["durak"] == 0:
            continue
        tahmin = kum[i] * T
        aday = [(abs((a + b) / 2 - tahmin), j) for j, (a, b) in enumerate(duraklar) if j not in kullanilan]
        if aday:
            fark, j = min(aday)
            if fark < 0.45:
                kullanilan.add(j)
                capalar.append((i, duraklar[j][0], duraklar[j][1]))
    capalar.sort()
    sonuc = [None] * len(kelimeler)
    bas_i, bas_t = 0, 0.0
    for i, son_t, sonraki_t in capalar + [(len(kelimeler) - 1, T, T)]:
        dilim = w[bas_i: i + 1]
        sinirlar = bas_t + np.concatenate([[0], np.cumsum(dilim) / dilim.sum()]) * (son_t - bas_t)
        for k in range(len(dilim)):
            sonuc[bas_i + k] = (float(sinirlar[k]), float(sinirlar[k + 1]))
        bas_i, bas_t = i + 1, sonraki_t
    return sonuc
