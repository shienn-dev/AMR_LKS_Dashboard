# Sesi 2 — Dokumentasi Pabrik & Persiapan Uji Roda

Dokumen ini mencatat pekerjaan sesi 2: penelusuran dokumentasi pabrik dari Google
Drive Hiwonder, temuan teknis yang mengubah asumsi, dan persiapan uji aktuasi roda.

> Prinsip yang tetap dipegang: **bukti di atas asumsi**. Tidak ada perintah motor
> yang dikirim selama sesi ini. Tidak ada paket dipasang, tidak ada konfigurasi
> sistem diubah, tidak ada `/dev/ttyACM0` yang dibuka.

**Tanggal:** 19 Oktober 2026
**Host:** `stematel-pi5` (Raspberry Pi 5, Ubuntu 24.04.5 ARM64)
**HEAD saat sesi dimulai:** `d88eb49`

---

## 1. Ringkasan

Sesi ini menghasilkan tiga hal:

1. **Dokumentasi pabrik berhasil diakses** dan 5 PDF tersimpan di `~/dokumentasi_lander/`.
2. **Dua pertanyaan lama terjawab**: konfigurasi roller Mecanum (ABAB) dan satuan
   kecepatan motor (**rps**).
3. **Alat uji roda siap** (`scripts/wheel_test.py`) tetapi **belum dijalankan**.

Yang **belum** terjawab: nilai numerik radius roda, `L`, `H`, dan apakah odometri
benar-benar memakai encoder.

---

## 2. Akses dokumentasi pabrik

Folder Drive: `1PQmoEIc0jQx20Lk4pmy5CA_bdfu59ayU` ("LanderPi"), berisi 4 subfolder:

| Subfolder | Isi | Status |
| --- | --- | --- |
| `1. Tutorials` | 14 kursus, tiap kursus 1 folder berisi PDF | Diakses |
| `2. Software` | 7 tool (App installer, VNC, formatter, flasher, dll.) | Dilihat, tidak diunduh |
| `3. System Image & Source Code` | Hanya `Important Notice.pdf` | Diakses |
| `FAQ` | — | Tidak diperiksa |

**Kendala teknis:** browser otomatis tidak dapat dijalankan di Pi ini
(`chromium: error while loading shared libraries: libatk-1.0.so.0`). Pustaka GUI
tidak tersedia pada Ubuntu Server headless. Karena memasang paket dilarang, daftar
folder diambil lewat endpoint `embeddedfolderview` dan berkas diunduh lewat HTTP.

**Catatan integritas unduhan:** dua berkas pertama terpotong tanpa peringatan
(tidak ada `%%EOF`). Deteksi dilakukan dengan membandingkan ukuran lokal terhadap
`Content-Length`, lalu dilanjutkan dengan `curl -C -`. Semua berkas di bawah sudah
diverifikasi utuh.

### PDF yang tersimpan

| Berkas | Ukuran | Keterbacaan teks |
| --- | --- | --- |
| `1. LanderPi User Manual.pdf` | 56.095.745 B | **Tidak terbaca** — font subset dengan encoding kustom; butuh library PDF |
| `3. Chassis Motion Control.pdf` | 10.694.144 B | Terbaca penuh |
| `4. Lidar.pdf` | 1.174.688 B | Terbaca |
| `6. Mapping & Navigation Course.pdf` | 11.730.523 B | Terbaca sebagian |
| `Important Notice.pdf` | 55.589 B | Terbaca |

---

## 3. Temuan teknis

### 3.1 Konfigurasi roller Mecanum: **ABAB** — TERKONFIRMASI

Dari `3. Chassis Motion Control.pdf` §3.1.1:

> "Typically, Mecanum wheels are used in sets of four, two left-handed wheels
> (Type A) and two right-handed wheels (Type B), which are arranged symmetrically.
> […] The Mecanum chassis uses the **ABAB** configuration, which enables true
> omnidirectional movement."

Sebelumnya parameter ini ditandai "belum ditemukan / perlu diukur langsung".
Sekarang ada sumber pabrik. **Ini menghapus satu kebutuhan pengukuran fisik.**

### 3.2 Satuan kecepatan motor: **rps** — TERKONFIRMASI

Dari §3.1.1, deskripsi `speed_covert`:

> "Converts linear velocity (m/s) to angular velocity (**rps**) based on wheel
> parameters."

Ini menyelesaikan kontradiksi yang tercatat di sesi 1:

| Sumber | Klaim lama |
| --- | --- |
| `stm32_protocol.py:42-44` | payload MOTOR "layout uncertain", tidak didekode |
| `docs/sesi_1.md:124` | `[0x01, n, (id-1:u8, rps:float32)]` |

Sumber pabrik menguatkan yang kedua: **float32 itu rps**, bukan duty 0–1.
Konsekuensi praktis: nilai `0.15` = 0,15 putaran/detik ≈ 9 rpm — sangat lambat.

### 3.3 Parameter kinematika: simbol ada, angka tidak

Dokumen mendefinisikan:

| Simbol | Arti |
| --- | --- |
| `L` | jarak antar-pusat roda kiri–kanan (track width) |
| `H` | jarak antar-pusat roda depan–belakang (wheelbase) |
| `Vx, Vy, Vω` | kecepatan linear X, Y, dan angular chassis |
| `VA..VD` | kecepatan putar empat roda |

**Nilai numeriknya tidak dicantumkan.** Dokumen hanya menyebut bahwa kelas
`Mecanum` "initializes the wheel dimensions" di `ros2_ws/src/driver/controller/controller/mecanum.py`.

Angka lain yang disebut:

| Nilai | Konteks |
| --- | --- |
| `0.3` m/s | clamp `linear_x` di `odom_publisher_node.py` |
| `−0.6 … 0.6` m/s | rentang kecepatan linear yang disarankan |
| `0.213` | `D` pada rumus Ackerman `tanΦA = D/R` |

### 3.4 Topik ROS 2 yang relevan

`/controller/cmd_vel`, `/imu`, `/odom`, `/odom_raw`,
`ros_robot_controller/set_motor` (tipe `MotorsState`),
`ros_robot_controller/bus_servo/set_state`.

Konfigurasi: `~/ros2_ws/src/driver/controller/config/calibrate_params.yaml`
(berisi `linear_correction_factor`, `angular_correction_factor`, `machine_type`).

### 3.5 Odometri: klaim dokumen vs analisis kode — BELUM SELESAI

**Dokumen** (§3.2.2) menyatakan:

> "odometry information is computed using the motor encoders combined with the
> robot's kinematic model" dan "For the robot, wheel odometry is used."

**Analisis kode upstream** (sesi 1) menyimpulkan `cal_odom_fun` mengintegralkan
**kecepatan perintah**, bukan hitungan encoder.

**Yang bisa dipastikan:** tidak ada satu pun topik encoder yang disebut di
dokumentasi — hanya `/odom` dan `/odom_raw`. Jadi meski encoder ada secara fisik,
tidak terbukti ada kanal publikasinya.

**Status: BELUM TERVERIFIKASI.** Perlu `odom_publisher_node.py` asli.

### 3.6 Lidar: default pabrik ≠ hardware kita

`4. Lidar.pdf` §4.1.3: *"The robot is equipped with **MS200** laser radar by
default"*. Hardware kita adalah **LD19/STL-19P** di `/dev/ttyUSB0`.

Kesimpulan: `LIDAR_TYPE` pada robot ini **bukan nilai default pabrik** — entah
diubah lewat tool, atau sensornya diganti sekolah. **Nilai aktualnya tetap tidak
diketahui** (file `.typerc` tidak pernah ada di sistem ini).

### 3.7 Lokasi URDF

`6. Mapping & Navigation Course.pdf` §6.1.2:
`/home/ubuntu/ros2_ws/src/simulations/landerpi_description/urdf/landerpi.xacro`,
memanggil komponen `inertial_matrix`, `mecanum`, `tank`, `ack`, `arm`.
**Parameter roda ada di `mecanum.xacro`** — belum diperoleh.

### 3.8 Sumber yang ditemukan tetapi TIDAK diunduh

Di `10. MoveIt → Configuration Files → 3 Feature Package Files`:

| Berkas | Perkiraan isi |
| --- | --- |
| `driver.zip` | `mecanum.py`, `odom_publisher_node.py`, `calibrate_params.yaml` |
| `landerpi_description.zip` | `mecanum.xacro` (geometri roda) |
| `hiwonder_moveit_config.zip` | Konfigurasi MoveIt |
| `robot_gazebo.zip` | Model Gazebo |

**Tidak diunduh** karena instruksi sesi ini membatasi unduhan pada PDF saja.
Kedua berkas pertama adalah sumber paling langsung untuk mengisi §3.3 dan §3.5.

Juga ditemukan (tidak relevan/tidak diunduh): `ubuntu_ros2_humble.zip` (VM image
x86, tidak dapat dipakai di ARM64) dan `Vmware 16.0 Pro.zip`.

### 3.9 Subfolder yang kosong

Enam subfolder `2. Basic Course` — termasuk **`4. STM32 Controller Course`** —
mengembalikan 0 entri meski judulnya termuat (folder terbaca, isinya kosong).
Folder `5. Depth Camera → Aurora Depth Camera` juga kosong. **Tidak ada PDF yang
bisa diambil dari sana.**

---

## 4. Alat baru: `scripts/wheel_test.py`

Skrip uji aktuasi sekali-jalan. **Tidak dijalankan selama sesi ini.**

### Pengaman berlapis

| Lapis | Perilaku |
| --- | --- |
| Dry run default | Tanpa `--confirm`, skrip hanya mencetak frame yang *akan* dikirim; port tidak dibuka |
| Konfirmasi interaktif | Dengan `--confirm`, harus mengetik `MOVE` (lewati dengan `--yes`) |
| Satu perintah lalu stop | Satu frame gerak, tahan `--duration`, lalu frame stop eksplisit |
| Stop di `finally` | Frame stop tetap dikirim walau error atau Ctrl+C |
| Kecepatan rendah | Default `0.15` rps (~9 rpm), jauh di bawah demo pabrik `0.6` |
| DTR/RTS pra-open | `dtr=False`, `rts=False` **sebelum** `open()` — mengurangi, bukan menjamin, reset MCU |
| Peringatan ModemManager | Mencetak peringatan `ID_MM_CANDIDATE=1` setiap kali akan transmisi |

### Verifikasi frame

Keluaran skrip dibandingkan dengan logika `set_motor_speed` SDK pabrik:

```
skrip : aa 55 03 16 01 04 00 9a 99 19 3e 01 9a 99 19 3e 02 9a 99 19 3e 03 9a 99 19 3e 5e
SDK   : aa 55 03 16 01 04 00 9a 99 19 3e 01 9a 99 19 3e 02 9a 99 19 3e 03 9a 99 19 3e 5e
IDENTIK: True | 27 byte | CRC valid: True
```

### Pemakaian

```bash
../.venv/bin/python scripts/wheel_test.py                      # dry run
../.venv/bin/python scripts/wheel_test.py --confirm            # transmisi, minta ketik MOVE
../.venv/bin/python scripts/wheel_test.py --confirm --motors 1 --speed 0.1
```

---

## 5. Rencana uji roda

**Perkiraan total: 60–90 menit.** Belum dijalankan.

### Prasyarat — wajib, jangan dilewati

- [ ] Roda **terangkat** dari permukaan, robot stabil
- [ ] Tidak ada yang bisa tersangkut di roda
- [ ] Saklar daya / E-stop dalam jangkauan, tangan siap
- [ ] Pemilik menyetujui aktuasi
- [ ] Keputusan soal ModemManager (lihat §6)

### Langkah

| # | Aksi | Estimasi |
| --- | --- | --- |
| 1 | Angkat robot, siapkan saklar, pastikan area aman | 15 mnt |
| 2 | Putuskan penanganan ModemManager | 10 mnt |
| 3 | Dry run: periksa frame | 5 mnt |
| 4 | Uji satu motor (`--motors 1 --speed 0.1`) | 10 mnt |
| 5 | Uji empat motor (`--speed 0.15`) | 10 mnt |
| 6 | Catat: berputar? arah? board tetap terhubung? | 10 mnt |
| 7 | Bila berhasil: ulangi per motor untuk memetakan ID → posisi fisik | 20 mnt |

### Kemungkinan hasil

| Hasil | Arti | Tindak lanjut |
| --- | --- | --- |
| Roda berputar | Protokol terkonfirmasi | Petakan ID motor → posisi roda |
| Diam total | Protokol tidak cocok | Rekam byte; firmware sekolah berbeda |
| Berputar, arah/urutan salah | Protokol benar, pemetaan salah | Betulkan urutan; tidak perlu protokol baru |

Ketiganya informatif — tidak ada hasil yang benar-benar gagal.

---

## 6. Keputusan terbuka

1. **ModemManager.** `/dev/ttyACM0` ber-flag `ID_MM_CANDIDATE=1` dan ModemManager
   aktif, tanpa rule `ID_MM_PORT_IGNORE`. Artinya port dapat dibuka/direset oleh
   sistem **tanpa kita melakukan apa pun**. Menonaktifkannya adalah perubahan
   konfigurasi dan butuh persetujuan. Alternatif: terima risiko, baca hasil dengan
   hati-hati.

2. **`driver.zip` + `landerpi_description.zip`.** Mengisi 4 dari 5 parameter yang
   masih kosong (§3.3) dan menyelesaikan perdebatan odometri (§3.5). Keduanya ZIP,
   bukan PDF, sehingga belum diunduh.

3. **User Manual tidak terbaca mesin.** 56 MB, font subset kustom. Perlu library
   PDF (tidak dipasang) atau pembacaan manual.

---

## 7. Status parameter kinematika

| Parameter | Status | Sumber |
| --- | --- | --- |
| Konfigurasi roller | **DITEMUKAN** — ABAB | Chassis PDF §3.1.1 |
| Satuan kecepatan | **DITEMUKAN** — rps | Chassis PDF §3.1.1 |
| Radius roda | Belum ditemukan | `mecanum.py` (belum diperoleh) |
| Track width `L` | Belum ditemukan | idem |
| Wheelbase `H` | Belum ditemukan | idem |
| Pemetaan ID motor → posisi | Belum ditemukan | perlu uji fisik |
| Resolusi encoder | Belum ditemukan | tidak ada di protokol |
| Rasio gearbox | Belum ditemukan | — |

---

## 8. Yang tidak diubah

- Tidak ada paket dipasang, tidak ada unduhan selain PDF
- Tidak ada konfigurasi sistem/RasPi diubah
- `/dev/ttyACM0` tidak dibuka; tidak ada perintah motor dikirim
- Tidak ada service dihentikan
- File sementara di `/tmp` sudah dibersihkan
