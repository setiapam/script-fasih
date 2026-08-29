import requests
import pandas as pd
import re
import time
import os
import json
import datetime
import sys

# ================= KONFIGURASI =================
DEFAULT_EXCEL_FILES = ['change_mode.xlsx', 'change-mode.xlsx', 'mode.xlsx', 'assign.xlsx']
KOLOM_SAMPEL_DEFAULT = 'idsbr'
KOLOM_PERUSAHAAN_DEFAULT = 'perusahaan'
KOLOM_MODE_DEFAULT = 'mode'

VALID_MODES = {'PAPI', 'CAPI', 'CAWI'}

class SessionExpiredException(Exception):
    pass

# ================= FUNGSI BANTUAN =================

def is_session_expired_response(response):
    """Mendeteksi apakah response menandakan sesi login / cURL sudah kadaluarsa."""
    if response.status_code in (401, 403):
        return True
    content_type = response.headers.get('Content-Type', '')
    if 'text/html' in content_type:
        text_lower = response.text.lower()
        if 'login' in text_lower or 'keycloak' in text_lower or 'sso' in text_lower or 'unauthorized' in text_lower:
            return True
    return False

def show_session_expired_banner(module_curl_path="change-mode/curl.txt", completed_count=0, total_count=0):
    """Menampilkan banner instruksi yang jelas saat sesi expired agar pengguna tidak salah paham."""
    print("\n" + "=" * 65)
    print("⚠️  [SESI LOGIN KADALUARSA / EXPIRED] (HTTP 401/403)")
    print("=" * 65)
    print(" Sesi login FASIH BPS atau token cURL Anda telah habis masa berlakunya.")
    print(" BUKAN karena data tidak ada di server BPS, melainkan akses ditolak.")
    print("\n Langkah mudah untuk melanjutkan:")
    print("  1. Buka browser dan login ulang ke https://fasih-sm.bps.go.id")
    print("  2. Buka tab Network (F12), lakukan interaksi/refresh halaman.")
    print(f"  3. Salin (Copy as cURL) request terbaru ke berkas: {module_curl_path}")
    print("  4. Jalankan ulang script (semua progress yang berhasil tersimpan otomatis).")
    if total_count > 0:
        print(f"\n Progress saat ini: {completed_count} dari {total_count} target selesai.")
    print("=" * 65 + "\n")

def parse_curl(filepath):
    """Membaca file cURL dan mengekstrak URL, Cookie, XSRF token, dan Header lainnya."""
    if not os.path.exists(filepath):
        print(f"❌ File {filepath} tidak ditemukan! Pastikan file sudah dibuat.")
        return "", "", "", "", ""
        
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
        
    url_match = re.search(r"(https?://[^\s'\"^\\]+)", content)
    url = url_match.group(1) if url_match else ""
    
    cookie_match = re.search(r"-b\s+['\"]([^'\"]+)['\"]", content)
    if not cookie_match:
        cookie_match = re.search(r"Cookie:\s*([^'\"]+)", content, re.IGNORECASE)
    cookie = cookie_match.group(1) if cookie_match else ""
    
    xsrf_match = re.search(r"X-XSRF-TOKEN:\s*([^'\"]+)", content, re.IGNORECASE)
    if not xsrf_match:
        # Fallback cari XSRF-TOKEN dari dalam cookie string
        xsrf_cookie = re.search(r"XSRF-TOKEN=([^;'\"]+)", cookie, re.IGNORECASE)
        xsrf = xsrf_cookie.group(1) if xsrf_cookie else ""
    else:
        xsrf = xsrf_match.group(1)
        
    referer_match = re.search(r"referer:\s*([^\s'\"^\\]+)", content, re.IGNORECASE)
    referer = referer_match.group(1) if referer_match else ""
    
    origin_match = re.search(r"origin:\s*([^\s'\"^\\]+)", content, re.IGNORECASE)
    origin = origin_match.group(1) if origin_match else "https://fasih-sm.bps.go.id"
    
    return url, cookie, xsrf, referer, origin

def extract_survey_period_id_from_file(filepath):
    """Mengekstrak surveyPeriodId dari parameter URL, query string, payload JSON, atau Referer."""
    if not os.path.exists(filepath):
        return ""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 1. Parameter surveyPeriodId di Query String
    match = re.search(r'surveyPeriodId=([a-f0-9\-]{36})', content, re.IGNORECASE)
    if match:
        return match.group(1)
        
    # 2. Key surveyPeriodId di Body Payload JSON
    match = re.search(r'["\']surveyPeriodId["\']\s*:\s*["\']([a-f0-9\-]{36})["\']', content, re.IGNORECASE)
    if match:
        return match.group(1)
        
    # 3. Path assign-by-selection-allocation/...
    match = re.search(r'assign-by-selection-allocation/([a-f0-9\-]{36})', content, re.IGNORECASE)
    if match:
        return match.group(1)
        
    # 4. Path /surveys/<surveyId>/<surveyPeriodId>/... (dari Referer atau URL)
    match = re.search(r'/surveys/[a-f0-9\-]{36}/([a-f0-9\-]{36})', content, re.IGNORECASE)
    if match:
        return match.group(1)

    return ""

def get_headers(cookie, xsrf, referer="", origin="https://fasih-sm.bps.go.id"):
    headers = {
        'Accept': 'application/json, text/plain, */*',
        'Content-Type': 'application/json',
        'Cookie': cookie,
        'X-XSRF-TOKEN': xsrf,
        'Origin': origin,
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36'
    }
    if referer:
        headers['Referer'] = referer
    return headers

def extract_list_from_json(json_data):
    if not isinstance(json_data, dict):
        return []
    if 'searchData' in json_data and isinstance(json_data['searchData'], list):
        return json_data['searchData']
    if 'data' in json_data and isinstance(json_data['data'], dict):
        if 'searchData' in json_data['data'] and isinstance(json_data['data']['searchData'], list):
            return json_data['data']['searchData']
        if 'data' in json_data['data'] and isinstance(json_data['data']['data'], list):
            return json_data['data']['data']
    if 'data' in json_data and isinstance(json_data['data'], list):
        return json_data['data']
    return []

def check_item_contains_value(item, target_value):
    """Memeriksa secara rekursif apakah target_value ada di dalam atribut apapun dari item."""
    if not isinstance(item, dict) or not target_value:
        return False
        
    target_str = str(target_value).strip().lower()
    if target_str.endswith('.0'):
        target_str = target_str[:-2]
    if not target_str:
        return False

    def collect_values(obj):
        vals = []
        if isinstance(obj, dict):
            for k, v in obj.items():
                vals.extend(collect_values(v))
        elif isinstance(obj, list):
            for elem in obj:
                vals.extend(collect_values(elem))
        elif isinstance(obj, (str, int, float)):
            s = str(obj).strip().lower()
            if s.endswith('.0'):
                s = s[:-2]
            vals.append(s)
        return vals

    all_vals = collect_values(item)
    for v in all_vals:
        if v == target_str or target_str in v:
            return True
    return False

def query_datatable(url, headers, survey_period_id, search_term, extra_filter=False):
    """Mengirim request pencarian langsung ke DataTables API dengan deteksi session expired."""
    extra_param = {"surveyPeriodId": survey_period_id}
    if extra_filter:
        extra_param["filterTargetType"] = "TARGET_ONLY"
        extra_param["assignmentErrorStatusType"] = -1

    payload = {
        "start": 0,
        "length": 50,
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
            {"data": "data10", "orderable": True},
            {"data": "data11", "orderable": True},
            {"data": "data12", "orderable": True},
            {"data": "data13", "orderable": True},
            {"data": "data14", "orderable": True},
            {"data": "data15", "orderable": True}
        ],
        "order": [],
        "search": {"value": str(search_term).strip(), "regex": False},
        "assignmentExtraParam": extra_param
    }

    for attempt in range(2):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=20)
            
            if is_session_expired_response(response):
                raise SessionExpiredException(f"HTTP {response.status_code}: Sesi login FASIH BPS telah habis masa berlakunya.")
                
            if response.status_code == 200:
                return extract_list_from_json(response.json())
            elif response.status_code == 429:
                time.sleep(1.5 * (attempt + 1))
            else:
                break
        except SessionExpiredException:
            raise
        except Exception:
            time.sleep(0.5)
            
    return []

def search_sample_direct(url, headers, survey_period_id, target_idsbr, target_perusahaan=""):
    """
    Mencari sampel secara LANGSUNG ke server FASIH tanpa mengandalkan bulk cache.
    Multi-strategi pencarian:
    1. Pencarian langsung nilai IDSBR (tanpa filter status/tipe sempit).
    2. Pencarian nilai IDSBR dengan tanda petik ganda (seperti perilaku Web UI BPS).
    3. Pencarian dengan filter TARGET_ONLY jika diperlukan.
    4. Fallback pencarian berdasarkan Nama Perusahaan.
    """
    idsbr_clean = str(target_idsbr).strip() if target_idsbr else ""
    if idsbr_clean.endswith('.0'):
        idsbr_clean = idsbr_clean[:-2]

    # --- TAHAP 1: Cari berdasarkan IDSBR langsung ke server ---
    if idsbr_clean:
        # Strategi 1.1: Pencarian umum bebas filter status
        results = query_datatable(url, headers, survey_period_id, idsbr_clean, extra_filter=False)
        for item in results:
            if check_item_contains_value(item, idsbr_clean):
                return item.get('id')
            if len(results) == 1 and item.get('id'):
                return item.get('id')

        # Strategi 1.2: Pencarian exact string quoted seperti web UI (misal: "46377507")
        results_quoted = query_datatable(url, headers, survey_period_id, f'"{idsbr_clean}"', extra_filter=False)
        for item in results_quoted:
            if check_item_contains_value(item, idsbr_clean):
                return item.get('id')
            if len(results_quoted) == 1 and item.get('id'):
                return item.get('id')

        # Strategi 1.3: Coba dengan extra_filter TARGET_ONLY
        results_filtered = query_datatable(url, headers, survey_period_id, idsbr_clean, extra_filter=True)
        for item in results_filtered:
            if check_item_contains_value(item, idsbr_clean):
                return item.get('id')
            if len(results_filtered) == 1 and item.get('id'):
                return item.get('id')

    # --- TAHAP 2: Fallback cari berdasarkan Nama Perusahaan ---
    nama_clean = str(target_perusahaan).strip() if target_perusahaan else ""
    if nama_clean and nama_clean.lower() != 'nan':
        results_nama = query_datatable(url, headers, survey_period_id, nama_clean, extra_filter=False)
        for item in results_nama:
            # Utamakan baris yang mengandung IDSBR kita jika ada
            if idsbr_clean and check_item_contains_value(item, idsbr_clean):
                return item.get('id')
            # Atau kecocokan nama perusahaan
            if check_item_contains_value(item, nama_clean):
                return item.get('id')

    return None

def find_excel_file():
    """Mencari berkas Excel yang tersedia dari daftar prioritas."""
    for candidate in DEFAULT_EXCEL_FILES:
        if os.path.exists(candidate):
            return candidate
    return None

def detect_columns(df):
    """Mendeteksi nama kolom untuk IDSBR, Perusahaan, dan Mode secara dinamis."""
    col_sampel = None
    col_perusahaan = None
    col_mode = None
    
    cols = {str(c).strip().lower(): c for c in df.columns}
    
    # 1. Kolom Sampel / IDSBR
    for alias in ['idsbr', 'id_sbr', 'kode_sampel', 'sampel', 'id']:
        if alias in cols:
            col_sampel = cols[alias]
            break
            
    # 2. Kolom Perusahaan
    for alias in ['perusahaan', 'nama_perusahaan', 'nama_usaha', 'company', 'nama']:
        if alias in cols:
            col_perusahaan = cols[alias]
            break
            
    # 3. Kolom Mode
    for alias in ['mode', 'moda', 'change_mode', 'tipe_mode', 'tipe_moda', 'modapengumpulan']:
        if alias in cols:
            col_mode = cols[alias]
            break
            
    return col_sampel, col_perusahaan, col_mode

# ================= EKSEKUSI UTAMA =================
def main():
    print("=" * 60)
    print("        CHANGE MODE (PAPI / CAPI / CAWI) AUTOMATION")
    print("=" * 60)
    print("Membaca konfigurasi file cURL...")
    
    curl_file = 'curl.txt'
    if not os.path.exists(curl_file):
        print(f"❌ File cURL tidak ditemukan! Sediakan file '{curl_file}' di folder 'change-mode/'.")
        return

    url_main, cookie, xsrf, referer, origin = parse_curl(curl_file)
    if not cookie or not xsrf:
        print(f"❌ Gagal membaca Cookie atau XSRF-TOKEN dari '{curl_file}'. Pastikan cURL valid.")
        return

    headers = get_headers(cookie, xsrf, referer=referer, origin=origin)
    survey_period_id = extract_survey_period_id_from_file(curl_file)
    
    # Cek apakah ada surveyPeriodId tersimpan di config.json
    config_file = 'config.json'
    prev_period_id = None
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                cdata = json.load(f)
                prev_period_id = cdata.get('surveyPeriodId')
        except Exception:
            pass

    if not survey_period_id and prev_period_id:
        survey_period_id = prev_period_id

    if not survey_period_id:
        print("\n[!] surveyPeriodId tidak ditemukan otomatis dari cURL.")
        survey_period_id = input("Masukkan surveyPeriodId secara manual (UUID 36 karakter): ").strip()
        if not survey_period_id:
            print("❌ Proses dibatalkan karena surveyPeriodId kosong.")
            return

    print(f"[*] Terdeteksi surveyPeriodId: {survey_period_id}")

    # Cek pergantian survei
    if prev_period_id and prev_period_id != survey_period_id:
        print(f"🔄 Terdeteksi pergantian kegiatan survei (Periode Baru: {survey_period_id} | Lama: {prev_period_id}).")
        print("   Mereset checkpoint progress lama...")
        if os.path.exists('completed_change_mode.json'):
            os.remove('completed_change_mode.json')

    # Simpan surveyPeriodId aktif ke config.json
    try:
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump({'surveyPeriodId': survey_period_id}, f, indent=2)
    except Exception:
        pass

    url_sampel = "https://fasih-sm.bps.go.id/app/api/analytic/api/v2/assignment/datatable-all-user-survey-periode"

    # 1. Cari File Excel
    excel_file = find_excel_file()
    if not excel_file:
        print(f"❌ File Excel tidak ditemukan! Sediakan berkas 'change_mode.xlsx' di folder 'change-mode/'.")
        return

    print(f"[*] Menggunakan file Excel: '{excel_file}'")
    try:
        df = pd.read_excel(excel_file, dtype=str)
    except Exception as e:
        print(f"❌ Gagal membaca file Excel: {e}")
        return

    col_sampel, col_perusahaan, col_mode = detect_columns(df)
    
    if not col_sampel:
        print("❌ Kolom IDSBR/Sampel tidak ditemukan di Excel! Pastikan ada kolom bernama 'idsbr'.")
        return
    if not col_mode:
        print("❌ Kolom Mode tidak ditemukan di Excel! Pastikan ada kolom bernama 'mode'.")
        return

    print(f"[*] Kolom terdeteksi -> Sampel: '{col_sampel}' | Mode: '{col_mode}' | Perusahaan: '{col_perusahaan or 'TIDAK DITEMUKAN'}'")

    # 2. Checkpoint & Riwayat Progress
    COMPLETED_FILE = "completed_change_mode.json"
    REPORT_FILE = "laporan_hasil_change_mode.xlsx"
    LEGACY_REPORT_CSV = "laporan_hasil_change_mode.csv"
    completed_data = {}
    if os.path.exists(COMPLETED_FILE):
        try:
            with open(COMPLETED_FILE, "r", encoding="utf-8") as f:
                completed_data = json.load(f)
        except Exception:
            completed_data = {}

    if completed_data.get("surveyPeriodId") != survey_period_id:
        completed_data = {"surveyPeriodId": survey_period_id, "success_idsbr": []}

    success_set = set(completed_data.get("success_idsbr", []))

    # Baca juga dari laporan_hasil_change_mode.xlsx (atau csv legacy) jika ada
    if os.path.exists(REPORT_FILE):
        try:
            df_rep = pd.read_excel(REPORT_FILE, dtype=str)
            for _, r in df_rep.iterrows():
                idsbr_val = str(r['IDSBR']).strip()
                status_val = str(r['Status']).strip()
                if idsbr_val and idsbr_val != 'nan' and 'Berhasil' in status_val:
                    success_set.add(idsbr_val)
        except Exception:
            pass
    elif os.path.exists(LEGACY_REPORT_CSV):
        try:
            df_rep = pd.read_csv(LEGACY_REPORT_CSV, dtype=str)
            for _, r in df_rep.iterrows():
                idsbr_val = str(r['IDSBR']).strip()
                status_val = str(r['Status']).strip()
                if idsbr_val and idsbr_val != 'nan' and 'Berhasil' in status_val:
                    success_set.add(idsbr_val)
        except Exception:
            pass

    completed_data["success_idsbr"] = list(success_set)
    try:
        with open(COMPLETED_FILE, "w", encoding="utf-8") as f:
            json.dump(completed_data, f, indent=2)
    except Exception:
        pass

    if success_set:
        print(f"\n[*] Ditemukan progress perubahan mode sebelumnya:")
        print(f"    - Sampel sudah berhasil diubah mode : {len(success_set)}")
        resume = input("[?] Lanjutkan progress (melewati sampel yang sudah berhasil)? (Y/n): ").strip().lower()
        if resume == 'n':
            print("[*] Memulai ulang dari awal (mereset progress)...")
            success_set = set()
            completed_data["success_idsbr"] = []
            try:
                with open(COMPLETED_FILE, "w", encoding="utf-8") as f:
                    json.dump(completed_data, f, indent=2)
            except Exception:
                pass

    # 3. Inisialisasi Logging
    timestamp_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_file = "execution.log"
    
    with open(log_file, "a", encoding="utf-8") as lf:
        lf.write(f"\n==================================================\n")
        lf.write(f"EKSEKUSI CHANGE MODE: {timestamp_str}\n")
        lf.write(f"==================================================\n")

    sukses = 0
    gagal = 0
    log_results = []
    failed_details = []
    session_expired_detected = False

    # Cache runtime per sesi agar jika ada baris excel dengan IDSBR sama tidak mengulang query
    runtime_cache = {}

    print("\nMemulai proses Change Mode (Pencarian Langsung On-Demand per Sampel)...")
    print("-" * 50)

    for index, row in df.iterrows():
        if pd.isna(row[col_sampel]) or str(row[col_sampel]).lower() == 'nan':
            continue
            
        sampel_excel = str(row[col_sampel]).strip()
        if sampel_excel.endswith('.0'):
            sampel_excel = sampel_excel[:-2]
            
        nama_perusahaan = ""
        if col_perusahaan and not pd.isna(row[col_perusahaan]) and str(row[col_perusahaan]).lower() != 'nan':
            nama_perusahaan = str(row[col_perusahaan]).strip()

        mode_raw = str(row[col_mode]).strip() if not pd.isna(row[col_mode]) else ""
        mode_upper = mode_raw.upper()

        if sampel_excel in success_set:
            log_msg = f"Memproses baris {index+1}/{len(df)} | IDSBR: {sampel_excel} -> [SKIPPED] Sudah berhasil diubah sebelumnya."
            print(log_msg)
            sukses += 1
            log_results.append({
                "IDSBR": sampel_excel,
                "Perusahaan": nama_perusahaan,
                "Mode": mode_upper,
                "Status": "Berhasil (Skipped - Sudah Berhasil Sebelumnya)"
            })
            continue

        log_msg = f"Memproses baris {index+1}/{len(df)} | IDSBR: {sampel_excel} | Perusahaan: {nama_perusahaan or '-'} | Mode Target: {mode_upper or '-'}"
        print(log_msg)
        with open(log_file, "a", encoding="utf-8") as lf:
            lf.write(log_msg + "\n")

        # Validasi Pilihan Mode
        if mode_upper not in VALID_MODES:
            msg = f" -> [GAGAL] Lewati {sampel_excel}: Nilai mode '{mode_raw}' tidak valid. Pilihan yang didukung: PAPI, CAPI, CAWI."
            print(msg)
            gagal += 1
            log_results.append({
                "IDSBR": sampel_excel,
                "Perusahaan": nama_perusahaan,
                "Mode": mode_raw,
                "Status": f"Gagal - Mode tidak valid (harus PAPI/CAPI/CAWI)"
            })
            failed_details.append({"idsbr": sampel_excel, "reason": f"Nilai mode '{mode_raw}' tidak valid (harus PAPI, CAPI, atau CAWI)"})
            with open(log_file, "a", encoding="utf-8") as lf:
                lf.write(msg + "\n")
            continue

        # 4. Pencarian Sampel Langsung ke Server
        sample_id = runtime_cache.get(sampel_excel)
        if not sample_id:
            s_msg = f"   🔍 Mencari sampel ke server BPS (IDSBR: '{sampel_excel}'" + (f", Perusahaan: '{nama_perusahaan}'" if nama_perusahaan else "") + ")..."
            print(s_msg)
            with open(log_file, "a", encoding="utf-8") as lf:
                lf.write(s_msg + "\n")
                
            try:
                sample_id = search_sample_direct(
                    url=url_sampel,
                    headers=headers,
                    survey_period_id=survey_period_id,
                    target_idsbr=sampel_excel,
                    target_perusahaan=nama_perusahaan
                )
            except SessionExpiredException as e:
                session_expired_detected = True
                print(f" -> [ERROR AUTH] {e}")
                with open(log_file, "a", encoding="utf-8") as lf:
                    lf.write(f" -> [ERROR AUTH] {e}\n")
                show_session_expired_banner(
                    module_curl_path="change-mode/curl.txt",
                    completed_count=sukses,
                    total_count=len(df)
                )
                break
            
            if sample_id:
                runtime_cache[sampel_excel] = sample_id

        if not sample_id:
            msg = f" -> [GAGAL] Lewati {sampel_excel}: Sampel tidak ditemukan di server FASIH (sudah dicari berdasarkan IDSBR & Nama Perusahaan)."
            print(msg)
            gagal += 1
            log_results.append({
                "IDSBR": sampel_excel,
                "Perusahaan": nama_perusahaan,
                "Mode": mode_upper,
                "Status": "Gagal - Sampel tidak ditemukan di server"
            })
            failed_details.append({"idsbr": sampel_excel, "reason": "Sampel tidak ditemukan di server"})
            with open(log_file, "a", encoding="utf-8") as lf:
                lf.write(msg + "\n")
            continue

        # 5. Hit Endpoint Change Mode
        url_change_mode = f"https://fasih-sm.bps.go.id/app/api/assignment-submit/api/assignment/{sample_id}/change-mode"
        payload = {"modes": [mode_upper]}

        try:
            response = requests.post(url_change_mode, headers=headers, json=payload, timeout=15)
            
            if is_session_expired_response(response):
                session_expired_detected = True
                msg = f" -> [ERROR AUTH] Sesi kadaluarsa saat mengubah mode {sampel_excel} (HTTP {response.status_code})."
                print(msg)
                with open(log_file, "a", encoding="utf-8") as lf:
                    lf.write(msg + "\n")
                show_session_expired_banner(
                    module_curl_path="change-mode/curl.txt",
                    completed_count=sukses,
                    total_count=len(df)
                )
                break
                
            if response.status_code in [200, 201, 204]:
                msg = f" -> [SUKSES] Berhasil Change Mode -> {sampel_excel} ke mode '{mode_upper}' (Status: {response.status_code})"
                print(msg)
                sukses += 1
                log_results.append({
                    "IDSBR": sampel_excel,
                    "Perusahaan": nama_perusahaan,
                    "Mode": mode_upper,
                    "Status": "Berhasil"
                })

                # Simpan ke Checkpoint
                success_set.add(sampel_excel)
                completed_data["success_idsbr"] = list(success_set)
                try:
                    with open(COMPLETED_FILE, "w", encoding="utf-8") as f:
                        json.dump(completed_data, f, indent=2)
                except Exception:
                    pass
            else:
                resp_text = response.text[:200] if response.text else ""
                msg = f" -> [GAGAL] Gagal Change Mode -> {sampel_excel} ke '{mode_upper}' | Server merespon: HTTP {response.status_code} {resp_text}"
                print(msg)
                gagal += 1
                log_results.append({
                    "IDSBR": sampel_excel,
                    "Perusahaan": nama_perusahaan,
                    "Mode": mode_upper,
                    "Status": f"Gagal HTTP {response.status_code}"
                })
                failed_details.append({"idsbr": sampel_excel, "reason": f"HTTP {response.status_code} ({resp_text})"})
                
            with open(log_file, "a", encoding="utf-8") as lf:
                lf.write(msg + "\n")
        except Exception as e:
            msg = f" -> [ERROR] Terjadi kesalahan saat menghubungi API untuk {sampel_excel}: {e}"
            print(msg)
            gagal += 1
            log_results.append({
                "IDSBR": sampel_excel,
                "Perusahaan": nama_perusahaan,
                "Mode": mode_upper,
                "Status": f"Error: {e}"
            })
            failed_details.append({"idsbr": sampel_excel, "reason": f"Exception: {e}"})
            with open(log_file, "a", encoding="utf-8") as lf:
                lf.write(msg + "\n")
                
        time.sleep(0.4)

    # 6. Format Ringkasan Akhir Sesuai Standar
    summary_lines = []
    summary_lines.append("\n" + "=" * 50)
    summary_lines.append("           RINGKASAN AKHIR PENGEKSEKUSIAN")
    summary_lines.append("=" * 50)
    summary_lines.append(f" - Berhasil diproses : {sukses}")
    summary_lines.append(f" - Gagal diproses    : {gagal}")
    summary_lines.append(f" - Total target      : {sukses + gagal}")
    summary_lines.append("=" * 50)
    
    if failed_details:
        summary_lines.append("DETAIL KEGAGALAN:")
        for fd in failed_details:
            summary_lines.append(f" - IDSBR: {fd['idsbr']} (Alasan: {fd['reason']})")
        summary_lines.append("=" * 50)
        
    summary_text = "\n".join(summary_lines)
    print(summary_text)
    with open(log_file, "a", encoding="utf-8") as lf:
        lf.write(summary_text + "\n")
        
    # 7. Pembaruan Berkas Laporan Excel (Upsert Mode)
    if log_results:
        existing_report = {}
        if os.path.exists(REPORT_FILE):
            try:
                df_old = pd.read_excel(REPORT_FILE, dtype=str)
                for _, r in df_old.iterrows():
                    idsbr_val = str(r['IDSBR']).strip()
                    if idsbr_val and idsbr_val != 'nan':
                        existing_report[idsbr_val] = {
                            "IDSBR": idsbr_val,
                            "Perusahaan": str(r.get('Perusahaan', '')).strip(),
                            "Mode": str(r.get('Mode', '')).strip(),
                            "Status": str(r.get('Status', '')).strip()
                        }
            except Exception:
                pass
        elif os.path.exists(LEGACY_REPORT_CSV):
            try:
                df_old = pd.read_csv(LEGACY_REPORT_CSV, dtype=str)
                for _, r in df_old.iterrows():
                    idsbr_val = str(r['IDSBR']).strip()
                    if idsbr_val and idsbr_val != 'nan':
                        existing_report[idsbr_val] = {
                            "IDSBR": idsbr_val,
                            "Perusahaan": str(r.get('Perusahaan', '')).strip(),
                            "Mode": str(r.get('Mode', '')).strip(),
                            "Status": str(r.get('Status', '')).strip()
                        }
            except Exception:
                pass

        for item in log_results:
            idsbr_val = str(item['IDSBR']).strip()
            existing_report[idsbr_val] = item

        df_log = pd.DataFrame(list(existing_report.values()))
        df_log.to_excel(REPORT_FILE, index=False)
        print(f"\n📝 Berkas laporan '{REPORT_FILE}' berhasil diperbarui dengan format Excel (.xlsx)!")

if __name__ == "__main__":
    main()
