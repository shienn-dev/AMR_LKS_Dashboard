# G1 — Identifikasi Tanda Gerak (Gerbang Hardware)

**Status:** MENUNGGU EKSEKUSI di Lander. Dokumen ini adalah procedure +
lembar rekaman, bukan hasil.
**Tanggal:** 21 Oktober 2026
**Dasar:** `docs/rencana_chassis_live.md` §6.1 dan §7 (P5)
**Perintah:** dihasilkan `scripts/g1_patterns.py` (hanya mencetak, tidak
mengirim apa pun)

---

## 1. Kenapa gerbang ini wajib

Pola tanda **maju** sudah terverifikasi di lantai. Pola tanda **samping** dan
**putar** belum pernah diuji di robot ini — keduanya **diturunkan** dari
susunan roller.

Yang pernah terjadi: konvensi tanda versi lama (`maju = 1:+,2:+,3:−,4:−`)
**terbalik**, karena ditentukan dengan roda terangkat — di situ rotasi terlihat,
tapi translasi chassis tidak. Commit `f8de64e` mengoreksinya setelah robot
ternyata berjalan mundur. Pola sisi dan putar berisiko mengalami hal yang
sama, jadi **tidak boleh diasumsikan**.

Selama G1 belum lewat, **tidak ada gerak lateral atau putar dari dashboard**.

---

## 2. Prasyarat

| # | Prasyarat | Catatan |
| --- | --- | --- |
| 1 | Robot **mati**, port `/dev/ttyACM0` bebas (cek `fuser -v /dev/ttyACM0`) | jangan ada proses lain yang memegang port |
| 2 | **Tahap 1: roda terangkat** dan robot stabil, tangan di atas power switch | amati arah putar tiap roda |
| 3 | **Tahap 2: lantai**, ruang kosong ≥ 1,5 m ke depan dan ke samping | amati translasi nyata |
| 4 | E-stop fisik dalam jangkauan, **spotter** standby di samping | wajib untuk tahap 2 |
| 5 | Kamera atau catatan siap | foto/deskripsi arah dan jarak |
| 6 | `--confirm` **tanpa** `--yes`; operator mengetik `MOVE` manual | pola ini sudah teruji di sesi 2/3 |

---

## 3. Cara menjalankan

Di Pi:

```
cd /home/stematelpi5/AMRTestLander/AMR_LKS_Dashboard
git pull --ff-only
git log --oneline -1        # harus c48024c atau sesudahnya
python scripts/g1_patterns.py
```

Skrip itu **mencetak** delapan perintah (maju, mundur, samping kiri/kanan,
putar kiri/kanan, dua diagonal) lengkap dengan pola motor, rate yang
dihitung, dan hasil yang diharapkan. Perintah yang diuji dijamin sama dengan
yang dipakai dashboard, karena keduanya berasal dari
`src/amr_core/robot/kinematics.py`.

Untuk durasi lebih pendek (disarankan 2 s) tambahkan `--duration 2`.

---

## 4. Tahap 1 — roda terangkat (amati arah putar)

Jalankan tiap pola **dengan roda terangkat**. Yang diamati: **arah putar tiap
roda**, bukan gerak robot.

| # | Pola motor | Diharapkan (kode) | Roda yang harus berputar | Sesuai? |
| --- | --- | --- | --- | --- |
| 1 | `1:- 2:- 3:+ 4:+` | maju | 1, 2, 3, 4 | — |
| 2 | `1:+ 2:+ 3:- 4:-` | mundur | 1, 2, 3, 4 | — |
| 3 | `1:- 2:+ 3:- 4:+` | samping kiri | 1, 2, 3, 4 | — |
| 4 | `1:+ 2:- 3:+ 4:-` | samping kanan | 1, 2, 3, 4 | — |
| 5 | `1:+ 2:+ 3:+ 4:+` | putar kiri | 1, 2, 3, 4 | — |
| 6 | `1:- 2:- 3:- 4:-` | putar kanan | 1, 2, 3, 4 | — |
| 7 | `1:- 2:+ 3:- 4:+` (2,3 ≈ 0) | diagonal maju-kiri | 1 dan 4 | — |
| 8 | `1:+ 2:- 3:+ 4:-` (1,4 ≈ 0) | diagonal maju-kanan | 2 dan 3 | — |

Perhatikan khusus:
- Pola 5 dan 6: **keempat motor bertanda sama** → seharusnya berputar di
  tempat. Ini yang pernah diamati di sesi 2 (perintah seragam = berputar,
  bukan maju).
- Pola 7 dan 8: **hanya dua roda** yang berputar (diagonal), dua lainnya
  hampir diam. Ini sifat mecanum yang wajar.

---

## 5. Tahap 2 — lantai (konfirmasi translasi)

Pola yang lolos tahap 1, diuji ulang **di lantai** dengan robot di garis
start tetap. Yang diamati: **arah translasi** dan apakah robot berputar saat
diharapkan meluncur (atau sebaliknya).

| # | Pola | D.expected (kode) | Diamati: gerak | Jarak (cm) | Sesuai? |
| --- | --- | --- | --- | --- | --- |
| 1 | maju | maju, lurus | — | — | — |
| 2 | mundur | mundur, lurus | — | — | — |
| 3 | samping kiri | meluncur kiri, **tidak** berputar | — | — | — |
| 4 | samping kanan | meluncur kanan, **tidak** berputar | — | — | — |
| 5 | putar kiri | berputar di tempat ke kiri | sudut ≈ ? | — | — |
| 6 | putar kanan | berputar di tempat ke kanan | sudut ≈ ? | — | — |
| 7 | diagonal maju-kiri | diagonal ke depan-kiri | — | — | — |
| 8 | diagonal maju-kanan | diagonal ke depan-kanan | — | — | — |

**Pola 1 (maju) wajib diulang di tahap ini** — itulah kontrol yang sudah
terverifikasi; kalau ternyata tidak cocok, semua pola lain harus dianggap
curiga.

Catat juga untuk tiap percobaan:
- apakah robot **terlalu miring** atau ada roda yang tidak ikut (slip),
- apakah ada **nyendet** (masalah terbuka, sesi 2 §9.6),
- berapa **jarak** untuk pola translasi (penggaris, ±1 cm).

---

## 6. Kalau hasilnya tidak sesuai

| Gejala | Arti | Tindakan |
| --- | --- | --- |
| Samping Instead of putar (atau sebaliknya) | tanda lateral/putar tertukar | **jangan** mengulang perintah; laporkan, nanti diperbaiki di `kinematics.py` |
| Mundur saat diharapkan maju | konvensi maju terbalik | cek dulu apakah robot dipasang terbalik (kepala menghadap 180°) |
| Robot berputar saat diharapkan meluncur | dua sumbu tercampur | periksa `ROLLER_DIRECTION_DEG` (susunan roller) |
| Roda slip, robot tidak bergerak | di bawah ambang stall (0,3 rps) | ulang dengan `--duration 3` atau rate lebih tinggi; jangan naikkan kecepatan |
| Gerakan tidak halus (nyendet) | masalah terbuka yang sudah diketahui | catat, jangan ganggu robot; bukan tanda yang salah |

**Aturan utama: kalau ada yang meleset, tulis apa yang terjadi — jangan
mengulang-ulang sampai kebetulan cocok.** Yang dicatat adalah fakta, dan
tandanya yang dikoreksi di kode.

---

## 7. Yang dikembalikan

1. Tabel tahap 1 dan tahap 2 terisi (tandai **GAGAL** kalau ada yang gagal,
   beserta alasannya — jangan diisi perkiraan).
2. Foto atau rekaman singkat tiap pola.
3. Output `python scripts/g1_patterns.py` (boleh dikirim apa adanya).
4. Konfirmasi: tidak ada kode yang diubah, tidak ada commit.

Dari data ini, `src/amr_core/robot/kinematics.py` diperbaiki **hanya pada
nilai tandanya** (satu baris per arah), lalu tesnya diperbarui. Gerbang P6
(lantai, 0,05 m/s, jarak terukur) baru jalan setelah G1 ini selesai.
