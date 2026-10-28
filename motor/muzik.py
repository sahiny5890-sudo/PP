"""Telifsiz fon müziği ve geçiş efektleri üretir (tamamen kodla sentezlenir)."""
import numpy as np
from scipy.signal import butter, fftconvolve, istft, sosfilt, stft

SR = 48000

# Her biri 4 ölçülük akor yürüyüşü (MIDI notaları). "merak" bilgi videoları için varsayılan.
YURUYUSLER = {
    "merak": [[50, 57, 60, 64, 65], [46, 53, 57, 62, 65], [41, 53, 57, 60, 64], [48, 55, 60, 62, 67]],
    "umut": [[48, 55, 60, 64, 67], [45, 52, 57, 60, 64], [41, 53, 57, 60, 65], [43, 55, 59, 62, 67]],
    "gizem": [[45, 52, 57, 60, 64], [41, 48, 57, 60, 65], [43, 50, 55, 59, 62], [40, 47, 55, 59, 64]],
}


def hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def _filtre(x, tur, f):
    return sosfilt(butter(2, f, btype=tur, fs=SR, output="sos"), x, axis=0)


def _yerlestir(hedef, ses, t):
    i = int(t * SR)
    if i >= len(hedef):
        return
    n = min(len(ses), len(hedef) - i)
    hedef[i:i + n] += ses[:n]


def _epiano(f, sure, guc):
    t = np.arange(int(sure * SR)) / SR
    indeks = 1.6 * np.exp(-t * 7)
    ton = np.sin(2 * np.pi * f * t + indeks * np.sin(2 * np.pi * f * t))
    parilti = 0.12 * np.sin(2 * np.pi * f * 7.0 * t) * np.exp(-t * 35)
    zarf = np.exp(-t * 2.4) * (1 - np.exp(-t * 600))
    return guc * (ton + parilti) * zarf


def _pad(f, sure):
    t = np.arange(int(sure * SR)) / SR
    x = np.zeros((len(t), 2))
    for kanal, sapma in enumerate((-0.0025, 0.0025)):
        for k in range(1, 6):
            x[:, kanal] += np.sin(2 * np.pi * f * k * (1 + sapma) * t + kanal * k) / k ** 1.6
    atak, birak = 0.35, 0.6
    zarf = np.minimum(1, t / atak) * np.minimum(1, np.maximum(0, (sure - t) / birak))
    return x * zarf[:, None]


def _kick():
    t = np.arange(int(0.45 * SR)) / SR
    frekans = 48 + 75 * np.exp(-t * 28)
    faz = 2 * np.pi * np.cumsum(frekans) / SR
    return np.sin(faz) * np.exp(-t * 7.5) + 0.25 * np.random.randn(len(t)) * np.exp(-t * 300)


def _snare():
    n = int(0.22 * SR)
    t = np.arange(n) / SR
    gurultu = _filtre(np.random.randn(n), "bandpass", [900, 4500])
    return (gurultu * np.exp(-t * 22) + 0.3 * np.sin(2 * np.pi * 190 * t) * np.exp(-t * 30))


def _hat():
    n = int(0.06 * SR)
    t = np.arange(n) / SR
    return _filtre(np.random.randn(n), "highpass", 7000) * np.exp(-t * 90)


def _reverb(x, sure=2.4, karisim=0.28):
    n = int(sure * SR)
    t = np.arange(n) / SR
    ir = np.random.randn(n, 2) * np.exp(-t * 6.9 / sure)[:, None]
    ir = _filtre(ir, "lowpass", 6000)
    ir /= np.sqrt((ir ** 2).sum(axis=0))
    islak = np.stack([fftconvolve(x[:, k], ir[:, k])[: len(x)] for k in range(2)], axis=1)
    return (1 - karisim) * x + karisim * islak


def fon_muzigi(sure, ruh_hali="merak", bpm=88, tohum=7):
    """Video süresince akan, sonunda kısılan stereo fon müziği."""
    rng = np.random.default_rng(tohum)
    np.random.seed(tohum)
    yuruyus = YURUYUSLER.get(ruh_hali, YURUYUSLER["merak"])
    vurus = 60 / bpm
    olcu = 4 * vurus
    n = int((sure + 3) * SR)
    melodik = np.zeros((n, 2))
    ritim = np.zeros((n, 2))
    arp_deseni = [0, 2, 1, 3, 2, 4, 3, 1]
    kick, snare, hat = _kick(), _snare(), _hat()
    o = 0
    while o * olcu < sure + 1:
        akor = yuruyus[o % len(yuruyus)]
        t0 = o * olcu
        for nota in akor[1:]:
            pad = _pad(hz(nota), olcu + 0.6) * 0.05
            _yerlestir(melodik, pad, t0)
        for adim in range(8):
            nota = akor[1:][arp_deseni[adim] % (len(akor) - 1)] + 12
            ton = _epiano(hz(nota), 1.2, 0.09 * rng.uniform(0.7, 1.0))
            pan = 0.5 + 0.35 * np.sin(adim * 0.9)
            _yerlestir(melodik, np.stack([ton * (1 - pan), ton * pan], axis=1), t0 + adim * vurus / 2)
        for vurus_i, uzunluk in ((0, 1.6), (2, 1.6)):
            t = np.arange(int(uzunluk * vurus * SR)) / SR
            bas = np.sin(2 * np.pi * hz(akor[0] - 12) * t) * np.minimum(1, t / 0.01) * np.exp(-t * 1.2) * 0.22
            _yerlestir(ritim, np.stack([bas, bas], axis=1), t0 + vurus_i * vurus)
        for adim in range(8):
            t = t0 + adim * vurus / 2 + (0.06 * vurus if adim % 2 else 0)
            if adim in (0, 4) or (adim == 5 and o % 2):
                _yerlestir(ritim, np.stack([kick, kick], axis=1) * 0.42, t)
            if adim in (2, 6):
                _yerlestir(ritim, np.stack([snare, snare], axis=1) * 0.10, t)
            g = 0.035 if adim % 2 else 0.05
            _yerlestir(ritim, np.stack([hat * 0.8, hat], axis=1) * g, t)
        o += 1
    melodik = _reverb(_filtre(melodik, "lowpass", 7000))
    x = melodik + ritim
    x = _filtre(x, "highpass", 35)
    x = np.tanh(x * 1.3) / 1.3
    x = x[: int(sure * SR)]
    giris = np.minimum(1, np.arange(len(x)) / (0.4 * SR))
    cikis = np.minimum(1, (len(x) - np.arange(len(x))) / (2.0 * SR))
    x *= (giris * cikis)[:, None]
    return (x / (np.sqrt(np.mean(x ** 2)) + 1e-9) * 0.05).astype(np.float32)


# --- Efektler ---------------------------------------------------------------
def whoosh(sure=0.5):
    n = int(sure * SR)
    f, _, Z = stft(np.random.randn(n), SR, nperseg=1024)
    merkez = np.geomspace(250, 5000, Z.shape[1])
    kazanc = np.exp(-0.5 * ((np.log(f[:, None] + 1) - np.log(merkez[None, :])) / 0.55) ** 2)
    _, y = istft(Z * kazanc, SR)
    y = y[:n]
    x = np.linspace(0, 1, len(y))
    zarf = np.sin(np.pi * np.minimum(1, x / 0.75) / 2) ** 2 * np.minimum(1, (1 - x) / 0.25)
    y = y * zarf
    y /= np.abs(y).max() + 1e-9
    sag = np.roll(y, 40)
    return np.stack([y, sag], axis=1).astype(np.float32)


def pop():
    t = np.arange(int(0.12 * SR)) / SR
    frekans = 520 + 900 * np.exp(-t * 60)
    faz = 2 * np.pi * np.cumsum(frekans) / SR
    y = (np.sin(faz) + 0.2 * np.sin(2 * faz)) * np.exp(-t * 38) * np.minimum(1, t / 0.002)
    y /= np.abs(y).max()
    return np.stack([y, y], axis=1).astype(np.float32)


def darbe():
    t = np.arange(int(1.2 * SR)) / SR
    frekans = 42 + 70 * np.exp(-t * 9)
    alt = np.sin(2 * np.pi * np.cumsum(frekans) / SR) * np.exp(-t * 3.2)
    kat = _filtre(np.random.randn(len(t)), "lowpass", 2500) * np.exp(-t * 18) * 0.5
    y = alt + kat
    y /= np.abs(y).max()
    y2 = np.stack([y, y], axis=1)
    return _reverb(y2, sure=1.6, karisim=0.25).astype(np.float32)


def zil():
    t = np.arange(int(1.4 * SR)) / SR
    f = 1318.5
    y = np.sin(2 * np.pi * f * t + 2.0 * np.exp(-t * 4) * np.sin(2 * np.pi * f * 3.5 * t)) * np.exp(-t * 3)
    y *= np.minimum(1, t / 0.003)
    y /= np.abs(y).max()
    return _reverb(np.stack([y, y], axis=1), sure=1.8, karisim=0.3).astype(np.float32)


EFEKTLER = {"whoosh": (whoosh, 0.20), "pop": (pop, 0.16), "darbe": (darbe, 0.30), "zil": (zil, 0.10)}


def efekt_izi(olaylar, sure):
    """olaylar: [{"tur": "whoosh", "t": 3.2}, ...] -> stereo efekt kanalı."""
    iz = np.zeros((int(sure * SR), 2), dtype=np.float32)
    onbellek = {}
    for olay in olaylar:
        uret, seviye = EFEKTLER[olay["tur"]]
        if olay["tur"] not in onbellek:
            onbellek[olay["tur"]] = uret()
        _yerlestir(iz, onbellek[olay["tur"]] * seviye, max(0.0, olay["t"]))
    return iz
