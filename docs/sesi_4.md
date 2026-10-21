# Sesi 4 — Menutup Ketidakpastian `C_eff` dan Memisahkan Model Rasio vs Offset

**Status: PARKED (21 Oktober 2026).** Priority operator berubah: target
"dashboard bisa menggerakkan robot" lebih penting daripada pemisahan model
rasio vs offset, dan video dibatalkan. Isi dokumen ini **tidak** dikerjakan
lagi untuk sekarang; ia tetap berguna sebagai protocol kalau kalibrasi
dipilih lagi nanti. Plan yang aktif ada di
`docs/rencana_chassis_live.md`.

**Status:** **PROTOCOL SIAP — DATA BELUM ADA.** Sesi 4 belum melakukan aktuasi
dari repo ini. Mesin penyusun adalah Windows tanpa `/dev/ttyACM0`, dan akses SSH
ke `stematel-pi5` ditolak (`Permission denied (publickey,password)`), sehingga
ketiga eksperimen harus dijalankan di Lander oleh operator. **Semua tabel data
di dokumen ini sengaja dibiarkan kosong**; angka tidak boleh diisi dengan
perkiraan.

**Tanggal:** 2026-10-21 (WIB, UTC+07:00)
**Host penyusun:** Windows (`D:\Telkom_sch\RobotCeunahh\AMR_LKS_Dashboard`)
**Repo Pi:** `/home/stematelpi5/AMRTestLander/AMR_LKS_Dashboard`
**Alat bantu analisis:** `scripts/analyze_sesi4.py` (komputasi offline, tanpa
port serial)

Peta dokumen:

| Bagian | Isi | Aktuasi? |
| --- | --- | --- |
| §1–§3 | baseline sesi 4, tujuan, dan mengapa urutan eksperimen begitu | tidak |
| §4 | aturan umum prosedur (rujukan, garis tetap, spotter, E-stop) | tidak |
| §5 | eksperimen 1: roll-out 10 putaran × 3 | tidak (robot mati) |
| §6 | eksperimen 2: durasi 3 s vs 9 s | **ya** |
| §7 | eksperimen 3: free-wheel 20 putaran | **ya** (roda terangkat) |
| §8 | kerangka analisis: fit model, residual, mechanism offset | tidak |
| §9 | status bukti | tidak |
| §10 | apa yang TIDAK boleh diklaim | tidak |
| §11 | keputusan dan langkah berikutnya | tidak |
| Lamp. A–C | lembar catatan, checklist lantai, paket perintah | tidak |

Grade bukti yang dipakai sama seperti sesi 3:

| Grade | Arti |
| --- | --- |
| **TERUKUR** | diukur di robot ini, alat dan prosedurnya dicatat |
| **TERVERIFIKASI** | dikonfirmasi lewat pembacaan langsung (protokol, port, berkas) |
| **INFERENSI** | diturunkan dari dokumen, bukan dibaca di sumber primer |
| **SOURCE-ONLY** | hanya dari dokumentasi pabrik, belum dicek di robot ini |
| **HIPOTESIS** | kandidat penjelasan, belum terpisah dari kandidat lain |
| **TIDAK DIKETAHUI** | belum ada bukti apa pun |

---

## 1. Baseline sesi 4

Semua baris di tabel ini **diverifikasi langsung** dari repo ini pada
2026-10-21, bukan diambil dari catatan sesi sebelumnya.

| Pemeriksaan | Perintah | Hasil |
| --- | --- | --- |
| HEAD | `git log --oneline -5` | `664b092 fix: cap linear_x at measured 0.19 m/s` |
| Sinkron dengan remote | `git pull --ff-only` | `Already up to date.` |
| Kebersihan working tree | `git status --short` | **kosong** |
| Test suite | `python -m pytest -q` | **318 passed** (15,35 s) |
| Linter | `python -m ruff check .` | **All checks passed!** |
| Batas kecepatan | `src/amr_core/robot/safety.py:32` | `max_linear_x: float = 0.19` ✓ |

### 1.1 Koreksi atas catatan §11 sesi 3

`docs/sesi_3.md` §11 menulis bahwa `safety.py` di checkout Pi masih `0.30`.
**Catatan itu adalah snapshot commit `780bb00`, bukan kondisi sekarang.**
Commit `664b092` menurunkan batas default menjadi `0,19` dan menambah tes
regresinya (`tests/test_robot_safety.py::test_default_linear_x_cap_matches_tested_speed`).

Yang **benar** per 2026-10-21:

- Batas di repo ini (dan setelah `git pull` di Pi) adalah **0,19 m/s**.
- Yang belum terverifikasi adalah **isi checkout Pi**: `git pull` di Pi belum
  dijalankan pada sesi ini, jadi versi Pi diasumsikan sudah ikut karena commit
  yang sama, tetapi belum dibuktikan.
- `max_linear_y = 0,30` dan `max_angular_z = 1,20` **tidak diubah** — gerak
  samping dan putar belum pernah diuji (lihat §10).

### 1.2 Keterbatasan akses pada sesi ini

| Kebutuhan | Status di mesin penyusun |
| --- | --- |
| `/dev/ttyACM0` | tidak ada (Windows) |
| SSH ke `stematel-pi5` | ditolak: `Permission denied (publickey,password)` |
| Pengukuran fisik di Lander | tidak tersedia |
| Video | tidak tersedia |

Konsekuensi: dokumen ini berisi **protokol, prediksi, dan kerangka analisis** —
bukan hasil. Isian data serta analisis final diisi setelah operator mengembalikan
lembar catatan (Lampiran A).

---

## 2. Tujuan sesi 4

Dua target, berurutan, dan **tidak** termasuk menaikkan kecepatan:

1. **Tutup ketidakpastian `C_eff`.** Sesi 3 mengukur `C_eff = 20,72 ± 1,84 cm`
   (CV 8,9 %) dari 3 percobaan roll-out 3 putaran. Galat 8,9 % itu **sebesar
   efek yang ingin dideteksi**, sehingga semua prediksi jarak mewarisi
   ketidakpastian yang sama.
2. **Pisahkan dua model yang masih hidup** (§7.2 sesi 3):
   - (a) **rasio konstan** `d = r · u · C · T`, `r ≈ 0,885`;
   - (b) **offset jarak tetap** `d = u · C · T − k`, `k ≈ 4,89 cm`.

Yang **bukan** tujuan sesi 4: menguji `u > 1,0`, menguji 0,30 m/s, menaikkan
`max_linear_x`, atau memindahkan `max_linear_y`/`max_angular_z`.

---

## 3. Mengapa urutan eksperimen harus begitu

### 3.1 Galat `C_eff` mengaburkan daya pemisah model

Pemisah kedua model pada `u = 0,6` dan `T = 9 s` hanya **8,0 cm**. Band 1σ
prediksi yang lahir dari `σ_C = 1,84 cm` (relatif 8,88 %) adalah:

| Prediksi | Nilai | Band 1σ dari `C_eff` saja |
| --- | --- | --- |
| Rasio, 9 s | 99,0 cm | 90,2 – 107,8 cm |
| Offset, 9 s | 107,0 cm | 97,5 – 116,5 cm |

**Kedua band itu saling menimpa.** Dengan `C_eff` sesi 3, percobaan 2 tidak
mampu memisahkan kedua model hanya lewat perbandingan angka terhadap
prediksi. Karena itu roll-out 10 putaran harus lebih dulu.

Kalau eksperimen 1 menurunkan CV ke ~3 % (`σ_C ≈ 0,62 cm`):

| Prediksi | Nilai | Band 1σ setelah `C_eff` membaik |
| --- | --- | --- |
| Rasio, 9 s | 99,0 cm | 96,1 – 102,0 cm |
| Offset, 9 s | 107,0 cm | 103,8 – 110,2 cm |

Sekarang ambang keputusan 101 cm / 105 cm berada di antara kedua band, dan
sedangkan galat penggaris (±1 cm per trial, SEM ±0,58 cm untuk mean 3 trial) masih
jauh di bawah lebar pita pemisah.

### 3.2 Cadangan: uji yang tidak bergantung pada `C_eff`

Ada satu aspek yang **tidak** memerlukan `C_eff` sama sekali dan tersedia dari data
durasi yang akan dikumpulkan, sehingga percobaan 2 tetap menghasilkan
keputusan walau eksperimen 1 gagal menurunkan galat:

```
D = Y9 − 3 · Y3
```

| Model | Prediksi `D` |
| --- | --- |
| Rasio konstan (`d = r·u·C·T`) | **0** |
| Offset tetap (`d = u·C·T − k`) | **+2k ≈ +9,8 cm** |

Alasannya: `C` muncul sebagai faktor yang sama di kedua prediksi, sehingga
selisih durasi membatalkan `C` secara analitis. Dengan galat per-trial ±1 cm
dan 3 trial per durasi, `σ_D ≈ 1,83 cm`, jadi jarak model offset dari
prediksi rasio adalah **≈ 5,3σ**. Uji inilah yang dipakai sebagai
**pembuat keputusan utama**, sedangkan ambang 101 cm / 105 cm dipakai sebagai
pembuat keputusan kedua (keduanya harus searah; kalau tidak, lihat §6.5).

---

## 4. Aturan umum prosedur

Aturan ini berlaku untuk **ketiga** eksperimen, dan sebagian di antaranya
membetulkan kelemahan protokol sesi 3 yang tercatat di §12 sesi 3
("semua jarak diukur dengan penggaris di lantai, tanpa garis start/finish
tetap").

1. **Rujukan yang sama.** Titik acuan pada robot yang sama harus dipakai
   untuk garis start **dan** garis finish. Contoh yang dipakai: **titik
   kontak roda depan-kiri dengan lantai**. Kalau titik acuan start berbeda dari
   titik acuan finish, selisih geometri chassis (mis. overhang) masuk ke
   angka sebagai offset konstan — persis bentuk "offset 4,9 cm" yang sedang
   diuji. Ini kontrol utama untuk memisahkan bias pengukuran dari losses
   robot (§8.3).
2. **Garis start/finish tetap** di lantai, ditandai spidol/meteran, tidak
   digeser antar trial.
3. **Hitung putaran dengan titik acuan yang sama** pada roda (bukan hitungan
   visual sudah benar di sesi 3, tapi sekarang titik acuannya dibuat eksplisit
   dan diikat ke garis start).
4. **Alat ukur**: penggaris/meteran. Batas presisi yang diakui: **±1 cm**.
   Jangka sorong belum dipakai.
5. **E-stop fisik dalam jangkauan**, tangan operator di atasnya, selama robot
   bergerak.
6. **Spotter**: satu orang lain yang berdiri di samping dan siap menekan
   E-stop. Uji lantai **wajib** memakai spotter.
7. **Tidak ada `--yes`** untuk uji lantai. Perintah `--confirm` tanpa `--yes`
   memaksa operator mengetik `MOVE` secara manual di prompt, dan checklist
   bawaan `wheel_test.py` (yang mengasumsikan roda terangkat) **tidak boleh
   dianggap terpenuhi** untuk uji lantai. Gunakan checklist lantai di
   Lampiran B.
8. **Tidak ada yang diubah di kode** selama pengambilan data. `wheel_test.py`
   dipakai apa adanya; kalau perlu perilaku lain, buat perintah baru — jangan
   mengubah skrip di tengah eksperimen.

---

## 5. Eksperimen 1 — Roll-out 10 putaran × 3

### 5.1 Protokol

- Robot **mati** (power motor off), tidak ada aktuasi, port tidak dibuka.
- Letakkan garis start tetap; robot ditempatkan dengan satu titik acuan roda
  tepat di garis start.
- Dorong robot **lurus** sepanjang garis, hitung **10 putaran penuh**, tandai
  posisi titik acuan roda yang sama saat putaran ke-10 selesai.
- Ukur jarak antara dua tanda dengan penggaris (±1 cm).
- Ulangi **3 kali**, dan **balik arah dorongan** pada trial kedua (dicek
  apakah bias arah dorongan berperan).

### 5.2 Data (menunggu)

| Trial | Arah dorong | Jarak 10 putaran (cm) | `C_eff = d/10` (cm) |
| --- | --- | --- | --- |
| 1 | maju | — | — |
| 2 | mundur | — | — |
| 3 | maju | — | — |

| Statistik | Nilai |
| --- | --- |
| Rata-rata | — |
| Simpangan baku sampel (n−1) | — |
| Median | — |
| Rentang 1σ | — |
| Koefisien variasi | — |
| Target mean | ≈ 20,7 cm |

### 5.3 Arti setiap kemungkinan hasil

| Hasil | Bacaan | Konsekuensi untuk sesi 4 |
| --- | --- | --- |
| CV turun ke ~3 % | galat lama **didominasi hitung putaran** | `C_eff` bisa dipakai sebagai pembagi kinematika; prediksi 9 s menyempit ke ±3 cm (§3.1) |
| CV tetap ~9 % | galat **bukan** dari hitung putaran; berasal dari lintasan dorong / permukaan lantai / penandaan | percobaan 2 **tetap** menghasilkan keputusan, tetapi lewat uji tanpa-`C_eff` (§3.2), bukan lewat ambang angka |
| CV naik, mean bergeser jauh dari 20,7 cm | ada bias sistematis pada protokol roll-out | `C_eff` sesi 3 **diragukan**; seluruh prediksi sesi 3 harus dihitung ulang |

---

## 6. Eksperimen 2 — Durasi `u = 0,6` pada 3 s vs 9 s

### 6.1 Prasyarat

- Lantai minimal **1,5 m** bebas di arah gerak, garis start **sama** dengan
  eksperimen 1.
- E-stop dalam jangkauan, **spotter** standby (§4).
- Robot sudah diuji bisa berhenti (stop frame selalu dikirim di blok
  `finally`).

### 6.2 Perintah

Pola maju terverifikasi sesi 3: `1:−`, `2:−`, `3:+`, `4:+`.

```
# 3 detik
../.venv/bin/python scripts/wheel_test.py --confirm --port /dev/ttyACM0 --rate 50 --duration 3 --speeds "1:-0.6,2:-0.6,3:+0.6,4:+0.6"

# 9 detik
../.venv/bin/python scripts/wheel_test.py --confirm --port /dev/ttyACM0 --rate 50 --duration 9 --speeds "1:-0.6,2:-0.6,3:+0.6,4:+0.6"
```

**Tanpa `--yes`.** Ketik `MOVE` manual. Kerjakan checklist lantai (Lampiran B),
bukan checklist bawaan yang mengasumsikan roda terangkat.

### 6.3 Data (menunggu)

| Durasi | Trial 1 (cm) | Trial 2 (cm) | Trial 3 (cm) | Mean (cm) | sd (cm) |
| --- | --- | --- | --- | --- | --- |
| 3 s | — | — | — | — | — |
| 9 s | — | — | — | — | — |

Catatan operator per trial: **jarak diukur dari garis start tetap ke posisi
titik acuan roda yang sama** (§4.1).

### 6.4 Prediksi dan aturan keputusan

Dengan `C_eff = 20,72 cm`, `r = 0,885`, `k = 4,89 cm`:

| Durasi | Model rasio | Model offset | Selisih | Status |
| --- | --- | --- | --- | --- |
| 3 s | 33,0 cm | 32,4 cm | 0,6 cm | **belum terpisah** |
| 9 s | 99,0 cm | 107,0 cm | **8,0 cm** | **terpisah** |

Aturan keputusan (mean 9 s):

| Mean 9 s | Keputusan |
| --- | --- |
| ≤ 101 cm | model **rasio konstan** |
| ≥ 105 cm | model **offset tetap** |
| 101 – 105 cm | **belum konklusif** — ulangi trial dan/atau periksa video |

Pita "belum konklusif" lebar 4 cm, ±2 cm dari titik tengah 103,0 cm; dengan
SEM mean 3 trial ±0,58 cm, pita itu ≈ ±3,5 SEM. Ulangan trial sudah harus
dilakukan **sebelum** menyimpulkan apa pun.

### 6.5 Kalau dua alat keputusan tidak searah

Kalau ambang 101/105 dan uji tanpa-`C_eff` (§3.2) berbeda arah, **tidak ada
yang dapat disimpulkan** dan tabel §9 ditulis `BELUM KONKLUSIF`. Urutan yang
benar: (1) cek ulang protokol pengukuran trial — apakah titik acuan start sama
dengan titik acuan finish (§4.1); (2) cek video start-up; (3) ulangi trial 9 s
dengan 5 trial.

### 6.6 Video (wajib direkam)

Rekam **setiap** trial 3 s dan 9 s dari samping, konstan, dengan titik acuan
terlihat. Gunanya mengukur **waktu mulai** (lihat §8.3): apakah robot diam
beberapa saat sebelum bergerak (dead time), atau bergerak langsung tapi
mempercepat (ramp). Bedakan keduanya dari video.

---

## 7. Eksperimen 3 — Free-wheel 20 putaran (roda terangkat)

### 7.1 Protokol

- Roda **terangkat** (robot stabil, aman, tidak ada yang bisa masuk roda).
- `u = 0,6` rps, pola yang sama.
- **2 putaran pemanasan**, lalu stopwatch dijalankan tepat saat putaran ke-3
  dimulai, dan dihentikan saat putaran ke-22 selesai.
- Ulangi 3 kali.

Perkiraan durasi: 20 putaran pada 0,6 rps = **33,3 s**; pada 0,5 rps =
**40,0 s**. Dengan 2 putaran pemanasan (22 putaran total): 36,7 s pada
0,6 rps, 44,0 s pada 0,5 rps.

### 7.2 Perintah

```
../.venv/bin/python scripts/wheel_test.py --confirm --port /dev/ttyACM0 --rate 50 --duration 45 --speeds "1:-0.6,2:-0.6,3:+0.6,4:+0.6"
```

`--duration 45` memberi margin untuk 22 putaran pada laju 0,5 rps (44,0 s).
**Kalau robot belum menyelesaikan 22 putaran pada 45 s, ulangi dengan
`--duration 60`** — jangan mengukur putaran yang tidak selesai.

### 7.3 Data (menunggu)

| Trial | Putaran (pemanasan + diukur) | Waktu 20 putaran (s) | Laju (rps) |
| --- | --- | --- | --- |
| 1 | 2 + 20 | — | — |
| 2 | 2 + 20 | — | — |
| 3 | 2 + 20 | — | — |

| Statistik | Nilai |
| --- | --- |
| Mean laju free-wheel | — |
| sd | — |
| Laju perintah | 0,600 rps |
| Laju lantai acuan (sesi 3) | 0,531 rps |

### 7.4 Arti setiap kemungkinan hasil

| Hasil | Bacaan | Konsekuensi |
| --- | --- | --- |
| ≈ 0,60 rps | motor **mencapai** kecepatan perintah tanpa beban | defisit lantai masuk akal sebagai beban/slip atau start-up; rasio 0,885 boleh dibaca sebagai efektivitas lantai |
| ≈ 0,50 rps | free-wheel **lebih lambat** dari laju lantai (0,531 rps) — secara fisis mustahil | ada yang salah di `C_eff` atau di pengukuran jarak; **jangan** tafsirkan sebagai efisiensi |
| 0,53 – 0,57 rps | free dan lantai praktis sama | selisih di dalam noise; **tidak boleh** dipakai sebagai faktor kalibrasi |

Resolusi: dengan 20 putaran dan stopwatch, galat ≈ ±2,5 %. Amortisasi
start-up diabaikan aman: bahkan ramp 0,9 s hanya kehilangan ~0,27 putaran dari
22 (1,2 %), jauh di bawah resolusi.

---

## 8. Kerangka analisis

### 8.1 Alat

`scripts/analyze_sesi4.py` menghitung semuanya dari satu berkas JSON:

```
python scripts/analyze_sesi4.py data.json
python scripts/analyze_sesi4.py data.json --c-eff 20.72 --c-eff-sd 0.58
```

Skrip ini **tidak** membuka port serial dan **tidak** mengirim perintah motor.
Yang dihitung: statistik `C_eff`, prediksi kedua model, aturan keputusan, uji
tanpa-`C_eff`, fit ketiga model (rasio / offset / gabung) dengan residual, rms
dan χ², serta laju free-wheel.

Catatan rms: skrip memakai pembagi `(n − p)` (simpangan baku residual).
Sesi 3 memakai pembagi `n`, jadi angka rms sesi 3 dan skrip ini **tidak**
boleh dibandingkan langsung (untuk 3 titik: 1,45 cm vs 1,77 cm untuk model
rasio). χ² skrip memakai σ = 1 cm (galat penggaris).

### 8.2 Model yang diadu

Dengan `X = u · C · T` (jarak perintah, cm) dan `Y` (jarak terukur):

| Model | Bentuk | Parameter |
| --- | --- | --- |
| M1 rasio konstan | `Y = r · X` | 1 (`r`) |
| M2 offset tetap | `Y = X − k` | 1 (`k`) |
| M3 gabung | `Y = r · X − k` | 2 (`r`, `k`) |

Penilaian: rms sisa, χ² terhadap derajat kebebasan, dan **pola residual**
(apakah sisa systematikal terhadap `u` atau `T`). Model menang bukan karena
rms-nya paling kecil saja, tetapi karena sisa-sisanya **tidak sistematikal**.

### 8.3 Kalau offset menang: start delay atau bias pengukuran?

Ini pertanyaan lanjutan yang harus dijawab **berurutan**, karena dua
mekanisme itu punya tanda berbeda.

Data sesi 3 (§7 sesi 3) memberi defisit jarak per titik:

| `u` | `v` (cm/s) | Defisit (cm) | Defisit sebagai waktu (s) |
| --- | --- | --- | --- |
| 0,3 | 5,15 | 5,33 | 1,034 |
| 0,6 | 11,00 | 4,30 | 0,391 |
| 1,0 | 19,00 | 5,16 | 0,272 |

Defisit **hampir konstan dalam sentimeter** (sd 0,55 cm) tetapi **tidak
konstan dalam detik** (1,03 → 0,27 s). Ini penting, karena:

| Mekanisme | Bentuk defisit | KONSEKUENSI |
| --- | --- | --- |
| Dead time (robot diam sejenak lalu jalan penuh) | `v · t_d` — **∝ v** | harus naik proporsional dengan kecepatan; data sesi 3 **menolaknya** |
| Ramp (robot jalan lalu dipercepat) | `½ · v · t_a` — **∝ v** | sama: harus ∝ v; data sesi 3 **menolaknya** |
| Loss jarak tetap (slip tetap, bias rujukan, kehilangan tetap) | `k` — **konstan** | cocok dengan data sesi 3 |

Artinya: **kalau model offset menang di 9 s, penjelasan "robot terlambat mulai"
hanya bisa diterima kalau delay-nya sendiri sebanding dengan 1/v** — dan itu
tidak masuk akal. Yang lebih mungkin adalah **bias rujukan atau kehilangan
jarak tetap**. Sesi 3 memang mencatat kelemahan ini secara eksplisit (§12
sesi 3): "semua jarak diukur dengan penggaris di lantai, tanpa garis
start/finish tetap".

Konsekuensi praktis: kontrol bias rujukan **sudah dilegur di §4.1** (rujukan
yang sama di start dan finish). Kalau setelah kontrol itu offset 4,9 cm tetap
muncul, maka offset itu **real**, bukan artefak penandaan — dan barulah video
dipakai untuk membedakan dead time vs ramp vs kehilangan tetap.

**Prediksi kuantitatif untuk video** (kalau `k = 4,93 cm` dan laju steady
`v_ss`):

| Mekanisme | Tanda yang harus terlihat di video | Angka yang diharapkan |
| --- | --- | --- |
| Dead time | robot diam dulu, lalu jalan pada laju penuh | `t_d = k / v_ss` ≈ **0,45 s** pada `u = 0,6` |
| Ramp | robot jalan langsung, lalu mempercepat ke laju penuh | `t_a = 2k / v_ss` ≈ **0,90 s** pada `u = 0,6` |
| Loss jarak tetap | tidak ada tanda khusus di video; jarak hilang tetap | video normal, tapi jarak tetap kurang ~4,9 cm |

Aturan: kalau video **tidak** menunjukkan delay/ramp sepanjang ~0,9 s, maka
mekanismenya **TIDAK DIKETAHUI** — jangan menulis "start delay" sebagai
penyebab.

Catatan pembukaran: sesi 3 menulis rata-rata defisit **4,89 cm**; hitung ulang
dari tabelnya sendiri menghasilkan **4,93 cm** (selisih 0,04 cm, tidak
mengubah apa pun). Angka 4,89 dipakai di prediksi §6.4 sesuai angka yang diberikan untuk sesi 4;
untuk perhitungan turunan di dokumen ini dipakai 4,93 cm.

### 8.4 Hipotesis turunan yang murah diuji (tanpa aktuasi)

Satu kandidat bias rujukan yang bisa diuji tanpa robot bergerak: **overhang
chassis di depan poros roda depan**. Kalau angka konstanta offset ~4,9 cm
kebetulan sama dengan jarak dari poros roda depan ke tepi depan chassis,
maka offset itu artefak penandaan — dan nilainya harus cocok setelah diukur
dengan penggaris. Ini **HIPOTESIS**, belum diuji; mengukurnya hanya perlu
penggaris dan tidak menambah risiko.

---

## 9. Status bukti (menunggu data)

| Klaim | Grade | Bukti |
| --- | --- | --- |
| Batas `max_linear_x` = 0,19 m/s di repo ini | **TERVERIFIKASI** | `src/amr_core/robot/safety.py:32`, HEAD `664b092` (§1) |
| Test suite 318 passed, ruff bersih | **TERVERIFIKASI** | §1 |
| `C_eff` sesi 3 = 20,72 ± 1,84 cm | **TERUKUR** | sesi 3 §6 |
| `C_eff` sesi 4 (10 putaran × 3) | **TIDAK DIKETAHUI** | menunggu eksperimen 1 |
| Model rasio konstan menang | **TIDAK DIKETAHUI** | menunggu eksperimen 2 |
| Model offset tetap menang | **TIDAK DIKETAHUI** | menunggu eksperimen 2 |
| Offset berasal dari start delay | **HIPOTESIS** | harus lewat video; data sesi 3 melawannya (§8.3) |
| Offset berasal dari bias rujukan | **HIPOTESIS** | kontrol rujukan §4.1 akan menyingkirkannya |
| Laju free-wheel | **TIDAK DIKETAHUI** | menunggu eksperimen 3 |
| Efektivitas motor di rpm rendah | **TIDAK DIKETAHUI** | tidak ada pengukuran torsi/arus; jangan diklaim |
| Kecepatan 0,30 m/s | **TIDAK DIKETAHUI** | di luar cakupan sesi 4 |

---

## 10. Apa yang TIDAK boleh diklaim (terus berlaku)

1. "Rasio naik seiring kecepatan" → **belum terbukti** (sesi 3 §7.2).
2. "Konsisten dengan losses rendah pada rpm rendah" → **dibuang** (sesi 3 §12).
3. "`v ≈ 19,8u − 0,8`" → **ditolak** (sesi 3 §7.3).
4. "Free-wheel 0,5 rps cocok dengan lantai 0,531 rps" → **bukan cocok**
   (sesi 3 §8.2; §7.4 sesi ini).
5. "Cocok dengan URDF 65,8 mm" → 65,8 mm adalah **INFERENSI** (sesi 3 §10).
6. "Rasio 19% menjelaskan motor tidak mencapai kecepatan" → **digantikan**
   (sesi 3 §9).
7. "Offset 4,9 cm = start delay" → **belum**, dan data sesi 3 secara kuantitatif
   melawannya (§8.3). Tulis "hipotesis", bukan penyebab.
8. **Nilai baru apa pun** tidak boleh masuk dokumen ini sebelum diukur di
   Lander. Tabel kosong berarti belum diukur.

---

## 11. Keputusan dan langkah berikutnya

### 11.1 Keputusan sesi ini

- **Tidak ada kenaikan kecepatan.** Batas `max_linear_x` tetap **0,19 m/s**.
- `max_linear_y = 0,30` dan `max_angular_z = 1,20` **tidak** disentuh.
- Tidak ada uji `u > 1,0`, tidak ada uji 0,30 m/s.
- Sesi 4 **belum menghasilkan temuan empiris baru**; yang dihasilkan adalah
  protokol yang bisa dieksekusi dan alat analisis offline.

### 11.2 Urutan kerja

| # | Pekerjaan | Menjawab | Aktuasi | Biaya |
| --- | --- | --- | --- | --- |
| 1 | Roll-out 10 putaran × 3 (§5) | galat `C_eff` | tidak | ~10 menit |
| 2 | Durasi 3 s vs 9 s, 3 trial, + video (§6) | rasio vs offset | ya | ~1,5 m lantai |
| 3 | Free-wheel 20 putaran (§7) | free vs beban | ya (roda atas) | ~5 menit |
| 4 | Analisis dengan `scripts/analyze_sesi4.py` + isi §9 | model yang menang | tidak | offline |
| 5 | Jika offset menang: ukur overhang chassis (§8.4) | bias rujukan? | tidak | 1 menit |
| 6 | Jika offset menang dan overhang tidak cocok: baca video | start delay vs lain | tidak | offline |

### 11.3 Prasyarat sebelum kecepatan boleh naik lagi

Semua ini harus **terpenuhi**, bukan "dipertimbangkan":

1. `C_eff` punya CV ≤ ~3 % (eksperimen 1).
2. Model yang menang sudah ditentukan eksperimen 2 dan lolos uji tanpa-`C_eff`
   dengan arah yang sama.
3. Sumber offset, kalau offset menang, sudah terisolasi (bias rujukan vs
   start delay vs loss tetap). Kalau belum terisolasi, **tidak** ada alasan
   untuk menaikkan kecepatan.
4. Uji 0,30 m/s baru boleh direncanakan setelah 1–3, di area panjang dengan
   E-stop — **dan tidak dalam sesi ini**.

---

## Lampiran A — Lembar catatan (isi di Lander, kirim balik)

### A.1 Eksperimen 1

```
Roll-out, 10 putaran x 3
Trial 1 (maju)   : jarak ____ cm
Trial 2 (mundur) : jarak ____ cm
Trial 3 (maju)   : jarak ____ cm
Alat ukur        : ______________________
Catatan          : ______________________
```

### A.2 Eksperimen 2

```
u = 0,6 rps, pola 1:-0,6  2:-0,6  3:+0,6  4:+0,6
Video          : nama berkas ______________________

3 s trial 1 : ____ cm      9 s trial 1 : ____ cm
3 s trial 2 : ____ cm      9 s trial 2 : ____ cm
3 s trial 3 : ____ cm      9 s trial 3 : ____ cm

Catatan per trial (ada slip roda? robot belok? mulai lambat?): ______________
```

### A.3 Eksperimen 3

```
Free-wheel, roda terangkat, u = 0,6 rps
Trial 1 : 20 putaran dalam ____ s
Trial 2 : 20 putaran dalam ____ s
Trial 3 : 20 putaran dalam ____ s
Catatan : ______________________________________________________________
```

### A.4 Bentuk JSON untuk `scripts/analyze_sesi4.py`

```json
{
  "rollout": {
    "rotations_per_trial": 10,
    "trials": [
      {"trial": 1, "distance_cm": 0.0},
      {"trial": 2, "distance_cm": 0.0},
      {"trial": 3, "distance_cm": 0.0}
    ]
  },
  "duration": {
    "u_rps": 0.6,
    "trials": [
      {"trial": 1, "duration_s": 3, "distance_cm": 0.0},
      {"trial": 2, "duration_s": 3, "distance_cm": 0.0},
      {"trial": 3, "duration_s": 3, "distance_cm": 0.0},
      {"trial": 1, "duration_s": 9, "distance_cm": 0.0},
      {"trial": 2, "duration_s": 9, "distance_cm": 0.0},
      {"trial": 3, "duration_s": 9, "distance_cm": 0.0}
    ]
  },
  "freewheel": {
    "u_rps": 0.6,
    "trials": [
      {"trial": 1, "rotations": 20, "seconds": 0.0},
      {"trial": 2, "rotations": 20, "seconds": 0.0},
      {"trial": 3, "rotations": 20, "seconds": 0.0}
    ]
  }
}
```

Angka `0.0` adalah **placeholder** — ganti dengan hasil ukur.

---

## Lampiran B — Checklist lantai (menggantikan checklist bawaan)

Checklist bawaan `wheel_test.py` mengasumsikan **roda terangkat**. Untuk uji
lantai gunakan yang ini, dan **jangan** memakai `--yes`.

```
CHECKLIST UJI LANTAI - u = 0,6 rps
[ ] Robot siap di garis start, titik acuan roda yang sama di garis start
[ ] Lantai bebas minimal 1,5 m ke depan, tanpa hambatan
[ ] E-stop fisik dalam jangkauan, tangan di atasnya
[ ] Spotter berdiri di samping, siap menekan E-stop
[ ] Area ukur start/finish sudah ditandai
[ ] Kamera/rekam video siap menghadap titik acuan
[ ] Perintah dieksekusi TANPA --yes, ketik MOVE manual
[ ] Setelah selesai: STOP terkirim, robot diam, dicatat jaraknya
```

---

## Lampiran C — Paket perintah untuk Hermes di Lander

### C.1 Persiapan (di Pi)

```
cd /home/stematelpi5/AMRTestLander/AMR_LKS_Dashboard
git pull --ff-only
git status --short            # harus kosong
git log --oneline -1          # harus 664b092
../.venv/bin/python -m pytest -q
../.venv/bin/python -m ruff check .
ls -l /dev/ttyACM0
fuser -v /dev/ttyACM0         # harus kosong: tidak ada proses memegang port
```

Kalau `git log` menunjukkan commit yang bukan `664b092`, **berhenti** dan
laporkan; jangan lanjutkan uji dengan kode yang tidak diketahui.

### C.2 Eksperimen 1 — roll-out (tanpa aktuasi)

Robot mati, tidak ada perintah motor, port tidak dibuka. Ikuti §5, isi
Lampiran A.1.

### C.3 Eksperimen 2 — durasi (AKTUASI)

```
../.venv/bin/python scripts/wheel_test.py --confirm --port /dev/ttyACM0 --rate 50 --duration 3 --speeds "1:-0.6,2:-0.6,3:+0.6,4:+0.6"
../.venv/bin/python scripts/wheel_test.py --confirm --port /dev/ttyACM0 --rate 50 --duration 9 --speeds "1:-0.6,2:-0.6,3:+0.6,4:+0.6"
```

ulangi tiap baris 3 kali, tanpa `--yes`, dengan checklist lantai (Lampiran B)
dan video aktif. Urutan: 3 s (trial 1–3) → 9 s (trial 1–3).

### C.4 Eksperimen 3 — free-wheel (AKTUASI)

```
../.venv/bin/python scripts/wheel_test.py --confirm --port /dev/ttyACM0 --rate 50 --duration 45 --speeds "1:-0.6,2:-0.6,3:+0.6,4:+0.6"
```

Roda terangkat, 2 putaran pemanasan, stopwatch 20 putaran. 3 kali. Kalau 22
putaran tidak selesai dalam 45 s → ulangi dengan `--duration 60`.

### C.5 Yang perlu dikembalikan

1. Lampiran A terisi (angka mentah, bukan bulatan).
2. Berkas video.
3. Keluaran `python scripts/analyze_sesi4.py data.json` (boleh dikirim apa
   adanya; tidak mengandung aktuasi).
4. Foto/catatan setup lantai dan garis start/finish.

### C.6 Larangan selama sesi

- Tidak mengubah kode, tidak melakukan commit/push.
- Tidak memakai `--yes`.
- Tidak menguji `u > 1,0` maupun 0,30 m/s.
- Tidak mengisi angka yang tidak terukur — kalau satu trial gagal, tulis
  "gagal" beserta alasannya, jangan dikira-kira.
