# Change Mode (PAPI / CAPI / CAWI) - FASIH BPS API Automation

Modul ini digunakan untuk mengubah moda pengumpulan data penugasan sampel (**PAPI**, **CAPI**, atau **CAWI**) pada sistem web **Fasih BPS** secara massal berdasarkan data pada berkas Excel.

---

## 📋 Alur Kerja (Workflow)

1. **Membaca cURL & Excel**: Script membaca konfigurasi cURL (headers, cookies, token XSRF, surveyPeriodId) dari 1 berkas `curl.txt` dan memuat daftar target dari berkas Excel `change_mode.xlsx`.
2. **Penarikan Cache Data Sampel**: Script mengunduh seluruh daftar sampel pada kegiatan survei aktif dari DataTables API ke memori (*caching*).
3. **Pencarian Sampel Spesifik (On-Demand)**:
   - **IDSBR**: Script mencari sampel berdasarkan nomor/angka `idsbr`.
   - **Fallback Perusahaan**: Jika `idsbr` tidak ditemukan di memori cache, script otomatis melakukan pencarian sekunder menggunakan nama `perusahaan` ke server BPS lalu memverifikasi kesesuaian targetnya.
4. **Validasi & Eksekusi Perubahan Mode**:
   - Nilai kolom `mode` divalidasi (didukung: `PAPI`, `CAPI`, `CAWI` - case-insensitive).
   - Mengirim request `POST` ke endpoint `.../change-mode` dengan payload `{"modes": ["<MODE>"]}`.
5. **Checkpoint & Resume Progress**:
   - Sampel yang berhasil diubah dicatat ke berkas `completed_change_mode.json` dan `laporan_hasil_change_mode.csv` secara *upsert*.
   - Saat dijalankan ulang, terdapat opsi melanjutkan progress untuk melewati sampel yang sudah sukses.

---

## 🛠️ Prasyarat (Prerequisites)

* **Python 3.x** terinstal pada sistem Anda.
* Library eksternal terdaftar pada berkas [requirements.txt](../requirements.txt) di root proyek:
  ```bash
  pip install -r requirements.txt
  ```

---

## 📂 File yang Terlibat

* **[hit_endpoint.py](hit_endpoint.py)**: Kode utama skrip otomatisasi change mode.
* **[__init__.py](__init__.py)**: Inisialisasi modul untuk runner utama.
* **`curl.txt`**: 1 salinan cURL dari request `change-mode` atau request datatable di browser web FASIH BPS.
* **`change_mode.xlsx`**: Berkas Excel berisi target perubahan mode (`idsbr`, `perusahaan`, `mode`).
* **`config.json`**: Konfigurasi `surveyPeriodId` yang aktif.
* **`completed_change_mode.json`**: Berkas checkpoint untuk mencatat sampel yang sudah berhasil diubah moda pengumpulannya (otomatis dibuat).
* **`laporan_hasil_change_mode.xlsx`**: Berkas laporan hasil perubahan mode (otomatis diperbarui secara *upsert*).
* **`execution.log`**: Berkas pencatatan log riwayat eksekusi lengkap.

---

## 🚀 Panduan Penggunaan (Step-by-Step)

### Langkah 1: Salin cURL dari Browser
1. Login ke website FASIH BPS di browser Anda.
2. Buka halaman daftar penugasan data / ubah moda survei.
3. Tekan **F12** untuk membuka Developer Tools $\rightarrow$ pilih tab **Network**.
4. Lakukan aksi ubah mode salah satu sampel (atau buka datatable) sehingga memicu request ke `.../change-mode` atau datatable.
5. Klik kanan pada request tersebut $\rightarrow$ **Copy** $\rightarrow$ **Copy as cURL (bash)**.
6. Tempel (paste) ke berkas: **`change-mode/curl.txt`**.

### Langkah 2: Siapkan Berkas Excel (`change_mode.xlsx`)
Pastikan berkas Excel diletakkan di `change-mode/change_mode.xlsx` dengan format header kolom:
* `idsbr` : Nomor ID SBR / kode sampel target.
* `perusahaan` : Nama Perusahaan / Usaha (sebagai cadangan pencarian jika IDSBR tidak langsung ditemukan di cache).
* `mode` : Pilihan moda pengumpulan target (**`PAPI`**, **`CAPI`**, atau **`CAWI`**).

Contoh isi tabel Excel:
| idsbr | perusahaan | mode |
| :--- | :--- | :--- |
| 48736 | PT MAJU JAYA | PAPI |
| 48737 | CV BERKAH ABADI | CAPI |
| 48738 | PT SUMBER REJEKI | CAWI |

### Langkah 3: Jalankan Modul
Buka terminal Anda di root direktori proyek, lalu jalankan:
```bash
python main.py change-mode
```
Atau melalui menu interaktif:
```bash
python main.py
```
Lalu pilih nomor modul **8** (`Change Mode`).

---

## 🔄 Fitur Resume Progress & Laporan

1. **Resume Progress (Auto-Skip)**:
   - Setiap sampel yang sukses diubah modanya dicatat ke `completed_change_mode.json`.
   - Jika koneksi terputus atau sesi habis di tengah jalan, Anda dapat mengulang eksekusi dan memilih **Y** pada prompt `[?] Lanjutkan progress (melewati sampel yang sudah berhasil)?` untuk melanjutkan hanya pada baris yang belum selesai.
2. **Pembaruan Laporan Excel (Upsert Mode)**:
   - Status setiap baris akan disimpan di `laporan_hasil_change_mode.xlsx`.
   - Jika sampel yang sebelumnya gagal berhasil diselesaikan pada eksekusi berikutnya, baris tersebut otomatis diperbarui menjadi `Berhasil`.
3. **Reset Cache Otomatis saat Berganti Survei**:
   - Jika `surveyPeriodId` pada `curl.txt` berubah dari kegiatan sebelumnya, checkpoint lama akan otomatis direset.

---

## 📝 Penjelasan Status Hasil Eksekusi & Logging

* **`[SUKSES]`**: Perubahan mode ke server FASIH BPS berhasil (HTTP 200, 201, 204).
* **`[SKIPPED]`**: Sampel dilewati karena sudah berhasil diubah modanya pada eksekusi sebelumnya.
* **`[GAGAL]`**: Sampel tidak ditemukan di server atau nilai kolom `mode` di Excel tidak valid.
* **`[ERROR]`**: Terjadi gangguan jaringan / exception teknis.
