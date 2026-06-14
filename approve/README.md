# Fasih BPS Bulk Assignment Approval Automation

Script ini digunakan untuk mengotomatiskan persetujuan (approval) penugasan (*assignment*) pada sistem Fasih BPS secara massal menggunakan API internal.

## Alur Kerja Script (Workflow)

1. **Autentikasi & Konfigurasi**: Script membaca perintah cURL dari [curl.txt](curl.txt) untuk mengambil cookies sesi browser aktif dan headers HTTP. Header `Content-Type` bawaan dari cURL akan diabaikan agar library `requests` Python dapat menyusun format `multipart/form-data` dengan *boundary* yang tepat secara dinamis.
2. **Membaca Target Approval**: Script membaca daftar ID assignment dari [ids.json](ids.json).
3. **Eksekusi Approval**: Script melakukan POST request secara berurutan ke API Endpoint Approval (`https://fasih-sm.bps.go.id/assignment-approval/api/v2/approval`) untuk setiap ID yang tertera dengan data payload:
   - `assignmentId`: `<ID dari ids.json>`
   - `statusApproval`: `true`
   - `comment`: `{"dataKey":"","notes":[]}`

---

## Persyaratan (Prerequisites)

* **Python 3.x** terinstal pada sistem Anda (dapat dikelola menggunakan [mise](mise.toml) dengan versi Python yang sesuai).
* Library eksternal yang dibutuhkan dapat diinstal menggunakan terminal dengan perintah:
  ```bash
  pip install -r requirements.txt
  ```

---

## File yang Terlibat

* **[hit_endpoint.py](hit_endpoint.py)**: Kode utama script otomatisasi Python.
* **[requirements.txt](requirements.txt)**: Berkas konfigurasi library dependensi (Python requests).
* **[curl.txt](curl.txt)**: Tempat menempelkan salinan perintah cURL dari browser Anda (berfungsi sebagai sumber autentikasi sesi).
* **[ids.json](ids.json)**: Berkas JSON berisi daftar objek dengan key `"id"` yang merupakan ID penugasan yang ingin disetujui secara massal.
* **[mise.toml](mise.toml)**: Konfigurasi runtime tool manager `mise` untuk mengunci versi Python yang digunakan.

---

## Cara Penggunaan (Step-by-Step)

### Langkah 1: Siapkan Autentikasi (`curl.txt`)
1. Buka browser Anda dan login ke sistem Fasih BPS.
2. Buka **Developer Tools** (tekan **F12** atau klik kanan -> **Inspect**) lalu navigasi ke tab **Network**.
3. Lakukan aksi persetujuan (approval) pada salah satu assignment secara manual di web untuk memicu request API.
4. Cari request API yang mengarah ke `https://fasih-sm.bps.go.id/assignment-approval/api/v2/approval`.
5. Klik kanan pada request tersebut -> Pilih **Copy** -> **Copy as cURL (bash)**.
6. Buka berkas [curl.txt](curl.txt) di folder `approve`, hapus isi lamanya, kemudian **paste** perintah cURL tersebut dan simpan.

### Langkah 2: Siapkan Daftar ID Target (`ids.json`)
1. Buka berkas [ids.json](ids.json).
2. Isi berkas dengan array JSON yang berisi daftar ID assignment yang ingin Anda setujui. Formatnya adalah sebagai berikut:
   ```json
   [
     {"id": "d4c5c0a6-b73c-4c97-9cb7-a2fdb6feda30"},
     {"id": "bda3d155-ecd4-4d33-8fa0-0ce657f4e613"}
   ]
   ```

### Langkah 3: Jalankan Script
Buka terminal Anda di direktori folder `approve`, lalu jalankan perintah berikut:
```bash
python hit_endpoint.py
```

Script akan memproses satu per satu ID yang ada di dalam `ids.json` dan menampilkan status respons dari server.

---

## Penjelasan Status HTTP saat Eksekusi

* **`Status HTTP: 200` / `201`**: Proses approval berhasil dilakukan untuk assignment tersebut.
* **`Status HTTP: 401` / `403`**: Sesi autentikasi Anda di [curl.txt](curl.txt) telah kedaluwarsa atau tidak valid. Silakan salin ulang perintah cURL yang baru dari browser Anda.
* **`Status HTTP: 500` / `400`**: Terjadi kesalahan dari sisi server atau parameter request yang tidak sesuai.
