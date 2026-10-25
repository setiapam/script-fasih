# Approve (Bulk Approval) - FASIH BPS API Automation

Modul ini melakukan approval penugasan FASIH secara massal. Alur dua akun
memisahkan **pengambilan daftar target** dari **pengiriman approval**.

## Pembagian tugas dua akun

| Tahap | Akun | Contoh | Kegunaan |
| --- | --- | --- | --- |
| Mengambil daftar | Admin/Dummy dengan akses wilayah yang cukup | `3175.maegan@dummy.sobat.id` | Membaca seluruh halaman penugasan dalam satu kelurahan dan memilih status `SUBMITTED BY Pencacah`. |
| Melakukan approval | Pengawas yang bertanggung jawab atas dokumen | `hanifah.afuwu` | Mengirim persetujuan untuk setiap ID target menggunakan sesi pengawas. |

Contoh kebutuhan: **Hanifah meng-approve Kelurahan Koja `3175040006`**.
Gunakan akun admin untuk mendapatkan daftar Koja, kemudian gunakan akun Hanifah
untuk menyetujui dokumen yang menjadi kewenangannya. Akun pengawas bisa memiliki
hak approval meskipun halaman daftar penugasannya kosong atau tidak bisa
menampilkan seluruh target sekaligus.

Alurnya:

```text
Admin/Dummy → daftar ID submitted di kelurahan target
           → periksa wilayah, periode, dan pengawas yang bertanggung jawab
Pengawas   → approve ID yang sudah diperiksa → execution.log
```

**Batasan penting:** menu 1 saat ini memfilter kelurahan dan status, tetapi belum
memfilter kepemilikan target berdasarkan username pengawas. Jika satu kelurahan
memiliki beberapa pengawas, daftar hasil admin belum tentu seluruhnya milik akun
approver. Siapkan daftar ID yang telah diverifikasi, lalu gunakan menu 4 untuk
approval khusus satu pengawas.

Status API yang dipakai adalah **`SUBMITTED BY Pencacah`**. Jangan menggantinya
dengan `SUBMITTED BY PPL`, karena filter tersebut dapat menghasilkan daftar kosong.

---

## 🔐 Cara Kerja Otomasi Login & 2FA / TOTP

Login otomatis kedua akun mendukung **Two-Factor Authentication (2FA / OTP)**.
Jika salah satu akun memerlukan OTP:
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

### 1. `approve/credentials.json` (Konfigurasi Akun)
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
    "password": "PasswordAkunAdmin",
    "totp_secret": ""
  },
  "approver_account": {
    "login_type": "sso_bps",
    "username": "hanifah.afuwu",
    "password": "PasswordAkunPengawas",
    "totp_secret": ""
  }
}
```
* **`admin_account`**: Akun untuk mengambil daftar pada menu 1. Sesi ini dipakai untuk membaca data; request approval memakai sesi pengawas.
* **`approver_account`**: Akun Pengawas (yang memiliki hak menyetujui dokumen). **Opsional**: jika bagian ini dikosongkan, script akan otomatis menggunakan sesi dari berkas `approve/curl.txt` seperti sebelumnya.
* **`login_type`**: 
  - `"eksternal"` : Untuk akun SSO Eksternal / Mitra Sobat.
  - `"sso_bps"`   : Untuk akun SSO Pegawai BPS resmi (`@bps.go.id`).
* **`totp_secret`**: Seed key base32 (opsional, jika kosong script memunculkan prompt input OTP di terminal saat login).
* **Penyimpanan lokal**: `credentials.json` sudah dicantumkan di `.gitignore`. Jangan menambahkan password, TOTP secret, atau cookie aktif ke Git.

### 2. `approve/curl.txt` (Metode Manual / Cadangan)
Jika Anda tidak mengisi `approver_account` di `credentials.json`, Anda tetap bisa menempelkan cURL request akun Pengawas dari browser ke `approve/curl.txt` seperti biasa.

**Sesi cURL ini harus milik pengawas**, bukan akun admin. `APPROVE_CURL_FILE`
hanya memilih berkas sesi pengawas; variabel ini tidak mengatur sesi admin.
Jika username dan password `approver_account` diisi, modul mencoba login otomatis
terlebih dahulu; cURL dipakai sebagai cadangan jika login tersebut gagal.

Untuk memakai berkas sesi lokal lain, tentukan `APPROVE_CURL_FILE` dengan path
absolut. Contoh, dari root repositori:
```bash
APPROVE_CURL_FILE="$PWD/approve/koja-approver.curl" python3 main.py approve
```
Jika daftar target dari akun admin sudah disimpan di `approve/id_spesifik.txt`,
pilih menu **4**. Modul memakai sesi pengawas untuk approval daftar tersebut.
Berkas sesi berisi cookie aktif; simpan hanya secara lokal dan kecualikan dari Git.

---

## Cara A: Dua akun login otomatis melalui `credentials.json`

Gunakan cara ini jika ingin modul mengambil daftar satu kelurahan dan melakukan
approval dalam satu proses.

1. Isi **kedua bagian** pada `approve/credentials.json` sesuai contoh di atas:
   `admin_account` untuk mengambil daftar, `approver_account` untuk approval.
   Dengan konfigurasi ini, tidak perlu menyalin cURL dari browser.
2. Pastikan `surveyPeriodId` di `approve/config.json` adalah periode kegiatan yang
   dimaksud. Jika belum tersedia, modul akan memintanya saat dijalankan.
3. Pastikan data wilayah tersedia di `approve/region_db.json` atau
   `tarik-data/region_db.json`, termasuk ID provinsi, kabupaten, kecamatan,
   dan kelurahan target untuk kegiatan tersebut.
4. Dari root repositori, jalankan:

   ```bash
   python3 main.py approve
   ```

5. Modul menyiapkan sesi **pengawas terlebih dahulu**. Jika diminta OTP, masukkan
   OTP akun pengawas yang sedang login.
6. Pilih **menu 1: Auto-Fetch 1 Kelurahan via Akun Admin/Dummy**. Modul kemudian
   login sebagai **admin** untuk mengambil daftar. Jika diminta OTP pada tahap
   ini, gunakan OTP akun admin.
7. Masukkan kode kelurahan lengkap, misalnya `3175040006` untuk **Kelurahan Koja**,
   bukan kode Kecamatan Koja `3175040`.
8. Modul mengambil seluruh halaman daftar melalui sesi admin dan memilih status
   `SUBMITTED BY Pencacah`. Pastikan cakupan tersebut memang menjadi kewenangan
   akun pengawas; menu 1 belum menyaring username pengawas secara otomatis.
9. Periksa jumlah target. Ketik `n` untuk membatalkan, atau `y` untuk menjalankan
   approval. **Menekan Enter juga menjalankan approval** pada implementasi saat ini.
10. Approval dikirim satu per satu melalui sesi **pengawas**, dan hasilnya dicatat
    di `approve/execution.log`.

## Cara B: Login admin otomatis + sesi pengawas dari browser

Gunakan cara ini jika pengawas sudah login di browser dan ingin memakai sesi itu.

1. Isi `admin_account` di `approve/credentials.json`. Kosongkan username/password
   `approver_account` agar modul langsung membaca sesi cURL pengawas.
2. Login sebagai **pengawas**, misalnya `hanifah.afuwu`, di browser tersendiri.
   Buka Developer Tools (**F12 → Network**), lalu buka atau refresh Data Penugasan
   pada kegiatan yang dimaksud.
3. Cari request POST `datatable-all-user-survey-periode`, pilih
   **Copy → Copy as cURL (bash)**, lalu simpan ke `approve/curl.txt`.
   Request tetap dapat menyediakan sesi meskipun hasil tabel pengawas kosong.
4. Jalankan `python3 main.py approve`, lalu pilih **menu 1** dan masukkan kode
   kelurahan. Pengambilan daftar memakai login admin; approval memakai sesi
   pengawas dari cURL. Periksa target dan konfirmasi seperti pada Cara A.

Dua browser atau dua profil terpisah dapat digunakan agar login admin dan pengawas
tidak saling mengganti. Pastikan identitas akun sebelum menyalin setiap sesi.

## Cara C: Daftar dari admin sudah disiapkan, approval memakai menu 4

Gunakan cara ini untuk daftar yang telah diperiksa khusus untuk satu pengawas,
misalnya daftar Koja milik Hanifah yang diperoleh dari sesi admin di browser.

1. Ambil seluruh halaman daftar memakai sesi **admin**, lalu pilih dokumen yang:
   - berada pada survei/periode yang dimaksud;
   - berada di kelurahan target;
   - berstatus tepat `SUBMITTED BY Pencacah`;
   - memiliki tanggung jawab approval aktif (`OPEN`) untuk pengawas tujuan.
2. Simpan ID hasil pemeriksaan ke `approve/id_spesifik.txt`, satu ID per baris.
   Template tersedia di `approve/id_spesifik.example.txt`.
3. Siapkan sesi **pengawas** melalui `approver_account`, `approve/curl.txt`, atau
   berkas cURL lokal yang dipilih dengan `APPROVE_CURL_FILE`.
4. Jika memakai berkas sesi lokal Hanifah yang sudah disiapkan, jalankan dari root:

   ```bash
   APPROVE_CURL_FILE="$PWD/approve/koja-approver.curl" python3 main.py approve
   ```

5. Pilih **menu 4**, periksa jumlah ID yang dimuat, lalu ketik `y` untuk approval
   atau `n` untuk membatalkan.

**Menu 4 hanya membaca ID yang diberikan.** Menu ini tidak mengambil ulang daftar,
tidak memeriksa ulang status atau pengawas, dan tidak memakai sesi admin saat
approval. Karena itu, pemeriksaan pada langkah 1 perlu dilakukan sebelum eksekusi.

**Dukungan dua sesi browser saat ini:** `APPROVE_CURL_FILE` sudah dapat membaca
cURL pengawas. Namun, menu 1 belum membaca berkas cURL admin secara langsung;
menu tersebut masih memakai login username/password admin. Jika hanya memiliki
sesi browser kedua akun, pengambilan dan pemeriksaan daftar admin perlu dilakukan
terpisah sebelum menu 4. Berkas lokal `koja-admin.curl` dan `koja-approver.curl`
merupakan sesi yang disiapkan sebelumnya, bukan berkas bawaan repositori; sesi ini
bisa kedaluwarsa dan perlu diperbarui dari browser akun masing-masing.

---

## 📝 Penjelasan Status Hasil & Logging

* **`[SUKSES]`**: Server mengembalikan HTTP 200/201 dan `success: true`.
* **`[GAGAL]`**: Ditolak server (misal status dokumen sudah bukan submitted).
* **`[ERROR AUTH]`**: Sesi pengawas kedaluwarsa. Perbarui sesi pengawas pada berkas cURL yang dipakai, atau login kembali jika memakai kredensial.
* **`ids.json`** menyimpan daftar target, bukan checkpoint keberhasilan. Sebelum menjalankan ulang setelah proses terputus, periksa log dan status terbaru agar daftar ulang hanya berisi target yang masih perlu di-approve.
* Daftar DataTables dapat terlambat mencerminkan hasil approval. Tunggu sebentar lalu periksa ulang status melalui akun admin.


## Laporan Excel setiap eksekusi

Setiap pemanggilan modul menghasilkan `laporan_eksekusi_approve.xlsx` di folder modul,
dengan sheet **Ringkasan** dan **Hasil**. Sheet Hasil memuat ID target, nama, wilayah,
periode (jika tersedia), status, keterangan, kode HTTP (jika tersedia), dan waktu.
Status membedakan `BERHASIL`, `GAGAL`, `ERROR`, `SESI EXPIRED`, `DILEWATI`,
dan `BELUM DIPROSES`. Keluaran khusus modul yang sudah ada tetap dipertahankan.

Laporan diperbarui saat hasil tiap target dicatat, termasuk ketika sesi habis
atau proses dihentikan dengan Ctrl+C. Target yang belum mendapat hasil tetap
bertanda `BELUM DIPROSES`; status ini tidak berarti berhasil atau gagal. Jika
persiapan gagal sebelum daftar target terbaca, laporan berisi ringkasan dengan
nol target.

Berkas di atas menunjukkan eksekusi terbaru. Salinan setiap eksekusi disimpan
di `reports/` dalam folder modul dengan nama bertanggal dan waktu, sehingga
riwayat sebelumnya tetap tersedia. Laporan merupakan catatan hasil menurut
respons API atau cache saat eksekusi, bukan pemeriksaan ulang status server
dan bukan checkpoint untuk mengulang aksi secara otomatis. Berkas hasil
dikecualikan dari Git karena dapat memuat data penugasan.
