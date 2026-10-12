# Arsitektur Aplikasi AMR LKS (Inti)

Oct 10, 2026 · @yokos

## Tujuan dan prinsip desain

Dokumen ini adalah acuan tunggal untuk membangun aplikasi robot AMR LKS. Isinya menjadi kontrak bagi manusia dan asisten AI: kode yang ditulis harus sesuai dokumen ini, dan perubahan desain dicatat di sini dulu sebelum masuk ke kode. Platform latihan saat ini adalah Hiwonder LanderPi (Raspberry Pi 5 + RRC Lite STM32), tetapi aplikasinya dirancang agar bisa dipindah ke robot rakitan tim.

**Lingkup:** perangkat lunak di atas driver platform (LanderPi atau robot custom) (misi, skill gerak, visi, navigasi, operasional, dashboard) untuk LKS 2026, dan tetap bisa dipakai saat aturan 2027 berubah.

**Prinsip desain**

1. **Misi adalah data, bukan kode.** Arena, titik target, urutan tugas, dan warna rak ditulis di file YAML. Aturan baru cukup diterjemahkan menjadi file misi baru.
2. **Robot mandiri saat lomba.** Tidak bergantung pada internet, laptop, maupun Wi-Fi selama run. Start lewat tombol fisik; e-stop memutus daya aktuator secara fisik.
3. **Setiap langkah punya batas waktu dan aturan gagal.** Tidak ada kondisi "menunggu selamanya".
4. **Robot memberi tahu kondisinya sendiri** lewat LED, buzzer, dan OLED.
5. **Satu sumber kebenaran.** Nama topik, frame, dan format pesan hanya didefinisikan di dokumen ini dan di satu modul konstanta di kode.
6. **Sederhana dan bisa dijelaskan siswa.** Kriteria C menilai kepemilikan rekayasa; tim harus bisa menjelaskan setiap keputusan.

**Status fakta.** Setiap pernyataan teknis diberi label agar asisten AI dan anggota tim tahu mana yang boleh dipakai sebagai dasar kode.

| Label | Arti | Boleh jadi dasar kode? |
| --- | --- | --- |
| Terverifikasi | Dibaca langsung dari kode repo, dokumen lomba, atau diukur di robot | Ya |
| Asumsi | Inferensi kuat, belum diuji di robot | Ya, dengan tes yang membuktikannya |
| Perlu konfirmasi | Bergantung pada keputusan panitia atau pengukuran | Tidak, sampai dikonfirmasi |

Sumber utama: [repo Hiwonder/LanderPi](https://github.com/Hiwonder/LanderPi), Kisi-kisi LKS Nasional AMR 2026, dan Deskripsi Teknis LKS AMR Provinsi Jawa Tengah 2026.

## Keterlacakan: penilaian ke komponen

Sebanyak 63 dari 100 poin (D, E, G) dinilai dari performa otonom, dan sebagian besar bersifat biner 1/0, jadi keandalan setiap langkah lebih penting daripada kecepatan. Tabel ini memakai skema penilaian Provinsi Jawa Tengah 2026; kisi-kisi nasional memakai pembagian modul berbeda (A 8, B 10, C 10, D 12, E 60) tetapi jenis tugasnya sama.

| Kriteria (bobot) | Yang dinilai | Kebutuhan sistem | Komponen penanggung jawab |
| --- | --- | --- | --- |
| A Organisasi (10) | Hadir tepat waktu, robot terakit lengkap akhir hari 1, area rapi | Robot siap dari boot tanpa perakitan ulang | Checklist hari lomba, auto-start |
| B Komunikasi (7) | Penalti menyentuh robot/laptop tanpa izin; panggilan ready, retry, reset, finish | RESET dan RETRY dari tombol robot, tanpa laptop | State machine operasional, tombol fisik |
| C Desain (10) | E-stop mudah diakses dan berfungsi; wiring berkode warna; modularitas; orisinalitas (2 poin) | E-stop pemutus daya; subsistem bisa dilepas; tim mampu menjelaskan desain | Hardware, dokumen ini sebagai bahan laporan teknis |
| D Gerak dasar (10) | Putar 90° kanan dan 180° kiri, wall following kanan dan kiri, berhenti di dinding, ambil dan letakkan kubus | Kontrol heading IMU, wall following LiDAR, skill ambil/letakkan | Skill `turn_heading`, `wall_follow`, `stop_at_wall`, `pick`, `place` |
| E Navigasi (13) | Start dengan satu tekan tombol fisik; 4 target berurutan acak; obstacle dari juri; waktu ≤ 600 s | Titik bernama, urutan dari file misi, Nav2 menghindari obstacle | Skill `go_to`, pengelola misi, Nav2 |
| F Visi (10) | Identitas 9 objek (3 warna × 3 bentuk) tampil di feed atau print | Deteksi warna dan bentuk, overlay label pada feed | Node visi, dashboard mode demo |
| G Performa (40) | G1 statis (16) dan G2 dinamis (24): start tombol, ambil objek, letakkan di slot benar, kembali ke home, nilai waktu | Misi end-to-end, membaca kondisi aktual sebelum placement (G2) | Pengelola misi, semua skill, visi |

Bobot terbesar di G: meletakkan di slot benar (30%) dan mengambil objek (25%). Kembali ke home bernilai 10%, sehingga pengelola misi wajib menyisakan waktu untuk pulang.

## Keputusan tech stack

Fondasi ROS2 Humble di Raspberry Pi 5 dipertahankan (di LanderPi beserta driver Hiwonder); tim menambah lapisan misi, skill, operasional, dan dashboard dalam Python. Setiap pilihan diuji dengan lima pertanyaan: diizinkan aturan, jalan tanpa internet, bisa dijelaskan siswa, tetap berguna jika aturan berubah, dan sudah teruji di repo.

| Area | Keputusan | Alasan | Status |
| --- | --- | --- | --- |
| Kontroler utama | Raspberry Pi 5 | Aturan hanya mengizinkan Raspberry Pi atau myRIO | Terverifikasi |
| Kontroler motor | Per platform: RRC Lite dengan protokol serial Hiwonder (LanderPi); STM32 Nucleo dengan micro-ROS (robot custom) | Detail di dokumen platform; juri lomba sebelumnya mengizinkan STM32 Nucleo sebagai slave controller | Perlu konfirmasi (STM32 sebagai co-controller) |
| OS dan middleware | Ubuntu 22.04 + ROS2 Humble dalam image Docker milik tim (Dockerfile di repo), dipakai di semua platform | Seluruh paket repo dibuat untuk Humble; Raspberry Pi 5 tidak didukung resmi Ubuntu 22.04, jadi container diperlukan di robot mana pun | Terverifikasi |
| Bahasa | Python (rclpy); C++ hanya jika ada bottleneck terukur | Aturan mengizinkan Python; repo berbahasa Python; paling mudah dipelajari | Terverifikasi |
| Fusi sensor | EKF `robot_localization` (odometri + IMU) dari repo | Sudah ada di `ekf.yaml` | Terverifikasi |
| Peta dan lokalisasi | slam\_toolbox untuk pemetaan, AMCL untuk lokalisasi | Bawaan repo; arena kecil dan statis | Terverifikasi |
| Navigasi titik | Nav2, dikonfigurasi per platform (Mecanum, omni 3 roda) | Menangani obstacle dan perencanaan ulang jalur | Asumsi (perlu tuning) |
| Gerak dasar Modul D | Kontroler reaktif sendiri: heading dari IMU, wall following dari LiDAR + PID | Lebih presisi dan mudah dijelaskan daripada lewat Nav2 | Asumsi |
| Visi | Objek yang sudah diketahui: OpenCV, HSV untuk warna dan kontur untuk bentuk | Ringan di CPU Pi, bisa dikalibrasi ulang di arena | Asumsi |
| Visi objek baru | Jalur utama: pendaftaran di tempat. Ciri warna dan bentuk OpenCV digabung dengan embedding dari model klasifikasi kecil yang sudah dilatih (misalnya keluarga MobileNet lewat ONNX Runtime di CPU), lalu diklasifikasi kNN. Cadangan: model zero-shot kecil (misalnya CLIP) yang mencocokkan gambar dengan daftar nama. Semua bobot model disimpan di image Docker tim. | Juri yang merujuk WSC bisa meminta identifikasi objek yang belum pernah dilihat; kNN tidak butuh pelatihan berat, jadi pendaftaran selesai dalam menit tanpa internet | Asumsi; perlu uji akurasi dengan set tersembunyi dan uji beban CPU |
| Kamera | Satu kamera depth (rencana tim); webcam USB disiapkan sebagai cadangan | Aturan: maksimal 1 webcam | Perlu konfirmasi (status kamera depth) |
| Pengelola misi | State machine Python + file misi YAML | Misi menjadi data; kode ratusan baris yang bisa dibaca siswa | Keputusan tim |
| Prioritas perintah gerak | `twist_mux`: stop > manual > skill/Nav2 | Perintah berhenti selalu menang | Asumsi |
| Auto-start | `systemd` | Robot READY setelah boot; node crash di-restart | Asumsi |
| Dashboard operator | NiceGUI (Python) sebagai node ROS2; cadangan HTML + roslibjs lewat rosbridge | Satu bahasa, akses langsung ke file misi; offline | Perlu uji beban CPU |
| Alat engineer | RViz2 atau Lichtblick | Visualisasi peta, scan, dan jalur selama pengembangan | Keputusan tim |
| Rekaman | `ros2 bag` + log misi | Analisis kegagalan dan bahan laporan teknis | Keputusan tim |

**Tidak dipakai:** paket `large_models` (butuh internet), micro-ROS di LanderPi (protokol Hiwonder sudah berfungsi; robot custom memakai micro-ROS di Nucleo, lihat dokumen platform), Behavior Tree XML untuk misi (sulit dijelaskan siswa), lengan 6-DOF bawaan untuk lomba (kemungkinan melanggar batas 3 standard servo).

**Risiko umur:** dukungan resmi ROS2 Humble berakhir sekitar Mei 2027. Kode misi dan skill ditulis tanpa ketergantungan khusus Humble agar bisa pindah ke ROS2 Jazzy.

## Arsitektur dan kontrak antarmuka

Aplikasi tersusun dalam lapisan; setiap lapisan hanya memanggil lapisan tepat di bawahnya, dan konfigurasi YAML masuk dari samping. Aturan lomba baru menyentuh konfigurasi dan misi; platform baru hanya menyentuh adaptor platform, driver, dan hardware.

&#91;embedded content: arsitektur berlapis · 6 lapisan, 3 file konfigurasi\]

Lapisan berwarna adalah kode tim; lapisan polos diambil dari repo Hiwonder atau paket ROS2 standar dan hanya dikonfigurasi.

**Kontrak antarmuka.** Nama di tabel ini adalah satu-satunya nama yang boleh dipakai di kode, dan didefinisikan sekali di `amr_core/interfaces.py`. Kode tim hanya memakai baris "Kode tim"; topik khusus Hiwonder hanya boleh muncul di dalam paket adaptor amr\_platform\_landerpi. Nama yang terverifikasi dibaca dari kode repo Hiwonder; tetap cocokkan dengan snapshot dari robot.

| Nama | Tipe | Arah | Dipakai oleh | Status |
| --- | --- | --- | --- | --- |
| `/scan` | `sensor_msgs/LaserScan` | platform → Nav2, skill | Kode tim | Terverifikasi di LanderPi (filter dari `scan_raw`) |
| `/odom` + TF `odom` → `base_footprint` | `nav_msgs/Odometry` | platform (EKF) → Nav2, skill | Kode tim | Terverifikasi di LanderPi (remap dari `odometry/filtered`) |
| `/imu` | `sensor_msgs/Imu` | platform → EKF, `turn_heading` | Kode tim | Rancangan; di LanderPi dipetakan dari `/ros_robot_controller/imu_raw` |
| `/image` | `sensor_msgs/Image` | platform → amr\_vision | Kode tim | Rancangan; nama asli diambil dari snapshot |
| `cmd_vel_in` (ke twist\_mux) | `geometry_msgs/Twist` | skill, Nav2 → twist\_mux → platform | Kode tim | Rancangan |
| `/amr/hw/button` | pesan tim: tombol, jenis tekan | platform → amr\_ops | Kode tim | Rancangan |
| `/amr/hw/estop` | `std_msgs/Bool` | platform → amr\_ops | Kode tim | Rancangan (relevan untuk e-stop opsi B) |
| `/amr/hw/indicator` | pesan tim: warna, pola buzzer, teks | amr\_ops → platform | Kode tim | Rancangan |
| `/amr/hw/battery` | `std_msgs/Float32`, volt | platform → amr\_ops | Kode tim | Rancangan |
| `oms/lift`, `oms/grip`, oms/store, oms/retrieve | action tim | skill `pick`/`place` → platform | Kode tim | Rancangan |
| `/amr/mission_state` | pesan tim: state, langkah aktif, waktu | amr\_mission → dashboard, amr\_ops | Kode tim | Rancangan |
| `/amr/start`, `/amr/reset`, `/amr/load_mission` | service tim | amr\_ops, dashboard → amr\_mission | Kode tim | Rancangan |
| `/amr/vision/detections`, `/amr/vision/annotated` | pesan tim; `sensor_msgs/Image` berlabel | amr\_vision → misi, dashboard | Kode tim | Rancangan |
| Frame `map` → `odom` → `base_footprint` | TF | AMCL, EKF | Kode tim | Terverifikasi di LanderPi |

Pemetaan kontrak ke topik dan perangkat tiap robot ada di dokumen platform: Platform LanderPi — Spesifikasi dan Adaptor dan Platform Robot Custom — Spesifikasi dan Firmware.

Nama topik kamera asli tiap platform diambil dari snapshot dan dipetakan ke /image oleh adaptor; contoh di LanderPi: `/ascamera/camera_publisher/rgb0/image` (detail di dokumen platform).

## Kesiapan multi-platform

Semua kode tim hanya berbicara dengan **kontrak platform**; setiap robot menyediakan satu paket adaptor yang memenuhinya. Ukuran keberhasilannya: file `missions/*.yaml` yang sama lulus di dua platform tanpa mengubah kode misi, skill, atau dashboard. Parameter tuning (kecepatan, toleransi, Nav2) boleh berbeda per platform.

| Platform | Peran | Adaptor | Komponen |
| --- | --- | --- | --- |
| `landerpi` | Robot latihan dan kandidat robot lomba | `amr_platform_landerpi`: membungkus driver Hiwonder ke kontrak | Raspberry Pi 5, RRC Lite STM32, MS200, roda Mecanum |
| `custom` | Robot lomba jika platform Hiwonder tidak diizinkan | `amr_platform_custom`: kinematika omni, odometri, jembatan topik micro-ROS (tombol, LED, sinyal e-stop lewat Nucleo) | Raspberry Pi 5, motor PG36, roda omni 100 mm, STM32 Nucleo sebagai slave controller lewat micro-ROS (PID kecepatan roda, encoder, tombol, sinyal e-stop); kinematika omni dan odometri dihitung di Pi |
| `mock` | Tes otomatis tanpa robot | `amr_platform_mock`: odometri dari integrasi `cmd_vel`, tombol dari terminal | Tidak ada hardware |

Spesifikasi hardware, adaptor, firmware, dan hasil ukur tiap robot ada di Platform LanderPi — Spesifikasi dan Adaptor dan Platform Robot Custom — Spesifikasi dan Firmware. Dokumen platform hanya memetakan ke kontrak di dokumen ini, tidak mendefinisikannya ulang; hal yang berlaku untuk kedua robot selalu ditulis di dokumen ini.

Setiap platform punya folder `config/platforms/<nama>/` berisi URDF dan posisi sensor, footprint, batas kecepatan, parameter Nav2, dan kalibrasi odometri. Platform dipilih dengan satu argumen: `ros2 launch amr_bringup robot.launch.py platform:=custom`. Kedua robot memakai image Docker milik tim yang sama, karena Raspberry Pi 5 tidak didukung resmi Ubuntu 22.04.

**Varian untuk keputusan panitia yang datang terlambat**

| Keputusan panitia | Varian yang disiapkan dan diuji sekarang | Cara beralih |
| --- | --- | --- |
| Servo bus dilarang | OMS tim: lifter L-Channel + gripper dengan ≤ 3 servo PWM (RRC Lite punya 4 port servo PWM) | Ganti modul OMS mekanik dan `oms_impl` di konfigurasi platform |
| Kamera depth tidak dihitung webcam | Kamera depth jalur utama; webcam USB disiapkan dan diuji sebagai cadangan; node visi membaca topik gambar dari parameter | Ganti satu parameter |
| E-stop wajib memutus daya, atau cukup motor | Tombol e-stop dua kontak NC, harness berkonektor untuk opsi A dan B | Pindah colokan harness |
| Platform Hiwonder dilarang | Robot `custom` dengan kontrak yang sama | `platform:=custom` |

OMS tim dengan servo PWM juga dipasang di LanderPi, sehingga menjadi jalur utama di kedua robot dan menambah bukti orisinalitas untuk Kriteria C.

**Konsekuensi negatif dan mitigasinya**

| Konsekuensi | Dampak | Mitigasi |
| --- | --- | --- |
| Pekerjaan awal bertambah | Kontrak, adaptor, mock, dan Dockerfile dikerjakan sebelum robot terlihat bergerak | Adaptor LanderPi dibuat tipis dulu; Gazebo tidak dibuat |
| Beban uji berlipat | Setiap perubahan idealnya diuji di setiap platform | Tes otomatis di mock untuk setiap commit; uji di robot kedua hanya uji asap rutin |
| Fitur khusus satu platform tidak bisa jadi inti | Lengan 6-DOF hanya ada di LanderPi; begitu pula setiap kemampuan yang hanya ada di satu robot | Fitur semacam ini dibuat opsional lewat penanda kemampuan platform, bukan bagian misi wajib |
| Abstraksi tidak menyembunyikan fisika | Kinematika omni vs Mecanum, selip roda, tinggi LiDAR, dan kecepatan maksimal berbeda | Misi memakai titik bernama dan skill, bukan kecepatan absolut; tuning dan kalibrasi disimpan per platform |
| Perhatian tim terbelah | Tim dua orang merawat dua robot; risiko keduanya setengah matang | Gerbang keputusan: satu platform ditetapkan sebagai utama, yang lain dirawat di level uji asap |
| Debugging lebih berlapis | Kesalahan bisa ada di misi, adaptor, atau driver vendor | Adaptor memublikasikan status kesehatan; snapshot `ros2` per platform |
| Docker menambah kerumitan akses hardware | GPIO, serial, dan kamera harus dipetakan ke dalam container | Pemetaan perangkat ditulis sekali di Dockerfile dan compose, lalu diuji di kedua robot |
| Pembaruan dari Hiwonder bisa merusak adaptor | Image atau driver baru mengubah nama topik atau perilaku | Versi vendor dikunci di `src/vendor/`; pembaruan hanya lewat keputusan tercatat |
| Fleksibilitas software tidak memperbaiki orisinalitas hardware | Robot kit yang dirakit apa adanya tetap berisiko nilai rendah di Kriteria C | OMS dan modifikasi mekanik dirancang tim |
| Ada sedikit lompatan topik tambahan | Adaptor menambah satu node antara | Jalur keselamatan (e-stop, watchdog) tidak lewat adaptor; e-stop tetap hardware |

Kesimpulannya, biaya fleksibilitas lebih kecil daripada menulis ulang software beberapa hari sebelum lomba, karena keputusan platform baru diketahui terlambat. Syaratnya, cakupan dijaga ramping: mock ya, Gazebo tidak, dan satu platform utama ditetapkan pada tanggal yang disepakati tim.

**Urutan kerja**

1. Kontrak platform, platform `mock`, dan Dockerfile tim
2. Adaptor `landerpi`, agar misi dan skill segera diuji di robot nyata
3. Robot `custom` sampai level bergerak, odometri, LiDAR, START dan e-stop
4. OMS tim (lifter + gripper), dipasang di kedua robot
5. Latihan pergantian platform secara rutin: misi yang sama di dua robot

## Desain OMS dan magazin

OMS (sistem manajemen objek) dibangun bertahap: gripper + lifter untuk satu kubus dulu sampai andal, lalu magazin carousel sebagai modul tambahan yang dibaut. Keputusan memakai magazin di lomba diambil setelah test project menunjukkan jumlah objek per run; format penilaian G1/G2 menulis "object target" (tunggal) dan Modul D hanya satu kubus.

**Anggaran aktuator** mengikuti batas aturan (4 motor DC, 3 standard servo, 2 continuous servo); alokasinya per robot ada di Platform LanderPi — Spesifikasi dan Adaptor (keempat motor DC untuk roda, lifter memakai servo) dan Platform Robot Custom — Spesifikasi dan Firmware (satu motor DC tersisa untuk lifter).

**Konsep magazin**

| Konsep | Cara kerja | Aktuator | Urutan keluar | Cocok untuk sortir warna |
| --- | --- | --- | --- | --- |
| Carousel 3–4 kantong (dipilih) | Kantong diputar ke depan gripper | 1 servo: standard 270° atau continuous + sensor | Bebas | Paling cocok |
| Tumpukan vertikal | Kubus ditumpuk, keluar dari bawah | 1 servo untuk pintu atau pendorong | Tetap: masuk pertama, keluar pertama | Hanya bila urutan ambil diatur |
| Baki geser linier | Baki berkantong digeser ke posisi gripper | 1 servo + tuas, atau continuous servo | Bebas, lebih lambat | Cukup |

Alokasi servo usulan: gripper buka/tutup (1 standard), indeks carousel (1 standard), cadangan untuk wrist atau pengunci (1 standard); lifter memakai motor DC di robot `custom` atau continuous servo di `landerpi`.

**Batasan fisik yang dihitung di CAD sebelum fabrikasi**

- Kubus 65 mm, sehingga kantong sekitar 70 mm; carousel 3 kantong diperkirakan sekitar 200 mm diameternya. Sulit muat di lebar LanderPi 174 mm, lebih realistis di robot `custom`.
- Lifter menjangkau puncak stand (100 mm) dan setiap ketinggian slot rak; angka slot diambil dari gambar teknis rak.
- Muatan 3–4 kubus × 50–60 g; pusat massa naik, jadi akselerasi Nav2 dibatasi saat magazin terisi.
- Satu sensor jarak IR per kantong untuk memastikan isi (aturan mengizinkan 4 sensor IR).

**Dampak ke software**

- Kontrak OMS bertambah: action `oms/store(kantong)` dan `oms/retrieve(kantong)`.
- Pengelola misi menyimpan inventaris magazin: kantong mana berisi kubus apa. Kamera memverifikasi ulang sebelum meletakkan.
- Urutan antar dihitung otomatis; dengan 3 rak, semua kemungkinan urutan bisa dicoba.
- Parameter misi `capacity`: nilai 1 berarti mode tanpa magazin, sehingga software tetap jalan bila magazin rusak, dilarang, atau tidak berguna.

**Riset ke panitia untuk OMS:** apakah servo bus dihitung sebagai standard servo, dan apakah aktuator di luar daftar (stepper, solenoid) dilarang.

## Katalog skill robot

Skill adalah satu-satunya cara misi menggerakkan robot. Setiap skill bisa diuji sendiri, menerima parameter dari YAML, dan selalu mengembalikan salah satu dari empat hasil: `SUCCESS`, `FAILURE`, `TIMEOUT`, atau `ABORTED` (dihentikan dari luar), plus pesan alasan. Skill baru untuk aturan 2027 ditambahkan ke katalog ini dulu, baru ditulis kodenya.

| Skill | Parameter utama | Sukses bila | Mode gagal yang ditangani | Modul |
| --- | --- | --- | --- | --- |
| `turn_heading` | `angle_deg`, `direction`, `tolerance_deg` | Selisih yaw IMU ≤ toleransi | Tidak konvergen dalam timeout | D |
| `wall_follow` | `side` (kiri/kanan), `distance_m`, `speed`, `until` (dinding depan / jarak / waktu) | Kondisi `until` tercapai tanpa menabrak | Dinding hilang dari LiDAR, timeout | D |
| `stop_at_wall` | `distance_m` | Jarak depan ≤ nilai target dan robot diam | Sensor depan tidak valid | D |
| `go_to` | `target` (nama titik di arena.yaml), `tolerance_m`, `retry` | Nav2 melaporkan goal tercapai | Nav2 gagal atau macet, lokalisasi tidak yakin | E, G |
| `align_reference_line` | `target` (nama stand), `offset_m` | Robot sejajar garis referensi dalam toleransi | Garis tidak terlihat | D, G |
| `detect_object` | `expected` (opsional), `min_confidence` | Warna dan bentuk terbaca stabil N frame | Tidak ada objek, hasil tidak konsisten | F, G2 |
| `pick` | `object_height_m` | Sensor gripper atau kamera memastikan objek terpegang | Objek lepas, gripper macet | D, G |
| `place` | `rack`, `slot` | Objek terlepas di slot, gripper kosong | Slot tidak terjangkau | D, G |
| `return_home` | `tolerance_m` | Robot di zona home dan berhenti | Sama dengan `go_to` | E, G |
| `wait_for_start` | sumber tombol | Tombol start ditekan sekali | Tidak berlaku (menunggu tanpa batas di READY) | Semua |

Aturan bersama untuk semua skill:

- Batas waktu dan jumlah retry datang dari file misi, bukan dikunci di kode. Sudut di YAML boleh dalam derajat (akhiran \_deg) dan dikonversi ke radian saat dimuat; di dalam kode semua satuan SI (REP-103).
- Skill tidak memanggil skill lain; urutan hanya diatur pengelola misi.
- Saat dibatalkan, skill wajib mengirim kecepatan nol sebelum keluar.
- Implementasi `pick` dan `place` bergantung pada OMS rancangan tim, sehingga antarmukanya ditetapkan sekarang dan isinya menyusul.

## Skema konfigurasi

Tiga jenis file memisahkan apa yang berubah: `arena.yaml` (dunia), `missions/*.yaml` (tugas), dan `calibration/*.yaml` (kondisi lokasi). Semua file divalidasi terhadap skema saat dimuat; file yang tidak valid ditolak dan robot tidak masuk READY. Angka di contoh bawah adalah ilustrasi format, bukan ukuran arena sebenarnya.

**arena.yaml** — titik bernama dalam frame `map`, satuan meter dan radian (REP-103).

```yaml
arena:
  name: lks2026_jateng
  map_file: maps/lks2026_jateng.yaml
points:            # x, y dalam meter; yaw dalam radian
  home:   {x: 0.30, y: 0.30, yaw: 0.0}
  T1:     {x: 1.20, y: 0.60, yaw: 1.57}
  stand_1: {x: 2.00, y: 1.10, yaw: 0.0, reference_line: true}
  rack_A:  {x: 3.50, y: 0.40, yaw: -1.57}
racks:
  rack_A: {slots: [red, blue, green]}   # urutan warna diisi sesuai soal
```

**missions/modul\_E.yaml** — urutan target diisi saat juri mengumumkan acakan.

```yaml
mission: modul_E
version: 1
time_limit_s: 600
reserve_for_home_s: 60      # sisa waktu minimal untuk pulang
start: physical_button
steps:
  - for_each: {targets: [T3, T1, T4, T2]}
    do: {skill: go_to, timeout_s: 90, retry: 2, on_fail: skip}
  - {skill: return_home, timeout_s: 90}
```

**missions/G2.yaml** — persepsi menentukan tujuan saat run.

```yaml
mission: G2
version: 1
time_limit_s: 600
steps:
  - {skill: go_to, target: stand_1}
  - {skill: align_reference_line, target: stand_1}
  - {skill: detect_object, save_as: obj}
  - {skill: pick, retry: 1}
  - {skill: go_to, target: "rack_for(obj.color)"}
  - {skill: place, slot: "slot_for(obj.color)"}
  - {skill: return_home}
```

**calibration/lokasi\_X.yaml** — dibuat ulang di arena saat sesi familiarisasi.

```yaml
profile: arena_hari1
hsv:            # OpenCV: H 0–179, S dan V 0–255
  red:          # merah melingkar di ujung skala H, jadi dua rentang
    - {lo: [0, 120, 70],   hi: [10, 255, 255]}
    - {lo: [170, 120, 70], hi: [179, 255, 255]}
  green: [{lo: [40, 80, 60],  hi: [85, 255, 255]}]
  blue:  [{lo: [95, 120, 60], hi: [130, 255, 255]}]
shape:
  min_area_px: 400
```

Ekspresi seperti `rack_for(obj.color)` hanya boleh memakai fungsi yang terdaftar di pengelola misi; tidak ada eksekusi kode bebas dari YAML.

## State machine operasional, tombol, dan e-stop

Robot hanya bergerak di state RUNNING, dan satu-satunya jalan masuk ke RUNNING adalah satu tekanan tombol START saat READY. Semua transisi bisa dipicu dari tombol fisik, sehingga operator tidak perlu menyentuh laptop selama run.

&#91;embedded content: state machine operasional · 7 state\]

DONE, FAILED, dan STOPPED kembali ke READY lewat RESET; posisi awal disetel ulang ke titik `home` dari arena.yaml, jadi operator tidak perlu melokalisasi robot secara manual.

**Tanda status.** Warna LED dan pola buzzer di bawah adalah usulan; tim menetapkannya sekali lalu memakainya juga di dashboard. ID tombol tiap platform (di LanderPi: dua tombol RRC Lite) dicocokkan dengan topik `button` di robot sebelum dipakai.

| State | LED RGB | Buzzer | OLED | Tombol aktif |
| --- | --- | --- | --- | --- |
| BOOT | Biru | - | Komponen yang sedang dicek | - |
| FAULT | Merah | 3 bunyi pendek | Nama komponen yang gagal | - (perbaiki, nyalakan ulang) |
| READY | Hijau | 1 bunyi saat masuk | Nama dan versi misi | Tombol 1 klik = START; tombol 2 klik = ganti misi |
| RUNNING | Kuning | - | Langkah aktif dan waktu | Hanya e-stop |
| DONE | Putih | 2 bunyi | Waktu total | Tombol 1 tekan lama = RESET |
| FAILED | Merah | 1 bunyi panjang | Langkah gagal dan alasannya | Tombol 1 tekan lama = RESET |
| STOPPED | Merah | - | E-STOP | Tombol 1 tekan lama = RESET, setelah e-stop dilepas |

Tombol START eksternal yang besar dipasang paralel dengan tombol 1 platform (LanderPi: tombol RRC Lite; robot custom: input Nucleo), sehingga sinyalnya masuk lewat jalur yang sudah ada.

**Desain e-stop.** Aturan mewajibkan tombol STOP merah yang mudah diakses dan berfungsi. Pilihan akhirnya menunggu jawaban panitia; implementasi per robot ada di dokumen platform (LanderPi praktis memakai opsi A, robot custom dirancang untuk opsi B).

| Opsi | Cara kerja | Kelebihan | Kekurangan |
| --- | --- | --- | --- |
| A. Pemutus daya total | Memutus baterai; robot mati | Sederhana, pasti aman, tidak bergantung software | Pi reboot; waktu kembali ke READY harus diukur |
| B. Pemutus daya motor + sinyal | Kontak 1 memutus jalur motor; kontak 2 memberi sinyal ke software (STOPPED) | Pulih cepat tanpa reboot, lokalisasi tetap | Butuh rail motor terpisah: di LanderPi perlu modifikasi jalur daya (RRC Lite memakai satu input baterai untuk motor dan Pi), robot custom dirancang untuk ini |

Apa pun opsinya, watchdog di amr\_ops mengirim kecepatan nol bila perintah gerak berhenti datang, sebagai lapisan pengaman software tambahan. Di robot custom, firmware Nucleo punya watchdog sendiri. Setelah e-stop dilepas, robot tidak boleh bergerak sendiri: hanya RESET lalu START yang menjalankannya kembali.

**Jalur perintah gerak tunggal.** Semua perintah gerak wajib lewat twist\_mux. Di repo Hiwonder, beberapa node (`joystick_control` yang diluncurkan bringup bawaan, `teleop_key_control`, `app/*`, `example/*`, kalibrasi) menerbitkan langsung ke `/controller/cmd_vel` dan melewati twist\_mux. Karena itu bringup tim tidak meluncurkan `joystick_control` maupun `start_app` milik Hiwonder; adaptor memetakan masukan driver motor ke topik privat yang hanya diisi keluaran twist\_mux. Rincian di dokumen platform LanderPi.

## Skenario kegagalan dan pemulihan

Setiap skenario punya respons otomatis dari robot dan satu prosedur operator yang dilatih. Operator tidak pernah perlu menyentuh laptop saat run untuk menangani skenario mana pun.

| # | Skenario | Deteksi | Respons robot | Prosedur operator |
| --- | --- | --- | --- | --- |
| 1 | E-stop ditekan, run diulang dari awal | Daya terputus | Opsi A: boot ulang, auto-start, health check, READY. Opsi B: STOPPED, lalu RESET setelah e-stop dilepas | Minta izin retry ke juri, letakkan robot di home, tunggu LED hijau, tekan START |
| 2 | Lokalisasi meleset | Kovarians AMCL melewati ambang | Berhenti, putar di tempat, ulangi lokalisasi; gagal → FAILED | Panggil retry atau reset sesuai aturan |
| 3 | Robot macet atau Nav2 berputar-putar | Timeout skill, progress checker Nav2 | Retry sesuai misi, lalu `skip` atau batal | Tidak ada; robot memutuskan sendiri |
| 4 | Waktu hampir habis | Sisa waktu < `reserve_for_home_s` | Lewati tugas tersisa, `return_home` | Tidak ada |
| 5 | Objek gagal diambil atau jatuh | Kamera atau sensor gripper | Retry `pick` sesuai misi, lalu lanjut ke tugas berikutnya | Tidak ada |
| 6 | Obstacle tersenggol dan jatuh | Perubahan scan mendadak | Berhenti, rencanakan ulang jalur | Tidak menyentuh obstacle tanpa izin juri |
| 7 | Baterai lemah | Tegangan di bawah ambang (topik `battery`) | START ditolak, LED merah, kode buzzer | Ganti baterai sebelum run |
| 8 | Sensor tidak terdeteksi saat boot | Health check (LiDAR, kamera, kontroler motor: agent micro-ROS atau `/dev/rrc`) | Tetap di BOOT, LED merah, OLED menyebut komponen | Cabut-pasang konektor, reboot |
| 9 | Node crash saat run | `systemd` dan watchdog perintah gerak | Motor berhenti, node di-restart, misi FAILED | Panggil reset |
| 10 | Wi-Fi dashboard putus | Koneksi websocket hilang | Tidak berpengaruh pada run | Tidak ada; dashboard menyambung sendiri |
| 11 | Soal berubah di hari lomba (aturan 30%) | Pengumuman juri | Tidak berlaku | Edit file misi lewat dashboard, validasi, uji kering |
| 12 | Cahaya arena berbeda dari latihan | Deteksi visi tidak stabil saat uji | Tidak berlaku | Kalibrasi ulang profil HSV saat familiarisasi |
| 13 | Misi yang salah termuat | OLED dan dashboard menampilkan nama dan versi misi | Tidak berlaku | Cek nama misi sebelum memanggil ready |

Waktu dari e-stop sampai READY kembali menentukan berapa banyak retry yang realistis dalam 600 detik. Angka ini belum diketahui dan wajib diukur pada tahap uji.

## Fitur operator: mode Lomba vs mode Pengembangan

Fiturnya tidak disamakan. Satu aplikasi dashboard punya dua mode: **mode Pengembangan** memberi akses penuh untuk engineer, sedangkan **mode Lomba** hanya menampilkan apa yang dibutuhkan operator di bawah tekanan dan mengunci sisanya. Kodenya sama; mode Lomba menyembunyikan dan mengunci, bukan memakai program lain, sehingga tidak ada perilaku baru yang muncul di hari lomba.

Prinsip mode Lomba:

- **Sedikit keputusan.** Di bawah tekanan, setiap pilihan ekstra adalah peluang salah. Jalur normal: pilih misi, isi acakan, cek READY, letakkan robot, tekan START.
- **Checklist, bukan ingatan.** Kesiapan diperiksa robot sendiri dan ditampilkan sebagai daftar hijau/merah, seperti checklist pilot.
- **Kontrol fisik utama.** START dan e-stop ada di robot; dashboard tidak punya tombol yang menggerakkan robot.
- **Status terbaca dari jauh.** Warna dashboard sama dengan LED robot; huruf besar; nama dan versi misi selalu tampil.
- **Edit terkunci saat RUNNING.**

| Fitur | Mode Lomba | Mode Pengembangan | Alasan pembedaan |
| --- | --- | --- | --- |
| Checklist kesiapan (sensor, baterai, lokalisasi, misi) dan indikator READY | Ya, layar utama | Ya | Kebutuhan utama sebelum setiap run |
| Pilih misi dan isi acakan (urutan target, warna rak) | Ya, lewat form dari skema | Ya, plus edit YAML mentah | Form mencegah salah ketik saat terburu-buru |
| Monitor run: langkah aktif, waktu berjalan, hasil per langkah | Ya, hanya baca | Ya | Operator tahu apa yang terjadi tanpa menyentuh apa pun |
| Riwayat run dan alasan gagal | Ya | Ya, plus log lengkap | Bahan keputusan retry dan perbaikan antar-run |
| Mode demo visi (feed + label identitas) | Ya, untuk Kriteria F | Ya | Dinilai langsung oleh juri |
| Kalibrasi HSV dengan preview kamera | Ya, saat familiarisasi saja | Ya | Cahaya arena berbeda dari latihan |
| Pendaftaran objek baru (foto per objek, label, uji langsung) | Ya, saat persiapan saja | Ya, plus ekspor dan impor set contoh | Objek identifikasi bisa baru diketahui di arena |
| Pemetaan dan penandaan titik bernama | Ya, saat sesi persiapan | Ya | Peta dibuat ulang di arena |
| Teleop (joystick virtual) | Tidak | Ya | Bisa memicu penalti dan kesalahan saat lomba |
| Uji satu skill (misalnya hanya `wall_follow`) | Tidak | Ya | Alat debugging, bukan alat lomba |
| Ubah parameter Nav2 dan PID secara langsung | Tidak | Ya | Perubahan tak teruji di hari lomba berisiko |
| Inspeksi topik, rekam dan putar `ros2 bag` | Rekam otomatis saja | Ya, penuh | Rekaman tetap diambil untuk analisis |

Ketentuan kapan laptop boleh disentuh (misalnya saat mengisi acakan dari juri) ditanyakan saat technical meeting. Sebagai cadangan, pemilihan misi juga bisa dilakukan dari tombol robot dan OLED.

## Pengembangan dengan asisten AI

Halusinasi AI pada kode robot hampir selalu berupa tebakan: nama topik, frame, tipe pesan, nama parameter, atau API dari versi ROS yang salah. Penangkalnya adalah membuat fakta tersedia sebagai file yang dibaca AI, dan membuat kesalahan langsung ketahuan lewat tes otomatis. Instruksi di CLAUDE.md hanyalah konteks yang tidak dipaksakan; yang benar-benar memaksa adalah hook dan tes ([dokumentasi memori Claude Code](https://code.claude.com/docs/en/memory)).

**Tujuh aturan anti-halusinasi**

1. **Satu sumber kebenaran.** Dokumen ini disimpan di repo sebagai `docs/architecture.md`. Nama topik, service, dan frame hanya ada di satu modul `amr_core/interfaces.py`; kode lain mengimpor dari sana, tidak menulis string sendiri.
2. **Fakta dari robot, bukan ingatan.** Hasil `ros2 topic list -t`, `ros2 interface show`, dan `ros2 param dump` dari robot asli disimpan di `docs/ros_snapshot/`. AI diwajibkan membaca snapshot sebelum memakai topik atau pesan apa pun.
3. **Kunci versi.** Hanya API ROS2 Humble dan rclpy. Setiap paket eksternal baru harus dicatat di tabel tech stack dulu.
4. **Vendor tidak disentuh.** Kode Hiwonder ditempatkan di `src/vendor/` dan hanya dibaca. Hook `PreToolUse` menolak edit ke folder itu; perubahan perilaku dilakukan lewat parameter, launch, atau paket tim sendiri.
5. **Tes sebagai pagar.** Parser misi, validator YAML, dan logika skill diuji dengan pytest memakai sensor tiruan. Hook `PostToolUse` menjalankan linter (ruff) dan tes setiap kali AI mengubah file Python.
6. **Perubahan kecil dan tercatat.** Satu tugas, satu commit. Keputusan desain baru ditulis sebagai catatan keputusan (ADR) singkat di `docs/adr/` sebelum kodenya.
7. **Uji di robot menutup setiap fitur.** Fitur dianggap selesai hanya setelah laporan uji lapangan ditulis (apa yang diubah, hasil, file rekaman).

**Struktur repo**

```text
amr-lks/
├── CLAUDE.md                 # < 200 baris, mengimpor docs/architecture.md
├── .claude/
│   ├── settings.json         # hooks: lint + tes, blokir edit vendor
│   ├── rules/                # aturan per jenis file (python, yaml, launch)
│   └── skills/               # skill proyek (tabel di bawah)
├── docker/                   # Dockerfile + compose tim, sama untuk semua robot
├── firmware/
│   └── nucleo/               # firmware micro-ROS robot custom (CLAUDE.md sendiri)
├── docs/
│   ├── architecture.md       # dokumen inti ini
│   ├── platforms/            # landerpi.md, custom.md (dokumen platform)
│   ├── adr/                  # catatan keputusan
│   ├── ros_snapshot/         # fakta dari robot asli, satu folder per platform
│   └── field_tests/          # laporan uji lapangan
├── config/
│   ├── arena.yaml, missions/, calibration/
│   └── platforms/            # landerpi/, custom/, mock/
└── src/
    ├── vendor/               # paket Hiwonder, hanya dibaca
    ├── amr_core/             # interfaces.py (kontrak), skema, hasil skill
    ├── amr_platform_landerpi/  # adaptor; CLAUDE.md mengimpor docs/platforms/landerpi.md
    ├── amr_platform_custom/    # adaptor; CLAUDE.md mengimpor docs/platforms/custom.md
    ├── amr_platform_mock/      # platform tiruan untuk tes
    ├── amr_skills/           # satu modul per skill
    ├── amr_mission/          # pengelola misi + state machine
    ├── amr_vision/           # deteksi warna dan bentuk
    ├── amr_ops/              # tombol, indikator, health check, watchdog (lewat /amr/hw/*)
    ├── amr_dashboard/        # NiceGUI, mode Lomba dan Pengembangan
    └── amr_bringup/          # robot.launch.py platform:=landerpi|custom|mock
```

CLAUDE.md di folder adaptor dan firmware hanya dimuat saat asisten AI bekerja di folder itu, sehingga nama topik satu platform tidak bocor ke kode platform lain.

**Skill Claude Code yang direkomendasikan.** Skill proyek disimpan di `.claude/skills/<nama>/SKILL.md`, ikut di-commit sehingga seluruh tim dan AI memakai prosedur yang sama ([dokumentasi skills](https://code.claude.com/docs/en/skills)). Setiap skill mengubah kebiasaan engineer menjadi langkah yang wajib diikuti AI.

| Skill | Kapan dipakai | Isi prosedur | Kebiasaan engineer yang dikodekan |
| --- | --- | --- | --- |
| `ros2-conventions` | Setiap kali menulis node ROS2 | Pola node rclpy, deklarasi parameter, QoS sensor vs perintah, satuan SI dan frame | Konvensi satuan REP-103 dan frame REP-105 (`map` → `odom` → `base_footprint`) |
| `add-robot-skill` | Menambah atau mengubah skill robot | Tambah ke katalog dokumen → antarmuka → implementasi dengan timeout dan abort → tes dengan sensor tiruan → contoh misi | Kontrak dulu, kode belakangan |
| `mission-yaml` | Membuat misi baru atau menerjemahkan aturan lomba | Skema misi, fungsi yang diizinkan, wajib menjalankan validator | Misi sebagai data |
| `verify-on-robot` | Sebelum memakai topik, pesan, atau parameter baru | Ambil snapshot dari robot lewat SSH, bandingkan dengan `interfaces.py` | Verifikasi di perangkat nyata |
| `nav2-tuning` | Mengubah perilaku navigasi | Ubah satu parameter per uji, catat sebelum/sesudah, mengacu [Nav2 Tuning Guide](https://docs.nav2.org/tuning/index.html) | Tuning terkendali dan tercatat |
| `field-test-report` | Setelah uji di arena | Template laporan: perubahan, skenario, hasil, file `ros2 bag` | Setiap uji meninggalkan bukti |
| `dashboard-page` | Menambah halaman dashboard | Konvensi NiceGUI, kunci mode Lomba, tidak ada kontrol gerak di mode Lomba | Antarmuka operator yang aman |

Skill-skill ini ditulis bertahap setelah repo dibuat, bukan sekaligus. Skill pertama yang dibuat adalah `ros2-conventions` dan `verify-on-robot`, karena keduanya langsung menekan tebakan nama topik dan frame.

## Rencana uji dan checklist hari lomba

Pengukuran pertama yang menentukan desain adalah tinggi LiDAR, beban CPU, dan waktu boot sampai READY. Ketiganya dilakukan sebelum fitur misi ditulis.

| Uji | Yang diukur | Kriteria lulus |
| --- | --- | --- |
| Tinggi bidang pindai LiDAR | Tinggi dari lantai | Di bawah 200 mm, agar obstacle terlihat |
| Beban CPU Pi 5 | CPU dan suhu saat SLAM/Nav2 + visi + dashboard berjalan | Ditetapkan setelah pengukuran pertama |
| Waktu e-stop sampai READY | Detik dari daya kembali sampai LED hijau | Ditetapkan setelah pengukuran pertama; dipakai untuk menghitung jumlah retry realistis |
| Kalibrasi odometri | Galat jarak lurus dan putaran (paket `calibration` repo) | Ditetapkan tim, diulang setelah ganti roda atau beban |
| Akurasi heading | Galat putar 90° dan 180° | Dalam toleransi juri (diumumkan di hari lomba) |
| Visi 9 objek | Identitas benar per objek, di cahaya latihan dan cahaya terang | 9 dari 9 di kedua kondisi |
| Visi objek baru | Akurasi setelah pendaftaran, memakai set objek tersembunyi yang tidak pernah dipakai saat pengembangan; waktu per gambar dan beban CPU | M9 di PRD: pendaftaran 5 objek ≤ 15 menit, lalu ≥ 4 dari 5 benar |
| Run penuh tanpa internet | Misi E dan G dari boot, Wi-Fi internet dimatikan | Selesai ≤ 600 s, tanpa menyentuh laptop |
| Pemulihan | Skenario 1–13 di tabel kegagalan | Setiap respons robot sesuai tabel |
| Uji penerimaan micro-ROS (robot custom) | Lima uji di dokumen platform robot custom | Lulus sebelum tanggal evaluasi; gagal → protokol serial custom |
| Tinjauan kelistrikan dan keselamatan | E-stop, sekring, rating kontak, lonjakan saat rail motor diputus; ditinjau orang yang paham kelistrikan | Disetujui peninjau sebelum uji dengan motor |

**Checklist sebelum run** (dicetak dan ditempel di kotak alat)

- [ ] Baterai terpasang penuh; baterai cadangan siap
- [ ] E-stop dilepas dan diuji sekali
- [ ] Dashboard: semua item kesiapan hijau
- [ ] Nama dan versi misi di OLED sesuai soal
- [ ] Acakan dari juri sudah diisi dan divalidasi
- [ ] Robot di zona home, menghadap arah yang ditetapkan
- [ ] Panggil "ready" ke juri, tunggu aba-aba
- [ ] Tekan START satu kali, lalu tangan menjauh dari robot dan laptop

**Checklist setelah run**

- [ ] Panggil "finish", "retry", atau "reset" sesuai prosedur
- [ ] Catat hasil di log kompetisi
- [ ] Lihat alasan gagal di riwayat run sebelum memutuskan perubahan
- [ ] Restorasi area kerja

## Isu terbuka

Empat pertanyaan pertama ke panitia menentukan apakah LanderPi bisa dipakai sebagai robot lomba atau hanya robot latihan. Software dalam dokumen ini tetap berlaku untuk kedua kemungkinan.

**Ditanyakan ke panitia**

- [ ] Apakah servo bus dihitung dalam batas "maksimal 3 standard servo"? (lengan LanderPi memakai 6)
- [ ] Apakah kamera depth (Aurora930 Pro di LanderPi dan kamera depth robot custom) dihitung sebagai "webcam"?
- [ ] Apakah mikrokontroler (STM32) boleh dipakai sebagai pengendali motor di samping Raspberry Pi? Pada lomba sebelumnya juri mengizinkan STM32 Nucleo sebagai slave controller, jadi risikonya rendah; tetap konfirmasi di technical meeting dan tulis di laporan teknis bahwa Raspberry Pi adalah main controller.
- [ ] Apakah robot berbasis kit komersial diizinkan, dan seberapa besar modifikasi yang diharapkan untuk orisinalitas?
- [ ] Kapan operator boleh menyentuh laptop (misalnya mengisi acakan sebelum run)?
- [ ] Apakah e-stop wajib memutus daya, atau cukup menghentikan motor?
- [ ] Apakah "baterai cadangan 2 buah @12V" wajib 12 V, atau mengikuti tegangan robot?

**Diputuskan atau diukur tim**

- [ ] Platform utama dan tanggal gerbang keputusannya: LanderPi dimodifikasi atau robot custom; kontroler motor robot custom sudah diputuskan: STM32 Nucleo + micro-ROS
- [ ] Desain OMS (gripper/lifter) dengan L-Channel sesuai kisi-kisi nasional
- [ ] Ambang tegangan aman untuk START per platform; satuan topik `battery` LanderPi diukur di dokumen platform
- [ ] Hasil uji beban CPU sebagai syarat final NiceGUI vs roslibjs

**Sumber**

- [Hiwonder/LanderPi (GitHub)](https://github.com/Hiwonder/LanderPi)
- [LanderPi product page](https://www.hiwonder.com/products/landerpi)
- Kisi-kisi LKS Nasional 2026 Robot Bergerak Otonom (berkas dari tim)
- Deskripsi Teknis LKS AMR Provinsi Jawa Tengah 2026 (berkas dari tim)
- [Nav2 Tuning Guide](https://docs.nav2.org/tuning/index.html)
- [Claude Code: skills](https://code.claude.com/docs/en/skills) · [memori dan CLAUDE.md](https://code.claude.com/docs/en/memory) · [hooks](https://code.claude.com/docs/en/hooks-guide)
- [REP-103: satuan dan konvensi koordinat](https://www.ros.org/reps/rep-0103.html) · [REP-105: frame platform bergerak](https://www.ros.org/reps/rep-0105.html)
