# Clear Assignment Automation Tool

Repositori ini berisi skrip otomatisasi Python untuk mengambil data ID assignment secara paginasi (page-by-page) dari API datatable dan melakukan penghapusan (clear assignment) secara massal dalam bentuk batch.

## Fitur Utama

- **Parser cURL Otomatis**: Mengekstrak URL, Headers, Cookie, dan Payload langsung dari perintah cURL yang disalin dari Developer Tools browser.
- **Paginasi Otomatis**: Mengambil semua ID assignment dengan melakukan iterasi parameter `start` pada payload request secara dinamis.
- **Penyimpanan Lokal**: Menyimpan semua ID yang ditemukan ke dalam file `ids.json` sebelum proses penghapusan dilakukan.
- **Konfirmasi Keamanan**: Meminta persetujuan pengguna sebelum melakukan penghapusan data.
- **Batching Execution**: Melakukan penghapusan secara bertahap (per 100 ID) untuk menghindari overload pada server.

---

## Prasyarat

Skrip ini memerlukan:
1. **Python 3.x** (versi terbaru direkomendasikan, dikelola menggunakan [mise](https://mise.jdx.dev/) di root proyek).
2. Library eksternal yang terdaftar pada `requirements.txt` di root proyek.

Instal dependensi Python dengan perintah berikut (dijalankan dari root proyek):
```bash
pip install -r requirements.txt
```

---

## Panduan Penggunaan

### 1. Dapatkan Perintah cURL dari Browser
Buka browser Anda, lalu buka menu **Developer Tools (F12)** -> tab **Network**.
1. Cari request untuk mengambil daftar assignment (biasanya memuat kata `datatable-all-user-survey-periode` atau `datatable`). Klik kanan -> **Copy** -> **Copy as cURL (bash)**.
2. Cari request saat melakukan penghapusan/clear assignment (biasanya mengarah ke `clear-assignment-user` atau sejenisnya). Klik kanan -> **Copy** -> **Copy as cURL (bash)**.

### 2. Siapkan File cURL

Untuk menjalankan skrip ini, Anda harus menyediakan dua file berisi perintah cURL yang disalin dari browser:
1. **`curl_get.txt`**: Letakkan perintah cURL untuk memuat daftar assignment (request datatable) di sini.
2. **`curl_clear.txt`**: Letakkan perintah cURL untuk menghapus alokasi (request clear assignment) di sini.

*Catatan: Pastikan isi file tersebut adalah satu perintah cURL utuh lengkap dengan semua header dan payload `--data-raw`.*

### 2.5. Siapkan File Daftar Email (Opsional)

Jika Anda ingin mengambil data assignment dari **beberapa petugas (email) sekaligus**, Anda tidak perlu mengganti-ganti perintah cURL secara manual. Cukup buat file bernama `emails.txt` di root direktori proyek dan masukkan daftar email petugas, satu per baris.

Contoh isi `emails.txt`:
```text
nrochman493@gmail.com
petugas2@gmail.com
petugas3@gmail.com
```

Skrip akan mendeteksi file `emails.txt` secara otomatis dan akan:
1. Melakukan pencarian (looping GET request) untuk setiap email tersebut secara bergantian dengan memodifikasi parameter pencarian cURL secara dinamis.
2. Mengumpulkan seluruh ID yang ditemukan dari setiap email dan menggabungkannya ke dalam file `ids.json`.
3. Menjalankan proses penghapusan massal sekaligus untuk seluruh ID tersebut.

*Catatan Penting:*
- **Mengambil alokasi email tertentu**: Isi file `emails.txt` dengan daftar email petugas/pengawas (satu per baris). Skrip akan secara khusus melakukan iterasi pencarian alokasi hanya untuk daftar email tersebut.
- **Mengambil semua alokasi secara global**: Kosongkan atau hapus file `emails.txt`. Skrip akan berjalan secara default menggunakan nilai pencarian bawaan yang ada di dalam perintah cURL (atau mengambil semuanya jika pencarian dikosongkan). Harap dicatat bahwa pencarian global tanpa filter email spesifik ini dibatasi maksimal **1000 data** oleh limitasi API dari sisi server.

### 3. Jalankan Skrip
Jalankan perintah berikut di terminal Anda:
```bash
python hit_endpoint.py
```

### 4. Alur Kerja Skrip
1. **Membaca cURL**: Skrip membaca dan mem-parsing perintah cURL yang Anda sediakan.
2. **Fetch ID**: Skrip akan mengambil ID dari endpoint datatable secara bertahap hingga seluruh halaman habis, lalu menyimpannya ke `ids.json`.
3. **Konfirmasi Penghapusan**: Skrip menampilkan jumlah ID yang akan dihapus dan meminta konfirmasi:
   ```text
   Apakah Anda yakin ingin menghapus X assignment ini? (y/N):
   ```
4. **Hapus Data**: Jika Anda menekan `y`, skrip akan mengirimkan request penghapusan dalam batch per 100 ID ke endpoint penghapusan.

### 5. Menjalankan Penghapusan Saja (Resume/Retry)

Jika proses penghapusan sebelumnya gagal/terputus atau Anda sudah memiliki file `ids.json`, Anda tidak perlu melakukan pengambilan ulang ID dari server.

Saat Anda menjalankan kembali skrip:
```bash
python hit_endpoint.py
```

Skrip akan otomatis mendeteksi file `ids.json` dan menampilkan pilihan:
```text
[*] Menemukan file 'ids.json' berisi X ID.
Apakah Anda ingin menggunakan ID yang sudah ada untuk proses clear saja? (Y/n):
```
- **Tekan `Enter` atau ketik `y`**: Skrip akan menggunakan ID yang ada dari `ids.json` dan langsung melompat ke proses penghapusan (melewati pengambilan data ulang).
- **Ketik `n`**: Skrip akan mengabaikan data lama dan mengambil ulang data ID baru dari server API datatable.

---

## Struktur File Proyek

- **[hit_endpoint.py](hit_endpoint.py)**: Kode utama skrip otomatisasi.
- **[requirements.txt](../requirements.txt)**: Berkas konfigurasi library dependensi terpusat di root proyek.
- **`curl_get.txt`**: File tempat menyimpan perintah cURL untuk mengambil data (*datatable*).
- **`curl_clear.txt`**: File tempat menyimpan perintah cURL untuk menghapus alokasi (*clear assignment*).
- **`emails.txt`**: File input opsional untuk menampung daftar email petugas yang ingin diproses sekaligus.
- **`ids.json`**: File output yang menyimpan daftar ID yang berhasil ditarik dari API datatable.
- **`output.txt`**: Log contoh keluaran dari skrip.
- **[mise.toml](../mise.toml)**: Konfigurasi penentu versi Python jika menggunakan runtime manager `mise` terpusat di root proyek.
