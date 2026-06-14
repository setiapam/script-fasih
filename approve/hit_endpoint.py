import json
import shlex
import requests

def parse_curl_file(filepath):
    """
    Membaca raw cURL dari file, mengekstrak headers dan cookies.
    Bagian payload (--data-raw) diabaikan karena kita akan merakitnya 
    secara dinamis khusus untuk multipart/form-data.
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        curl_content = f.read().strip()
    
    curl_content = curl_content.replace('\\\n', ' ')
    tokens = shlex.split(curl_content)
    
    headers = {}
    cookies_str = ""
    
    for i in range(len(tokens)):
        if tokens[i] in ['-H', '--header'] and i + 1 < len(tokens):
            header_line = tokens[i+1]
            if ':' in header_line:
                key, value = header_line.split(':', 1)
                # KITA HARUS MEMBUANG CONTENT-TYPE BAWAAN cURL
                # Jika kita pakai multipart/form-data dari cURL, boundary-nya akan statis
                # Library 'requests' butuh kebebasan untuk membuat boundary-nya sendiri
                if key.strip().lower() != 'content-type':
                    headers[key.strip()] = value.strip()
                
        elif tokens[i] in ['-b', '--cookie'] and i + 1 < len(tokens):
            cookies_str = tokens[i+1]
            
    if cookies_str:
        headers['Cookie'] = cookies_str
        
    return headers

def main():
    print("[*] Mengekstrak headers dan cookies dari curl.txt...")
    try:
        headers = parse_curl_file('curl.txt')
    except FileNotFoundError:
        print("[!] File curl.txt tidak ditemukan!")
        return

    print("[*] Membaca data dari ids.json...")
    try:
        with open('ids.json', 'r', encoding='utf-8') as f:
            ids = json.load(f)
    except FileNotFoundError:
        print("[!] File ids.json tidak ditemukan!")
        return

    # Endpoint approval yang benar
    url_base = "https://fasih-sm.bps.go.id/assignment-approval/api/v2/approval"
    
    import datetime
    timestamp_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_file = "execution.log"
    
    with open(log_file, "a", encoding="utf-8") as lf:
        lf.write(f"\n==================================================\n")
        lf.write(f"EKSEKUSI APPROVE: {timestamp_str}\n")
        lf.write(f"==================================================\n")
        
    print(f"[*] Memulai proses approval untuk {len(ids)} ID...\n")
    print("-" * 40)
    
    total_success = 0
    total_failed = 0
    failed_details = []
    
    for idx, item in enumerate(ids):
        assignment_id = item.get("id")
        
        if not assignment_id:
            continue
            
        log_msg = f"[{idx+1}/{len(ids)}] Memproses ID: {assignment_id}"
        print(log_msg)
        with open(log_file, "a", encoding="utf-8") as lf:
            lf.write(log_msg + "\n")
        
        # --- PERAKITAN PAYLOAD MULTIPART/FORM-DATA ---
        # Berdasarkan cURL Anda, ada 3 field yang harus dikirim
        multipart_data = {
            'assignmentId': (None, assignment_id),
            'statusApproval': (None, 'true'),
            'comment': (None, '{"dataKey":"","notes":[]}')
        }
        
        try:
            # Kita menggunakan parameter 'files' alih-alih 'data' agar 
            # library requests otomatis memformatnya menjadi multipart/form-data
            response = requests.post(url_base, headers=headers, files=multipart_data)
            
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
            except json.JSONDecodeError:
                resp_msg = f" -> Response: {response.text}"
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
    summary_lines.append(f" - Total target      : {len(ids)}")
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
