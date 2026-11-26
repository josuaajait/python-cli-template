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

Baris berikutnya menunjukkan direktori arsip. Untuk daftar yang lebih panjang dari delapan baris, renderer memilih kegagalan terlebih dahulu. Jika lebih dari delapan baris gagal, setiap penyebab mendapat hitungan dan satu contoh. Untuk daftar yang seluruhnya berhasil, delapan baris pertama menjadi pratinjau.

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
| `python -m cli_template archives` | Lokasi, jumlah, dan ukuran arsip |
| `python -m cli_template archives --clean` | Tinjau jumlah dan ukuran, lalu konfirmasi penghapusan |
| `python -m cli_template --help` | Daftar command dan opsi |
| `python -m cli_template --version` | Versi aplikasi |

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
```

`--pretty`, `--json`, dan `--no-color` bersifat opsional dan dapat diletakkan sebelum atau sesudah subcommand. Bila format ditentukan di kedua posisi, format eksplisit yang terakhir dipakai. `NO_COLOR` juga mematikan warna; `TERM=dumb` mematikan warna dan animasi. Terminal Windows lama yang tidak mendukung ANSI memakai layout teks biasa. Help dan version selalu berupa teks.

Tabel membungkus nilai panjang sesuai lebar terminal. Nilai `0`, `false`, `null`, hasil gagal, dan status yang belum dikenal tetap dipertahankan; `null` ditampilkan sebagai `N/A`. Kontrol terminal dari data dibersihkan hanya untuk tampilan, sedangkan JSON mempertahankan data asli.

Exit code: `0` berhasil, `1` command selesai dengan hasil gagal, `2` argumen/input atau operasi gagal, `130` dibatalkan dengan Ctrl+C.

## Error dan arsip

Saat handler melempar exception, hasil memuat tipe, pesan asli dan lokasi. Tambahkan `--debug` untuk traceback di stderr. Hasil gagal yang dikembalikan handler memakai alasan yang disediakan handler tersebut.

Setiap hasil yang dipersingkat di terminal atau berakhir gagal disimpan ke direktori unik. `result.json` berisi payload lengkap yang sama dengan stdout mode JSON. `result.log` memuat semua nilai dalam format teks serta traceback untuk exception. Pada mode JSON, lokasi arsip dicetak ke stderr. Hasil singkat yang berhasil langsung ditampilkan tanpa membuat arsip.

| Platform | Direktori default |
| --- | --- |
| Windows | `%LOCALAPPDATA%/python-cli-template/logs` |
| macOS | `~/Library/Logs/python-cli-template/logs` |
| Linux | `$XDG_STATE_HOME/python-cli-template/logs`, default `~/.local/state/python-cli-template/logs` |

Folder `python-cli-template` mengikuti `APP_ID`. Gunakan `--log-dir DIR` atau variabel `PYTHON_CLI_LOG_DIR` (nama variabelnya mengikuti `LOG_DIR_ENV`) untuk memilih lokasi sendiri. `--no-archive` menonaktifkan penyimpanan untuk satu eksekusi. Jika penulisan gagal, stderr menampilkan peringatan dan hasil lengkap. Exit code tetap mengikuti pekerjaan utama. Arsip tersimpan sampai pengguna memilih menghapusnya.

## Jadikan CLI milikmu

Cara tercepat: jalankan script rename sekali dari root repo. Script ini mengganti nama distribusi dan command, folder paket beserta imports, folder arsip, variabel environment arsip, serta judul terminal.

```powershell
python scripts/rename_template.py my-tool --description "Alat baris perintah saya"
python -m pip install -e .
my-tool doctor
```

Tambahkan `--dry-run` untuk melihat file yang akan berubah, `--package` untuk nama import lain, dan `--title` untuk judul lain. Baris yang memuat URL GitHub tidak diubah. Script mencetak sisa langkah manual: URL repository, badge, penulis, dan lisensi.

Untuk mengatur secara manual:

1. Ganti konstanta branding di bagian atas `cli_template/cli.py`: `APP_NAME`, `APP_DESCRIPTION`, `PROG` (nama command di help), `APP_ID` (folder arsip), `LOG_DIR_ENV` (variabel environment untuk lokasi arsip), dan `RICH_MINIMUM` (samakan dengan dependency Rich).
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
  status.py         # Kosakata status bersama (berhasil, gagal, peringatan)
  summary.py        # Pemilihan contoh dan pengelompokan penyebab
  archives.py       # Penyimpanan serta penghapusan hasil lengkap
tests/
  test_cli.py           # Tes CLI lewat subprocess dan kontrak renderer
  test_presentation.py  # Ringkasan, arsip, branding, decorator, dan doctor
  test_rename.py        # Script rename pada salinan project
scripts/rename_template.py  # Ganti nama template menjadi CLI milikmu
.github/workflows/tests.yml
pyproject.toml
```

```powershell
python -m unittest discover -s tests -v
```

Workflow CI menjalankan tes dan smoke installed entry point pada Windows/Linux dengan Python 3.11, 3.12, dan 3.13. Lihat [kontribusi](CONTRIBUTING.md) dan [catatan desain](docs/design.md).

## Lisensi dan asal

[MIT](LICENSE), Mikhael Josua Roganda.
