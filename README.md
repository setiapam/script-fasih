# Fasih BPS API Automation Scripts

Repositori monorepo ini berisi kumpulan skrip otomatisasi Python untuk membantu memproses data dan melakukan aksi massal pada sistem internal **Fasih BPS** menggunakan API endpoint.

---

## Proyek yang Tersedia

Repository ini terdiri dari 3 sub-proyek (folder):

### 1. **[Approve (Bulk Approval)](approve/README.md)**
* **Lokasi Folder**: `approve/`
* **Deskripsi**: Mengotomatiskan proses persetujuan (*approval*) massal penugasan (*assignment*) berdasarkan daftar ID penugasan yang terdapat pada file `ids.json` dengan mengirimkan request POST multipart/form-data.

### 2. **[Clear Assignment](clear-assignment/README.md)**
* **Lokasi Folder**: `clear-assignment/`
* **Deskripsi**: Menarik semua ID assignment secara paginasi (page-by-page) dari API datatable lalu melakukan penghapusan alokasi penugasan secara massal (batching per 100 data) berdasarkan daftar email petugas/pengawas yang terdaftar di berkas `emails.txt`.

### 3. **[Clear Petugas](clear-petugas/README.md)**
* **Lokasi Folder**: `clear-petugas/`
* **Deskripsi**: Mengotomatiskan pencarian `userId` dan regional penugasan petugas (`petugas.txt`) serta pengawas (`pengawas.txt`), mengumpulkan seluruh ID regional target alokasi mereka ke dalam berkas `ids.json`, lalu menghapusnya (*clear*) secara massal satu per satu.

---

## Persyaratan Sistem & Instalasi Library

Semua sub-proyek di dalam repositori ini dibangun menggunakan **Python 3.x** dan menggunakan library pihak ketiga **`requests`** untuk melakukan pemanggilan API HTTP.

### Cara Instalasi Dependensi

Anda dapat menginstal dependensi dengan dua cara:

#### Opsi A: Menginstal Dependensi di Salah Satu Folder Proyek
Masuk ke salah satu direktori proyek (misal `approve/`) dan jalankan:
```bash
pip install -r requirements.txt
```

#### Opsi B: Menginstal Dependensi Secara Global
Jika Anda ingin memastikan seluruh dependensi di semua proyek terinstal, Anda dapat menginstal dari root folder dengan menjalankan:
```bash
pip install requests
```

Setiap folder proyek juga dilengkapi berkas `mise.toml` bagi Anda yang menggunakan runtime manager [mise](https://mise.jdx.dev/) untuk mengelola versi Python secara otomatis.

---

## Dokumentasi Detail Masing-Masing Proyek

Untuk melihat panduan penyiapan autentikasi via `curl.txt`, format payload `ids.json` atau file konfigurasi lainnya, silakan baca dokumentasi README spesifik pada tautan berikut:

* **[Dokumentasi Proyek Approve](approve/README.md)**
* **[Dokumentasi Proyek Clear Assignment](clear-assignment/README.md)**
* **[Dokumentasi Proyek Clear Petugas](clear-petugas/README.md)**
