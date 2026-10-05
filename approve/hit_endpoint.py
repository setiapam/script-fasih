import json
import shlex
import re
import requests
import datetime
import os
import sys
import copy
import time
import urllib3

urllib3.disable_warnings()

BASE_REGION_URL = "https://fasih-sm.bps.go.id/app/api/region/api/v1/region"
SSO_EKSTERNAL_AUTH = "https://fasih-sm.bps.go.id/oauth2/authorization/eksternal"
SSO_BPS_AUTH = "https://fasih-sm.bps.go.id/app/auth/login"

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
    """Memisahkan satu file yang berisi banyak perintah curl."""
    normalized = content.replace('\\\n', ' ').replace('\\\r\n', ' ')
    parts = re.split(r'\bcurl\s+', normalized, flags=re.IGNORECASE)
    commands = []
    for part in parts:
        part = part.strip()
        if part:
            commands.append('curl ' + part)
    return commands

def extract_survey_period_id(parsed_curl, raw_curl_content=""):
    """Mengekstrak surveyPeriodId dari payload JSON, query string, atau referer URL cURL."""
    if parsed_curl.get('data'):
        try:
            data_obj = json.loads(parsed_curl['data'])
            if isinstance(data_obj, dict):
                sp_id = data_obj.get('assignmentExtraParam', {}).get('surveyPeriodId')
                if sp_id: return sp_id
                sp_id = data_obj.get('surveyPeriodId')
                if sp_id: return sp_id
        except Exception:
            pass

    match = re.search(r'["\']surveyPeriodId["\']\s*:\s*["\']([a-f0-9\-]{36})["\']', raw_curl_content, re.IGNORECASE)
    if match: return match.group(1)
    match = re.search(r'/surveys/[a-f0-9\-]{36}/([a-f0-9\-]{36})', raw_curl_content, re.IGNORECASE)
    if match: return match.group(1)
    match = re.search(r'surveyPeriodId=([a-f0-9\-]{36})', raw_curl_content, re.IGNORECASE)
    if match: return match.group(1)
    return ""

def login_keycloak_with_totp(username, password, login_type="eksternal", totp_secret=None, session=None):
    """
    Melakukan login otomatis ke Keycloak FASIH (SSO Eksternal atau SSO BPS) dengan dukungan TOTP 2FA.
    totp_secret: seed string base32 / otpauth URI. Jika None dan akun butuh OTP, akan meminta input di terminal.
    """
    if session is None:
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36"
        })

    auth_url = SSO_EKSTERNAL_AUTH if str(login_type).lower() == "eksternal" else SSO_BPS_AUTH
    print(f"[*] Menghubungi endpoint autentikasi ({login_type})...")
    
    r1 = session.get(auth_url, verify=False, timeout=20)
    m = re.search(r'<form[^>]*action="([^"]+)"', r1.text)
    if not m:
        raise RuntimeError(f"Gagal menemukan form login Keycloak pada {auth_url}. Status: {r1.status_code}")
    action_url = m.group(1).replace("&amp;", "&")

    print(f"[*] Mengirim kredensial username/password ({username})...")
    r2 = session.post(action_url, data={"username": username, "password": password, "credentialId": ""},
                      verify=False, timeout=20, allow_redirects=False)

    if r2.status_code == 200:
        inputs = re.findall(r'<input[^>]*name="([^"]+)"', r2.text)
        if "otp" in inputs:
            print("[*] Akun memerlukan verifikasi Two-Factor Authentication (TOTP / OTP)...")
            otp_code = None
            if totp_secret:
                try:
                    import pyotp
                    totp_obj = pyotp.parse_uri(totp_secret) if "otpauth://" in totp_secret else pyotp.TOTP(totp_secret)
                    otp_code = totp_obj.now()
                    print("[+] Kode TOTP berhasil di-generate otomatis via Secret Key.")
                except Exception as e:
                    print(f"[!] Gagal generate TOTP otomatis: {e}")
            
            if not otp_code:
                otp_code = input("\n[?] Masukkan 6 digit kode OTP dari aplikasi Authenticator di HP Anda: ").strip()

            m_otp = re.search(r'<form[^>]*action="([^"]+)"', r2.text)
            if not m_otp:
                raise RuntimeError("Gagal menemukan form action OTP.")
            otp_url = m_otp.group(1).replace("&amp;", "&")

            r_otp = session.post(otp_url, data={"otp": otp_code}, verify=False, timeout=20, allow_redirects=False)
            if r_otp.status_code != 302:
                err_otp = "Kode OTP tidak valid atau ditolak oleh server."
                m_err = re.search(r'<span[^>]*class="[^"]*kc-feedback-text[^"]*"[^>]*>(.*?)</span>', r_otp.text, re.DOTALL)
                if m_err:
                    err_otp = re.sub(r'<[^>]+>', '', m_err.group(1)).strip()
                raise RuntimeError(f"Submit OTP gagal: {err_otp} (Status HTTP {r_otp.status_code})")
            redirect_url = r_otp.headers.get("Location")
        else:
            err_msg = "Username atau password salah (Invalid username or password)."
            m_err = re.search(r'<span[^>]*class="[^"]*kc-feedback-text[^"]*"[^>]*>(.*?)</span>', r2.text, re.DOTALL)
            if m_err:
                err_msg = re.sub(r'<[^>]+>', '', m_err.group(1)).strip()
            raise RuntimeError(f"Login Keycloak ditolak: {err_msg}")
    elif r2.status_code == 302:
        redirect_url = r2.headers.get("Location")
    else:
        raise RuntimeError(f"Status respons login tak terduga: {r2.status_code}")

    if not redirect_url:
        raise RuntimeError("Callback redirect URL tidak ditemukan.")

    session.get(redirect_url, verify=False, timeout=20, allow_redirects=True)
    cookies = session.cookies.get_dict()
    if not cookies.get("SESSION"):
        raise RuntimeError("Gagal memperoleh cookie SESSION setelah callback autentikasi.")
    
    print("[+] Login berhasil! Cookie sesi siap digunakan.")
    return session

def resolve_group_id(headers, survey_period_id, datatable_url):
    """Mendeteksi groupId wilayah secara otomatis dari datatable atau file region."""
    for path in ['config.json', '../tarik-data/config.json']:
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    c = json.load(f)
                    if c.get('groupId'): return c['groupId']
            except Exception:
                pass

    for rpath in ['curl_region.txt', '../tarik-data/curl_region.txt']:
        if os.path.exists(rpath):
            try:
                with open(rpath, 'r', encoding='utf-8') as f:
                    m = re.search(r'groupId=([a-f0-9\-]{36})', f.read())
                    if m: return m.group(1)
            except Exception:
                pass

    payload = {
        "start": 0, "length": 1,
        "columns": [{"data": "id", "orderable": True}],
        "order": [], "search": {"value": "", "regex": False},
        "assignmentExtraParam": {
            "surveyPeriodId": survey_period_id,
            "assignmentErrorStatusType": -1,
            "filterTargetType": "TARGET_ONLY"
        }
    }
    try:
        r = requests.post(datatable_url, headers=headers, json=payload, verify=False, timeout=15)
        if r.status_code == 200:
            items = r.json().get("searchData") or r.json().get("data") or []
            if items:
                first = items[0]
                meta = first.get("regionMetadata")
                if isinstance(meta, dict) and meta.get("id"): return meta["id"]
                reg = first.get("region")
                if isinstance(reg, dict) and reg.get("groupId"): return reg["groupId"]
    except Exception:
        pass

    return "a45adac1-e711-4c15-b3f9-1f30fc151565"

def extract_submitted_ids_from_items(data_list):
    """Hanya mengekstrak ID penugasan yang berstatus SUBMITTED (menunggu approval)."""
    valid_ids = []
    for item in data_list:
        if not isinstance(item, dict):
            continue
        item_id = item.get('id')
        if not item_id:
            continue

        status_alias = str(item.get('assignmentStatusAlias') or item.get('status') or '').strip().upper()
        status_id = item.get('assignmentStatusId')
        
        is_submitted = False
        if 'SUBMIT' in status_alias and 'APPROV' not in status_alias and 'REJECT' not in status_alias:
            is_submitted = True
        elif status_id in (2, 3):
            is_submitted = True
        elif not status_alias and status_id is None:
            is_submitted = True

        if is_submitted:
            valid_ids.append({
                "id": item_id,
                "nama": item.get("data1", "-")
            })

    return valid_ids

def main():
    print("=" * 60)
    print("           BULK APPROVAL AUTOMATION SCRIPT")
    print("  (Cross-Account Auto-Fetch + Multi-Factor TOTP Support)")
    print("=" * 60)

    # 1. Siapkan Sesi Pengawas (Eksekutor Approval)
    session_approver = None
    headers_approver = None
    survey_period_id = None
    datatable_url = "https://fasih-sm.bps.go.id/app/api/analytic/api/v2/assignment/datatable-all-user-survey-periode"

    cred_file = "credentials.json"
    approver_creds = {}
    if os.path.exists(cred_file):
        try:
            with open(cred_file, 'r', encoding='utf-8') as cf:
                approver_creds = json.load(cf).get("approver_account", {})
        except Exception:
            pass

    # Jika approver_account diisi di credentials.json, gunakan login otomatis
    if approver_creds.get("username") and approver_creds.get("password"):
        print(f"[*] Menemukan konfigurasi akun Pengawas di {cred_file}: {approver_creds['username']}")
        try:
            session_approver = login_keycloak_with_totp(
                username=approver_creds["username"],
                password=approver_creds["password"],
                login_type=approver_creds.get("login_type", "sso_bps"),
                totp_secret=approver_creds.get("totp_secret")
            )
            headers_approver = {
                "X-XSRF-TOKEN": session_approver.cookies.get("XSRF-TOKEN", ""),
                "Content-Type": "application/json"
            }
        except Exception as e:
            print(f"[!] Gagal login otomatis akun Pengawas: {e}")
            print("[*] Beralih ke metode pembacaan berkas approve/curl.txt...")

    # Fallback / Model sebelumnya: Membaca approve/curl.txt
    if not headers_approver:
        print("[*] Membaca sesi pengawas dari approve/curl.txt...")
        try:
            with open('curl.txt', 'r', encoding='utf-8') as f:
                curl_content = f.read().strip()
        except FileNotFoundError:
            print("[!] File curl.txt maupun approver_account di credentials.json tidak ditemukan!")
            print("    Silakan buat file 'approve/curl.txt' atau lengkapi 'approver_account' di credentials.json.")
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
        headers_approver = dict(parsed_curl['headers'])
        headers_approver['Content-Type'] = 'application/json'
        if parsed_curl.get('url') and 'approval' not in parsed_curl['url']:
            datatable_url = parsed_curl['url']

    if not survey_period_id:
        if os.path.exists('config.json'):
            try:
                with open('config.json', 'r', encoding='utf-8') as f:
                    survey_period_id = json.load(f).get('surveyPeriodId')
            except Exception:
                pass
        if not survey_period_id:
            sp_input = input("[?] Masukkan surveyPeriodId kegiatan (contoh: fd68e454-ba45-4b85-8205-f3bf777ded24): ").strip()
            if sp_input:
                survey_period_id = sp_input

    if survey_period_id:
        print(f"[*] Terdeteksi surveyPeriodId: {survey_period_id}")

    config_file = 'config.json'
    prev_period_id = None
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                cdata = json.load(f)
                prev_period_id = cdata.get('surveyPeriodId')
        except Exception:
            pass

    if survey_period_id and prev_period_id and prev_period_id != survey_period_id:
        print(f"\n🔄 Terdeteksi pergantian kegiatan survei ({prev_period_id} -> {survey_period_id}).")
        if os.path.exists('ids.json'):
            os.remove('ids.json')

    if survey_period_id:
        try:
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump({'surveyPeriodId': survey_period_id}, f, indent=2)
        except Exception:
            pass

    base_payload = None
    if parsed_curl and parsed_curl.get('data'):
        try:
            base_payload = json.loads(parsed_curl['data'])
        except Exception:
            base_payload = None

    if not isinstance(base_payload, dict):
        base_payload = {
            "start": 0, "length": 100,
            "columns": [{"data": "id", "orderable": True}, {"data": "codeIdentity", "orderable": True}],
            "order": [], "search": {"value": "", "regex": False},
            "assignmentExtraParam": {"assignmentErrorStatusType": -1, "filterTargetType": "TARGET_ONLY"}
        }

    if 'assignmentExtraParam' not in base_payload:
        base_payload['assignmentExtraParam'] = {}
    base_payload['assignmentExtraParam']['assignmentStatusAlias'] = "SUBMITTED BY PPL"
    if survey_period_id and not base_payload['assignmentExtraParam'].get('surveyPeriodId'):
        base_payload['assignmentExtraParam']['surveyPeriodId'] = survey_period_id

    # Menu Opsi
    print("\n[?] Pilih metode penarikan target ID:")
    print("1. [FITUR OTOMATIS] Auto-Fetch 1 Kelurahan via Akun Admin/Dummy (Tarik seluruh Sub-SLS)")
    print("2. Ambil dari API DataTables (sesuai filter browser curl.txt saat ini)")
    print("3. Gunakan ID dari berkas ids.json (cache sebelumnya)")
    print("4. Baca dari berkas id_spesifik.txt (satu ID per baris)")
    print("5. Masukkan ID secara manual via terminal")
    pilihan = input("Masukkan pilihan (1/2/3/4/5) [1]: ").strip() or "1"

    all_targets = []

    if pilihan == '1':
        # ==============================================================
        # OPSI 1: CROSS-ACCOUNT AUTO-FETCH (AKUN ADMIN/DUMMY + TOTP)
        # ==============================================================
        print("\n" + "=" * 60)
        print(" MODE OTOMATIS: AUTO-FETCH KELURAHAN DENGAN AKUN ADMIN/DUMMY")
        print("=" * 60)

        cred_file = "credentials.json"
        username_admin = ""
        password_admin = ""
        login_type = "eksternal"
        totp_secret = ""

        if os.path.exists(cred_file):
            try:
                with open(cred_file, 'r', encoding='utf-8') as cf:
                    cdata = json.load(cf).get("admin_account", {})
                    username_admin = cdata.get("username", "")
                    password_admin = cdata.get("password", "")
                    login_type = cdata.get("login_type", "eksternal")
                    totp_secret = cdata.get("totp_secret", "")
            except Exception as e:
                print(f"[!] Gagal membaca credentials.json: {e}")

        if not username_admin:
            print("[*] Konfigurasi credentials.json belum ada atau kosong.")
            username_admin = input("Masukkan username akun Admin/Dummy (contoh: 3175.xxx@dummy.sobat.id): ").strip()
            import getpass
            password_admin = getpass.getpass("Masukkan password akun Admin/Dummy: ").strip()
            ltype_in = input("Tipe login (eksternal / sso_bps) [eksternal]: ").strip().lower()
            if ltype_in in ("sso_bps", "bps"):
                login_type = "sso_bps"
            totp_secret = input("TOTP Secret Key base32 (kosongkan jika akun tidak pakai OTP atau ingin input manual): ").strip()

        print(f"\n[*] Menghubungkan sesi akun Admin/Dummy ({username_admin})...")
        try:
            session_admin = login_keycloak_with_totp(
                username=username_admin,
                password=password_admin,
                login_type=login_type,
                totp_secret=totp_secret
            )
        except Exception as e:
            print(f"\n❌ Gagal login akun Admin/Dummy: {e}")
            return

        headers_admin = {
            "X-XSRF-TOKEN": session_admin.cookies.get("XSRF-TOKEN", ""),
            "Content-Type": "application/json"
        }

        rdb_path = "region_db.json"
        if not os.path.exists(rdb_path) and os.path.exists("../tarik-data/region_db.json"):
            rdb_path = "../tarik-data/region_db.json"

        rdb = {}
        if os.path.exists(rdb_path):
            with open(rdb_path, 'r', encoding='utf-8') as rf:
                rdb = json.load(rf)

        parent_kel_code = input("\nMasukkan 10 digit Kode Kelurahan target (contoh: 3175040006 untuk Koja): ").strip()
        if not parent_kel_code or len(parent_kel_code) < 10:
            print("[!] Kode kelurahan wajib 10 digit!")
            return

        prov_code = parent_kel_code[:2]
        kab_code = parent_kel_code[:4]
        kec_code = parent_kel_code[:7]
        kel_code = parent_kel_code[:10]

        reg1 = rdb.get(prov_code, {}).get("id")
        reg2 = rdb.get(kab_code, {}).get("id")
        reg3 = rdb.get(kec_code, {}).get("id")
        reg4 = rdb.get(kel_code, {}).get("id")

        print(f"[*] Melakukan pemindaian seluruh sampel SUBMITTED di Kelurahan {parent_kel_code}...")

        start = 0
        length = 100
        page = 1

        while True:
            fetch_payload = {
                "start": start,
                "length": length,
                "columns": [],
                "order": [],
                "search": {"value": "", "regex": False},
                "assignmentExtraParam": {
                    "surveyPeriodId": survey_period_id,
                    "region1Id": reg1,
                    "region2Id": reg2,
                    "region3Id": reg3,
                    "region4Id": reg4,
                    "assignmentErrorStatusType": -1,
                    "filterTargetType": "TARGET_ONLY"
                }
            }
            try:
                rf = session_admin.post(datatable_url, headers=headers_admin, json=fetch_payload, verify=False, timeout=25)
                if rf.status_code != 200:
                    print(f"   [!] Gagal memuat data datatable: HTTP {rf.status_code}")
                    break
                res_data = rf.json()
                items = res_data.get("data") or res_data.get("searchData") or []
                if not items:
                    break

                submitted_items = extract_submitted_ids_from_items(items)
                all_targets.extend(submitted_items)

                print(f"\r    Paginasi {page} (start {start}) | Ditemukan: {len(all_targets)} SUBMITTED terakumulasi", end="", flush=True)

                if len(items) < length:
                    break
                start += length
                page += 1
                time.sleep(0.04)
            except Exception as e:
                print(f"\n   [!] Gangguan koneksi saat fetch: {e}")
                break

        print(f"\n\n[+] Selesai! Berhasil mengumpulkan {len(all_targets)} dokumen SUBMITTED dari Kelurahan {parent_kel_code}.")

    elif pilihan == '2':
        print("\n[*] Menjalankan penarikan data ID assignment dari API DataTables (curl.txt)...")
        start = base_payload.get('start', 0)
        length = base_payload.get('length', 100) or 100
        page = 1

        while True:
            base_payload['start'] = start
            base_payload['length'] = length
            try:
                response = requests.post(datatable_url, headers=headers_approver, json=base_payload, verify=False, timeout=30)
                if is_session_expired_response(response):
                    show_session_expired_banner("approve/curl.txt")
                    return
                response.raise_for_status()
                res_json = response.json()
            except Exception as e:
                print(f"[!] Gagal menghubungi API DataTables: {e}")
                break

            items = res_json.get('data') or res_json.get('searchData') or []
            if not items: break

            submitted_items = extract_submitted_ids_from_items(items)
            all_targets.extend(submitted_items)

            print(f" -> Halaman {page}: Ditemukan {len(submitted_items)} SUBMITTED. Total: {len(all_targets)} ID.")

            if len(items) < length: break
            start += length
            page += 1

    elif pilihan == '3':
        if os.path.exists('ids.json'):
            try:
                with open('ids.json', 'r', encoding='utf-8') as f:
                    for it in json.load(f):
                        all_targets.append({"id": it["id"], "nama": it.get("nama", "-")})
                print(f" -> Berhasil memuat {len(all_targets)} ID dari ids.json")
            except Exception as e:
                print(f"[!] Gagal membaca ids.json: {e}")
                return
        else:
            print("[!] Berkas ids.json tidak ditemukan!")
            return

    elif pilihan == '4':
        if os.path.exists('id_spesifik.txt'):
            try:
                with open('id_spesifik.txt', 'r', encoding='utf-8') as f:
                    for line in f.read().splitlines():
                        if line.strip():
                            all_targets.append({"id": line.strip(), "nama": "-"})
                print(f" -> Berhasil memuat {len(all_targets)} ID dari id_spesifik.txt")
            except Exception as e:
                print(f"[!] Gagal membaca id_spesifik.txt: {e}")
                return
        else:
            print("[!] Berkas id_spesifik.txt tidak ditemukan!")
            return

    elif pilihan == '5':
        ids_input = input("Masukkan ID (pisahkan dengan koma jika > 1):\n> ").strip()
        for it in ids_input.split(','):
            if it.strip():
                all_targets.append({"id": it.strip(), "nama": "-"})

    if not all_targets:
        print("\n[!] Tidak ada target penugasan berstatus SUBMITTED yang perlu diapprove.")
        return

    # Deduplikasi ID
    seen_ids = set()
    unique_targets = []
    for t in all_targets:
        if t["id"] not in seen_ids:
            seen_ids.add(t["id"])
            unique_targets.append(t)

    with open('ids.json', 'w', encoding='utf-8') as f:
        json.dump(unique_targets, f, indent=2)

    print(f"\n[?] Siap melakukan approval massal untuk {len(unique_targets)} assignment (STATUS: SUBMITTED ONLY).")
    confirm = input(f"Apakah Anda yakin ingin menyetujui (approve) {len(unique_targets)} assignment ini via akun Pengawas? (Y/n): ").strip().lower()
    if confirm == 'n':
        print("[*] Dibatalkan oleh pengguna.")
        return

    url_approval = "https://fasih-sm.bps.go.id/app/api/assignment-approval/api/v2/approval"
    timestamp_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_file = "execution.log"

    with open(log_file, "a", encoding="utf-8") as lf:
        lf.write(f"\n==================================================\n")
        lf.write(f"EKSEKUSI APPROVE (SUBMITTED ONLY): {timestamp_str}\n")
        lf.write(f"Total Target: {len(unique_targets)}\n")
        lf.write(f"==================================================\n")

    print(f"\n[*] Memulai proses approval untuk {len(unique_targets)} ID...\n")
    print("-" * 40)

    total_success = 0
    total_failed = 0
    failed_details = []

    for idx, target in enumerate(unique_targets):
        assignment_id = target["id"]
        nama = target["nama"]

        payload = {
            "assignmentId": assignment_id,
            "statusApproval": "true",
            "comment": "{\"dataKey\":\"\",\"notes\":[]}"
        }

        try:
            response = requests.post(url_approval, headers=headers_approver, json=payload, verify=False, timeout=15)
            
            if is_session_expired_response(response):
                msg = f" -> [ERROR AUTH] Sesi login pengawas kadaluarsa saat approve ID {assignment_id}."
                print(msg)
                with open(log_file, "a", encoding="utf-8") as lf: lf.write(msg + "\n")
                show_session_expired_banner("approve/curl.txt", completed_count=total_success, total_count=len(unique_targets))
                break

            if response.status_code in (200, 201) and response.json().get("success"):
                msg = f"[{idx+1}/{len(unique_targets)}] [SUKSES] ID: {assignment_id} | {nama}"
                print(msg)
                total_success += 1
            else:
                resp_text = response.text[:120]
                msg = f"[{idx+1}/{len(unique_targets)}] [GAGAL] ID: {assignment_id} | {nama} -> {resp_text}"
                print(msg)
                total_failed += 1
                failed_details.append({"id": assignment_id, "reason": resp_text})

            with open(log_file, "a", encoding="utf-8") as lf:
                lf.write(msg + "\n")

            time.sleep(0.08)

        except requests.exceptions.RequestException as e:
            msg = f"[{idx+1}/{len(unique_targets)}] [ERROR] Request gagal: {e}"
            print(msg)
            with open(log_file, "a", encoding="utf-8") as lf: lf.write(msg + "\n")
            total_failed += 1
            failed_details.append({"id": assignment_id, "reason": str(e)})

    summary_lines = []
    summary_lines.append("\n" + "=" * 50)
    summary_lines.append("           RINGKASAN AKHIR PENGEKSEKUSIAN")
    summary_lines.append("=" * 50)
    summary_lines.append(f" - Berhasil di-approve : {total_success}")
    summary_lines.append(f" - Gagal di-approve    : {total_failed}")
    summary_lines.append(f" - Total target        : {len(unique_targets)}")
    summary_lines.append("=" * 50)

    summary_text = "\n".join(summary_lines)
    print(summary_text)
    with open(log_file, "a", encoding="utf-8") as lf:
        lf.write(summary_text + "\n")

if __name__ == "__main__":
    main()
