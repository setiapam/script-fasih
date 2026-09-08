# Fasih BPS API Automation Scripts

Repositori monorepo ini berisi kumpulan skrip otomatisasi Python untuk membantu memproses data dan melakukan aksi massal pada sistem internal **Fasih BPS** menggunakan API endpoint.

Proyek ini telah direstrukturisasi sehingga semua skrip di dalam sub-folder berfungsi sebagai modul modular yang dapat dijalankan secara terpusat melalui satu runner utama di root direktori.

---

## Struktur Proyek

```text
.
├── README.md                # Dokumentasi utama proyek
├── main.py                  # Runner utama terpusat (CLI & menu interaktif)
├── requirements.txt         # Daftar dependensi library (terpusat)
├── mise.toml                # Runtime tool manager Python (terpusat)
│
├── approve/                 # Modul: Bulk Approval Penugasan
│   ├── __init__.py
│   ├── hit_endpoint.py      # Kode utama modul
│   ├── curl.txt             # Salinan cURL datatable penugasan khusus modul
│   ├── config.json          # Konfigurasi surveyPeriodId aktif
│   └── ids.json             # Database target ID modul (auto-generated / disunting manual)
│
├── reject/                  # Modul: Bulk Reject Penugasan
│   ├── __init__.py
│   ├── hit_endpoint.py      # Kode utama modul
│   ├── curl.txt             # Salinan cURL datatable penugasan
│   ├── ids.json             # Cache daftar ID target
│   └── config.json          # Konfigurasi surveyPeriodId
│
├── clear-assignment/        # Modul: Clear Assignment massal via email
│   ├── __init__.py
│   ├── hit_endpoint.py
│   ├── curl_get.txt
│   ├── curl_clear.txt
│   ├── emails.txt
│   └── ids.json
│
├── clear-petugas/           # Modul: Clear Region Petugas & Pengawas
│   ├── __init__.py
│   ├── hit_endpoint.py
│   ├── curl.txt
│   ├── petugas.txt
│   ├── pengawas.txt
│   └── ids.json
│
└── assign/                  # Modul: Auto Allocation (Assign)
    ├── __init__.py
    ├── hit_endpoint.py
    ├── curl.txt             # Salinan cURL datatable penugasan (cukup 1 file)
    ├── assign.xlsx          # Berkas Excel daftar target penugasan
    ├── data_pencacah.csv
    └── data_pengawas.csv
│
└── tarik-data/              # Modul: Tarik Data (Ekstraksi Data per Sub SLS)
    ├── __init__.py
    ├── hit_endpoint.py
    ├── curl.txt
    ├── curl_region.txt
    ├── config.json
    ├── subsls_target.xlsx
    ├── region_db.json
    └── result.xlsx
│
├── rekap/                   # Modul: Rekap Progress Petugas Pencacah & Pengawas
│   ├── __init__.py
│   ├── hit_endpoint.py
│   ├── curl.txt
│   ├── rekap.xlsx
│   ├── progress.json
│   └── hasil_rekap.xlsx
│
│
├── change-mode/             # Modul: Ubah Moda Pengumpulan (PAPI/CAPI/CAWI)
│   ├── __init__.py
│   ├── hit_endpoint.py
│   ├── curl.txt
│   ├── config.json
│   ├── change_mode.xlsx
│   ├── completed_change_mode.json
│   └── laporan_hasil_change_mode.xlsx
│
└── dtsen/                   # Modul: Update Status Pendataan DTSEN ke Excel
    ├── __init__.py
    ├── hit_endpoint.py
    ├── curl.txt             # Salinan cURL datatable penugasan (cukup 1 file)
    ├── config.json
    └── dtsen_sample.xlsx    # Template berkas target DTSEN
```

---

## Persyaratan Sistem & Instalasi Library

Proyek ini menggunakan **Python 3.x**. Seluruh pustaka eksternal yang dibutuhkan oleh modul didefinisikan secara terpusat di berkas [requirements.txt](requirements.txt).

### Cara Instalasi Dependensi
Jalankan perintah berikut pada terminal di root direktori proyek:
```bash
pip install -r requirements.txt
```

Bagi pengguna [mise](https://mise.jdx.dev/), versi Python Anda akan terkonfigurasi secara otomatis berkat berkas [mise.toml](mise.toml) di root direktori.

---

## Cara Menjalankan Modul

Anda dapat menjalankan skrip modul melalui runner [main.py](main.py) dengan beberapa cara:

### 1. Menggunakan Menu Interaktif (Direkomendasikan)
Jalankan runner tanpa argumen tambahan:
```bash
python main.py
```
Anda akan disajikan menu interaktif untuk memilih modul mana yang ingin dieksekusi, atau melihat langkah-langkah persiapan dengan memilih menu `h`.

### 2. Menjalankan Modul Secara Langsung (CLI Command)
Tentukan nama modul sebagai argumen baris perintah pertama:
```bash
python main.py approve
python main.py reject
python main.py clear-assignment
python main.py clear-petugas
python main.py assign
python main.py tarik-data
python main.py rekap
python main.py change-mode
python main.py dtsen
```

### 3. Melihat Bantuan Langkah Persiapan (Sebelum Run Script)
Jika Anda bingung apa saja langkah persiapan (seperti cara menyalin cURL session/token browser, format file target dll) sebelum menjalankan suatu modul, Anda dapat melihat panduan langkahnya langsung di terminal lewat perintah:
```bash
python main.py help <nama_modul>
```
Contoh perintah bantuan yang tersedia:
```bash
python main.py help approve
python main.py help reject
python main.py help clear-assignment
python main.py help clear-petugas
python main.py help assign
python main.py help tarik-data
python main.py help rekap
python main.py help change-mode
python main.py help dtsen
```

*Catatan: Saat modul dijalankan lewat `main.py`, runner akan otomatis mengubah direktori kerja (working directory) secara dinamis ke folder modul tersebut agar seluruh file input/output (seperti `curl.txt`, `ids.json`) dibaca dan ditulis dari dalam folder masing-masing.*

---

## Cara Menambahkan Modul Baru

Untuk memperluas fungsionalitas repositori ini dengan menambahkan modul baru, silakan ikuti standar arsitektur dan langkah-langkah berikut:

### Standar Arsitektur Modul
Setiap modul di repositori ini dirancang mandiri di dalam foldernya masing-masing dan wajib mematuhi konvensi berikut:
1. **Template Dummy Aman (Bukan Data Riil)**: Seluruh file contoh input/output (`.xlsx`, `.csv`, `.txt`, `.json`, `curl.txt`) yang disertakan ke dalam Git **wajib hanya berupa data dummy/template**. Jangan pernah menyimpan data riil ataupun token/cookie aktif ke repositori.
2. **Dynamic Working Directory**: Saat dipanggil via `main.py`, direktori kerja (*current working directory*) otomatis dialihkan ke folder modul terkait. Skrip dapat membaca dan menulis file lokal (seperti `curl.txt`, `config.json`, `execution.log`) langsung dengan path relatif tanpa prefix nama folder.
3. **Deteksi Sesi Expired & Banner**: Wajib mendeteksi respons HTTP `401`/`403` atau pengalihan ke laman login Keycloak/SSO, lalu menampilkan banner instruksi yang ramah pengguna (`show_session_expired_banner()`) agar user paham bahwa cURL perlu diperbarui.
4. **Resumable Checkpoint / State Persistence**: Simpan target yang berhasil diproses ke file JSON/Excel checkpoint (misalnya `completed_<modul>.json`) sehingga eksekusi yang terputus dapat dilanjutkan tanpa mengulang dari awal.
5. **Standardized Logging & Summary**: Catat hasil eksekusi ke `execution.log` (hanya detail kegagalan yang dicatat pada ringkasan akhir log) dan cetak ringkasan standar terminal.

---

### Langkah-langkah Pembuatan Modul Baru

#### Langkah 1: Buat Folder Modul Baru
Buat folder baru di bawah root direktori proyek, misalnya `modul-baru/`:
```bash
mkdir modul-baru
```

#### Langkah 2: Buat Berkas `__init__.py`
Buat berkas `__init__.py` di dalam folder modul untuk mengekspor fungsi `main`:
```python
# modul-baru/__init__.py
from .hit_endpoint import main
```

#### Langkah 3: Buat Template Berkas Konfigurasi & Dummy
Siapkan berkas-berkas template kosong/dummy di dalam folder modul:
1. **`curl.txt`**: Berkas template cURL dengan placeholder token/cookie:
   ```bash
   curl --url 'https://fasih-sm.bps.go.id/app/api/...' \
     -H 'accept: */*' \
     -H 'content-type: application/json' \
     -b 'SESSION=YOUR_SESSION_COOKIE_HERE; XSRF-TOKEN=YOUR_XSRF_TOKEN_HERE' \
     -H 'x-xsrf-token: YOUR_XSRF_TOKEN_HERE'
   ```
2. **`config.json`**: Berkas state JSON default:
   ```json
   {
     "surveyPeriodId": ""
   }
   ```
3. **Input Data Contoh (Dummy)**: Jika menggunakan Excel/CSV, sertakan baris header dan 1-2 baris data contoh dummy (misal `modul_baru.xlsx` atau `data_target.csv`).

#### Langkah 4: Buat Kode Utama Modul (`hit_endpoint.py`)
Implementasikan logika utama dengan fungsi `main()`, parser cURL, deteksi sesi expired, sistem logging, dan ringkasan akhir:

```python
# modul-baru/hit_endpoint.py
import os
import sys
import datetime
import requests

MODULE_CURL_PATH = "modul-baru/curl.txt"

def is_session_expired(response):
    if response.status_code in (401, 403):
        return True
    content_type = response.headers.get("Content-Type", "")
    if "text/html" in content_type:
        text_lower = response.text.lower()
        if any(k in text_lower for k in ("login", "keycloak", "sso", "unauthorized")):
            return True
    return False

def show_session_expired_banner(completed_count=0, total_count=0):
    print("\n" + "=" * 65)
    print("⚠️  [SESI LOGIN KADALUARSA / EXPIRED] (HTTP 401/403)")
    print("=" * 65)
    print(" Sesi login FASIH BPS atau token cURL Anda telah habis masa berlakunya.")
    print(" BUKAN karena data tidak ada di server BPS, melainkan akses ditolak.")
    print("\n Langkah mudah untuk melanjutkan:")
    print("  1. Buka browser dan login ulang ke https://fasih-sm.bps.go.id")
    print("  2. Buka tab Network (F12), lakukan interaksi/refresh halaman.")
    print(f"  3. Salin (Copy as cURL) request terbaru ke berkas: {MODULE_CURL_PATH}")
    print("  4. Jalankan ulang script (semua progress yang berhasil tersimpan otomatis).")
    if total_count > 0:
        print(f"\n Progress saat ini: {completed_count} dari {total_count} target selesai.")
    print("=" * 65 + "\n")

def main():
    print("[*] Memulai modul baru...")
    log_file = "execution.log"
    timestamp_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_file, "a", encoding="utf-8") as lf:
        lf.write(f"\n==================================================\n")
        lf.write(f"EKSEKUSI MODUL BARU: {timestamp_str}\n")
        lf.write(f"==================================================\n")

    # Logika eksekusi modul...
    sukses = 0
    gagal = 0
    total = 0

    # Cetak ringkasan akhir standar
    print("\n" + "=" * 50)
    print("           RINGKASAN AKHIR PENGEKSEKUSIAN")
    print("=" * 50)
    print(f" - Berhasil diproses : {sukses}")
    print(f" - Gagal diproses    : {gagal}")
    print(f" - Total target      : {total}")
    print("=" * 50)

if __name__ == "__main__":
    main()
```

#### Langkah 5: Daftarkan Modul Baru di `main.py`
Buka berkas [main.py](main.py) di root direktori:
1. Tambahkan informasi modul baru ke dictionary `MODULES`:
   ```python
   # main.py
   MODULES = {
       # ... modul yang sudah ada ...
       "9": {
           "name": "modul-baru",
           "title": "Modul Baru (Judul Singkat)",
           "desc": "Deskripsi singkat fungsi modul baru ini."
       }
   }
   ```
2. Tambahkan petunjuk langkah persiapan pada dictionary `HELP_STEPS`:
   ```python
   HELP_STEPS = {
       # ...
       "modul-baru": [
           "1. Login ke website FASIH BPS di browser Anda.",
           "2. Buka DevTools (F12) -> tab 'Network'.",
           "3. Salin request API terkait sebagai cURL (bash).",
           "4. Tempel ke berkas: modul-baru/curl.txt",
           "5. Siapkan berkas input (jika ada), lalu jalankan: python main.py modul-baru"
       ]
   }
   ```

#### Langkah 6: Tambahkan Dokumentasi Sub-Modul (`modul-baru/README.md`)
Buat file `modul-baru/README.md` yang menjelaskan alur kerja modul, format file input/output, dan langkah mendapatkan cURL. Tautkan juga di daftar README utama.

#### Langkah 7: Tambahkan Dependensi Baru (Jika Diperlukan)
Jika modul baru menggunakan dependensi pihak ketiga di luar standard library (seperti `pandas`, `openpyxl`), pastikan telah terdaftar di [requirements.txt](requirements.txt).

---

## Standardisasi Output Modul

Setiap modul wajib mengikuti standar format output terminal (log) berikut agar pemantauan hasil eksekusi sukses dan gagal dapat dipantau secara konsisten:

### 1. Label Status Pemrosesan
Selama iterasi pemrosesan target, wajib menggunakan indikator penunjuk status berikut:
* **`[SUKSES]`**: Untuk request yang berhasil diselesaikan oleh server (misalnya kode HTTP `200`, `201`, `204`).
* **`[GAGAL]`**: Untuk request yang ditolak oleh server karena kendala bisnis/validasi (misalnya kode HTTP `400`, `403`, `500`).
* **`[ERROR]`**: Untuk penanganan pengecualian (*exception*) teknis seperti *timeout* atau putusnya koneksi internet.

### 2. Format Ringkasan Akhir (Summary)
Di akhir baris eksekusi modul, wajib menampilkan ringkasan hasil dengan format teks persis seperti ini:
```text
==================================================
           RINGKASAN AKHIR PENGEKSEKUSIAN
==================================================
 - Berhasil diproses : <jumlah_sukses>
 - Gagal diproses    : <jumlah_gagal_dan_error>
 - Total target      : <total_target_data>
==================================================
```

---

## Sistem Log Eksekusi (Logging)

Setiap modul dilengkapi dengan sistem pencatatan log otomatis untuk memantau riwayat pemrosesan data secara mendalam:

1. **Berkas Log**: Log disimpan di dalam berkas `execution.log` di dalam masing-masing folder modul (misal `approve/execution.log`).
2. **Akumulasi Riwayat**: Log ini bertipe *append*, artinya setiap kali Anda menjalankan skrip, riwayat baru akan ditambahkan di bagian akhir file log dengan diawali *timestamp* eksekusi (seperti `EKSEKUSI APPROVE: 2026-06-14 21:10:00`).
3. **Penyaringan Detail Summary**:
   * Bagian ringkasan log di akhir hanya menampilkan **detail daftar target yang mengalami kegagalan** (seperti ID target, email, wilayah regional, atau nomor IDSBR, beserta pesan error/alasan penolakannya).
   * Target yang berhasil diproses **tidak akan dicantumkan secara detail** pada rangkuman akhir log untuk menjaga ukuran berkas tetap efisien dan memudahkan pelacakan masalah (*troubleshooting*).
4. **Keamanan Git**: Berkas `*.log` telah didaftarkan pada [.gitignore](.gitignore), sehingga log aktivitas lokal Anda tidak akan diunggah ke repositori GitHub.

---

## Dokumentasi Detail Sub-Proyek
Untuk melihat instruksi spesifik cara mendapatkan token cURL dan detail teknis masing-masing modul:
* **[Dokumentasi Modul Approve](approve/README.md)**
* **[Dokumentasi Modul Reject](reject/README.md)**
* **[Dokumentasi Modul Clear Assignment](clear-assignment/README.md)**
* **[Dokumentasi Modul Clear Petugas](clear-petugas/README.md)**
* **[Dokumentasi Modul Assign](assign/README.md)**
* **[Dokumentasi Modul Tarik Data](tarik-data/README.md)**
* **[Dokumentasi Modul Rekap](rekap/README.md)**
* **[Dokumentasi Modul Change Mode](change-mode/README.md)**
* **[Dokumentasi Modul DTSEN](dtsen/README.md)**


