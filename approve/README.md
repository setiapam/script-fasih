# Approve (Bulk Approval) - FASIH BPS API Automation

Modul ini digunakan untuk melakukan persetujuan (*approval*) penugasan (*assignment*) pada sistem internal FASIH BPS secara massal dan otomatis, dengan **filter ketat hanya sampel berstatus `SUBMITTED`**.

Modul ini juga dilengkapi **Fitur Auto-Expand 1 Kelurahan**, sehingga Anda tidak perlu lagi menyalin cURL per Sub-SLS secara manual ketika data di FASIH baru muncul pada filter level terbawah.

---

## 🌟 Fitur Utama

1. **Eksklusif Filter `SUBMITTED`**:
   - Menjamin hanya dokumen yang sudah dikirim oleh pencacah/PPL yang akan disetujui. Dokumen berstatus `OPEN`, `APPROVED`, atau `REJECTED` otomatis diabaikan agar tidak menimbulkan error HTTP 400.
2. **Auto-Expand 1 Kelurahan (Solusi Jitu Masalah Sub-SLS)**:
   - Cukup masukkan 10 digit Kode Kelurahan/Desa (contoh: `3175040001`).
   - Script akan otomatis menelusuri seluruh SLS (Level 5) dan Sub-SLS (Level 6) di bawah kelurahan tersebut via API wilayah internal FASIH, menarik seluruh sampel berstatus `SUBMITTED`, lalu meng-approve semuanya sekaligus.
3. **Multi-Sumber ID**:
   - Ambil via DataTables API langsung (sesuai filter browser).
   - Auto-Expand Kelurahan.
   - Gunakan cache `ids.json`.
   - Baca daftar ID dari `id_spesifik.txt`.
   - Masukkan ID manual via prompt terminal.

---

## 🛠️ Prasyarat (Prerequisites)

* **Jaringan / VPN**: Script mengakses endpoint internal BPS (`https://fasih-sm.bps.go.id`). Wajib dijalankan di environment yang memiliki akses jaringan internal (misalnya melalui Dev Gateway LXC 107 atau laptop terhubung VPN kantor).
* **Python 3.x** terinstal pada sistem Anda.
* Dependensi terpasang dari root proyek:
  ```bash
  pip install -r requirements.txt
  ```

---

## 📂 File yang Terlibat

* **`hit_endpoint.py`**: Script eksekutor utama approval otomatis.
* **`curl.txt`**: Tempat menempelkan salinan cURL DataTables dari browser (sebagai sumber cookies sesi login dan headers).
* **`ids.json`**: Berkas JSON tempat menyimpan otomatis daftar ID yang berhasil ditarik (bisa digunakan untuk eksekusi ulang).
* **`id_spesifik.txt`**: (Opsional) File teks berisi daftar ID tertentu (satu baris satu ID).
* **`config.json`**: Menyimpan metadata kegiatan survei (`surveyPeriodId`).
* **`execution.log`**: Catatan riwayat hasil eksekusi approval.

---

## 🚀 Panduan Penggunaan (Step-by-Step)

### Langkah 1: Siapkan Autentikasi Sesi Browser (`curl.txt`)
1. Buka browser dan login ke **https://fasih-sm.bps.go.id**.
2. Buka halaman **Data Penugasan / DataTables Survei** target.
3. Buka **Developer Tools** (tekan **F12** atau klik kanan $\to$ **Inspect**) lalu pilih tab **Network**.
4. Lakukan interaksi / filter / refresh tabel penugasan.
5. Cari request POST yang mengarah ke:
   `https://fasih-sm.bps.go.id/app/api/analytic/api/v2/assignment/datatable-all-user-survey-periode`
6. Klik kanan request tersebut $\to$ **Copy** $\to$ **Copy as cURL (bash)**.
7. Buka berkas `approve/curl.txt`, hapus isi lamanya, lalu **paste** perintah cURL tersebut dan simpan.

---

### Langkah 2: Jalankan Script
Buka terminal di root direktori `script-fasih`, lalu jalankan:
```bash
python3 main.py approve
```
*(Atau `python3 main.py` lalu pilih menu `approve`)*

---

### Langkah 3: Pilih Mode Penarikan ID

Di terminal akan muncul 5 pilihan:

```text
[?] Pilih sumber ID untuk diproses:
1. Ambil dari API DataTables (otomatis sesuai filter curl.txt)
2. [FITUR JITU] Auto-Expand 1 Kelurahan (Otomatis sisir semua SLS & Sub-SLS)
3. Gunakan ID dari berkas ids.json (cache/sebelumnya)
4. Baca dari berkas id_spesifik.txt (satu ID per baris)
5. Masukkan ID secara manual via terminal
```

#### Cara Pakai Mode 2 (Rekomendasi untuk 1 Kelurahan Penuh):
1. Pilih opsi **`2`**.
2. Masukkan **10 digit kode kelurahan** target saat diminta:
   ```text
   Masukkan 10 digit Kode Kelurahan (misal: 3175040001): 3175040001
   ```
3. Script otomatis:
   * Mengambil semua daftar SLS dan Sub-SLS di kelurahan tersebut.
   * Melakukan query datatable per Sub-SLS di latar belakang.
   * Memfilter hanya sampel yang berstatus `SUBMITTED`.
   * Mengumpulkan semua ID ke `ids.json`.
4. Tekan **`Y`** saat muncul konfirmasi:
   ```text
   Apakah Anda yakin ingin menyetujui (approve) X assignment ini? (Y/n): Y
   ```
5. Script akan menyetujui seluruh dokumen secara massal satu per satu hingga selesai.

#### Cara Pakai Mode 1 (Reguler sesuai Filter Browser):
* Pilih opsi **`1`**. Script akan menarik data mengikuti filter yang sudah Anda pasang di browser saat menyalin cURL, mengekstrak hanya data yang berstatus `SUBMITTED`, dan melakukan approval massal.

---

## 📝 Penjelasan Status Hasil & Logging

* **`[SUKSES]`**: Dokumen berhasil disetujui (HTTP 200/201).
* **`[GAGAL]`**: Server menolak approval (HTTP 400/500, misalnya sampel sudah pernah diapprove sebelumnya atau status berubah).
* **`[ERROR AUTH]`**: Sesi login browser kedaluwarsa. Banner instruksi akan muncul meminta Anda menyalin ulang cURL baru. Progress ID yang tersimpan di `ids.json` tetap aman dan tidak hilang.

Semua detail ID yang berhasil dan gagal tercatat rapi di berkas `approve/execution.log`.
