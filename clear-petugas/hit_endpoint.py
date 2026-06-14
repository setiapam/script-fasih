import json
import shlex
import re
import requests
from urllib.parse import urlparse, parse_qs

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

    # Hapus Host dan Content-Length bawaan cURL agar requests bisa merakit sendiri dengan benar
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

def load_emails(filename):
    """
    Membaca list email unik dari file teks, mengabaikan baris kosong.
    """
    emails = []
    seen = set()
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            for line in f:
                email = line.strip()
                if email and '@' in email:
                    email_lower = email.lower()
                    if email_lower not in seen:
                        seen.add(email_lower)
                        emails.append(email)
    except FileNotFoundError:
        print(f"[!] Warning: File {filename} tidak ditemukan.")
    return emails

def alternate_emails(petugas_emails, pengawas_emails):
    """
    Menggabungkan dua list email secara bergantian (interleave).
    """
    i = 0
    j = 0
    alternated = []
    while i < len(petugas_emails) or j < len(pengawas_emails):
        if i < len(petugas_emails):
            alternated.append(('petugas', petugas_emails[i]))
            i += 1
        if j < len(pengawas_emails):
            alternated.append(('pengawas', pengawas_emails[j]))
            j += 1
    return alternated

def main():
    print("=" * 60)
    print("           CLEAR ASSIGNMENT AUTOMATION SCRIPT")
    print("=" * 60)
    
    # Nilai default survey ID dari user prompt
    survey_period_id = "fd68e454-ba45-4b85-8205-f3bf777ded24"
    survey_role_petugas = "6d7d919a-45e5-4779-bb87-2905b49fd31a"
    survey_role_pengawas = "93bcf446-c4c1-4462-8ed0-4b0f7ae89e52"
    
    headers = {}
    has_curl = False
    
    # 1. Coba baca cURL dari curl.txt untuk mendapatkan headers/cookies dan parameter survey
    try:
        with open('curl.txt', 'r', encoding='utf-8') as f:
            curl_content = f.read().strip()
        commands = split_curl_commands(curl_content)
        if commands:
            parsed = parse_curl(commands[0])
            headers = parsed.get('headers', {})
            has_curl = True
            print("[*] Berhasil mengekstrak headers/cookies dari curl.txt.")
            
            # Cari surveyPeriodId dan surveyRoleId dari URL
            for cmd in commands:
                parsed_cmd = parse_curl(cmd)
                url = parsed_cmd.get('url')
                if url:
                    parsed_url = urlparse(url)
                    qs = parse_qs(parsed_url.query)
                    if 'surveyPeriodId' in qs:
                        survey_period_id = qs['surveyPeriodId'][0]
                    if 'surveyRoleId' in qs:
                        role_id = qs['surveyRoleId'][0]
                        # Identifikasi role berdasarkan context atau value
                        if 'petugas' in url.lower() or role_id == survey_role_petugas:
                            survey_role_petugas = role_id
                        elif 'pengawas' in url.lower() or role_id == survey_role_pengawas:
                            survey_role_pengawas = role_id
    except FileNotFoundError:
        print("[!] File curl.txt tidak ditemukan.")

    # Jika tidak ada curl.txt, coba fallback ke curl_get.txt
    if not has_curl:
        try:
            with open('curl_get.txt', 'r', encoding='utf-8') as f:
                parsed = parse_curl(f.read())
                headers = parsed.get('headers', {})
                has_curl = True
                print("[*] Berhasil mengekstrak headers/cookies dari curl_get.txt.")
        except FileNotFoundError:
            pass

    print(f"[*] Parameter Aktif:")
    print(f"    - surveyPeriodId : {survey_period_id}")
    print(f"    - Role Petugas   : {survey_role_petugas}")
    print(f"    - Role Pengawas  : {survey_role_pengawas}")

    all_targets = []
    perform_search = False
    
    # Cek apakah kita bisa melakukan pencarian baru
    if has_curl:
        petugas_emails = load_emails('petugas.txt')
        pengawas_emails = load_emails('pengawas.txt')
        if petugas_emails or pengawas_emails:
            perform_search = True
        else:
            print("[!] File petugas.txt atau pengawas.txt kosong/tidak ditemukan.")
    else:
        print("[!] Tidak ada cURL/autentikasi aktif untuk pencarian API.")

    if perform_search:
        print(f"\n[*] Memulai pencarian alokasi berdasarkan email...")
        print(f" -> Petugas: {len(petugas_emails)} email")
        print(f" -> Pengawas: {len(pengawas_emails)} email")
        
        alternated = alternate_emails(petugas_emails, pengawas_emails)
        print(f" -> Total email bergantian: {len(alternated)} alamat")
        
        for idx, (role_type, email) in enumerate(alternated):
            role_id = survey_role_petugas if role_type == 'petugas' else survey_role_pengawas
            print(f"\n[{idx+1}/{len(alternated)}] Mencari {role_type}: {email} ...")
            
            # Step 1: Cari user berdasarkan email
            search_url = "https://fasih-sm.bps.go.id/app/api/survey-user/api/v1/allocations-view/by-user"
            params = {
                'surveyRoleId': role_id,
                'surveyPeriodId': survey_period_id,
                'page': 0,
                'size': 10,
                'keyword': email
            }
            
            try:
                resp = requests.get(search_url, headers=headers, params=params, timeout=15)
                resp.raise_for_status()
                content = resp.json().get('data', {}).get('content', [])
                
                if not content:
                    print("    [-] Tidak ada data user ditemukan.")
                    continue
                    
                for user in content:
                    user_id = user.get('userId')
                    username = user.get('username')
                    total_regions = user.get('totalRegions', 0)
                    print(f"    [+] Ditemukan user {username} (ID: {user_id}), total region: {total_regions}")
                    
                    # Step 2: Ambil alokasi region untuk user tersebut (mendukung paginasi)
                    page = 0
                    size = 50
                    user_regions = []
                    while True:
                        region_url = f"https://fasih-sm.bps.go.id/app/api/survey-user/api/v1/allocations-view/by-user/allocated-region/{user_id}"
                        region_params = {
                            'surveyPeriodId': survey_period_id,
                            'page': page,
                            'size': size
                        }
                        reg_resp = requests.get(region_url, headers=headers, params=region_params, timeout=15)
                        reg_resp.raise_for_status()
                        
                        reg_data = reg_resp.json().get('data', {})
                        reg_content = reg_data.get('content', [])
                        user_regions.extend(reg_content)
                        
                        total_pages = reg_data.get('totalPages', 1)
                        page_number = reg_data.get('pageNumber', 0)
                        
                        if page_number >= total_pages - 1 or not reg_content:
                            break
                        page += 1
                        
                    print(f"        [+] Berhasil memuat {len(user_regions)} region teralokasi.")
                    for reg in user_regions:
                        if reg.get('allocationId') and reg.get('regionCode'):
                            all_targets.append({
                                'email': email,
                                'role': role_type,
                                'userId': user_id,
                                'allocationId': reg.get('allocationId'),
                                'regionCode': reg.get('regionCode'),
                                'regionName': reg.get('regionName')
                            })
            except Exception as e:
                print(f"    [!] Error saat memproses email {email}: {e}")
                
        # Simpan hasil pencarian ke ids.json
        if all_targets:
            try:
                with open('ids.json', 'w', encoding='utf-8') as f:
                    json.dump(all_targets, f, indent=2)
                print(f"\n[*] Berhasil menyimpan {len(all_targets)} target ke ids.json.")
            except Exception as e:
                print(f"[!] Gagal menulis ids.json: {e}")
        else:
            print("\n[-] Tidak ditemukan alokasi region untuk semua email.")
            
    else:
        # Fallback: Baca data target langsung dari ids.json
        print("\n[*] Mencoba membaca data target dari ids.json...")
        try:
            with open('ids.json', 'r', encoding='utf-8') as f:
                all_targets = json.load(f)
            print(f" -> Berhasil memuat {len(all_targets)} target dari ids.json.")
        except FileNotFoundError:
            print("[!] File ids.json tidak ditemukan. Silakan lakukan pencarian baru.")
            return
        except Exception as e:
            print(f"[!] Gagal memuat ids.json: {e}")
            return

    if not all_targets:
        print("[!] Tidak ada alokasi target yang akan diproses.")
        return

    # Tampilkan Ringkasan Target
    stats = {}
    for t in all_targets:
        key = f"{t.get('email')} ({t.get('role')})"
        stats[key] = stats.get(key, 0) + 1
        
    print("\n" + "=" * 50)
    print("            RINGKASAN TARGET HAPUS")
    print("=" * 50)
    for email_role, count in stats.items():
        print(f" - {email_role:<40}: {count} alokasi")
    print("-" * 50)
    print(f"TOTAL TARGET: {len(all_targets)} alokasi.")
    print("=" * 50)

    # Konfirmasi sebelum delete
    confirm = input(f"\nApakah Anda yakin ingin menghapus {len(all_targets)} assignment ini? (y/N): ").strip().lower()
    if confirm != 'y':
        print("[*] Dibatalkan oleh pengguna.")
        return

    # Step 3: Hapus assignment (DELETE request)
    total_deleted = 0
    total_failed = 0
    
    print("\n[*] Memulai proses penghapusan...")
    for idx, target in enumerate(all_targets):
        alloc_id = target.get('allocationId')
        reg_code = target.get('regionCode')
        email = target.get('email')
        reg_name = target.get('regionName', '-')
        
        print(f"[{idx+1}/{len(all_targets)}] Menghapus {email} | Region: {reg_name} ({reg_code}) ... ", end="")
        
        delete_url = f"https://fasih-sm.bps.go.id/app/api/survey-user/api/v1/allocation/{alloc_id}/{reg_code}"
        params = {
            'surveyPeriodId': survey_period_id
        }
        
        try:
            response = requests.delete(delete_url, headers=headers, params=params, timeout=15)
            if response.status_code in (200, 201, 204):
                print(f"[SUKSES] (Status: {response.status_code})")
                total_deleted += 1
            else:
                print(f"[GAGAL] (Status: {response.status_code})")
                total_failed += 1
        except Exception as e:
            print(f"[ERROR] ({e})")
            total_failed += 1


    print("\n" + "=" * 50)
    print("           RINGKASAN AKHIR PENGEKSEKUSIAN")
    print("=" * 50)
    print(f" - Berhasil diproses : {total_deleted}")
    print(f" - Gagal diproses    : {total_failed}")
    print(f" - Total target      : {len(all_targets)}")
    print("=" * 50)

if __name__ == "__main__":
    main()
