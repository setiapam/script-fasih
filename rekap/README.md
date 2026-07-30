# Modul Rekap Progress Petugas (PCL & PML)

## Deskripsi

Modul ini digunakan untuk mengambil data rekap progress penugasan dari masing-masing Petugas Pencacah (PPL/PCL) dan Pengawas (PML) dari API FASIH BPS berdasarkan daftar email di berkas Excel.

## Fitur Utama

- **Filter Email Otomatis**: Hanya petugas yang memiliki email yang akan diproses oleh skrip API.
- **Breakdown Per Wilayah (Sub SLS)**: Mendukung rincian penugasan per kode Sub SLS maupun total agregat per petugas.
- **Penanganan HTTP 429 Rate-Limit**: Menggunakan penanganan *retry* otomatis dengan *exponential backoff* jika server memberlakukan pembatasan request.
- **Resume Otomatis Mulus**: Progress disimpan secara *real-time* setelah setiap 1 request. Jika sesi habis atau koneksi terputus, skrip dapat dijalankan ulang dan otomatis melanjutkan dari petugas terakhir.
- **Output Excel 3 Sheet**: Menyajikan data secara rapi, berwama, dan mudah dibaca oleh orang awam.

---

## Persiapan Berkas Input

### 1. Berkas Excel Petugas (`rekap.xlsx`)

Siapkan berkas Excel dengan daftar petugas pada **sheet pertama**. Format kolom yang dibaca:

| Kolom | Header di Excel | Keterangan |
|-------|-----------------|------------|
| **C** | Kelurahan & Tim | Contoh: `"RAWA BADAK SELATAN\nTIM 1"` |
| **D** | Role | Isi `PML` untuk Pengawas, atau kosongkan untuk Pencacah (PPL) |
| **E** | Nama Mitra | Nama lengkap petugas |
| **F** | Email Mitra | Email aktif terdaftar di FASIH (Petugas tanpa email otomatis dilewati) |
| **G** | Kelurahan | Nama kelurahan penugasan |

### 2. Berkas cURL (`curl.txt`)

1. Login ke sistem **FASIH BPS** di peramban (browser).
2. Buka menu **Report Progress** (baik halaman pengawas maupun pencacah).
3. Tekan tombol **F12** untuk membuka Developer Tools, lalu pilih tab **Network**.
4. Klik salah satu nama petugas di tabel untuk memicu panggilan API.
5. Cari request POST ke endpoint: `.../report-progress-by-responsibility`
6. Klik kanan pada request tersebut → **Copy** → **Copy as cURL (bash)**.
7. Paste cURL tersebut ke dalam berkas `rekap/curl.txt`.

---

## Cara Menjalankan Modul

```bash
# Dari root direktori proyek (via main runner)
python main.py rekap

# Atau langsung dari dalam folder modul
cd rekap
python hit_endpoint.py
```

---

## Mekanisme Resume & Penanganan Session Expired / Rate-Limit

- **Session Expired (Sesi Habis)**: Jika sesi cURL kedaluwarsa di tengah jalan, skrip akan memberi peringatan `❌ SESSION HABIS!`. Anda tinggal login ulang di peramban, salin cURL baru ke `rekap/curl.txt`, lalu jalankan ulang `python main.py rekap`. Skrip akan otomatis melanjutkan dari petugas yang belum selesai.
- **Rate Limit (HTTP 429)**: Jika terkena batas request server, skrip akan secara otomatis menampilkan status `⏳ Rate Limit (429)! Menunggu Xs...` dan melakukan percobaan ulang (*retry*) hingga 5 kali per request.

---

## Format Output (`hasil_rekap.xlsx`)

Berkas luaran Excel `hasil_rekap.xlsx` terdiri dari 3 sheet:

### 1. Sheet `Detail Per Wilayah` (Breakdown Sub SLS)
Menampilkan rincian penugasan per baris untuk setiap Kode Sub SLS yang diampu oleh petugas:

| Kolom | Keterangan |
|-------|------------|
| **No** | Nomor urut per tim |
| **Kelurahan** | Nama kelurahan penugasan |
| **Tim** | Nama tim (TIM 1, TIM 2, dst) |
| **Role** | PML (Pengawas) / PPL (Pencacah) |
| **Nama Mitra** | Nama lengkap petugas |
| **Email Mitra** | Email mitra yang terdaftar |
| **Nama PML** | Nama pengawas (khusus untuk baris PPL) |
| **Kode Sub SLS** | Kode unik wilayah penugasan (sub SLS) |
| **Total Assignment** | Total sampel/target di wilayah tersebut |
| **Approved (Pengawas)** | Jumlah sampel disetujui pengawas |
| **Submitted (Pencacah)** | Jumlah sampel disubmit pencacah |
| **Open** | Jumlah sampel belum dikerjakan |
| **Draft** | Jumlah sampel status draft |
| **Rejected (Pengawas)** | Jumlah sampel ditolak pengawas |
| **Revoked (Pengawas)** | Jumlah sampel dicabut pengawas |
| **Status** | Status pengambilan data |

### 2. Sheet `Rekap Per Petugas` (Total per Petugas)
Menampilkan akumulasi total penugasan (1 baris per petugas):

| Kolom | Keterangan |
|-------|------------|
| **No** | Nomor urut per tim |
| **Kelurahan** | Nama kelurahan penugasan |
| **Tim** | Nama tim |
| **Role** | PML / PPL |
| **Nama Mitra** | Nama lengkap petugas |
| **Email Mitra** | Email mitra |
| **Nama PML** | Nama pengawas |
| **Jml Sub SLS** | Jumlah wilayah Sub SLS yang diampu |
| **Total Assignment** | Total keseluruhan target sampel petugas |
| **Approved / Submitted / Open / Draft / Rejected / Revoked** | Akumulasi status penugasan |
| **Status** | Persentase ketercapaian (%) & indikator visual |

### 3. Sheet `Ringkasan`
Ringkasan statistik total petugas, total wilayah Sub SLS, dan grand total agregasi sampel seluruh petugas.

---

## Berkas yang Dihasilkan

| Berkas | Deskripsi |
|--------|-----------|
| `hasil_rekap.xlsx` | Berkas output utama (Format Excel 3 sheet) |
| `progress.json` | Berkas rekap sementara/resume (Otomatis dihapus jika semua data 100% sukses diproses) |
| `execution.log` | Catatan riwayat log pemrosesan dan rincian kesalahan |
