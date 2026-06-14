import json
import shlex
import re
import requests

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

def detect_curl_type(parsed_curl):
    """
    Mendeteksi apakah cURL tersebut untuk mengambil data (GET/Datatable) atau menghapus (CLEAR).
    """
    url = parsed_curl.get('url', '') or ''
    if 'datatable' in url or 'survey-periode' in url:
        return 'get'
    if 'clear-assignment' in url:
        return 'clear'
        
    # Fallback/default berdasarkan payload
    data = parsed_curl.get('data', '') or ''
    if data:
        if '"start"' in data or '"columns"' in data:
            return 'get'
        if data.strip().startswith('['):
            return 'clear'
    return None

def main():
    print("=" * 60)
    print("           CLEAR ASSIGNMENT AUTOMATION SCRIPT")
    print("=" * 60)
    
    curl_get = None
    curl_clear = None
    
    # 1. Coba baca dari curl_get.txt dan curl_clear.txt terlebih dahulu (Utama)
    try:
        with open('curl_get.txt', 'r', encoding='utf-8') as f:
            print("[*] Membaca cURL get dari curl_get.txt...")
            curl_get = parse_curl(f.read())
    except FileNotFoundError:
        pass
        
    try:
        with open('curl_clear.txt', 'r', encoding='utf-8') as f:
            print("[*] Membaca cURL clear dari curl_clear.txt...")
            curl_clear = parse_curl(f.read())
    except FileNotFoundError:
        pass

    # 2. Fallback: Coba baca dari curl.txt jika file terpisah belum lengkap
    if not curl_get or not curl_clear:
        try:
            with open('curl.txt', 'r', encoding='utf-8') as f:
                curl_content = f.read().strip()
            print("[*] Fallback: Membaca cURL dari curl.txt...")
            commands = split_curl_commands(curl_content)
            for cmd in commands:
                parsed = parse_curl(cmd)
                c_type = detect_curl_type(parsed)
                if c_type == 'get' and not curl_get:
                    curl_get = parsed
                elif c_type == 'clear' and not curl_clear:
                    curl_clear = parsed
        except FileNotFoundError:
            pass

    # 3. Validasi
    if not curl_get and not curl_clear:
        print("[!] Error: Tidak ditemukan cURL command.")
        print("    Silakan buat file 'curl_get.txt' (ambil data) dan 'curl_clear.txt' (hapus data).")
        return

    # Flow A: Ambil data dan simpan ke ids.json (jika ada curl_get)
    all_ids = []
    use_existing = False

    # Coba baca dari ids.json terlebih dahulu jika ada
    try:
        with open('ids.json', 'r', encoding='utf-8') as f:
            ids_data = json.load(f)
            all_ids = [item['id'] for item in ids_data if isinstance(item, dict) and 'id' in item]
    except Exception:
        all_ids = []

    if all_ids:
        if curl_get:
            print(f"\n[*] Menemukan file 'ids.json' berisi {len(all_ids)} ID.")
            ans = input("Apakah Anda ingin menggunakan ID yang sudah ada untuk proses clear saja? (Y/n): ").strip().lower()
            if ans != 'n':
                print(" -> Menggunakan ID dari ids.json (melewati pengambilan data ulang).")
                use_existing = True
            else:
                all_ids = []
        else:
            print(f"\n[*] Tidak ada cURL untuk mengambil data (GET). Menggunakan {len(all_ids)} ID dari ids.json.")
            use_existing = True

    if not use_existing:
        if curl_get:
            # Cek apakah emails.txt ada dan berisi data
            emails = []
            try:
                with open('emails.txt', 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            emails.append(line)
            except FileNotFoundError:
                pass

            if emails:
                print(f"\n[*] Menemukan {len(emails)} email di 'emails.txt'. Menjalankan pencarian per email...")
            else:
                print("\n[*] Menjalankan flow pengambilan data ID assignment...")

            try:
                base_payload = json.loads(curl_get['data'])
            except Exception as e:
                print(f"[!] Gagal mengekstrak payload JSON dari cURL Get: {e}")
                return
                
            # Jika emails kosong, kita jalankan satu kali menggunakan payload default dari cURL
            loop_targets = emails if emails else [None]
            import copy
            
            for idx, target_email in enumerate(loop_targets):
                roles = ["TARGET_ONLY", "SUPERVISOR_ONLY"] if target_email else [None]
                email_ids_count = 0
                
                for role in roles:
                    payload = copy.deepcopy(base_payload)
                    if target_email:
                        # Tentukan role filter di payload
                        if 'assignmentExtraParam' in payload:
                            payload['assignmentExtraParam']['filterTargetType'] = role
                        
                        role_label = "Pencacah/Petugas" if role == "TARGET_ONLY" else "Pengawas"
                        print(f"\n[{idx+1}/{len(emails)}] Memproses email: {target_email} ({role_label})")
                        
                        if 'search' in payload:
                            payload['search']['value'] = target_email
                        else:
                            payload['search'] = {'value': target_email, 'regex': False}
                    
                    start = payload.get('start', 0)
                    length = payload.get('length', 50)
                    
                    while True:
                        payload['start'] = start
                        print(f" -> Mengambil data mulai dari indeks {start} (length: {length})...")
                        
                        try:
                            response = requests.post(
                                curl_get['url'],
                                headers=curl_get['headers'],
                                json=payload
                            )
                            response.raise_for_status()
                            res_json = response.json()
                        except Exception as e:
                            print(f"[!] Gagal menghubungi API datatable pada indeks {start}: {e}")
                            break
                            
                        records_filtered = res_json.get('recordsFiltered') or res_json.get('totalHit')
                        if records_filtered is not None and start == 0:
                            print(f" -> Total data terfilter di server: {records_filtered}")
                            
                        data_list = res_json.get('data') or res_json.get('searchData') or []
                        if not data_list:
                            print(" -> Halaman kosong / tidak ada data lagi.")
                            if start == 0:
                                print(f" -> Response JSON dari server: {res_json}")
                            break
                            
                        page_ids = []
                        for item in data_list:
                            if isinstance(item, dict) and 'id' in item:
                                page_ids.append(item['id'])
                            elif isinstance(item, list) and len(item) > 0:
                                page_ids.append(item[0])
                                
                        all_ids.extend(page_ids)
                        email_ids_count += len(page_ids)
                        print(f" -> Ditemukan {len(page_ids)} ID. Total terakumulasi: {len(all_ids)} ID.")
                        
                        if len(data_list) < length:
                            break
                            
                        start += length
                        
                if target_email:
                    print(f" -> Selesai memproses {target_email}. Total terkumpul: {email_ids_count} ID.")
                
            if all_ids:
                # Simpan ke ids.json
                ids_to_save = [{"id": r_id} for r_id in all_ids]
                with open('ids.json', 'w', encoding='utf-8') as f:
                    json.dump(ids_to_save, f, indent=2)
                print(f"\n[*] Berhasil menyimpan {len(all_ids)} ID ke ids.json.")
            else:
                print("[!] Tidak ada ID yang ditemukan dari API datatable.")
        else:
            print("[!] File ids.json tidak ditemukan atau kosong, dan tidak ada cURL untuk mengambil data baru.")
            return

    # Flow B: Eksekusi clear/hapus assignment
    if not all_ids:
        print("[!] Tidak ada ID yang akan diproses untuk dihapus.")
        return

    if not curl_clear:
        print("\n[!] Perhatian: cURL untuk clear/hapus assignment tidak ditemukan.")
        print("    ID telah disimpan di ids.json. Silakan berikan cURL untuk clear assignment")
        print("    di curl.txt atau curl_clear.txt untuk melanjutkan penghapusan.")
        return

    print(f"\n[?] Siap melakukan clear untuk {len(all_ids)} assignment.")
    confirm = input(f"Apakah Anda yakin ingin menghapus {len(all_ids)} assignment ini? (y/N): ").strip().lower()
    if confirm != 'y':
        print("[*] Dibatalkan oleh pengguna.")
        return

    import datetime
    timestamp_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_file = "execution.log"
    
    with open(log_file, "a", encoding="utf-8") as lf:
        lf.write(f"\n==================================================\n")
        lf.write(f"EKSEKUSI CLEAR ASSIGNMENT: {timestamp_str}\n")
        lf.write(f"==================================================\n")
        
    # Kirim request ke clear endpoint dalam batch
    batch_size = 100
    total_cleared = 0
    total_failed = 0
    failed_details = []
    
    print(f"\n[*] Memulai pengiriman batch (batch size: {batch_size})...")
    
    for i in range(0, len(all_ids), batch_size):
        batch = all_ids[i:i+batch_size]
        log_msg = f"[{i//batch_size + 1}/{(len(all_ids)-1)//batch_size + 1}] Mengirim {len(batch)} ID..."
        print(log_msg)
        with open(log_file, "a", encoding="utf-8") as lf:
            lf.write(log_msg + "\n")
        
        try:
            response = requests.post(
                curl_clear['url'],
                headers=curl_clear['headers'],
                json=batch
            )
            
            if response.status_code in (200, 201):
                msg = f" -> [SUKSES] Status HTTP: {response.status_code}"
                print(msg)
                total_cleared += len(batch)
            else:
                msg = f" -> [GAGAL] Status HTTP: {response.status_code}"
                print(msg)
                total_failed += len(batch)
                for item_id in batch:
                    failed_details.append({"id": item_id, "reason": f"Batch HTTP {response.status_code}"})
                
            with open(log_file, "a", encoding="utf-8") as lf:
                lf.write(msg + "\n")
                
            try:
                res_json = response.json()
                resp_msg = f" -> Response: {res_json}"
                print(resp_msg)
                with open(log_file, "a", encoding="utf-8") as lf:
                    lf.write(resp_msg + "\n")
            except Exception:
                resp_msg = f" -> Response Text: {response.text[:200]}"
                print(resp_msg)
                with open(log_file, "a", encoding="utf-8") as lf:
                    lf.write(resp_msg + "\n")
                
        except Exception as e:
            msg = f" -> [ERROR] Terjadi error saat mengirim batch: {e}"
            print(msg)
            with open(log_file, "a", encoding="utf-8") as lf:
                lf.write(msg + "\n")
            total_failed += len(batch)
            for item_id in batch:
                failed_details.append({"id": item_id, "reason": f"Exception: {e}"})
            
    summary_lines = []
    summary_lines.append("\n" + "=" * 50)
    summary_lines.append("           RINGKASAN AKHIR PENGEKSEKUSIAN")
    summary_lines.append("=" * 50)
    summary_lines.append(f" - Berhasil diproses : {total_cleared}")
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
