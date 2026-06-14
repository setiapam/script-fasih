# Fasih BPS Allocation Cleaner Automation

Script ini digunakan untuk mengotomatiskan pencarian dan penghapusan alokasi penugasan (assignment) petugas dan pengawas pada sistem Fasih BPS secara massal menggunakan API internal.

## Alur Kerja Script (Workflow)

1. **Autentikasi & Konfigurasi**: Script membaca data cURL dari `curl.txt` untuk mengambil cookies sesi browser yang aktif dan parameter survey (`surveyPeriodId`).
2. **Pencarian Target (Step 1 & 2)**:
   - Membaca daftar email dari `petugas.txt` dan `pengawas.txt`.
   - Melakukan pencarian bergantian (selang-seling) untuk setiap email.
   - Mencari `userId` menggunakan API **Step 1 (by-user)**.
   - Mengambil semua alokasi region untuk user tersebut menggunakan API **Step 2 (allocated-region)** dengan dukungan paginasi otomatis.
3. **Penyimpanan**: Hasil pencarian disimpan ke `ids.json` sebagai database target.
4. **Penghapusan (Step 3)**: Meminta konfirmasi Anda sebelum mengeksekusi request **DELETE** satu per satu untuk setiap alokasi region yang ditemukan.

---

## Persyaratan (Prerequisites)

* **Python 3.x** terinstal pada sistem Anda (bisa dikelola dengan runtime manager [mise](../mise.toml) terpusat di root proyek).
* Library eksternal yang terdaftar pada `requirements.txt` terpusat. Instal menggunakan terminal (dijalankan dari root proyek):
  ```bash
  pip install -r requirements.txt
  ```

---

## File yang Terlibat

* **[hit_endpoint.py](hit_endpoint.py)**: File utama script Python.
* **[requirements.txt](../requirements.txt)**: Berkas konfigurasi library dependensi terpusat di root proyek.
* **[curl.txt](curl.txt)**: File teks untuk menempelkan perintah cURL dari browser Anda (digunakan sebagai sumber autentikasi).
* **[petugas.txt](petugas.txt)**: File teks berisi daftar email petugas (satu email per baris).
* **[pengawas.txt](pengawas.txt)**: File teks berisi daftar email pengawas (satu email per baris).
* **[ids.json](ids.json)**: File database sementara tempat script menyimpan hasil pencarian target sebelum dihapus.
* **[mise.toml](../mise.toml)**: Konfigurasi penentu versi Python jika menggunakan runtime manager `mise` terpusat di root proyek.

---

## Cara Penggunaan (Step-by-Step)

### Langkah 1: Siapkan Autentikasi (`curl.txt`)
1. Buka browser Anda dan buka halaman Fasih BPS yang menampilkan alokasi petugas.
2. Tekan **F12** atau klik kanan -> **Inspect** lalu pilih tab **Network**.
3. Lakukan interaksi (seperti refresh halaman atau klik menu alokasi) agar memicu pemanggilan API.
4. Cari salah satu request API ke domain `https://fasih-sm.bps.go.id` (misalnya request `datatable` atau `by-user`).
5. Klik kanan pada request tersebut -> Pilih **Copy** -> **Copy as cURL**.
6. Buka file `curl.txt` di folder project ini, hapus isi lamanya, lalu **paste** perintah cURL tersebut dan simpan file.

### Langkah 2: Siapkan Daftar Email
1. Buka `petugas.txt` dan isi dengan daftar email petugas yang ingin dibersihkan (satu email per baris).
2. Buka `pengawas.txt` dan isi dengan daftar email pengawas yang ingin dibersihkan (satu email per baris).

### Langkah 3: Jalankan Script
Jalankan script menggunakan terminal dengan perintah berikut:
```bash
python3 hit_endpoint.py
```

### Langkah 4: Tinjau Ringkasan & Konfirmasi
1. Script akan mencari user secara bergantian antara petugas dan pengawas, lalu memuat seluruh alokasi region mereka.
2. Hasil pencarian akan disimpan di `ids.json`.
3. Script akan menampilkan **Ringkasan Target Hapus** (jumlah alokasi per email).
4. Konfirmasi penghapusan dengan mengetik **`y`** lalu tekan **Enter** untuk mulai menghapus. Ketik **`n`** jika ingin membatalkannya.

---

## Penjelasan Status HTTP saat Eksekusi DELETE

* **`[OK] (Status: 204 / 200 / 201)`**: Alokasi berhasil dihapus dari sistem Fasih.
* **`[GAGAL] (Status: 400)`**: Request ditolak oleh server. Ini biasanya terjadi karena:
  1. Alokasi tersebut **sudah dihapus sebelumnya**.
  2. Region tersebut **sudah memiliki data survei yang dikirimkan** oleh petugas, sehingga server Fasih melarang penghapusan demi keamanan data.
* **`[GAGAL] (Status: 401 / 403)`**: Session cookie di `curl.txt` sudah kedaluwarsa atau salah. Silakan salin kembali cURL baru dari browser Anda.
