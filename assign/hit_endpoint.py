import requests
import pandas as pd
import re
import time
import os
import json
import sys

# ================= KONFIGURASI =================
EXCEL_FILE = 'assign.xlsx'
KOLOM_SAMPEL = 'idsbr'
KOLOM_PERUSAHAAN = 'perusahaan'  # Kolom baru sesuai instruksi kamu
KOLOM_PCL = 'email_pencacah'
KOLOM_PML = 'email_pengawas'

FILE_CURL_PCL = 'curl_pencacah.txt'
FILE_CURL_PML = 'curl_pengawas.txt'
FILE_CURL_SAMPEL = 'curl_sampel.txt'
FILE_CURL_ASSIGN = 'curl_assign.txt'

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

def show_session_expired_banner(module_curl_path="assign/curl.txt", completed_count=0, total_count=0):
    """Menampilkan banner instruksi yang jelas saat sesi expired agar pengguna tidak salah paham."""
    print("\n" + "=" * 65)
    print("⚠️  [SESI LOGIN KADALUARSA / EXPIRED] (HTTP 401/403)")
    print("=" * 65)
    print(" Sesi login FASIH BPS atau token cURL Anda telah habis masa berlakunya.")
    print(" BUKAN karena data/petugas tidak ada di server, melainkan akses ditolak.")
    print("\n Langkah mudah untuk melanjutkan:")
    print("  1. Buka browser dan login ulang ke https://fasih-sm.bps.go.id")
    print("  2. Buka tab Network (F12), lakukan interaksi/refresh halaman.")
    print(f"  3. Salin (Copy as cURL) request terbaru ke berkas: {module_curl_path}")
    print("  4. Jalankan ulang script (semua progress yang berhasil tersimpan otomatis).")
    if total_count > 0:
        print(f"\n Progress saat ini: {completed_count} dari {total_count} target selesai.")
    print("=" * 65 + "\n")

def normalize_email(email):
    if not email:
        return ""
    email_str = str(email).strip().lower()
    email_str = re.sub(r'@bps\.goid$', '@bps.go.id', email_str)
    email_str = re.sub(r'@bps\.goid\.id$', '@bps.go.id', email_str)
    email_str = re.sub(r'@bps\.go$', '@bps.go.id', email_str)
    return email_str

def parse_curl(filepath):
    if not os.path.exists(filepath):
        print(f"❌ File {filepath} tidak ditemukan! Pastikan file sudah dibuat.")
        return "", "", ""
        
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
        
    url_match = re.search(r"(https?://[^\s'\"^\\]+)", content)
    url = url_match.group(1) if url_match else ""
    
    cookie_match = re.search(r"-b\s+['\"]([^'\"]+)['\"]", content)
    if not cookie_match:
        cookie_match = re.search(r"Cookie:\s*([^'\"]+)", content, re.IGNORECASE)
    cookie = cookie_match.group(1) if cookie_match else ""
    
    xsrf_match = re.search(r"X-XSRF-TOKEN:\s*([^'\"]+)", content, re.IGNORECASE)
    xsrf = xsrf_match.group(1) if xsrf_match else ""
    
    return url, cookie, xsrf

def extract_survey_period_id_from_file(filepath):
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
        
    # 4. Path /surveys/<surveyId>/<surveyPeriodId>/...
    match = re.search(r'/surveys/[a-f0-9\-]{36}/([a-f0-9\-]{36})', content, re.IGNORECASE)
    if match:
        return match.group(1)

    # 5. UUID 36 Karakter dari URL
    url_match = re.search(r"(https?://[^\s'\"^\\]+)", content)
    if url_match:
        uuid_match = re.search(r'([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})', url_match.group(1))
        if uuid_match:
            return uuid_match.group(1)
            
    return ""

def get_headers(cookie, xsrf):
    return {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'Cookie': cookie,
        'X-XSRF-TOKEN': xsrf,
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

def extract_list_from_json(json_data):
    if not isinstance(json_data, dict): return []
    if 'searchData' in json_data and isinstance(json_data['searchData'], list): return json_data['searchData']
    if 'data' in json_data and isinstance(json_data['data'], dict):
        if 'searchData' in json_data['data'] and isinstance(json_data['data']['searchData'], list): return json_data['data']['searchData']
        if 'data' in json_data['data'] and isinstance(json_data['data']['data'], list): return json_data['data']['data']
    if 'data' in json_data and isinstance(json_data['data'], list): return json_data['data']
    return []

def fetch_all_users(url, headers, role_name):
    import urllib.parse
    print(f"Mengambil data {role_name}...")
    users_dict = {}
    page = 0
    page_size = 500
    
    parsed_url = urllib.parse.urlparse(url)
    query_params = urllib.parse.parse_qs(parsed_url.query)
    
    while True:
        query_params['page'] = [str(page)]
        query_params['size'] = [str(page_size)]
        
        new_query = urllib.parse.urlencode(query_params, doseq=True)
        new_url = urllib.parse.urlunparse((
            parsed_url.scheme,
            parsed_url.netloc,
            parsed_url.path,
            parsed_url.params,
            new_query,
            parsed_url.fragment
        ))
        
        response = requests.get(new_url, headers=headers)
        if is_session_expired_response(response):
            raise SessionExpiredException(f"Sesi login kadaluarsa saat mengambil data {role_name} (HTTP {response.status_code}).")
        if response.status_code != 200: break
        try: json_response = response.json()
        except requests.exceptions.JSONDecodeError: break
            
        data = []
        if isinstance(json_response, dict):
            inner_data = json_response.get('data')
            if isinstance(inner_data, dict):
                data = inner_data.get('content') or []
            elif isinstance(inner_data, list):
                data = inner_data
            else:
                data = extract_list_from_json(json_response)
        
        if not data or len(data) == 0: break
            
        for item in data:
            if not isinstance(item, dict): continue
            email = item.get('email') or item.get('username')
            if not email and 'user' in item and isinstance(item['user'], dict):
                email = item['user'].get('email') or item['user'].get('username')
                
            if email:
                allocation_id = item.get('allocationId') or item.get('id')
                if not allocation_id:
                    regions = item.get('regions')
                    if isinstance(regions, list) and len(regions) > 0 and isinstance(regions[0], dict):
                        allocation_id = regions[0].get('allocationId')
                
                if allocation_id:
                    users_dict[str(email).strip().lower()] = allocation_id
                
        if len(data) < page_size: break
        page += 1
        time.sleep(0.3)
        
    print(f"✅ Total {role_name} ditemukan: {len(users_dict)}")
    return users_dict

def fetch_all_samples(url, headers, survey_period_id):
    print("Mengambil data sampel awal (Limit Request: 500)...")
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
        
        response = requests.post(url, headers=headers, json=payload)
        if is_session_expired_response(response):
            raise SessionExpiredException(f"Sesi login kadaluarsa saat mengambil data sampel (HTTP {response.status_code}).")
        if response.status_code != 200: break
        try: json_response = response.json()
        except requests.exceptions.JSONDecodeError: break
            
        data = extract_list_from_json(json_response)
        if not data or len(data) == 0: break
        total_fetched += len(data)
            
        for item in data:
            if not isinstance(item, dict): continue
            sample_id = item.get('id')
            if not sample_id: continue
                
            for key in ['codeIdentity'] + [f'data{i}' for i in range(1, 16)]:
                val = str(item.get(key, '')).strip()
                if val.endswith('.0'): val = val[:-2]
                if val and val.lower() != 'none':
                    samples_dict[val] = sample_id
        
        print(f"  -> Halaman {draw}: Terambil {len(data)} baris (Total: {total_fetched})")
        if len(data) < length: break
        start += length
        draw += 1
        time.sleep(0.3)
        
    print(f"✅ Selesai mengambil {total_fetched} sampel awal ke dalam memori.")
    return samples_dict

def fetch_single_sample_on_demand(url, headers, survey_period_id, keyword, target_idsbr):
    """Mencari 1 sampel secara spesifik ke server dan memverifikasi dengan IDSBR"""
    search_term = str(keyword).strip()
    
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
            response = requests.post(url, headers=headers, json=payload, timeout=10)
            if is_session_expired_response(response):
                raise SessionExpiredException(f"Sesi login kadaluarsa saat mencari sampel {keyword} (HTTP {response.status_code}).")
            if response.status_code == 200:
                data = extract_list_from_json(response.json())
                for item in data:
                    if not isinstance(item, dict): continue
                    
                    # Double-Check: Apakah di antara baris hasil pencarian ini ada IDSBR target kita?
                    for key in ['codeIdentity'] + [f'data{i}' for i in range(1, 16)]:
                        val = str(item.get(key, '')).strip()
                        if val.endswith('.0'): val = val[:-2]
                        
                        if val == str(target_idsbr) or str(target_idsbr) in str(item.get('codeIdentity', '')):
                            return item.get('id')
                break
            elif response.status_code == 429:
                time.sleep(2.0 * (attempt + 1))
            else:
                break
        except SessionExpiredException:
            raise
        except Exception:
            time.sleep(1.0)
        
    return None


def fetch_single_user_on_demand(headers, survey_period_id, email):
    """Mencari 1 user (PCL/PML) secara spesifik berdasarkan email jika belum ada di cache"""
    import urllib.parse
    email_clean = str(email).strip().lower()
    if not email_clean: return None
    
    url = f"https://fasih-sm.bps.go.id/app/api/survey-user/api/v1/allocations-view/by-user?surveyPeriodId={survey_period_id}&keyword={urllib.parse.quote(email_clean)}"
    
    for attempt in range(2):
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if is_session_expired_response(response):
                raise SessionExpiredException(f"Sesi login kadaluarsa saat mencari user {email} (HTTP {response.status_code}).")
            if response.status_code == 200:
                json_resp = response.json()
                data = extract_list_from_json(json_resp)
                for item in data:
                    if not isinstance(item, dict): continue
                    item_email = (item.get('email') or item.get('username') or '').strip().lower()
                    if not item_email and 'user' in item and isinstance(item['user'], dict):
                        item_email = (item['user'].get('email') or item['user'].get('username') or '').strip().lower()
                        
                    if item_email == email_clean or email_clean in item_email:
                        alloc_id = item.get('allocationId') or item.get('id')
                        if not alloc_id and isinstance(item.get('regions'), list) and len(item['regions']) > 0:
                            alloc_id = item['regions'][0].get('allocationId')
                        if alloc_id:
                            return alloc_id
                break
        except SessionExpiredException:
            raise
        except Exception:
            time.sleep(0.5)
    return None


def save_dict_to_csv(data_dict, filename, col1_name, col2_name):
    if data_dict:
        df = pd.DataFrame(list(data_dict.items()), columns=[col1_name, col2_name])
        df.to_csv(filename, index=False)

# ================= EKSEKUSI UTAMA =================
def main():
    print("Membaca konfigurasi file cURL...")
    
    # Cek apakah user punya 4 file cURL lama terpisah secara lengkap
    has_legacy_all_files = (
        os.path.exists(FILE_CURL_PCL) and 
        os.path.exists(FILE_CURL_PML) and 
        os.path.exists(FILE_CURL_SAMPEL) and 
        os.path.exists(FILE_CURL_ASSIGN)
    )
    
    # Prioritas file cURL tunggal
    single_curl_candidates = ['curl.txt', FILE_CURL_ASSIGN, FILE_CURL_SAMPEL, FILE_CURL_PCL, FILE_CURL_PML]
    found_single_curl = None
    for cfile in ['curl.txt'] + single_curl_candidates[1:]:
        if os.path.exists(cfile):
            found_single_curl = cfile
            break

    if has_legacy_all_files and not os.path.exists('curl.txt'):
        print("ℹ️ Menggunakan mode multi-cURL terpisah (legacy).")
        url_pcl, cookie_pcl, xsrf_pcl = parse_curl(FILE_CURL_PCL)
        url_pml, cookie_pml, xsrf_pml = parse_curl(FILE_CURL_PML)
        url_sampel, cookie_sampel, xsrf_sampel = parse_curl(FILE_CURL_SAMPEL)
        url_assign, cookie_assign, xsrf_assign = parse_curl(FILE_CURL_ASSIGN)
        
        headers_pcl = get_headers(cookie_pcl, xsrf_pcl)
        headers_pml = get_headers(cookie_pml, xsrf_pml)
        headers_sampel = get_headers(cookie_sampel, xsrf_sampel)
        headers_assign = get_headers(cookie_assign, xsrf_assign)
        
        survey_period_id = extract_survey_period_id_from_file(FILE_CURL_ASSIGN) or (url_assign.split('/')[-1] if url_assign else "")
    elif found_single_curl:
        print(f"ℹ️ Menggunakan mode 1 cURL terpusat dari '{found_single_curl}'.")
        url_main, cookie, xsrf = parse_curl(found_single_curl)
        if not cookie and not xsrf:
            print(f"❌ File {found_single_curl} kosong atau gagal dibaca.")
            return
            
        headers = get_headers(cookie, xsrf)
        survey_period_id = extract_survey_period_id_from_file(found_single_curl)
        
        if not survey_period_id:
            print("❌ Gagal mengekstrak surveyPeriodId dari cURL. Pastikan cURL valid.")
            return
            
        url_assign = f"https://fasih-sm.bps.go.id/app/api/assignment-general/api/assign-by-selection-allocation/{survey_period_id}"
        url_sampel = "https://fasih-sm.bps.go.id/app/api/analytic/api/v2/assignment/datatable-all-user-survey-periode"
        url_pcl = f"https://fasih-sm.bps.go.id/app/api/survey-user/api/v1/allocations-view/by-user?surveyPeriodId={survey_period_id}"
        url_pml = url_pcl
        
        headers_pcl = headers
        headers_pml = headers
        headers_sampel = headers
        headers_assign = headers
    else:
        print("❌ File cURL tidak ditemukan! Sediakan 1 file 'curl.txt' di folder 'assign/'.")
        return

    if not survey_period_id:
        print("❌ Proses dihentikan karena surveyPeriodId tidak ditemukan.")
        return
        
    print(f"[*] Terdeteksi surveyPeriodId: {survey_period_id}")

    # Cek apakah kegiatan survei berganti (surveyPeriodId baru)
    config_file = 'config.json'
    prev_period_id = None
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                cdata = json.load(f)
                prev_period_id = cdata.get('surveyPeriodId')
        except Exception:
            pass

    if prev_period_id and prev_period_id != survey_period_id:
        print(f"🔄 Terdeteksi pergantian kegiatan survei (Periode Baru: {survey_period_id} | Lama: {prev_period_id}).")
        print("   Mereset cache petugas lama (data_pencacah.csv & data_pengawas.csv)...")
        if os.path.exists('data_pencacah.csv'): os.remove('data_pencacah.csv')
        if os.path.exists('data_pengawas.csv'): os.remove('data_pengawas.csv')

    # Simpan surveyPeriodId aktif ke config.json
    try:
        with open(config_file, 'w', encoding='utf-8') as f:
            json.dump({'surveyPeriodId': survey_period_id}, f, indent=2)
    except Exception:
        pass

    # 1. Tarik Kamus Data Cache
    try:
        dict_pencacah = fetch_all_users(url_pcl, headers_pcl, "Pencacah")
        dict_pengawas = fetch_all_users(url_pml, headers_pml, "Pengawas")
        dict_sampel = fetch_all_samples(url_sampel, headers_sampel, survey_period_id)
    except SessionExpiredException as e:
        print(f"\n[!] {e}")
        show_session_expired_banner(module_curl_path="assign/curl.txt")
        return
    
    # Muat dari CSV cache jika ada
    def load_dict_from_csv(filename):
        u_dict = {}
        if os.path.exists(filename):
            try:
                df_csv = pd.read_csv(filename, dtype=str)
                for _, r in df_csv.iterrows():
                    em = str(r['Email']).strip().lower()
                    rid = str(r['RoleUserID']).strip()
                    if em and rid and rid != 'nan': u_dict[em] = rid
            except Exception: pass
        return u_dict

    csv_pcl = load_dict_from_csv('data_pencacah.csv')
    csv_pml = load_dict_from_csv('data_pengawas.csv')
    for k, v in csv_pcl.items(): dict_pencacah.setdefault(k, v)
    for k, v in csv_pml.items(): dict_pengawas.setdefault(k, v)

    save_dict_to_csv(dict_pencacah, 'data_pencacah.csv', 'Email', 'RoleUserID')
    save_dict_to_csv(dict_pengawas, 'data_pengawas.csv', 'Email', 'RoleUserID')
    
    # 2. Muat Checkpoint Progress Penugasan Berhasil (completed_assign.json & laporan_hasil_assign.csv)
    COMPLETED_FILE = "completed_assign.json"
    REPORT_FILE = "laporan_hasil_assign.csv"
    completed_assign = {}
    if os.path.exists(COMPLETED_FILE):
        try:
            with open(COMPLETED_FILE, "r", encoding="utf-8") as f:
                completed_assign = json.load(f)
        except Exception:
            completed_assign = {}

    if completed_assign.get("surveyPeriodId") != survey_period_id:
        completed_assign = {"surveyPeriodId": survey_period_id, "success_idsbr": []}

    success_set = set(completed_assign.get("success_idsbr", []))

    # Baca juga dari laporan_hasil_assign.csv jika ada (agar riwayat dari eksekusi sebelumnya langsung terdeteksi)
    if os.path.exists(REPORT_FILE):
        try:
            df_rep = pd.read_csv(REPORT_FILE, dtype=str)
            for _, r in df_rep.iterrows():
                idsbr_val = str(r['IDSBR']).strip()
                status_val = str(r['Status']).strip()
                if idsbr_val and idsbr_val != 'nan' and 'Berhasil' in status_val:
                    success_set.add(idsbr_val)
        except Exception:
            pass

    completed_assign["success_idsbr"] = list(success_set)
    try:
        with open(COMPLETED_FILE, "w", encoding="utf-8") as f:
            json.dump(completed_assign, f, indent=2)
    except Exception:
        pass

    # 3. Baca File Excel
    try:
        df = pd.read_excel(EXCEL_FILE, dtype=str)
    except Exception as e:
        print(f"\n❌ Gagal membaca file Excel: {e}")
        return

    if success_set:
        print(f"\n[*] Ditemukan progress penugasan sebelumnya:")
        print(f"    - Sampel sudah berhasil di-assign : {len(success_set)}")
        resume = input("[?] Lanjutkan progress (melewati sampel yang sudah berhasil)? (Y/n): ").strip().lower()
        if resume == 'n':
            print("[*] Memulai ulang dari awal (mereset progress penugasan)...")
            success_set = set()
            completed_assign["success_idsbr"] = []
            try:
                with open(COMPLETED_FILE, "w", encoding="utf-8") as f:
                    json.dump(completed_assign, f, indent=2)
            except Exception:
                pass
        
    # Validasi apakah kolom 'perusahaan' sudah dibuat di Excel
    kolom_tersedia = df.columns.tolist()
    if KOLOM_PERUSAHAAN not in kolom_tersedia:
        print(f"⚠️ Peringatan: Kolom '{KOLOM_PERUSAHAAN}' tidak ditemukan di Excel. Pencarian sekunder dimatikan.")
        
    import datetime
    timestamp_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_file = "execution.log"
    
    with open(log_file, "a", encoding="utf-8") as lf:
        lf.write(f"\n==================================================\n")
        lf.write(f"EKSEKUSI ASSIGN: {timestamp_str}\n")
        lf.write(f"==================================================\n")
        
    sukses = 0
    gagal = 0
    log_assignment = []
    failed_details = []
    
    print("\nMulai proses Assignment...")
    for index, row in df.iterrows():
        if pd.isna(row[KOLOM_SAMPEL]) or str(row[KOLOM_SAMPEL]).lower() == 'nan':
            continue
            
        sampel_excel = str(row[KOLOM_SAMPEL]).strip()
        if sampel_excel.endswith('.0'):
            sampel_excel = sampel_excel[:-2]
            
        if sampel_excel in success_set:
            log_msg = f"Memproses baris {index+1} | IDSBR: {sampel_excel} -> [SKIPPED] Sudah berhasil di-assign sebelumnya."
            print(log_msg)
            sukses += 1
            log_assignment.append({"IDSBR": sampel_excel, "Status": "Berhasil (Skipped - Ter-assign Sebelumnya)"})
            continue

        email_pcl = normalize_email(row[KOLOM_PCL])
        email_pml = normalize_email(row[KOLOM_PML])
        
        # Ambil nama perusahaan jika kolomnya tersedia
        nama_perusahaan = ""
        if KOLOM_PERUSAHAAN in kolom_tersedia:
            nama_perusahaan = str(row[KOLOM_PERUSAHAAN]).strip()
            if nama_perusahaan.lower() == 'nan':
                nama_perusahaan = ""
        
        log_msg = f"Memproses baris {index+1} | IDSBR: {sampel_excel} | PCL: {email_pcl} | PML: {email_pml}"
        print(log_msg)
        with open(log_file, "a", encoding="utf-8") as lf:
            lf.write(log_msg + "\n")
            
        sample_id = dict_sampel.get(sampel_excel)
        
        # JIKA GAGAL DITEMUKAN DI CACHE: Lakukan Pencarian On-Demand
        try:
            if not sample_id:
                # 1. Utamakan pencarian presisi berdasarkan angka IDSBR
                f_msg = f"🔍 [Pencarian IDSBR] Mencari sampel ke server berdasarkan IDSBR: {sampel_excel}..."
                print(f_msg)
                with open(log_file, "a", encoding="utf-8") as lf:
                    lf.write(f_msg + "\n")
                sample_id = fetch_single_sample_on_demand(url_sampel, headers_sampel, survey_period_id, keyword=sampel_excel, target_idsbr=sampel_excel)
                
                # 2. Jika IDSBR tidak ketemu, Fallback cari berdasarkan Nama Perusahaan
                if not sample_id and nama_perusahaan:
                    p_msg = f"🔍 [Pencarian Perusahaan] Fallback mencari berdasarkan Nama Perusahaan: '{nama_perusahaan}'..."
                    print(p_msg)
                    with open(log_file, "a", encoding="utf-8") as lf:
                        lf.write(p_msg + "\n")
                    sample_id = fetch_single_sample_on_demand(url_sampel, headers_sampel, survey_period_id, keyword=nama_perusahaan, target_idsbr=sampel_excel)

                if sample_id:
                    dict_sampel[sampel_excel] = sample_id # Simpan hasil yang baru ketemu
                
            pcl_id = dict_pencacah.get(email_pcl)
            if not pcl_id and email_pcl:
                pcl_id = fetch_single_user_on_demand(headers_pcl, survey_period_id, email_pcl)
                if pcl_id:
                    dict_pencacah[email_pcl] = pcl_id

            pml_id = dict_pengawas.get(email_pml)
            if not pml_id and email_pml:
                pml_id = fetch_single_user_on_demand(headers_pml, survey_period_id, email_pml)
                if pml_id:
                    dict_pengawas[email_pml] = pml_id
        except SessionExpiredException as e:
            print(f" -> [ERROR AUTH] {e}")
            with open(log_file, "a", encoding="utf-8") as lf:
                lf.write(f" -> [ERROR AUTH] {e}\n")
            show_session_expired_banner(module_curl_path="assign/curl.txt", completed_count=sukses, total_count=len(df))
            break
        
        if not sample_id:
            msg = f" -> [GAGAL] Lewati {sampel_excel}: Sampel tidak ditemukan meski sudah dicari manual."
            print(msg)
            gagal += 1
            log_assignment.append({"IDSBR": sampel_excel, "Status": "Gagal - Sampel tidak ada di server"})
            failed_details.append({"idsbr": sampel_excel, "reason": "Sampel tidak ditemukan di server"})
            with open(log_file, "a", encoding="utf-8") as lf:
                lf.write(msg + "\n")
            continue
        if not pcl_id:
            msg = f" -> [GAGAL] Lewati {sampel_excel}: Pencacah '{email_pcl}' belum terdaftar/dialokasikan pada kegiatan survei ini (surveyPeriodId: {survey_period_id})."
            print(msg)
            gagal += 1
            log_assignment.append({"IDSBR": sampel_excel, "Status": f"Gagal - PCL {email_pcl} belum terdaftar di survei ini"})
            failed_details.append({"idsbr": sampel_excel, "reason": f"Pencacah '{email_pcl}' belum dialokasikan pada kegiatan survei ini di FASIH BPS"})
            with open(log_file, "a", encoding="utf-8") as lf:
                lf.write(msg + "\n")
            continue
        if not pml_id:
            msg = f" -> [GAGAL] Lewati {sampel_excel}: Pengawas '{email_pml}' belum terdaftar/dialokasikan pada kegiatan survei ini (surveyPeriodId: {survey_period_id})."
            print(msg)
            gagal += 1
            log_assignment.append({"IDSBR": sampel_excel, "Status": f"Gagal - PML {email_pml} belum terdaftar di survei ini"})
            failed_details.append({"idsbr": sampel_excel, "reason": f"Pengawas '{email_pml}' belum dialokasikan pada kegiatan survei ini di FASIH BPS"})
            with open(log_file, "a", encoding="utf-8") as lf:
                lf.write(msg + "\n")
            continue
            
        # 3. Eksekusi Assign
        assign_payload = {
            "level1Id": None, "level2Id": None, "level3Id": None, "level4Id": None, "level5Id": None,
            "level6Id": None, "level7Id": None, "level8Id": None, "level9Id": None, "level10Id": None,
            "surveyPeriodRoleUserIds": [pml_id, pcl_id],
            "allocationIds": [pml_id, pcl_id],
            "assignmentIds": [sample_id],
            "replaceUser": True
        }
        
        try:
            assign_req = requests.post(url_assign, headers=headers_assign, json=assign_payload, timeout=15)
            if is_session_expired_response(assign_req):
                msg = f" -> [ERROR AUTH] Sesi kadaluarsa saat meng-assign {sampel_excel} (HTTP {assign_req.status_code})."
                print(msg)
                with open(log_file, "a", encoding="utf-8") as lf:
                    lf.write(msg + "\n")
                show_session_expired_banner(module_curl_path="assign/curl.txt", completed_count=sukses, total_count=len(df))
                break
                
            if assign_req.status_code in [200, 201]:
                msg = f" -> [SUKSES] Berhasil Assign - {sampel_excel} | PCL: {email_pcl}, PML: {email_pml} (Status: {assign_req.status_code})"
                print(msg)
                sukses += 1
                log_assignment.append({"IDSBR": sampel_excel, "Status": "Berhasil"})

                # Simpan ke completed_assign.json
                success_set.add(sampel_excel)
                completed_assign["success_idsbr"] = list(success_set)
                try:
                    with open(COMPLETED_FILE, "w", encoding="utf-8") as f:
                        json.dump(completed_assign, f, indent=2)
                except Exception:
                    pass
            else:
                msg = f" -> [GAGAL] Gagal Assign - {sampel_excel} | Server merespon: {assign_req.status_code}"
                print(msg)
                gagal += 1
                log_assignment.append({"IDSBR": sampel_excel, "Status": f"Gagal HTTP {assign_req.status_code}"})
                failed_details.append({"idsbr": sampel_excel, "reason": f"HTTP Status {assign_req.status_code}"})
            with open(log_file, "a", encoding="utf-8") as lf:
                lf.write(msg + "\n")
        except Exception as e:
            msg = f" -> [ERROR] Terjadi kesalahan saat assign {sampel_excel}: {e}"
            print(msg)
            gagal += 1
            log_assignment.append({"IDSBR": sampel_excel, "Status": f"Error: {e}"})
            failed_details.append({"idsbr": sampel_excel, "reason": f"Exception: {e}"})
            with open(log_file, "a", encoding="utf-8") as lf:
                lf.write(msg + "\n")
            
        time.sleep(0.4) 

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
    
    REPORT_FILE = 'laporan_hasil_assign.csv'
    if log_assignment:
        existing_report = {}
        if os.path.exists(REPORT_FILE):
            try:
                df_old = pd.read_csv(REPORT_FILE, dtype=str)
                for _, r in df_old.iterrows():
                    idsbr_val = str(r['IDSBR']).strip()
                    status_val = str(r['Status']).strip()
                    if idsbr_val and idsbr_val != 'nan':
                        existing_report[idsbr_val] = status_val
            except Exception:
                pass

        for item in log_assignment:
            idsbr_val = str(item['IDSBR']).strip()
            status_val = str(item['Status']).strip()
            existing_report[idsbr_val] = status_val

        df_log = pd.DataFrame(list(existing_report.items()), columns=['IDSBR', 'Status'])
        df_log.to_csv(REPORT_FILE, index=False)
        print(f"\n📝 File '{REPORT_FILE}' berhasil diperbarui dengan status terbaru!")

if __name__ == "__main__":
    main()