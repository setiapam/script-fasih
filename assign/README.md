# 🚀 Auto Assign FASIH BPS

Script Python cerdas untuk mengotomatiskan proses *assignment* (penugasan) Pencacah dan Pengawas ke daftar Sampel pada aplikasi web FASIH BPS. 

Versi ini dilengkapi dengan fitur **Anti-Blokir Server**, **Smart Memory Cache**, dan **Pencarian Spesifik (On-Demand)**. Script mampu menembus batasan (*limit*) 1000 data dari server FASIH dengan cara menembak API pencarian secara spesifik menggunakan nama perusahaan atau ID sampel.

---

## 🛠️ 1. Persiapan Awal

Pastikan komputer/laptop kamu sudah terinstal **Python 3.x** (dapat dikelola menggunakan [mise](../mise.toml) di root proyek dengan versi Python yang sesuai).
Instal library yang didefinisikan secara terpusat pada file [requirements.txt](../requirements.txt) di root proyek menggunakan perintah berikut:

```bash
pip install -r requirements.txt
```

---

## 📂 2. Struktur File

Sub-proyek ini terdiri dari berkas-berkas berikut:

1. `assign.xlsx` : File Excel berisi daftar penugasan.
2. `curl_pencacah.txt` : Berisi *copy* cURL dari *datatable* pencacah.
3. `curl_pengawas.txt` : Berisi *copy* cURL dari *datatable* pengawas.
4. `curl_sampel.txt` : Berisi *copy* cURL dari *datatable* sampel kegiatan.
5. `curl_assign.txt` : Berisi *copy* cURL dari proses *assign* (simpan) manual 1x.
6. **[hit_endpoint.py](hit_endpoint.py)** : Kode utama modul Python.
7. **[__init__.py](__init__.py)** : Inisialisasi modul.

---

## 📝 3. Format File Excel (`assign.xlsx`)

Script membaca data dalam format teks murni untuk menghindari masalah desimal (ex: `.0`). Pastikan baris pertama (Header) Excel kamu memiliki nama kolom persis seperti berikut (huruf kecil semua):

* `idsbr` : ID Sampel target.
* `email_pencacah` : Email petugas pencacah.
* `email_pengawas` : Email petugas pengawas.
* `perusahaan` : Nama Perusahaan/Usaha *(Opsional tapi **SANGAT DISARANKAN**)*. Kolom ini digunakan oleh script sebagai "Kunci Pencarian Cadangan" jika `idsbr` gagal ditemukan di 1000 data pertama.

---

## 🕵️ 4. Cara Mengambil cURL dari FASIH

Script ini membutuhkan data *Cookie* dan *Token* untuk masing-masing aksi agar tidak terjadi *Cookie Mismatch* (Error 401).

**Langkah-langkah mendapatkan cURL:**
1. Login ke web FASIH menggunakan browser.
2. Tekan **F12** untuk membuka *Developer Tools* -> tab **Network**. (Pastikan tombol *recording* merah menyala).
3. Buka halaman Assignment di web FASIH.
4. **cURL Pencacah:** Filter/klik tabel pencacah. Cari *request* bernama `datatable?...`. Klik Kanan -> **Copy** -> **Copy as cURL (bash)**. Paste isinya ke `curl_pencacah.txt`.
5. **cURL Pengawas:** Lakukan hal yang sama pada tabel pengawas, paste ke `curl_pengawas.txt`.
6. **cURL Sampel:** Lakukan hal yang sama pada tabel sampel, paste ke `curl_sampel.txt`. *(Pastikan ini adalah cURL yang paling baru agar sesi tetap fresh!)*
7. **cURL Assign:** Lakukan uji coba 1 kali *assign* manual di web. Cari *request* bernama `assign-by-selection/...`. Copy sebagai cURL dan paste ke `curl_assign.txt`.

---

## ▶️ 5. Cara Menjalankan Script

Buka Terminal di root direktori proyek, lalu jalankan:

```bash
python main.py assign
```

### 🧠 Bagaimana Cara Script Ini Bekerja?
1. **Caching Aman:** Script akan menyedot data Pencacah, Pengawas, dan 1000 Sampel pertama (dengan limit 500 per tarikan agar tidak diblokir server).
2. **Auto-Export:** Data hasil tarikan akan disimpan otomatis menjadi file `data_pencacah.csv`, `data_pengawas.csv`, dan `data_sampel.csv` sebagai bukti/referensi.
3. **On-Demand Search:** Jika ada sampel di Excel yang posisinya di atas urutan 1000 (tidak ada di *cache*), script akan otomatis mengetikkan **Nama Perusahaan** (atau IDSBR) ke kolom *Search* server untuk menemukannya secara paksa.
4. **Auto-Assign:** Script memasangkan PCL dan PML ke sampel yang ditemukan.
5. **Reporting:** Di akhir proses, script akan membuat file `laporan_hasil_assign.csv` yang berisi status sukses/gagal dari setiap IDSBR.

---

## ⚠️ 6. Troublehsooting (Masalah yang Sering Terjadi)

1. **Error HTTP 401 (Unauthorized) / Sesi Expired:**
   Jika script gagal ditarik atau gagal assign dengan status `401`, berarti sesi FASIH kamu sudah habis/ter-logout. 
   **Solusi:** Refresh web FASIH, ambil ulang cURL Sampel / Assign yang baru dari *Inspect Element*, lalu *paste* ulang ke file teksnya.
2. **Sampel BENAR-BENAR Tidak Ditemukan:**
   Jika script sudah mencoba mencari spesifik menggunakan nama perusahaan dan IDSBR tapi tetap gagal, berarti data tersebut memang belum diturunkan ke wilayah/survei tersebut di database server. Silakan cek file `laporan_hasil_assign.csv` untuk melihat daftar sampel yang gagal diproses.