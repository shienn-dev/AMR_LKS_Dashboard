# Rencana Aktivasi Chassis Langsung (Dashboard → Robot)

**Status:** **RENCANA — belum ada implementasi.** Dokumen ini untuk review
sebelum ada kode yang ditulis.
**Tanggal:** 2026-10-21
**Basis:** HEAD `664b092` (test suite 318 passed, ruff bersih)
**Pemohon:** operator — "aku cuma pengen dari dashboard bisa gerakin robot"

---

## 1. Tujuan

Membuat robot **bergerak dari dashboard NiceGUI** di Pi, lewat jalur yang sudah
diverifikasi di hardware: STM32 di `/dev/ttyACM0`, motor frame func-3, satuan
**rps**.

Target penerimaan (acceptance) versi pertama:

1. Dari browser, operator bisa membuat robot **maju/mundur/samping/putar**,
   selama tombol ditahan.
2. Melepas tombol → robot **berhenti**.
3. Kehilangan koneksi (browser ditutup, Wi-Fi putus, laptop tidur) → robot
   **berhenti sendiri**.
4. Kecepatan di layar **berarti m/s**, bukan angka abstrak.
5. Batas keras **0,19 m/s** tetap berlaku tanpa kecuali.

Yang **bukan** tujuan: arm, kamera, odometri, navigasi otonom, dan
menaikkan `max_linear_x`.

---

## 2. Batasan yang tidak bisa dilanggar

| Batasan | Sumber |
| --- | --- |
| `max_linear_x = 0,19 m/s` — kecepatan tertinggi yang pernah terukur | `src/amr_core/robot/safety.py:32` |
| `max_linear_y = 0,30 m/s`, `max_angular_z = 1,20 rad/s` — **belum pernah diuji**, jadi nilai ini bukan izin | `safety.py:33-34` |
| Tidak boleh menguji `u > 1,0` atau 0,30 m/s | keputusan sesi 3/4 |
| Motor hanya boleh bergerak kalau board terus menerima frame (watchdog) | sesi 2 §9.3 |
| Tidak boleh ada streaming dari dashboard tanpa operator manusia di dekat robot | prinsip proyek (`docs/robot_integration.md` §1) |

---

## 3. Yang sudah ada (tidak perlu ditulis ulang)

| Komponen | Lokasi | Status |
| --- | --- | --- |
| Panel kontrol chassis (maju/mundur/samping/putar/STOP) | `src/amr_dashboard/robot_panel.py:88` | UI ada, submit ke adapter offline |
| Software E-stop + konfirmasi clear | `src/amr_dashboard/robot_panel.py:135` | ada |
| Clamp + validasi perintah | `src/amr_core/robot/safety.py:36-63` | ada, teruji |
| `ChassisAdapter` protocol | `src/amr_core/robot/interfaces.py:111` | ada |
| Encoder frame motor | `scripts/wheel_test.py:81` | **hanya di skrip**, belum di `amr_core` |
| Pembuat frame STM32 + CRC | `src/amr_core/robot/stm32_protocol.py:225` | ada |
| Streaming 50 Hz, penjadwalan absolut, flush akhir | `scripts/wheel_test.py:195-208` | ada, terukur |
| DTR/RTS turun sebelum `open()` | `scripts/wheel_test.py:181-188` | ada, terbukti tidak me-reset board |
| STOP frame di blok `finally` | `scripts/wheel_test.py:214-225` | ada |
| Pemetaan ID motor → roda | sesi 2 §9.5 | **1=FL, 2=RL, 3=FR, 4=RR** |
| Konvensi tanda maju | commit `f8de64e` | **maju = 1:−, 2:−, 3:+, 4:+** (diverifikasi lewat translasi) |
| Geometri `L = 145 mm`, `H = 135 mm` | sesi 3 §10 | terukur |
| Konfigurasi roller ABAB | sesi 2 | dari PDF, belum diuji di robot ini |

---

## 4. Yang belum ada — lima celah

| # | Celah | Dampak |
| --- | --- | --- |
| C1 | `SerialChassisAdapter` masih placeholder yang **menolak** mengirim (`src/amr_core/robot/chassis.py:63`) | tidak ada jalur gerak sama sekali |
| C2 | `robot_runtime.build_adapters()` hardcode `OfflineChassisAdapter` (`src/amr_dashboard/robot_runtime.py:43`) | meski adapter nyata ada, tidak pernah dipilih |
| C3 | Encoder frame motor hanya ada di `scripts/wheel_test.py` | dashboard akan menulis encoder sendiri → risko bercabang, tidak sinkron |
| C4 | Kinematika mecanum belum ada | perlu memetakan (vx, vy, wz) → 4 perintah roda |
| C5 | Tombol sekali-klik = 1 frame = "twitch" | perlu semantik tahan-tekan + fail-safe |

Tambahan dari pilihanmu "semua: maju/mundur/samping/putar": **pola tanda
untuk lateral dan putar belum pernah diverifikasi.** Hanya pola maju yang
terverifikasi translasi. Konvensi tanda sebelumnya **salah** justru karena
ditentukan dengan roda terangkat (rotasi terlihat, translasi tidak) — commit
`f8de64e`. Jadi identifikasi tanda lateral/putar harus jadi **gate**, bukan
asumsi.

---

## 5. Keputusan desain (sudah dipilih)

| Keputusan | Pilihan | Konsekuensi yang harus ditangani |
| --- | --- | --- |
| Semantik gerak | **hold-to-move** | event "lepas" bisa hilang → butuh fail-safe berlapis (§6.4) |
| Cakupan | **maju/mundur/samping/putar** | lateral & putar tanpa pola tanda terverifikasi → gate identifikasi (§6.1) |
| Transport | opt-in eksplisit | default dashboard tetap offline; tidak ada aktuasi tak sengaja |

---

## 6. Rancangan teknis

### 6.1 Kinematika mecanum

Model standar: tiap roda mecanum menggabungkan dua komponen (maju dan lateral)
sesuai posisi roller 45°-nya.

```
ω_FL = k·[(v_x ∓ v_y) + ω_z·(a ± b)]
ω_RL = k·[(v_x ± v_y) − ω_z·(a ∓ b)]
ω_FR = k·[(v_x ∓ v_y) − ω_z·(a ∓ b)]
ω_RR = k·[(v_x ± v_y) + ω_z·(a ± b)]

a = L/2 = 0,0725 m   (jarak roda ke sumbu tengah)
b = H/2 = 0,0675 m
k = 1/(C_eff·r)     (skala m/s → rps, lihat §6.2)
```

**Tanda `∓/±` di atas sengaja tidak dipublikasikan.** Pola lengkap untuk semua
arah adalah hasil **identifikasi**, bukan deduksi: konvensi tanda yang
ter-published sebelumnya terbukti terbalik. Yang harus dilakukan:

**Gate G1 — identifikasi tanda, dua tahap:**

- **Tahap 1 (roda terangkat):** untuk tiap pola, jalankan motor dengan tanda
  kandidat dan amati arah putar tiap roda. Ini mempersempit kandidat.
- **Tahap 2 (lantai):** kandidat yang tersisa harus **dikonfirmasi lewat translasi
  nyata**, persis seperti cara `f8de64e` mengoreksi kesalahan sebelumnya.
  Roda terangkat saja tidak cukup — itu persis cara konvensi yang lama terbukti
  terbalik.

| Uji | Pola yang diuji | Yang diamati | Kriteria lulus |
| --- | --- | --- | --- |
| G1.1 | `1:−,2:−,3:+,4:+` | translasi maju | robot maju (sudah terverifikasi, tapi **ulang** saat gerbang ini) |
| G1.2 | `1:+,2:+,3:−,4:−` | translasi | robot mundur |
| G1.3 | 2 kandidat lateral | translasi | robot meluncur kiri (atau kanan) — bukan berputar |
| G1.4 | 2 kandidat putar | translasi | robot berputar di tempat, arah ditentukan |
| G1.5 | 4 diagonal | translasi | lurch diagonal, bukan gerak majemuk |

Tanpa G1–G1.5, tidak ada gerak yang boleh terjadi di lantai dari dashboard.

### 6.2 Skala m/s → rps, dan ambang stall

Dari `C_eff = 20,72 ± 1,84 cm` (sesi 3 §6) dan rasio `r ≈ 0,885`:

```
u_perintah = v_diminta / (r · C_eff)
```

| `v_diminta` | `u_perintah` | Status |
| --- | --- | --- |
| 0,05 m/s | 0,273 rps | **di zona abu-abu stall** (0,2–0,3 rps) — lihat catatan |
| 0,10 m/s | 0,545 rps | belum pernah diuji |
| 0,19 m/s | 1,036 rps | **tepat u = 1,0 yang terukur 0,19 m/s** |

**Catatan stall (sesi 2 §9.7):** 0,15 rps = berhenti total (bunyi, tidak
bergerak); 0,3 rps = jalan; ambang antara 0,2–0,3 rps. Konsekuensi untuk UX:
**slider kecepatan tidak boleh punya opsi di bawah ~0,06 m/s**, karena robot
akan mendengung tanpa bergerak — dan operator akan mengira tombolnya rusak.
Batas bawah slider sebaiknya **0,06 m/s** (≈0,33 rps, di atas 0,3 rps yang
terbukti jalan) dan diberi label.

Butuh satu keputusan: slider berarti *kecepatan target di lantai* (butuh
kompensasi `r`, robot jadi jalan sesuai angka) atau *kecepatan yang diminta ke
motor* (robot jalan ~11 % lebih lambat dari angka, tapi angkanya jujur).
Rekomendasi: **target di lantai**, karena operator berpikir dalam m/s; dengan
baris readout kedua yang menampilkan kecepatan sebenarnya, dan catatan bahwa
`r` sendiri baru pasti ±11 % sampai sesi 4 selesai.

### 6.3 Adapter serial (C1, C3)

Modul baru `src/amr_core/robot/serial_chassis.py` (mengikuti pola
`amr_core/lidar/reader.py`), berisi:

- `SerialChassisAdapter` yang benar-benar mengirim.
- Thread background pemilik port; **tidak** ada dua penulis port.
- Alur: `submit(cmd)` → validasi + clamp → **set target** (bukan kirim
  sekali) → thread stream frame motor 50 Hz selama target ≠ 0.
- `stop()` → target = 0, kirim frame nol, (opsional) stream nol sebentar
  lalu tutup port.
- `finally` → frame STOP selalu, seperti `wheel_test.py:214`.
- `close()` dipanggil saat dashboard shut down.
- `state()` mengembalikan `CONNECTED` / `DISCONNECTED` / `UNAVAILABLE` yang
  **jujur** (bukan `DISABLED` palsu).

Encoder frame motor pindah ke `src/amr_core/robot/stm32_protocol.py`:

```python
def build_motor_frame(speeds: list[tuple[int, float]]) -> bytes:
    """func-3 MOTOR frame: [0x01, n, (id-1, float32 LE rps) x n]"""
```

`scripts/wheel_test.py` lalu memakai fungsi yang sama — **satu encoder, satu
sumber kebenaran**.

**Risiko khusus dashboard:** ModemManager aktif dan `/dev/ttyACM0` membawa
`ID_MM_CANDIDATE=1` (sesi 3 §1). Kalau ModemManager merebut port saat robot
bergerak, stream putus → **board langsung mematikan motor** (watchdog). Ini
berhasil fail-safe, tapi operator harus diberi tahu: state berubah ke
`DISCONNECTED` + notifikasi keras di panel.

### 6.4 Fail-safe untuk hold-to-move (C5) — bagian terpenting

Risiko utama hold-to-move: **event "lepas" tidak pernah sampai** (mouseup di
luar tombol, browser crash, Wi-Fi putus, laptop tidur, tab ditutup). Kalau
server terus streaming frame, robot terus jalan.

Lapisan pelindung, dari yang paling penting:

| # | Lapisan | Cara kerja | Waktu reaksi |
| --- | --- | --- | --- |
| L1 | **Heartbeat klien** | browser kirim "masih mau gerak" tiap 100 ms; server STOP kalau telat > 300 ms | ≤ 300 ms |
| L2 | **Release global** | `pointerup`, `pointercancel`, `blur`, `visibilitychange` di level dokumen → lepas semua tombol | seketika |
| L3 | **Abort/keyboard** | `keyup` + penolakan auto-repeat; `Escape` melepas semua | seketika |
| L4 | **Disconnect browser** | NiceGUI `app.on_disconnect` → STOP | seketika |
| L5 | **E-stop software** | latch → STOP + tolak perintah baru sampai di-clear | seketika |
| L6 | **Watchdog board** | stream frame berhenti → board mematikan motor | ~1 frame |
| L7 | **Lease kendali** | hanya satu sesi browser boleh memegang kendali; sesi lain read-only | — |
| L8 | **E-stop fisik** | tombol E-stop fisik, selalu di jangkauan operator | manual |

L1 adalah jaring pengaman utama: heartbeat berhenti persis ketika
kendali hilang, apa pun penyebabnya. Reaksi 300 ms pada 0,19 m/s = robot
telesat **±5,7 cm** sebelum berhenti. Jika ini terlalu lama, turunkan ke
150 ms (→ ±2,9 cm) dengan konsekuensi: jitter jaringan bisa menghentikan
robot di tengah jalan.

**L7 (lease)** perlu karena dashboard bisa dibuka di beberapa tab/HP.
Tanpa lease, dua browser bisa mengapit perintah dan robot bergerak tak
terduga. Implementasi: token kendali diambil saat operator menekan tombol
"ARM", dilepas saat E-stop atau disconnect.

### 6.5 UI

- Tombol tahan-tekan untuk 4 arah, plus putar CW/CCW (maksimal 6 tombol).
- Tombol STOP besar, selalu terlihat, tidak bisa tertutup dialog.
- Indikator **HOLD** yang menyala saat ada perintah aktif.
- Panel state: `CONNECTED` / `DISCONNECTED`, port, laju stream (Hz), frame
  terkirim, error terakhir, dan **rekomendasi AMBANG** (jika di bawah
  ambang stall → "di bawah ambang stall, robot tidak akan bergerak").
- Indikator "controller aktif: sesi ini / sesi lain".
- Notifikasi keras saat port putus di tengah gerak.

### 6.6 Aktivasi opt-in (C2)

Default dashboard **tetap offline** — tidak ada env var/flag yang bisa
menyalakan aktuasi secara tidak sengaja.

```
python run_dashboard.py --chassis-port /dev/ttyACM0 --chassis-live
```

- `--chassis-live` wajib ada; tanpa itu adapter offline dipasang.
- Port default `/dev/ttyACM0`, mengikuti `--lidar-port` yang polanya sudah
  ada (`src/amr_dashboard/__main__.py:20-36`).
- Env var `AMR_CHASSIS_LIVE=1` boleh ada sebagai dokumentasi, tetapi **tidak
  cukup untuk mengaktifkan aktuasi** — flag eksplisit tetap wajib.
- Menjalankan dengan `--chassis-live` mencetak peringatan di console:
  "AKTUASI NYATA — robot akan bergerak".

---

## 7. Tahapan dan gerbang

| Tahap | Isi | Testing | Gerbang |
| --- | --- | --- | --- |
| **P0** | Encoder frame motor pindah ke `stm32_protocol.py`; `wheel_test.py` ikut memakainya | tes unit: byte frame motor identik dengan output lama | byte identik → lanjut |
| **P1** | `kinematics.py` (murni): (vx,vy,wz) → 4 rps, skala m/s→rps | tes unit: maju murni → semua roda berimpit; 0,0 → semua 0; simetri kiri/kanan | fungsi murni, tanpa I/O → lanjut |
| **P2** | `motion_guard.py`: heartbeat, lease, latch, state machine | tes unit: heartbeat telat → STOP; lease ganda → tolak | guard bisa diuji tanpa robot → lanjut |
| **P3** | `serial_chassis.py`: thread, stream 50 Hz, STOP di finally, state jujur | tes dengan port **palsu** (loopback in-memory) — jumlah frame, urutan, STOP terakhir | tidak ada byte yang salah → lanjut |
| **P4** | UI hold-to-move + slider + ARM + panel state | tes UI yang ada + tes manual di browser | → gerbang hardware |
| **P5** | **Gerbang hardware**: roda terangkat, G1.1–G1.5 (identifikasi tanda) | observasi langsung | semua pola teridentifikasi |
| **P6** | Gerbang hardware: lantai, 0,05 m/s, jarak diukur, spotter + E-stop | penggaris + observasi | jarak masuk akal, tidak jatuh dari 0,19 m/s |
| **P7** | Aktifkan lateral & putar di lantai, satu arah satu waktu | penggaris + pengukur sudut | siap dipakai |

**P0–P4 sepenuhnya offline** — bisa dikerjakan dan direview tanpa robot.
P5–P7 butuh operator di lokasi.

---

## 8. Risiko dan mitigasi

| Risiko | Dampak | Mitigasi |
| --- | --- | --- |
| Event "lepas" hilang | robot terus jalan | L1 heartbeat + L2/L3 release global + L6 watchdog board |
| Konvensi tanda lateral/putar salah | robot bergerak ke arah yang tidak diminta | G1 gate + konfirmasi translasi, bukan observasi roda |
| Slider di bawah ambang stall | robot mengaum, operator mengira tombolnya rusak | batas bawah slider 0,06 m/s + peringatan eksplisit di panel |
| ModemManager merebut port | stream putus di tengah gerak | watchdog board mematikan motor; panel memberi tahu keras |
| Dashboard mati mendadak | robot bisa lanjut sampai frame berikutnya | watchdog board + `finally` STOP |
| Dua browser mengapit perintah | gerakan tak terduga | L7 lease kendali |
| Nyendet saat berbeban (masalah terbuka, sesi 2 §9.6) | UX buruk, bisa dikira macet | masalah yang diketahui; jangan diklaim sudah beres |
| Kecepatan meleset ~11 % (kalibrasi belum final) | angka di layar ≠ kenyataan | slider menampilkan kecepatan TARGET; konstanta per arah; kalibrasi sesi 4 menyusul |
| `linear_y`/`angular_z` di `safety.py` = 0,30/1,20 | batas itu tidak berdasarkan data | **turunkan batas v1** ke nilai konservatif sampai ada pengukuran |

---

## 9. Keputusan yang masih terbuka

| # | Pertanyaan | Rekomendasi |
| --- | --- | --- |
| O1 | Batas `linear_y` dan `angular_z` di versi pertama? | 0,05 m/s dan 0,20 rad/s, sampai ada pengukuran di lantai |
| O2 | Slider berarti kecepatan target (yang dimaksud operator) atau kecepatan perintah? | **Target** — operator melihat kecepatan yang dia maksud, bukan kecepatan yang benar-benar terjadi |
| O3 | Batas bawah slider? | 0,06 m/s (≈0,33 rps) — di atas 0,3 rps yang terbukti jalan |
| O4 | Reaksi heartbeat 300 ms atau 150 ms? | 300 ms dulu; 150 ms kalau jarak tempuh terasa lama |
| O5 | ARM eksplisit per sesi, atau cukup tombol "live"? | ARM eksplisit + lease |
| O6 | Keyboard (WASD) sebagai cara utama? | Ya — menekan tombol mouse sambil robot bergerak terasa jauh lebih melelahkan daripada menekan keyboard |

---

## 10. Yang tidak boleh diklaim setelah ini selesai

- "Dashboard sudah bisa mengarahkan robot" — baru bisa **maju/mundur/samping/putar
  pada kecepatan rendah**, dengan batas keras dan pola tanda terverifikasi per
  arah.
- "Kalibrasi selesai" — `C_eff` masih 20,72 ± 1,84 cm; rasio vs offset belum
  dipisahkan (sesi 4). Slider awal akan memakai konstanta sesi 3.
- "Lateral dan putar terverifikasi" — baru setelah P5/P6.
- "Odometri tersedia" — tidak ada; panel odometri tetap `UNAVAILABLE`.
- Tidak boleh menaikkan `max_linear_x` di REV ini.

---

## Lampiran — Batas yang tidak berubah di revisi ini

Tidak ada bagian dari rencana ini yang mengubah
`src/amr_core/robot/safety.py`. Batas kecepatan tetap **0,19 / 0,30 / 1,20**
sampai ada keputusan eksplisit lain. Penurunan batas `linear_y` dan
`angular_z` (O1) adalah satu-satunya perubahan yang diizinkan, dan hanya
setelah pengukuran di lantai.
