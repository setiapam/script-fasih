# Clear Petugas (Hapus Alokasi Per Petugas) - FASIH BPS API Automation

Modul ini digunakan untuk mengotomatiskan pencarian dan penghapusan alokasi penugasan (*assignment*) petugas dan pengawas pada sistem FASIH BPS secara massal menggunakan API internal berdasarkan email spesifik.

---

## 📋 Alur Kerja (Workflow)

1. **Autentikasi & Konfigurasi**: Script membaca data cURL dari `curl.txt` untuk mengambil cookies sesi browser aktif.
2. **Pencarian Target**:
   - Membaca daftar email dari `petugas.txt` dan `pengawas.txt`.
   - Mencari `userId` menggunakan API **by-user**.
   - Mengambil semua alokasi region untuk user tersebut menggunakan API **allocated-region** (mendukung paginasi).
3. **Penyimpanan**: Hasil pencarian alokasi region disimpan ke `ids.json`.
4. **Penghapusan (Clear)**: Meminta konfirmasi Anda sebelum mengeksekusi request **DELETE** satu per satu untuk setiap alokasi region yang ditemukan.

---

## 🛠️ Prasyarat (Prerequisites)

* **Python 3.x** terinstal pada sistem Anda (dapat dikelola menggunakan [mise](../mise.toml) di root proyek dengan versi Python yang sesuai).
* Library eksternal terdaftar pada berkas [requirements.txt](../requirements.txt) di root proyek. Instal menggunakan terminal di root proyek:
  ```bash
  pip install -r requirements.txt
  ```

---

## 📂 File yang Terlibat

* **[hit_endpoint.py](hit_endpoint.py)**: Kode utama script Python.
* **[__init__.py](__init__.py)**: Inisialisasi modul untuk runner utama.
* **[requirements.txt](../requirements.txt)**: Berkas konfigurasi library dependensi terpusat di root proyek.
* **[curl.txt](curl.txt)**: File teks untuk menempelkan perintah cURL dari browser Anda (digunakan sebagai sumber autentikasi sesi).
* **[petugas.txt](petugas.txt)**: File teks berisi daftar email petugas (satu email per baris).
* **[pengawas.txt](pengawas.txt)**: File teks berisi daftar email pengawas (satu email per baris).
* **[ids.json](ids.json)**: File database sementara tempat script menyimpan hasil pencarian target sebelum dihapus.
* **[mise.toml](../mise.toml)**: Konfigurasi penentu versi Python jika menggunakan runtime manager `mise` terpusat di root proyek.

---

## 🚀 Panduan Penggunaan (Step-by-Step)

### Langkah 1: Siapkan Autentikasi (`curl.txt`)
1. Buka browser Anda dan buka halaman FASIH BPS yang menampilkan alokasi petugas.
2. Tekan **F12** atau klik kanan -> **Inspect** lalu pilih tab **Network**.
3. Lakukan interaksi (seperti refresh halaman atau klik menu alokasi) agar memicu pemanggilan API.
4. Cari salah satu request API ke domain `https://fasih-sm.bps.go.id` (misalnya request `datatable` atau `by-user`).
5. Klik kanan pada request tersebut -> Pilih **Copy** -> **Copy as cURL (bash)**.
6. Buka file `curl.txt`, hapus isi lamanya, kemudian **paste** perintah cURL tersebut dan simpan.

### Langkah 2: Siapkan Daftar Email
1. Buka `petugas.txt` dan isi dengan daftar email petugas yang ingin dibersihkan (satu email per baris).
2. Buka `pengawas.txt` dan isi dengan daftar email pengawas yang ingin dibersihkan (satu email per baris).

### Langkah 3: Jalankan Modul
Buka terminal Anda di root direktori proyek, lalu jalankan:
```bash
python main.py clear-petugas
```

---

## 📝 Penjelasan Status Hasil Eksekusi & Logging

* **`[SUKSES]`**: Alokasi berhasil dihapus dari sistem FASIH (HTTP status 200, 201, atau 204).
* **`[GAGAL]`**: Request ditolak oleh server (HTTP status 400 karena alokasi sudah dihapus sebelumnya, region sudah memiliki data survei yang dikirimkan, atau cookie kedaluwarsa).
* **`[ERROR]`**: Terjadi masalah teknis atau gangguan koneksi saat pemanggilan API.

Seluruh riwayat eksekusi akan dicatat secara otomatis ke berkas `execution.log` di dalam folder ini (diabaikan dari Git).
