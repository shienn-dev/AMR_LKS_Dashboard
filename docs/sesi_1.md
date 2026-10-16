# Sesi 1 — Audit & Integrasi LanderPi (Ringkasan Proses)

Dokumen ini merangkum **seluruh proses pada sesi 1**: audit kondisi aktual robot,
pemetaan integrasi, implementasi adapter dashboard, audit protokol STM32, pembuatan
parser & listener read-only, sampai audit source upstream. Disusun berdasarkan bukti
yang benar-benar diperiksa — fakta, inferensi, dan hal yang belum diketahui dipisah.

> Prinsip yang dipegang sepanjang sesi: **bukti di atas asumsi**. Tidak ada data
> hardware palsu, tidak ada perintah aktuasi, tidak ada commit/push, LiDAR tidak diubah.

---

## 1. Lingkungan & kondisi awal

| Item | Nilai (terverifikasi) |
| --- | --- |
| Repo dashboard | `~/AMRTestLander/AMR_LKS_Dashboard` (branch `main`, HEAD `b9fb2d1`) |
| Board | Raspberry Pi 5 Model B Rev 1.0, aarch64 |
| OS | Ubuntu 24.04.5 LTS (noble), kernel `6.8.0-1065-raspi` |
| Python | sistem `3.12.3`; venv `~/AMRTestLander/.venv` (nicegui 3.18.0, pyserial 3.5, pytest 9.1.1, ruff 0.17.0) |
| ROS 2 | **Tidak terpasang** (`/opt` kosong, tanpa `ros2`, tanpa paket dpkg ROS) |
| LiDAR | STL-19P/LD19 di `/dev/ttyUSB0` (CH340 `1a86:7523`), 230400 baud — **berfungsi** |
| STM32 | `/dev/ttyACM0`, USB `1a86:55d4` (CDC-ACM) |
| Kamera | **Deptrum Aurora 930** depth camera, USB `3251:1930` — tanpa driver, tanpa `/dev/video` |
| Jaringan | `wlan0 = 10.122.66.226/24`; dashboard di `0.0.0.0:8080` |

Kondisi Git awal: working tree bersih, sinkron `origin/main`, ada stash `lidar-wip-phase1`
(**dipertahankan, tidak disentuh**).

---

## 2. Fase A — Audit kondisi aktual (read-only)

- **Repo/dashboard**: NiceGUI + pyserial, satu loop server-side, LiDAR terintegrasi
  (commit `b9fb2d1`). Entry point `run_dashboard.py` → `amr_dashboard.app.run`.
- **OS/middleware**: tidak ada ROS 2 (dicek via `/opt`, `find setup.bash`, `dpkg`, `env`,
  workspace). Tidak ada node/service robot berjalan. Tidak ada software ROBO JX di Pi.
- **Hardware**: LiDAR `/dev/ttyUSB0` (CH340), STM32 `/dev/ttyACM0` (`1a86:55d4`, cocok
  udev upstream `ros_robot_controller`), kamera Aurora 930 (vendor-specific, kelas `0xFF`,
  tanpa driver). `/dev/video19..37` = ISP/codec internal Pi (`pispbe`/`rpivid`), **bukan** kamera.
- **Upstream Hiwonder/LanderPi**: berbasis **ROS 2** (Pi 5 + STM32) — chassis/odom,
  kamera Deptrum, arm bus-servo, kinematics. Keberadaan upstream ≠ tersedia di robot sekolah.

**Temuan kunci**: robot sekolah = hardware LanderPi **tanpa** stack ROS 2 → antarmuka
upstream (`/odom`, `/cmd_vel`, `/kinematics`, driver kamera) **tidak ada**.

---

## 3. Fase B — Peta integrasi (matriks bukti)

Status bukti: **TERVERIFIKASI** (diperiksa di perangkat) / **SOURCE-ONLY** /
**BELUM DIKETAHUI** / **BLOCKED**.

| Fungsi | Sumber | Status | Catatan |
| --- | --- | --- | --- |
| LiDAR | `/dev/ttyUSB0` LD19 | TERVERIFIKASI | jangan diubah |
| Kamera | Aurora 930 (USB, tanpa driver) | TERVERIFIKASI tidak tersedia | butuh SDK Deptrum |
| Odometri | — | BELUM DIKETAHUI | tanpa `/odom`; encoder STM32 belum terverifikasi |
| Chassis | STM32 `/dev/ttyACM0` | SOURCE-ONLY | protokol belum diverifikasi di board sekolah |
| Arm | bus servo via STM32 | SOURCE-ONLY | idem |
| ROS 2 | — | TERVERIFIKASI absen | jangan pasang tanpa persetujuan |

Arsitektur terpilih: **adapter** (UI tidak bergantung ke transport). Transport nyata
belum diimplementasikan (butuh verifikasi + uji fisik).

---

## 4. Fase C — Implementasi (aman, non-actuating)

### Paket adapter `src/amr_core/robot/`
- `interfaces.py` — tipe & protocol (`ChassisAdapter`, `ArmAdapter`, `OdometrySource`).
- `safety.py` — `SpeedLimits` (±0.30 m/s, ±1.20 rad/s), validasi NaN/Inf, `EStopLatch` (software).
- `chassis.py` / `arm.py` — `OfflineChassisAdapter`/`OfflineArmAdapter` (validasi + catat,
  **tidak mengirim**); `SerialChassisAdapter`/`SerialArmAdapter` (menolak mengirim).
- `camera.py` — `probe_camera()` (read-only; laporkan penyebab).
- `odometry.py` — `NoOdometrySource` (UNAVAILABLE, tidak mengarang pose).

### Dashboard
- `src/amr_dashboard/robot_runtime.py` — registry adapter per-proses.
- `src/amr_dashboard/robot_panel.py` — panel Camera / Odometry / Remote chassis / Arm
  (status jujur; tombol memvalidasi tapi **tidak** mengirim).
- `src/amr_dashboard/app.py` — menambahkan refreshable `robot_view`; panel "Vision" kini
  hanya deteksi simulasi.
- `tests/conftest.py` — reset singleton adapter.

---

## 5. Fase D — Tes

| Perintah | Hasil |
| --- | --- |
| `pytest` (baseline) | **246 passed** |
| `pytest` (setelah adapter robot) | **275 passed** |
| `ruff check .` | **All checks passed!** |
| Smoke test + render check headless | lulus (HTTP 200; panel tampil) |

Guard test `tests/test_robot_no_actuation.py`: paket robot **tidak** meng-import `serial`,
adapter tidak pernah `transmitted=True`.

---

## 6. Restart dashboard

Dashboard lama (PID 5781) dihentikan graceful (atas persetujuan), LiDAR diverifikasi ulang
read-only (**2074 paket, 0 CRC fail, coverage 100%**), lalu dashboard baru dijalankan
(PID 14661, `0.0.0.0:8080`, memegang `/dev/ttyUSB0`).

---

## 7. Investigasi protokol STM32

### 7.1 Source firmware
- **Tidak ada** source firmware STM32 di Pi maupun di repo upstream GitHub.
- Firmware Hiwonder hanya berupa `.hex` (`RosRobotControllerLite20250722.hex`) via bundle
  Google Drive. Board: **STM32F407VET6**.
- Yang tersedia: **host-side SDK** (`ros_robot_controller_sdk.py`) di dua sumber (upstream
  GitHub + bundle "LanderAsli") — keduanya **sepakat** pada inti protokol.

### 7.2 Protokol (SOURCE-ONLY)
- Frame: **`0xAA 0x55 <func> <len> <data…> <crc8>`**; CRC atas `func+len+data`.
- CRC-8: **reflected/LSB-first, poly `0x8C`** (tabel 256 entri; check value `0xA1`).
- Fungsi: SYS=0, LED=1, BUZZER=2, MOTOR=3, PWM_SERVO=4, BUS_SERVO=5, KEY=6, IMU=7,
  GAMEPAD=8, SBUS=9, OLED=10, RGB=11, NONE=12 (drift versi: bundle stok `NONE=11`, tanpa RGB).
- Motor: func 3, `[0x01, n, (id-1:u8, rps:float32)…]`.
- IMU: func 7, `<6f` = ax,ay,az,gx,gy,gz.
- **Tidak ada fungsi encoder.**

### 7.3 Analisis `LanderAsli(Beta).zip`
- Isi: **software sisi-PC (arm + tool) + config rootfs** LanderPi **stok** (Debian 12,
  user `pi`); ROS 2 dijalankan di **Docker** (`MentorPi`). **Bukan** firmware.
- 260 entri, 14 file `.py`; hanya `arm_pc/ros_robot_controller_sdk.py` yang relevan protokol.
- Tidak ada source chassis/motor/odom/kinematics (paket `kinematics` di-import tapi tak ada).
- Ekstraksi read-only ke `/tmp/lander_asli` (~3.4 MiB).

---

## 8. Parser & listener read-only (implementasi sesi ini)

### 8.1 `src/amr_core/robot/stm32_protocol.py`
Decoder murni (tanpa I/O): `crc8`, `Stm32Function`, `Stm32Frame`, `FrameDecoder`,
`decode_imu`/`decode_battery`/`decode_button`/`decode_payload`, `build_frame` (untuk tes).
- CRC diturunkan dari SDK stok dan **diverifikasi** terhadap implementasi bitwise
  independen + check value `0xA1`.
- Hanya payload yang **terbukti** yang di-decode; lainnya dicatat mentah (**unrecognized**).

### 8.2 `src/amr_core/robot/stm32_listener.py`
Listener **mode replay saja**: `Stm32Listener` (feed byte → decode → catat, buffer & record
dibatasi, statistik), `replay_bytes`, `replay_file`. `SerialTransport` **inert** (menolak
buka). Tidak ada `import serial`, tidak ada `.write(` (diuji via AST).

### 8.3 Tes
- `tests/test_stm32_protocol.py` — **25 tes**.
- `tests/test_stm32_listener.py` — **17 tes**.
- **Total suite: 317 passed, Ruff clean.**

---

## 9. Audit kesiapan uji read-only STM32

- **Spontan vs polling**: SDK hanya menyetel flag host (`enable_reception`); `get_imu/battery/button`
  **hanya baca queue** → firmware kemungkinan **mengirim spontan** (SOURCE-ONLY).
- **Risiko buka `/dev/ttyACM0`**: DTR/RTS dapat **me-reset** board (SDK set `dtr/rts=False`
  sebelum open — mengurangi, bukan menjamin); **ModemManager aktif** tanpa rule
  `ID_MM_PORT_IGNORE`; tidak ada proses lain memegang port saat ini.
- **Prasyarat**: izin pemilik + pengawasan, robot diamankan, E-stop siap, path `by-id`,
  hanya baca, buffer/durasi dibatasi.
- **Parser dapat membaca tanpa mengirim byte** (murni; tanpa I/O).

---

## 10. Audit source upstream (jawaban ringkas)

- **Odometri**: `odom_publisher_node.py` `cal_odom_fun` **mengintegralkan kecepatan perintah**
  (dead-reckoning), bukan encoder; IMU dipublikasikan terpisah; `robot_localization` EKF
  memfusi (`odometry/filtered → odom`). Jadi **bukan** odometri encoder, **bukan** LiDAR.
- **`/cmd_vel` → motor**: Twist → `mecanum.set_velocity` (m/s→rps) → `MotorsState` →
  topik `ros_robot_controller/set_motor` → `board.set_motor_speed` (func 3).
- **Kecepatan per roda**: **ya** (`MotorState{uint16 id, float64 rps}`).
- **Encoder**: **tidak** dilaporkan oleh STM32.
- **Kompatibilitas parser**: byte-level (layout, CRC, IMU/battery/button) **cocok** dengan
  source ini. Perbedaan kebijakan: parser menerima `func ≥ 12` (receiver stok menolak);
  strategi resync CRC sedikit berbeda.

---

## 11. Tambahan kode, file, dan fungsinya

### 11.1 File baru — paket adapter `src/amr_core/robot/`

| File | Kelas / fungsi | Kegunaan |
| --- | --- | --- |
| `__init__.py` | — | penanda paket |
| `interfaces.py` | `ConnectionState` | enum status koneksi (DISABLED/UNAVAILABLE/DISCONNECTED/CONNECTED) |
| | `ChassisCommand` | perintah kecepatan (linear_x, linear_y, angular_z) + `is_zero()` |
| | `ArmCommand` | perintah arm (positions, duration_s) |
| | `CommandOutcome` | hasil submit (accepted, transmitted, reason) |
| | `OdometrySample` | satu sampel odometri (x, y, yaw, kecepatan, stamp, source, valid) |
| | `CameraStatus` | status ketersediaan kamera (state, kind, device, detail, frames_available) |
| | `ChassisAdapter` / `ArmAdapter` / `OdometrySource` | Protocol (kontrak antarmuka) |
| `safety.py` | `SpeedLimits` | batas kecepatan chassis + `clamp()` |
| | `validate_chassis_command()` | tolak NaN/Inf, clamp ke batas |
| | `validate_arm_command()` | clamp pulse 0..1000, durasi 0.02..30 s |
| | `EStopLatch` | latch stop **software** (`trip`, `clear(confirmed_safe=...)`) |
| `chassis.py` | `OfflineChassisAdapter` | validasi+clamp+catat, **tidak mengirim** (`submit`, `stop`, `state`, `last_command`) |
| | `SerialChassisAdapter` | placeholder yang **menolak** mengirim |
| `arm.py` | `OfflineArmAdapter` / `SerialArmAdapter` | idem untuk arm |
| `camera.py` | `probe_camera()` | probe read-only: deteksi UVC vs Aurora 930, laporkan penyebab |
| | `_uvc_nodes()`, `_usb_present()` | helper baca sysfs |
| `odometry.py` | `NoOdometrySource` | sumber "tidak ada" (UNAVAILABLE, tak pernah memberi sampel) |
| | `validate_sample()` | validasi sampel (finite) |
| `stm32_protocol.py` | `crc8()` | CRC-8 reflected poly 0x8C (tabel diambil dari SDK stok) |
| | `Stm32Function` | enum kode fungsi (SYS..OLED) |
| | `Stm32Frame` | frame tervalidasi |
| | `ImuReading` / `BatteryReading` / `ButtonEvent` | tipe payload yang di-decode |
| | `decode_imu` / `decode_battery` / `decode_button` / `decode_payload` | decoder payload (hanya format terbukti) |
| | `FrameDecoder` | parser inkremental (`feed`, `pending`, `reset`); tahan data parsial, multi-frame, CRC salah, resync, buffer dibatasi |
| | `build_frame()` | encoder frame (khusus tes) |
| `stm32_listener.py` | `Stm32Listener` | konsumsi byte → decode → catat (`feed`, `records`, `raw_records`, `stats`, `summary`) |
| | `RawRecord` / `FrameRecord` / `ListenerStats` | tipe record & statistik |
| | `function_name()` | nama fungsi / `UNKNOWN(0x..)` |
| | `replay_bytes()` / `replay_file()` | mode replay (tanpa serial) |
| | `SerialTransport` (+ `SerialTransportDisabled`) | placeholder inert yang **menolak** buka port |

### 11.2 File baru — dashboard

| File | Kelas / fungsi | Kegunaan |
| --- | --- | --- |
| `src/amr_dashboard/robot_runtime.py` | `RobotAdapters` | wadah adapter per-proses |
| | `build_adapters()` / `get_adapters()` / `reset_adapters()` | bangun / ambil / reset singleton |
| `src/amr_dashboard/robot_panel.py` | `robot_panels()` | render semua panel robot |
| | `camera_panel()`, `odometry_panel()` | status jujur (tanpa feed/pose palsu) |
| | `chassis_control_panel()`, `arm_control_panel()` | kontrol offline (validasi, **tidak** mengirim) |
| | `_estop_controls()` | E-stop software + konfirmasi untuk clear |
| | `_state_badge()`, `_report()`, `_metric()` | helper tampilan |

### 11.3 File baru — tes

| File | Jumlah | Cakupan |
| --- | --- | --- |
| `tests/test_robot_safety.py` | 6 | clamp, NaN/Inf, clamp arm, E-stop |
| `tests/test_robot_chassis.py` | 6 | offline validate/clamp, stop, state, serial menolak |
| `tests/test_robot_arm.py` | 5 | idem untuk arm |
| `tests/test_robot_camera.py` | 4 | probe (none / depth / uvc / node internal Pi) |
| `tests/test_robot_odometry.py` | 3 | `NoOdometrySource`, `validate_sample` |
| `tests/test_robot_runtime.py` | 3 | build & singleton |
| `tests/test_robot_no_actuation.py` | 2 | paket tidak impor `serial`, tidak transmit |
| `tests/test_stm32_protocol.py` | 25 | CRC vs referensi, frame valid/rusak/terpotong, batas buffer, payload |
| `tests/test_stm32_listener.py` | 17 | replay, CRC/noise/unknown, batas record, tanpa serial/write |

Total tes baru = **71** (baseline 246 → **317**).

### 11.4 File yang diubah

| File | Perubahan | Kegunaan |
| --- | --- | --- |
| `src/amr_dashboard/app.py` | tambah refreshable `robot_view` + panggil panel robot; panel "Vision" disederhanakan | menampilkan panel robot di dashboard |
| `tests/conftest.py` | reset singleton adapter robot | isolasi antar-tes |

### 11.5 Dokumen

| File | Isi |
| --- | --- |
| `docs/robot_integration.md` | matriks bukti, arsitektur adapter, cara jalan, prasyarat |
| `docs/sesi_1.md` | ringkasan proses sesi ini |

### 11.6 Yang TIDAK dilakukan

commit, push, reset, clean, ubah stash, ubah LiDAR/udev/ModemManager/service/OS.

---

## 12. Batasan & yang BELUM terbukti

- **Belum ada pengujian hardware** untuk STM32; tidak ada port yang dibuka.
- **Kompatibilitas board sekolah (ROBO JX) belum terbukti** dengan protokol stok.
- Apakah board sekolah memancarkan IMU/SYS/KEY spontan — belum diketahui.
- Odometri encoder **tidak tersedia** lewat protokol ini.
- Kamera Aurora 930 butuh SDK Deptrum (dependency besar → butuh persetujuan).

---

## 13. Langkah berikutnya

1. Konfirmasi pemilik: apakah modifikasi ROBO JX mengubah firmware/protokol; minta source
   firmware / dokumen protokol RRC Lite.
2. (Opsional) catat/uji bahwa receiver stok menolak `func ≥ 12`.
3. Setelah izin + pengawasan: **satu sesi listen read-only** ke `/dev/ttyACM0`
   (`dtr/rts=False`, hanya baca) untuk membuktikan board bicara protokol ini.
4. Baru setelah itu: pertimbangkan transport serial read-only (terpisah dari replay).
5. Motor/arm hanya setelah verifikasi protokol + uji fisik terisolasi (roda terangkat, E-stop siap).
