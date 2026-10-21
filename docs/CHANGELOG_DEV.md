# Catatan Perubahan Pengembangan — AMR LKS Dashboard

Dokumen ini mencatat setiap perubahan pada *working tree* (direktori kerja Git)
repository AMR LKS Dashboard, baik yang sudah ada sebelum tahap audit ini maupun
yang dibuat selama tahap audit. Tujuannya agar setiap perubahan dapat
ditulusuri: apa yang berubah, mengapa, berdampak ke mana, kebutuhan PRD mana
yang terkait, dan bagaimana verifikasinya.

Istilah teknis yang dipakai:

- **Working tree** — kumpulan file di disk yang belum tentu sudah masuk ke
  commit Git. Perubahan "belum terlacak" (untracked) adalah file yang belum
  pernah ditambahkan ke Git.
- **Commit dasar** — commit Git terakhir yang menjadi titik acuan. Saat audit
  ini, commit dasar adalah `9df1632` ("phase 1- Initialitation and Baseline Py &
  NiceGUI"), di branch `main`.
- **Diff** — selisih antara file di disk dan versi yang tersimpan di commit.
- **Simulasi (mock)** — kode yang meniru perilaku robot tanpa perangkat keras,
  ROS 2, maupun koneksi jaringan, sehingga dapat diuji otomatis dan
  deterministik (hasil sama untuk masukan yang sama).

---

## 1. Ringkasan tahap

Tahap ini adalah **audit dan dokumentasi**, bukan implementasi fitur baru.
Sesuai batas pekerjaan:

- Tidak ada `git reset --hard`, `git clean`, commit, push, atau ganti branch.
- Tidak ada file yang dihapus atau ditimpa.
- Tidak ada penulisan ulang mission runner atau subsistem baru.

Satu-satunya perubahan yang *dilakukan selama tahap ini* adalah pembuatan file
dokumen ini (`docs/CHANGELOG_DEV.md`). Semua perubahan lain yang tercatat di
bawah adalah **kondisi yang sudah ada sebelum audit** (perubahan lokal yang
belum masuk commit), yang didokumentasikan ulang agar dapat ditelusuri.

---

## 2. Kondisi Git

### 2.1 Sebelum audit

- Branch: `main` (satu-satunya branch; tidak ada remote yang dikonfigurasi).
- Commit dasar / HEAD: `9df1632` (`phase 1- Initialitation and Baseline Py & NiceGUI`).
- Riwayat sebelumnya: `15ad5b4` (commit inisialisasi). Tidak ada `git stash` aktif.
- **5 file terlacak berubah (modified), 0 file bersih (unstaged=0, staged=0):**

  | File | +Baris | −Baris |
  | --- | --- | --- |
  | `src/amr_core/__init__.py` | 31 | 1 |
  | `src/amr_core/mission.py` | 96 | 0 |
  | `src/amr_core/simulation.py` | 50 | 3 |
  | `src/amr_dashboard/app.py` | 63 | 19 |
  | `src/amr_dashboard/panels.py` | 31 | 0 |

- **15 file baru yang belum terlacak (untracked):**
  `src/amr_core/mission_loader.py`, `src/amr_core/mission_runner.py`,
  `src/amr_core/mock_platform.py`, `src/amr_core/skills.py`,
  `src/amr_dashboard/runtime.py`, `tests/conftest.py`,
  `tests/test_dashboard_mission_log.py`, `tests/test_dashboard_refresh_only.py`,
  `tests/test_engine_runner_integration.py`, `tests/test_mission_loader.py`,
  `tests/test_mission_runner.py`, `tests/test_runtime.py`,
  `tests/test_server_loop.py`, `tests/test_server_loop_integration.py`,
  `tests/test_skills_mock.py`.
- Direktori `docs/` **belum ada** sebelum tahap ini.

### 2.2 Sesudah audit

- Branch dan HEAD tidak berubah (`main` @ `9df1632`).
- 5 file modified dan 15 file untracked tetap utuh (tidak ada yang dibuang).
- Tambahan baru: 1 file baru `docs/CHANGELOG_DEV.md` (file ini).
- Tidak ada commit, push, reset, atau pembersihan.

> Catatan penting untuk penelusuran: `src/amr_core/__init__.py` (modified) dan
> `src/amr_dashboard/app.py` (modified) meng-*import* modul yang **belum
> terlacak** (`mission_loader`, `mission_runner`, `skills`, `runtime`). Artinya
> working tree ini **hanya dapat dijalankan sebagai satu kesatuan**; versi pada
> commit dasar `9df1632` (tanpa file untracked) tidak akan bisa meng-import
> `amr_core`/`amr_dashboard` karena import baru menunjuk ke modul yang tidak ada
> di sana. Ini menegaskan perubahan lokal harus dipertahankan.

---

## 3. Perubahan yang sudah ada sebelum audit (Phase 2)

Bagian ini mendokumentasikan perubahan lokal yang ditemukan saat audit.
Kondisi "Sebelum" diambil dari `git show HEAD:<file>` (commit dasar `9df1632`).
Kondisi "Sesudah" adalah isi file di disk saat audit. Semua "Verifikasi"
menunjukkan hasil tes yang benar-benar dijalankan pada tahap ini.

### 3.1 `src/amr_core/mission_loader.py` (baru)

- **File:** `src/amr_core/mission_loader.py`
- **Jenis perubahan:** baru (belum terlacak Git).
- **Sebelum:** tidak ada. Pada commit dasar, belum ada pemuat misi YAML; misi
  hanya berupa data contoh di memori (`amr_core/samples.py`) yang belum dibaca
  dari file.
- **Sesudah:** modul pemuat dan validator misi YAML. Fungsi publik
  `load_mission_yaml(text)` mengembalikan `(MissionSpec | None, list[ValidationIssue])`
  dan `load_mission_file(path)` membaca berkas lalu memanggil yang pertama.
  Modul memvalidasi: `mission`, `version`, `time_limit_s` (dengan batas
  `MIN/MAX_TIME_LIMIT_S`), `reserve_for_home_s`, `start` (hanya
  `physical_button`), dan `steps`. Bentuk `for_each: {targets: [...]}` +
  `do: {...}` (sesuai arsitektur) dinormalisasi menjadi langkah datar. Ekspresi
  dinamis (mengandung `(` atau `)`, mis. `rack_for(obj.color)`) **ditolak**,
  bukan dievaluasi. YAML rusak atau dokumen kosong menghasilkan
  `ValidationIssue("document", ...)` dan tidak melempar pengecualian.
- **Alasan:** arsitektur prinsip #1 "misi adalah data, bukan kode"; PRD MIS-02
  (misi dimuat dari YAML dan divalidasi skema). Memisahkan validasi misi dari
  eksekusi agar file tidak valid ditolak sebelum robot masuk READY.
- **Dampak terhadap sistem:** menyediakan jalur "sumber kebenaran" misi berbasis
  file. Belum diintegrasikan ke dashboard (dashboard masih memakai
  `spec_from_config` dan sampel di memori); jadi belum mengubah perilaku
  runtime dashboard saat ini.
- **Referensi PRD/arsitektur:** PRD MIS-02, MIS-05, MIS-06, NF-08, C-08;
  Arsitektur "Skema konfigurasi".
- **Verifikasi:** `python -m pytest tests/test_mission_loader.py -q` — **16 tes
  lulus**. Mencakup: parsing valid, `for_each` menjadi 5 langkah datar, bentuk
  datar, `timeout_s` wajib, `mission_id` hilang, versi 0, batas waktu di luar
  rentang, reserve ≥ limit, reserve negatif, skill tak dikenal, `go_to` tanpa
  target, target tak dikenal, target `for_each` duplikat, `on_fail` tidak valid,
  `retry` negatif, ekspresi dinamis ditolak, YAML rusak, dan dokumen kosong.
- **Status:** lulus (untuk tes unit yang ada). Belum diuji pada robot fisik.

### 3.2 `src/amr_core/mission_runner.py` (baru)

- **File:** `src/amr_core/mission_runner.py`
- **Jenis perubahan:** baru (belum terlacak Git).
- **Sebelum:** tidak ada. Pada commit dasar, kemajuan misi dihitung di dalam
  `SimulationEngine.tick` dengan pola sintetis ("satu langkah per beberapa detik
  simulasi"), tanpa retry, timeout per langkah, atau batas pulang (reserve).
- **Sesudah:** pengeksekusi misi (sequencer) deterministik berbasis
  `MissionSpec`. Kelas utama `MissionRunner` (dataclass) dengan state internal
  `RunnerState {IDLE, RUNNING, RETURNING, FINISHED}` dan hasil
  `RunnerOutcome {WAIT, DONE, FAIL}`. API publik: `configure`, `start`,
  `abort`, `reset`, `step_once(now_s)`, properti `return_home_completed`, serta
  helper `mission_status(runner)` yang mengembalikan `MissionStatus` (view model
  baca-saja untuk dashboard). Aturan yang diterapkan, sesuai docstring modul:
  batas waktu global selalu menang; reserve dievaluasi hanya pada batas langkah
  (bukan di tengah skill); retry hanya dimulai bila tidak memakan jatah reserve;
  setiap percobaan menghasilkan paling banyak satu catatan terminal; setiap
  langkah yang dilewati karena reserve mendapat catatan `SKIPPED` eksplisit;
  `return_home` yang belum selesai saat batas waktu mendapat catatan
  `TIMEOUT` `incomplete=True` sebelum run menjadi FAILED; sekali masuk
  RETURNING, run hanya DONE bila `return_home` sukses. Setiap percobaan
  menghasilkan `StepLogRecord` (log misi terstruktur/typed) yang juga
  meringkas satu baris ke log engine.
- **Alasan:** arsitektur prinsip #3 ("setiap langkah punya batas waktu dan aturan
  gagal"), skenario kegagalan #3/#4 (retry lalu `skip`; reserve waktu pulang),
  dan pemisahan tanggung jawab: runner mengatur **urutan** langkah, sedangkan
  state aplikasi tetap milik `SimulationEngine`.
- **Dampak terhadap sistem:** menyediakan mesin eksekusi misi yang mengikuti
  misi YAML (timeout, retry, on_fail, reserve). Karena `SimulationEngine`
  mendelegasikan `tick` ke runner bila ada runner terlampir, mesin ini sekarang
  aktif di jalur dashboard.
- **Referensi PRD/arsitektur:** PRD MIS-04, MIS-05, MIS-08; Arsitektur "Katalog
  skill", "State machine operasional", skenario kegagalan #3/#4.
- **Verifikasi:** `python -m pytest tests/test_mission_runner.py -q` — **19 tes
  lulus**. Mencakup happy path, retry 0=1 percobaan / retry 2=3 percobaan,
  retry lalu sukses, `on_fail=skip` vs `fail`, timeout yang dipaksa manager vs
  dilaporkan skill, batas waktu global, `return_home` belum selesai mendapat
  TIMEOUT `incomplete`, kegagalan `return_home`, reserve melewati langkah dan
  pulang, langkah aktif tidak dibunuh di batas reserve, retry tidak dimulai bila
  memakan reserve, abort membatalkan skill, reset membuang state, dan invarian
  log (maksimal satu catatan terminal per percobaan; satu catatan per langkah
  yang di-skip; field catatan lengkap; determinisme).
- **Status:** lulus (tes unit). Belum diuji pada robot fisik.

### 3.3 `src/amr_core/skills.py` (baru)

- **File:** `src/amr_core/skills.py`
- **Jenis perubahan:** baru (belum terlacak Git).
- **Sebelum:** tidak ada kontrak skill. Commit dasar hanya punya state machine,
  model misi, simulation engine, dan vision.
- **Sesudah:** kontrak skill Phase 2. `SkillStatus {SUCCESS, FAILURE, TIMEOUT,
  ABORTED}`, `SkillResult(status, reason, output)`, `SkillContext(log, outputs)`,
  dan `Protocol` `Skill` dengan `start(params, ctx)`, `poll(now_s)`,
  `cancel(reason)`. Membedakan dua jenis TIMEOUT: TIMEOUT yang **dilaporkan
  skill** (batas internal skill) vs TIMEOUT yang **dipaksa manager** (manager
  memanggil `cancel` lalu mencatat sendiri). Antarmuka bersifat *pull* (tanpa
  thread, tanpa sleep) agar manager deterministik.
- **Alasan:** arsitektur "Katalog skill" (skill adalah satu-satunya cara misi
  menggerakkan robot; setiap skill mengembalikan salah satu dari empat hasil
  plus alasan). Mengunci kontrak sebelum implementasi skill nyata.
- **Dampak terhadap sistem:** menetapkan antarmuka yang harus dipatuhi skill
  nyata di masa depan (mis. `go_to`, `pick`, `place`); runner mengonsumsi
  kontrak ini.
- **Referensi PRD/arsitektur:** PRD MIS-05; Arsitektur "Katalog skill" (aturan
  bersama: timeout dan retry dari file misi; skill tidak memanggil skill lain;
  saat dibatalkan kirim kecepatan nol).
- **Verifikasi:** diuji bersama `tests/test_skills_mock.py` (lihat 3.4) —
  **7 tes lulus**.
- **Status:** lulus (tes unit). Belum diuji pada robot fisik.

### 3.4 `src/amr_core/mock_platform.py` (baru)

- **File:** `src/amr_core/mock_platform.py`
- **Jenis perubahan:** baru (belum terlacak Git).
- **Sebelum:** tidak ada platform tiruan. Commit dasar hanya mensimulasikan
  kemajuan misi tanpa skill.
- **Sesudah:** platform tiruan Phase 2. `MissionClock` (jam monotonik yang
  dimajukan eksplisit, tanpa sleep) dan `ScriptedSkill` (skill yang perilakunya
  berupa skrip deterministik per percobaan: `SUCCESS`/`FAILURE`/`TIMEOUT`,
  dengan `duration_s` tiap percobaan; percobaan melebihi panjang skrip
  mengulang entri terakhir). `default_skill_factory()` menyediakan `go_to`,
  `return_home`, `wait_for_start`.
- **Alasan:** arsitektur platform `mock` (PLAT-02: platform tiruan untuk tes
  otomatis tiap commit) dan prinsip determinisme. Memungkinkan menguji runner,
  timeout, retry, dan reserve tanpa perangkat keras.
- **Dampak terhadap sistem:** menjadi sumber skill untuk `RobotRuntime`
  dashboard, sehingga misi berjalan end-to-end dalam simulasi.
- **Referensi PRD/arsitektur:** PRD PLAT-02, MIS-05; Arsitektur "Kesiapan
  multi-platform" (platform `mock`).
- **Verifikasi:** `python -m pytest tests/test_skills_mock.py -q` — **7 tes
  lulus**: skill sukses, skill melaporkan TIMEOUT, percobaan mengikuti skrip,
  `cancel` idempoten dan menghentikan hasil, paling banyak satu hasil, jam hanya
  maju ke depan, dan nama skill default.
- **Status:** lulus (tes unit). Belum diuji pada robot fisik.

### 3.5 `src/amr_dashboard/runtime.py` (baru)

- **File:** `src/amr_dashboard/runtime.py`
- **Jenis perubahan:** baru (belum terlacak Git).
- **Sebelum:** tidak ada runtime sisi-server. Pada commit dasar, kemajuan
  simulasi bergantung pada `ui.timer` **per halaman**: setiap browser yang
  membuka dashboard menjalankan timer sendiri, dan menutup browser menghentikan
  kemajuan.
- **Sesudah:** runtime robot sisi-server ("Opsi A"). `RobotRuntime` memiliki satu
  `SimulationEngine` + satu `MissionRunner` untuk seluruh proses server;
  `step(dt_s)` memajukan engine secara terbatas. Singleton proses `get_runtime()`
  dan `reset_runtime()` (dipakai tes). `ServerRuntimeLoop` memiliki **satu** loop
  kemajuan untuk proses; `start()` idempoten (klien kedua / startup ganda tidak
  membuat loop kedua), `stop()` membatalkan. `start_server_loop()`/
  `stop_server_loop()` adalah manajer loop tingkat proses. Catatan di kode:
  menargetkan arsitektur "server di robot, browser di laptop/HP operator", dan
  **belum divalidasi di Raspberry Pi**.
- **Alasan:** menegakkan satu sumber kemajuan tunggal agar misi tidak bergantung
  pada koneksi browser (DASH-06) dan agar menambah browser tidak menambah laju
  kemajuan. Menggantikan pola timer-per-halaman.
- **Dampak terhadap sistem:** mengubah arsitektur runtime dashboard dari
  "timer per halaman memajukan simulasi" menjadi "loop server tunggal memajukan,
  halaman hanya menyegarkan tampilan". Ini perubahan perilaku yang signifikan
  (lihat 3.8).
- **Referensi PRD/arsitektur:** PRD DASH-06, DASH-16; Arsitektur "Fitur operator"
  dan state machine operasional (dashboard sebagai node terpisah, tidak
  menggerakkan robot).
- **Verifikasi:** `python -m pytest tests/test_runtime.py tests/test_server_loop.py
  tests/test_server_loop_integration.py -q` — **21 tes lulus** (lihat 3.15 untuk
  rincian hasil gabungan). Termasuk tes integrasi yang menjalankan server NiceGUI
  sungguhan dan membuktikan loop maju tanpa browser serta tidak bertambah saat
  halaman diakses berulang.
- **Status:** lulus (tes unit + integrasi server). **Belum divalidasi di
  Raspberry Pi 5 / LanderPi** (klaim ini sengaja tidak dibuat).

### 3.6 `src/amr_core/skills.py` / nama modul lain — catatan penamaan

- Modul `skills.py` berada di `src/amr_core/`, sedangkan arsitektur
  mencantumkan paket terpisah `src/amr_skills/` (satu modul per skill) dan
  `src/amr_mission/` untuk pengelola misi. Lihat temuan ketidaksesuaian di
  bagian 5.

### 3.7 `src/amr_core/mission.py` (diubah — tambahan Phase 2)

- **File:** `src/amr_core/mission.py`
- **Jenis perubahan:** diubah (modified, belum di-commit). +96 baris, −0.
- **Sebelum:** hanya berisi `MissionConfig` (dataclass), `ValidationIssue`,
  `validate_mission`, `_validate_target_order`, `_validate_rack_colors`,
  `is_valid`, dan konstanta `ALLOWED_COLORS`, `SAMPLE_TARGETS`, `SAMPLE_RACKS`,
  `MIN/MAX_TIME_LIMIT_S`. (Dikonfirmasi via `git show HEAD:src/amr_core/mission.py`.)
- **Sesudah:** ditambahkan, di bagian bawah file, tipe misi Phase 2 yang bersifat
  aditif (dinamai komentar "Phase 2 — mission spec"):
  - `KNOWN_SKILLS = ("go_to", "return_home", "wait_for_start")`,
    `SKILLS_REQUIRING_TARGET = ("go_to",)`, `ON_FAIL_SKIP`, `ON_FAIL_FAIL`,
    `ALLOWED_ON_FAIL`, `RETURN_HOME_SKILL`.
  - `StepSpec` (frozen dataclass): `step_id`, `skill`, `timeout_s`, `retry`,
    `on_fail`, `target`.
  - `MissionSpec` (frozen dataclass): `mission_id`, `version`, `time_limit_s`,
    `reserve_for_home_s`, `steps`, `start`; properti `display_name`.
  - `spec_from_config(config, *, default_timeout_s=90.0)`: adaptor kompatibilitas
    yang mengubah `MissionConfig` (Phase 1) menjadi `MissionSpec` yang dapat
    dijalankan runner (urutan target menjadi langkah `go_to`, ditutup
    `return_home`).
  - `MissionConfig` dan validator Phase 1 tidak diubah.
- **Alasan:** menyediakan bentuk terurai (parsed) misi yang dikonsumsi runner
  tanpa mengubah model konfigurasi Phase 1 yang dipakai draft dashboard.
- **Dampak terhadap sistem:** `amr_core` kini mengekspor tipe misi Phase 2;
  `SimulationEngine` dan `runtime.py` memakai `spec_from_config` untuk memulai
  runner. Tidak ada perubahan perilaku pada `MissionConfig`/validasi Phase 1.
- **Referensi PRD/arsitektur:** PRD MIS-02, MIS-05; Arsitektur "Skema
  konfigurasi".
- **Verifikasi:** diimpor dan diuji lewat `tests/test_mission_loader.py`,
  `test_mission_runner.py`, `test_engine_runner_integration.py`,
  `test_dashboard_mission_log.py`, `test_runtime.py` — semuanya lulus.
- **Status:** lulus (tes unit). Belum diuji pada robot fisik.

### 3.8 `src/amr_core/simulation.py` (diubah — integrasi runner)

- **File:** `src/amr_core/simulation.py`
- **Jenis perubahan:** diubah (modified, belum di-commit). +50 baris, −3.
- **Sebelum:** `SimulationEngine` memajukan misi sendiri di `tick(dt_s)` dengan
  pola sintetis: `step_duration = max(2.0, time_limit_s / (total_steps * 8))`,
  menambah `history`, dan `DONE` bila semua langkah selesai. Tidak ada runner.
  (Dikonfirmasi via `git show HEAD:...`.)
- **Sesudah:** ditambahkan atribut `runner: object | None = None` dan metode:
  - `attach_runner(runner)` — melampirkan runner; `tick` lalu mendelegasikan.
  - `_start_runner(mission)` — membangun `spec_from_config(mission)`, memanggil
    `runner.configure(spec)` lalu `runner.start(0.0)`.
  - `_abort_runner(reason)` — memanggil `runner.abort(reason)` lalu
    `runner.reset()` bila runner punya state.
  - `_step_runner(dt_s)` — menambah `elapsed_s`, memanggil
    `runner.step_once(elapsed_s)`, dan memetakan hasil `DONE`/`FAIL` ke
    `complete_mission()`/`fail_mission()`.
  Perubahan pada jalur yang ada:
  - `start_mission()` memanggil `self._start_runner(mission)` setelah START.
  - `reset()` memanggil `self._abort_runner("reset")` sebelum menyelesaikan
    transisi.
  - `tick()`: bila ada runner dan terdeteksi kegagalan komponen kritis, memanggil
    `self.runner.abort(f"health:{names}")` sebelum `_apply(HEALTH_FAILED)`;
    bila tidak ada kegagalan, mendelegasikan ke `_step_runner(dt_s)` dan keluar
    lebih awal. Jalur sintetis lama tetap dipertahankan sebagai fallback saat
    `runner is None` (kompatibilitas Phase 1).
- **Alasan:** memisahkan tanggung jawab — engine tetap pemilik state aplikasi,
  runner pemilik urutan misi. Menjaga kompatibilitas versi lama (tes Phase 1
  tetap lulus tanpa runner).
- **Dampak terhadap sistem:** saat runner terlampir (jalur dashboard),
  kemajuan misi, retry, timeout, dan reserve dikendalikan runner. Jalur tanpa
  runner tetap berperilaku seperti Phase 1.
- **Referensi PRD/arsitektur:** PRD MIS-04, MIS-05, OPS-11; Arsitektur "State
  machine operasional" (RUNNING → FAILED saat komponen kritis gagal) dan
  skenario #3/#4.
- **Verifikasi:** `python -m pytest tests/test_engine_runner_integration.py
  tests/test_simulation.py tests/test_stabilization.py -q` — lulus (termasuk
  jalur warisan tanpa runner dan pemetaan kegagalan misi ke state FAILED).
- **Temuan audit terkeit (belum diperbaiki, lihat bagian 5.1):** abort runner
  pada kegagalan kesehatan **runtime** hanya terjadi di jalur `tick`, bukan di
  jalur `apply_health`. Ini menyebabkan skill aktif tidak dibatalkan pada jalur
  yang dipakai tombol health di mode Development.
- **Status:** lulus untuk tes yang ada, tetapi ada **cacat perilaku** yang perlu
  ditambahkan tesnya (bagian 5.1).

### 3.9 `src/amr_dashboard/app.py` (diubah — refresh-only + log misi)

- **File:** `src/amr_dashboard/app.py`
- **Jenis perubahan:** diubah (modified, belum di-commit). +63 baris, −19.
- **Sebelum:** `DashboardState` membuat `SimulationEngine(auto_check=False)`
  sendiri (engine per halaman). `TICK_INTERVAL_S = 0.5`, `TICK_DT_S = 2.0`.
  `_on_tick` memanggil `state.engine.run_health_check()` dan
  `state.engine.tick(TICK_DT_S)` — jadi timer per halaman memajukan simulasi.
  Tidak ada log misi terstruktur. (Dikonfirmasi via `git show HEAD:...`.)
- **Sesudah:**
  - `DashboardState` memakai `get_runtime()` proses; `self.engine =
    runtime.engine`, `self.runner = runtime.runner`. Dua halaman berbagi engine
    dan runner yang sama.
  - Konstanta `TICK_DT_S` dihapus; `TICK_INTERVAL_S = 0.5` kini hanya interval
    penyegaran tampilan per halaman.
  - `_on_tick` tidak lagi memanggil `engine.tick()`/`runtime.step()`; hanya
    menyegarkan region baca-saja (`monitor.refresh()`, `mission_panel.refresh()`,
    `mission_log.refresh()`) dan menambah event log. Komentar menegaskan aturan
    "REFRESH ONLY".
  - Ditambahkan region `mission_log` (`ui.refreshable`) dan fungsi
    `_render_mission_log(state)` yang menampilkan "Structured mission log" lewat
    `panels.mission_log_panel(mission_status(state.engine.runner))`.
  - Tombol "Pause simulated run" berganti menjadi "Pause display refresh"
    (hanya menghentikan penyegaran tampilan browser ini; misi tetap berjalan di
    server).
  - Ditambahkan `_start_runtime_loop`/`_stop_runtime_loop` yang didaftarkan lewat
    `app.on_startup`/`app.on_shutdown` → memulai/menghentikan loop server
    tunggal.
- **Alasan:** DASH-06 (putus koneksi dashboard tidak memengaruhi run) dan
  DASH-16 (hanya satu sesi pengendali; perangkat lain hanya membaca) — meski
  DASH-16 belum sepenuhnya; serta menyediakan log misi terstruktur (MIS-08,
  DASH-09).
- **Dampak terhadap sistem:** perilaku runtime berubah: kemajuan tidak lagi
  bergantung pada halaman; menambah browser tidak menambah laju. Tampilan
  sekarang menampilkan struktur log misi. Ini perubahan antarmuka (label tombol)
  dan perilaku (sumber kemajuan).
- **Referensi PRD/arsitektur:** PRD DASH-06, DASH-09, DASH-16, MIS-08;
  Arsitektur "Fitur operator" (monitor run baca-saja) dan skenario #10.
- **Verifikasi:** `python -m pytest tests/test_dashboard_refresh_only.py
  tests/test_dashboard_mission_log.py tests/test_ux_traceability.py
  tests/test_mission_draft.py -q` — lulus. `tests/test_dashboard_refresh_only.py`
  memakai inspeksi AST untuk membuktikan `_on_tick` dan `main_page` tidak
  memanggil `*.step`/`*.tick`.
- **Status:** lulus (tes unit + inspeksi AST). Belum diuji dengan browser nyata
  (tidak ada tes E2E browser).

### 3.10 `src/amr_dashboard/panels.py` (diubah — panel log misi)

- **File:** `src/amr_dashboard/panels.py`
- **Jenis perubahan:** diubah (modified, belum di-commit). +31 baris, −0.
- **Sebelum:** hanya berisi helper tampilan Phase 1 (banner, indikator koneksi,
  indikator state, checklist kesehatan, ringkasan misi, progress, event log,
  `append_events`). Tidak ada yang merender log misi terstruktur.
  (Dikonfirmasi via `git show HEAD:...`.)
- **Sesudah:** ditambahkan fungsi `mission_log_panel(status: MissionStatus | None)`
  yang merender satu baris per `StepLogRecord` (step id, skill, attempt, outcome,
  reason, durasi, penanda `[incomplete]`) dan menangani `status is None` dengan
  pesan "No mission runner attached (legacy simulation path).". Import
  `MissionStatus` ditambahkan.
- **Alasan:** DASH-09 (monitor run baca-saja: hasil per langkah) dan MIS-08 (log
  misi berisi langkah, hasil, alasan, waktu).
- **Dampak terhadap sistem:** komponen tampilan baru; tidak mengubah logika
  misi. UI tetap baca-saja.
- **Referensi PRD/arsitektur:** PRD DASH-09, MIS-08; Arsitektur "Fitur operator".
- **Verifikasi:** `python -m pytest tests/test_dashboard_mission_log.py -q` —
  lulus, termasuk `mission_log_panel(None)` tidak melempar.
- **Status:** lulus (tes unit). Belum diuji dengan render browser nyata.

### 3.11 `src/amr_core/__init__.py` (diubah — ekspor Phase 2)

- **File:** `src/amr_core/__init__.py`
- **Jenis perubahan:** diubah (modified, belum di-commit). +31 baris, −1.
- **Sebelum:** meng-import `MissionConfig, ValidationIssue, is_valid,
  validate_mission` dari `mission`, `HealthChangeResult, LogEvent,
  SimulationEngine` dari `simulation`, dan `Action, RobotState,
  TransitionResult, can_edit_mission, transition` dari `states`. `__all__` berisi
  12 nama. (Dikonfirmasi via `git show HEAD:...`.)
- **Sesudah:** menambahkan import `MissionSpec`, `StepSpec`, `spec_from_config`
  (dari `mission`), `load_mission_yaml` (dari `mission_loader`), `MissionRunner`,
  `MissionStatus`, `RunnerOutcome`, `StepLogRecord`, `mission_status` (dari
  `mission_runner`), dan `Skill`, `SkillContext`, `SkillResult`, `SkillStatus`
  (dari `skills`). `__all__` diperluas sesuai.
- **Alasan:** mempermudah impor Phase 2 dari satu tempat dan menandai API publik
  paket `amr_core`.
- **Dampak terhadap sistem:** `import amr_core` kini mengimpor modul Phase 2;
  karena itu file untracked harus ada (lihat catatan 2.2).
- **Referensi PRD/arsitektur:** umum (struktur modul).
- **Verifikasi:** seluruh tes (yang meng-import `amr_core`) lulus: **205 tes
  lulus**.
- **Status:** lulus.

### 3.12 Berkas konfigurasi misi (sudah ada, tidak berubah)

- **File:** `config/missions/modul_E.yaml`, `config/missions/G2.yaml`.
- **Jenis perubahan:** tidak berubah. Kedua file sudah terlacak di commit dasar
  dan berisi komentar bahwa ini adalah contoh data simulasi Phase 1 yang belum
  dibaca dashboard. `modul_E.yaml` cocok dengan skema yang diparse
  `mission_loader` (bersama `G2.yaml` yang memakai ekspresi dinamis dan
  skill yang belum didukung).
- **Referensi:** PRD MIS-02; Arsitektur "Skema konfigurasi".
- **Verifikasi:** `tests/test_mission_loader.py::test_valid_mission_parses`
  memakai teks YAML yang identik dengan `modul_E.yaml`; **lulus**. Catatan:
  belum ada tes yang benar-benar membaca file `config/missions/*.yaml` dari disk
  (`load_mission_yaml` diuji dengan string), sehingga jalur baca-berkas belum
  diuji.
- **Status:** belum diverifikasi untuk jalur baca-berkas.

### 3.13 Berkas tes baru (belum terlacak)

- **File:** `tests/conftest.py` dan 9 file `tests/test_*.py` Phase 2
  (daftar di bagian 2.1).
- **Jenis perubahan:** baru (belum terlacak Git).
- **Sebelum:** tidak ada. Commit dasar hanya punya 7 file tes Phase 1
  (`test_event_retention.py`, `test_mission_config.py`, `test_mission_draft.py`,
  `test_simulation.py`, `test_stabilization.py`, `test_states.py`,
  `test_ux_traceability.py`).
- **Sesudah:** ditambahkan `tests/conftest.py` (fixture `autouse` yang
  memanggil `reset_runtime()` sebelum dan sesudah tiap tes agar singleton
  runtime tidak bocor antar-tes) dan 9 berkas tes Phase 2:
  `test_dashboard_mission_log.py`, `test_dashboard_refresh_only.py`,
  `test_engine_runner_integration.py`, `test_mission_loader.py`,
  `test_mission_runner.py`, `test_runtime.py`, `test_server_loop.py`,
  `test_server_loop_integration.py`, `test_skills_mock.py`.
- **Alasan:** arsitektur prinsip "tes sebagai pagar" (NF-07) dan PLAT-02.
- **Dampak terhadap sistem:** tidak mengubah kode produksi; menambah cakupan
  verifikasi.
- **Referensi PRD/arsitektur:** PRD NF-07, PLAT-02, MIS-*; Arsitektur "Tes
  sebagai pagar".
- **Verifikasi:** seluruh tes lulus — **205 tes lulus dalam 17.95 detik**.
- **Status:** lulus.

---

## 4. Perubahan yang dibuat SELAMA tahap audit ini

### 4.1 `docs/CHANGELOG_DEV.md` (baru)

- **File:** `docs/CHANGELOG_DEV.md`
- **Jenis perubahan:** baru (dibuat pada tahap ini).
- **Sebelum:** tidak ada. Direktori `docs/` belum ada di repository.
- **Sesudah:** dokumen catatan perubahan ini, berisi kondisi Git sebelum/sesudah,
  daftar perubahan yang sudah ada sebelum audit, perubahan baru, temuan
  ketidaksesuaian, hasil tes aktual, serta risiko dan pekerjaan yang belum
  selesai.
- **Alasan:** memenuhi aturan wajib B (catat setiap perubahan) dan output wajib 1.
- **Dampak terhadap sistem:** tidak ada dampak pada kode atau perilaku runtime;
  hanya dokumentasi. Direktori `docs/` yang sebelumnya tidak ada kini dibuat.
- **Referensi PRD/arsitektur:** Arsitektur "Struktur repo" (`docs/`), prinsip #6
  "perubahan kecil dan tercatat".
- **Verifikasi:** file ada di `docs/CHANGELOG_DEV.md`; tidak memengaruhi tes
  (tes tetap lulus setelah dibuat — lihat bagian 6).
- **Status:** lulus (dokumen tersedia).

> Tidak ada file lain yang dibuat, diubah, dihapus, atau dipindahkan selama tahap
> audit ini.

---

## 5. Ketidaksesuaian dan temuan audit

Temuan dicatat di sini; **perbaikan kode dijadwalkan pada tahap berikutnya**
sesuai batas pekerjaan. Setiap temuan disertai bukti dari kode dan/atau
percobaan langsung.

### 5.1 Kegagalan kesehatan saat RUNNING via `apply_health` tidak membatalkan skill

- **Bukti kode:** `SimulationEngine.tick` memanggil `self.runner.abort(...)`
  sebelum transisi ketika mendeteksi komponen kritis gagal. Tetapi
  `SimulationEngine.apply_health` (dipakai tombol health di mode Development
  melalui `app._set_health` → `engine.apply_health`) memanggil
  `_apply(Action.HEALTH_FAILED)` **tanpa** memanggil `abort`/`_abort_runner`.
- **Bukti percobaan:** dengan skill `go_to` berdurasi 999 s aktif, memanggil
  `engine.apply_health("lidar", False)` menghasilkan `engine.state == FAILED`
  tetapi `runner.state == RUNNING` dan `sk["go_to"].cancelled == False`; catatan
  log misi kosong. Sebaliknya, jalur yang terdeteksi di dalam `tick`
  menghasilkan `runner.state == FINISHED`, `go_to.cancelled == True`.
- **Dampak:** pada jalur yang benar-benar dipakai UI (sakelar health), skill
  tetap "berjalan" di runner setelah misi FAILED; kontrak arsitektur ("Saat
  dibatalkan, skill wajib mengirim kecepatan nol sebelum keluar" dan "batal
  sebelum transisi") tidak dipenuhi pada jalur ini. Tes yang ada
  (`test_health_failure_during_run_cancels_skill_and_fails`) hanya menguji jalur
  `tick`/nama tes menyiratkan cancel, tetapi tidak menguji jalur `apply_health`,
  sehingga cacat ini tidak tertangkap.
- **Referensi:** PRD OPS-11; Arsitektur "State machine operasional" dan
  "Skenario kegagalan"; catatan kontrak skill.
- **Usulan perbaikan (tahap berikutnya):** perlakukan jalur `apply_health`
  seperti jalur `tick`: saat transisi RUNNING → FAILED karena komponen kritis,
  panggil `runner.abort(...)` sebelum `_apply`, dan tambahkan tes regresi yang
  menguji jalur `apply_health` untuk cancel skill + `runner.state == FINISHED`.

### 5.2 Struktur modul berbeda dari arsitektur

- **Bukti:** arsitektur menyebut paket `src/amr_skills/` (satu modul per skill),
  `src/amr_mission/` (pengelola misi + state machine), `src/amr_ops/`,
  `src/amr_vision/`, `src/amr_platform_mock/`, `src/amr_bringup/`. Repository
  saat ini menaruh semuanya di dalam `src/amr_core/` (`mission.py`,
  `mission_loader.py`, `mission_runner.py`, `skills.py`, `mock_platform.py`,
  `simulation.py`, `states.py`, `vision.py`, `interfaces.py`) dan
  `src/amr_dashboard/`.
- **Dampak:** penamaan modul tidak mengikuti peta struktur repo arsitektur;
  pengembangan berikutnya berisiko menyimpang semakin jauh bila tidak
  diklarifikasi. Belum tentu salah (prototipe boleh menyederhanakan), tetapi
  perlu dicatat sebagai utang arsitektur.
- **Referensi:** Arsitektur "Struktur repo" dan "Katalog skill".
- **Usulan:** putuskan apakah akan memetakan ulang ke struktur arsitektur
  (mis. `amr_mission`, `amr_skills`) atau mencatat penyederhanaan ini sebagai
  keputusan (ADR) sebelum menambah skill/misi baru.

### 5.3 `MissionStatus.active_step_id` dan pengintaian `runner._active` yang privat

- **Bukti:** `mission_status()` membaca `runner._active` (atribut privat) untuk
  view model. Ini pelanggaran enkapsulasi ringan; bila runner berubah, dashboard
  ikut rusak tanpa peringatan tipe.
- **Dampak:** kerapuhan pemeliharaan, bukan bug fungsional saat ini.
- **Referensi:** PRD DASH-09; Arsitektur "pengelola misi" sebagai pemilik state.
- **Usulan:** sediakan properti publik baca-saja (mis. `active_step`) pada
  `MissionRunner` dan pakai itu.

### 5.4 `wait_for_start` terdaftar sebagai skill tapi tidak berfungsi

- **Bukti:** `KNOWN_SKILLS` dan `default_skill_factory()` mendaftarkan
  `wait_for_start`, tetapi tidak ada langkah misi yang memakainya dan
  `scripts`/runner tidak menangani "menunggu tombol". Arsitektur menyatakan
  `wait_for_start` "menunggu tanpa batas di READY".
- **Dampak:** skill ada di katalog tapi belum berfungsi; berpotensi
  disalahpahami sebagai sudah selesai.
- **Referensi:** PRD MIS-01; Arsitektur "Katalog skill".
- **Usulan:** tandai jelas sebagai placeholder atau implementasikan pada tahap
  yang sesuai.

### 5.5 Fitur dashboard PRD yang belum ada (parsial)

- **DASH-13 (PIN mode Pengembangan) dan DASH-16 (satu sesi pengendali)**:
  pencarian string di `app.py` tidak menemukan "PIN"/"session"/"read-only
  session". Mode saat ini hanya `state.mode` per halaman; tidak ada penguncian
  sesi pengendali. Verifikasi: inspeksi `inspect.getsource(dash)`.
- **DASH-01/DASH-04**: mode Lomba/Development ada, dan mode Lomba tanpa kontrol
  gerak tampak terpenuhi (tombol START/RESET diberi label "Simulate ...", hanya
  di sisi simulasi). Namun penguncian mode Lomba (DASH-13) belum ada.
- **Dampak:** sebagian kebutuhan dashboard masih "belum ada", bukan "lulus".
- **Referensi:** PRD DASH-01, DASH-04, DASH-13, DASH-16.
- **Usulan:** jadwalkan pada tahap dashboard berikutnya; jangan tandai lulus
  tanpa implementasi + tes.

### 5.6 `status()` mengembalikan `MissionStatus` yang menghitung `records` tuple

- Catatan kecil: `MissionStatus.records` adalah tuple yang disalin dari daftar
  setiap kali `mission_status()` dipanggil (dipanggil di setiap refresh). Untuk
  misi kecil ini tidak masalah; untuk misi panjang berpotensi menyalin banyak.
  Dicatat sebagai risiko skalabilitas rendah.

---

## 6. Hasil verifikasi aktual (dijalankan pada tahap ini)

Lingkungan: Windows, shell bash, Python 3.12.4 di
`C:\Users\Satria\AppData\Local\Programs\Python\Python312`. **Tidak ada
virtual environment proyek** (`venv`/`.venv`) di repository; dependensi terpasang
di Python sistem. Versi terpasang: `nicegui 3.18.0`, `pytest 9.1.1`, `pyyaml`,
`ruff` tersedia. `requirements.txt` membatasi `nicegui>=2.0,<4.0` (cocok dengan
3.18.0). `pyproject.toml` menetapkan `pythonpath=["src"]` dan `testpaths=["tests"]`.

| Perintah | Tujuan | Hasil aktual | Status |
| --- | --- | --- | --- |
| `python -m pytest -q` | Seluruh tes otomatis | `205 passed in 17.95s` | lulus |
| `python -m ruff check .` | Lint (E, F, I, UP, B) | `All checks passed!` (exit 0) | lulus |
| `python scripts/smoke_dashboard.py` | Smoke test dashboard (server + GET `/`) | exit 0 (server siap di `127.0.0.1:8077`) | lulus |
| Probe HTTP manual (venv python) | Konfirmasi HTTP 200 pada `/` | `HTTP_STATUS 200`, returncode 0 | lulus |

Catatan kejujuran hasil:

- Baris `SMOKE: GET / -> HTTP 200` dari `scripts/smoke_dashboard.py` tidak
  selalu tercetak karena `os._exit(0)` dijalankan dari thread daemon sebelum
  flush `print` selesai. **Exit code 0** adalah sinyal lulus (skrip hanya keluar
  0 bila status HTTP == 200). Probe HTTP tambahan (di atas) mencetak
  `HTTP_STATUS 200` secara eksplisit, sehingga bukti tidak bergantung pada baris
  `SMOKE:` yang hilang.
- **Belum ada uji di robot fisik.** Tidak ada klaim tes robot fisik berhasil.
  Modul `runtime.py` secara eksplisit menyatakan belum divalidasi di
  Raspberry Pi 5. Semua tes di atas adalah tes unit/integrasi di komputer
  pengembangan dengan platform simulasi (`mock`).
- Kegagalan lingkungan pengujian tidak ditemukan (tidak ada dependensi hilang).

Cakupan tes (205 total): 7 file tes Phase 1 (event retention, mission config,
mission draft, simulation, stabilization, states, ux traceability) + 9 file tes
Phase 2 (dashboard mission log, dashboard refresh only, engine-runner
integration, mission loader, mission runner, runtime, server loop, server loop
integration, skills mock) + `conftest.py` (fixture autouse).

---

## 7. Fitur: sudah diimplementasikan / parsial / belum ada

Penilaian berikut berdasarkan bukti kode + tes, bukan hanya nama modul. Kode
PRD yang dirujuk adalah kode kebutuhan (bukan status kelulusan resmi).

| Kebutuhan | Status | Bukti |
| --- | --- | --- |
| MIS-02 pemuat + validator YAML | **sudah** (unit) | `mission_loader.py` + `test_mission_loader.py` (16 tes) |
| MIS-03 urutan target dari acakan tanpa ubah kode | **parsial** | Urutan dari `samples.py`/draft; YAML belum dihubungkan ke runtime dashboard |
| MIS-04 reserve → return_home | **sudah** (unit) | `mission_runner._enter_return_home` + tes reserve |
| MIS-05 timeout + retry + skip/fail per langkah | **sudah** (unit) | `mission_runner` + tes retry/timeout/on_fail |
| MIS-06 ekspresi dinamis G2 | **belum** | `mission_loader` justru *menolak* ekspresi dinamis (sesuai catatan; belum ada evaluator fungsi terdaftar) |
| MIS-07 RESET → READY + pose awal | **parsial** | `reset()` mengembalikan READY; "pose ke home" hanya pesan log simulasi |
| MIS-08 log misi + ros2 bag | **parsial** | Log misi terstruktur ada (`StepLogRecord`, panel); `ros2 bag` belum ada |
| OPS-11 pantau laju data saat run | **parsial** | Kegagalan komponen kritis -> FAILED ada; pemantauan laju data sensor belum ada; jalur `apply_health` tidak membatalkan skill (5.1) |
| DASH-01 dua mode | **parsial** | Mode ada; penguncian mode Lomba (DASH-13) belum |
| DASH-04 tanpa tombol gerak di mode Lomba | **sudah** (inspeksi) | Tombol hanya "Simulate START/RESET"; tidak ada teleop |
| DASH-05 edit terkunci saat RUNNING | **sudah** (unit) | `can_edit_mission` + `test_mission_draft.py` |
| DASH-06 putus koneksi tidak memengaruhi run | **sudah** (unit+integrasi) | `runtime.py` loop server tunggal + `test_server_loop_integration.py` |
| DASH-09 monitor run baca-saja + hasil per langkah | **sudah** (unit) | `panels.mission_log_panel` + `test_dashboard_mission_log.py` |
| DASH-13 PIN mode Pengembangan | **belum** | Tidak ada "PIN" di `app.py` |
| DASH-16 satu sesi pengendali | **belum** | Tidak ada mekanisme sesi di `app.py` |
| PLAT-02 platform mock untuk tes tiap commit | **sudah** (unit) | `mock_platform.py` + `test_skills_mock.py` |
| Kontrak 4 hasil skill (SUCCESS/FAILURE/TIMEOUT/ABORTED) | **sudah** (unit) | `skills.py` + tes |

---

## 8. Risiko dan pekerjaan yang belum selesai

1. **Cacat abort kesehatan via `apply_health`** (5.1) — risiko: skill tidak
   dibatalkan pada jalur UI health; perlu tes regresi. **Belum diperbaiki**.
2. **Working tree tidak dapat dipisah dari file untracked** — `__init__.py` dan
   `app.py` meng-import modul untracked; jangan buang/move file tanpa
   memperbarui ini. **Belum di-commit** (sesuai aturan tahap ini).
3. **YAML misi belum dihubungkan ke runtime dashboard** — `mission_loader`
   diuji dengan string; `config/missions/*.yaml` belum dibaca. Misi dashboard
   masih dari `samples.py` + `spec_from_config`. **Belum**.
4. **Belum ada validasi di Raspberry Pi/LanderPi** — `runtime.py` menyatakannya
   eksplisit; semua tes di komputer pengembangan.
5. **Struktur modul ≠ struktur arsitektur** (5.2) — utang arsitektur.
6. **Fitur dashboard PRD belum lengkap** (DASH-13, DASH-16, sebagian DASH-01) —
   lihat 5.5.
7. **`wait_for_start` dan G2 (`detect_object`, `pick`, `place`, `align_reference_line`)
   belum ada** sebagai skill; misi G2 saat ini tidak dapat dijalankan runner
   (validator akan menolak sebagian skill/ekspresinya).
8. **Tidak ada tes E2E browser** — tes dashboard memakai AST dan helper, bukan
   browser nyata; label tombol dan render aktual belum diverifikasi secara visual.
9. **Tidak ada virtual environment proyek** — tes berjalan di Python sistem;
   reproduksibilitas lingkungan bergantung pada pemasangan global.

---

## 9. Verifikasi akhir kondisi Git

Setelah pekerjaan ini: branch `main`, HEAD `9df1632` (tidak berubah). 5 file
modified dan 15 file untracked tetap utuh. Tambahan hanya
`docs/CHANGELOG_DEV.md`. Tidak ada commit, push, reset, clean, atau ganti branch.

---

# Tahap 2 — Perbaikan Cacat Abort Kesehatan (`apply_health`) + Tes Regresi

Bagian di atas (Tahap 1) mendokumentasikan audit dan perubahan lokal yang sudah
ada. Bagian Tahap 2 ini mendokumentasikan **pekerjaan baru** yang dilakukan
setelah audit. Semua perubahan Tahap 2 dicatat di sini; bagian Tahap 1 **tidak
ditulis ulang**.

## 10. Ringkasan Tahap 2

Tujuan tunggal: memperbaiki cacat temuan audit bagian 5.1 — saat
`SimulationEngine.apply_health()` mendeteksi komponen kritis gagal ketika misi
sedang RUNNING, engine berpindah ke FAILED tetapi **skill aktif pada
`MissionRunner` tidak dibatalkan**. Jalur `tick()` sudah benar; jalur
`apply_health()` (yang dipakai oleh sakelar health di dashboard mode Development
lewat `app._set_health`) belum.

Batasan yang dipatuhi:

- Tidak ada `git reset --hard`, `git clean`, commit, push, atau ganti branch.
- Tidak ada file lama yang dihapus atau ditimpa.
- Tidak ada refactor besar atau pemindahan modul.
- Tidak ada temuan audit lain yang ikut diperbaiki pada tahap ini.
- Perilaku jalur `tick()` tidak diubah (hanya dijadikan acuan konsistensi).

Hasil: 2 file diubah pada Tahap 2 —
`src/amr_core/simulation.py` (perbaikan) dan
`tests/test_engine_runner_integration.py` (4 tes regresi baru) — serta file
dokumen ini (`docs/CHANGELOG_DEV.md`).

## 11. Perubahan file pada Tahap 2

### 11.1 `src/amr_core/simulation.py` (diubah pada Tahap 2)

- **File:** `src/amr_core/simulation.py`
- **Jenis perubahan:** diubah (modified). Catatan: file ini **sudah** modified
  sebelum Tahap 2 karena integrasi runner Phase 2 (lihat bagian 3.8). Tahap 2
  menambah satu perubahan kecil di dalam `apply_health()`.
- **Sebelum (kondisi pada awal Tahap 2):** pada `apply_health()`, saat
  `self.state is not RobotState.BOOT and not ok and item.critical`, kode
  langsung memanggil `result = self._apply(Action.HEALTH_FAILED)` tanpa
  membatalkan runner. Akibatnya, meski engine berpindah RUNNING → FAILED,
  skill aktif tetap berjalan dan `runner.state` tetap `RUNNING`.
- **Sesudah (perubahan Tahap 2):** ditambahkan, tepat sebelum
  `self._apply(Action.HEALTH_FAILED)`, blok berikut:

  ```python
  if self.state is RobotState.RUNNING and self.runner is not None:
      failures = self._critical_failures()
      names = ", ".join(h.label for h in failures)
      self.runner.abort(f"health:{names}")
  ```

  Penjelasannya:
  - Nama komponen dihitung dengan cara **yang sama** dengan jalur `tick()`
    (`self._critical_failures()` lalu `", ".join(h.label ...)`), sehingga pesan
    alasan konsisten (`aborted:health:LiDAR`).
  - Guard `self.state is RobotState.RUNNING` memastikan abort hanya terjadi pada
    transisi RUNNING → FAILED (OPS-11). Untuk transisi pra-run
    (READY/BOOT → FAULT, OPS-02) tidak ada misi yang berjalan, jadi tidak perlu
    abort.
  - Guard `self.runner is not None` mempertahankan perilaku engine tanpa runner.
  - Guard RUNNING juga membuat jalur ini **idempoten terhadap abort ganda**:
    setelah state menjadi FAILED, panggilan `apply_health` berikutnya tidak lagi
    memenuhi syarat RUNNING sehingga `abort` tidak dipanggil ulang.
  - Memakai API `MissionRunner.abort()` yang sudah ada, bukan mengubah
    `runner.state` langsung, sehingga skill aktif menerima `cancel()`.
- **Alasan teknis:** menutup celah konsistensi antara `tick()` dan
  `apply_health()`; menegakkan kontrak arsitektur "saat dibatalkan, skill wajib
  berhenti" dan "batalkan sebelum transisi".
- **Dampak terhadap perilaku sistem:** pada jalur UI health (mode Development),
  kegagalan komponen kritis saat RUNNING kini benar-benar menghentikan skill
  aktif dan mengakhiri runner (FINISHED). Jalur `tick()`, kondisi nonkritis,
  transisi lain, dan engine tanpa runner **tidak berubah**.
- **Referensi PRD/arsitektur:** PRD **OPS-11** (komponen kritis gagal saat run →
  robot berhenti, misi FAILED), didukung **MIS-05**; Arsitektur "State machine
  operasional" (RUNNING → FAILED) dan kontrak skill katalog.
- **Verifikasi:** `python -m pytest tests/test_engine_runner_integration.py -q`
  → **12 lulus**; suite penuh → **209 lulus**. Lihat bagian 12.
- **Status:** lulus (tes otomatis). Belum diverifikasi di robot fisik.

### 11.2 `tests/test_engine_runner_integration.py` (diubah pada Tahap 2)

- **File:** `tests/test_engine_runner_integration.py`
- **Jenis perubahan:** diubah (modified). Catatan: file ini **belum terlacak Git**
  (untracked) sebelum Tahap 2; Tahap 2 menambahkan tes ke dalamnya. Karena belum
  terlacak, ia tetap muncul sebagai untracked.
- **Sebelum (kondisi pada awal Tahap 2):** berisi 8 tes. Tes yang ada untuk
  kegagalan kesehatan, `test_health_failure_during_run_cancels_skill_and_fails`,
  **hanya** memanggil `engine.tick(1.0)` lalu `engine.apply_health("lidar",
  False)` — dan hanya meng-assert `engine.state is RobotState.FAILED`. Karena
  `apply_health` tidak membatalkan apa pun, tes itu lulus tanpa membuktikan
  pembatalan skill. Import `RunnerState` belum ada.
- **Sesudah (perubahan Tahap 2):** import diubah menjadi
  `from amr_core.mission_runner import MissionRunner, RunnerState, mission_status`.
  Ditambahkan 4 tes regresi baru di akhir file:
  1. `test_apply_health_aborts_active_skill_and_finishes_runner` — memulai misi
     dengan skill `go_to` berdurasi 999 s (belum selesai alami), mengaktifkannya
     via `tick(1.0)`, lalu memanggil `engine.apply_health("lidar", False)`.
     Meng-assert: `engine.state is FAILED`, `runner.state is RunnerState.FINISHED`,
     `go_to.cancelled is True`, dan `runner.terminal_reason ==
     "aborted:health:LiDAR"`. Ini membuktikan pembatalan lewat `runner.abort()`,
     bukan sekadar perubahan state engine.
  2. `test_apply_health_non_critical_keeps_runner_running` — `battery` (nonkritis)
     gagal: `engine.state is RUNNING`, `runner.state is RUNNING`, skill tidak
     dibatalkan (perilaku lama terjaga).
  3. `test_apply_health_critical_without_runner_unaffected` — engine tanpa runner:
     `apply_health("lidar", False)` dari READY → FAULT, tidak ada runner yang
     tersentuh (perilaku lama terjaga).
  4. `test_apply_health_critical_repeated_does_not_double_abort` — kegagalan
     kritis kedua (`camera`) saat engine sudah FAILED tidak mengubah
     `terminal_reason` (guard RUNNING membuat abort tidak terpanggil lagi).
- **Alasan teknis:** menutup celah pengujian yang membuat cacat 5.1 tidak
  tertangkap; mengunci perilaku baru agar tidak regresi.
- **Dampak terhadap perilaku sistem:** tidak mengubah kode produksi; menambah
  cakupan verifikasi (dari 205 menjadi 209 tes).
- **Referensi PRD/arsitektur:** PRD OPS-11, MIS-05, NF-07 (tes sebagai pagar);
  Arsitektur "Tes sebagai pagar".
- **Verifikasi:** `python -m pytest tests/test_engine_runner_integration.py -q`
  → **12 lulus** (8 lama + 4 baru). Lihat bagian 12.
- **Status:** lulus (tes otomatis). Tidak menguji robot fisik.

### 11.3 `docs/CHANGELOG_DEV.md` (diubah pada Tahap 2)

- **File:** `docs/CHANGELOG_DEV.md`
- **Jenis perubahan:** diubah (ditambahkan Bagian "Tahap 2", yaitu bagian 10–16
  ini) pada Tahap 2. File ini dibuat pada Tahap 1 (bagian 4.1).
- **Sebelum:** berisi 9 bagian audit Tahap 1 sampai baris 689.
- **Sesudah:** ditambahkan catatan Tahap 2 (ringkasan, perubahan per file,
  verifikasi, kondisi Git, batas validasi, status akhir) tanpa mengubah isi
  Tahap 1.
- **Alasan teknis:** memenuhi aturan pencatatan wajib setiap perubahan.
- **Dampak terhadap perilaku sistem:** tidak ada; hanya dokumentasi.
- **Referensi PRD/arsitektur:** Arsitektur prinsip #6 "perubahan kecil dan
  tercatat".
- **Verifikasi:** file dapat dibuka dan memuat bagian Tahap 2 ini. Tidak
  memengaruhi tes (suite tetap lulus setelah pembaruan — lihat 12.3).
- **Status:** lulus (dokumen tersedia).

## 12. Verifikasi aktual (Tahap 2)

Lingkungan: Windows, shell bash, Python 3.12.4 (`python` sistem; tidak ada
virtual environment proyek). `nicegui 3.18.0`, `pytest 9.1.1`. Tidak ada
kegagalan dependensi/lingkungan.

### 12.1 Perintah dan hasil

| Perintah | Tujuan | Hasil aktual | Status |
| --- | --- | --- | --- |
| `python -m pytest tests/test_engine_runner_integration.py -q` | Tes regresi baru + tes integrasi engine-runner | `12 passed in 0.30s` | lulus |
| `python -m pytest tests/test_engine_runner_integration.py tests/test_mission_runner.py tests/test_simulation.py tests/test_stabilization.py tests/test_skills_mock.py -q` | Tes terkait engine, runner, dan health failure | `72 passed in 4.10s` | lulus |
| `python -m pytest -q` | Seluruh suite | `209 passed in 20.66s` | lulus |
| `python -m ruff check .` | Lint (E, F, I, UP, B) | `All checks passed!` (exit 0) | lulus |
| `python scripts/smoke_dashboard.py` | Smoke test dashboard | exit code `0` (sinyal HTTP 200) | lulus |
| Probe HTTP manual | Konfirmasi eksplisit status `/` | `HTTP_STATUS 200`, returncode 0 | lulus |

### 12.2 Bukti sebelum/sesudah perbaikan (probe langsung)

Probe langsung (di luar pytest) dengan skill `go_to` berdurasi 999 s aktif:

- **Sebelum perbaikan:** `engine.state == FAILED`, tetapi
  `runner.state == RUNNING` dan `sk["go_to"].cancelled == False`, `records == []`.
- **Sesudah perbaikan:** `engine.state == FAILED`,
  `runner.state == RunnerState.FINISHED`, `sk["go_to"].cancelled == True`,
  `terminal_reason == "aborted:health:LiDAR"`.

### 12.3 Catatan kejujuran hasil

- Baris `SMOKE: GET / -> HTTP 200` dari `scripts/smoke_dashboard.py` kadang tidak
  tercetak karena proses keluar lewat `os._exit(0)` di thread daemon sebelum
  `print` ter-flush. **Exit code 0** adalah sinyal lulus (skrip hanya keluar 0
  bila status HTTP == 200). Probe HTTP manual mencetak `HTTP_STATUS 200` secara
  eksplisit, sehingga bukti tidak bergantung pada baris yang hilang itu.
- Jumlah tes naik dari 205 (baseline Tahap 1) menjadi 209 (Tahap 2), sesuai
  penambahan 4 tes regresi. Tidak ada tes lama yang diubah ekspektasinya.

## 13. Kondisi Git (Tahap 2)

- **Sebelum Tahap 2:** branch `main`, HEAD `9df1632`. 5 file modified
  (`__init__.py`, `mission.py`, `simulation.py`, `app.py`, `panels.py`),
  16 entri untracked (15 file + `docs/`).
- **Sesudah Tahap 2:** branch `main`, HEAD `9df1632` (**tidak berubah**).
  5 file modified (daftar sama; `simulation.py` kini punya perubahan tambahan
  Tahap 2), 16 entri untracked (daftar sama; `test_engine_runner_integration.py`
  kini punya tambahan tes Tahap 2).
- Tidak ada commit, push, reset, clean, atau ganti branch.
- **Perubahan lama (pra-audit) tetap terjaga:** 5 file modified dan 15 file
  untracked dari Tahap 1 utuh.
- **Perubahan baru Tahap 2:** isi tambahan pada `src/amr_core/simulation.py`,
  `tests/test_engine_runner_integration.py`, dan `docs/CHANGELOG_DEV.md`.

## 14. Batas validasi

Seluruh verifikasi Tahap 2 adalah **tes otomatis** pada simulasi (`mock`) di
komputer pengembangan. Ini **bukan bukti** bahwa robot fisik telah berhenti
dengan aman: tidak ada perangkat keras, ROS 2, aktuator, atau e-stop fisik yang
diuji. Klaim keamanan fisik apa pun memerlukan uji di robot (protokol R pada
PRD) dan belum dilakukan.

## 15. Risiko dan pekerjaan yang belum selesai (setelah Tahap 2)

1. **Verifikasi robot fisik** untuk OPS-11 dan perilaku pembatalan skill —
   belum dilakukan (di luar cakupan tahap ini).
2. Temuan audit lain (bagian 5.2–5.6) **sengaja belum diperbaiki** sesuai batas
   tahap: struktur modul, pembacaan atribut privat `runner._active`,
   `wait_for_start`, DASH-13/DASH-16, dan lain-lain.
3. Working tree tetap tidak dapat dipisahkan dari file untracked (belum
   di-commit, sesuai aturan).

## 16. Status akhir Tahap 2

- [x] Jalur `apply_health()` membatalkan skill aktif sebelum transisi ke FAILED.
- [x] Tes regresi memverifikasi pembatalan skill (`go_to.cancelled is True` dan
      `runner.state is FINISHED`), bukan hanya perubahan state engine.
- [x] Tes relevan lulus (12 pada file tes integrasi; 72 pada kelompok terkait).
- [x] Seluruh suite (`209 passed`) dan Ruff (`All checks passed!`) dijalankan.
- [x] Smoke test dijalankan (exit 0; HTTP 200 dikonfirmasi eksplisit).
- [x] `docs/CHANGELOG_DEV.md` mencatat seluruh perubahan Tahap 2.
- [x] Perubahan lokal sebelumnya tetap terjaga.
- [x] Tidak ada commit, push, reset, clean, atau pergantian branch.
- [ ] Verifikasi robot fisik — **belum diverifikasi** (di luar cakupan).

## 17. Penurunan batas linear_x setelah audit Sesi 3 (21 Oktober 2026)

Data Sesi 3 hanya menguji sampai `u=1,0` dengan kecepatan lantai terukur
0,19 m/s. Batas default `SpeedLimits.max_linear_x=0.30` karena itu 1,6x di atas
bukti dan diturunkan menjadi `0.19`. Batas `max_linear_y=0.30` dan
`max_angular_z=1.20` tidak diubah karena gerak samping dan putar belum diuji.

- Perubahan: `src/amr_core/robot/safety.py` (`max_linear_x` 0.30 -> 0.19).
- Tes baru: `tests/test_robot_safety.py::test_default_linear_x_cap_matches_tested_speed`.
- Verifikasi: `13 passed` pada tes safety/chassis; `318 passed` pada seluruh suite.
- Tidak ada uji hardware pada perubahan ini; menaikkan kembali ke 0.30 memerlukan
  uji 0,3 m/s di area panjang dengan E-stop.
- Tidak ada commit, push, reset, clean, atau pergantian branch.

## 18. Persiapan Sesi 4 — protokol eksperimen dan alat analisis offline (21 Oktober 2026)

Sesi 3 meninggalkan dua hal terbuka: ketidakpastian `C_eff` (20,72 ± 1,84 cm,
CV 8,9 %) dan pemisahan dua model yang masih hidup — rasio konstan ~0,885 vs
offset jarak tetap ~4,89 cm. Tahap ini **menyiapkan** protokalnya, belum
menghasilkan temuan empiris baru.

**Tidak ada aktuasi pada tahap ini.** Mesin penyusun tidak punya
`/dev/ttyACM0` (Windows) dan akses SSH ke `stematel-pi5` ditolak
(`Permission denied (publickey,password)`). Karena itu seluruh tabel data di
`docs/sesi_4.md` sengaja dikosongkan — isinya menunggu operator di Lander.
Tidak ada angka yang dikira-kira.

- Perubahan (tambahan baru, tanpa file lama yang diubah):
  - `docs/sesi_4.md` — protokol tiga eksperimen, prediksi, aturan keputusan,
    kerangka analisis, lembar catatan, checklist lantai, dan paket perintah.
  - `scripts/analyze_sesi4.py` — alat analisis offline: statistik `C_eff`,
    prediksi kedua model, ambang keputusan 101 cm / 105 cm, uji tanpa-`C_eff`
    (`D = Y9 − 3·Y3`), fit model rasio/offset/gabung dengan residual, rms, dan
    χ², serta laju free-wheel. Skrip tidak membuka port serial dan tidak
    mengirim perintah motor.
  - `tests/test_analyze_sesi4.py` — 15 tes untuk aritmetika di atas. Semua
    data di dalam tes adalah **sintetis**, bukan data sesi.
- Analisis yang sudah dihitung di dokumen (tanpa hardware): dengan `C_eff`
  sesi 3, band 1σ prediksi 9 s saling menimpa (90,2–107,8 cm untuk rasio vs
  97,5–116,5 cm untuk offset), sehingga percobaan 2 hanya bisa memakai
  ambang mutlak itu bila `C_eff` membaik; karena itu ada uji pengganti
  `D = Y9 − 3·Y3` yang tidak bergantung pada `C_eff` sama sekali.
- Verifikasi: `333 passed` pada seluruh suite (318 lama + 15 baru);
  `All checks passed!` untuk Ruff; `git status --short` bersih selain tiga
  berkas baru.
- Batas kecepatan tidak disentuh: `max_linear_x` tetap 0,19 m/s,
  `max_linear_y` 0,30 dan `max_angular_z` 1,20 tidak diubah. Tidak ada uji
  `u > 1,0` maupun 0,30 m/s.
- Tidak ada commit, push, reset, clean, atau pergantian branch.

## 19. Rencana aktivasi chassis langsung dari dashboard (21 Oktober 2026)

Permintaan operator berubah arah: target sesi 4 (memisahkan model rasio vs
offset) diturunkan prioritasnya, karena blocker sebenarnya untuk "robot bisa
digerakkan dari dashboard" adalah **transport**, bukan kalibrasi. Video pun
dibatalkan — video hanya dibutuhkan untuk cabang penjelasan mekanisme
(start delay vs ramp), bukan untuk keputusan rasio-vs-offset.

**Belum ada kode yang ditulis.** Bagian ini hanya rencana untuk review.

- Perubahan:
  - `docs/rencana_chassis_live.md` (baru) — rencana implementasi: lima celah
    yang harus ditutup (transport serial, pemilihan adapter, encoder frame
    motor di `amr_core`, kinematika mecanum, semantik hold-to-move), rancangan
    fail-safe delapan lapis, tahapan P0–P7 dengan gerbang, dan risiko.
  - `docs/robot_integration.md` — penunjuk ke rencana tersebut di §7.
- Keputusan operator yang masuk rencana: **hold-to-move** (bukan klik-sekali)
  dan cakupan **maju/mundur/samping/putar**.
- Temuan yang mengubah rencana: pola tanda untuk **lateral dan putar belum
  pernah diverifikasi** — hanya pola maju yang terverifikasi lewat translasi
  (commit `f8de64e` mengoreksi konvensi lama yang salah karena ditentukan
  dengan roda terangkat). Karena itu identifikasi tanda menjadi **gate G1**
  sebelum ada gerak di lantai dari dashboard.
- Batas yang tidak berubah: `max_linear_x` 0,19 m/s, `max_linear_y` 0,30,
  `max_angular_z` 1,20. Yang boleh diturunkan (bukan dinaikkan) adalah batas
  lateral dan putar, sampai ada pengukuran lantai.
- Verifikasi: `333 passed` pada seluruh suite; `All checks passed!` untuk Ruff.
- Tidak ada aktuasi, tidak ada perubahan pada `src/amr_core/robot/`, tidak ada
  commit, push, reset, clean, atau pergantian branch.

## 20. Jalur dashboard ke robot — P0–P4 dari rencana chassis langsung (21 Oktober 2026)

Rencana ada di `docs/rencana_chassis_live.md`. Tahap ini mengerjakan P0–P4:
seluruhnya **offline**, tanpa robot, tanpa port, dan direview lewat diff.
P5–P7 (gerbang hardware) belum dikerjakan.

**Perubahan kode**

- `src/amr_core/robot/stm32_protocol.py` — menambah `build_motor_frame()`.
  Encoder frame motor sekarang tinggal satu; `scripts/wheel_test.py` memakainya
  juga, jadi skrip dan dashboard tidak bisa berbeda pendapat soal byte.
- `src/amr_core/robot/kinematics.py` (baru) — kinematika invers mecanum:
  (vx, vy, wz) → 4 perintah roda, skala m/s → rps, dan `direction_report()` yang
  menampilkan pola tiap arah dalam bentuk perintah motor.
- `src/amr_core/robot/motion_guard.py` (baru) — fail-safe kontrol tahan-tekan:
  heartbeat klien, lease kendali, latch E-stop software.
- `src/amr_core/robot/serial_chassis.py` (baru) — adapter serial yang
  benar-benar mengirim: thread pemilik port, stream 50 Hz, frame stop di
  `finally`, state koneksi yang jujur.
- `src/amr_core/robot/chassis.py` — placeholder `SerialChassisAdapter` yang
  selalu menolak dihapus (alasan penolakannya sudah usang: protokolnya
  terverifikasi di sesi 2).
- `src/amr_dashboard/chassis_panel.py` (baru) — panel kontrol tahan-tekan.
- `src/amr_dashboard/chassis_transport.py` (baru) — satu-satunya tempat yang
  mengimpor pyserial (pembuka port dengan DTR/RTS turun sebelum `open()`).
- `src/amr_dashboard/robot_runtime.py` — memilih adapter live/offline, batas
  live (`LIVE_LIMITS`), dan siklus hidup port.
- `src/amr_dashboard/app.py` — merender panel chassis **sekali** di luar region
  yang di-refresh (tombol yang di-re-render menelan event "lepas"), melepas
  gerakan saat browser disconnect dan saat struktur halaman dibangun ulang.
- `src/amr_dashboard/__main__.py` — flag `--chassis-port` dan `--chassis-live`.
- `tests/test_robot_kinematics.py`, `tests/test_robot_motion_guard.py`,
  `tests/test_robot_serial_chassis.py`, `tests/test_dashboard_chassis_panel.py`
  (baru).

**Perubahan pada tes yang ada**

- `tests/test_robot_no_actuation.py` — placeholder yang selalu menolak
  transmitter diganti assertion yang lebih relevan: adapter live **tidak boleh
  mengirim apa pun sebelum port dibuka**.
- `tests/test_robot_chassis.py` — import placeholder dipindah ke modul barunya.

**Temuan yang mengubah rencana**

- Pola tanda **maju** yang dihitung persis sama dengan pola terverifikasi di
  lantai (`1:- 2:- 3:+ 4:+`), dan **putar di tempat** menghasilkan tanda sama
  di keempat motor — cocok dengan observasi sesi 2 bahwa perintah seragam
  membuat robot berputar, bukan maju. Pola **lateral** masih turunan, bukan
  hasil ukur, dan itu sebabnya gerbang G1 tetap wajib.
- Skala di-anchor ke pengukuran: 0,19 m/s → 1,036 rps, yaitu titik uji
  `u = 1,0` yang pernah diukur di lantai.
- **Perintah diagonal tanpa batas akan menuntut 2,07 rps** — di atas rentang
  yang pernah diuji. Ditambahkan invariant: tidak ada perintah yang boleh
  melebihi 1,0 rps.
- `amr_core.robot` **dilarang** mengimpor pyserial (ada guard test). Pembuka
  port karena itu pindah ke `amr_dashboard/chassis_transport.py`; logika
  adapter tetap murni dan bisa diuji tanpa device.

**Verifikasi**: `370 passed` pada seluruh suite; `All checks passed!` untuk
Ruff; `scripts/smoke_dashboard.py` exit 0 (HTTP 200); `run_dashboard.py
--help` menampilkan kelompok flag chassis.

**Tidak ada aktuasi**: tidak ada port yang dibuka, tidak ada byte yang
dikirim, tidak ada perintah motor yang dijalankan. Batas `safety.py` tidak
diubah. Tidak ada commit, push, reset, clean, atau pergantian branch.

## 21. Paket G1 — identifikasi tanda gerak (21 Oktober 2026)

Paket procedure + lembar rekaman untuk gerbang hardware P5: memastikan pola
tanda **samping** dan **putar** sebelum ada gerak lateral atau putar dari
dashboard. Dua pola itu diturunkan dari susunan roller, bukan diukur, dan
konvensi tanda versi lama di robot ini pernah terbalik persis karena
ditentukan dengan roda terangkat (commit `f8de64e`).

Perubahan:

- `scripts/g1_patterns.py` (baru) — **hanya mencetak**, tidak mengirim apa
  pun. Delapan perintah `wheel_test.py` dibangkitkan dari
  `amr_core.robot.kinematics`, jadi pola yang diuji dijamin sama dengan
  pola yang dipakai dashboard.
- `docs/g1_identifikasi_tanda.md` (baru) — prasyarat, tahap 1 (roda
  terangkat: arah putar tiap roda), tahap 2 (lantai: translasi nyata),
  lembar rekaman, dan apa yang harus dilakukan kalau hasilnya meleset.

Verifikasi: `370 passed`; `All checks passed!` untuk Ruff; skrip G1
dijalankan dan keluarannya diperiksa (tanpa aktuasi).

Tidak ada aktuasi, tidak ada perubahan pada `src/`, tidak ada commit, push,
reset, clean, atau pergantian branch.
