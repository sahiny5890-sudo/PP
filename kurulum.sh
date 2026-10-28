#!/usr/bin/env bash
# Gerekli Python paketlerini, Türkçe ses modellerini ve Postiz CLI'ı kurar. Tekrar çalıştırmak güvenlidir.
set -euo pipefail
cd "$(dirname "$0")"

pip install -q -r requirements.txt 2>&1 | grep -v -i "warning" || true

mkdir -p .modeller
for ses in fahrettin fettah; do
  dizin=".modeller/vits-piper-tr_TR-${ses}-medium"
  [ -f "$dizin/tr_TR-${ses}-medium.onnx" ] && continue
  echo "Ses modeli indiriliyor: $ses"
  curl -sSL -o "/tmp/${ses}.tar.bz2" \
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/vits-piper-tr_TR-${ses}-medium.tar.bz2"
  tar xjf "/tmp/${ses}.tar.bz2" -C .modeller && rm "/tmp/${ses}.tar.bz2"
done

command -v postiz >/dev/null 2>&1 || npm install -g postiz >/dev/null 2>&1 || echo "Uyarı: postiz CLI kurulamadı"
command -v ffmpeg >/dev/null || { echo "ffmpeg gerekli"; exit 1; }
node -e "require('playwright')" 2>/dev/null || { echo "Playwright gerekli: npm i -g playwright && npx playwright install chromium"; exit 1; }
echo "Kurulum tamam."
