# Sesi 3 — Baseline, Kalibrasi Roda, dan Audit Metode

**Status:** fase 1 (statis) selesai; fase 2 (kalibrasi di lantai) selesai;
audit metode sudah dimasukkan. Fase 2 **melakukan aktuasi** — bagian itu
diberi tanda jelas di bawah.

**Tanggal:** 2026-10-20 (fase 1), 2026-10-21 (fase 2) — WIB, UTC+07:00
**Host:** `stematel-pi5`

Peta dokumen:

| Bagian | Isi | Aktuasi? |
| --- | --- | --- |
| §1–§5 | fase 1: baseline lingkungan, dimensi, dampak ke sesi 2 | tidak |
| §6–§9 | fase 2: roll-out, speed sweep, free-wheel, koreksi 19% | **ya** |
| §10–§11 | dimensi (terukur vs inferensi), batas kecepatan | tidak |
| §12–§14 | audit metode, sisa pekerjaan, ringkasan status bukti | tidak |

Grade bukti yang dipakai konsisten di seluruh dokumen:

| Grade | Arti |
| --- | --- |
| **TERUKUR** | diukur di robot ini, alat dan prosedurnya dicatat |
| **TERVERIFIKASI** | dikonfirmasi lewat pembacaan langsung (protokol, port, berkas) |
| **INFERENSI** | diturunkan dari dokumen, bukan dibaca di sumber primer |
| **SOURCE-ONLY** | hanya dari dokumentasi pabrik, belum dicek di robot ini |
| **HIPOTESIS** | kandidat penjelasan, belum terpisah dari kandidat lain |
| **TIDAK DIKETAHUI** | belum ada bukti apa pun |

Bagian §1–§5 di bawah ditulis **sebelum** fase 2 dan sengaja dibiarkan apa
adanya sebagai catatan sejarah; angka yang sudah digantikan ditandai di §9.

Fase 1 tidak melakukan aktuasi dan tidak mengubah kode. Semua angka di §1–§5
diambil tanpa membuka `/dev/ttyACM0`.

## Data mentah fase 1

### 1. Baseline lingkungan

- Tanggal: 2026-10-20 (WIB, UTC+07:00)
- Host: `stematel-pi5` (Raspberry Pi 5, Ubuntu 24.04.5 LTS ARM64)
- Repo: `/home/stematelpi5/AMRTestLander/AMR_LKS_Dashboard`
- Branch: `main`
- HEAD: `f8de64e` — docs: record ground drive tests and correct the drive sign convention
- `git status --short`: bersih (tidak ada perubahan tak terduga)
- Interpreter: `../.venv/bin/python` → `/home/stematelpi5/AMRTestLander/.venv/bin/python` (Python 3.12.3)
  - Catatan: `./.venv/bin/python` tidak ada di dalam repo, jadi urutan deteksi jatuh ke `../.venv`
- pyserial: 3.5
- Port STM32: `/dev/ttyACM0` — `crw-rw---- root dialout 166,0`
  - `ID_VENDOR=1a86`, `ID_MODEL=USB_Single_Serial`, `ID_MODEL_ID=55d4`
  - `ID_MM_CANDIDATE=1` (ModemManager masih menganggap port ini kandidat)
- ModemManager: `active` (sengaja tidak dimatikan)
- `fuser -v /dev/ttyACM0`: tidak ada proses yang memegang port
- `pytest -q`: **317 passed, 0 failed** (12.33 s)

### 2. Data pengukuran mekanik

| Besaran | Nilai | Status |
| --- | --- | --- |
| D1 | 5,5 cm | terukur |
| D2 | — | tidak diukur |
| D3 | — | tidak diukur |
| D rata-rata | 5,5 cm | **satu sampel saja** |
| Keliling roda C = pi × D | 17,28 cm | 0,1728 m |
| L (kiri–kanan, pusat ke pusat) | 14,5 cm | lolos validasi |
| H (depan–belakang, pusat ke pusat) | 13,5 cm | lolos validasi |
| Alat ukur | penggaris | kasar, bukan jangka sorong |
| Validasi rentang (D 5,0–6,0 cm; L,H 10–30 cm) | lolos | D=5,5 · L=14,5 · H=13,5 |

> **Baris `C = 17,28 cm` di tabel ini sudah digantikan.** Itu keliling
> *geometris* dari `D` = 5,5 cm (satu sampel). Jarak tempuh per putaran yang
> sebenarnya diukur langsung di §6: **`C_eff` = 20,72 ± 1,84 cm**. Alasan
> 5,5 cm tidak lagi dipakai ada di §10.2.

### 3. Catatan: angka D yang dibuang (6,32 cm)

Pengukuran pertama melaporkan **D = 6,32 cm** dan **ditolak**, bukan dinormalkan.
Dua alasan:

1. Di luar rentang kewajaran yang ditetapkan (5,0–6,0 cm).
2. Bentrok **14,9%** dengan `docs/sesi_2.md` §9.7 yang mencatat D = 5,5 cm.

**Penyebab kesalahan — terkonfirmasi oleh operator:** angka 6,32 cm diambil dengan
**mengukur dari lantai ke atas** (tinggi dari tanah sampai puncak roda), bukan
melintasi titik tengah roda. Metode itu ikut menghitung bagian yang menonjol dan
pandangan miring, sehingga hasilnya kebesaran.

Ukur ulang dengan metode melintasi pusat roda menghasilkan **5,5 cm**, konsisten
dengan sesi 2.

**Pelajaran metodologis:** diameter roda harus diukur melintasi pusat, pada
permukaan yang menyentuh lantai. Mengukur tinggi lantai-ke-puncak bukan pengganti.

### 4. Dampak ke perhitungan kecepatan (sesi 2 §9.7)

Dengan D = 5,5 cm dipertahankan (bukan 6,32 cm):

```
kecepatan perintah = 0,3 rps × 17,28 cm = 5,18 cm/s
kecepatan aktual   = 5 cm / 5 s         = 1,00 cm/s
rasio              = 1,00 / 5,18        ≈ 19,3%
```

Bila D = 6,32 cm dipakai, rasio jadi ≈ 16,8%. Jadi kesalahan diameter **tidak**
menjelaskan rasio 19% — selisihnya hanya 1,5 poin persentase. Dua kandidat penyebab
di sesi 2 (faktor skala satuan vs motor tidak mencapai kecepatan perintah) tetap
terbuka, dan harus dipisahkan dengan mengukur jarak percobaan 0,6 rps / 3 s yang
belum pernah diukur.

> **Sudah digantikan oleh fase 2.** Angka rasio ≈19,3% di atas berasal dari
> percobaan 5 cm / 5 s di sesi 2, yang tidak reprodusibel — lihat §9. Angka yang
> dipakai sekarang: rasio 83–92% (§7). Dua kandidat penyebab yang disebut di
> paragraf ini sudah diputuskan: satuan **rps terbukti benar** (§8), jadi kandidat
> "faktor skala satuan" gugur.

### 5. Keterbatasan yang harus diakui

- **D hanya satu sampel.** Instruksi meminta 3 pengukuran untuk menaksir sebaran;
  yang ada hanya 1. Nilai 5,5 cm dipercaya karena **dua pengukuran independen**
  (sesi 2 dan sesi 3) sepakat, bukan karena sampelnya banyak.
- **Semua ukuran pakai penggaris.** Galat ±1 mm pada D ≈ ±1,8% pada keliling.
  Jangka sorong belum dipakai.
- **Roller mecanum** membuat keliling efektif tidak identik dengan keliling
  geometris. Angka C = 17,28 cm adalah keliling geometris, bukan jarak tempuh
  per putaran yang sebenarnya.

---

## Fase 2 — Kalibrasi roda dan kecepatan

**Tanggal:** 2026-10-21
**Aktuasi:** ya. Roda bergerak, sebagian dengan robot di lantai.
**Prasyarat yang dipenuhi:** area kosong, E-stop dalam jangkauan, kecepatan
rendah, durasi pendek, izin pemilik.

Alat yang dipakai: `scripts/wheel_test.py` (streaming frame di `--rate`,
STOP selalu dikirim di blok `finally`), penggaris/meteran, stopwatch.

## 6. 2A — Roll-out (robot mati, didorong)

Metode: robot dimatikan, roda didorong manual sejauh **3 putaran penuh**,
jarak tempuh diukur dengan penggaris. Tidak ada perintah motor, tidak ada
port yang dibuka. Tujuan: mengukur jarak tempuh per putaran (`C_eff`)
**tanpa** bergantung pada satuan perintah maupun pada motor.

| Trial | Jarak 3 putaran | `C_eff = d/3` |
| --- | --- | --- |
| 1 | 61,5 cm | 20,50 cm |
| 2 | 57,0 cm | 19,00 cm |
| 3 | 68,0 cm | 22,67 cm |

| Statistik | Nilai |
| --- | --- |
| Rata-rata | **20,72 cm** |
| Simpangan baku sampel (n−1) | 1,84 cm |
| Koefisien variasi | **8,9%** |
| Median | 20,50 cm |
| Rentang 1σ | **18,88 – 22,57 cm** |
| Sebaran min–maks | 3,67 cm (17,7% dari rata-rata) |
| `D_eff = C_eff/π` | 6,60 cm |

**Status: TERUKUR.** Ini satu-satunya pengukuran `C_eff` yang tidak
meminjam asumsi apa pun dari protokol atau dari pabrik.

**Dipakai sebagai titik kerja, bukan angka eksak.** Yang benar adalah
`C_eff = 20,7 ± 1,8 cm`. Setiap perhitungan turunan di dokumen ini membawa
galat itu; di §7 galat tersebut dihitung eksplisit karena besarnya (9%)
sebanding dengan efek yang ingin dideteksi.

**Kenapa hanya 3 putaran.** Hitungan putaran manual punya resolusi ±0,5
putaran, yaitu ±6,7% pada 3 putaran. Itu galat hitung saja, belum termasuk
galat penggaris (±1 cm pada 62 cm ≈ ±1,6%) dan variasi lintasan dorong.
Perbaikan termurah ada di §13 butir 1.

## 7. 2B — Speed sweep di lantai

Perintah (pola maju terverifikasi: `1:−`, `2:−`, `3:+`, `4:+`):

```
wheel_test.py --rate 50 --duration <D> \
    --speeds "1:-<u>,2:-<u>,3:+<u>,4:+<u>"
```

| `u` (rps) | Durasi | Jarak rata-rata | `v` | rps efektif (`v/C_eff`) | Rasio ke perintah |
| --- | --- | --- | --- | --- | --- |
| 0,3 | 5 s | 25,75 cm | 5,15 cm/s | 0,249 | **83%** |
| 0,6 | 3 s | 33,0 cm | 11,00 cm/s | 0,531 | **89%** |
| 1,0 | 3 s | 57,0 cm | 19,00 cm/s | 0,918 | **92%** |

Perintah pada `u` dinyatakan sebagai `u × C_eff` = 6,22 / 12,43 / 20,72 cm/s.

### 7.1 Apa yang boleh diklaim

Rasio teramati: **83%, 89%, 92%**. Itu fakta.

### 7.2 Apa yang TIDAK boleh diklaim

**Tren "rasio naik seiring kecepatan" belum terbukti.** Tiga alasan:

1. **Galat `C_eff` bersifat common-mode.** Karena `C_eff` yang sama dipakai
   untuk ketiga baris, galat 8,9%-nya menggeser semua rasio ke arah yang
   sama dan tidak bisa dibedakan dari tren nyata. Dengan galat itu
   dimasukkan, ketiga rasio konsisten dengan satu nilai konstan
   `r = 0,877`: uji chi-kuadrat memberi **χ² = 0,58** pada 2 derajat
   kebebasan (nilai kritis 5,99).
2. **Uji relatif (galat `C_eff` saling menghapus) tetap tidak signifikan.**
   Dengan hanya galat jarak (±1 cm) dan durasi (±0,1 s):
   - 0,6 vs 0,3 → +6,8% ± 6,3% = **1,08σ**
   - 1,0 vs 0,3 → +10,7% ± 5,8% = **1,85σ**
   Arahnya konsisten dengan tren, tetapi 1,85σ **di bawah** ambang lazim.
3. **Durasi tidak seragam.** 0,3 rps diukur 5 s, dua lainnya 3 s. Variabel
   yang berbeda antara baris, jadi tren tidak bisa diatribusikan ke `u`.

**Model "offset jarak tetap" juga cocok, bahkan lebih cocok.**

| Model | Parameter | rms sisa |
| --- | --- | --- |
| `d = r·u·C·T` | r = 0,896 | 1,45 cm |
| `d = u·C·T − k` | k = 4,89 cm (sd 0,55) | **0,45 cm** |
| `d = r·u·C·T − k` | r = 0,995, k = 4,70 cm | 0,45 cm |
| ramp loss `v²/2a` | a = 34 cm/s² | 3,06 cm |

Defisit jarak per titik: **5,33 / 4,30 / 5,16 cm** — hampir konstan dalam
sentimeter (rata-rata 4,89, sd 0,55), padahal kecepatannya berbeda 3,7×.
Model offset tetap juga **secara alami menghasilkan rasio yang tampak naik**
pada `u` lebih tinggi, karena porsi offset mengecil terhadap total jarak.
Artinya pola di tabel §7 bisa dijelaskan tanpa mengandaikan efisiensi
yang bergantung pada kecepatan.

**Status: HIPOTESIS, dua kandidat hidup.** (a) rasio konstan ≈0,89,
(b) kecepatan steady ≈100% dengan offset jarak tetap ≈4,9 cm. Keduanya
belum terpisah; §13 butir 2 adalah uji pemisahnya.

**Jangan menulis "efisiensi rendah di rpm rendah".** Kalimat itu tidak
ditopang data: tidak ada pengukuran torsi, arus, atau suhu, dan arah
hubungannya pun belum pasti (rasio rendah di kecepatan rendah berarti loss
relatif lebih besar, yang juga dihasilkan model offset tetap tanpa perlu
menyinggung efisiensi motor).

### 7.3 Model `v ≈ 19,8u − 0,8` — ditolak

Regresi linear tiga titik memberi slope 19,80 ± 0,14 cm/s per rps dan
intersep −0,82 ± 0,10 cm/s. Angka itu **tidak dipakai**, karena:

- **Intersep tidak signifikan.** Hanya 1 derajat kebebasan; t = 8,42,
  sedangkan t kritis (dof = 1, 95%) = 12,71.
- **Bertentangan dengan pengamatan stall.** Model itu memprediksi
  `v(0,15) = +2,15 cm/s`, padahal di 0,15 rps roda berhenti total
  (sesi 2 §9.7). Garis itu salah di bawah titik data terendahnya sendiri.
- Rentang `u` yang pernah diuji hanya **0,3–1,0** (faktor 3,3); ekstrapolasi
  ke luar itu tidak punya dasar, apalagi ke bawah melewati ambang stall.

**Pengganti sementara:** `v ≈ 18,2u cm/s` (lewat titik asal, satu
parameter), **hanya sah untuk u = 0,3–1,0**. Ini titik kerja, bukan
kalibrasi final. Bentuk `19,8u − 0,8` menyiratkan presisi yang tidak
dimiliki data dan menyesatkan di dekat ambang stall.

## 8. 2C — Free-wheel (roda terangkat)

Perintah: `wheel_test.py --duration 10 --speeds "1:-0.6,2:-0.6,3:+0.6,4:+0.6"`.

| Trial | `u` | Durasi | Putaran | Posisi akhir | Catatan |
| --- | --- | --- | --- | --- | --- |
| (pra-uji) | 0,6 | — | — | — | **nyendet**; bukan trial 1, tidak dipakai |
| 1 | 0,6 | 10 s | 3 putaran lebih | 270° | **mulus** |
| 2 | 0,6 | 10 s | ~5 putaran | 180° | **mulus** |

Trial 1 konsisten dengan dirinya sendiri: 3 putaran + 270° = 3,75 putaran
→ 0,375 rps. Trial 2 → 0,500 rps.

### 8.1 Yang dibuktikan: satuan adalah rps — TERVERIFIKASI

Bila float itu rad/s, `0,6 rad/s = 0,0955 rps` → hanya **0,95 putaran**
dalam 10 s. Terukur 3,75 dan 5 putaran: faktor **3,1×–5,2×** di atas
prediksi rad/s, dan **di bawah** prediksi rps (6 putaran). Tidak ada
pembacaan yang mendukung rad/s.

Catatan penting: hasilnya **di bawah** 6 putaran yang diprediksi rps murni,
jadi data ini konsisten dengan rps **plus** sedikit loss — bukan bukti
bahwa loss-nya nol.

### 8.2 Yang TIDAK dibuktikan: besarnya loss

- **Resolusi hitung ±0,5 putaran** = ±13% (trial 1) dan ±10% (trial 2).
  Itu cukup untuk memutuskan rps vs rad/s (selisih 3–5×), **tidak cukup**
  untuk mengukur loss 17%.
- **Ground 0,531 rps vs free-wheel 0,500 rps** (trial 2) berbeda 6,2%,
  yaitu **di dalam** resolusi ±10%. Angkanya tidak boleh disebut "cocok"
  maupun dipakai untuk menyimpulkan loss lantai.
- Roda bebas seharusnya berputar **sama atau lebih cepat** daripada roda
  berbeban. Ground (0,531) > free (0,500) berarti jarak per putaran di
  lantai lebih besar daripada di udara — secara fisis mustahil, jadi
  selisih ini **harus** dibaca sebagai noise, bukan sebagai efisiensi.
- Urutan yang benar hanya bisa muncul bila `C_eff` lebih besar dari 20,72
  (butuh ≥22,0 cm), yang masih di dalam 1σ. Jadi datanya tidak melanggar
  fisika; yang melanggar adalah tafsir "keduanya 83%".

**Kesimpulan §8:** free-wheel menetapkan **satuan** (rps) dan kira-kira
menunjukkan bahwa drag tanpa beban kecil. Ia tidak menetapkan loss, dan
tidak boleh dipakai sebagai faktor kalibrasi.

## 9. Koreksi terhadap sesi 2 — klaim "19%"

Klaim sesi 2 §9.7: 5 cm dalam 5 s → 1,00 cm/s → 19% dari perintah. Klaim
itu **digantikan**, bukan dibuktikan sebagai artefak.

| Pemeriksaan | Hasil |
| --- | --- |
| Waktu yang diperlukan untuk 5 cm pada `u` = 0,3 | **0,80–0,97 s** (0,80 s pada laju perintah 6,22 cm/s; 0,97 s pada laju terukur 5,15 cm/s) |
| Durasi yang dicatat saat itu | 5 s — **5–6× lebih lama** dari yang dibutuhkan |
| Data baru pada `u` = 0,3 | 26 cm dan 25,5 cm, **reprodusibel**, setara 5,15 cm/s |
| Rasio yang konsisten dengan data baru | 83%, bukan 19% |

Selisihnya 4,3× — terlalu besar untuk dijelaskan oleh galat penggaris
(±1 cm pada 5 cm = ±20%) maupun oleh salah ukur `D` (yang efeknya hanya
1,5 poin persentase, §4).

**Sebab pasti tidak terbukti.** Kandidat yang masih mungkin: durasi efektif
lebih pendek dari yang dicatat, jarak awal/akhir salah ditandai, atau
gerakan tertahan. Tidak ada bukti yang memisahkannya, jadi tidak ditulis
sebagai "terbukti artefak".

**Yang berubah karena koreksi ini:**

- Kandidat "faktor skala satuan ~1/5" **gugur** — satuan rps terbukti (§8),
  dan tidak ada lagi anomali 5× yang perlu dijelaskan.
- Kandidat "motor tidak mencapai kecepatan perintah" **tidak lagi
  didukung** oleh angka 19%. Yang tersisa adalah pertanyaan yang jauh lebih
  kecil: selisih 8–11% atau offset 4,9 cm (§7).

## 10. Dimensi chassis — terukur vs inferensi

| Besaran | Terukur di robot | Pabrik | Selisih | Status |
| --- | --- | --- | --- | --- |
| `L` (kiri–kanan, pusat–pusat) | **145 mm** | 147,5 mm (73,75×2) | −1,7% | TERUKUR |
| `H` (depan–belakang, pusat–pusat) | **135 mm** | 133,54 mm (66,77×2) | +1,1% | TERUKUR |
| `D` (diameter roda) | tidak diukur langsung | 64,5 mm / 65,8 mm | — | lihat di bawah |
| `C_eff` (jarak per putaran) | **20,72 ± 1,84 cm** | — | — | TERUKUR (§6) |

Sumber pabrik `L`/`H`: dokumentasi URDF Hiwonder (`mecanum.xacro`, origin
joint `±0,073754` dan `±0,066774`). Keduanya cocok dengan pengukuran
dalam ±2%, jadi geometri chassis **tidak** lagi jadi penghambat.

### 10.1 `D` = 65,8 mm adalah INFERENSI, bukan spec

Angka 65,8 mm diturunkan dari PDF `6. Mapping & Navigation Course.pdf`
(hlm. 9/14/15), **bukan** dibaca sebagai spesifikasi diameter. Grade:
**INFERENSI**.

Pada 2026-10-21 dicek ulang di Pi: PDF itu **tidak punya text layer yang
bisa diekstrak** — 0 entri `/ToUnicode`, font tidak tertanam, dan tidak ada
`pdftotext`/poppler di sistem ini. Jadi angka tersebut **tidak dapat
diverifikasi ulang** dari mesin ini; yang bisa dikutip hanyalah halaman
sumbernya.

### 10.2 Jangan memilih 65,8 mm sebagai kebenaran tunggal

Bandingkan dengan `C_eff` terukur (20,72 ± 1,84 cm). z = (C−20,72)/1,84:

| Asumsi `D` | `C_geo = π·D` | z terhadap `C_eff` | Kesimpulan |
| --- | --- | --- | --- |
| 64,5 mm (halaman produk) | 20,26 cm | **−0,25** | di dalam 1σ |
| 65,0 mm | 20,42 cm | −0,16 | di dalam 1σ |
| **65,8 mm (inferensi PDF)** | 20,67 cm | **−0,03** | di dalam 1σ |
| 60,0 mm | 18,85 cm | −1,02 | di dalam 1σ, batas |
| 55,0 mm (sesi 2/3) | 17,28 cm | **−1,87** | di luar 1σ |

Ketiga kandidat 64,5 / 65,0 / 65,8 mm **tidak dapat dipisahkan** oleh data
`C_eff` — semuanya di dalam 1σ dan berjarak < 0,5 cm satu sama lain,
sedangkan 1σ-nya 1,84 cm. Yang bisa disimpulkan hanya: **55 mm salah**, dan
`C_eff` ada di kisaran 64–66 mm.

Konsekuensi praktis: kalau nanti kinematika mecanum ditulis, gunakan
`C_eff` terukur sebagai pembagi, **bukan** `π·D` dari salah satu kandidat.
`C_eff` sudah memasukkan efek roller dan kompresi ban; `π·D` tidak.

## 11. Batas kecepatan — apa yang benar-benar teruji

| Hal | Nilai | Status |
| --- | --- | --- |
| Kecepatan tertinggi yang pernah diperintah | `u` = 1,0 rps | TERVERIFIKASI |
| Kecepatan lantai pada perintah itu | **19,0 cm/s = 0,19 m/s** | TERUKUR (rata-rata 3 s, belum steady-state) |
| `SpeedLimits.max_linear_x` di checkout Pi | **0,30 m/s** | TERVERIFIKASI (`src/amr_core/robot/safety.py:32`) |
| 0,30 m/s | butuh `u` ≈ **1,45–1,65 rps** | **BELUM DIUJI** |

Selisihnya: 0,30 m/s adalah **1,58×** kecepatan tertinggi yang pernah
diukur, dan `u` yang dibutuhkan sekitar 45–65% di atas perintah tertinggi
yang pernah dikirim. Belum ada data di rentang itu — termasuk belum ada
pengamatan nyendet, arus, atau tegangan baterai di atas 1,0 rps.

**Catatan penerapan — kondisi Pi per 2026-10-21:**

- `safety.py:32` di checkout Pi **masih `0.30`**, dan `git diff` kosong.
- Di working tree Windows, `max_linear_x` kabarnya sudah 0,19, tetapi
  **belum di-push** dan belum ada di Pi.
- Jadi jangan menulis seolah batas 0,19 sudah diterapkan di Pi. Yang benar:
  batas kode di Pi masih 0,30 sementara bukti hanya sampai 0,19.

**Tingkat risiko hari ini: rendah**, karena `SerialChassisAdapter` masih
menolak mengirim (placeholder) dan hanya `OfflineChassisAdapter` yang
dipakai. Risikonya menjadi nyata begitu transport serial disambungkan —
konstanta 0,30 akan mengizinkan 1,58× di atas apa pun yang pernah diuji.

## 12. Audit metode — enam klaim yang harus dicabut

Dicatat agar tidak masuk dokumen berikutnya:

1. "Rasio naik seiring kecepatan" → **belum terbukti** (§7.2).
2. "Konsisten dengan losses rendah pada rpm rendah" → arah hubungannya
   terbalik dan tidak diukur; **dibuang**.
3. "`v ≈ 19,8u − 0,8` sebagai model empiris" → **ditolak** (§7.3).
4. "Free-wheel 0,5 rps cocok dengan lantai 0,531 rps" → bukan cocok,
   selisihnya di dalam noise dan urutannya fisis mustahil (§8.2).
5. "Cocok dengan URDF 65,8 mm" → 65,8 adalah **inferensi**, dan 64,5 mm
   sama-sama di dalam 1σ (§10).
6. "Rasio 19% menjelaskan motor tidak mencapai kecepatan" → **digantikan**
   (§9); tidak ada yang terbukti tentang penyebabnya.

Dan satu yang harus ditambahkan ke daftar keterbatasan: **semua jarak
diukur dengan penggaris di lantai, tanpa garis start/finish tetap.** Offset
tetap 4,9 cm yang muncul di §7.2 bisa berasal dari sini, bukan dari robot.

## 13. Sisa pekerjaan

Diurutkan menurut nilai per usaha. Butir 1 dan 5 bisa dikerjakan **tanpa
aktuasi** (butir 5 cukup mendengarkan port sambil roda didorong tangan).

| # | Pekerjaan | Menjawab | Perkiraan biaya |
| --- | --- | --- | --- |
| 1 | **Roll-out 10 putaran × 3 trial** (robot mati, meteran, garis start tetap) | menurunkan galat `C_eff` dari ±8,9% ke ~±3% **bila** galat itu didominasi hitung putaran; bila tidak, perbaikan lebih kecil | nol risiko, 10 menit |
| 2 | **Uji durasi: `u`=0,6 pada 3 s vs 9 s** | memisahkan "rasio konstan" dari "offset 4,9 cm" | lantai ~1,2 m |
| 3 | **Free-wheel 20 putaran** dengan stopwatch (bukan menaksir) | loss bebas vs berbeban, resolusi ±2,5% | roda terangkat |
| 4 | **Putar di tempat dan geser samping** (`1:+,2:+,3:+,4:+` dan pola samping) | dua gerak mecanum yang belum pernah diuji | area kosong |
| 5 | **Encoder / odometri** | apakah ada kanal umpan balik roda sama sekali | pengamatan lebih lama |
| 6 | Naikkan kecepatan bertahap 1,2 → 1,4 → 1,6 rps | apakah 0,30 m/s terjangkau dan aman | **setelah 1–3** |

Prediksi untuk butir 2, supaya hasilnya bisa langsung dinilai
(`C_eff` = 20,72 cm):

| Durasi | Model rasio 0,885 | Model offset 4,89 cm | Selisih |
| --- | --- | --- | --- |
| 3 s | 33,0 cm | 32,4 cm | 0,6 cm (tidak terpisah) |
| 9 s | 99,0 cm | 107,0 cm | **8,0 cm (terpisah)** |

Butir 1 menurunkan ambang noise dari 9 poin persen ke ~3 poin persen (dengan
syarat di tabel), dan itu prasyarat agar butir 2 dan 3 bisa disimpulkan.
Kerjakan 1 lebih dulu. Kalau galat `C_eff` ternyata **tidak** turun setelah
10 putaran, berarti sebarannya bukan dari hitung putaran — dan itu sendiri
informasi penting: lintasan dorong atau permukaan lantai yang bervariasi.

## 14. Ringkasan status bukti

| Klaim | Grade | Bukti |
| --- | --- | --- |
| Satuan perintah adalah **rps**, bukan rad/s | **TERVERIFIKASI** | free-wheel 3,75–5 putaran/10 s vs prediksi rad/s 0,95 (§8.1) |
| `C_eff = 20,72 ± 1,84 cm` | **TERUKUR** | roll-out 3 putaran × 3 trial (§6) |
| `D_eff` ≈ 6,6 cm; 55 mm salah, 64–66 mm mungkin | **TERUKUR / INFERENSI** | §6, §10.2 |
| `D` = 65,8 mm | **INFERENSI** | PDF hlm. 9/14/15; tak dapat diverifikasi ulang di Pi (§10.1) |
| `L` = 145 mm, `H` = 135 mm | **TERUKUR** | penggaris; pabrik 147,5/133,54 mm |
| Rasio lantai 83–92% | **TERUKUR** | §7, dengan galat ±9,4 poin |
| Tren rasio terhadap kecepatan | **TIDAK TERBUKTI** | 1,08σ dan 1,85σ; χ² = 0,58 (§7.2) |
| `v ≈ 18,2u` (0,3–1,0 saja) | **TITIK KERJA** | regresi 3 titik; intersep tak signifikan (§7.3) |
| `v ≈ 19,8u − 0,8` | **DITOLAK** | bertentangan dengan stall 0,15 rps (§7.3) |
| Kecepatan tertinggi teruji 0,19 m/s | **TERUKUR** | `u` = 1,0, 57 cm / 3 s |
| 0,30 m/s tercapai | **TIDAK DIKETAHUI** | butuh `u` ≈ 1,45–1,65, belum diuji (§11) |
| Batas 0,19 sudah diterapkan di Pi | **SALAH** | `safety.py:32` masih 0,30; `git diff` kosong |
| Penyebab klaim 19% | **TIDAK DIKETAHUI** | hanya digantikan, bukan dijelaskan (§9) |
| Ada kanal encoder | **TIDAK DIKETAHUI** | belum ada di pengamatan 8 s (sesi 2 §9.2) |

**Yang berubah dari sesi 2 ke sesi 3:** dari "kecepatan efektif hanya 19%,
penyebab tidak diketahui, kemungkinan faktor skala satuan 1/5" menjadi
"satuan rps, rasio 83–92% dengan galat ±9 poin, penyebab sisa belum
terpisah antara rasio konstan dan offset jarak tetap".
