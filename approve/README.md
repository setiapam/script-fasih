# Approve (Bulk Approval) - FASIH BPS API Automation

Modul ini digunakan untuk menyetujui (*approval*) penugasan (*assignment*) pada sistem internal FASIH BPS secara massal, otomatis, dan berurutan, dengan **filter ketat hanya sampel berstatus `SUBMITTED`**.

Modul ini telah dilengkapi fitur **Cross-Account Auto-Fetch dengan Dukungan 2FA / TOTP**, yang menyelesaikan kendala keterbatasan hak akses pengawas per Sub-SLS.

---

## 🌟 Mengapa Butuh Fitur Ini? (Masalah & Solusi)

* **Masalah Lapangan**:
  Di sistem FASIH BPS, akun pengawas lapangan (**PML**) dibatasi oleh server hanya bisa melihat Sub-SLS yang dialokasikan ke dirinya sendiri. Jika di satu kelurahan ada ratusan sampel dari berbagai Sub-SLS, pengawas harus memfilter satu per satu di browser.
* **Solusi Script (Cross-Account)**:
  Script menggunakan akun **Admin/Dummy (level Kab/Kota)** untuk menarik **seluruh target ID penugasan berstatus `SUBMITTED` se-kelurahan sekaligus** tanpa batasan alokasi wilayah, lalu mengeksekusi *approval* massal menggunakan **sesi akun Pengawas** yang berhak menyetujui dokumen.

---

## 🔐 Cara Kerja Otomasi Login & 2FA / TOTP

Jika akun Admin/Dummy memerlukan verifikasi **Two-Factor Authentication (2FA / OTP)**:
1. **Otomatis Tanpa Sentuh (Headless)**:
   Jika Anda mengisi field `totp_secret` di berkas `credentials.json` dengan seed key akun (string base32 atau `otpauth://`), script akan menghitung kode 6 digit OTP secara lokal secara *real-time* menggunakan library `pyotp` dan langsung mengirimkannya ke server Keycloak tanpa perlu membuka HP.
2. **Semi-Otomatis (Input Terminal)**:
   Jika `totp_secret` dikosongkan, saat server mendeteksi tantangan 2FA, script akan menampilkan prompt di terminal:
   ```text
   [*] Akun memerlukan verifikasi Two-Factor Authentication (TOTP / OTP)...
   [?] Masukkan 6 digit kode OTP dari aplikasi Authenticator di HP Anda: ______
   ```
   Cukup masukkan 6 digit angka dari aplikasi authenticator di HP Anda. Kode hanya diminta **sekali di awal** untuk membentuk sesi aktif.

---

## 🛠️ Prasyarat (Prerequisites)

1. **Jaringan / VPN**: Script mengakses endpoint internal BPS (`https://fasih-sm.bps.go.id`). Wajib dijalankan di jaringan kantor atau melalui VPN/Dev Gateway (LXC 107).
2. **Python 3.x** terinstal pada sistem.
3. Install dependensi (termasuk `pyotp` untuk kalkulasi OTP lokal):
   ```bash
   pip install -r requirements.txt
   ```

---

## 📂 Konfigurasi Berkas

### 1. `approve/credentials.json` (Konfigurasi Akun Admin/Dummy)
Salin berkas contoh `approve/credentials.example.json` menjadi `approve/credentials.json`:
```bash
cp approve/credentials.example.json approve/credentials.json
```
Isi konfigurasinya:
```json
{
  "admin_account": {
    "login_type": "eksternal",
    "username": "3175.maegan@dummy.sobat.id",
    "password": "PasswordAkunAnda",
    "totp_secret": ""
  }
}
```
* **`login_type`**: 
  - `"eksternal"` : Untuk akun SSO Eksternal / Mitra Sobat.
  - `"sso_bps"`   : Untuk akun SSO Pegawai BPS resmi (`@bps.go.id`).
* **`totp_secret`**: Seed key base32 (opsional, kosongkan jika ingin memasukkan OTP via terminal saat script berjalan).
* **Catatan Keamanan**: Berkas `credentials.json` sudah didaftarkan ke `.gitignore` sehingga aman dan tidak akan ter-push ke repository git publik.

### 2. `approve/curl.txt` (Sesi Akun Pengawas)
Tempatkan salinan cURL dari browser saat login sebagai akun **Pengawas** (yang memiliki hak menyetujui dokumen).

---

## 🚀 Panduan Penggunaan Langkah demi Langkah

### Langkah 1: Siapkan cURL Akun Pengawas (`curl.txt`)
1. Buka browser dan login ke **https://fasih-sm.bps.go.id** menggunakan akun **Pengawas**.
2. Masuk ke halaman **Data Penugasan**.
3. Buka **Developer Tools** (tekan **F12** $\to$ tab **Network**).
4. Refresh atau filter tabel, cari request POST:
   `https://fasih-sm.bps.go.id/app/api/analytic/api/v2/assignment/datatable-all-user-survey-periode`
5. Klik kanan request $\to$ **Copy** $\to$ **Copy as cURL (bash)**.
6. Paste perintah cURL tersebut ke berkas `approve/curl.txt`.

### Langkah 2: Jalankan Script
Dari root direktori `script-fasih`, jalankan:
```bash
python3 main.py approve
```

### Langkah 3: Pilih Mode dan Masukkan Wilayah
1. Pilih menu nomor **`1`** (Auto-Fetch 1 Kelurahan via Akun Admin/Dummy).
2. Script otomatis melakukan login ke akun Admin/Dummy (meminta OTP via terminal jika `totp_secret` tidak diisi).
3. Masukkan **10 digit Kode Kelurahan/Desa** target saat diminta:
   ```text
   Masukkan 10 digit Kode Kelurahan target (contoh: 3175040006 untuk Koja): 3175040006
   ```
4. Script akan menyisir seluruh penugasan se-kelurahan dan memfilter dokumen yang berstatus **`SUBMITTED BY Pencacah`**.
5. Tekan **`Y`** untuk konfirmasi eksekusi approval massal:
   ```text
   Apakah Anda yakin ingin menyetujui (approve) X assignment ini via akun Pengawas? (Y/n): Y
   ```
6. Selesai! Seluruh sampel disetujui satu per satu dan riwayat lengkap dicatat di `approve/execution.log`.

---

## 📝 Penjelasan Status Hasil & Logging

* **`[SUKSES]`**: Dokumen berhasil di-approve (HTTP 200/201).
* **`[GAGAL]`**: Ditolak server (misal status dokumen sudah bukan submitted).
* **`[ERROR AUTH]`**: Sesi login browser kedaluwarsa. Salin ulang cURL baru ke `curl.txt` dan jalankan kembali script (progres ID tersimpan otomatis di `ids.json`).
