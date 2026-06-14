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
│   ├── curl.txt             # Salinan cURL (auth) khusus modul
│   └── ids.json             # Database target ID modul
│
├── clear-assignment/        # Modul: Clear Assignment massal via email
│   ├── __init__.py
│   ├── hit_endpoint.py
│   ├── curl_get.txt
│   ├── curl_clear.txt
│   ├── emails.txt
│   └── ids.json
│
└── clear-petugas/           # Modul: Clear Region Petugas & Pengawas
    ├── __init__.py
    ├── hit_endpoint.py
    ├── curl.txt
    ├── petugas.txt
    ├── pengawas.txt
    └── ids.json
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

Anda dapat menjalankan skrip modul melalui runner [main.py](main.py) dengan dua cara:

### 1. Menggunakan Menu Interaktif (Direkomendasikan)
Jalankan runner tanpa argumen tambahan:
```bash
python main.py
```
Anda akan disajikan menu interaktif untuk memilih modul mana yang ingin dieksekusi.

### 2. Menjalankan Modul Secara Langsung (CLI Command)
Tentukan nama modul sebagai argumen baris perintah pertama:
```bash
python main.py approve
python main.py clear-assignment
python main.py clear-petugas
```

*Catatan: Saat modul dijalankan lewat `main.py`, runner akan otomatis mengubah direktori kerja (working directory) secara dinamis ke folder modul tersebut agar seluruh file input/output (seperti `curl.txt`, `ids.json`) dibaca dan ditulis dari dalam folder masing-masing.*

---

## Cara Menambahkan Modul Baru

Untuk memperluas fungsionalitas repositori ini dengan menambahkan modul baru, silakan ikuti langkah-langkah berikut:

### Langkah 1: Buat Folder Modul Baru
Buat folder baru di bawah root direktori proyek, misalnya `laporan-baru/`:
```bash
mkdir laporan-baru
```

### Langkah 2: Buat Kode Modul
Buat file Python utama di dalam folder tersebut (misalnya `hit_endpoint.py`). Pastikan script Anda memiliki fungsi entrypoint `main()`:
```python
# hit_endpoint.py
def main():
    print("Modul baru berhasil dijalankan!")

if __name__ == "__main__":
    main()
```

### Langkah 3: Tambahkan Berkas `__init__.py`
Buat berkas `__init__.py` di dalam folder modul baru untuk mendaftarkannya sebagai package dan mengekspor fungsi `main`:
```python
# __init__.py
from .hit_endpoint import main
```

### Langkah 4: Daftarkan Modul Baru di `main.py`
Buka berkas [main.py](main.py) di root direktori, lalu tambahkan entri baru ke dalam dictionary `MODULES`:
```python
# main.py
MODULES = {
    # ... modul yang sudah ada ...
    "4": {
        "name": "laporan-baru",
        "title": "Laporan Baru (Deskripsi Singkat)",
        "desc": "Detail fungsionalitas dari modul baru ini."
    }
}
```

### Langkah 5: Tambahkan Dependensi Baru (Opsional)
Jika modul baru Anda memerlukan pustaka python eksternal (misalnya `pandas`), tambahkan pustaka tersebut ke dalam file [requirements.txt](requirements.txt) di root proyek.

---

## Dokumentasi Detail Sub-Proyek
Untuk melihat instruksi spesifik cara mendapatkan token cURL dan detail teknis masing-masing modul:
* **[Dokumentasi Modul Approve](approve/README.md)**
* **[Dokumentasi Modul Clear Assignment](clear-assignment/README.md)**
* **[Dokumentasi Modul Clear Petugas](clear-petugas/README.md)**
