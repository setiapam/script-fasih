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
    
    print(f"[*] Memulai proses approval untuk {len(ids)} ID...\n")
    print("-" * 40)
    
    for idx, item in enumerate(ids):
        assignment_id = item.get("id")
        
        if not assignment_id:
            continue
            
        print(f"[{idx+1}/{len(ids)}] Memproses ID: {assignment_id}")
        
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
            
            print(f" -> Status HTTP: {response.status_code}")
            
            try:
                parsed_response = response.json()
                # Hanya menampilkan sebagian isi response agar rapi
                print(f" -> Response Status: {parsed_response.get('message')} | Data: {parsed_response.get('data')}")
            except json.JSONDecodeError:
                print(f" -> Response: {response.text}")
                
            print("-" * 40)
            
        except requests.exceptions.RequestException as e:
            print(f" -> [Error] Request gagal: {e}")
            print("-" * 40)

if __name__ == "__main__":
    main()
