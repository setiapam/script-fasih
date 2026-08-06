# Reject (Bulk Reject) - FASIH BPS API Automation

Modul ini digunakan untuk mengotomatiskan penolakan (*reject*) penugasan (*assignment*) pada sistem internal FASIH BPS secara massal berdasarkan daftar target ID penugasan.

---

## 📋 Alur Kerja (Workflow)

1. **Autentikasi & Konfigurasi**: Script membaca perintah cURL dari [curl.txt](curl.txt) (salinan cURL DataTables dari browser) untuk mengambil cookies sesi browser aktif, headers HTTP, dan parameter pencarian DataTables. Anda juga dapat menentukan ID penugasan secara spesifik (manual input atau melalui text file).
2. **Pemilihan Mode Penarikan Target ID**: Script akan menampilkan menu interaktif saat dijalankan. Anda dapat memilih sumber ID:
   - Ambil dari API DataTables secara otomatis berdasarkan filter/pencarian dari `curl.txt`. Script mendukung penarikan dari halaman 1 hingga selesai (pagination).
   - Gunakan ID dari [ids.json](ids.json) yang tersimpan dari proses sebelumnya.
   - Baca daftar ID secara spesifik baris-per-baris dari file `id_spesifik.txt`.
   - Masukkan ID spesifik secara manual via input terminal.
3. **Eksekusi Reject**: Script melakukan POST request secara berurutan ke API Endpoint Approval (`https://fasih-sm.bps.go.id/app/api/assignment-approval/api/v2/approval`) untuk setiap ID yang tertera dengan data payload JSON (atau multipart):
   - `assignmentId`: (Sesuai ID target)
   - `statusApproval`: `false` (mengindikasikan aksi *Reject*)
   - `comment`: `{"dataKey":"","notes":[]}`

---

## 🛠️ Prasyarat (Prerequisites)

* **Python 3.x** terinstal pada sistem Anda.
* Library eksternal terdaftar pada berkas [requirements.txt](../requirements.txt) di root proyek.

---

## 📂 File yang Terlibat

* **[hit_endpoint.py](hit_endpoint.py)**: Kode utama script otomatisasi Python.
* **[__init__.py](__init__.py)**: Inisialisasi modul untuk runner utama.
* **[curl.txt](curl.txt)**: Tempat menempelkan salinan perintah cURL DataTables penugasan dari browser Anda (berfungsi sebagai sumber autentikasi sesi dan parameter filter). Wajib ada jika Anda memilih opsi pengambilan ID via API DataTables.
* **[ids.json](ids.json)**: Berkas JSON tempat menyimpan otomatis daftar ID penugasan.
* **id_spesifik.txt**: (Opsional) Berkas teks yang bisa Anda buat sendiri untuk memuat daftar target ID secara spesifik (satu baris satu ID).
* **[config.json](config.json)**: Berkas yang mencatat `surveyPeriodId` kegiatan aktif.
* **execution.log**: Catatan aktivitas logging eksekusi.

---

## 🚀 Panduan Penggunaan (Step-by-Step)

### Langkah 1: Siapkan Autentikasi (Opsional jika ingin otomatis narik dari list)
1. Buka browser Anda dan login ke sistem FASIH BPS.
2. Buka **Developer Tools** (tekan **F12** atau klik kanan -> **Inspect**) lalu navigasi ke tab **Network**.
3. Buka halaman Data Penugasan / DataTables Survei.
4. Cari request API DataTables yang mengarah ke endpoint `datatable-all-user-survey-periode`.
5. Klik kanan pada request tersebut -> Pilih **Copy** -> **Copy as cURL (bash)**.
6. Buat berkas `curl.txt` di dalam direktori `reject`, lalu paste perintah cURL tersebut.

### Langkah 2: Jalankan Modul
Buka terminal Anda di root direktori proyek, lalu jalankan:
```bash
python main.py reject
```
Atau cukup jalankan `python main.py` lalu pilih menu `reject`.

### Langkah 3: Pilih Mode Pencarian
Di dalam terminal, Anda akan diminta untuk memilih mode:
```text
[?] Pilih sumber ID untuk diproses (REJECT):
1. Ambil dari API DataTables (otomatis semua hasil dari curl)
2. Gunakan ID dari berkas ids.json (cache/sebelumnya)
3. Baca dari berkas id_spesifik.txt (satu ID per baris)
4. Masukkan ID secara manual via terminal
```
Silakan pilih nomor yang sesuai dengan kebutuhan Anda.

* Setelah mengonfirmasi, script akan mulai menolak (*reject*) seluruh penugasan tersebut secara massal dan berurutan.

---

## 📝 Penjelasan Status Hasil Eksekusi & Logging

* **`[SUKSES]`**: Proses reject berhasil (HTTP status 200 atau 201).
* **`[GAGAL]`**: Proses reject ditolak oleh server (misalnya HTTP status 400).
* **`[ERROR]`**: Terjadi gangguan jaringan (RequestException).

Riwayat eksekusi dicatat otomatis ke berkas `execution.log` di dalam folder ini (diabaikan dari Git).
