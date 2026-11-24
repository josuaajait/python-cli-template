# Python CLI Template

[![Tests](https://github.com/josuaajait/python-cli-template/actions/workflows/tests.yml/badge.svg)](https://github.com/josuaajait/python-cli-template/actions/workflows/tests.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

Starter CLI Python dengan header berwarna, spinner, tabel hasil, dan output JSON yang siap dipakai oleh script. Cukup Python **3.11 atau lebih baru**, tanpa dependency runtime tambahan.

Gaya tampilannya terinspirasi [PTerm CLI Template](https://github.com/pterm/cli-template), lalu diadaptasi ke Python standard library. Ini implementasi Python mandiri; PTerm/Cobra/Go tidak diperlukan.

## Langsung coba

```powershell
git clone https://github.com/josuaajait/python-cli-template.git
cd python-cli-template
python -m cli_template demo
```

Tidak perlu install paket untuk mencoba dari folder repository. Perintah yang sama bisa digunakan di PowerShell, Windows Terminal, macOS, atau Linux; bila interpreter bernama `python3`, gunakan `python3` sebagai pengganti `python`.

Contoh tampilan terminal; digest diperpendek di ilustrasi ini:

```text
 PYTHON CLI
 demo / A reusable Python CLI starter
 -------------------------------------------------------------

 [WORKING] Step 1/3: hashing sample input...
 [OK] Step 1/3 complete.
 [WORKING] Step 2/3: hashing sample input...
 [OK] Step 2/3 complete.
 [WORKING] Step 3/3: hashing sample input...
 [OK] Step 3/3 complete.

 [ SUCCESS ]
+-----------+---------+
| Field     | Value   |
+-----------+---------+
| Status    | SUCCESS |
| Completed | 3       |
+-----------+---------+

 Results
+------+---------------+
| Step | Sha256        |
+------+---------------+
| 1    | bedcdd84...   |
| 2    | 631831e6...   |
| 3    | ac34c6fe...   |
+------+---------------+
```

`demo` benar-benar menghitung SHA-256 atas input contoh; jeda singkat hanya untuk memperlihatkan spinner. Tidak mengakses jaringan atau menulis file. Hasil sesungguhnya menampilkan digest lengkap.

## Command contoh

| Command | Kegunaan |
| --- | --- |
| `python -m cli_template greet Mikhael` | Contoh command sederhana dengan argumen |
| `python -m cli_template greet Mikhael --shout` | Contoh opsi boolean |
| `python -m cli_template doctor` | Pemeriksaan Python lokal tanpa jaringan |
| `python -m cli_template demo` | Proses bertahap dengan spinner dan tabel |
| `python -m cli_template demo --steps 5 --delay 0.2` | Mengatur jumlah langkah dan jeda demo |
| `python -m cli_template demo --fail` | Mencontohkan hasil gagal dan exit code 1 |
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

## Jadikan CLI milikmu

1. Ganti `APP_NAME` dan `APP_DESCRIPTION` di `cli_template/cli.py`.
2. Ganti metadata `[project]`, URL repository, dan nama command pada `[project.scripts]` di `pyproject.toml`.
3. Tambahkan parser dan handler di `build_parser()`. Handler menerima `(args, console)` lalu mengembalikan `(result_dict, exit_code)`.
4. Ganti command contoh dengan logika aplikasimu, tambah tes perilakunya, dan perbarui README/badge ini. Jika menamai ulang folder paket, perbarui imports, entry point, package discovery, tes, dan workflow.
5. Sesuaikan pemilik lisensi pada salinanmu sambil mempertahankan notice yang berlaku untuk kode yang kamu gunakan.

Contoh handler:

```python
def build(args, console):
    console.progress('Building output...')
    # Jalankan pekerjaanmu di sini.
    console.notice('Build complete.', 'OK')
    return {'status': 'SUCCESS', 'files': 3}, 0
```

Registrasi command di `build_parser()`, sebelum loop `add_output_flags`:

```python
command = subcommands.add_parser('build', help='Build project output.')
command.set_defaults(handler=build)
```

Renderer juga dapat dipakai langsung:

```python
from cli_template.console import Console

with Console(title='MY APP', description='My command line tool') as console:
    console.header('build')
    console.progress('Preparing output...')
    console.result({'status': 'SUCCESS', 'files': 3})
```

Keluar dari blok `with` selalu menghentikan spinner, termasuk bila terjadi exception. `console.read('Continue? ')` menghentikan spinner sebelum membaca input. Pemanggilan `console.result(...)` tidak menentukan exit code; handler tetap bertanggung jawab atas arti hasilnya.

## Instalasi opsional

Untuk menggunakan command pendek `python-cli`, buat virtual environment dan install secara lokal. Runtime tetap tanpa dependency; pip mungkin perlu mengunduh setuptools untuk proses build/install.

```powershell
python -m venv .venv
# Windows
.\.venv\Scripts\python -m pip install -e .
.\.venv\Scripts\python-cli demo
```

Di macOS/Linux gunakan `.venv/bin/python` dan `.venv/bin/python-cli`.

## Struktur dan pengujian

```text
cli_template/
  __init__.py       # Versi paket
  __main__.py       # python -m cli_template
  cli.py            # Branding, parser, dan contoh handler
  console.py        # Tampilan terminal dan JSON
tests/test_cli.py   # Tes CLI asli dan kontrak renderer
.github/workflows/tests.yml
pyproject.toml
```

```powershell
python -m unittest discover -s tests -v
```

Workflow CI menjalankan tes dan smoke installed entry point pada Windows/Linux dengan Python 3.11, 3.12, dan 3.13. Lihat [kontribusi](CONTRIBUTING.md) dan [catatan desain](docs/design.md).

## Lisensi dan asal

[MIT](LICENSE), Mikhael Josua Roganda. Template ini dipisahkan dari lapisan presentasi CLI Critic Agent dan digeneralisasi; tidak membawa logika Laravel, model AI, atau artefak penelitian. Referensi visual: [pterm/cli-template](https://github.com/pterm/cli-template). Kode Go, release automation, dan branding PTerm tidak disalin.
