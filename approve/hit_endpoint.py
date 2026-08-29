import json
import shlex
import re
import requests
import datetime
import os
import sys

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

def show_session_expired_banner(module_curl_path="approve/curl.txt", completed_count=0, total_count=0):
    """Menampilkan banner instruksi yang jelas saat sesi expired agar pengguna tidak salah paham."""
    print("\n" + "=" * 65)
    print("⚠️  [SESI LOGIN KADALUARSA / EXPIRED] (HTTP 401/403)")
    print("=" * 65)
    print(" Sesi login FASIH BPS atau token cURL Anda telah habis masa berlakunya.")
    print(" BUKAN karena data tidak ada di server, melainkan akses ditolak.")
    print("\n Langkah mudah untuk melanjutkan:")
    print("  1. Buka browser dan login ulang ke https://fasih-sm.bps.go.id")
    print("  2. Buka tab Network (F12), lakukan interaksi/refresh halaman.")
    print(f"  3. Salin (Copy as cURL) request terbaru ke berkas: {module_curl_path}")
    print("  4. Jalankan ulang script (semua progress yang berhasil tersimpan otomatis).")
    if total_count > 0:
        print(f"\n Progress saat ini: {completed_count} dari {total_count} target selesai.")
    print("=" * 65 + "\n")

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
            val = tokens[i+1]
            if data is None or val.strip().startswith('{'):
                data = val
            method = 'POST'
            i += 2
        elif token in ('-X', '--request') and i + 1 < len(tokens):
            method = tokens[i+1].upper()
            i += 2
        elif token.startswith('http://') or token.startswith('https://'):
            url = token
            i += 1
        elif token.startswith("'http://") or token.startswith("'https://") or token.startswith('"http://') or token.startswith('"https://'):
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

    headers.pop('Host', None)
    headers.pop('Content-Length', None)

    return {
        'url': url,
        'headers': headers,
        'method': method,
        'data': data
    }

def split_curl_commands(content):
    """
    Memisahkan satu file yang berisi banyak perintah curl.
    """
    normalized = content.replace('\\\n', ' ').replace('\\\r\n', ' ')
    parts = re.split(r'\bcurl\s+', normalized, flags=re.IGNORECASE)
    commands = []
    for part in parts:
        part = part.strip()
        if part:
            commands.append('curl ' + part)
    return commands

def extract_survey_period_id(parsed_curl, raw_curl_content=""):
    """
    Mengekstrak surveyPeriodId dari payload JSON, query string, atau referer URL cURL.
    """
    if parsed_curl.get('data'):
        try:
            data_obj = json.loads(parsed_curl['data'])
            if isinstance(data_obj, dict):
                sp_id = data_obj.get('assignmentExtraParam', {}).get('surveyPeriodId')
                if sp_id:
                    return sp_id
                sp_id = data_obj.get('surveyPeriodId')
                if sp_id:
                    return sp_id
        except Exception:
            pass

    match = re.search(r'["\']surveyPeriodId["\']\s*:\s*["\']([a-f0-9\-]{36})["\']', raw_curl_content, re.IGNORECASE)
    if match:
        return match.group(1)

    match = re.search(r'/surveys/[a-f0-9\-]{36}/([a-f0-9\-]{36})', raw_curl_content, re.IGNORECASE)
    if match:
        return match.group(1)

    match = re.search(r'surveyPeriodId=([a-f0-9\-]{36})', raw_curl_content, re.IGNORECASE)
    if match:
        return match.group(1)

    return ""

def main():
    print("=" * 60)
    print("           BULK APPROVAL AUTOMATION SCRIPT")
    print("=" * 60)

    print("[*] Membaca perintah cURL dari curl.txt...")
    try:
        with open('curl.txt', 'r', encoding='utf-8') as f:
            curl_content = f.read().strip()
    except FileNotFoundError:
        print("[!] File curl.txt tidak ditemukan!")
        print("    Silakan buat file 'approve/curl.txt' dan tempel perintah cURL DataTables dari browser.")
        return

    commands = split_curl_commands(curl_content)
    parsed_curl = None
    for cmd in commands:
        parsed = parse_curl(cmd)
        if parsed.get('url') and ('datatable' in parsed['url'] or 'survey-periode' in parsed['url']):
            parsed_curl = parsed
            break
        if parsed.get('data') and ('"start"' in parsed['data'] or '"columns"' in parsed['data']):
            parsed_curl = parsed
            break

    if not parsed_curl and commands:
        parsed_curl = parse_curl(commands[0])

    if not parsed_curl or not parsed_curl.get('headers'):
        print("[!] Gagal mengekstrak headers dan cookies dari curl.txt.")
        return

    survey_period_id = extract_survey_period_id(parsed_curl, curl_content)
    if survey_period_id:
        print(f"[*] Terdeteksi surveyPeriodId: {survey_period_id}")

    # Cek pergantian kegiatan survei via config.json
    config_file = 'config.json'
    prev_period_id = None
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                cdata = json.load(f)
                prev_period_id = cdata.get('surveyPeriodId')
        except Exception:
            pass

    # Jika terjadi pergantian kegiatan survei, reset list ID lama
    if survey_period_id and prev_period_id and prev_period_id != survey_period_id:
        print(f"\n🔄 Terdeteksi pergantian kegiatan survei.")
        print(f"   - Periode Baru : {survey_period_id}")
        print(f"   - Periode Lama : {prev_period_id}")
        print("   Mereset cache list ID lama (ids.json)...")
        if os.path.exists('ids.json'):
            os.remove('ids.json')

    # Simpan surveyPeriodId aktif ke config.json
    if survey_period_id:
        try:
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump({'surveyPeriodId': survey_period_id}, f, indent=2)
        except Exception:
            pass

    headers_json = dict(parsed_curl['headers'])
    headers_json['Content-Type'] = 'application/json'
    headers_approval = {k: v for k, v in parsed_curl['headers'].items() if k.lower() != 'content-type'}

    datatable_url = parsed_curl.get('url')
    if not datatable_url or 'approval' in datatable_url:
        datatable_url = "https://fasih-sm.bps.go.id/app/api/analytic/api/v2/assignment/datatable-all-user-survey-periode"

    base_payload = None
    if parsed_curl.get('data'):
        try:
            base_payload = json.loads(parsed_curl['data'])
        except Exception:
            base_payload = None

    if not isinstance(base_payload, dict):
        base_payload = {
            "start": 0,
            "length": 100,
            "columns": [
                {"data": "id", "orderable": True},
                {"data": "codeIdentity", "orderable": True}
            ],
            "order": [],
            "search": {"value": "", "regex": False},
            "assignmentExtraParam": {"assignmentErrorStatusType": -1, "filterTargetType": "TARGET_ONLY"}
        }

    all_ids = []

    print("\n[?] Pilih sumber ID untuk diproses:")
    print("1. Ambil dari API DataTables (otomatis semua hasil dari curl)")
    print("2. Gunakan ID dari berkas ids.json (cache/sebelumnya)")
    print("3. Baca dari berkas id_spesifik.txt (satu ID per baris)")
    print("4. Masukkan ID secara manual via terminal")
    pilihan = input("Masukkan pilihan (1/2/3/4) [1]: ").strip()

    if pilihan == '2':
        if os.path.exists('ids.json'):
            try:
                with open('ids.json', 'r', encoding='utf-8') as f:
                    ids_data = json.load(f)
                    if isinstance(ids_data, list):
                        all_ids = [item['id'] for item in ids_data if isinstance(item, dict) and 'id' in item]
                print(f" -> Berhasil memuat {len(all_ids)} ID dari ids.json")
            except Exception as e:
                print(f"[!] Gagal membaca ids.json: {e}")
        else:
            print("[!] Berkas ids.json tidak ditemukan!")
            return
            
    elif pilihan == '3':
        if os.path.exists('id_spesifik.txt'):
            try:
                with open('id_spesifik.txt', 'r', encoding='utf-8') as f:
                    lines = f.read().splitlines()
                    all_ids = [line.strip() for line in lines if line.strip()]
                print(f" -> Berhasil memuat {len(all_ids)} ID dari id_spesifik.txt")
            except Exception as e:
                print(f"[!] Gagal membaca id_spesifik.txt: {e}")
        else:
            print("[!] Berkas id_spesifik.txt tidak ditemukan!")
            return
            
    elif pilihan == '4':
        ids_input = input("Masukkan ID (pisahkan dengan koma jika lebih dari satu):\n> ").strip()
        all_ids = [i.strip() for i in ids_input.split(',') if i.strip()]
        print(f" -> Memperoleh {len(all_ids)} ID dari input manual.")
        if not all_ids:
            print("[!] Tidak ada ID yang dimasukkan.")
            return

    else:
        print("\n[*] Menjalankan alur pengambilan data ID assignment dari API DataTables...")
        start = base_payload.get('start', 0)
        length = base_payload.get('length', 100)
        if length <= 0:
            length = 100

        all_ids = []
        page = 1

        while True:
            base_payload['start'] = start
            base_payload['length'] = length

            print(f" -> Mengambil halaman {page} (start: {start}, length: {length})...")

            try:
                response = requests.post(
                    datatable_url,
                    headers=headers_json,
                    json=base_payload,
                    timeout=30
                )
                if is_session_expired_response(response):
                    print(f"\n[!] Sesi login kadaluarsa saat mengambil data DataTables (HTTP {response.status_code}).")
                    show_session_expired_banner("approve/curl.txt")
                    return
                response.raise_for_status()
                res_json = response.json()
            except Exception as e:
                print(f"[!] Gagal menghubungi API DataTables pada indeks {start}: {e}")
                break

            records_filtered = res_json.get('recordsFiltered') or res_json.get('recordsTotal') or res_json.get('totalHit')
            if records_filtered is not None and start == 0:
                print(f" -> Total data di server: {records_filtered}")

            data_list = res_json.get('data') or res_json.get('searchData') or []
            if not data_list:
                print(" -> Halaman kosong / tidak ada data lagi.")
                break

            page_ids = []
            for item in data_list:
                if isinstance(item, dict) and 'id' in item:
                    page_ids.append(item['id'])
                elif isinstance(item, list) and len(item) > 0:
                    page_ids.append(item[0])

            all_ids.extend(page_ids)
            total_str = f" / {records_filtered}" if records_filtered is not None else ""
            print(f" -> Halaman {page}: Ditemukan {len(page_ids)} ID. Total terakumulasi: {len(all_ids)}{total_str} ID.")

            if len(data_list) < length:
                break

            if records_filtered is not None and len(all_ids) >= records_filtered:
                break

            start += length
            page += 1

        if all_ids:
            ids_to_save = [{"id": item_id} for item_id in all_ids]
            with open('ids.json', 'w', encoding='utf-8') as f:
                json.dump(ids_to_save, f, indent=2)
            print(f"\n[*] Berhasil menyimpan {len(all_ids)} ID ke berkas ids.json.")
        else:
            print("[!] Tidak ada ID yang ditemukan dari API DataTables.")
            return

    if not all_ids:
        print("[!] Tidak ada ID yang akan diproses untuk approval.")
        return

    print(f"\n[?] Siap melakukan approval massal untuk {len(all_ids)} assignment.")
    confirm = input(f"Apakah Anda yakin ingin menyetujui (approve) {len(all_ids)} assignment ini? (Y/n): ").strip().lower()
    if confirm == 'n':
        print("[*] Dibatalkan oleh pengguna.")
        return

    # Sesuai Endpoint user terbaru atau default (coba pakai yg dari curl user: /app/api/assignment-approval/api/v2/approval atau biarkan default sebelumnya)
    url_approval = "https://fasih-sm.bps.go.id/app/api/assignment-approval/api/v2/approval"
    timestamp_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_file = "execution.log"

    with open(log_file, "a", encoding="utf-8") as lf:
        lf.write(f"\n==================================================\n")
        lf.write(f"EKSEKUSI APPROVE: {timestamp_str}\n")
        lf.write(f"==================================================\n")

    print(f"\n[*] Memulai proses approval untuk {len(all_ids)} ID...\n")
    print("-" * 40)

    total_success = 0
    total_failed = 0
    failed_details = []

    for idx, assignment_id in enumerate(all_ids):
        log_msg = f"[{idx+1}/{len(all_ids)}] Memproses ID: {assignment_id}"
        print(log_msg)
        with open(log_file, "a", encoding="utf-8") as lf:
            lf.write(log_msg + "\n")

        # Approval endpoint requires Content-Type: application/json in the new curl format provided by user, 
        # but let's send it as multipart just in case, unless we want to change it to JSON. 
        # Wait, I will keep multipart for approve because it was written like that before, 
        # or change it to JSON based on user's new reject curl.
        # Let's use JSON payload for approve as well to be consistent.
        payload = {
            "assignmentId": assignment_id,
            "statusApproval": "true",
            "comment": "{\"dataKey\":\"\",\"notes\":[]}"
        }
        
        try:
            response = requests.post(url_approval, headers=headers_json, json=payload, timeout=15)
            # fallback ke cara lama jika error 415/400?
            if response.status_code not in (200, 201) and not is_session_expired_response(response):
                # coba pakai multipart/form-data
                multipart_data = {
                    'assignmentId': (None, assignment_id),
                    'statusApproval': (None, 'true'),
                    'comment': (None, '{"dataKey":"","notes":[]}')
                }
                response = requests.post(url_approval, headers=headers_approval, files=multipart_data, timeout=15)

            if is_session_expired_response(response):
                msg = f" -> [ERROR AUTH] Sesi login kadaluarsa saat approve ID {assignment_id} (HTTP {response.status_code})."
                print(msg)
                with open(log_file, "a", encoding="utf-8") as lf:
                    lf.write(msg + "\n")
                show_session_expired_banner(module_curl_path="approve/curl.txt", completed_count=total_success, total_count=len(all_ids))
                break

            if response.status_code in (200, 201):
                msg = f" -> [SUKSES] Status HTTP: {response.status_code}"
                print(msg)
                total_success += 1
            else:
                msg = f" -> [GAGAL] Status HTTP: {response.status_code}"
                print(msg)
                total_failed += 1
                failed_details.append({"id": assignment_id, "reason": f"Status HTTP {response.status_code}"})

            with open(log_file, "a", encoding="utf-8") as lf:
                lf.write(msg + "\n")

            try:
                parsed_response = response.json()
                resp_msg = f" -> Response Status: {parsed_response.get('message')} | Data: {parsed_response.get('data')}"
                print(resp_msg)
                with open(log_file, "a", encoding="utf-8") as lf:
                    lf.write(resp_msg + "\n")
            except Exception:
                resp_msg = f" -> Response: {response.text[:200]}"
                print(resp_msg)
                with open(log_file, "a", encoding="utf-8") as lf:
                    lf.write(resp_msg + "\n")

            print("-" * 40)

        except requests.exceptions.RequestException as e:
            msg = f" -> [ERROR] Request gagal: {e}"
            print(msg)
            with open(log_file, "a", encoding="utf-8") as lf:
                lf.write(msg + "\n")
            total_failed += 1
            failed_details.append({"id": assignment_id, "reason": f"RequestException: {e}"})
            print("-" * 40)

    summary_lines = []
    summary_lines.append("\n" + "=" * 50)
    summary_lines.append("           RINGKASAN AKHIR PENGEKSEKUSIAN")
    summary_lines.append("=" * 50)
    summary_lines.append(f" - Berhasil diproses : {total_success}")
    summary_lines.append(f" - Gagal diproses    : {total_failed}")
    summary_lines.append(f" - Total target      : {len(all_ids)}")
    summary_lines.append("=" * 50)

    if failed_details:
        summary_lines.append("DETAIL KEGAGALAN:")
        for fd in failed_details:
            summary_lines.append(f" - ID: {fd['id']} (Alasan: {fd['reason']})")
        summary_lines.append("=" * 50)

    summary_text = "\n".join(summary_lines)
    print(summary_text)
    with open(log_file, "a", encoding="utf-8") as lf:
        lf.write(summary_text + "\n")

if __name__ == "__main__":
    main()
