// Zaman çizelgesini (cizelge.json) kare kare render eder ve ffmpeg ile H.264 videoya kodlar.
// Kareler birkaç sekmeye bölünüp paralel çizilir; parçalar sonunda kayıpsız birleştirilir.
// Kullanım: node render.js cizelge.json cikti.mp4 [--isci 3]
//           node render.js cizelge.json onek --kareler 1.2 5.0 ...   (seçili anların JPG'leri)
//           node render.js cizelge.json kapak.jpg --kapak             (kapak görseli)
const fs = require('fs');
const os = require('os');
const path = require('path');
const { spawn } = require('child_process');
const { chromium } = require('playwright');

async function sayfaAc(browser, tl) {
  const page = await browser.newPage({ viewport: { width: 1080, height: 1920 }, deviceScaleFactor: 1 });
  await page.goto('file://' + path.join(__dirname, 'sahne.html'));
  await page.evaluate(tl => window.SETUP(tl), tl);
  await page.evaluate(() => document.fonts.ready);
  return page;
}

function kodlayici(cikti, fps) {
  return spawn('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(fps),
    '-c:v', 'mjpeg', '-i', '-', '-c:v', 'libx264', '-preset', 'medium', '-crf', '19',
    '-maxrate', '10M', '-bufsize', '20M', '-pix_fmt', 'yuv420p', '-profile:v', 'high',
    '-g', String(fps * 2), cikti], { stdio: ['pipe', 'inherit', 'inherit'] });
}

async function parcaCiz(browser, tl, bas, son, cikti, ilerleme) {
  const page = await sayfaAc(browser, tl);
  const fps = tl.fps || 30;
  const ff = kodlayici(cikti, fps);
  for (let i = bas; i < son; i++) {
    await page.evaluate(t => window.FRAME(t), i / fps);
    const kare = await page.screenshot({ type: 'jpeg', quality: 93 });
    if (!ff.stdin.write(kare)) await new Promise(r => ff.stdin.once('drain', r));
    ilerleme();
  }
  ff.stdin.end();
  const kod = await new Promise(r => ff.on('close', r));
  await page.close();
  if (kod !== 0) throw new Error('ffmpeg parça kodlaması başarısız: ' + cikti);
}

(async () => {
  const [cizelgeYolu, cikti, mod, ...zamanlar] = process.argv.slice(2);
  const tl = JSON.parse(fs.readFileSync(cizelgeYolu, 'utf8'));
  const browser = await chromium.launch();

  if (mod === '--kapak') {
    const page = await sayfaAc(browser, tl);
    await page.evaluate(k => window.KAPAK(k), tl.kapak || {});
    await page.screenshot({ path: cikti, type: 'jpeg', quality: 93 });
    await browser.close();
    return;
  }

  if (mod === '--kareler') {
    const page = await sayfaAc(browser, tl);
    for (const z of zamanlar) {
      await page.evaluate(t => window.FRAME(t), parseFloat(z));
      await page.screenshot({ path: `${cikti}-${z}.jpg`, type: 'jpeg', quality: 92 });
    }
    await browser.close();
    return;
  }

  const fps = tl.fps || 30;
  const toplam = Math.ceil(tl.sure * fps);
  const isci = mod === '--isci' ? parseInt(zamanlar[0]) : Math.max(1, Math.min(4, os.cpus().length - 1));
  const gecici = fs.mkdtempSync(path.join(os.tmpdir(), 'render-'));
  const baslangic = Date.now();
  let biten = 0, sonRapor = 0;
  const ilerleme = () => {
    biten++;
    if (biten - sonRapor >= 300 || biten === toplam) {
      sonRapor = biten;
      process.stdout.write(`    kare ${biten}/${toplam} (${((Date.now() - baslangic) / 1000).toFixed(0)} sn)\n`);
    }
  };
  const parcalar = [];
  for (let k = 0; k < isci; k++) {
    const bas = Math.floor(toplam * k / isci), son = Math.floor(toplam * (k + 1) / isci);
    parcalar.push({ bas, son, yol: path.join(gecici, `parca${k}.mp4`) });
  }
  await Promise.all(parcalar.map(p => parcaCiz(browser, tl, p.bas, p.son, p.yol, ilerleme)));
  await browser.close();

  const liste = path.join(gecici, 'liste.txt');
  fs.writeFileSync(liste, parcalar.map(p => `file '${p.yol}'`).join('\n'));
  const birlestir = spawn('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', liste,
    '-c', 'copy', '-movflags', '+faststart', cikti], { stdio: 'inherit' });
  const kod = await new Promise(r => birlestir.on('close', r));
  fs.rmSync(gecici, { recursive: true, force: true });
  if (kod !== 0) process.exit(kod);
})().catch(e => { console.error(e); process.exit(1); });
