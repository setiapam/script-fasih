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

## 🔑 Cara Mendapatkan TOTP Secret Key dari Authenticator

TOTP Secret Key adalah teks rahasia (berisi huruf & angka base32) yang dijadikan dasar oleh aplikasi seperti Google Authenticator untuk menghasilkan 6 digit kode OTP yang berganti setiap 30 detik.

Ada 3 cara untuk mendapatkannya:

### Cara 1: Saat Pertama Kali Setup 2FA / Reset 2FA di Web SSO (Paling Mudah)
Ketika Anda mengaktifkan 2FA di portal SSO/Keycloak atau meminta admin mereset 2FA akun:
1. Di layar akan muncul **QR Code**.
2. Di bawah atau di dekat QR Code tersebut biasanya terdapat opsi teks: **`"Can't scan it?"`** / **`"Unable to scan code?"`** / **`"Secret Key / Entry Code"`**.
3. Klik tautan tersebut $\to$ akan muncul teks string panjang (misal: `JBSWY3DPEHPK3PXP` atau `4SDF7K...`).
4. Salin string teks tersebut dan tempel ke field `totp_secret` di `credentials.json`.

---

### Cara 2: Ekspor dari Google Authenticator (Jika Akun Sudah Ada di HP)
Google Authenticator memiliki fitur transfer akun:
1. Buka aplikasi **Google Authenticator** di HP.
2. Ketuk ikon menu garis tiga (kiri atas) atau menu opsi $\to$ Pilih **Transfer accounts** (Transfer akun) $\to$ **Export accounts** (Ekspor akun).
3. Pilih akun BPS / SSO yang ingin diekspor $\to$ Aplikasi akan menampilkan sebuah **QR Code besar**.
4. Foto / screenshot QR Code tersebut, lalu scan menggunakan QR Scanner biasa di HP atau laptop (misal via web `webqr.com` atau tool ZXing).
5. Hasil scan akan berupa teks berformat:
   `otpauth-migration://offline?data=...`
6. Teks migration tersebut bisa didecode menjadi `otpauth://totp/...` atau string base32 yang langsung bisa ditempelkan ke `totp_secret`.

---

### Cara 3: Menggunakan Password Manager (Bitwarden / 1Password / Vaultwarden)
Jika Anda menyimpan 2FA di password manager seperti **Bitwarden** atau **Vaultwarden**:
1. Buka item login akun di web/ekstensi Bitwarden/Vaultwarden.
2. Lihat field **Authenticator Key (TOTP)**.
3. Klik tombol **Edit** $\to$ string rahasia base32 akun Anda akan terlihat jelas.
4. Salin string tersebut dan tempelkan ke `credentials.json`.

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
    "totp_secret": "JBSWY3DPEHPK3PXP"
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
