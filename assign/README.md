# Assign (Auto Allocation) - FASIH BPS API Automation

Modul ini digunakan untuk mengotomatiskan proses *assignment* (penugasan) Pencacah (PCL) dan Pengawas (PML) ke daftar Sampel kegiatan pada aplikasi web FASIH BPS secara massal berdasarkan data input berkas Excel.

---

## 📋 Alur Kerja (Workflow)

1. **Membaca cURL & Excel**: Script membaca konfigurasi cURL (headers/cookies) dari file teks pendukung dan memuat data penugasan dari berkas Excel `assign.xlsx`.
2. **Penarikan Cache Data**: Script mengunduh daftar Pencacah, Pengawas, dan 1000 data sampel kegiatan pertama dari server untuk disimpan dalam memori (*caching*).
3. **Pencarian Spesifik (On-Demand)**: Jika ada ID sampel di Excel yang posisinya di atas urutan 1000 (tidak ada di memori cache), script akan memicu pencarian spesifik menggunakan nama perusahaan atau ID sampel ke API server.
4. **Auto-Assign**: Script memasangkan PCL dan PML ke sampel yang ditemukan menggunakan request POST.

---

## 🛠️ Prasyarat (Prerequisites)

* **Python 3.x** terinstal pada sistem Anda (dapat dikelola menggunakan [mise](../mise.toml) di root proyek dengan versi Python yang sesuai).
* Library eksternal terdaftar pada berkas [requirements.txt](../requirements.txt) di root proyek. Instal menggunakan terminal di root proyek:
  ```bash
  pip install -r requirements.txt
  ```

---

## 📂 File yang Terlibat

* **[hit_endpoint.py](hit_endpoint.py)**: Kode utama script otomatisasi Python.
* **[__init__.py](__init__.py)**: Inisialisasi modul untuk runner utama.
* **[requirements.txt](../requirements.txt)**: Berkas konfigurasi library dependensi terpusat di root proyek (memerlukan `requests`, `pandas`, dan `openpyxl`).
* **`assign.xlsx`**: File Excel berisi daftar penugasan.
* **`curl_pencacah.txt`**: Salinan cURL request dari tabel pencacah.
* **`curl_pengawas.txt`**: Salinan cURL request dari tabel pengawas.
* **`curl_sampel.txt`**: Salinan cURL request dari tabel sampel kegiatan.
* **`curl_assign.txt`**: Salinan cURL request dari aksi assign manual 1x.
* **[mise.toml](../mise.toml)**: Konfigurasi runtime tool manager `mise` terpusat di root proyek.

---

## 🚀 Panduan Penggunaan (Step-by-Step)

### Langkah 1: Siapkan Autentikasi (cURL)
Dapatkan 4 jenis file cURL dari browser Anda (Developer Tools F12 -> Network tab -> Klik Kanan -> Copy as cURL (bash)):
1. **`curl_pencacah.txt`**: Salin request bernama `datatable?...` dari tabel pencacah.
2. **`curl_pengawas.txt`**: Salin request bernama `datatable?...` dari tabel pengawas.
3. **`curl_sampel.txt`**: Salin request bernama `datatable?...` dari tabel sampel kegiatan.
4. **`curl_assign.txt`**: Lakukan uji coba assign manual 1x, lalu salin request bernama `assign-by-selection/...`.

### Langkah 2: Siapkan Berkas Excel (`assign.xlsx`)
Pastikan baris pertama (Header) Excel memiliki nama kolom persis seperti berikut (huruf kecil semua):
* `idsbr` : ID Sampel target.
* `email_pencacah` : Email petugas pencacah.
* `email_pengawas` : Email petugas pengawas.
* `perusahaan` : Nama Perusahaan/Usaha (sebagai backup jika idsbr tidak ada di 1000 data pertama).

### Langkah 3: Jalankan Modul
Buka terminal Anda di root direktori proyek, lalu jalankan:
```bash
python main.py assign
```

---

## 📝 Penjelasan Status Hasil Eksekusi & Logging

* **`[SUKSES]`**: Proses assign/pemasangan PCL dan PML ke sampel berhasil (HTTP status 200 atau 201).
* **`[GAGAL]`**: Proses dilewati (*skip*) karena sampel/petugas tidak ditemukan atau server menolak request.
* **`[ERROR]`**: Terjadi masalah teknis atau gangguan koneksi saat pemanggilan API.

Seluruh riwayat eksekusi akan dicatat secara otomatis ke berkas `execution.log` di dalam folder ini (diabaikan dari Git).