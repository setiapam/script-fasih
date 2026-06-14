# Clear Assignment (Hapus Alokasi Massal) - FASIH BPS API Automation

Modul ini digunakan untuk menarik data ID assignment secara paginasi (page-by-page) dari API datatable FASIH BPS dan melakukan penghapusan alokasi penugasan (*clear assignment*) secara massal dalam bentuk batch.

---

## 📋 Alur Kerja (Workflow)

1. **Membaca cURL & Konfigurasi**: Script membaca dan mem-parsing perintah cURL yang Anda sediakan pada file `curl_get.txt` dan `curl_clear.txt`.
2. **Fetch ID**: Script mengambil ID dari endpoint datatable secara bertahap hingga seluruh halaman habis, lalu menyimpannya ke `ids.json`.
   * *Mendukung pencarian spesifik*: Jika file `emails.txt` diisi dengan daftar email petugas, script akan memodifikasi parameter pencarian secara dinamis untuk mengumpulkan ID regional alokasi mereka.
3. **Konfirmasi Penghapusan**: Script menampilkan jumlah ID yang akan dihapus dan meminta konfirmasi.
4. **Hapus Data (Clear)**: Mengirimkan request penghapusan dalam batch per 100 ID ke API endpoint penghapusan.

---

## 🛠️ Prasyarat (Prerequisites)

* **Python 3.x** terinstal pada sistem Anda (dapat dikelola menggunakan [mise](../mise.toml) di root proyek dengan versi Python yang sesuai).
* Library eksternal terdaftar pada berkas [requirements.txt](../requirements.txt) di root proyek. Instal menggunakan terminal di root proyek:
  ```bash
  pip install -r requirements.txt
  ```

---

## 📂 File yang Terlibat

* **[hit_endpoint.py](hit_endpoint.py)**: Kode utama skrip otomatisasi.
* **[__init__.py](__init__.py)**: Inisialisasi modul untuk runner utama.
* **[requirements.txt](../requirements.txt)**: Berkas konfigurasi library dependensi terpusat di root proyek.
* **`curl_get.txt`**: File tempat menyimpan perintah cURL untuk mengambil data (*datatable*).
* **`curl_clear.txt`**: File tempat menyimpan perintah cURL untuk menghapus alokasi (*clear assignment*).
* **`emails.txt`**: File input opsional untuk menampung daftar email petugas yang ingin diproses sekaligus (satu email per baris).
* **`ids.json`**: File output database sementara yang menyimpan daftar ID hasil tarikan dari API datatable.
* **[mise.toml](../mise.toml)**: Konfigurasi runtime tool manager `mise` terpusat di root proyek.

---

## 🚀 Panduan Penggunaan (Step-by-Step)

### Langkah 1: Dapatkan Perintah cURL dari Browser
1. Buka browser Anda, lalu buka menu **Developer Tools (F12)** -> tab **Network**.
2. Cari request untuk mengambil daftar assignment (memuat `datatable-all-user-survey-periode` atau `datatable`). Klik kanan -> **Copy** -> **Copy as cURL (bash)**. Tempel isinya ke file `curl_get.txt`.
3. Cari request saat melakukan penghapusan/clear assignment (memuat `clear-assignment-user` atau sejenisnya). Klik kanan -> **Copy** -> **Copy as cURL (bash)**. Tempel isinya ke file `curl_clear.txt`.

### Langkah 2: Siapkan File Daftar Email (Opsional)
* Jika ingin membersihkan alokasi petugas tertentu saja secara otomatis, buat/isi file `emails.txt` dengan daftar email petugas (satu email per baris). 
* Kosongkan atau hapus file `emails.txt` jika ingin mengambil data alokasi secara global (dibatasi maks 1000 data oleh limitasi API server).

### Langkah 3: Jalankan Modul
Buka terminal Anda di root direktori proyek, lalu jalankan:
```bash
python main.py clear-assignment
```

---

## 📝 Penjelasan Status Hasil Eksekusi & Logging

* **`[SUKSES]`**: Batch assignment berhasil dihapus dari sistem FASIH (HTTP status 200 atau 201).
* **`[GAGAL]`**: Proses penghapusan ditolak oleh server (HTTP status 400 atau 500 karena alokasi sudah dihapus sebelumnya, region memiliki data survei yang dikirimkan, atau cookie kedaluwarsa).
* **`[ERROR]`**: Terjadi masalah teknis atau gangguan koneksi saat pemanggilan API.

Seluruh riwayat eksekusi akan dicatat secara otomatis ke berkas `execution.log` di dalam folder ini (diabaikan dari Git).
