# Approve (Bulk Approval) - FASIH BPS API Automation

Modul ini digunakan untuk mengotomatiskan persetujuan (*approval*) penugasan (*assignment*) pada sistem internal FASIH BPS secara massal berdasarkan daftar target ID penugasan.

---

## 📋 Alur Kerja (Workflow)

1. **Autentikasi & Konfigurasi**: Script membaca perintah cURL dari [curl.txt](curl.txt) (salinan cURL DataTables dari browser) untuk mengambil cookies sesi browser aktif, headers HTTP, dan parameter pencarian DataTables.
2. **Penarikan Target ID Otomatis**: Script menghubungi API DataTables penugasan (`.../datatable-all-user-survey-periode`) secara otomatis dari halaman 1 hingga selesai (dukungan penuh pagination) untuk mengekstrak seluruh ID assignment dan menyimpannya ke [ids.json](ids.json). Jika [ids.json](ids.json) sudah ada, script akan menanyakan apakah Anda ingin memakai ID yang tersimpan atau menarik data baru dari server.
3. **Eksekusi Approval**: Script melakukan POST request secara berurutan ke API Endpoint Approval (`https://fasih-sm.bps.go.id/assignment-approval/api/v2/approval`) untuk setiap ID yang tertera dengan data payload multipart:
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
* **[curl.txt](curl.txt)**: Tempat menempelkan salinan perintah cURL DataTables penugasan dari browser Anda (berfungsi sebagai sumber autentikasi sesi dan parameter filter).
* **[ids.json](ids.json)**: Berkas JSON tempat menyimpan otomatis daftar ID penugasan (dapat di-generate otomatis oleh script atau disunting manual bila diperlukan).
* **[config.json](config.json)**: Berkas yang mencatat `surveyPeriodId` kegiatan aktif untuk mendeteksi pergantian kegiatan survei secara otomatis.
* **[mise.toml](../mise.toml)**: Konfigurasi runtime tool manager `mise` terpusat di root proyek.

---

## 🚀 Panduan Penggunaan (Step-by-Step)

### Langkah 1: Siapkan Autentikasi & Datatable cURL (`curl.txt`)
1. Buka browser Anda dan login ke sistem FASIH BPS.
2. Buka **Developer Tools** (tekan **F12** atau klik kanan -> **Inspect**) lalu navigasi ke tab **Network**.
3. Buka halaman Data Penugasan / DataTables Survei.
4. Cari request API DataTables yang mengarah ke `https://fasih-sm.bps.go.id/app/api/analytic/api/v2/assignment/datatable-all-user-survey-periode` (atau request DataTables penugasan sejenis).
5. Klik kanan pada request tersebut -> Pilih **Copy** -> **Copy as cURL (bash)**.
6. Buka berkas [curl.txt](curl.txt), hapus isi lamanya, kemudian **paste** perintah cURL tersebut dan simpan.

### Langkah 2: Jalankan Modul
Buka terminal Anda di root direktori proyek, lalu jalankan:
```bash
python main.py approve
```
* **Otomatisasi ID**: Script akan membaca cURL di `curl.txt`, lalu secara otomatis mengambil seluruh ID assignment (melintasi seluruh halaman/pagination) dari server dan menyimpannya ke `approve/ids.json`.
* **Proses Approval**: Setelah mengonfirmasi jumlah ID target, script akan menyetujui (*approve*) seluruh penugasan tersebut secara massal.


---

## 📝 Penjelasan Status Hasil Eksekusi & Logging

* **`[SUKSES]`**: Proses approval berhasil dilakukan untuk assignment tersebut (HTTP status 200 atau 201).
* **`[GAGAL]`**: Proses approval ditolak oleh server (misalnya HTTP status 400 atau 500 karena parameter tidak sesuai atau session kedaluwarsa).
* **`[ERROR]`**: Terjadi gangguan jaringan atau masalah teknis (RequestException).

Seluruh riwayat eksekusi akan dicatat secara otomatis ke berkas `execution.log` di dalam folder ini (diabaikan dari Git).
