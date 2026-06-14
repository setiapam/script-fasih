import requests
import pandas as pd
import re
import time
import os

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

# ================= FUNGSI BANTUAN =================

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
        cookie_match = re.search(r"[Cc]ookie:\s*([^'\"]+)", content)
    cookie = cookie_match.group(1) if cookie_match else ""
    
    xsrf_match = re.search(r"X-XSRF-TOKEN:\s*([^'\"]+)", content)
    xsrf = xsrf_match.group(1) if xsrf_match else ""
    
    return url, cookie, xsrf

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
    print(f"Mengambil data {role_name}...")
    users_dict = {}
    page = 0
    page_size = 500
    
    while True:
        payload = {"pageNumber": page, "pageSize": page_size, "sortBy": "ID", "sortDirection": "ASC", "keywordSearch": ""}
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code != 200: break
        try: json_response = response.json()
        except requests.exceptions.JSONDecodeError: break
            
        data = extract_list_from_json(json_response)
        if not data or len(data) == 0: break
            
        for item in data:
            if not isinstance(item, dict): continue
            email = None
            if 'user' in item and isinstance(item['user'], dict):
                email = item['user'].get('email') or item['user'].get('username')
            if not email: email = item.get('email')
            if email: users_dict[str(email).strip().lower()] = item.get('id')
                
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
                
            for key in ['codeIdentity', 'data1', 'data2', 'data3', 'data4', 'data5']:
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
    # Bersihkan keyword agar pencarian lebih akurat (hilangkan kutip dsb jika perlu)
    search_term = str(keyword).strip()
    
    payload = {
        "draw": 999,
        "columns": [
            {"data": "id", "searchable": True, "orderable": False, "search": {"value": "", "regex": False}},
            {"data": "codeIdentity", "searchable": True, "orderable": False, "search": {"value": "", "regex": False}},
            {"data": "data1", "searchable": True, "orderable": True, "search": {"value": "", "regex": False}},
            {"data": "data2", "searchable": True, "orderable": True, "search": {"value": "", "regex": False}},
            {"data": "data3", "searchable": True, "orderable": True, "search": {"value": "", "regex": False}},
            {"data": "data4", "searchable": True, "orderable": True, "search": {"value": "", "regex": False}}
        ],
        "order": [{"column": 0, "dir": "asc"}],
        "start": 0,
        "length": 100,  # Ambil hingga 100 hasil mirip, lalu cari mana yang idsbr-nya cocok
        "search": {"value": search_term, "regex": False},
        "assignmentExtraParam": {"surveyPeriodId": survey_period_id, "filterTargetType": "TARGET_ONLY", "assignmentErrorStatusType": -1}
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code == 200:
            data = extract_list_from_json(response.json())
            for item in data:
                if not isinstance(item, dict): continue
                
                # Double-Check: Apakah di antara baris hasil pencarian ini ada IDSBR target kita?
                for key in ['codeIdentity', 'data1', 'data2', 'data3', 'data4', 'data5']:
                    val = str(item.get(key, '')).strip()
                    if val.endswith('.0'): val = val[:-2]
                    
                    if val == str(target_idsbr):
                        return item.get('id')
    except Exception:
        pass
        
    return None

def save_dict_to_csv(data_dict, filename, col1_name, col2_name):
    if data_dict:
        df = pd.DataFrame(list(data_dict.items()), columns=[col1_name, col2_name])
        df.to_csv(filename, index=False)

# ================= EKSEKUSI UTAMA =================
def main():
    print("Membaca konfigurasi file cURL...")
    url_pcl, cookie_pcl, xsrf_pcl = parse_curl(FILE_CURL_PCL)
    url_pml, cookie_pml, xsrf_pml = parse_curl(FILE_CURL_PML)
    url_sampel, cookie_sampel, xsrf_sampel = parse_curl(FILE_CURL_SAMPEL)
    url_assign, cookie_assign, xsrf_assign = parse_curl(FILE_CURL_ASSIGN)
    
    headers_pcl = get_headers(cookie_pcl, xsrf_pcl)
    headers_pml = get_headers(cookie_pml, xsrf_pml)
    headers_sampel = get_headers(cookie_sampel, xsrf_sampel)
    headers_assign = get_headers(cookie_assign, xsrf_assign)
    
    if not url_assign:
        print("❌ Proses dihentikan karena cURL Assign gagal dibaca.")
        return
        
    survey_period_id = url_assign.split('/')[-1]
    
    # 1. Tarik Kamus Data Cache
    dict_pencacah = fetch_all_users(url_pcl, headers_pcl, "Pencacah")
    dict_pengawas = fetch_all_users(url_pml, headers_pml, "Pengawas")
    dict_sampel = fetch_all_samples(url_sampel, headers_sampel, survey_period_id)
    
    save_dict_to_csv(dict_pencacah, 'data_pencacah.csv', 'Email', 'RoleUserID')
    save_dict_to_csv(dict_pengawas, 'data_pengawas.csv', 'Email', 'RoleUserID')
    
    # 2. Baca File Excel
    try:
        df = pd.read_excel(EXCEL_FILE, dtype=str)
    except Exception as e:
        print(f"\n❌ Gagal membaca file Excel: {e}")
        return
        
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
            
        email_pcl = str(row[KOLOM_PCL]).strip().lower()
        email_pml = str(row[KOLOM_PML]).strip().lower()
        
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
        if not sample_id:
            # Utamakan cari berdasarkan Nama Perusahaan
            if nama_perusahaan:
                p_msg = f"🔍 [Pencarian Perusahaan] Mencari: '{nama_perusahaan}' (IDSBR: {sampel_excel})..."
                print(p_msg)
                with open(log_file, "a", encoding="utf-8") as lf:
                    lf.write(p_msg + "\n")
                sample_id = fetch_single_sample_on_demand(url_sampel, headers_sampel, survey_period_id, keyword=nama_perusahaan, target_idsbr=sampel_excel)
            
            # Jika perusahaan kosong atau tidak ketemu, Fallback cari pakai angka IDSBR-nya sendiri
            if not sample_id:
                f_msg = f"🔍 [Pencarian IDSBR] Mencari fallback: {sampel_excel}..."
                print(f_msg)
                with open(log_file, "a", encoding="utf-8") as lf:
                    lf.write(f_msg + "\n")
                sample_id = fetch_single_sample_on_demand(url_sampel, headers_sampel, survey_period_id, keyword=sampel_excel, target_idsbr=sampel_excel)

            if sample_id:
                dict_sampel[sampel_excel] = sample_id # Simpan hasil yang baru ketemu
            
        pcl_id = dict_pencacah.get(email_pcl)
        pml_id = dict_pengawas.get(email_pml)
        
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
            msg = f" -> [GAGAL] Lewati {sampel_excel}: Pencacah '{email_pcl}' tidak ditemukan."
            print(msg)
            gagal += 1
            log_assignment.append({"IDSBR": sampel_excel, "Status": f"Gagal - PCL {email_pcl} tidak ada"})
            failed_details.append({"idsbr": sampel_excel, "reason": f"Pencacah '{email_pcl}' tidak terdaftar"})
            with open(log_file, "a", encoding="utf-8") as lf:
                lf.write(msg + "\n")
            continue
        if not pml_id:
            msg = f" -> [GAGAL] Lewati {sampel_excel}: Pengawas '{email_pml}' tidak ditemukan."
            print(msg)
            gagal += 1
            log_assignment.append({"IDSBR": sampel_excel, "Status": f"Gagal - PML {email_pml} tidak ada"})
            failed_details.append({"idsbr": sampel_excel, "reason": f"Pengawas '{email_pml}' tidak terdaftar"})
            with open(log_file, "a", encoding="utf-8") as lf:
                lf.write(msg + "\n")
            continue
            
        # 3. Eksekusi Assign
        assign_payload = {
            "level1Id": None, "level2Id": None, "level3Id": None, "level4Id": None, "level5Id": None,
            "level6Id": None, "level7Id": None, "level8Id": None, "level9Id": None, "level10Id": None,
            "surveyPeriodRoleUserIds": [pml_id, pcl_id],
            "assignmentIds": [sample_id],
            "replaceUser": True
        }
        
        try:
            assign_req = requests.post(url_assign, headers=headers_assign, json=assign_payload, timeout=15)
            if assign_req.status_code in [200, 201]:
                msg = f" -> [SUKSES] Berhasil Assign - {sampel_excel} | PCL: {email_pcl}, PML: {email_pml} (Status: {assign_req.status_code})"
                print(msg)
                sukses += 1
                log_assignment.append({"IDSBR": sampel_excel, "Status": "Berhasil"})
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
            
        time.sleep(0.1) 

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
    
    if log_assignment:
        df_log = pd.DataFrame(log_assignment)
        df_log.to_csv('laporan_hasil_assign.csv', index=False)
        print("\n📝 File 'laporan_hasil_assign.csv' berhasil dibuat!")

if __name__ == "__main__":
    main()