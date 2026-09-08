#!/usr/bin/env python3
"""
Modul: DTSEN
Deskripsi: Mencocokkan data target DTSEN dari berkas Excel ke API datatable penugasan FASIH BPS,
lalu memperbarui Kolom I (Keterangan) dan Kolom J (Kolom 1) sesuai ketentuan:
  a. 'sdh didata' di kolom I:
     - Ditemukan 1 row match, status != open, ada nomor urut bangunan (bukan -) -> kolom J = 'ditemukan'
     - Ditemukan 1 row match, status != open, tidak ada nomor urut bangunan (-) -> kolom J = 'tidak ditemukan'
     - Ditemukan > 1 row match -> kolom J = 'ditemukan lebih dari 1 row'
  b. 'blm didata' di kolom I:
     - Ditemukan 1 row match dan status == open (kolom J kosong atau '-')
     - Hasil pencarian tidak ditemukan sama sekali / 0 row (kolom J kosong atau '-')
"""

import os
import sys
import re
import json
import time
import datetime
import shlex
import requests
import openpyxl

MODULE_CURL_PATH = "dtsen/curl.txt"
CONFIG_FILE = "config.json"
CHECKPOINT_FILE = "completed_dtsen.json"
REGION_DB_FILE = "region_db.json"
DEFAULT_INPUT_EXCEL = "/home/murphi/Documents/dtsen_koja.xlsx"

# Mapping nama kelurahan / kode kelurahan ke fullCode standar BPS (3175040xxx)
KELURAHAN_MAPPING = {
    'RAWABADAK SELATAN': '3175040001',
    'RAWA BADAK SELATAN': '3175040001',
    '31.72.03.1006': '3175040001',

    'TUGU SELATAN': '3175040002',
    '31.72.03.1005': '3175040002',

    'TUGU UTARA': '3175040003',
    '31.72.03.1002': '3175040003',

    'LAGOA': '3175040004',
    '31.72.03.1003': '3175040004',

    'RAWABADAK UTARA': '3175040005',
    'RAWA BADAK UTARA': '3175040005',
    '31.72.03.1004': '3175040005',

    'KOJA': '3175040006',
    '31.72.03.1001': '3175040006'
}


def is_session_expired(response):
    """Mendeteksi apakah response API menunjukkan sesi cURL/login telah expired."""
    if response.status_code in (401, 403):
        return True
    content_type = response.headers.get("Content-Type", "")
    if "text/html" in content_type:
        text_lower = response.text.lower()
        if any(k in text_lower for k in ("login", "keycloak", "sso", "unauthorized")):
            return True
    return False


def show_session_expired_banner(completed_count=0, total_count=0):
    """Menampilkan instruksi saat sesi expired."""
    print("\n" + "=" * 65)
    print("⚠️  [SESI LOGIN KADALUARSA / EXPIRED] (HTTP 401/403)")
    print("=" * 65)
    print(" Sesi login FASIH BPS atau token cURL Anda telah habis masa berlakunya.")
    print(" BUKAN karena data tidak ada di server BPS, melainkan akses ditolak.")
    print("\n Langkah mudah untuk melanjutkan:")
    print("  1. Buka browser dan login ulang ke https://fasih-sm.bps.go.id")
    print("  2. Buka tab Network (F12), lakukan interaksi/refresh halaman data.")
    print(f"  3. Salin (Copy as cURL) request terbaru ke berkas: {MODULE_CURL_PATH}")
    print("  4. Jalankan ulang script (seluruh progress yang berhasil tersimpan di Excel).")
    if total_count > 0:
        print(f"\n Progress saat ini: {completed_count} dari {total_count} baris selesai.")
    print("=" * 65 + "\n")


def parse_curl(filepath):
    """Mengekstrak URL, headers, cookies, xsrf-token, dan surveyPeriodId dari curl.txt."""
    if not os.path.exists(filepath):
        print(f"❌ File '{filepath}' tidak ditemukan!")
        return None

    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read().strip()

    # Ekstrak surveyPeriodId
    sp_match = re.search(r'surveyPeriodId["\']?\s*[:=]\s*["\']([a-f0-9\-]{36})["\']', content, re.IGNORECASE)
    if not sp_match:
        sp_match = re.search(r'/surveys/[a-f0-9\-]{36}/([a-f0-9\-]{36})', content, re.IGNORECASE)
    survey_period_id = sp_match.group(1) if sp_match else ""

    # Normalisasi baris sambungan backslash
    content_clean = re.sub(r"\\\r?\n", " ", content)

    try:
        tokens = shlex.split(content_clean)
    except Exception:
        tokens = content_clean.split()

    url = ""
    headers = {}
    cookies = ""
    data_raw = ""

    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token.lower() in ("curl", "curl.exe"):
            i += 1
            continue
        elif token in ("--url", "-u"):
            if i + 1 < len(tokens):
                url = tokens[i + 1]
                i += 2
                continue
        elif token in ("-H", "--header"):
            if i + 1 < len(tokens):
                h = tokens[i + 1]
                if ":" in h:
                    k, v = h.split(":", 1)
                    headers[k.strip()] = v.strip()
                i += 2
                continue
        elif token in ("-b", "--cookie"):
            if i + 1 < len(tokens):
                cookies = tokens[i + 1]
                i += 2
                continue
        elif token in ("--data", "--data-raw", "-d"):
            if i + 1 < len(tokens):
                data_raw = tokens[i + 1]
                i += 2
                continue
        elif token.startswith("http://") or token.startswith("https://"):
            url = token

        i += 1

    if not url:
        url = "https://fasih-sm.bps.go.id/app/api/analytic/api/v2/assignment/datatable-all-user-survey-periode"

    if cookies:
        headers["Cookie"] = cookies

    xsrf_token = headers.get("x-xsrf-token") or headers.get("X-XSRF-TOKEN")
    if not xsrf_token and "Cookie" in headers:
        m = re.search(r"XSRF-TOKEN=([^;]+)", headers["Cookie"])
        if m:
            xsrf_token = m.group(1)
            headers["x-xsrf-token"] = xsrf_token

    return {
        "url": url,
        "headers": headers,
        "survey_period_id": survey_period_id,
        "data_raw": data_raw
    }


def resolve_group_id(headers, survey_period_id, datatable_url):
    """
    Mengambil groupId secara otomatis dengan melakukan 1 query awal ke datatable
    lalu membaca regionMetadata.id atau region.groupId dari server BPS.
    """
    payload = {
        "start": 0,
        "length": 1,
        "columns": [{"data": "id", "orderable": True}],
        "order": [],
        "search": {"value": "", "regex": False},
        "assignmentExtraParam": {
            "surveyPeriodId": survey_period_id,
            "assignmentErrorStatusType": -1,
            "filterTargetType": "TARGET_ONLY"
        }
    }
    try:
        r = requests.post(datatable_url, headers=headers, json=payload, timeout=15)
        if r.status_code == 200:
            res = r.json()
            items = res.get("searchData", [])
            if items:
                first = items[0]
                meta = first.get("regionMetadata")
                if isinstance(meta, dict) and meta.get("id"):
                    return meta["id"]
                reg = first.get("region")
                if isinstance(reg, dict) and reg.get("groupId"):
                    return reg["groupId"]
    except Exception as e:
        print(f"⚠️ Gagal mendeteksi groupId otomatis dari datatable: {e}")

    # Fallback group ID default SE2026 jika tidak terdeteksi
    return "a45adac1-e711-4c15-b3f9-1f30fc151565"


def load_or_fetch_region_db(headers, group_id):
    """
    Memuat region_db.json lokal. Jika level 4 untuk kelurahan Koja belum lengkap,
    mengambil data level 4 dari API region BPS secara dinamis.
    """
    db = {}
    if os.path.exists(REGION_DB_FILE):
        try:
            with open(REGION_DB_FILE, "r", encoding="utf-8") as f:
                db = json.load(f)
        except Exception:
            db = {}

    # Periksa apakah level 4 Koja (3175040xxx) sudah lengkap di DB
    needed_codes = ["3175040001", "3175040002", "3175040003", "3175040004", "3175040005", "3175040006"]
    missing = [c for c in needed_codes if c not in db]

    if missing and group_id:
        print(f"[*] Mengambil informasi region level 4 dari API untuk Kecamatan Koja...")
        api_url = "https://fasih-sm.bps.go.id/app/api/region/api/v1/region/level4"
        params = {"groupId": group_id, "level3FullCode": "3175040"}
        try:
            r = requests.get(api_url, headers=headers, params=params, timeout=15)
            if r.status_code == 200:
                resp_json = r.json()
                items = resp_json.get("data", []) if isinstance(resp_json, dict) else resp_json
                if isinstance(items, list):
                    for item in items:
                        fcode = str(item.get("fullCode", "")).strip()
                        if fcode:
                            db[fcode] = item
                    with open(REGION_DB_FILE, "w", encoding="utf-8") as f:
                        json.dump(db, f, indent=2, ensure_ascii=False)
                    print(f"   [+] Database region level 4 berhasil diperbarui ({len(items)} kelurahan).")
        except Exception as e:
            print(f"   [!] Gagal mengambil region level 4: {e}")

    return db


def get_region4_id(kelurahan_raw, kode_kelurahan_raw, region_db):
    """
    Mendapatkan region4Id UUID berdasarkan teks nama kelurahan atau kode kelurahan.
    """
    norm_name = str(kelurahan_raw or "").strip().upper()
    norm_code = str(kode_kelurahan_raw or "").strip()

    target_fullcode = KELURAHAN_MAPPING.get(norm_name) or KELURAHAN_MAPPING.get(norm_code)
    if not target_fullcode:
        # Coba cari di region_db berdasarkan kesamaan nama
        for fcode, rinfo in region_db.items():
            if str(rinfo.get("level")) == "4":
                rname = str(rinfo.get("name", "")).strip().upper()
                if norm_name and (norm_name == rname or norm_name in rname or rname in norm_name):
                    target_fullcode = fcode
                    break

    if target_fullcode and target_fullcode in region_db:
        return region_db[target_fullcode].get("id")

    return None


def query_fasih_datatable(headers, datatable_url, survey_period_id, region4_id, nama_search, max_retries=3):
    """
    Mengeksekusi request pencarian ke API datatable FASIH BPS.
    Dilengkapi mekanisme otomatis retry dengan exponential backoff saat terkena HTTP 429 (Rate Limit).
    Returns: (status_code, list of item dict)
    """
    clean_search = str(nama_search or "").strip()
    if not clean_search:
        return 200, []

    payload = {
        "start": 0,
        "length": 10,
        "columns": [{"data": "id", "orderable": True}],
        "order": [],
        "search": {"value": f'"{clean_search}"', "regex": False},
        "assignmentExtraParam": {
            "region4Id": region4_id,
            "surveyPeriodId": survey_period_id,
            "assignmentErrorStatusType": -1,
            "filterTargetType": "TARGET_ONLY"
        }
    }

    retry_delay = 5
    for attempt in range(max_retries):
        try:
            resp = requests.post(datatable_url, headers=headers, json=payload, timeout=25)
            if is_session_expired(resp):
                return 401, []

            if resp.status_code == 429:
                print(f"   [!] Rate limit (HTTP 429). Menunggu {retry_delay} detik sebelum mencoba ulang...")
                time.sleep(retry_delay)
                retry_delay *= 2
                continue

            if resp.status_code == 200:
                res_json = resp.json()
                search_data = res_json.get("searchData", [])
                return 200, search_data
            else:
                return resp.status_code, []
        except requests.exceptions.RequestException:
            time.sleep(2)

    return 429, []


def evaluate_dtsen_rules(search_results):
    """
    Mengevaluasi hasil pencarian berdasarkan ketentuan:
    a. 'sdh didata' di kolom I:
       - 1 row match, status != open, ada nomor urut bangunan (bukan -) -> kolom J = 'ditemukan'
       - 1 row match, status != open, tidak ada nomor urut bangunan (-) -> kolom J = 'tidak ditemukan'
       - > 1 row match -> kolom J = 'ditemukan lebih dari 1 row'
    b. 'blm didata' di kolom I:
       - 1 row match, status == open -> kolom J = '-'
       - 0 row match / tidak ketemu -> kolom J = '-'
    """
    count = len(search_results)

    if count == 0:
        return "blm didata", ""

    if count > 1:
        return "sdh didata", "ditemukan lebih dari 1 row"

    # Tepat 1 row match
    item = search_results[0]
    status_alias = str(item.get("assignmentStatusAlias", "")).strip().upper()
    status_id = item.get("assignmentStatusId")

    # Status OPEN (id=0 atau alias='OPEN')
    is_open = (status_alias == "OPEN") or (status_id == 0)

    if is_open:
        return "blm didata", ""

    # Status != OPEN -> cek nomor urut bangunan
    # Pada sistem FASIH: data3 adalah 'No Urut Bangunan / IDSBR' (misal: '85 / ' atau '- / ' atau '-')
    no_urut_raw = str(item.get("data3", "")).strip()

    # Ekstrak bagian sebelum slash jika ada format 'NO / IDSBR'
    parts = no_urut_raw.split("/", 1)
    no_bangunan = parts[0].strip()

    has_nomor_bangunan = bool(no_bangunan and no_bangunan != "-" and no_bangunan != "")

    if has_nomor_bangunan:
        return "sdh didata", "ditemukan"
    else:
        return "sdh didata", "tidak ditemukan"


def main():
    print("=" * 60)
    print("      MODUL AUTOMATION: DTSEN FASIH BPS")
    print("=" * 60)

    # 1. Parsing cURL
    curl_file = "curl.txt"
    if not os.path.exists(curl_file):
        print(f"❌ File '{curl_file}' tidak ditemukan di folder 'dtsen/'.")
        print("   Silakan salin cURL datatable dari browser ke 'dtsen/curl.txt'.")
        return

    parsed = parse_curl(curl_file)
    if not parsed or not parsed["headers"]:
        print("❌ Gagal membaca headers atau cookies dari 'dtsen/curl.txt'.")
        return

    survey_period_id = parsed["survey_period_id"]
    if not survey_period_id:
        # Coba ambil dari config.json
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as cf:
                    cdata = json.load(cf)
                    survey_period_id = cdata.get("surveyPeriodId", "")
            except Exception:
                pass

    if not survey_period_id:
        print("❌ surveyPeriodId tidak ditemukan di 'curl.txt' maupun 'config.json'.")
        return

    # Simpan surveyPeriodId ke config.json
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as cf:
            json.dump({"surveyPeriodId": survey_period_id}, cf, indent=2)
    except Exception:
        pass

    datatable_url = parsed["url"]
    headers = parsed["headers"]

    # 2. Otomasi Region & Group ID
    print("[*] Mendeteksi konfigurasi wilayah...")
    group_id = resolve_group_id(headers, survey_period_id, datatable_url)
    region_db = load_or_fetch_region_db(headers, group_id)

    # 3. Validasi Berkas Excel Input
    excel_path = DEFAULT_INPUT_EXCEL
    if len(sys.argv) > 1 and sys.argv[1].endswith(".xlsx"):
        excel_path = sys.argv[1]
    elif not os.path.exists(excel_path):
        if os.path.exists("dtsen_sample.xlsx"):
            excel_path = "dtsen_sample.xlsx"
        else:
            excel_path = input("Masukkan path berkas Excel (.xlsx): ").strip()

    if not os.path.exists(excel_path):
        print(f"❌ Berkas Excel tidak ditemukan: {excel_path}")
        return

    print(f"[*] Membuka berkas Excel: '{excel_path}'...")
    wb = openpyxl.load_workbook(excel_path)
    ws = wb.active
    if ws is None:
        print("❌ Gagal membaca sheet aktif pada file Excel.")
        return

    # Validasi header Kolom I dan Kolom J
    header_col_i = ws.cell(row=1, column=9).value
    header_col_j = ws.cell(row=1, column=10).value
    print(f"[*] Kolom 9 (I): '{header_col_i}' | Kolom 10 (J): '{header_col_j}'")

    if not header_col_i:
        ws.cell(row=1, column=9, value="Keterangan")
    if not header_col_j:
        ws.cell(row=1, column=10, value="Kolom 1")

    # Logging setup
    log_file = "execution.log"
    timestamp_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_file, "a", encoding="utf-8") as lf:
        lf.write(f"\n==================================================\n")
        lf.write(f"EKSEKUSI DTSEN: {timestamp_str}\n")
        lf.write(f"Excel target: {excel_path}\n")
        lf.write(f"==================================================\n")

    # 4. Memproses Baris Data
    total_rows = ws.max_row
    print(f"[*] Total baris pada sheet: {total_rows}")

    sukses = 0
    gagal = 0
    skipped = 0
    total_target = 0
    failed_details = []

    # Simpan per batch agar hemat I/O
    BATCH_SAVE_SIZE = 50

    try:
        for row_idx in range(2, total_rows + 1):
            total_target += 1
            kode_kel = ws.cell(row=row_idx, column=3).value
            nama_kel = ws.cell(row=row_idx, column=4).value
            nama_anggota = ws.cell(row=row_idx, column=7).value
            val_col_i = ws.cell(row=row_idx, column=9).value
            val_col_j = ws.cell(row=row_idx, column=10).value

            # Jika sudah pernah diproses dan terisi, lewati (resumable)
            if val_col_i and str(val_col_i).strip() in ("sdh didata", "blm didata"):
                skipped += 1
                sukses += 1
                continue

            if not nama_anggota or str(nama_anggota).strip() == "":
                # Tidak ada nama anggota
                ws.cell(row=row_idx, column=9, value="blm didata")
                ws.cell(row=row_idx, column=10, value="")
                sukses += 1
                continue

            nama_search = str(nama_anggota).strip()
            region4_id = get_region4_id(nama_kel, kode_kel, region_db)

            if not region4_id:
                msg = f"Baris {row_idx} | Kelurahan '{nama_kel}' ({kode_kel}) tidak ditemukan di region database."
                print(f"[GAGAL] {msg}")
                gagal += 1
                failed_details.append({"baris": row_idx, "nama": nama_search, "alasan": msg})
                continue

            # Hit API Datatable
            status_code, results = query_fasih_datatable(headers, datatable_url, survey_period_id, region4_id, nama_search)

            if status_code == 401 or status_code == 403:
                show_session_expired_banner(completed_count=sukses, total_count=total_target)
                wb.save(excel_path)
                print(f"[*] Progress berhasil disimpan ke '{excel_path}'.")
                return

            if status_code != 200:
                msg = f"Baris {row_idx} | HTTP Error {status_code} saat mencari '{nama_search}'"
                print(f"[ERROR] {msg}")
                gagal += 1
                failed_details.append({"baris": row_idx, "nama": nama_search, "alasan": msg})
                time.sleep(1)
                continue

            # Evaluasi aturan DTSEN
            status_i, status_j = evaluate_dtsen_rules(results)

            ws.cell(row=row_idx, column=9, value=status_i)
            ws.cell(row=row_idx, column=10, value=status_j)
            sukses += 1

            print(f"[SUKSES] Baris {row_idx}/{total_rows} | {nama_search} ({nama_kel}) -> Col I: '{status_i}' | Col J: '{status_j}' (Hits: {len(results)})")

            # Batch save berkala
            if sukses % BATCH_SAVE_SIZE == 0:
                wb.save(excel_path)

            # Jeda sopan agar tidak terkena rate-limiting WAF
            time.sleep(1.0)

    except KeyboardInterrupt:
        print("\n\n[!] Eksekusi dihentikan oleh pengguna (Ctrl+C). Menyimpan perubahan...")
    finally:
        wb.save(excel_path)
        print(f"[*] Perubahan berhasil disimpan ke: '{excel_path}'")

        # Tulis detail kegagalan ke execution.log
        with open(log_file, "a", encoding="utf-8") as lf:
            lf.write(f"\nHASIL: Sukses: {sukses} (Termasuk resume: {skipped}), Gagal: {gagal}, Total: {total_target}\n")
            if failed_details:
                lf.write("\nRINCIAN TARGET GAGAL:\n")
                for fd in failed_details:
                    lf.write(f"- Baris {fd['baris']} | {fd['nama']}: {fd['alasan']}\n")
            lf.write("--------------------------------------------------\n")

    # 5. Ringkasan Akhir Standar
    print("\n" + "=" * 50)
    print("           RINGKASAN AKHIR PENGEKSEKUSIAN")
    print("=" * 50)
    print(f" - Berhasil diproses : {sukses}")
    if skipped > 0:
        print(f"   (Termasuk resume) : {skipped}")
    print(f" - Gagal diproses    : {gagal}")
    print(f" - Total target      : {total_target}")
    print("=" * 50)


if __name__ == "__main__":
    main()
