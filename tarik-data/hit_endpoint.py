import json
import shlex
import requests
import datetime
import os
import copy
import time
import pandas as pd

# ============================================================
#  KONFIGURASI
# ============================================================
BASE_URL = "https://fasih-sm.bps.go.id/app/api/region/api/v1/region"
DATA_URL = "https://fasih-sm.bps.go.id/app/api/analytic/api/v2/assignment/datatable-all-user-survey-periode"
REGION_DB_FILE = "region_db.json"
RESULT_FILE = "result.xlsx"
TARGET_FILE = "subsls_target.xlsx"
LOG_FILE = "execution.log"
REQUEST_DELAY = 0.3  # Delay antar request (detik) untuk menghindari rate-limit


# ============================================================
#  CURL PARSER
# ============================================================
def parse_curl(curl_command):
    """
    Membaca raw cURL command, mengekstrak headers, cookies, URL, dan data payload.
    """
    curl_command = curl_command.replace('\\\n', ' ').replace('\\\r\n', ' ')
    try:
        tokens = shlex.split(curl_command)
    except ValueError as e:
        print(f"[!] Warning shlex: {e}. Mencoba splitting manual.")
        tokens = curl_command.split()

    url = None
    headers = {}
    method = 'GET'
    data = None
    cookies_str = None

    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token.lower() == 'curl':
            i += 1
            continue

        if token in ('-H', '--header') and i + 1 < len(tokens):
            header_val = tokens[i+1]
            if ':' in header_val:
                k, v = header_val.split(':', 1)
                headers[k.strip()] = v.strip()
            i += 2
        elif token in ('-b', '--cookie') and i + 1 < len(tokens):
            cookies_str = tokens[i+1]
            i += 2
        elif token in ('-d', '--data', '--data-raw', '--data-binary') and i + 1 < len(tokens):
            data = tokens[i+1]
            method = 'POST'
            i += 2
        elif token in ('-X', '--request') and i + 1 < len(tokens):
            method = tokens[i+1].upper()
            i += 2
        elif token.startswith('http://') or token.startswith('https://'):
            url = token
            i += 1
        elif token.startswith("'http://") or token.startswith("'https://") or \
             token.startswith('"http://') or token.startswith('"https://'):
            url = token.strip("'\"")
            i += 1
        else:
            if not token.startswith('-') and url is None:
                if '://' in token or '.' in token or '/' in token:
                    url = token.strip("'\"")
            i += 1

    if cookies_str:
        if 'Cookie' in headers:
            headers['Cookie'] = headers['Cookie'] + '; ' + cookies_str
        else:
            headers['Cookie'] = cookies_str

    # Hapus Host dan Content-Length bawaan cURL agar requests bisa merakit sendiri
    headers.pop('Host', None)
    headers.pop('Content-Length', None)

    return {
        'url': url,
        'headers': headers,
        'method': method,
        'data': data
    }


def extract_session_headers(parsed_curl):
    """
    Mengekstrak headers autentikasi/session dari parsed cURL.
    Menghapus content-type agar requests bisa set sendiri.
    """
    headers = dict(parsed_curl['headers'])
    # Biarkan content-type untuk JSON request
    return headers


# ============================================================
#  REGION API: Membangun Database Wilayah
# ============================================================
def fetch_region_level(headers, level, group_id, parent_code=None):
    """
    Mengambil data region dari API untuk level tertentu.
    Returns: list of dict dari response API.
    """
    params = {"groupId": group_id}
    if parent_code:
        parent_key = f"level{level - 1}FullCode"
        params[parent_key] = parent_code

    url = f"{BASE_URL}/level{level}"
    try:
        response = requests.get(url, headers=headers, params=params)
        if response.status_code == 200:
            data = response.json()
            # API bisa mengembalikan list langsung atau dict dengan key 'data'
            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                return data.get('data', data.get('content', [data]))
            return [data]
        else:
            print(f"   [GAGAL] HTTP {response.status_code} untuk level{level} (parent: {parent_code})")
            return []
    except requests.exceptions.RequestException as e:
        print(f"   [ERROR] Gagal mengambil level{level} (parent: {parent_code}): {e}")
        return []


def extract_parent_codes(subsls_code):
    """
    Dari kode fullCode sub SLS, pecah menjadi kode parent di setiap level.
    Struktur fullCode:
      - Level 1 (Provinsi)  : 2 digit pertama   → "31"
      - Level 2 (Kab/Kota)  : 4 digit pertama   → "3175"
      - Level 3 (Kecamatan) : 7 digit pertama   → "3175010"
      - Level 4 (Desa)      : 10 digit pertama  → "3175010001"
      - Level 5 (SLS)       : 14 digit pertama  → "31750100010001"
      - Level 6 (Sub SLS)   : seluruh kode      → "317501000100010001"
    """
    return {
        1: subsls_code[:2],
        2: subsls_code[:4],
        3: subsls_code[:7],
        4: subsls_code[:10],
        5: subsls_code[:14],
        6: subsls_code,
    }


def build_region_database(headers, group_id, target_subsls_codes):
    """
    Membangun database wilayah HANYA untuk wilayah yang bersesuaian
    dengan daftar kode sub SLS yang ditargetkan.

    Returns: dict dengan key = fullCode, value = region info dict
    """
    region_db = {}

    # Kumpulkan semua parent codes unik per level dari target
    needed = {1: set(), 2: set(), 3: set(), 4: set(), 5: set(), 6: set()}
    for code in target_subsls_codes:
        parents = extract_parent_codes(code)
        for lvl, parent_code in parents.items():
            needed[lvl].add(parent_code)

    level_names = {1: "Provinsi", 2: "Kab/Kota", 3: "Kecamatan",
                   4: "Desa/Kel", 5: "SLS", 6: "Sub SLS"}

    print(f"\n[*] Wilayah unik yang perlu diambil dari target:")
    for lvl in sorted(needed.keys()):
        print(f"    - {level_names[lvl]}: {len(needed[lvl])} wilayah")

    # === LEVEL 1: Provinsi ===
    prov_codes_needed = needed[1]
    print(f"\n[*] Mengambil data Level 1 (Provinsi) - {len(prov_codes_needed)} target...")
    prov_list = fetch_region_level(headers, 1, group_id)
    found = 0
    for prov in prov_list:
        prov_code = prov.get('fullCode', '')
        if prov_code in prov_codes_needed:
            region_db[prov_code] = {
                "id": prov.get('id', ''),
                "fullCode": prov_code,
                "name": prov.get('name', ''),
                "level": 1
            }
            found += 1
    print(f"    Ditemukan {found}/{len(prov_codes_needed)} provinsi.")
    time.sleep(REQUEST_DELAY)

    # === LEVEL 2-6: Ambil per parent yang dibutuhkan saja ===
    level_config = [
        (2, 1, "Kab/Kota"),
        (3, 2, "Kecamatan"),
        (4, 3, "Desa/Kel"),
        (5, 4, "SLS"),
        (6, 5, "Sub SLS"),
    ]

    for level, parent_level, label in level_config:
        codes_needed = needed[level]
        # Ambil parent codes yang sudah berhasil di-fetch
        parent_codes_to_query = set()
        for code in codes_needed:
            parents = extract_parent_codes(code)
            parent_code = parents[parent_level]
            if parent_code in region_db:
                parent_codes_to_query.add(parent_code)

        print(f"[*] Mengambil data Level {level} ({label}) - {len(codes_needed)} target dari {len(parent_codes_to_query)} parent...")
        found = 0
        for parent_code in sorted(parent_codes_to_query):
            children = fetch_region_level(headers, level, group_id, parent_code)
            for child in children:
                child_code = child.get('fullCode', '')
                if child_code in codes_needed:
                    region_db[child_code] = {
                        "id": child.get('id', ''),
                        "fullCode": child_code,
                        "name": child.get('name', ''),
                        "level": level,
                        "parentCode": parent_code
                    }
                    found += 1
            time.sleep(REQUEST_DELAY)
        print(f"    Ditemukan {found}/{len(codes_needed)} {label.lower()}.")

    return region_db


def resolve_region_hierarchy(region_db, subsls_code):
    """
    Dari kode sub SLS, ambil semua region ID (level 1-6) menggunakan
    parent codes yang diturunkan dari fullCode.

    Returns: dict dengan key region1Id ... region6Id, atau None jika tidak ditemukan.
    """
    parents = extract_parent_codes(subsls_code)
    result = {}
    level_key_map = {
        1: 'region1Id', 2: 'region2Id', 3: 'region3Id',
        4: 'region4Id', 5: 'region5Id', 6: 'region6Id'
    }

    for lvl, key in level_key_map.items():
        code = parents[lvl]
        if code not in region_db:
            return None
        result[key] = region_db[code]['id']

    return result


# ============================================================
#  DATA FETCHER: Mengambil data berdasarkan sub SLS
# ============================================================
def fetch_data_for_subsls(headers, base_payload, region_ids):
    """
    Mengambil data dari endpoint datatable-all-user-survey-periode
    untuk satu sub SLS tertentu. Mendukung pagination.

    Returns: list of data records
    """
    payload = copy.deepcopy(base_payload)

    # Set region IDs
    if 'assignmentExtraParam' not in payload:
        payload['assignmentExtraParam'] = {}

    payload['assignmentExtraParam']['region1Id'] = region_ids['region1Id']
    payload['assignmentExtraParam']['region2Id'] = region_ids['region2Id']
    payload['assignmentExtraParam']['region3Id'] = region_ids['region3Id']
    payload['assignmentExtraParam']['region4Id'] = region_ids['region4Id']
    payload['assignmentExtraParam']['region5Id'] = region_ids['region5Id']
    payload['assignmentExtraParam']['region6Id'] = region_ids['region6Id']

    all_records = []
    start = 0
    length = payload.get('length', 100)

    while True:
        payload['start'] = start
        try:
            response = requests.post(DATA_URL, headers=headers, json=payload)
            if response.status_code != 200:
                return None, f"HTTP {response.status_code}"

            res_json = response.json()
            data_list = res_json.get('data') or res_json.get('searchData') or []

            if not data_list:
                break

            all_records.extend(data_list)

            if len(data_list) < length:
                break

            start += length
            time.sleep(REQUEST_DELAY)

        except requests.exceptions.RequestException as e:
            return None, f"RequestException: {e}"

    return all_records, None


# ============================================================
#  MAIN ENTRY POINT
# ============================================================
def main():
    print("=" * 60)
    print("         TARIK DATA - FASIH BPS DATA EXTRACTOR")
    print("=" * 60)

    # --- LANGKAH 1: Baca cURL datatable dari curl.txt ---
    print("\n[*] Membaca cURL datatable dari curl.txt...")
    try:
        with open('curl.txt', 'r', encoding='utf-8') as f:
            curl_content = f.read().strip()
    except FileNotFoundError:
        print("[!] File curl.txt tidak ditemukan!")
        print("    Paste cURL dari request datatable di browser ke file: tarik-data/curl.txt")
        return

    parsed_curl = parse_curl(curl_content)
    headers = extract_session_headers(parsed_curl)

    # Ekstrak base payload dari cURL (jika ada)
    base_payload = None
    if parsed_curl.get('data'):
        try:
            base_payload = json.loads(parsed_curl['data'])
        except json.JSONDecodeError:
            print("[!] Gagal mem-parse payload JSON dari cURL.")
            return

    if not base_payload:
        # Default payload structure berdasarkan contoh
        base_payload = {
            "start": 0,
            "length": 100,
            "columns": [
                {"data": "id", "orderable": True},
                {"data": "codeIdentity", "orderable": True},
                {"data": "data1", "orderable": True},
                {"data": "data2", "orderable": True},
                {"data": "data3", "orderable": True},
                {"data": "data4", "orderable": True},
                {"data": "data5", "orderable": True},
                {"data": "data6", "orderable": True},
                {"data": "data7", "orderable": True},
                {"data": "data8", "orderable": True},
                {"data": "data9", "orderable": True},
                {"data": "data10", "orderable": True}
            ],
            "order": [],
            "search": {"value": "", "regex": False},
            "assignmentExtraParam": {
                "surveyPeriodId": "",
                "assignmentErrorStatusType": -1,
                "filterTargetType": "TARGET_ONLY"
            }
        }

    # --- Ekstrak surveyPeriodId dari payload cURL ---
    survey_period_id = None
    if base_payload:
        survey_period_id = base_payload.get('assignmentExtraParam', {}).get('surveyPeriodId', '')

    if not survey_period_id:
        print("[!] surveyPeriodId tidak ditemukan di payload cURL!")
        print("    Pastikan curl.txt berisi cURL dari request datatable.")
        return

    # --- LANGKAH 2: Baca cURL region dari curl_region.txt (untuk groupId) ---
    import re as _re
    group_id = None

    print("[*] Membaca cURL region dari curl_region.txt...")
    try:
        with open('curl_region.txt', 'r', encoding='utf-8') as f:
            region_content = f.read().strip()
        # Scan isi file untuk mencari groupId=<uuid>
        match = _re.search(r'groupId=([a-f0-9\-]{36})', region_content)
        if match:
            group_id = match.group(1)
    except FileNotFoundError:
        pass

    # Fallback: coba dari config.json
    if not group_id:
        try:
            with open('config.json', 'r', encoding='utf-8') as f:
                config = json.load(f)
                group_id = config.get('groupId')
        except FileNotFoundError:
            pass

    if not group_id:
        print("[!] File curl_region.txt tidak ditemukan atau tidak mengandung groupId!")
        print("")
        print("    CARA MENDAPATKANNYA:")
        print("    1. Buka halaman Fasih BPS, tekan F12 -> tab Network.")
        print("    2. Klik dropdown wilayah (misal dropdown Provinsi).")
        print("    3. Cari request ke URL yang mengandung '/region/level'.")
        print("       Contoh: .../region/level1?groupId=a45adac1-e711-4c15-b3f9-...")
        print("    4. Klik kanan request tersebut -> Copy -> Copy as cURL (bash).")
        print("    5. Paste ke file: tarik-data/curl_region.txt")
        return

    print(f"[*] groupId       : {group_id}")
    print(f"[*] surveyPeriodId: {survey_period_id}")

    # Simpan config untuk pemakaian selanjutnya
    config_data = {"groupId": group_id, "surveyPeriodId": survey_period_id}
    with open('config.json', 'w', encoding='utf-8') as f:
        json.dump(config_data, f, indent=2)

    # Set surveyPeriodId di base payload
    if 'assignmentExtraParam' not in base_payload:
        base_payload['assignmentExtraParam'] = {}
    base_payload['assignmentExtraParam']['surveyPeriodId'] = survey_period_id

    # --- LANGKAH 2: Baca daftar target sub SLS ---
    print(f"\n[*] Membaca daftar target sub SLS dari {TARGET_FILE}...")
    target_subsls_codes = []
    try:
        df_target = pd.read_excel(TARGET_FILE, dtype=str)
        # Cari kolom yang berisi kode sub SLS
        col_name = None
        for candidate in ['subsls_code', 'fullCode', 'kode', 'code', 'sub_sls']:
            if candidate in df_target.columns:
                col_name = candidate
                break
        if col_name is None:
            col_name = df_target.columns[0]
        
        # Jika nama kolom (header) adalah kode sub SLS (angka panjang), masukkan juga sebagai target
        col_clean = str(col_name).strip()
        if col_clean.isdigit() and len(col_clean) >= 14:
            target_subsls_codes.append(col_clean)
            print(f"    Menggunakan kolom data langsung (baris pertama terdeteksi sebagai kode): '{col_clean}'")
        else:
            print(f"    Menggunakan kolom: '{col_name}'")
            
        for val in df_target[col_name].dropna():
            code = str(val).strip()
            if code:
                target_subsls_codes.append(code)
    except FileNotFoundError:
        print(f"[!] File {TARGET_FILE} tidak ditemukan!")
        print(f"    Buat file Excel tersebut dengan kolom pertama berisi kode fullCode sub SLS.")
        print("    Contoh isi kolom:")
        print("    317501000100010001")
        print("    317501000100010002")
        return
    except Exception as e:
        print(f"[!] Gagal membaca {TARGET_FILE}: {e}")
        return

    if not target_subsls_codes:
        print(f"[!] File {TARGET_FILE} kosong atau tidak ada data valid!")
        return

    print(f"    Ditemukan {len(target_subsls_codes)} target sub SLS.")

    # --- LANGKAH 3: Bangun atau muat database region (hanya wilayah yang relevan) ---
    region_db = {}
    if os.path.exists(REGION_DB_FILE):
        print(f"\n[*] Ditemukan file '{REGION_DB_FILE}'. Memuat database wilayah...")
        with open(REGION_DB_FILE, 'r', encoding='utf-8') as f:
            region_db = json.load(f)

        # Cek apakah semua target sudah ada di database
        missing = []
        for code in target_subsls_codes:
            if code not in region_db:
                missing.append(code)

        if missing:
            print(f"    {len(missing)} dari {len(target_subsls_codes)} target belum ada di database.")
            print(f"    Melengkapi data wilayah yang kurang...")
            new_db = build_region_database(headers, group_id, missing)
            region_db.update(new_db)
            # Simpan ulang
            with open(REGION_DB_FILE, 'w', encoding='utf-8') as f:
                json.dump(region_db, f, indent=2, ensure_ascii=False)
            print(f"    Database wilayah diperbarui.")
        else:
            print(f"    Semua {len(target_subsls_codes)} target sudah ada di database.")

    if not region_db:
        print("\n[*] Memulai pengambilan data wilayah (hanya yang relevan dengan target)...")
        region_db = build_region_database(headers, group_id, target_subsls_codes)

        if not region_db:
            print("[!] Gagal membangun database wilayah!")
            return

        # Simpan ke file
        with open(REGION_DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(region_db, f, indent=2, ensure_ascii=False)
        print(f"\n[*] Database wilayah disimpan ke '{REGION_DB_FILE}'.")

    # Validasi target terhadap database
    valid_targets = []
    invalid_targets = []
    for code in target_subsls_codes:
        region_ids = resolve_region_hierarchy(region_db, code)
        if region_ids:
            valid_targets.append((code, region_ids))
        else:
            invalid_targets.append(code)

    if invalid_targets:
        print(f"\n[!] Peringatan: {len(invalid_targets)} kode sub SLS tidak ditemukan di API:")
        for inv in invalid_targets[:10]:
            print(f"    - {inv}")
        if len(invalid_targets) > 10:
            print(f"    ... dan {len(invalid_targets) - 10} lainnya.")

    if not valid_targets:
        print("[!] Tidak ada target sub SLS yang valid!")
        return

    print(f"\n[*] Target valid: {len(valid_targets)} sub SLS.")
    confirm = input(f"[?] Mulai mengambil data untuk {len(valid_targets)} sub SLS? (Y/n): ").strip().lower()
    if confirm == 'n':
        print("[*] Dibatalkan oleh pengguna.")
        return

    # --- LANGKAH 4: Eksekusi pengambilan data ---
    timestamp_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as lf:
        lf.write(f"\n{'='*50}\n")
        lf.write(f"EKSEKUSI TARIK DATA: {timestamp_str}\n")
        lf.write(f"{'='*50}\n")

    print(f"\n[*] Memulai pengambilan data...\n")
    print("-" * 60)

    all_results = []
    total_success = 0
    total_failed = 0
    total_records = 0
    failed_details = []

    for idx, (subsls_code, region_ids) in enumerate(valid_targets):
        subsls_info = region_db.get(subsls_code, {})
        subsls_name = subsls_info.get('name', 'N/A')

        log_msg = f"[{idx+1}/{len(valid_targets)}] Sub SLS: {subsls_code} ({subsls_name})"
        print(log_msg)
        with open(LOG_FILE, "a", encoding="utf-8") as lf:
            lf.write(log_msg + "\n")

        try:
            records, error = fetch_data_for_subsls(headers, base_payload, region_ids)

            if error:
                msg = f" -> [GAGAL] {error}"
                print(msg)
                total_failed += 1
                failed_details.append({
                    "subsls_code": subsls_code,
                    "subsls_name": subsls_name,
                    "reason": error
                })
                with open(LOG_FILE, "a", encoding="utf-8") as lf:
                    lf.write(msg + "\n")
            elif records is not None:
                record_count = len(records)
                msg = f" -> [SUKSES] {record_count} record ditemukan."
                print(msg)
                total_success += 1
                total_records += record_count

                # Tambahkan metadata wilayah ke setiap record
                for record in records:
                    if isinstance(record, dict):
                        record['_subsls_code'] = subsls_code
                        record['_subsls_name'] = subsls_name

                all_results.extend(records)

                with open(LOG_FILE, "a", encoding="utf-8") as lf:
                    lf.write(msg + "\n")
            else:
                msg = " -> [SUKSES] 0 record (kosong)."
                print(msg)
                total_success += 1
                with open(LOG_FILE, "a", encoding="utf-8") as lf:
                    lf.write(msg + "\n")

        except Exception as e:
            msg = f" -> [ERROR] {e}"
            print(msg)
            total_failed += 1
            failed_details.append({
                "subsls_code": subsls_code,
                "subsls_name": subsls_name,
                "reason": f"Exception: {e}"
            })
            with open(LOG_FILE, "a", encoding="utf-8") as lf:
                lf.write(msg + "\n")

        print("-" * 60)
        time.sleep(REQUEST_DELAY)

    # Simpan hasil ke Excel
    if all_results:
        df_result = pd.json_normalize(all_results)
        df_result.to_excel(RESULT_FILE, index=False, engine='openpyxl')
        print(f"\n[*] Data berhasil disimpan ke '{RESULT_FILE}' ({len(all_results)} record total).")
        print(f"    Jumlah kolom: {len(df_result.columns)}")
        print(f"    Kolom: {', '.join(df_result.columns[:10])}{'...' if len(df_result.columns) > 10 else ''}")

    # Ringkasan akhir
    summary_lines = []
    summary_lines.append("\n" + "=" * 50)
    summary_lines.append("           RINGKASAN AKHIR PENGEKSEKUSIAN")
    summary_lines.append("=" * 50)
    summary_lines.append(f" - Berhasil diproses : {total_success}")
    summary_lines.append(f" - Gagal diproses    : {total_failed}")
    summary_lines.append(f" - Total target      : {len(valid_targets)}")
    summary_lines.append(f" - Total record data : {total_records}")
    summary_lines.append("=" * 50)

    if failed_details:
        summary_lines.append("DETAIL KEGAGALAN:")
        for fd in failed_details:
            summary_lines.append(
                f" - Sub SLS: {fd['subsls_code']} ({fd['subsls_name']}) "
                f"(Alasan: {fd['reason']})"
            )
        summary_lines.append("=" * 50)

    summary_text = "\n".join(summary_lines)
    print(summary_text)
    with open(LOG_FILE, "a", encoding="utf-8") as lf:
        lf.write(summary_text + "\n")


if __name__ == "__main__":
    main()
