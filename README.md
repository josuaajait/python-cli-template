# Python CLI Template

[![Tests](https://github.com/josuaajait/python-cli-template/actions/workflows/tests.yml/badge.svg)](https://github.com/josuaajait/python-cli-template/actions/workflows/tests.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

Template CLI untuk Python **3.11+**. Terminal menampilkan ringkasan, tabel, dan pesan error menggunakan Rich. Ketika stdout dialihkan ke file atau pipe, command menghasilkan satu dokumen JSON lengkap. Gaya tampilannya mengadaptasi [PTerm CLI Template](https://github.com/pterm/cli-template).

## Langsung coba di Windows

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e .
.\.venv\Scripts\python-cli demo --batch
```

Jalankan dari folder repo. Di macOS atau Linux, gunakan `.venv/bin/python` dan `.venv/bin/python-cli`. Dari environment yang sudah aktif, `python -m cli_template` juga bisa dipakai.

Demo batch memvalidasi 1.000 item lokal. Tiga kesalahan sengaja disisipkan untuk memperlihatkan perilaku command dengan exit code 1. Ringkasan yang terlihat di terminal memuat:

```text
FAILED   997 succeeded  /  3 failed

 Results
 1000 total; 997 rows omitted from preview.
+----------------------------------------+
| Item      | Status | Reason            |
|-----------+--------+-------------------|
| item-0017 | FAILED | Empty record      |
| item-0506 | FAILED | Invalid integer   |
| item-0998 | FAILED | Negative quantity |
+----------------------------------------+
```

Baris berikutnya menunjukkan ID pendek arsip beserta command untuk membukanya, misalnya `Archive: e3a00daf   python-cli archives --show e3a00daf`. Untuk daftar yang lebih panjang dari delapan baris, renderer memilih kegagalan terlebih dahulu. Jika lebih dari delapan baris gagal, setiap penyebab mendapat hitungan dan satu contoh. Untuk daftar yang seluruhnya berhasil, delapan baris pertama menjadi pratinjau.

## Command contoh

| Command | Kegunaan |
| --- | --- |
| `python -m cli_template greet Mikhael` | Contoh command sederhana dengan argumen |
| `python -m cli_template greet Mikhael --shout` | Contoh opsi boolean |
| `python -m cli_template doctor` | Pemeriksaan versi Python dan Rich lokal tanpa jaringan |
| `python -m cli_template demo` | Proses bertahap dengan spinner dan tabel |
| `python -m cli_template demo --steps 5 --delay 0.2` | Mengatur jumlah langkah dan jeda demo |
| `python -m cli_template demo --fail` | Mencontohkan hasil gagal dan exit code 1 |
| `python -m cli_template demo --batch` | Ringkasan dan arsip lengkap 1.000 item |
| `python -m cli_template archives` | Lokasi, jumlah, ukuran, dan daftar arsip (terbaru dulu) |
| `python -m cli_template archives --show 3f2a` | Hasil lengkap satu run; awalan ID sudah cukup |
| `python -m cli_template archives --clean` | Tinjau jumlah dan ukuran, lalu konfirmasi penghapusan |
| `python -m cli_template archives --clean --older-than 7d --yes` | Hapus run yang lebih lama dari 7 hari tanpa bertanya |
| `python -m cli_template --help` | Daftar command dan opsi |
| `python -m cli_template --version` | Versi aplikasi |
| `python -m cli_template demo --batch --jsonl` | JSON Lines: satu record per baris |
| `python-cli --completion powershell` | Script tab completion untuk shell |

## Tampilan otomatis

Jalankan command tanpa opsi tambahan: terminal mendapat tampilan yang mudah dibaca, sementara stdout yang dipipe/dialihkan menjadi JSON murni. Kemajuan proses berada di stderr; hasil akhir berada di stdout.

```powershell
# Otomatis JSON karena dipipe
python -m cli_template doctor | ConvertFrom-Json

# Paksa JSON saat terminal masih interaktif
python -m cli_template demo --json

# Paksa tabel ketika output ditangkap editor atau runner
python -m cli_template demo --pretty

# Tata letak tetap aktif, warna dimatikan
python -m cli_template demo --no-color

# Sembunyikan progress dan pesan informasi; hasil, peringatan, dan error tetap tampil
python -m cli_template demo --quiet
```

`--pretty`, `--json`, `--jsonl`, `--no-color`, dan `--quiet` (`-q`) bersifat opsional dan dapat diletakkan sebelum atau sesudah subcommand. Bila format ditentukan di kedua posisi, format eksplisit yang terakhir dipakai. `NO_COLOR` juga mematikan warna; `TERM=dumb` mematikan warna dan animasi. Terminal Windows lama yang tidak mendukung ANSI memakai layout teks biasa. Help dan version selalu berupa teks.

Hasil yang hanya punya satu nilai sederhana ditampilkan sebagai satu baris, bukan tabel. `message` tampil apa adanya; field lain sebagai `Label: nilai`. Flag `ready`/`valid` tidak diulang di bawah status yang sudah berwarna, tetapi tetap ada di JSON. Saat spinner berjalan, pesan progress hanya tampil di spinner; tanpa spinner (stderr bukan terminal) pesan tetap dicetak sebagai `[WORKING]`. Tabel membungkus nilai panjang sesuai lebar terminal. Nilai `0`, `false`, `null`, hasil gagal, dan status yang belum dikenal tetap dipertahankan; `null` ditampilkan sebagai `N/A`. Kontrol terminal dari data dibersihkan hanya untuk tampilan, sedangkan JSON mempertahankan data asli.

Exit code: `0` berhasil, `1` command selesai dengan hasil gagal, `2` argumen/input atau operasi gagal, `130` dibatalkan dengan Ctrl+C.

## JSON Lines

`--jsonl` menulis satu record JSON per baris ke stdout. Mode ini cocok untuk `grep`, `jq -c`, atau membaca baris demi baris di PowerShell:

```powershell
python -m cli_template demo --batch --jsonl | ConvertFrom-Json | Where-Object status -eq FAILED
```

Record yang ditulis adalah isi satu-satunya field list di tingkat atas hasil. Field lainnya, misalnya `status` atau `succeeded`, dicetak sebagai satu baris JSON ringkasan ke stderr, kecuali dengan `--quiet`. Jika ada beberapa field list, handler memilih salah satunya dengan `console.records('results')`; tanpa pilihan itu, seluruh hasil ditulis sebagai satu baris. Hasil tanpa list juga menjadi satu baris. Exit code dan arsip tetap sama dengan mode lain. `--jsonl` harus diminta secara eksplisit. Saat stdout dialihkan tanpa flag, outputnya tetap satu dokumen JSON. Data tetap dikumpulkan dulu oleh handler, jadi mode ini mengubah format, bukan pemakaian memori.

## Tab completion

Command yang terpasang bisa melengkapi nama command dan opsinya dengan tombol Tab. Daftarnya dibaca dari parser saat script dicetak, jadi command baru yang memakai `@command` ikut otomatis.

```powershell
# PowerShell: tambahkan baris ini ke $PROFILE agar aktif di setiap sesi
python-cli --completion powershell | Out-String | Invoke-Expression
```

```bash
# bash (~/.bashrc) atau zsh (~/.zshrc)
eval "$(python-cli --completion bash)"
eval "$(python-cli --completion zsh)"
```

Completion terdaftar untuk nama command terpasang (`PROG`), bukan untuk `python -m cli_template`. `--completion` mencetak script polos lalu keluar, sama seperti `--version`.

## File konfigurasi

Default pribadi bisa disimpan dalam file TOML. Semua pengaturan bersifat opsional:

```toml
color = false             # sama dengan --no-color
quiet = true              # sama dengan --quiet
log_dir = "~/cli-logs"    # sama dengan --log-dir; path relatif dihitung dari folder file ini
archive = false           # sama dengan --no-archive
```

| Platform | Lokasi default |
| --- | --- |
| Windows | `%APPDATA%/python-cli-template/config.toml` |
| macOS | `~/Library/Application Support/python-cli-template/config.toml` |
| Linux | `$XDG_CONFIG_HOME/python-cli-template/config.toml`, default `~/.config/python-cli-template/config.toml` |

Gunakan `--config FILE` atau variabel `PYTHON_CLI_CONFIG` untuk file lain. Urutan prioritasnya: flag command line, lalu variabel environment (misalnya `PYTHON_CLI_LOG_DIR`), lalu file konfigurasi. File di lokasi default boleh tidak ada. File yang disebut secara eksplisit tetapi tidak ditemukan, TOML yang rusak, pengaturan yang tidak dikenal, atau tipe nilai yang salah menghentikan command dengan exit code 2 dan pesan yang menyebut file serta pengaturannya. `--help` tetap berfungsi walaupun konfigurasi rusak. `doctor` menampilkan path konfigurasi dan apakah file tersebut dimuat.

Format output sengaja tidak bisa diatur dari file, karena stdout yang dialihkan harus selalu berupa JSON. Folder konfigurasi mengikuti `APP_ID` dan nama variabelnya mengikuti `CONFIG_ENV` di `cli_template/cli.py`.

## Error dan arsip

Saat handler melempar exception, hasil memuat tipe, pesan asli dan lokasi. Tambahkan `--debug` untuk traceback di stderr. Hasil gagal yang dikembalikan handler memakai alasan yang disediakan handler tersebut.

Setiap hasil yang dipersingkat di terminal atau berakhir gagal disimpan ke direktori unik. `result.json` berisi payload lengkap yang sama dengan stdout mode JSON. `result.log` memuat semua nilai dalam format teks serta traceback untuk exception. Di terminal, arsip ditampilkan sebagai ID pendek dan command `archives --show` yang siap disalin; path lengkap ada di `archives --show`. Pada mode JSON, path lengkap arsip dicetak ke stderr. Hasil singkat yang berhasil langsung ditampilkan tanpa membuat arsip.

| Platform | Direktori default |
| --- | --- |
| Windows | `%LOCALAPPDATA%/python-cli-template/logs` |
| macOS | `~/Library/Logs/python-cli-template/logs` |
| Linux | `$XDG_STATE_HOME/python-cli-template/logs`, default `~/.local/state/python-cli-template/logs` |

Folder `python-cli-template` mengikuti `APP_ID`. Gunakan `--log-dir DIR` atau variabel `PYTHON_CLI_LOG_DIR` (nama variabelnya mengikuti `LOG_DIR_ENV`) untuk memilih lokasi sendiri. `--no-archive` menonaktifkan penyimpanan untuk satu eksekusi. Jika penulisan gagal, stderr menampilkan peringatan dan hasil lengkap. Exit code tetap mengikuti pekerjaan utama. Arsip tersimpan sampai pengguna memilih menghapusnya.

`archives` menampilkan setiap run beserta ID, waktu simpan, hasil (`outcome`), dan ukurannya. Run yang gagal tetap tercantum sebagai data, bukan sebagai kegagalan command. `--show RUN_ID` mengembalikan payload asli di field `result`. Ini berguna dengan `--json` untuk membuka kembali hasil yang diringkas. ID boleh ditulis sebagian atau dengan awalan `run-`; awalan yang cocok dengan lebih dari satu run ditolak dengan exit code 2. `--clean` bisa dibatasi dengan `--older-than` (satuan `s`, `m`, `h`, `d`, `w`) dan dijalankan tanpa prompt dengan `--yes`, misalnya dari jadwal otomatis. Hasilnya memuat jumlah run yang cocok (`matched`) dan yang benar-benar dihapus (`removed`); run yang berubah setelah ditinjau tidak dihapus. Command `archives` sendiri tidak pernah membuat arsip. Command lain bisa memilih perilaku yang sama dengan `@command(..., archive=False)`.

## Jadikan CLI milikmu

Cara tercepat: jalankan script rename sekali dari root repo. Script ini mengganti nama distribusi dan command, folder paket beserta imports, folder arsip dan konfigurasi, variabel environment, serta judul terminal.

```powershell
python scripts/rename_template.py my-tool --description "Alat baris perintah saya"
python -m pip install -e .
my-tool doctor
```

Tambahkan `--dry-run` untuk melihat file yang akan berubah, `--package` untuk nama import lain, dan `--title` untuk judul lain. Baris yang memuat URL GitHub tidak diubah. Script mencetak sisa langkah manual: URL repository, badge, penulis, dan lisensi.

Untuk mengatur secara manual:

1. Ganti konstanta branding di bagian atas `cli_template/cli.py`: `APP_NAME`, `APP_DESCRIPTION`, `PROG` (nama command di help), `APP_ID` (folder arsip), `LOG_DIR_ENV` (variabel environment untuk lokasi arsip), `CONFIG_ENV` (variabel environment untuk file konfigurasi), dan `RICH_MINIMUM` (samakan dengan dependency Rich).
2. Ganti metadata `[project]`, URL repository, dan nama command pada `[project.scripts]` di `pyproject.toml` agar sama dengan `PROG`.
3. Tambahkan command dengan decorator `@command` dan `@argument` (lihat contoh di bawah). Handler menerima `(args, console)` lalu mengembalikan `(result_dict, exit_code)`.
4. Ganti command contoh dengan logika aplikasimu, tambah tes perilakunya, dan perbarui README/badge ini. Jika menamai ulang folder paket tanpa script, perbarui imports, entry point, package discovery, tes, dan workflow.
5. Sesuaikan pemilik lisensi pada salinanmu sambil mempertahankan notice yang berlaku untuk kode yang kamu gunakan.

Contoh command:

```python
from .commands import argument, command


@command('build', help='Build project output.')
@argument('target', nargs='?', default='dist')
@argument('--clean', action='store_true', help='Remove old output first.')
def build(args, console):
    console.keep('files')  # Selalu tampilkan seluruh field ini, termasuk jika nilainya list.
    console.progress('Building output...')
    # Jalankan pekerjaanmu di sini.
    console.notice('Build complete.', 'OK')
    return {'status': 'SUCCESS', 'files': 3}, 0
```

`@argument` menerima parameter yang sama dengan `argparse.add_argument` dan dibaca dari atas ke bawah. Command tampil di help sesuai urutan definisinya, dan opsi output (`--json`, `--pretty`, `--log-dir`, dan lainnya) ditambahkan otomatis. Nama command yang terdaftar dua kali memunculkan `ValueError`. Jika command ditaruh di modul lain, impor modul itu di `cli.py` sebelum `build_parser()` dipanggil.

Renderer juga dapat dipakai langsung:

```python
from cli_template.console import Console

with Console(title='MY APP', description='My command line tool') as console:
    console.header('build')
    console.progress('Preparing output...')
    console.result({'status': 'SUCCESS', 'files': 3})
```

Keluar dari blok `with` selalu menghentikan spinner, termasuk bila terjadi exception. `console.read('Continue? ')` menghentikan spinner sebelum membaca input. Pemanggilan `console.result(...)` tidak menentukan exit code; handler tetap bertanggung jawab atas arti hasilnya.

## Struktur dan pengujian

```text
cli_template/
  __init__.py       # Versi paket
  __main__.py       # python -m cli_template
  cli.py            # Branding, parser, dan contoh handler
  console.py        # Tampilan terminal dan JSON
  commands.py       # Decorator @command/@argument dan registry command
  config.py         # Membaca dan memvalidasi config.toml
  completion.py     # Script tab completion dari parser
  status.py         # Kosakata status bersama (berhasil, gagal, peringatan)
  summary.py        # Pemilihan contoh dan pengelompokan penyebab
  archives.py       # Penyimpanan serta penghapusan hasil lengkap
tests/
  test_cli.py           # Tes CLI lewat subprocess dan kontrak renderer
  test_presentation.py  # Ringkasan, arsip, branding, decorator, dan doctor
  test_config.py        # --quiet dan file konfigurasi
  test_display.py       # Detail tampilan terminal
  test_formats.py       # --jsonl dan tab completion
  test_rename.py        # Script rename pada salinan project
scripts/rename_template.py  # Ganti nama template menjadi CLI milikmu
.github/workflows/tests.yml
pyproject.toml
```

```powershell
python -m unittest discover -s tests -v
```

Tool pengembangan (ruff, mypy, coverage) adalah dependency opsional `dev`. Tool ini tidak ikut terpasang untuk pengguna CLI. Pasang ke virtual environment project, lalu jalankan:

```powershell
.\.venv\Scripts\python -m pip install -e ".[dev]"
```

```powershell
.\.venv\Scripts\python -m ruff check .
```

```powershell
.\.venv\Scripts\python -m mypy
```

```powershell
.\.venv\Scripts\python -m coverage run -m unittest discover -s tests; .\.venv\Scripts\python -m coverage combine; .\.venv\Scripts\python -m coverage report
```

Semua fungsi di `cli_template` dan `scripts` wajib memiliki anotasi tipe (`disallow_untyped_defs`). Coverage mencakup command yang dijalankan lewat subprocess dan gagal bila di bawah 85%.

Workflow CI menjalankan ruff dan mypy, lalu menjalankan tes dengan coverage dan smoke installed entry point pada Windows, Linux, dan macOS dengan Python 3.11, 3.12, dan 3.13. Lihat [kontribusi](CONTRIBUTING.md).

## Lisensi dan asal

[MIT](LICENSE), Mikhael Josua Roganda.
