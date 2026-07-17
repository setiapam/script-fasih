# Modul Tarik Data (Data Extractor)

Modul ini berfungsi untuk **menarik (mengekstrak) data penugasan** dari sistem Fasih BPS berdasarkan daftar kode Sub SLS yang diberikan oleh pengguna.

---

## Cara Kerja

Modul ini bekerja dalam 3 tahap utama:

### Tahap 1: Baca Daftar Target Sub SLS
Script membaca daftar kode Sub SLS dari file `subsls_target.xlsx`. Script ini sangat fleksibel dan dapat memproses file Excel baik yang memiliki baris header (seperti `subsls_code`) maupun yang datanya langsung diletakkan di baris/kolom pertama tanpa header.

### Tahap 2: Bangun/Lengkapi Database Wilayah (Terarah)
Script akan mencocokkan target sub SLS dengan database lokal `region_db.json`. 
- Jika ada wilayah target yang belum tersimpan di database lokal, script akan mengambil hierarki wilayah tersebut (Provinsi s.d. Sub SLS) secara terarah langsung dari API region BPS.
- Pendekatan terarah ini hanya memanggil API untuk wilayah yang Anda butuhkan saja (sangat cepat dibandingkan men-download data seluruh Indonesia).
- Hasilnya disimpan/di-cache ke file `region_db.json`.

### Tahap 3: Tarik Data Penugasan
Untuk setiap Sub SLS target yang valid, script akan mengambil data penugasan dari endpoint `datatable-all-user-survey-periode` dengan parameter wilayah yang bersesuaian, lalu mengekspor hasilnya menjadi file Excel `result.xlsx`.

---

## Persiapan Sebelum Menjalankan

### 1. Salin cURL dari Browser
1. Login ke website **Fasih BPS** di browser Anda.
2. Tekan **F12** untuk membuka Developer Tools, lalu pilih tab **Network**.
3. Cari request **`datatable-all-user-survey-periode`**.
4. Klik kanan pada request tersebut → **Copy** → **Copy as cURL (bash)**.
5. Paste cURL tersebut ke file: **`tarik-data/curl.txt`**

### 2. Salin cURL Region dari Browser
1. Masih di halaman yang sama (Developer Tools → Network masih terbuka).
2. **Klik dropdown wilayah** di halaman (misal dropdown Provinsi).
3. Cari request ke URL yang mengandung **`/region/level`**.
4. Klik kanan pada request tersebut → **Copy** → **Copy as cURL (bash)**.
5. Paste cURL tersebut ke file: **`tarik-data/curl_region.txt`**

> **Catatan**: `curl_region.txt` hanya perlu dibuat **sekali**. Setelah `groupId` tersimpan di `config.json`, file ini tidak perlu diperbarui lagi. Yang perlu diperbarui berkala hanya `curl.txt` (saat session expired).

### 3. Siapkan Daftar Target Sub SLS
Buat file Excel **`tarik-data/subsls_target.xlsx`** dengan kolom pertama berisi kode `fullCode` sub SLS.

Script akan mendeteksi kolom secara otomatis dengan urutan prioritas:
`subsls_code` → `fullCode` → `kode` → `code` → `sub_sls` → **kolom pertama** (fallback).

Contoh isi file Excel:

| subsls_code        |
|-----------------|
| 317501000100010001 |
| 317501000100010002 |
| 317501000200020001 |

---

## File Input/Output

| File | Jenis | Keterangan |
|------|-------|------------|
| `curl.txt` | Input | cURL dari request datatable (untuk session + surveyPeriodId) |
| `curl_region.txt` | Input | cURL dari request dropdown wilayah (untuk groupId, cukup sekali) |
| `config.json` | Config | Menyimpan `groupId` dan `surveyPeriodId` (otomatis dibuat) |
| `subsls_target.xlsx` | Input | Daftar kode fullCode sub SLS target (file Excel) |
| `region_db.json` | Cache | Database wilayah lengkap level 1-6 (otomatis dibuat) |
| `result.xlsx` | Output | Hasil data yang berhasil ditarik (file Excel) |
| `execution.log` | Log | Riwayat eksekusi (append mode) |

---

## Contoh Menjalankan

```bash
# Via runner utama (dari root proyek)
python main.py tarik-data

# Atau langsung
cd tarik-data && python hit_endpoint.py
```

---

## Tips

- **Database wilayah (`region_db.json`) diperbarui secara incremental**. Jika Anda mengganti/menambah list target di `subsls_target.xlsx`, script akan secara cerdas hanya men-download wilayah baru yang belum ada di cache. Anda tidak perlu menghapus database lokal atau menjawab prompt interaktif.
- Jika session/token expired, cukup **update file `curl.txt`** dengan cURL datatable yang baru dari browser.
- File `result.xlsx` akan **ditimpa** setiap kali script dijalankan. Backup terlebih dahulu jika data hasil ekstraksi sebelumnya masih diperlukan.
