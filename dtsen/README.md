# Modul DTSEN (Pencocokan Target DTSEN & FASIH BPS)

Modul ini digunakan untuk memeriksa status pendataan target **DTSEN** (Data Terpadu Sosial Ekonomi Nasional) pada sistem **FASIH BPS** dan memperbarui Kolom I (`Keterangan`) serta Kolom J (`Kolom 1`) pada berkas Excel target.

---

## Logika Penentuan Status (Kolom I & Kolom J)

Pencarian dilakukan per nama anggota keluarga dengan filter wilayah hingga tingkat Kelurahan (`region4Id`). Hasil pencarian diklasifikasikan sebagai berikut:

1. **`sdh didata` pada Kolom I**:
   * **Ditemukan 1 row match**, status **bukan OPEN**, dan **ada nomor urut bangunan** (bukan `-`):
     * Kolom J diisi: **`ditemukan`**
   * **Ditemukan 1 row match**, status **bukan OPEN**, dan **tidak ada nomor urut bangunan** (`-`):
     * Kolom J diisi: **`tidak ditemukan`**
   * **Ditemukan lebih dari 1 row match**:
     * Kolom J diisi: **`ditemukan lebih dari 1 row`**

2. **`blm didata` pada Kolom I**:
   * **Ditemukan 1 row match** dan status **OPEN**.
   * **Hasil pencarian tidak ada / 0 row match**.
   * (Kolom J dibiarkan kosong / `-`).

---

## Persiapan & Penggunaan

### 1. Salin cURL Datatable
Cukup sediakan **1 file cURL** dari browser:
1. Buka browser dan login ke https://fasih-sm.bps.go.id.
2. Buka halaman data survei / penugasan (Developer Tools F12 -> tab Network).
3. Salin salah satu request `datatable-all-user-survey-periode` sebagai cURL (bash).
4. Tempel ke dalam berkas: **`dtsen/curl.txt`**.

### 2. Jalankan Modul
Jalankan melalui runner utama terpusat:
```bash
python main.py dtsen
```
Atau jalankan interaktif `python main.py` dan pilih menu `DTSEN`.

Jika ingin menentukan path file Excel khusus atau mereset progress dari awal:
```bash
# Menjalankan dengan file Excel tertentu
python main.py dtsen /home/murphi/Documents/dtsen_koja.xlsx

# Mengulang proses dari baris pertama (mereset kolom I dan J)
python main.py dtsen --reset
python main.py dtsen /home/murphi/Documents/dtsen_koja.xlsx --reset
```

---

## Fitur Unggulan
* **Auto Group ID & Region Level 4**: Script secara otomatis membaca Group ID dan mengambil hierarki wilayah Kelurahan tanpa perlu repot menyediakan cURL dropdown wilayah terpisah.
* **Resumable**: Baris yang sudah memiliki status `sdh didata` atau `blm didata` akan otomatis dilewati saat script dijalankan kembali.
* **Batch Auto-Save**: Excel disimpan secara berkala tiap 50 baris dan saat proses diinterupsi (`Ctrl+C`) sehingga progress tidak hilang.
* **Session Expired Banner**: Jika sesi login FASIH habis, banner informatif muncul dan progres yang tersimpan tetap aman.
