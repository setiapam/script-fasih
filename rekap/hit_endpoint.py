#!/usr/bin/env python3
"""
Modul Rekap Petugas FASIH BPS
==============================
Mengambil data rekap progress pencacah (PPL/PCL) dan pengawas (PML)
dari API FASIH BPS berdasarkan daftar email di file Excel.

Fitur:
- Membaca daftar email dari file Excel (sheet pertama)
- Filter otomatis: hanya petugas yang memiliki email yang diikutsertakan
- Parsing cURL untuk mendapatkan session cookies & surveyPeriodId
- Pencarian progress per petugas dan per wilayah/Sub SLS
- Resume otomatis secara mulus jika script terhenti/session habis
- Output Excel 3 Sheet:
  1. Detail Per Wilayah (Breakdown per Kode Sub SLS)
  2. Rekap Per Petugas (Total per Petugas)
  3. Ringkasan (Statistik Keseluruhan)

Ketentuan:
- File input: rekap.xlsx (daftar email petugas)
- File session: curl.txt (cURL dari browser)
- File output: hasil_rekap.xlsx
- File resume: progress.json (untuk melanjutkan proses yang gagal)
"""

import json
import shlex
import requests
import os
import time
import re
import sys
import openpyxl
from datetime import datetime


# ============================================================
#  KONFIGURASI
# ============================================================
EXCEL_INPUT = "rekap.xlsx"
CURL_FILE = "curl.txt"
OUTPUT_FILE = "hasil_rekap.xlsx"
PROGRESS_FILE = "progress.json"
LOG_FILE = "execution.log"
REQUEST_DELAY = 1.5  # Delay antar request (detik) untuk menghindari rate limit HTTP 429

# API endpoint
API_URL = "https://fasih-sm.bps.go.id/app/api/analytic/api/v2/assignment/report-progress-by-responsibility"

# Survey Role IDs
ROLE_PML = "93bcf446-c4c1-4462-8ed0-4b0f7ae89e52"  # Pengawas
ROLE_PPL = "6d7d919a-45e5-4779-bb87-2905b49fd31a"  # Pencacah/PPL

# Kolom pada Excel input (1-indexed)
COL_KELURAHAN_TIM = 3   # Kolom C: Kelurahan + TIM
COL_ROLE = 4             # Kolom D: PML / (kosong=PPL)
COL_NAMA = 5             # Kolom E: Nama Mitra
COL_EMAIL = 6            # Kolom F: Email Mitra
COL_KELURAHAN = 7        # Kolom G: Kelurahan

# Status yang direkap dari API
STATUS_KEYS = [
    'APPROVED BY Pengawas',
    'SUBMITTED BY Pencacah',
    'OPEN',
    'DRAFT',
    'REJECTED BY Pengawas',
    'REVOKED BY Pengawas',
]


# ============================================================
#  CURL PARSER
# ============================================================
def parse_curl(curl_file):
    """
    Membaca file cURL, mengekstrak headers, cookies, dan token XSRF.
    Returns dict: {url, headers, cookies_str, xsrf_token, survey_period_id}
    """
    if not os.path.exists(curl_file):
        print(f"❌ File '{curl_file}' tidak ditemukan!")
        print("   Silakan salin cURL dari browser dan simpan ke file tersebut.")
        return None

    with open(curl_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # Normalisasi line continuation
    content = content.replace('\\\n', ' ').replace('\\\r\n', ' ')

    try:
        tokens = shlex.split(content)
    except ValueError as e:
        print(f"[!] Warning shlex: {e}. Mencoba splitting manual.")
        tokens = content.split()

    url = None
    headers = {}
    cookies_str = None
    data = None

    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token.lower() == 'curl':
            i += 1
            continue

        if token in ('-H', '--header') and i + 1 < len(tokens):
            header_val = tokens[i + 1]
            if ':' in header_val:
                k, v = header_val.split(':', 1)
                headers[k.strip()] = v.strip()
            i += 2
        elif token in ('-b', '--cookie') and i + 1 < len(tokens):
            cookies_str = tokens[i + 1]
            i += 2
        elif token in ('-d', '--data', '--data-raw', '--data-binary') and i + 1 < len(tokens):
            data = tokens[i + 1]
            i += 2
        elif token == '--url' and i + 1 < len(tokens):
            url = tokens[i + 1].strip("'\"")
            i += 2
        elif token.startswith('http://') or token.startswith('https://'):
            url = token
            i += 1
        elif token.startswith("'http") or token.startswith('"http'):
            url = token.strip("'\"")
            i += 1
        else:
            if not token.startswith('-') and url is None:
                if '://' in token:
                    url = token.strip("'\"")
            i += 1

    # Gabungkan cookies dari -b dan header Cookie
    if cookies_str:
        if 'Cookie' in headers:
            headers['Cookie'] = headers['Cookie'] + '; ' + cookies_str
        else:
            headers['Cookie'] = cookies_str

    # Ekstrak XSRF token
    xsrf_token = headers.get('x-xsrf-token', '')
    if not xsrf_token:
        xsrf_token = headers.get('X-XSRF-TOKEN', '')
    if not xsrf_token and cookies_str:
        match = re.search(r'XSRF-TOKEN=([^;]+)', cookies_str)
        if match:
            xsrf_token = match.group(1)

    # Ekstrak surveyPeriodId dari data payload atau URL
    survey_period_id = ""
    if data:
        match = re.search(r'"surveyPeriodId"\s*:\s*"([a-f0-9-]{36})"', data)
        if match:
            survey_period_id = match.group(1)

    if not survey_period_id:
        referer = headers.get('referer', headers.get('Referer', ''))
        match = re.search(r'/surveys/[a-f0-9-]{36}/([a-f0-9-]{36})', referer)
        if match:
            survey_period_id = match.group(1)

    if not survey_period_id and url:
        match = re.search(r'([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})', url)
        if match:
            survey_period_id = match.group(1)

    headers.pop('Host', None)
    headers.pop('Content-Length', None)

    return {
        'url': url,
        'headers': headers,
        'xsrf_token': xsrf_token,
        'survey_period_id': survey_period_id,
        'data': data,
    }


# ============================================================
#  EXCEL PARSER: Membaca Daftar Petugas
# ============================================================
def parse_excel_petugas(filepath):
    """
    Membaca Excel daftar petugas dari sheet pertama.
    Hanya petugas yang memiliki email yang akan dimasukkan.
    """
    if not os.path.exists(filepath):
        print(f"❌ File '{filepath}' tidak ditemukan!")
        return []

    wb = openpyxl.load_workbook(filepath, read_only=True, data_only=True)
    ws = wb[wb.sheetnames[0]]
    print(f"[*] Membaca sheet: '{wb.sheetnames[0]}'")

    petugas_list = []
    current_kelurahan = ""
    current_tim = ""
    current_pml_nama = ""
    current_pml_email = ""
    total_rows = 0
    skipped_no_email = 0

    for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=False), start=2):
        cell_values = [cell.value for cell in row]

        while len(cell_values) < 10:
            cell_values.append(None)

        kelurahan_tim = cell_values[COL_KELURAHAN_TIM - 1]  # Kolom C
        role = cell_values[COL_ROLE - 1]                     # Kolom D
        nama = cell_values[COL_NAMA - 1]                     # Kolom E
        email = cell_values[COL_EMAIL - 1]                   # Kolom F
        kelurahan = cell_values[COL_KELURAHAN - 1]           # Kolom G

        if nama is None or str(nama).strip() == '':
            continue

        total_rows += 1
        nama = str(nama).strip()

        if kelurahan_tim and str(kelurahan_tim).strip():
            kel_tim_str = str(kelurahan_tim).strip()
            parts = re.split(r'\n+', kel_tim_str)
            if len(parts) >= 1:
                current_kelurahan = parts[0].strip()
            if len(parts) >= 2:
                current_tim = parts[-1].strip()

        if kelurahan and str(kelurahan).strip():
            display_kelurahan = str(kelurahan).strip()
        else:
            display_kelurahan = current_kelurahan

        is_pml = role and str(role).strip().upper() == 'PML'

        if is_pml:
            current_pml_nama = nama
            current_pml_email = str(email).strip() if email else ""

        clean_email = str(email).strip().lower() if email else ""

        if not clean_email:
            skipped_no_email += 1
            continue

        petugas = {
            'row': row_idx,
            'nama': nama,
            'email': clean_email,
            'role': 'PML' if is_pml else 'PPL',
            'kelurahan': display_kelurahan,
            'tim': current_tim,
            'pml_nama': current_pml_nama if not is_pml else '',
            'pml_email': current_pml_email if not is_pml else '',
        }
        petugas_list.append(petugas)

    wb.close()

    pml_count = sum(1 for p in petugas_list if p['role'] == 'PML')
    ppl_count = sum(1 for p in petugas_list if p['role'] == 'PPL')

    print(f"[*] Total baris dengan nama   : {total_rows}")
    print(f"    - Dilewati (tanpa email)  : {skipped_no_email}")
    print(f"    - Akan diproses           : {len(petugas_list)}")
    print(f"      • PML (Pengawas)        : {pml_count}")
    print(f"      • PPL (Pencacah)        : {ppl_count}")

    return petugas_list


# ============================================================
#  API REQUEST & STATUS EXTRACTION (PER PETUGAS & PER WILAYAH)
# ============================================================
def build_request_headers(parsed_curl):
    """Membangun headers untuk request API."""
    headers = {
        'accept': '*/*',
        'content-type': 'application/json',
        'origin': 'https://fasih-sm.bps.go.id',
        'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36',
    }

    cookie = parsed_curl['headers'].get('Cookie', '')
    if cookie:
        headers['Cookie'] = cookie

    if parsed_curl['xsrf_token']:
        headers['x-xsrf-token'] = parsed_curl['xsrf_token']

    return headers


def build_request_payload(survey_period_id, role_id, email):
    """Membangun JSON payload untuk API request."""
    return {
        "surveyPeriodId": survey_period_id,
        "surveyRoleId": role_id,
        "size": 5,
        "page": 0,
        "search": email,
        "target": "TARGET_ONLY",
        "region": {
            "region1Id": None,
            "region2Id": None,
            "region3Id": None,
            "region4Id": None,
            "region5Id": None,
            "region6Id": None,
            "region7Id": None,
            "region8Id": None,
            "region9Id": None,
            "region10Id": None,
        },
        "regionSummaryLevel": 6,
    }


def fetch_progress(headers, survey_period_id, role_id, email, max_retries=5):
    """
    Mengambil data progress satu petugas dari API dengan penanganan HTTP 429 (Rate Limit).
    Returns: (success: bool, data: dict|None, error_msg: str)
    """
    payload = build_request_payload(survey_period_id, role_id, email)

    for attempt in range(1, max_retries + 1):
        try:
            response = requests.post(
                API_URL,
                headers=headers,
                json=payload,
                timeout=30,
            )

            if response.status_code == 200:
                content_type = response.headers.get('Content-Type', '')
                if 'text/html' in content_type or response.text.strip().startswith('<'):
                    return False, None, "SESSION_EXPIRED"

                data = response.json()
                return True, data, ""

            elif response.status_code in (401, 403):
                return False, None, "SESSION_EXPIRED"

            elif response.status_code == 429:
                retry_after = response.headers.get('Retry-After')
                if retry_after and retry_after.isdigit():
                    wait_time = int(retry_after) + 1
                else:
                    wait_time = attempt * 5  # Exponential backoff: 5s, 10s, 15s, 20s, 25s

                print(f"⏳ Rate Limit (429)! Menunggu {wait_time}s (Attempt {attempt}/{max_retries})...", end=" ", flush=True)
                time.sleep(wait_time)
                continue

            else:
                return False, None, f"HTTP_{response.status_code}"

        except requests.exceptions.Timeout:
            if attempt < max_retries:
                time.sleep(3)
                continue
            return False, None, "TIMEOUT"
        except requests.exceptions.ConnectionError:
            if attempt < max_retries:
                time.sleep(3)
                continue
            return False, None, "CONNECTION_ERROR"
        except requests.exceptions.RequestException as e:
            return False, None, str(e)

    return False, None, "RATE_LIMIT_EXCEEDED (HTTP 429)"


def normalize_status(status_name):
    """
    Normalisasi variasi penulisan nama status dari API FASIH BPS.
    """
    if not status_name:
        return ""
    s = str(status_name).strip()
    s_upper = s.upper()

    mappings = {
        'APPROVED_BY_PENGAWAS': 'APPROVED BY Pengawas',
        'APPROVED_BY_PML': 'APPROVED BY Pengawas',
        'APPROVED BY PML': 'APPROVED BY Pengawas',
        'APPROVED BY PENGAWAS': 'APPROVED BY Pengawas',
        'APPROVED': 'APPROVED BY Pengawas',
        'TOTALAPPROVED': 'APPROVED BY Pengawas',
        'APPROVEDBYPENGAWAS': 'APPROVED BY Pengawas',

        'SUBMITTED_BY_PENCACAH': 'SUBMITTED BY Pencacah',
        'SUBMITTED_BY_PPL': 'SUBMITTED BY Pencacah',
        'SUBMITTED BY PPL': 'SUBMITTED BY Pencacah',
        'SUBMITTED BY PENCACAH': 'SUBMITTED BY Pencacah',
        'SUBMITTED': 'SUBMITTED BY Pencacah',
        'TOTALSUBMITTED': 'SUBMITTED BY Pencacah',
        'SUBMITTEDBYPENCACAH': 'SUBMITTED BY Pencacah',

        'REJECTED_BY_PENGAWAS': 'REJECTED BY Pengawas',
        'REJECTED_BY_PML': 'REJECTED BY Pengawas',
        'REJECTED BY PML': 'REJECTED BY Pengawas',
        'REJECTED BY PENGAWAS': 'REJECTED BY Pengawas',
        'REJECTED': 'REJECTED BY Pengawas',
        'TOTALREJECTED': 'REJECTED BY Pengawas',

        'REVOKED_BY_PENGAWAS': 'REVOKED BY Pengawas',
        'REVOKED_BY_PML': 'REVOKED BY Pengawas',
        'REVOKED BY PML': 'REVOKED BY Pengawas',
        'REVOKED BY PENGAWAS': 'REVOKED BY Pengawas',
        'REVOKED': 'REVOKED BY Pengawas',
        'TOTALREVOKED': 'REVOKED BY Pengawas',

        'OPEN': 'OPEN',
        'TOTALOPEN': 'OPEN',
        'DRAFT': 'DRAFT',
        'TOTALDRAFT': 'DRAFT',
    }

    if s_upper in mappings:
        return mappings[s_upper]

    if 'APPROVED' in s_upper:
        return 'APPROVED BY Pengawas'
    if 'SUBMITTED' in s_upper:
        return 'SUBMITTED BY Pencacah'
    if 'REJECTED' in s_upper:
        return 'REJECTED BY Pengawas'
    if 'REVOKED' in s_upper:
        return 'REVOKED BY Pengawas'
    if 'OPEN' in s_upper:
        return 'OPEN'
    if 'DRAFT' in s_upper:
        return 'DRAFT'

    return ""


def crawl_node_statuses(node, target_dict, depth=0):
    """
    Penjelajah rekursif untuk menemukan status dan jumlahnya dalam satu node/objek JSON.
    """
    if depth > 10 or not node:
        return

    if isinstance(node, dict):
        st_val = None
        # Evaluasi apakah ada string bernilai nama status di dict ini
        for k, v in node.items():
            if isinstance(v, str):
                norm = normalize_status(v)
                if norm:
                    st_val = norm
                    break

        if st_val:
            num_val = None
            # Cari angka pendamping di dict ini
            for k, v in node.items():
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    if any(term in k.lower() for term in ['count', 'total', 'val', 'amount', 'size', 'qty', 'num', 'target']):
                        num_val = int(v)
                        break
            if num_val is None:
                for k, v in node.items():
                    if isinstance(v, (int, float)) and not isinstance(v, bool):
                        if not any(term in k.lower() for term in ['id', 'code', 'level', 'page']):
                            num_val = int(v)
                            break
            if num_val is not None:
                target_dict[st_val] += num_val

        # Evaluasi jika key bernilai nama status langsung e.g. {'APPROVED BY Pengawas': 162}
        for k, v in node.items():
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                norm = normalize_status(k)
                if norm and not st_val:
                    target_dict[norm] += int(v)
            elif isinstance(v, (dict, list)):
                crawl_node_statuses(v, target_dict, depth + 1)

    elif isinstance(node, list):
        for item in node:
            crawl_node_statuses(item, target_dict, depth + 1)


def extract_progress_data(api_response):
    """
    Mengekstrak data progress dari API response FASIH BPS.

    Returns:
        dict: {
            'summary': { totalAssignment, APPROVED..., SUBMITTED..., ... },
            'regions': [
                { kodeSubSls, totalAssignment, APPROVED..., SUBMITTED..., ... },
                ...
            ]
        }
    """
    summary = {
        'totalAssignment': 0,
        'APPROVED BY Pengawas': 0,
        'SUBMITTED BY Pencacah': 0,
        'OPEN': 0,
        'DRAFT': 0,
        'REJECTED BY Pengawas': 0,
        'REVOKED BY Pengawas': 0,
    }
    regions = []

    if not api_response:
        return {'summary': summary, 'regions': regions}

    data = api_response
    if isinstance(data, dict) and 'data' in data:
        data = data['data']

    records = []
    if isinstance(data, dict):
        if 'content' in data and isinstance(data['content'], list):
            records = data['content']
        elif 'searchData' in data and isinstance(data['searchData'], list):
            records = data['searchData']
        else:
            records = [data]
    elif isinstance(data, list):
        records = data

    if not records:
        return {'summary': summary, 'regions': regions}

    main_record = records[0]
    region_nodes = []

    # 1. Cari list region dalam main_record
    if isinstance(main_record, dict):
        for key in ['regionProgressList', 'regionList', 'regions', 'details', 'content', 'items', 'responsibilities', 'subSlsList']:
            if key in main_record and isinstance(main_record[key], list) and len(main_record[key]) > 0:
                region_nodes = main_record[key]
                break

    # 2. Jika records sendiri merupakan list region
    if not region_nodes and isinstance(records, list) and len(records) > 0:
        first = records[0]
        if isinstance(first, dict) and any(rk in first for rk in ['subSlsCode', 'regionCode', 'code', 'fullCode', 'regionName', 'codeIdentity']):
            region_nodes = records

    # 3. Pencarian rekursif list region jika belum ketemu
    if not region_nodes and isinstance(main_record, dict):
        def find_region_list(node, depth=0):
            if depth > 5:
                return None
            if isinstance(node, dict):
                for k, v in node.items():
                    if isinstance(v, list) and len(v) > 0 and isinstance(v[0], dict):
                        if any(rk in v[0] for rk in ['subSlsCode', 'regionCode', 'code', 'fullCode', 'regionName', 'codeIdentity', 'statusList', 'statuses']):
                            return v
                    if isinstance(v, dict):
                        res = find_region_list(v, depth + 1)
                        if res:
                            return res
            return None
        found = find_region_list(main_record)
        if found:
            region_nodes = found

    # Parsing setiap region node
    for rnode in region_nodes:
        if not isinstance(rnode, dict):
            continue

        region_code = ""
        for rk in ['subSlsCode', 'regionCode', 'fullCode', 'code', 'regionName', 'codeIdentity', 'name', 'id']:
            if rk in rnode and rnode[rk]:
                region_code = str(rnode[rk]).strip()
                break

        r_summary = {
            'kodeSubSls': region_code,
            'totalAssignment': 0,
            'APPROVED BY Pengawas': 0,
            'SUBMITTED BY Pencacah': 0,
            'OPEN': 0,
            'DRAFT': 0,
            'REJECTED BY Pengawas': 0,
            'REVOKED BY Pengawas': 0,
        }

        crawl_node_statuses(rnode, r_summary)

        if r_summary['totalAssignment'] == 0:
            r_summary['totalAssignment'] = sum(r_summary[s] for s in STATUS_KEYS)

        if r_summary['kodeSubSls'] or r_summary['totalAssignment'] > 0:
            regions.append(r_summary)
            summary['totalAssignment'] += r_summary['totalAssignment']
            for s in STATUS_KEYS:
                summary[s] += r_summary[s]

    # Fallback jika tidak ada region node khusus
    if not regions:
        crawl_node_statuses(main_record, summary)
        if summary['totalAssignment'] == 0:
            summary['totalAssignment'] = sum(summary[s] for s in STATUS_KEYS)

    return {'summary': summary, 'regions': regions}


# ============================================================
#  PROGRESS / RESUME MANAGEMENT
# ============================================================
def load_progress():
    """Memuat progress sebelumnya dari file JSON."""
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def save_progress(progress_data):
    """Menyimpan progress ke file JSON."""
    try:
        with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
            json.dump(progress_data, f, indent=2, ensure_ascii=False)
    except IOError as e:
        print(f"[!] Gagal menyimpan progress: {e}")


def log_message(message):
    """Menulis pesan ke file log."""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_line = f"[{timestamp}] {message}"
    try:
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(log_line + '\n')
    except IOError:
        pass


# ============================================================
#  OUTPUT: Menulis Hasil ke Excel (3 Sheet)
# ============================================================
def write_output_excel(petugas_list, progress_results, output_file):
    """
    Menulis hasil rekap ke file Excel dengan 3 Sheet:
    1. Detail Per Wilayah: Breakdown per baris untuk setiap Kode Sub SLS
    2. Rekap Per Petugas: Ringkasan 1 baris per petugas (menampilkan Total Sub SLS & Total Assignment)
    3. Ringkasan: Statistik keseluruhan
    """
    wb = openpyxl.Workbook()

    # Sheet 1: Detail Per Wilayah
    ws_detail = wb.active
    ws_detail.title = "Detail Per Wilayah"

    # Sheet 2: Rekap Per Petugas
    ws_rekap = wb.create_sheet("Rekap Per Petugas")

    # Sheet 3: Ringkasan
    ws_summary = wb.create_sheet("Ringkasan")

    # ---- STYLES ----
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

    header_font = Font(name='Calibri', bold=True, size=11, color='FFFFFF')
    header_fill = PatternFill(start_color='2F5496', end_color='2F5496', fill_type='solid')
    header_alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)

    pml_fill = PatternFill(start_color='D6E4F0', end_color='D6E4F0', fill_type='solid')
    pml_font = Font(name='Calibri', bold=True, size=10)
    ppl_font = Font(name='Calibri', size=10)

    thin_border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin'),
    )

    success_fill = PatternFill(start_color='E2EFDA', end_color='E2EFDA', fill_type='solid')
    warning_fill = PatternFill(start_color='FCE4D6', end_color='FCE4D6', fill_type='solid')
    error_fill = PatternFill(start_color='F8D7DA', end_color='F8D7DA', fill_type='solid')

    number_alignment = Alignment(horizontal='center', vertical='center')

    # ============================================================
    # 1. SHEET 1: DETAIL PER WILAYAH
    # ============================================================
    headers_detail = [
        'No',
        'Kelurahan',
        'Tim',
        'Role',
        'Nama Mitra',
        'Email Mitra',
        'Nama PML',
        'Kode Sub SLS',
        'Total Assignment',
        'Approved\n(Pengawas)',
        'Submitted\n(Pencacah)',
        'Open',
        'Draft',
        'Rejected\n(Pengawas)',
        'Revoked\n(Pengawas)',
        'Status',
    ]

    for col_idx, header in enumerate(headers_detail, 1):
        cell = ws_detail.cell(row=1, column=col_idx, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment
        cell.border = thin_border

    row_detail = 2
    prev_kelurahan_tim_d = ""
    entry_no_d = 0

    for petugas in petugas_list:
        email = petugas['email']
        nama = petugas['nama']
        role = petugas['role']
        kelurahan = petugas['kelurahan']
        tim = petugas['tim']
        pml_nama = petugas['pml_nama']
        kelurahan_tim_key = f"{kelurahan}|{tim}"

        if kelurahan_tim_key != prev_kelurahan_tim_d:
            prev_kelurahan_tim_d = kelurahan_tim_key
            entry_no_d = 0

        entry_no_d += 1

        result = progress_results.get(email, {})
        data_obj = result.get('data', {})
        regions = data_obj.get('regions', [])
        status = result.get('status', 'BELUM_DIPROSES')

        # Jika ada data breakdown per region
        if regions:
            for reg in regions:
                kode_subsls = reg.get('kodeSubSls', '-')
                tot = reg.get('totalAssignment', 0)
                appr = reg.get('APPROVED BY Pengawas', 0)
                subm = reg.get('SUBMITTED BY Pencacah', 0)
                opn = reg.get('OPEN', 0)
                dft = reg.get('DRAFT', 0)
                rej = reg.get('REJECTED BY Pengawas', 0)
                rvk = reg.get('REVOKED BY Pengawas', 0)

                status_display = "✅ OK" if status == 'SUCCESS' else status

                row_data = [
                    entry_no_d,
                    kelurahan,
                    tim,
                    role,
                    nama,
                    email,
                    pml_nama if pml_nama else '-',
                    kode_subsls if kode_subsls else '-',
                    tot,
                    appr,
                    subm,
                    opn,
                    dft,
                    rej,
                    rvk,
                    status_display,
                ]

                for col_idx, value in enumerate(row_data, 1):
                    cell = ws_detail.cell(row=row_detail, column=col_idx, value=value)
                    cell.border = thin_border
                    cell.alignment = Alignment(vertical='center')

                    if col_idx >= 8 and col_idx <= 15:
                        cell.alignment = number_alignment

                    if role == 'PML':
                        cell.fill = pml_fill
                        cell.font = pml_font
                    else:
                        cell.font = ppl_font

                    if col_idx == len(headers_detail):
                        if status == 'SUCCESS':
                            cell.fill = success_fill
                        elif status in ('NOT_FOUND', 'SESSION_EXPIRED'):
                            cell.fill = error_fill

                row_detail += 1
        else:
            # Jika tidak ada breakdown wilayah (gagal/kosong)
            summary_obj = data_obj.get('summary', {})
            tot = summary_obj.get('totalAssignment', '-')
            appr = summary_obj.get('APPROVED BY Pengawas', '-')
            subm = summary_obj.get('SUBMITTED BY Pencacah', '-')
            opn = summary_obj.get('OPEN', '-')
            dft = summary_obj.get('DRAFT', '-')
            rej = summary_obj.get('REJECTED BY Pengawas', '-')
            rvk = summary_obj.get('REVOKED BY Pengawas', '-')

            status_display = "❌ Tidak Ditemukan" if status == 'NOT_FOUND' else status

            row_data = [
                entry_no_d,
                kelurahan,
                tim,
                role,
                nama,
                email,
                pml_nama if pml_nama else '-',
                '-',
                tot,
                appr,
                subm,
                opn,
                dft,
                rej,
                rvk,
                status_display,
            ]

            for col_idx, value in enumerate(row_data, 1):
                cell = ws_detail.cell(row=row_detail, column=col_idx, value=value)
                cell.border = thin_border
                cell.alignment = Alignment(vertical='center')

                if col_idx >= 8 and col_idx <= 15:
                    cell.alignment = number_alignment

                if role == 'PML':
                    cell.fill = pml_fill
                    cell.font = pml_font
                else:
                    cell.font = ppl_font

            row_detail += 1

    # ============================================================
    # 2. SHEET 2: REKAP PER PETUGAS
    # ============================================================
    headers_rekap = [
        'No',
        'Kelurahan',
        'Tim',
        'Role',
        'Nama Mitra',
        'Email Mitra',
        'Nama PML',
        'Jml Sub SLS',
        'Total Assignment',
        'Approved\n(Pengawas)',
        'Submitted\n(Pencacah)',
        'Open',
        'Draft',
        'Rejected\n(Pengawas)',
        'Revoked\n(Pengawas)',
        'Status',
    ]

    for col_idx, header in enumerate(headers_rekap, 1):
        cell = ws_rekap.cell(row=1, column=col_idx, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment
        cell.border = thin_border

    row_rekap = 2
    prev_kelurahan_tim_r = ""
    entry_no_r = 0

    for petugas in petugas_list:
        email = petugas['email']
        nama = petugas['nama']
        role = petugas['role']
        kelurahan = petugas['kelurahan']
        tim = petugas['tim']
        pml_nama = petugas['pml_nama']
        kelurahan_tim_key = f"{kelurahan}|{tim}"

        if kelurahan_tim_key != prev_kelurahan_tim_r:
            prev_kelurahan_tim_r = kelurahan_tim_key
            entry_no_r = 0

        entry_no_r += 1

        result = progress_results.get(email, {})
        data_obj = result.get('data', {})
        summary_obj = data_obj.get('summary', {})
        regions = data_obj.get('regions', [])
        status = result.get('status', 'BELUM_DIPROSES')

        total_assignment = summary_obj.get('totalAssignment', '')
        approved = summary_obj.get('APPROVED BY Pengawas', '')
        submitted = summary_obj.get('SUBMITTED BY Pencacah', '')
        open_count = summary_obj.get('OPEN', '')
        draft = summary_obj.get('DRAFT', '')
        rejected = summary_obj.get('REJECTED BY Pengawas', '')
        revoked = summary_obj.get('REVOKED BY Pengawas', '')
        jml_subsls = len(regions) if regions else (1 if isinstance(total_assignment, (int, float)) and total_assignment > 0 else 0)

        if status == 'SUCCESS':
            if isinstance(total_assignment, (int, float)) and total_assignment > 0:
                non_open = _to_int(approved) + _to_int(submitted)
                pct = round(non_open / total_assignment * 100, 1)
                if pct >= 100:
                    status_display = "✅ Selesai 100%"
                elif pct >= 50:
                    status_display = f"🔶 {pct}%"
                else:
                    status_display = f"⚠️ {pct}%"
            else:
                status_display = "✅ Data Diterima"
        elif status == 'NOT_FOUND':
            status_display = "❌ Tidak Ditemukan"
        elif status == 'SESSION_EXPIRED':
            status_display = "🔄 Session Habis"
        elif status == 'BELUM_DIPROSES':
            status_display = "⏳ Belum Diproses"
        else:
            status_display = f"❌ {status}"

        row_data = [
            entry_no_r,
            kelurahan,
            tim,
            role,
            nama,
            email,
            pml_nama if pml_nama else '-',
            jml_subsls if jml_subsls > 0 else '-',
            total_assignment if total_assignment != '' else '-',
            approved if approved != '' else '-',
            submitted if submitted != '' else '-',
            open_count if open_count != '' else '-',
            draft if draft != '' else '-',
            rejected if rejected != '' else '-',
            revoked if revoked != '' else '-',
            status_display,
        ]

        for col_idx, value in enumerate(row_data, 1):
            cell = ws_rekap.cell(row=row_rekap, column=col_idx, value=value)
            cell.border = thin_border
            cell.alignment = Alignment(vertical='center')

            if col_idx >= 8 and col_idx <= 15:
                cell.alignment = number_alignment

            if role == 'PML':
                cell.fill = pml_fill
                cell.font = pml_font
            else:
                cell.font = ppl_font

            if col_idx == len(headers_rekap):
                if status == 'SUCCESS':
                    cell.fill = success_fill
                elif status in ('NOT_FOUND', 'SESSION_EXPIRED'):
                    cell.fill = error_fill
                elif status == 'BELUM_DIPROSES':
                    cell.fill = warning_fill

        row_rekap += 1

    # ============================================================
    # 3. SHEET 3: RINGKASAN
    # ============================================================
    ws_summary.cell(row=1, column=1, value="RINGKASAN REKAP PROGRESS PETUGAS & WILAYAH").font = Font(bold=True, size=14)
    ws_summary.cell(row=2, column=1, value=f"Tanggal: {datetime.now().strftime('%d %B %Y %H:%M')}").font = Font(size=10)

    total_petugas = len(petugas_list)
    total_pml = sum(1 for p in petugas_list if p['role'] == 'PML')
    total_ppl = sum(1 for p in petugas_list if p['role'] == 'PPL')
    total_success = sum(1 for r in progress_results.values() if r.get('status') == 'SUCCESS')
    total_not_found = sum(1 for r in progress_results.values() if r.get('status') == 'NOT_FOUND')
    total_failed = sum(1 for r in progress_results.values()
                       if r.get('status') not in ('SUCCESS', 'NOT_FOUND', ''))

    grand_total_subsls = 0
    grand_total_assignment = 0
    grand_approved = 0
    grand_submitted = 0
    grand_open = 0
    grand_draft = 0
    grand_rejected = 0
    grand_revoked = 0

    for r in progress_results.values():
        if r.get('status') == 'SUCCESS':
            d = r.get('data', {})
            sum_obj = d.get('summary', {})
            regs = d.get('regions', [])
            grand_total_subsls += len(regs)
            grand_total_assignment += _to_int(sum_obj.get('totalAssignment', 0))
            grand_approved += _to_int(sum_obj.get('APPROVED BY Pengawas', 0))
            grand_submitted += _to_int(sum_obj.get('SUBMITTED BY Pencacah', 0))
            grand_open += _to_int(sum_obj.get('OPEN', 0))
            grand_draft += _to_int(sum_obj.get('DRAFT', 0))
            grand_rejected += _to_int(sum_obj.get('REJECTED BY Pengawas', 0))
            grand_revoked += _to_int(sum_obj.get('REVOKED BY Pengawas', 0))

    summary_data = [
        ('STATISTIK PETUGAS', ''),
        ('Total Petugas (dengan email)', total_petugas),
        ('PML (Pengawas)', total_pml),
        ('PPL (Pencacah)', total_ppl),
        ('', ''),
        ('STATUS PENGAMBILAN DATA', ''),
        ('Berhasil Diambil', total_success),
        ('Tidak Ditemukan di Sistem', total_not_found),
        ('Gagal (Session/Error)', total_failed),
        ('', ''),
        ('TOTAL AGREGASI (keseluruhan)', ''),
        ('Total Sub SLS (Wilayah)', grand_total_subsls),
        ('Total Assignment', grand_total_assignment),
        ('Approved by Pengawas', grand_approved),
        ('Submitted by Pencacah', grand_submitted),
        ('Open', grand_open),
        ('Draft', grand_draft),
        ('Rejected by Pengawas', grand_rejected),
        ('Revoked by Pengawas', grand_revoked),
    ]

    for i, (label, value) in enumerate(summary_data, start=4):
        label_cell = ws_summary.cell(row=i, column=1, value=label)
        value_cell = ws_summary.cell(row=i, column=2, value=value)
        if value == '' and label != '':
            label_cell.font = Font(bold=True, size=11, color='2F5496')
        else:
            label_cell.font = Font(size=10)
            value_cell.font = Font(size=10)

    # ---- KOLOM WIDTH ----
    col_widths_detail = {
        1: 5,    # No
        2: 22,   # Kelurahan
        3: 12,   # Tim
        4: 6,    # Role
        5: 28,   # Nama Mitra
        6: 35,   # Email Mitra
        7: 28,   # Nama PML
        8: 22,   # Kode Sub SLS
        9: 16,   # Total Assignment
        10: 14,  # Approved
        11: 14,  # Submitted
        12: 10,  # Open
        13: 10,  # Draft
        14: 14,  # Rejected
        15: 14,  # Revoked
        16: 20,  # Status
    }
    for col_idx, width in col_widths_detail.items():
        ws_detail.column_dimensions[openpyxl.utils.get_column_letter(col_idx)].width = width
        ws_rekap.column_dimensions[openpyxl.utils.get_column_letter(col_idx)].width = width

    ws_summary.column_dimensions['A'].width = 35
    ws_summary.column_dimensions['B'].width = 15

    ws_detail.auto_filter.ref = f"A1:{openpyxl.utils.get_column_letter(len(headers_detail))}{row_detail - 1}"
    ws_detail.freeze_panes = 'A2'

    ws_rekap.auto_filter.ref = f"A1:{openpyxl.utils.get_column_letter(len(headers_rekap))}{row_rekap - 1}"
    ws_rekap.freeze_panes = 'A2'

    wb.save(output_file)
    print(f"\n[✓] Hasil rekap disimpan ke: {output_file}")
    print(f"    Sheet 1: Detail Per Wilayah ({row_detail - 2} baris data)")
    print(f"    Sheet 2: Rekap Per Petugas ({row_rekap - 2} baris data)")
    print(f"    Sheet 3: Ringkasan")


def _to_int(value):
    """Konversi value ke int, return 0 jika gagal."""
    if isinstance(value, (int, float)):
        return int(value)
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


# ============================================================
#  MAIN: Alur Utama
# ============================================================
def main():
    print("=" * 60)
    print("   MODUL REKAP PROGRESS PETUGAS - FASIH BPS")
    print("=" * 60)

    # ---- 1. Parse cURL ----
    print("\n[1/4] Membaca session dari cURL...")
    parsed = parse_curl(CURL_FILE)
    if not parsed:
        sys.exit(1)

    survey_period_id = parsed['survey_period_id']
    if not survey_period_id:
        print("❌ Tidak dapat menemukan surveyPeriodId dari cURL!")
        print("   Pastikan cURL yang di-copy benar (dari halaman report progress).")
        sys.exit(1)

    print(f"   ✓ Survey Period ID: {survey_period_id}")
    print(f"   ✓ XSRF Token: {parsed['xsrf_token'][:20]}..." if parsed['xsrf_token'] else "   ⚠ XSRF Token tidak ditemukan")

    headers = build_request_headers(parsed)

    # ---- 2. Baca Excel Petugas ----
    print(f"\n[2/4] Membaca daftar petugas dari '{EXCEL_INPUT}'...")
    petugas_list = parse_excel_petugas(EXCEL_INPUT)
    if not petugas_list:
        print("❌ Tidak ada petugas dengan email yang ditemukan!")
        sys.exit(1)

    # ---- 3. Cek & Load Progress (Resume Otomatis) ----
    print(f"\n[3/4] Memeriksa progress sebelumnya...")
    progress = load_progress()
    already_done = set()

    if progress and 'results' in progress:
        for email_key, result in progress['results'].items():
            if result.get('status') in ('SUCCESS', 'NOT_FOUND'):
                already_done.add(email_key)

    if already_done:
        existing_in_list = sum(1 for p in petugas_list if p['email'] in already_done)
        remaining = len(petugas_list) - existing_in_list
        print(f"   ✓ Ditemukan cache progress: {existing_in_list}/{len(petugas_list)} petugas di Excel sudah pernah diambil.")
        if remaining > 0:
            print(f"   → Hanya mengambil {remaining} petugas baru yang belum ada di cache...")
        else:
            print(f"   → Semua {len(petugas_list)} petugas di Excel sudah ada di cache.")
    else:
        progress = {'results': {}}

    # ---- 4. Proses Fetch Data Progress ----
    print(f"\n[4/4] Mengambil data progress dari API...")
    print("-" * 60)

    total_to_process = len(petugas_list) - len(already_done)
    processed = 0
    success_count = 0
    fail_count = 0
    session_expired = False

    log_message(f"=== Mulai proses rekap: {len(petugas_list)} petugas ===")

    for idx, petugas in enumerate(petugas_list):
        email = petugas['email']
        nama = petugas['nama']
        role = petugas['role']

        # Skip jika sudah berhasil diproses sebelumnya
        if email in already_done:
            continue

        processed += 1
        role_id = ROLE_PML if role == 'PML' else ROLE_PPL
        role_label = "PML" if role == 'PML' else "PPL"

        print(f"  [{processed}/{total_to_process}] {role_label} - {nama} ({email})...", end=" ", flush=True)

        # Lakukan request ke API
        success, api_data, error_msg = fetch_progress(headers, survey_period_id, role_id, email)

        if success:
            extracted = extract_progress_data(api_data)
            summary_res = extracted.get('summary', {})
            regions_res = extracted.get('regions', [])

            if summary_res and summary_res.get('totalAssignment', 0) > 0:
                progress['results'][email] = {
                    'status': 'SUCCESS',
                    'data': extracted,
                    'timestamp': datetime.now().isoformat(),
                }
                already_done.add(email)
                success_count += 1

                total_asgn = summary_res.get('totalAssignment', 0)
                n_regions = len(regions_res)
                approved = summary_res.get('APPROVED BY Pengawas', 0)
                submitted = summary_res.get('SUBMITTED BY Pencacah', 0)
                open_c = summary_res.get('OPEN', 0)
                draft = summary_res.get('DRAFT', 0)
                rejected = summary_res.get('REJECTED BY Pengawas', 0)
                revoked = summary_res.get('REVOKED BY Pengawas', 0)
                print(f"✓ Total: {total_asgn} ({n_regions} Sub SLS) | Approved: {approved} | Submitted: {submitted} | Open: {open_c} | Draft: {draft} | Rejected: {rejected} | Revoked: {revoked}")
            else:
                progress['results'][email] = {
                    'status': 'NOT_FOUND',
                    'data': {'summary': summary_empty(), 'regions': []},
                    'timestamp': datetime.now().isoformat(),
                }
                already_done.add(email)
                print("⚠ Data kosong / tidak ditemukan")
        else:
            if error_msg == "SESSION_EXPIRED":
                progress['results'][email] = {
                    'status': 'SESSION_EXPIRED',
                    'data': {},
                    'timestamp': datetime.now().isoformat(),
                }
                fail_count += 1
                session_expired = True
                print("❌ SESSION HABIS!")
                log_message(f"Session expired saat memproses: {email}")

                save_progress(progress)

                print("\n" + "=" * 60)
                print("⚠️  SESSION HABIS / EXPIRED!")
                print("=" * 60)
                print("Langkah untuk melanjutkan:")
                print("1. Login kembali ke FASIH BPS di browser")
                print("2. Copy cURL baru dan simpan ke: rekap/curl.txt")
                print("3. Jalankan ulang script ini (progress tersimpan otomatis)")
                print(f"\nProgress tersimpan: {len(already_done)} selesai dari {len(petugas_list)} total petugas.")
                print("=" * 60)
                break
            else:
                progress['results'][email] = {
                    'status': error_msg,
                    'data': {},
                    'timestamp': datetime.now().isoformat(),
                }
                fail_count += 1
                print(f"❌ Error: {error_msg}")
                log_message(f"Error untuk {email}: {error_msg}")

        # Simpan progress SETIAP kali request selesai
        save_progress(progress)

        time.sleep(REQUEST_DELAY)

    # Simpan progress final
    save_progress(progress)

    # ---- 5. Generate Output Excel ----
    if not session_expired or success_count > 0 or len(already_done) > 0:
        print(f"\n[*] Membuat file output Excel...")
        write_output_excel(petugas_list, progress['results'], OUTPUT_FILE)

    # ---- RINGKASAN AKHIR ----
    total_processed = len(already_done)
    total_all = len(petugas_list)

    print("\n" + "=" * 60)
    print("           RINGKASAN AKHIR REKAP")
    print("=" * 60)
    print(f"  Total petugas (email): {total_all}")
    print(f"  ─────────────────────────────────")
    print(f"  Berhasil diambil     : {total_processed}/{total_all}")
    print(f"  Gagal                : {fail_count}")
    if session_expired:
        remaining = total_all - total_processed
        print(f"  Sisa belum diproses  : {remaining}")
        print(f"\n  ⚠ Session habis. Update rekap/curl.txt lalu jalankan ulang script ini untuk melanjutkan.")
    print("=" * 60)

    # Simpan progress akhir (progress.json dipertahankan sebagai cache)
    save_progress(progress)

    log_message(f"=== Selesai: {total_processed}/{total_all} berhasil, {fail_count} gagal ===")
    print("\n[i] Data progress tersimpan di 'rekap/progress.json'.")
    print("    Hapus file 'rekap/progress.json' jika Anda ingin mengambil ulang seluruh data dari awal.")


def summary_empty():
    return {
        'totalAssignment': 0,
        'APPROVED BY Pengawas': 0,
        'SUBMITTED BY Pencacah': 0,
        'OPEN': 0,
        'DRAFT': 0,
        'REJECTED BY Pengawas': 0,
        'REVOKED BY Pengawas': 0,
    }


if __name__ == "__main__":
    main()
