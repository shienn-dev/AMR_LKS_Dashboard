# PRD Software Robot AMR LKS

Oct 10, 2026 · @yokos

## Tujuan dan cakupan

PRD ini menetapkan **apa** yang harus dilakukan software robot AMR untuk LKS 2026 dan **kapan** sebuah kebutuhan dianggap terpenuhi. **Bagaimana** membangunnya ada di dokumen arsitektur inti dan dua dokumen platform. Jika keduanya bertentangan soal apa yang dibutuhkan, PRD yang berlaku; soal cara membangunnya, dokumen arsitektur yang berlaku.

**Tujuan**

- Meraih nilai sebanyak mungkin di kriteria yang ditentukan software: D, E, F, dan G (73 dari 100 poin), serta B lewat operasi tanpa menyentuh laptop.
- Satu run lengkap berjalan dari boot sampai selesai tanpa internet dan tanpa laptop.
- Aturan berubah (hari lomba atau tahun 2027) cukup ditangani dengan file misi baru, bukan kode baru.
- Platform berganti (LanderPi atau robot custom) cukup ditangani dengan adaptor, tanpa mengubah misi, skill, atau dashboard.

**Termasuk cakupan:** pengelola misi dan state machine, skill gerak dan navigasi, visi, kendali OMS dari sisi software, keselamatan dan operasional (tombol, LED, watchdog, health check), dashboard operator, adaptor platform, perilaku firmware Nucleo yang terlihat dari luar, serta alat bantu software untuk membangun dan menguji robot (bring-up), terutama robot custom.

**Di luar cakupan (non-goals 2026):**

- Perakitan mekanik dan kelistrikan; dikelola lewat checklist hardware terpisah dan hanya muncul di sini sebagai batasan.
- Simulasi Gazebo; tes otomatis cukup memakai platform mock.
- Misi dalam Behavior Tree XML.
- Lengan 6-DOF bawaan LanderPi sebagai alat lomba.
- Fitur yang butuh internet atau layanan AI online.
- Melatih model deteksi besar (misalnya YOLO) dari nol. Model terlatih kecil yang dibawa offline untuk mengenali objek baru justru termasuk cakupan (VIS-09, VIS-10).
- Tombol penggerak robot di dashboard mode Lomba.

**Konvensi.** Setiap kebutuhan punya ID `<MODUL>-<nomor>` yang tidak pernah dipakai ulang; kebutuhan yang dibatalkan diberi status batal, bukan dihapus. ID ini dirujuk di commit, nama tes, dan prompt untuk asisten AI. Prioritas: **P0** wajib sebelum lomba (tanpanya nilai besar hilang atau robot tidak aman), **P1** penting dan dikerjakan setelah semua P0 lulus, **P2** dikerjakan bila waktu cukup. Setiap kriteria terima harus bisa diuji. Kolom Verifikasi: T = tes otomatis di mock, R = uji di robot mengikuti protokol uji, I = inspeksi (pemeriksaan kode, konfigurasi, atau tampilan). Kolom Pemilik diisi nama siswa penanggung jawab. Kolom Status bernilai Belum, Sedang, atau Lulus; Lulus hanya ditulis bila ada laporan uji atau tes yang lulus.

## Pengguna dan konteks pemakaian

| Pengguna | Kapan | Kebutuhan utama | Batasan konteks |
| --- | --- | --- | --- |
| Operator lomba (satu siswa) | Hari lomba, sebelum dan selama run | Tahu robot siap, memuat misi dan acakan yang benar, memulai run, memulihkan setelah gagal | Di bawah tekanan waktu; penalti bila menyentuh robot atau laptop tanpa izin; tanpa internet dan tanpa AI |
| Tim pengembang (dua siswa) | Masa latihan sampai familiarisasi | Menguji skill satu per satu, tuning, kalibrasi, membaca log dan rekaman | Waktu terbatas; dibantu asisten AI yang bisa menebak nama topik bila tidak diberi fakta |
| Pembimbing | Masa latihan | Meninjau kemajuan per kebutuhan, memutuskan prioritas | Tidak selalu hadir saat uji |
| Juri | Hari lomba | Melihat start dengan satu tombol, identitas objek di feed, e-stop berfungsi, robot bisa dijelaskan | Menilai dari luar; tidak membaca kode |

Konteks yang membentuk banyak kebutuhan di bawah: sebagian besar butir penilaian bernilai 1 atau 0, run E dan G dibatasi 600 detik, dan hingga 30% soal bisa berubah di hari lomba. Karena itu keandalan setiap langkah dan kecepatan mengganti misi lebih penting daripada kecepatan gerak.

## Ukuran keberhasilan

Angka target di bawah adalah **usulan awal** untuk disepakati tim dan pembimbing; yang bertanda "setelah ukur" baru bisa ditetapkan setelah pengukuran pertama di robot. Ukuran diambil dari uji di arena latihan dengan susunan dan acakan yang berbeda tiap run.

| ID | Ukuran | Target usulan | Kriteria terkait |
| --- | --- | --- | --- |
| M1 | Run G lengkap (ambil, letakkan di slot benar, kembali ke home) berhasil | ≥ 18 dari 20 run terakhir | G (40) |
| M2 | Setiap gerak dasar Modul D lulus | ≥ 19 dari 20 percobaan terakhir per gerak | D (10) |
| M3 | Empat target acak + obstacle juri selesai dalam batas waktu | ≥ 18 dari 20 run terakhir, setiap run ≤ 600 s | E (13) |
| M4 | Identitas 9 objek (3 warna × 3 bentuk) benar | 9 dari 9, di cahaya latihan dan cahaya terang, pada rentang jarak dan sudut di tabel lingkungan operasi | F (10) |
| M5 | Sentuhan laptop selama run | Nol | B (7) |
| M6 | Waktu dari daya ON sampai READY | Setelah ukur; dipakai menghitung jumlah retry yang realistis | B, E, G |
| M7 | Waktu dari pengumuman perubahan soal sampai uji kering misi baru lulus | ≤ 15 menit | Aturan 30% |
| M8 | File misi yang sama lulus di dua platform tanpa ubah kode misi, skill, atau dashboard | Lulus di mock dan robot utama setiap rilis; di robot kedua pada uji asap | Kesiapan platform |
| M9 | Objek yang belum pernah dilihat dikenali setelah pendaftaran di tempat | Pendaftaran 5 objek ≤ 15 menit, lalu ≥ 4 dari 5 dikenali benar; objek diambil dari set uji tersembunyi | F, tantangan ala WSC |

## Lingkungan operasi dan protokol uji

Kriteria terima hanya bisa dibandingkan antar-sesi bila kondisi ujinya sama. Nilai bertanda "isi" diambil dari gambar teknis kisi-kisi atau diukur tim, lalu dicantumkan di sini sebelum R2.

| Aspek | Nilai | Sumber |
| --- | --- | --- |
| Ukuran arena dan dinding | Isi | Gambar teknis kisi-kisi |
| Permukaan lantai | Isi | Technical meeting atau foto arena |
| Obstacle | Tinggi 200 mm; ukuran alas isi | Aturan |
| Objek visi | 3 warna × 3 bentuk | Kisi-kisi |
| Objek ambil dan letakkan | Kubus 65 mm; berat isi | Kisi-kisi |
| Stand dan rak | Tinggi stand 100 mm; tinggi, lebar, dan kedalaman slot isi | Gambar teknis rak |
| Zona home | Ukuran dan arah hadap isi | Gambar teknis |
| Pencahayaan | Dua kondisi: cahaya ruang latihan dan cahaya terang dengan lampu tambahan | Keputusan tim |
| Variasi posisi kubus di stand | Geser dan putar maksimal: isi | Technical meeting atau perkiraan tim |
| Jarak dan sudut objek saat uji visi | Rentang jarak dan sudut: isi | Technical meeting atau perkiraan tim |
| Objek pengecoh | Set uji milik tim: warna mirip (misalnya oranye, merah muda) dan bentuk di luar 3 jenis | Keputusan tim |
| Obstacle sulit | Set uji milik tim: benda rendah di bawah bidang pindai, bahan hitam doff, dan bahan mengilap | Keputusan tim |
| Set objek uji tersembunyi | Minimal 15 benda sehari-hari dan buah yang tidak pernah dipakai saat pengembangan; disimpan pembimbing dan hanya dibuka saat uji M9 dan VIS-10 | Keputusan tim |

**Protokol uji**

1. Satu percobaan dimulai dari tekan START dan berakhir di DONE, FAILED, atau batas waktu. Sentuhan tangan ke robot selama percobaan dihitung gagal.
2. Posisi objek, urutan target, dan posisi obstacle diacak setiap percobaan; susunannya dicatat.
3. Sebagian percobaan dilakukan dengan baterai mendekati ambang bawah, karena perilaku motor berubah saat tegangan turun.
4. Keandalan dihitung dari jendela 20 percobaan terakhir pada versi software yang sama. Perubahan kode atau konfigurasi pada modul terkait mengulang hitungan dari nol.
5. Setiap sesi uji menghasilkan laporan uji lapangan: versi, susunan, hasil per percobaan, alasan gagal, dan file rekaman.

Alasan memakai 20 percobaan \[pasti, statistik binomial\]: dari 8 sukses dalam 10 percobaan, batas bawah selang kepercayaan 95% untuk keandalan sebenarnya hanya sekitar 44%; dari 18 dalam 20 sekitar 68%, dan dari 19 dalam 20 sekitar 75%.

## Anggaran teknis

Angka di bagian ini adalah **usulan awal** \[menebak\] untuk disepakati tim, lalu dikoreksi dengan hasil ukur.

### Anggaran toleransi meletakkan

Kubus masuk slot hanya bila jumlah semua galat lebih kecil dari celah, yaitu lebar slot dikurangi 65 mm. Lebar slot belum diketahui, sehingga alokasi ditulis sebagai bagian dari celah.

| Sumber galat | Bagian dari celah (usulan) | Diverifikasi lewat |
| --- | --- | --- |
| Penyejajaran ke garis referensi stand atau rak | 40% | NAV-07 |
| Posisi dan kemiringan kubus di gripper | 30% | OMS-02 |
| Cadangan (selip, getaran, galat ukur) | 30% | - |
| Ketinggian lifter terhadap dasar slot | Dihitung terpisah dari celah vertikal slot | OMS-02 |

Galat lokalisasi Nav2 tidak masuk anggaran langsung karena dikoreksi penyejajaran, tetapi pose akhir Nav2 harus berada di dalam jangkauan penyejajaran (NAV-08). Galat sudut ikut menggeser posisi kubus: galat 2° pada jarak 150 mm dari pusat putar sudah menggeser sekitar 5 mm.

### Toleransi internal gerak dasar

Toleransi juri baru diumumkan di hari lomba, sehingga latihan memakai toleransi internal yang lebih ketat.

| Gerak | Toleransi internal (usulan) |
| --- | --- |
| Putar 90° dan 180° | ±3° |
| Berhenti di depan dinding | ±2 cm dari jarak target |
| Wall following | Jarak ke dinding ±3 cm sepanjang lintasan |
| Penempatan awal robot di zona home | Robot boleh meleset ±5 cm dan ±10° dari pose home, dan lokalisasi tetap konvergen (MIS-10) |

### Anggaran waktu run (600 s)

| Fase | Anggaran | Cara mengisi |
| --- | --- | --- |
| Keluar dari zona home | Isi | Ukur |
| Per target E (4 kali) | Isi | Ukur rata-rata dan terburuk |
| Per objek G: menuju, ambil, menuju rak, letakkan | Isi | Ukur rata-rata dan terburuk |
| Pulang ke home | Isi; menjadi nilai cadangan pulang di file misi | Ukur dari titik terjauh |
| Cadangan untuk retry | Minimal 120 s (usulan) | Ditetapkan tim |

Jumlah anggaran tanpa cadangan retry tidak boleh melebihi 480 s.

### Anggaran baterai

| Ukuran | Nilai | Cara mengisi |
| --- | --- | --- |
| Run penuh per baterai sebelum tegangan turun ke ambang START | Isi | Ukur |
| Waktu ganti baterai sampai READY | Isi | Ukur (bagian dari M6) |
| Jumlah baterai yang dibawa | Cukup untuk sesi familiarisasi, semua run satu hari, dan satu cadangan | Dihitung dari dua baris di atas |

## Kebutuhan fungsional

Kolom Sumber menunjuk kriteria penilaian (A–G, skema Jawa Tengah 2026), aturan lomba, atau keputusan tim. Rincian cara memenuhinya ada di bagian dokumen arsitektur dengan nama yang sama.

### MIS — Misi dan state machine

| ID | Kebutuhan | Sumber | Prio | Kriteria terima | Verifikasi | Pemilik | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| MIS-01 | Robot hanya bergerak di state RUNNING; satu-satunya jalan masuk RUNNING adalah satu tekanan START saat READY | E, G, keselamatan | P0 | Perintah gerak di state lain menghasilkan kecepatan nol; satu tekan START memulai run | T, R | - | Belum |
| MIS-02 | Misi dimuat dari file YAML dan divalidasi skema; file tidak valid membuat robot tidak masuk READY dan alasannya ditampilkan | Fleksibilitas aturan | P0 | File rusak, kunci hilang, dan nilai di luar batas ditolak dengan pesan yang menyebut barisnya | T | - | Belum |
| MIS-03 | Urutan empat target E diisi dari acakan juri tanpa mengubah kode | E | P0 | Tiga acakan berbeda berjalan benar di mock | T | - | Belum |
| MIS-04 | Pengelola misi memantau sisa waktu dan menjalankan return\_home bila sisa waktu kurang dari cadangan pulang di file misi | G (home 10%), E | P0 | Dengan jam dipercepat, robot pulang sebelum batas 600 s | T | - | Belum |
| MIS-05 | Batas waktu dan jumlah retry tiap langkah diambil dari file misi; setelah retry habis, langkah dilewati atau misi FAILED sesuai file misi | D, E, G | P0 | Ketiga hasil (sukses, lewati, FAILED) teruji | T | - | Belum |
| MIS-06 | Mode G2: robot membaca kondisi aktual dengan kamera sebelum meletakkan, lalu menentukan rak dan slot dari aturan di file misi yang hanya memakai fungsi terdaftar | G2 (24) | P0 | Setiap kombinasi warna teruji dengan deteksi tiruan; ekspresi tak terdaftar ditolak validator | T | - | Belum |
| MIS-07 | RESET mengembalikan robot ke READY dan menyetel pose awal ke titik start misi (default: home dari arena.yaml) | B, G | P0 | Setelah RESET, lokalisasi benar tanpa penandaan pose manual | R | - | Belum |
| MIS-08 | Setiap run menghasilkan log misi (langkah, hasil, alasan, waktu) dan rekaman ros2 bag otomatis | Pemulihan, laporan teknis | P1 | File log dan bag ada untuk setiap run, termasuk yang FAILED | I | - | Belum |
| MIS-09 | Inventaris magazin: misi mencatat isi tiap kantong; parameter capacity bernilai 1 berarti mode tanpa magazin | G (bila magazin dipakai) | P2 | Misi yang sama lulus dengan capacity 1 dan 3 | T | - | Belum |
| MIS-10 | Lokalisasi konvergen bila robot diletakkan di dalam toleransi penempatan awal | B, E, G | P0 | 20 penempatan acak di dalam toleransi, semuanya konvergen sebelum robot bergerak | R | - | Belum |
| MIS-11 | Titik start dan arah hadap awal dipilih di file misi dari titik bernama, sehingga robot bisa mulai dari tempat lain atau di arena yang dicerminkan | Aturan 30% | P1 | Misi yang sama berjalan dari dua titik start berbeda | T, R | - | Belum |
| MIS-12 | Bila kondisi aktual G2 tidak sesuai harapan (slot terisi, rak berbeda, objek berubah), perilaku diambil dari file misi: pilih slot lain yang sah, lewati, atau pulang | G2 (24) | P0 | Setiap kasus diuji dengan deteksi tiruan di mock dan sekali di robot | T, R | - | Belum |

### NAV — Gerak dasar dan navigasi

| ID | Kebutuhan | Sumber | Prio | Kriteria terima | Verifikasi | Pemilik | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| NAV-01 | Putar 90° ke kanan dan 180° ke kiri berdasarkan IMU | D | P0 | M2; galat di dalam toleransi internal | R | - | Belum |
| NAV-02 | Wall following sisi kanan dan kiri pada jarak dari file misi | D | P0 | M2; jarak ke dinding di dalam toleransi internal, tanpa menyentuh dinding | R | - | Belum |
| NAV-03 | Berhenti di depan dinding pada jarak target | D | P0 | M2; jarak berhenti di dalam toleransi internal, tanpa menyentuh dinding | R | - | Belum |
| NAV-04 | Menuju titik bernama dan menghindari obstacle setinggi 200 mm yang posisinya tidak diketahui sebelumnya | E, G | P0 | M3 | R | - | Belum |
| NAV-05 | Peta arena dan titik bernama bisa dibuat ulang di arena saat sesi persiapan | E, G | P0 | Peta dan arena.yaml baru selesai dalam satu sesi familiarisasi | R | - | Belum |
| NAV-06 | Lokalisasi yang tidak yakin terdeteksi dan dicoba dipulihkan; gagal berarti FAILED | E, G | P1 | Robot yang dipindah diam-diam di mock terdeteksi tidak yakin | T | - | Belum |
| NAV-07 | Menyejajarkan diri ke garis referensi stand atau rak sebelum mengambil atau meletakkan | D, G | P0 | Galat sejajar di dalam porsi penyejajaran pada anggaran toleransi meletakkan | R | - | Belum |
| NAV-08 | Pose akhir Nav2 di titik ambil dan letakkan berada di dalam jangkauan penyejajaran NAV-07 | G | P0 | 20 kedatangan berturut-turut, semuanya bisa disejajarkan tanpa retry | R | - | Belum |
| NAV-09 | Skill cadangan drive\_distance: maju, mundur, atau geser sejauh jarak tertentu dengan odometri | Aturan 30% | P0 | Galat ≤ 2 cm per 1 m (usulan), 20 percobaan | R | - | Belum |
| NAV-10 | Putar ke sudut relatif sembarang dan ke arah absolut terhadap peta | Aturan 30% | P1 | 20 sudut acak, semuanya di dalam toleransi internal | R | - | Belum |
| NAV-11 | Skill cadangan stop\_at\_line dan follow\_line dengan sensor garis | Aturan 30% (4 sensor garis diizinkan) | P1 | Lulus di garis uji; bergantung pada pemasangan sensor garis di kedua platform | R | - | Belum |
| NAV-12 | Skill cadangan stop\_at\_distance berbasis ultrasonik ke benda di depan | Aturan 30% | P1 | Jarak berhenti di dalam toleransi internal | R | - | Belum |
| NAV-13 | Jarak minimum robot ke obstacle saat navigasi ditetapkan di konfigurasi, sehingga obstacle tidak tersenggol, termasuk bila target dekat obstacle | E, G | P0 | 20 run tanpa senggolan; target di dekat obstacle dilewati bila tidak bisa dicapai dengan aman | R | - | Belum |

**Skill cadangan.** NAV-09 sampai NAV-12 disiapkan walaupun belum diminta soal, karena aturan 30% bisa mengganti jenis tugas, bukan hanya angkanya, dan menulis skill baru di hari lomba tanpa asisten AI tidak realistis. Bila juri meminta perilaku di luar semua skill yang tersedia, misi memakai hasil lewati (MIS-05) untuk mengamankan nilai langkah lain. Strategi lewati ini dilatih sebagai keputusan, bukan dianggap kegagalan.

### VIS — Visi

| ID | Kebutuhan | Sumber | Prio | Kriteria terima | Verifikasi | Pemilik | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| VIS-01 | Mengenali 3 warna × 3 bentuk objek | F, G | P0 | M4 | R | - | Belum |
| VIS-02 | Feed kamera dengan label identitas objek tampil di dashboard (mode demo) | F | P0 | Juri bisa membaca label dari layar laptop | I | - | Belum |
| VIS-03 | Profil HSV dikalibrasi ulang dengan preview kamera dan disimpan per lokasi | F, G | P0 | Kalibrasi satu lokasi selesai ≤ 10 menit (usulan) | R | - | Belum |
| VIS-04 | Sumber gambar dipilih lewat parameter, sehingga kamera depth atau webcam USB bisa dipakai tanpa ubah kode | Keputusan panitia soal kamera | P0 | Kedua sumber lulus VIS-01 | R | - | Belum |
| VIS-05 | Deteksi dilaporkan hanya bila stabil N frame; bila tidak, hasilnya "tidak yakin", bukan tebakan | G | P1 | Pada rekaman, objek yang setengah terlihat tidak dilaporkan sebagai identitas pasti | T | - | Belum |
| VIS-06 | Deteksi sambil robot bergerak | G (efisiensi waktu) | P2 | Diputuskan setelah uji kecepatan kamera | R | - | Belum |
| VIS-07 | Di tugas ambil dan letakkan, objek di luar daftar misi dan objek pengecoh (misalnya oranye di dekat merah) dilaporkan "tidak dikenal" agar tidak diambil. Di tugas identifikasi, robot tetap memberi jawaban terbaik beserta tingkat keyakinannya | F, G | P1 | Set objek pengecoh tidak diambil di tugas G; di tugas identifikasi selalu ada jawaban | R | - | Belum |
| VIS-08 | Bila lebih dari satu objek terlihat, objek yang dipilih ditentukan aturan di file misi (misalnya paling dekat atau paling tengah) | G | P1 | Dua objek dalam satu frame: yang dipilih sesuai aturan | T | - | Belum |
| VIS-09 | Pendaftaran objek baru di tempat: operator memotret tiap objek dari beberapa sudut lewat dashboard dan memberi label; software menyusun pengenal tanpa internet dan tanpa pelatihan berat, lalu langsung bisa dipakai | Tantangan juri ala WSC (objek yang belum pernah dilihat) | P0 | M9 | R | - | Belum |
| VIS-10 | Cadangan bila tidak ada contoh objek: model terlatih yang dibawa offline mengenali objek dari daftar nama yang diumumkan juri | Tantangan juri ala WSC | P1 | ≥ 3 dari 5 objek dari set tersembunyi dikenali hanya dari nama (usulan); waktu per gambar diukur di Pi 5 | R | - | Belum |
| VIS-11 | Feed dan dashboard menampilkan identitas beserta tingkat keyakinan, dan hasil identifikasi tercatat di log | F | P0 | Setiap identifikasi di uji M9 tampil dan tercatat | I | - | Belum |

### OMS — Manipulasi objek

| ID | Kebutuhan | Sumber | Prio | Kriteria terima | Verifikasi | Pemilik | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| OMS-01 | Mengambil kubus dari ketinggian yang ditentukan file misi | D, G (ambil 25%) | P0 | ≥ 19 dari 20 percobaan terakhir | R | - | Belum |
| OMS-02 | Meletakkan kubus di slot rak yang ditentukan misi | D, G (letakkan 30%) | P0 | ≥ 19 dari 20 percobaan terakhir; kubus masuk slot tanpa disentuh; galat gripper dan lifter di dalam anggaran toleransi | R | - | Belum |
| OMS-03 | Antarmuka oms/lift, oms/grip, oms/store, oms/retrieve sama untuk semua varian OMS; varian dipilih di konfigurasi platform | Keputusan panitia soal servo | P0 | Misi yang sama berjalan dengan dua varian OMS di mock | T | - | Belum |
| OMS-04 | Robot memastikan objek terpegang; objek lepas memicu retry | G | P1 | Objek yang dicabut paksa saat diangkat terdeteksi | R | - | Belum |
| OMS-05 | Validator konfigurasi menolak jumlah aktuator di atas batas aturan | Aturan aktuator | P1 | Konfigurasi dengan 4 standard servo ditolak | T | - | Belum |
| OMS-06 | Magazin carousel: simpan dan keluarkan per kantong, isi diverifikasi sensor IR | G (bila magazin dipakai) | P2 | Diputuskan setelah test project menunjukkan jumlah objek per run | R | - | Belum |
| OMS-07 | Pengambilan tetap berhasil bila kubus digeser atau diputar di stand, di dalam rentang pada tabel lingkungan operasi | D, G | P1 | ≥ 19 dari 20 percobaan dengan posisi kubus diacak di dalam rentang | R | - | Belum |

### OPS — Keselamatan dan operasional

| ID | Kebutuhan | Sumber | Prio | Kriteria terima | Verifikasi | Pemilik | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| OPS-01 | Daya ON langsung menjalankan health check lalu READY, tanpa laptop | A, B | P0 | 10 kali nyala berturut-turut sampai READY tanpa campur tangan | R | - | Belum |
| OPS-02 | Health check memeriksa LiDAR, kamera, kontroler motor, baterai, dan misi; kegagalan membuat FAULT dan nama komponennya tampil di OLED dan dashboard | A, B | P0 | Setiap komponen yang dicabut terdeteksi dengan nama yang benar | R | - | Belum |
| OPS-03 | Status tampil lewat LED, buzzer, dan OLED sesuai tabel state di dokumen arsitektur, dengan warna yang sama di dashboard | B | P0 | Setiap state diperiksa dan cocok dengan tabel | I | - | Belum |
| OPS-04 | RESET dan RETRY bisa dilakukan dari tombol fisik robot | B | P0 | Seluruh skenario pemulihan dijalankan tanpa laptop | R | - | Belum |
| OPS-05 | Setelah e-stop dilepas, robot tidak bergerak sendiri; hanya RESET lalu START yang menjalankannya kembali | C, keselamatan | P0 | 10 kali e-stop di tengah gerak, tidak ada gerakan setelah dilepas | R | - | Belum |
| OPS-06 | Watchdog mengirim kecepatan nol bila perintah gerak berhenti datang lebih lama dari batas di konfigurasi | Keselamatan | P0 | Node misi dimatikan paksa saat bergerak, robot berhenti dalam batas waktu | R | - | Belum |
| OPS-07 | Semua perintah gerak lewat twist\_mux; tidak ada node lain yang menerbitkan langsung ke masukan driver motor | Keselamatan | P0 | Topik masukan driver hanya punya satu publisher di bringup lomba | I | - | Belum |
| OPS-08 | START ditolak bila tegangan baterai di bawah ambang | Keandalan | P1 | Diuji dengan catu daya yang diturunkan | R | - | Belum |
| OPS-09 | Node yang crash di-restart, motor berhenti, dan misi FAILED | Keandalan | P1 | Node dimatikan paksa saat run | R | - | Belum |
| OPS-10 | Jalur penuh tanpa laptop: misi dipilih dan acakan (urutan target, warna rak) diisi dari tombol robot dan OLED, lalu ditampilkan ulang untuk dicek | B | P1; menjadi P0 bila technical meeting melarang laptop disentuh | Ganti misi dan isi acakan E tanpa laptop dalam ≤ 90 detik (usulan), tanpa salah isi dalam 10 percobaan | R | - | Belum |
| OPS-11 | Selama run, laju data LiDAR, kamera, IMU, odometri, dan status kontroler motor dipantau; bila salah satu di bawah ambang lebih lama dari batas waktu, robot berhenti, misi FAILED, dan nama komponennya ditampilkan | Keselamatan, G | P0 | Tes dengan sensor tiruan yang dihentikan; di robot, kabel LiDAR dan kamera dicabut saat run | T, R | - | Belum |
| OPS-12 | Versi software (tag atau commit) dan versi misi tampil di OLED dan dashboard, dan tercatat di log run | NF-04 | P1 | Versi di layar sama dengan tag rilis | I | - | Belum |
| OPS-13 | Penghenti depan independen: ultrasonik atau IR depan menghentikan robot bila jarak di bawah ambang, terlepas dari LiDAR; menutupi obstacle di bawah bidang pindai, bahan hitam atau mengilap, dan benda yang bergerak masuk | Keselamatan, E, G | P1 | Obstacle rendah berwarna hitam dan tangan yang masuk di depan robot memicu berhenti | R | - | Belum |

### DASH — Dashboard operator

| ID | Kebutuhan | Sumber | Prio | Kriteria terima | Verifikasi | Pemilik | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| DASH-01 | Satu aplikasi dengan dua mode: Lomba dan Pengembangan; mode Lomba menyembunyikan dan mengunci fitur, bukan program terpisah | B | P0 | Fitur di tabel fitur operator tampil atau tersembunyi sesuai mode | T, I | - | Belum |
| DASH-02 | Layar utama mode Lomba: checklist kesiapan hijau atau merah, indikator READY, serta nama dan versi misi | A, B | P0 | Operator yang tidak ikut membangun bisa menyatakan robot siap atau tidak dalam 10 detik (usulan) | R | - | Belum |
| DASH-03 | Acakan juri diisi lewat form yang dibuat dari skema misi dan divalidasi sebelum disimpan | E, G | P0 | Masukan salah ditolak dengan pesan jelas | T | - | Belum |
| DASH-04 | Mode Lomba tidak punya kontrol gerak; teleop, uji satu skill, alat bring-up, dan ubah parameter hanya di mode Pengembangan | B | P0 | Tidak ada tombol gerak di mode Lomba | I | - | Belum |
| DASH-05 | Semua edit terkunci saat RUNNING | Keselamatan | P0 | Edit saat RUNNING ditolak | T | - | Belum |
| DASH-06 | Putus koneksi dashboard tidak mempengaruhi run, dan dashboard menyambung sendiri | B | P0 | Wi-Fi laptop dimatikan saat run, run tetap selesai | R | - | Belum |
| DASH-07 | Dashboard berjalan tanpa internet; tidak ada aset yang diambil dari CDN | Aturan offline | P0 | Dashboard terbuka normal dengan Wi-Fi tanpa internet | R | - | Belum |
| DASH-08 | Mode demo visi, kalibrasi HSV, serta pemetaan dan penandaan titik tersedia untuk sesi persiapan | F, E, G | P0 | Lihat VIS-02, VIS-03, NAV-05 | R | - | Belum |
| DASH-09 | Monitor run baca-saja: langkah aktif, waktu berjalan, hasil per langkah | B | P1 | Tampilan sesuai log misi | I | - | Belum |
| DASH-10 | Riwayat run dan alasan gagal | Pemulihan | P1 | Alasan gagal run terakhir terbaca tanpa membuka terminal | I | - | Belum |
| DASH-11 | Mode Pengembangan: edit YAML mentah dengan validator untuk menyusun misi baru | Aturan 30% | P1 | M7 | R | - | Belum |
| DASH-12 | Sebelum START, isi acakan yang termuat (misi, urutan target, warna rak) ditampilkan besar di dashboard dan ringkasnya di OLED untuk dicocokkan dengan lembar juri | E, G | P0 | Acakan yang sengaja ditukar di file terlihat berbeda di layar dan OLED; operator uji menemukannya dalam 10 detik (usulan) | R | - | Belum |
| DASH-13 | Konfigurasi lomba selalu menyala dalam mode Lomba; pindah ke mode Pengembangan butuh PIN, dan mode aktif selalu tampil jelas | B, keselamatan | P0 | Setelah boot dengan konfigurasi lomba, mode Pengembangan tidak bisa dibuka tanpa PIN | T, R | - | Belum |
| DASH-14 | Panel keputusan setelah FAILED atau STOPPED: langkah yang gagal, alasannya, sisa waktu dari 600 s, dan perkiraan waktu sampai READY lagi | B, E, G | P1 | Operator bisa memutuskan retry atau finish tanpa membuka halaman lain | R | - | Belum |
| DASH-15 | Peta baca-saja di mode Lomba: posisi robot, titik target bernama, dan status lokalisasi (konvergen atau belum) sebelum START | E, G | P1 | Titik yang salah tandai dan lokalisasi yang belum konvergen terlihat sebelum START | R | - | Belum |
| DASH-16 | Hanya satu sesi pengendali; perangkat lain yang membuka dashboard bersamaan hanya bisa membaca | Keselamatan | P1 | Dua browser terbuka bersamaan: perubahan dari browser kedua ditolak | T | - | Belum |
| DASH-17 | Acakan diisi dengan memilih dari daftar, bukan mengetik; huruf besar dan kontras tinggi agar terbaca di cahaya arena | B | P1 | Pengisian acakan E selesai ≤ 60 detik (usulan); teks status terbaca dari jarak 1 meter | R | - | Belum |
| DASH-18 | Pencatat percobaan: jumlah run, retry yang sudah dipakai per modul, dan hasil yang dicatat juri | Strategi lomba | P2 | Rekap satu hari lomba bisa dibaca dan diunduh | I | - | Belum |
| DASH-19 | Jam robot disinkronkan dari browser laptop saat dashboard terhubung, agar urutan log benar tanpa internet | Pemulihan, laporan teknis | P2 | Selisih jam robot dan laptop ≤ 1 detik setelah sinkron | T | - | Belum |
| DASH-20 | Halaman pendaftaran objek di sesi persiapan: ambil foto per objek, beri label, lihat jumlah contoh per label, uji langsung, dan hapus contoh yang buruk | F, tantangan ala WSC | P0 | Operator yang tidak ikut membangun bisa mendaftarkan 5 objek tanpa bantuan dalam batas waktu M9 | R | - | Belum |

### PLAT — Adaptor platform

| ID | Kebutuhan | Sumber | Prio | Kriteria terima | Verifikasi | Pemilik | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| PLAT-01 | Kode misi, skill, visi, operasional, dan dashboard hanya memakai nama dari kontrak antarmuka | Kesiapan platform | P0 | Tidak ada nama topik vendor di luar paket adaptor | T | - | Belum |
| PLAT-02 | Platform mock untuk tes otomatis di setiap commit | Keterpeliharaan | P0 | Semua tes misi berjalan di mock tanpa hardware | T | - | Belum |
| PLAT-03 | Platform dipilih dengan satu argumen launch | Kesiapan platform | P0 | Ganti platform tanpa ubah file lain selain konfigurasi platform | T | - | Belum |
| PLAT-04 | Adaptor LanderPi memenuhi kontrak | Platform latihan | P0 | Uji asap semua baris kontrak di LanderPi | R | - | Belum |
| PLAT-05 | Adaptor robot custom dan firmware Nucleo memenuhi kontrak; lima uji penerimaan micro-ROS lulus, atau beralih ke protokol serial tim | Platform cadangan | P0 bila robot custom jadi robot lomba, P1 bila tidak | Lima uji di dokumen platform robot custom | R | - | Belum |
| PLAT-06 | Firmware Nucleo menghentikan motor bila perintah tidak datang, dan mengunci PWM di nol selama e-stop aktif sampai RESET | Keselamatan | P0 bila robot custom jadi robot lomba | Uji putus kabel dan uji e-stop di robot custom | R | - | Belum |
| PLAT-07 | Penanda kemampuan platform (misalnya kamera depth, lengan) membuat fitur khusus satu robot menjadi opsional | Kesiapan platform | P2 | Misi wajib tidak bergantung pada kemampuan opsional | T | - | Belum |

### BRG — Dukungan pembangunan robot (bring-up)

Alat ini dipakai saat merakit dan menghidupkan robot pertama kali, terutama robot custom: memastikan setiap motor, encoder, sensor, dan aktuator benar sebelum skill dan misi diuji. Semuanya hanya ada di mode Pengembangan, kecepatannya dibatasi, dan e-stop tetap berlaku. Fitur yang sama dipakai juga di LanderPi setelah ganti roda, motor, atau kabel.

| ID | Kebutuhan | Sumber | Prio | Kriteria terima | Verifikasi | Pemilik | Status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| BRG-01 | Uji satu motor: memutar satu roda dengan kecepatan dan durasi terbatas, lalu menampilkan arah putar dan hitungan encoder roda itu | Pembangunan robot | P0 | Kabel tertukar, arah terbalik, atau tanda encoder terbalik langsung terlihat untuk tiap roda | R | - | Belum |
| BRG-02 | Tampilan data mentah: encoder per roda, IMU, tombol, sinyal e-stop, tegangan baterai, beserta laju data tiap topik | Pembangunan robot | P0 | Setiap sensor yang digerakkan tangan terlihat berubah di layar | R | - | Belum |
| BRG-03 | Status koneksi kontroler motor: terhubung atau putus, jumlah sambung ulang, dan versi firmware yang dilaporkan Nucleo dibandingkan dengan versi yang diharapkan | PLAT-05 | P0 | Versi firmware salah ditandai merah; cabut-pasang kabel terlihat sebagai sambung ulang | R | - | Belum |
| BRG-04 | Uji aktuator OMS satu per satu (gripper, lifter, servo carousel) dengan batas gerak dari konfigurasi dan tombol posisi aman | OMS-01, OMS-02 | P0 | Setiap aktuator bergerak sesuai perintah tanpa melewati batas | R | - | Belum |
| BRG-05 | Kalibrasi kinematika: rutinitas jalan lurus maju, geser samping, dan putar 360° yang menghitung koreksi jari-jari roda dan jarak roda ke pusat, lalu menyimpannya ke kalibrasi platform | NAV-01 sampai NAV-04 | P0 | Setelah kalibrasi, galat odometri di dalam batas yang ditetapkan tim | R | - | Belum |
| BRG-06 | Tuning PID kecepatan roda: memberi perintah langkah, menampilkan grafik target dan kecepatan aktual, serta menyimpan gain yang dipilih | Pembangunan robot | P1 | Respons tiap roda terekam dan gain tersimpan dengan catatan versi | R | - | Belum |
| BRG-07 | Pemeriksaan pemasangan sensor: scan LiDAR dan citra kamera ditampilkan di atas model robot (URDF) untuk mengecek posisi, arah, dan tinggi bidang pindai | C-10 | P1 | Dinding lurus terlihat lurus dan di posisi yang benar terhadap model robot | R | - | Belum |
| BRG-08 | Self-test hardware: BRG-01, BRG-02, dan BRG-04 dijalankan berurutan saat roda diangkat, dengan laporan lulus atau gagal per komponen | Pembangunan robot | P1 | Laporan tersimpan setiap kali dijalankan | R | - | Belum |
| BRG-09 | Platform mock bisa meniru topik firmware robot custom, sehingga adaptor custom bisa diuji sebelum hardware selesai | PLAT-05 | P1 | Tes adaptor custom lulus di mock | T | - | Belum |

## Kebutuhan non-fungsional

| ID | Kebutuhan | Prio | Kriteria terima | Verifikasi | Pemilik | Status |
| --- | --- | --- | --- | --- | --- | --- |
| NF-01 | Tidak ada ketergantungan pada internet saat berjalan, termasuk paket, model, font, dan aset dashboard | P0 | Seluruh uji lapangan dijalankan dengan Wi-Fi tanpa internet | R | - | Belum |
| NF-02 | Beban CPU dan suhu Raspberry Pi 5 aman saat SLAM atau Nav2, visi, dan dashboard berjalan bersamaan | P0 | Tanpa throttling termal selama run 600 s; ambang ditetapkan setelah ukur | R | - | Belum |
| NF-03 | Waktu dari daya ON sampai READY diketahui dan cukup kecil untuk retry di dalam 600 s | P0 | Diukur 10 kali; angka dipakai di anggaran waktu (M6) | R | - | Belum |
| NF-04 | Konfigurasi yang dibawa ke lomba dibekukan dengan tag git; perubahan di hari lomba hanya pada file misi dan kalibrasi | P0 | Tag rilis ada; perubahan hari lomba hanya menyentuh missions/ dan calibration/ | I | - | Belum |
| NF-05 | Hanya API ROS2 Humble dan rclpy; setiap paket eksternal baru dicatat dulu di tabel tech stack | P0 | Pemeriksaan dependensi di setiap rilis | I | - | Belum |
| NF-06 | Kode vendor Hiwonder tidak diedit; perubahan perilaku lewat parameter, launch, atau paket tim | P0 | Hook menolak edit ke src/vendor/ | I | - | Belum |
| NF-07 | Setiap perubahan kode lulus linter dan tes otomatis di mock sebelum diuji di robot | P0 | Hook dan riwayat commit | I | - | Belum |
| NF-08 | Satuan SI dan frame sesuai REP-103 dan REP-105; derajat hanya di YAML dengan akhiran \_deg | P0 | Tes konversi dan validator skema | T | - | Belum |
| NF-09 | Setiap siswa mampu menjelaskan alur dari START sampai FINISH dan alasan desain utama | P1 | Presentasi ke pembimbing sebelum lomba; mendukung kriteria C | I | - | Belum |
| NF-10 | Jaringan robot memakai SSID dan password tim sendiri; dashboard hanya bisa dibuka dari jaringan itu | P1 | Kredensial bawaan pabrik tidak lagi berlaku | I | - | Belum |
| NF-11 | Kode misi dan skill tidak bergantung pada fitur khusus Humble, agar bisa pindah ke ROS2 Jazzy untuk 2027 | P2 | Daftar ketergantungan khusus Humble kosong atau tercatat | I | - | Belum |

## Batasan dari aturan dan hardware

Batasan bukan fitur yang dibangun, melainkan pagar yang tidak boleh dilanggar software. Yang bertanda "menunggu panitia" disiapkan dalam dua varian (lihat bagian varian di dokumen arsitektur).

| ID | Batasan | Asal | Dampak ke software | Status |
| --- | --- | --- | --- | --- |
| C-01 | Main controller Raspberry Pi | Aturan | Semua logika misi, navigasi, dan visi di Pi; STM32 hanya slave controller | Pasti; STM32 sebagai slave perlu dikonfirmasi ulang |
| C-02 | Aktuator maksimal 4 motor DC, 3 standard servo, 2 continuous servo | Aturan | OMS-05; varian OMS dipilih di konfigurasi | Pasti; status servo bus menunggu panitia |
| C-03 | Sensor maksimal 1 webcam, 1 LiDAR, 1 IMU, 4 IR, 2 ultrasonik, 4 sensor garis | Aturan | Health check dan konfigurasi tidak memakai sensor di luar daftar | Pasti; status kamera depth menunggu panitia |
| C-04 | Tombol STOP merah yang mudah diakses dan berfungsi | Aturan | OPS-05, OPS-06; opsi A atau B dipilih lewat harness | Pasti; putus daya total atau motor saja menunggu panitia |
| C-05 | Start dengan satu tekan tombol fisik | Aturan | MIS-01 | Pasti |
| C-06 | Batas waktu run 600 s | Aturan | MIS-04, M3 | Pasti |
| C-07 | Penalti bila menyentuh robot atau laptop tanpa izin | Aturan | OPS-04, OPS-10, DASH-04 | Pasti; kapan laptop boleh disentuh menunggu technical meeting |
| C-08 | Hingga 30% soal bisa berubah di hari lomba | Aturan | MIS-02, DASH-11, M7 | Pasti |
| C-09 | Baterai maksimal 28 V | Aturan | Ambang OPS-08 per platform | Pasti |
| C-10 | Obstacle setinggi 200 mm | Aturan | Bidang pindai LiDAR harus di bawah 200 mm, atau obstacle tidak terlihat oleh NAV-04 | Tinggi LiDAR belum diukur |
| C-11 | Tanpa internet dan tanpa AI saat lomba | Aturan dan kondisi lomba | NF-01; semua alat yang dibutuhkan operator ada di robot dan laptop | Pasti |
| C-12 | Satu kontroler motor per platform (RRC Lite atau Nucleo) dengan protokol masing-masing | Hardware | Hanya adaptor yang mengenal protokolnya (PLAT-01) | Pasti |

## Matriks keterlacakan penilaian

Setiap butir penilaian harus punya minimal satu kebutuhan P0. Kriteria yang sebagian besar ditentukan hardware atau perilaku tim tetap dicatat agar terlihat bagian mana yang tidak ditanggung software.

| Kriteria (bobot) | Yang dinilai | Kebutuhan software | Di luar software |
| --- | --- | --- | --- |
| A Organisasi (10) | Tepat waktu, robot lengkap akhir hari 1, area rapi | OPS-01, OPS-02, DASH-02 | Disiplin tim, checklist hari lomba |
| B Komunikasi (7) | Tidak menyentuh tanpa izin; panggilan ready, retry, reset, finish | OPS-03, OPS-04, OPS-10, MIS-07, DASH-04, DASH-06, DASH-13, DASH-14, DASH-17 | Latihan prosedur operator |
| C Desain (10) | E-stop berfungsi, wiring rapi, modularitas, orisinalitas | OPS-05, OPS-06, PLAT-06, NF-09 | Mekanik, kelistrikan, OMS buatan tim |
| D Gerak dasar (10) | Putar 90° dan 180°, wall following kanan dan kiri, berhenti di dinding, ambil dan letakkan kubus | NAV-01, NAV-02, NAV-03, NAV-07, OMS-01, OMS-02, BRG-05 | Kalibrasi roda dan IMU |
| E Navigasi (13) | Start satu tombol, 4 target acak, obstacle, ≤ 600 s | MIS-01, MIS-03, MIS-04, MIS-10, NAV-04, NAV-05, NAV-13, OPS-11, OPS-13, DASH-03, DASH-12, DASH-15 | Tinggi LiDAR (C-10) |
| F Visi (10) | Identitas 9 objek tampil di feed | VIS-01, VIS-02, VIS-03, VIS-04, VIS-09, VIS-10, VIS-11, DASH-20 | Posisi kamera dan pencahayaan |
| G1 Performa statis (16) | Start, ambil, letakkan di slot benar, kembali ke home, waktu | MIS-01, MIS-04, MIS-05, MIS-10, OMS-01, OMS-02, OMS-03, NAV-04, NAV-07, NAV-08, OPS-11 | Ketepatan mekanik gripper dan lifter |
| G2 Performa dinamis (24) | Sama dengan G1, tetapi tujuan ditentukan dari kondisi aktual | MIS-06, MIS-12, VIS-01, VIS-05, VIS-07, VIS-08, ditambah kebutuhan G1 | Sama dengan G1 |

Urutan pengerjaan mengikuti bobot: G (40) dan D (10) bergantung pada OMS-01 dan OMS-02, sehingga keandalan ambil dan letakkan adalah jalur kritis bersama navigasi.

## Milestone dan urutan rilis

Tanggal belum diisi karena jadwal lomba dan tanggal evaluasi micro-ROS belum ditetapkan. Setiap rilis selesai hanya bila kriteria keluarnya lulus; rilis berikutnya tidak dimulai sebelum P0 rilis sebelumnya lulus.

| Rilis | Isi | Kriteria keluar | Target tanggal |
| --- | --- | --- | --- |
| R0 Fondasi | Kontrak antarmuka, platform mock, image Docker, hook dan tes; pengukuran tinggi LiDAR, beban CPU, waktu boot | PLAT-01, PLAT-02, PLAT-03, NF-07 lulus; hasil ukur tercatat di dokumen platform; tabel lingkungan operasi terisi dan anggaran teknis disepakati | Diisi tim |
| R1 Bergerak aman | Adaptor LanderPi, state machine, tombol, LED, watchdog, health check | BRG-01 sampai BRG-05, OPS-01 sampai OPS-07, OPS-11, MIS-01, MIS-07; siklus START, e-stop, RESET aman 10 kali | Diisi tim |
| Gerbang platform | Memilih robot lomba utama; evaluasi micro-ROS di robot custom | Di robot custom: BRG-01 sampai BRG-05 lulus, PLAT-05 dan PLAT-06 lulus atau beralih ke protokol serial; keputusan dicatat sebagai ADR | Tanggal evaluasi micro-ROS |
| R2 Gerak dasar | Skill Modul D dan OMS satu kubus (gripper dan lifter) | NAV-01 sampai NAV-03, OMS-01, OMS-02; M2 | Diisi tim |
| R3 Navigasi dan visi | Nav2 dengan titik bernama, file misi, deteksi warna dan bentuk, dashboard mode Lomba | NAV-04, NAV-05, NAV-09, NAV-13, MIS-02 sampai MIS-05, MIS-10, VIS-01 sampai VIS-04, VIS-09, VIS-11, DASH-20, DASH-01 sampai DASH-08, DASH-12, DASH-13; M3, M4 | Diisi tim |
| R4 Performa | Misi G1 lalu G2 end-to-end | MIS-06, MIS-12, OMS-03, NAV-07, NAV-08; M1 | Diisi tim |
| R5 Siap lomba | Gladi tanpa internet, latihan 13 skenario pemulihan, pembekuan konfigurasi | Semua P0 lulus, NF-04, M5, M7; skill cadangan NAV-10 sampai NAV-12 teruji; strategi lewati dilatih; checklist hari lomba dicetak | Sebelum keberangkatan |

Kebutuhan P1 dikerjakan setelah P0 rilis yang sama lulus. P2 (magazin, deteksi sambil bergerak, penanda kemampuan) hanya dikerjakan setelah R4 lulus.

## Asumsi dan pertanyaan terbuka

**Asumsi** (bila terbukti salah, kebutuhan terkait ditinjau ulang)

- Skema penilaian Jawa Tengah 2026 berlaku di tingkat yang diikuti; kisi-kisi nasional membagi bobot berbeda tetapi jenis tugasnya sama.
- Format G1 dan G2 menyebut satu objek target per tugas, sehingga magazin tetap P2.
- Operator boleh memakai laptop untuk mengisi acakan sebelum run; bila tidak, OPS-10 naik menjadi P0.
- Angka target di ukuran keberhasilan adalah usulan dan disepakati tim sebelum R2.

**Pertanyaan terbuka** (pertanyaan ke panitia dan pengukuran dicatat lengkap di dokumen arsitektur dan dokumen platform)

- [ ] Tim dan pembimbing menyepakati target M1 sampai M8, toleransi internal, dan anggaran teknis
- [ ] Tanggal lomba dan tanggal evaluasi micro-ROS untuk mengisi tabel milestone
- [ ] Toleransi juri untuk putaran 90° dan 180° serta jarak berhenti di dinding, untuk mengoreksi toleransi internal
- [ ] Lama sesi familiarisasi, sebagai batas NAV-05 dan VIS-03
- [ ] Kapan laptop boleh disentuh (menentukan prioritas OPS-10)
- [ ] Keputusan panitia soal servo bus, kamera depth, dan jenis e-stop (C-02, C-03, C-04)
- [ ] Ukuran arena, zona home, obstacle, serta tinggi, lebar, dan kedalaman slot rak dari gambar teknis kisi-kisi
- [ ] Pemilik setiap kebutuhan P0 diisi sebelum R1
- [ ] Sensor garis dan ultrasonik depan dipasang di kedua platform atau tidak (syarat NAV-11, NAV-12, OPS-13), dengan tetap di dalam batas jumlah sensor
- [ ] Rentang variasi posisi kubus serta jarak dan sudut uji visi, untuk mengisi tabel lingkungan operasi
- [ ] Apakah juri memberi contoh fisik objek saat persiapan (menentukan VIS-09 atau VIS-10 sebagai jalur utama), dan apakah jawaban identifikasi yang salah dikenai penalti dibanding tidak menjawab

Dokumen terkait: [Arsitektur Aplikasi AMR LKS (Inti)](https://claude.ai/code/artifact/6c262358-74ef-48e4-94e0-8bbd48ad8ef4), [Platform LanderPi](https://claude.ai/code/artifact/8ac7d295-c134-4073-8388-9ddf84fd890f), [Platform Robot Custom](https://claude.ai/code/artifact/b5300349-16b8-484d-b8f3-20c51b8ec048).
