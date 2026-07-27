# Assign (Auto Allocation) - FASIH BPS API Automation

Modul ini digunakan untuk mengotomatiskan proses *assignment* (penugasan) Pencacah (PCL) dan Pengawas (PML) ke daftar Sampel kegiatan pada aplikasi web FASIH BPS secara massal berdasarkan data input berkas Excel.

---

## 📋 Alur Kerja (Workflow)

1. **Membaca cURL & Excel**: Script membaca konfigurasi cURL (headers/cookies/period ID) dari 1 berkas `curl.txt` dan memuat data penugasan dari berkas Excel `assign.xlsx`.
2. **Penarikan Cache Data**: Script mengunduh daftar Pencacah, Pengawas, dan sampel kegiatan dari server BPS ke memori (*caching*).
3. **Pencarian Spesifik (On-Demand)**:
   - **Sampel**: Jika ID sampel di Excel tidak ada di memori cache, script memicu pencarian spesifik ke server dengan mengutamakan **angka IDSBR terlebih dahulu**, baru menggunakan nama perusahaan sebagai *fallback*.
   - **Petugas**: Jika email PCL/PML belum ada di memori, script secara otomatis mencari petugas langsung ke API server BPS.
4. **Auto-Assign & Checkpoint**: Script memasangkan PCL dan PML ke sampel menggunakan request POST, mencatat progress yang berhasil ke `completed_assign.json`, dan memperbarui laporan CSV (`laporan_hasil_assign.csv`) secara *upsert*.

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
* **`assign.xlsx`**: File Excel berisi daftar penugasan (`idsbr`, `email_pencacah`, `email_pengawas`, `perusahaan`).
* **`curl.txt`**: Cukup 1 salinan cURL dari request `datatable` di halaman penugasan web FASIH BPS.
* **`completed_assign.json`**: Berkas checkpoint untuk mencatat sampel yang sudah berhasil di-assign (otomatis dibuat).
* **`laporan_hasil_assign.csv`**: Berkas laporan hasil penugasan (otomatis diperbarui secara *upsert*).
* **[mise.toml](../mise.toml)**: Konfigurasi runtime tool manager `mise` terpusat di root proyek.

---

## 🚀 Panduan Penggunaan (Step-by-Step)

### Langkah 1: Siapkan Autentikasi (cURL)
Cukup dapatkan **1 file cURL dari Datatable** di browser Anda (Developer Tools F12 -> Network tab -> Klik Kanan -> Copy as cURL (bash)):
* Login ke web FASIH BPS, buka halaman penugasan, tekan **F12** $\rightarrow$ tab **Network**.
* Cari request bernama **`datatable-all-user-survey-periode`** (atau request datatable lainnya).
* Klik Kanan $\rightarrow$ **Copy** $\rightarrow$ **Copy as cURL (bash)**.
* Paste ke file: **`assign/curl.txt`**.
*(Catatan: Mode lama dengan 4 file cURL terpisah juga tetap didukung secara opsional).*

### Langkah 2: Siapkan Berkas Excel (`assign.xlsx`)
Pastikan baris pertama (Header) Excel memiliki nama kolom persis seperti berikut (huruf kecil semua):
* `idsbr` : ID Sampel target.
* `email_pencacah` : Email petugas pencacah.
* `email_pengawas` : Email petugas pengawas.
* `perusahaan` : Nama Perusahaan/Usaha (sebagai backup jika idsbr tidak ada di memori cache).

### Langkah 3: Jalankan Modul
Buka terminal Anda di root direktori proyek, lalu jalankan:
```bash
python main.py assign
```

---

## 🔄 Fitur Resume Progress & Laporan

Modul `assign` dilengkapi dengan fitur pintar penanganan progress dan laporan:

1. **Resume Progress (Auto-Skip)**:
   * Setiap kali sampel berhasil di-assign (`Status 200/201`), sampel tersebut akan dicatat ke berkas checkpoint `completed_assign.json` dan `laporan_hasil_assign.csv`.
   * Saat dijalankan ulang (*re-run*), script otomatis memindai riwayat penugasan yang sudah `Berhasil` dari berkas checkpoint dan `laporan_hasil_assign.csv`.
   * Script akan menampilkan prompt:
     `[?] Lanjutkan progress (melewati sampel yang sudah berhasil)? (Y/n):`
   * Jika menjawab **Y** (atau menekan Enter), script akan **melewati (*skip*) sampel yang sudah berhasil** dan **hanya memproses sampel yang belum berhasil/gagal**.

2. **Pembaruan Laporan CSV (Upsert Mode)**:
   * Berkas `laporan_hasil_assign.csv` tidak akan ditimpa (*overwrite*) secara total.
   * Apabila sampel yang sebelumnya berstatus `Gagal` berhasil di-assign pada eksekusi berikutnya, statusnya pada berkas CSV akan **otomatis diperbarui menjadi `Berhasil`**.

3. **Reset Cache Otomatis saat Berganti Survei**:
   * Apabila cURL yang disalin berasal dari kegiatan survei baru (`surveyPeriodId` baru), cache petugas lama (`data_pencacah.csv` & `data_pengawas.csv`) dan checkpoint lama akan otomatis dibersihkan agar tidak terjadi bentrok `allocationId` antar kegiatan.

---

## 📝 Penjelasan Status Hasil Eksekusi & Logging

* **`[SUKSES]`**: Proses assign/pemasangan PCL dan PML ke sampel berhasil (HTTP status 200 atau 201).
* **`[SKIPPED]`**: Sampel dilewati karena sudah berhasil di-assign pada eksekusi sebelumnya.
* **`[GAGAL]`**: Proses dilewati (*skip*) karena sampel/petugas tidak ditemukan atau belum terdaftar pada kegiatan survei tersebut.
* **`[ERROR]`**: Terjadi masalah teknis atau gangguan koneksi saat pemanggilan API.

Seluruh riwayat eksekusi akan dicatat secara otomatis ke berkas `execution.log` di dalam folder ini (diabaikan dari Git).