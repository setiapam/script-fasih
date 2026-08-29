import requests
import pandas as pd
import re
import time
import os
import json
import datetime

# ================= KONFIGURASI =================
DEFAULT_EXCEL_FILES = ['change_mode.xlsx', 'change-mode.xlsx', 'mode.xlsx', 'assign.xlsx']
KOLOM_SAMPEL_DEFAULT = 'idsbr'
KOLOM_PERUSAHAAN_DEFAULT = 'perusahaan'
KOLOM_MODE_DEFAULT = 'mode'

VALID_MODES = {'PAPI', 'CAPI', 'CAWI'}

# ================= FUNGSI BANTUAN =================

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

def fetch_all_samples(url, headers, survey_period_id):
    """Mengambil data sampel awal secara bertahap dari API DataTables."""
    print("Mengambil data sampel awal (Limit Request: 500 per halaman)...")
    samples_dict = {}
    start = 0
    draw = 1
    length = 500 
    total_fetched = 0
    
    while True:
        payload = {
            "draw": draw,
            "columns": [{"data": "id", "searchable": True, "orderable": False, "search": {"value": "", "regex": False}}],
            "order": [{"column": 0, "dir": "asc"}],
            "start": start,
            "length": length,
            "search": {"value": "", "regex": False},
            "assignmentExtraParam": {"surveyPeriodId": survey_period_id, "filterTargetType": "TARGET_ONLY", "assignmentErrorStatusType": -1}
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=25)
            if response.status_code != 200:
                break
            json_response = response.json()
        except Exception:
            break
            
        data = extract_list_from_json(json_response)
        if not data or len(data) == 0:
            break
        total_fetched += len(data)
            
        for item in data:
            if not isinstance(item, dict):
                continue
            sample_id = item.get('id')
            if not sample_id:
                continue
                
            for key in ['codeIdentity', 'data1', 'data2', 'data3', 'data4', 'data5']:
                val = str(item.get(key, '')).strip()
                if val.endswith('.0'):
                    val = val[:-2]
                if val and val.lower() != 'none':
                    samples_dict[val] = sample_id
        
        print(f"  -> Halaman {draw}: Terambil {len(data)} baris (Total: {total_fetched})")
        if len(data) < length:
            break
        start += length
        draw += 1
        time.sleep(0.3)
        
    print(f"✅ Selesai mengambil {total_fetched} sampel awal ke dalam memori.")
    return samples_dict

def fetch_single_sample_on_demand(url, headers, survey_period_id, keyword, target_idsbr):
    """Mencari 1 sampel secara spesifik ke server dan memverifikasi dengan IDSBR."""
    search_term = str(keyword).strip()
    if not search_term:
        return None
    
    payload = {
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
        "search": {"value": search_term, "regex": False},
        "assignmentExtraParam": {"surveyPeriodId": survey_period_id, "filterTargetType": "TARGET_ONLY", "assignmentErrorStatusType": -1}
    }
    
    for attempt in range(3):
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=15)
            if response.status_code == 200:
                data = extract_list_from_json(response.json())
                for item in data:
                    if not isinstance(item, dict):
                        continue
                    
                    # Double-Check: Apakah di antara baris hasil pencarian ini ada IDSBR target kita?
                    for key in ['codeIdentity', 'data1', 'data2', 'data3', 'data4', 'data5']:
                        val = str(item.get(key, '')).strip()
                        if val.endswith('.0'):
                            val = val[:-2]
                        
                        if val == str(target_idsbr) or str(target_idsbr) in str(item.get('codeIdentity', '')):
                            return item.get('id')
                break
            elif response.status_code == 429:
                time.sleep(2.0 * (attempt + 1))
            else:
                break
        except Exception:
            time.sleep(1.0)
        
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

    # 2. Tarik Kamus Data Sampel Awal ke Memori
    dict_sampel = fetch_all_samples(url_sampel, headers, survey_period_id)

    # 3. Checkpoint & Riwayat Progress
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

    # 4. Inisialisasi Logging
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

    print("\nMemulai proses Change Mode...")
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
            log_msg = f"Memproses baris {index+1} | IDSBR: {sampel_excel} -> [SKIPPED] Sudah berhasil diubah sebelumnya."
            print(log_msg)
            sukses += 1
            log_results.append({
                "IDSBR": sampel_excel,
                "Perusahaan": nama_perusahaan,
                "Mode": mode_upper,
                "Status": "Berhasil (Skipped - Sudah Berhasil Sebelumnya)"
            })
            continue

        log_msg = f"Memproses baris {index+1} | IDSBR: {sampel_excel} | Perusahaan: {nama_perusahaan or '-'} | Mode Target: {mode_upper or '-'}"
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

        # Cari ID Sampel dari Cache
        sample_id = dict_sampel.get(sampel_excel)
        
        # JIKA GAGAL DITEMUKAN DI CACHE: Lakukan Pencarian On-Demand
        if not sample_id:
            # 1. Utamakan pencarian spesifik berdasarkan IDSBR
            f_msg = f"🔍 [Pencarian IDSBR] Mencari sampel ke server berdasarkan IDSBR: {sampel_excel}..."
            print(f_msg)
            with open(log_file, "a", encoding="utf-8") as lf:
                lf.write(f_msg + "\n")
            sample_id = fetch_single_sample_on_demand(url_sampel, headers, survey_period_id, keyword=sampel_excel, target_idsbr=sampel_excel)
            
            # 2. Jika IDSBR tidak ketemu, Fallback cari berdasarkan Nama Perusahaan
            if not sample_id and nama_perusahaan:
                p_msg = f"🔍 [Pencarian Perusahaan] Fallback mencari berdasarkan Nama Perusahaan: '{nama_perusahaan}'..."
                print(p_msg)
                with open(log_file, "a", encoding="utf-8") as lf:
                    lf.write(p_msg + "\n")
                sample_id = fetch_single_sample_on_demand(url_sampel, headers, survey_period_id, keyword=nama_perusahaan, target_idsbr=sampel_excel)

            if sample_id:
                dict_sampel[sampel_excel] = sample_id  # Simpan ke cache memori

        if not sample_id:
            msg = f" -> [GAGAL] Lewati {sampel_excel}: Sampel tidak ditemukan di server meski sudah dicari manual (IDSBR & Nama Perusahaan)."
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
