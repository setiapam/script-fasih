# Approve (Bulk Approval) - FASIH BPS API Automation

Modul ini digunakan untuk mengotomatiskan persetujuan (*approval*) penugasan (*assignment*) pada sistem internal FASIH BPS secara massal berdasarkan daftar target ID penugasan.

---

## 📋 Alur Kerja (Workflow)

1. **Autentikasi & Konfigurasi**: Script membaca perintah cURL dari [curl.txt](curl.txt) untuk mengambil cookies sesi browser aktif dan headers HTTP.
2. **Membaca Target Approval**: Script membaca daftar ID assignment dari [ids.json](ids.json).
3. **Eksekusi Approval**: Script melakukan POST request secara berurutan ke API Endpoint Approval (`https://fasih-sm.bps.go.id/assignment-approval/api/v2/approval`) untuk setiap ID yang tertera dengan data payload:
   - `assignmentId`: ID dari `ids.json`
   - `statusApproval`: `true`
   - `comment`: `{"dataKey":"","notes":[]}`

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
* **[requirements.txt](../requirements.txt)**: Berkas konfigurasi library dependensi terpusat di root proyek.
* **[curl.txt](curl.txt)**: Tempat menempelkan salinan perintah cURL dari browser Anda (berfungsi sebagai sumber autentikasi sesi).
* **[ids.json](ids.json)**: Berkas JSON berisi daftar objek dengan key `"id"` yang merupakan ID penugasan yang ingin disetujui secara massal.
* **[mise.toml](../mise.toml)**: Konfigurasi runtime tool manager `mise` terpusat di root proyek.

---

## 🚀 Panduan Penggunaan (Step-by-Step)

### Langkah 1: Siapkan Autentikasi (`curl.txt`)
1. Buka browser Anda dan login ke sistem FASIH BPS.
2. Buka **Developer Tools** (tekan **F12** atau klik kanan -> **Inspect**) lalu navigasi ke tab **Network**.
3. Lakukan aksi persetujuan (approval) pada salah satu assignment secara manual di web untuk memicu request API.
4. Cari request API yang mengarah ke `https://fasih-sm.bps.go.id/assignment-approval/api/v2/approval`.
5. Klik kanan pada request tersebut -> Pilih **Copy** -> **Copy as cURL (bash)**.
6. Buka berkas [curl.txt](curl.txt), hapus isi lamanya, kemudian **paste** perintah cURL tersebut dan simpan.

### Langkah 2: Siapkan Daftar ID Target (`ids.json`)
1. Buka berkas [ids.json](ids.json).
2. Isi berkas dengan array JSON yang berisi daftar ID assignment yang ingin Anda setujui. Formatnya adalah sebagai berikut:
   ```json
   [
     {"id": "d4c5c0a6-b73c-4c97-9cb7-a2fdb6feda30"},
     {"id": "bda3d155-ecd4-4d33-8fa0-0ce657f4e613"}
   ]
   ```

### Langkah 3: Jalankan Modul
Buka terminal Anda di root direktori proyek, lalu jalankan:
```bash
python main.py approve
```

---

## 📝 Penjelasan Status Hasil Eksekusi & Logging

* **`[SUKSES]`**: Proses approval berhasil dilakukan untuk assignment tersebut (HTTP status 200 atau 201).
* **`[GAGAL]`**: Proses approval ditolak oleh server (misalnya HTTP status 400 atau 500 karena parameter tidak sesuai atau session kedaluwarsa).
* **`[ERROR]`**: Terjadi gangguan jaringan atau masalah teknis (RequestException).

Seluruh riwayat eksekusi akan dicatat secara otomatis ke berkas `execution.log` di dalam folder ini (diabaikan dari Git).
