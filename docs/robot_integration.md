# Integrasi Robot: Kamera, Odometri, Remote Chassis, dan Arm

Dokumen ini mencatat **apa yang benar-benar terverifikasi di robot sekolah**
(`stematel-pi5`, Raspberry Pi 5, Ubuntu 24.04.5 ARM64) versus apa yang hanya
ditemukan di source code atau masih memerlukan pengujian/persetujuan. Dokumen
ini melengkapi kode di `src/amr_core/robot/` dan panel di
`src/amr_dashboard/robot_panel.py`.

Prinsip: **tidak ada data atau perintah palsu**. Adapter yang belum
terverifikasi tidak mengirim apa pun dan tidak menampilkan apa pun sebagai data
hardware sungguhan.

---

## 1. Fakta terverifikasi (perangkat aktual)

| Item | Nilai | Sumber |
| --- | --- | --- |
| Board | Raspberry Pi 5 Model B Rev 1.0, aarch64 | `/proc/device-tree/model`, `uname -a` |
| OS | Ubuntu 24.04.5 LTS (noble), kernel `6.8.0-1065-raspi` | `/etc/os-release` |
| Python dashboard | `/usr/bin/python3.12` + venv `~/AMRTestLander/.venv` (nicegui 3.18.0, pyserial 3.5) | `pip list` |
| ROS 2 | **Tidak terpasang** (`/opt` kosong, tidak ada `ros2`, tidak ada paket `dpkg` ROS) | pemeriksaan langsung |
| LiDAR | STL-19P/LD19 di `/dev/ttyUSB0`, CH340 (`1a86:7523`), 230400 baud | dipegang oleh dashboard yang berjalan (PID 5781) |
| Chassis/Arm/IMU | STM32 di `/dev/ttyACM0`, USB `1a86:55d4` (sama dengan upstream `ros_robot_controller`) | `udevadm`, `lsusb` |
| Kamera | **Deptrum Aurora 930** depth camera, USB `3251:1930`, kelas antarmuka `0xFF` (vendor-specific) | sysfs, `kern.log` |
| Node `/dev/video` | hanya `pispbe`/`rpivid` (ISP & codec internal Pi) — **bukan** kamera | `/sys/class/video4linux` |

**Kamera bukan UVC.** Aurora 930 tidak punya driver kernel yang ter-bind
(`driver=[none]`) dan tidak membuat node `/dev/video`. Untuk membacanya
diperlukan SDK Deptrum / driver ROS `deptrum-ros-driver-aurora930` (seperti di
upstream). Tidak ada frame yang bisa dibaca pada kondisi saat ini.

**Tidak ada ROS 2.** Upstream LanderPi berbasis ROS 2; robot sekolah sudah
dimodifikasi (ROBO JX) dan stack ROS 2-nya tidak ada di Pi ini.

---

## 2. Matriks integrasi (status bukti)

Kategori: **TERVERIFIKASI** (diperiksa di perangkat), **SOURCE-ONLY** (ada di
kode/dokumentasi, belum diverifikasi berjalan), **BELUM DIKETAHUI**,
**BLOCKED** (butuh akses/hardware/persetujuan).

| Fungsi | Hardware/software sumber | Antarmuka aktual | Status bukti | Cara dashboard mengakses | Pekerjaan tersisa | Risiko / prasyarat |
| --- | --- | --- | --- | --- | --- | --- |
| LiDAR | STL-19P/LD19 @ `/dev/ttyUSB0` | paket 47 byte `0x54 0x2C`, 230400 baud | **TERVERIFIKASI** | `amr_core.lidar` + `lidar_panel` (sudah ada) | — | jangan sampai port/baud/panel rusak |
| Kamera | Deptrum Aurora 930 `3251:1930` | vendor-specific, tanpa driver | **TERVERIFIKASI tidak tersedia** | `amr_core.robot.camera.probe_camera` (status saja) | pasang SDK Deptrum + dependency, lalu tulis source frame | instalasi dependency besar → butuh persetujuan |
| Odometri | tidak ada sumber aktif | — | **BELUM DIKETAHUI** | `amr_core.robot.odometry.NoOdometrySource` (UNAVAILABLE) | verifikasi jalur encoder/IMU STM32, lalu implementasi source | butuh protokol terverifikasi |
| Chassis | STM32 @ `/dev/ttyACM0` | serial `0xAA 0x55 ...` (`ros_robot_controller_sdk`) | **TERVERIFIKASI** (protokol + konvensi tanda) | `amr_core.robot.serial_chassis` (live, opt-in) + `amr_dashboard.chassis_panel` | verifikasi tanda lateral/putar di lantai (gate G1) | aktuasi nyata → **hanya dengan `--chassis-live`** |
| Arm | bus servo di STM32 | `ros_robot_controller/bus_servo/set_position` (pulse 0..1000) | **SOURCE-ONLY** | `amr_core.robot.arm` (offline, tidak mengirim) | verifikasi jumlah joint, rentang aman, protokol | actuation → **BLOCKED** |
| ROS 2 | tidak ada | — | **TERVERIFIKASI absen** | — | jangan pasang tanpa persetujuan | perubahan besar → butuh persetujuan |

---

## 3. Arsitektur integrasi (paling sedikit mengganggu)

UI dipisahkan dari hardware melalui **adapter**. Dashboard hanya bergantung pada
protokol di `amr_core/robot/interfaces.py`:

- `ChassisAdapter` — `state()`, `last_command()`, `submit(cmd)`, `stop()`.
- `ArmAdapter` — idem untuk arm.
- `OdometrySource` — `state()`, `detail()`, `sample()`.
- `probe_camera()` — status kamera (read-only, tanpa membuka device).

Implementasi yang dikirim pada fase ini:

- `OfflineChassisAdapter` / `OfflineArmAdapter`: memvalidasi + meng-clamp +
  mencatat perintah, tetapi **tidak mengirim apa pun** (`transmitted=False`).
- `SerialChassisAdapter` (`amr_core.robot.serial_chassis`): transport serial
  yang **benar-benar mengirim** — thread pemilik port, stream 50 Hz (board
  mematikan motor kalau frame berhenti mengalir), frame stop di `finally`, dan
  state koneksi yang jujur. **Tidak** diaktifkan secara default: dashboard
  memilihnya hanya bila dijalankan dengan `--chassis-live`.
- `MotionGuard` (`amr_core.robot.motion_guard`): lapis fail-safe untuk
  kontrol tahan-tekan — heartbeat klien, lease kendali, latch E-stop software.
- `amr_core.robot.kinematics`: kinematika invers mecanum (vx, vy, wz) → 4
  perintah roda, dengan pola maju yang terverifikasi di lantai.
- `NoOdometrySource`: selalu `UNAVAILABLE`, tidak pernah mengarang pose.
- `probe_camera`: melaporkan penyebab spesifik (mis. "Aurora 930 terdeteksi,
  tetapi tanpa driver/SDK").

`safety.py` menyediakan pembatas kecepatan (`SpeedLimits`), validasi input
(menolak NaN/Inf), dan `EStopLatch` (software, **bukan** tombol E-stop fisik).
`amr_dashboard/robot_runtime.py` membangun satu set adapter per proses (mirip
`lidar_runtime`), sehingga semua tab browser berbagi adapter yang sama.

Mengganti adapter offline dengan transport terverifikasi = perubahan kecil di
`robot_runtime.build_adapters()` setelah verifikasi + uji fisik disetujui.

---

## 4. Yang sudah diimplementasikan (aman, non-actuating)

- Paket adapter `src/amr_core/robot/` (interfaces, safety, chassis, arm,
  camera, odometry).
- Registry `src/amr_dashboard/robot_runtime.py`.
- Panel `src/amr_dashboard/robot_panel.py`:
  - **Camera (robot)**: menampilkan "NO LIVE FEED" + penyebab spesifik; tidak
    menampilkan placeholder sebagai live feed.
  - **Odometry (robot)**: status `UNAVAILABLE` + "No odometry data available.";
    tidak mengarang posisi.
  - **Remote chassis control**: tombol maju/mundur/kiri/kanan/rotasi/STOP yang
    memvalidasi + clamp tetapi **tidak mengirim**; status koneksi, batas
    kecepatan, dan E-stop software dengan konfirmasi untuk clear.
  - **Arm control**: validasi input joint; **tidak mengirim**; status "NOT
    CONNECTED".
- LiDAR yang sudah ada **tidak diubah** (port, baud, panel, tes tetap).

---

## 5. Yang belum bisa dilakukan dan alasannya

1. **Live camera feed** — Aurora 930 butuh SDK Deptrum/driver ROS; tanpa itu
   tidak ada frame. (Terpasang: tidak. Izin: belum.)
2. **Odometri** — tidak ada node `/odom` (tanpa ROS 2) dan jalur encoder/IMU
   STM32 belum diverifikasi.
3. **Gerak chassis** — transport serialnya sudah ada dan aktif hanya dengan
   `--chassis-live`, tetapi **pola tanda untuk lateral dan putar belum pernah
   diverifikasi di lantai** (hanya pola maju yang terverifikasi translasi).
   Gerbang G1 di `docs/rencana_chassis_live.md` harus dilewati lebih dulu.
4. **E-stop fisik** — tombol E-stop hardware belum diuji (dan tidak boleh diuji
   dengan menggerakkan robot lebih dulu).

---

## 6. Cara menjalankan & mengonfigurasi

Menjalankan dashboard (dari `~/AMRTestLander/AMR_LKS_Dashboard`):

```bash
python run_dashboard.py                     # http://127.0.0.1:8080
python run_dashboard.py --host 0.0.0.0      # akses dari LAN (perhatikan keamanan)
python run_dashboard.py --no-lidar          # tanpa membuka port LiDAR
python run_dashboard.py --lidar-port /dev/ttyUSB1
AMR_LIDAR_PORT=/dev/ttyUSB1 AMR_LIDAR_BAUD=230400 python run_dashboard.py
```

Akses dari laptop (jaringan lokal): buka `http://<ip-pi>:8080`. IP Pi saat audit:
`10.122.66.226`. **Jangan** mengekspos ke internet.

Panel robot (camera/odometry/arm) memakai adapter **offline** pada fase ini;
tidak ada environment variable yang mengaktifkan pengiriman perintah ke
hardware. Perintah yang di-klik hanya divalidasi dan dicatat.

Chassis punya satu pengecualian, dan hanya satu: `--chassis-live`.

```
python run_dashboard.py --chassis-live --chassis-port /dev/ttyACM0
```

Tanpa `--chassis-live`, dashboard tetap offline: chassis divalidasi dan
di-clamp, tidak ada byte yang dikirim, dan robot tidak bisa bergerak. Dengan
flag itu, port STM32 dibuka saat start-up, panel kontrol berubah menjadi
tahan-tekan (maju/mundur/samping/putar + STOP), dan fail-safe aktif: heartbeat
klien, lease kendali, latch E-stop software, dan watchdog board.

Tes & lint:

```bash
python -m pytest -q          # seluruh tes
python -m ruff check .       # lint
python scripts/smoke_dashboard.py   # server + GET '/' (HTTP 200)
```

---

## 7. Prasyarat untuk mengaktifkan transport nyata (langkah berikutnya)

1. Verifikasi protokol `/dev/ttyACM0` di board sekolah **tanpa** menggerakkan
   aktuator (mis. baca status/ID saja) dengan pengawasan.
2. Uji fisik terisolasi (roda diangkat / area aman) untuk chassis dengan batas
   kecepatan rendah, satu perintah pada satu waktu, E-stop fisik siap.
3. Verifikasi jumlah joint, rentang aman, dan arah servo arm dari dokumentasi
   resmi + pengukuran, sebelum menambahkan transport arm.
4. Untuk kamera: setujui instalasi SDK Deptrum (dependency besar) sebelum
   menulis adapter frame.

Rencana implementasi rincinya — kinematika mecanum, adapter serial, fail-safe
hold-to-move, dan gate verifikasi hardware — ada di
`docs/rencana_chassis_live.md` (21 Oktober 2026). Point 3 di atas masih
berlaku: jalur kontrol harus diverifikasi di board sekolah lebih dulu.
