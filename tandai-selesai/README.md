# Tandai Selesai (Listing Wilayah) - FASIH BPS API Automation

Modul ini mencari assignment wilayah berdasarkan **list kode Sub SLS** lalu
menandai listing selesai melalui endpoint `assignment-region/done`.

## Persiapan

1. Login ke FASIH BPS, buka halaman data survei dan Developer Tools → Network.
2. Salin **Copy as cURL (bash)** request `assignment-region/datatable?periodeId=...`
   ke `tandai-selesai/curl.txt`. Format tersedia di `curl.example.txt`;
   gunakan Cookie dan X-XSRF-TOKEN sesi browser aktif.
3. Isi `tandai-selesai/list.txt` dengan satu kode lengkap Sub SLS (16 digit) per
   baris. Kode dibaca sebagai teks sehingga nol di depan tetap dipertahankan.
   Baris kosong dan komentar `#` diabaikan; kode duplikat hanya diproses sekali.

Contoh list:

```text
3175040006000100
3175040006000200
```

## Menjalankan

Dari root proyek:

```bash
python main.py help tandai-selesai
python main.py tandai-selesai
```

Atau pilih menu **10** pada `python main.py`. Script menampilkan daftar target
dan meminta konfirmasi `y` sebelum memulai. Bisa juga dijalankan langsung:

```bash
python tandai-selesai/hit_endpoint.py
```

## Alur dan hasil

1. Membaca sesi dari `curl.txt` dan periode dari query **`periodeId`**.
2. Melakukan POST pencarian per kode, dengan pagination dan pemeriksaan kode
   **persis** pada `smallestRegionFullCode`. Hasil kosong atau ambigu dicatat gagal.
3. Mengambil `id`, `surveyPeriodId`, `smallestRegionFullCode`, `region`, `regionId`,
   `regionGroupId`, `doneListing`, dan `doneTarikSample` dari hasil pencarian.
   Payload `/done` memakai status saat ini, termasuk `doneListing=false`,
   mengikuti cURL browser yang diberikan. Objek region tidak dibuat manual.
4. Wilayah yang sudah `doneListing=true` dilewati. Saat dijalankan ulang,
   status dibaca lagi dari server sehingga target yang sudah selesai tidak dikirim ulang.
5. Respons `/done` harus berupa JSON dengan `success=true` agar dicatat sukses.
   Karena contoh respons API belum tersedia, format lain dicatat gagal untuk
   diperiksa di FASIH; tidak dilakukan retry POST otomatis.
6. HTTP 401/403 atau respons HTML menghentikan proses. Perbarui `curl.txt`
   dengan sesi baru lalu jalankan ulang. Kegagalan target lain dicatat dan
   proses berlanjut ke kode berikutnya.

`laporan_hasil_tandai_selesai.xlsx` berisi kolom **Periode, Kode Sub SLS,
Status, Keterangan, Waktu**. Laporan disimpan setiap target diproses, termasuk
target gagal, sudah selesai, sesi expired, serta target yang belum diproses.
Saat dijalankan ulang, hasil diperbarui berdasarkan pasangan periode dan kode;
hasil target lain tetap dipertahankan. Kode wilayah disimpan sebagai teks.

`config.json` mencatat periode aktif dan `execution.log` mencatat hasil serta
ringkasan. Menggunakan `requests` dan `openpyxl` dari requirements root.
File sesi `curl.txt` diabaikan Git; template tidak berisi kredensial aktif.

## Pengujian tanpa server

```bash
python -m unittest discover -s tandai-selesai -p 'test_*.py' -v
```
