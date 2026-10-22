# Tugas untuk Hermes — Gerbang Robot Sesi 4

Brief ini untuk **Hermes** (agent yang jalan di Lander, dekat robot). Kamu
tidak perlu memahami seluruh repo — cukup mengikuti urutan di bawah dan
mengembalikan angka apa adanya.

Semua angka di sini **belum terverifikasi** dan beberapa sengaja kosong. Isi
dengan hasil ukur. Kalau satu langkah gagal, tulis **GAGAL** beserta
alasannya — jangan menebak, jangan mengulang sampai kebetulan cocok.

---

## 0. Konteks, 30 detik

Tujuan sesi ini: membuat robot **bisa dikemudikan dari dashboard** dengan
kecepatan yang terukur dan aman.

Yang sudah beres (kode di repo, sudah ter-push):

| Sudah | Belum |
| --- | --- |
| Dashboard bisa mengirim perintah motor (opt-in `--chassis-live`) | Pola tanda **lateral** sudah dikoreksi (kiri/kanan terbalik) tapi **belum diuji ulang** |
| Fail-safe: lepas tombol, tab ditutup, E-stop, disconnect | **Roda depan kanan (motor 3) tidak berputar** di lantai |
| Kinematika maju & putar (terverifikasi) | **Nyendet brutal** di semua arah, robot lambat |
| Instrumen: laju stream + jeda frame | Pola diagonal |

Temuan lapangan terakhir: keempat motor berputar normal **saat roda
terangkat**, tapi di lantai roda depan kanan diam dan robot melenceng ke
kanan. Jadi motor dan kabelnya baik; masalahnya ada di **roda/roller**.

---

## 1. Aturan wajib

| Larangan | Kenapa |
| --- | --- |
| **Jangan** `--yes` | Perintah harus diketik `MOVE` manual oleh operator |
| **Jangan** menguji `u > 1,0` atau 0,30 m/s | Di luar bukti |
| **Jangan** mengubah kode, commit, atau push | Cuma jalankan dan catat |
| **Jangan** menjalankan `--chassis-live` sebelum ada di depan robot | Aktuasi nyata |
| **Jangan** mengisi angka yang tidak terukur | Kosong berarti belum diukur |

Untuk semua langkah yang ada geraknya: **operator manusia** harus di dekat
robot dengan E-stop dalam jangkauan, dan ada **spotter**. Kamu yang
menjalankan perintahnya; manusia yang mengukur dan menekan E-stop.

---

## 2. Peta urutan

```
 TUGAS 1  Diagnosa nyendet   →  TUGAS 2  Motor per motor   →  TUGAS 3  G1 tanda
 (A/B: dashboard vs script)     (roda terangkat, motor 3?)      (8 pola, 2 tahap)
        │                              │                             │
        └──────────────────────────────┴─────────────────────────────┘
                                       │
                                       ▼
                            TUGAS 4  Fail-safe (4 uji)
                                       │
                                       ▼
                            LAPORAN  (isi format di §7)
```

TUGAS 1 dan 2 bisa dikerjakan **berdampingan** dengan TUGAS 3, tapi jangan
lompat ke TUGAS 3 sebelum TUGAS 2 selesai — pola tanda yang salah akan
menghasilkan data yang menyesatkan.

---

## 3. TUGAS 1 — Nyendet: dari server atau dari robot?

Pertanyaan: nyendet terjadi karena **frame motor yang jatuh** (server) atau
karena **motor/roda/board** (robot)? Pemeriksaan ini menentukan efforts
seluruhnya, jadi kerjakan lebih dulu.

### 1A — Tanpa dashboard (plain script, tidak ada UI)

Robot di lantai, di garis start. Roda **turun**.

```
cd /home/stematelpi5/AMRTestLander/AMR_LKS_Dashboard
../.venv/bin/python scripts/wheel_test.py --confirm --port /dev/ttyACM0 --rate 50 --duration 3 --speeds "1:-0.6,2:-0.6,3:+0.6,4:+0.6"
```

Ulangi 2×. **Catat:** nyendet? melenceng? jaraknya berapa?

### 1B — Dengan dashboard

```bash
fuser -v 8080/tcp          # pastikan tidak ada dashboard lama
fuser -v /dev/ttyACM0      # harus kosong
pkill -f run_dashboard.py   # kalau ada yang jalan
python run_dashboard.py --chassis-live --host 0.0.0.0 --port 8080
```

Buka `http://<ip-pi>:8080` di browser, slider **0,06 m/s**, tahan **MAJU**
3 detik. **Catat dari status bar:**

```
stream  __ Hz    max gap  __ ms    frames  __    heartbeat  __ s
```

Ulangi 2×, catat angkanya tiap kali.

### 1C — Motor per motor (roda TERANGKAT)

```
for m in 1 2 3 4; do
  ../.venv/bin/python scripts/wheel_test.py --confirm --port /dev/ttyACM0 --motors $m --speed 0.3 --duration 2
done
```

Operator mengamati **roda mana yang berputar** untuk tiap motor.

### 1D — Putting it together (keputusan)

| Hasil 1A | Hasil 1B | Kesimpulan | Tindakan |
| --- | --- | --- | --- |
| nyendet | nyendet | masalah di **board/motor/roda** | fokus ke roda FR (TUGAS 2) |
| nyendet | mulus | masalah di **server** | baca `max gap`; kalau > 200 ms → event loop macet, laporkan angkanya |
| mulus | nyendet | masalah di **server** |idem |
| mulus | mulus | nyendet tadi karena **kecepatan/arena** | ulangi di lantai rata |

Isi tabel keputusan di lembar rekaman §7.

---

## 4. TUGAS 2 — Motor per motor di lantai (roda FR)

Setelah 1C, dua pemeriksaan lagi dengan **roda di lantai**:

```
# motor 3 saja, roda di lantai
../.venv/bin/python scripts/wheel_test.py --confirm --port /dev/ttyACM0 --motors 3 --speed 0.3 --duration 2
```

| Motor | Berputar di udara? (1C) | Berputar di lantai? | Roda yang bergeser |
| --- | --- | --- | --- |
| 1 (depan kiri) | — | — | — |
| 2 (belakang kiri) | — | — | — |
| 3 (depan kanan) | — | — | — |
| 4 (belakang kanan) | — | — | — |

Kalau **motor 3 tidak berputar di lantai tapi berputar di udara** → masalahnya
mekanis di roda/roller. Isi tabel di §7 dan **berhenti** — ini perlu orang
yang bisa membongkar roda.

---

## 5. TUGAS 3 — G1: identifikasi tanda

Procedure lengkap: `docs/g1_identifikasi_tanda.md`. Perintahnya sudah
dicetak oleh:

```
python scripts/g1_patterns.py
```

Dua tahap:

1. **Roda terangkat** — jalankan tiap pola, amati **arah putar tiap roda**.
2. **Lantai** — jalankan pola yang lolos tahap 1, amati **arah translasi**.

Yang sudah diketahui dan **tidak perlu diuji ulang**: maju
(`1:- 2:- 3:+ 4:+`) dan putar (keempat motor tanda sama).

Yang baru: **sampling kiri/kanan** (sudah dikoreksi di kode — ini yang mau
dikonfirmasi) dan **dua diagonal**.

---

## 6. TUGAS 4 — Fail-safe (tidak butuh roda bagus)

Empat uji. Untuk A dan B, operator **menahan tombol** sementara kamu atau
operator melakukan aksinya. Catat **berapa lama** robot berhenti.

| Uji | Cara | Seharusnya |
| --- | --- | --- |
| A | Tahan tombol + **Ctrl+W** (tab ditutup) | berhenti ≤ 1 s |
| B | Tahan tombol + **matikan Wi-Fi laptop** | berhenti ≤ 1 s |
| C | E-STOP software dari **tab kedua** (HP) | berhenti seketika |
| D | Tahan tombol + kamu **Ctrl+C** server-nya | berhenti (frame stop + watchdog board) |

Isi: A __ s · B __ s · C __ s · D __ s

---

## 7. Format laporan (kembalikan ini)

```markdown
## Laporan Hermes — <tanggal> <waktu>

### 1A (tanpa dashboard)
- pola: 1:-0.6,2:-0.6,3:+0.6,4:+0.6
- nyendet: ya/tidak | melenceng: ya/tidak (ke mana)
- jarak: trial 1 __ cm, trial 2 __ cm, trial 3 __ cm
- durasi: __ s (dari panel atau stopwatch?)

### 1B (dashboard)
- slider: __ m/s | waktu tahan: __ s (dari panel)
- stream: __ Hz | max gap: __ ms | frames: __ | heartbeat: __ s
- nyendet: ya/tidak | melenceng: ya/tidak
- jarak: __ cm

### 1C (motor per motor, roda terangkat)
| motor | 1 | 2 | 3 | 4 |
|---|---|---|---|---|
| roda yang berputar | | | | |

### 1D (keputusan)
- 1A: __ | 1B: __ → kesimpulan: __

### 2 (motor per motor, di lantai)
| motor | 1 | 2 | 3 | 4 |
|---|---|---|---|---|
| berputar di lantai? | | | | |
| roda yang bergeser | | | | |

### 3 (G1 tanda)
| pola | diука yang diharapkan | yang terjadi | sesuai? |
|---|---|---|---|
| sampling kiri | | | |
| sampling kanan | | | |
| diagonal maju-kiri | | | |
| diagonal maju-kanan | | | |

### 4 (fail-safe)
A __ s | B __ s | C __ s | D __ s

### 5 (catatan)
- __
```

---

## 8. Kalau ada masalah

| Gejala | Tindakan |
| --- | --- |
| Port `/dev/ttyACM0` sudah dipakai | `fuser -v /dev/ttyACM0` → laporkan, jangan paksa |
| `address already in use` | `fuser -k 8080/tcp` lalu jalankan ulang |
| Port web tidak terbuka dari laptop | cek IP Pi: `hostname -I` |
| Robot tidak berhenti saat seharusnya | E-stop fisik, lalu laporkan **segera** |
| `pyserial` tidak ada | `../.venv/bin/python -c "import serial; print(serial.__version__)"` → laporkan |
