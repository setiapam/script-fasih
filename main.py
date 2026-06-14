#!/usr/bin/env python3
import os
import sys
import importlib

# Daftar modul yang tersedia
MODULES = {
    "1": {
        "name": "approve",
        "title": "Approve (Bulk Approval Penugasan)",
        "desc": "Mengotomatiskan approval massal berdasarkan target ID di ids.json."
    },
    "2": {
        "name": "clear-assignment",
        "title": "Clear Assignment (Hapus Alokasi Massal)",
        "desc": "Menarik ID dari API datatable dan menghapus alokasi berdasarkan email petugas/pengawas."
    },
    "3": {
        "name": "clear-petugas",
        "title": "Clear Petugas (Hapus Alokasi Per Petugas/Pengawas)",
        "desc": "Menghapus alokasi wilayah regional penugasan petugas/pengawas secara spesifik."
    },
    "4": {
        "name": "assign",
        "title": "Assign (Auto Allocation)",
        "desc": "Mengotomatiskan assignment Pencacah/Pengawas ke sampel berdasarkan assign.xlsx."
    }
}

# Langkah-langkah persiapan sebelum menjalankan modul
HELP_STEPS = {
    "approve": [
        "1. Login ke website FASIH BPS di browser Anda.",
        "2. Tekan F12 untuk membuka Developer Tools, lalu pilih tab 'Network'.",
        "3. Lakukan aksi persetujuan (approval) secara manual 1x pada web untuk memicu pemanggilan API.",
        "4. Cari request POST ke '.../api/v2/approval', klik kanan -> Copy -> Copy as cURL (bash).",
        "5. Paste cURL tersebut ke file: approve/curl.txt",
        "6. Siapkan daftar ID assignment yang ingin Anda setujui secara massal di berkas: approve/ids.json dalam format array JSON."
    ],
    "clear-assignment": [
        "1. Login ke website FASIH BPS di browser Anda.",
        "2. Tekan F12 untuk membuka Developer Tools, lalu pilih tab 'Network'.",
        "3. Copy cURL dari request memuat daftar (datatable-all-user-survey-periode atau sejenisnya) -> Paste ke: clear-assignment/curl_get.txt",
        "4. Copy cURL dari request saat menghapus/clear alokasi -> Paste ke: clear-assignment/curl_clear.txt",
        "5. (Opsional) Masukkan daftar email petugas ke file: clear-assignment/emails.txt (satu email per baris)."
    ],
    "clear-petugas": [
        "1. Buka browser Anda dan buka halaman FASIH BPS yang menampilkan alokasi petugas.",
        "2. Tekan F12 untuk membuka Developer Tools, lalu pilih tab 'Network'.",
        "3. Lakukan interaksi (seperti refresh halaman atau klik menu alokasi) agar memicu pemanggilan API.",
        "4. Cari salah satu request API ke domain fasih-sm.bps.go.id (seperti request 'by-user' atau 'datatable').",
        "5. Klik kanan pada request tersebut -> Copy -> Copy as cURL (bash) -> Paste ke: clear-petugas/curl.txt",
        "6. Isi berkas email target yang ingin dibersihkan alokasinya pada: clear-petugas/petugas.txt (satu email per baris) dan clear-petugas/pengawas.txt (satu email per baris)."
    ],
    "assign": [
        "1. Login ke website FASIH BPS di browser Anda dan tekan F12 untuk membuka Developer Tools -> tab 'Network'.",
        "2. cURL Pencacah: Klik/filter tabel pencacah. Cari request bernama 'datatable?...' -> Klik Kanan -> Copy as cURL (bash) -> Paste ke: assign/curl_pencacah.txt",
        "3. cURL Pengawas: Klik/filter tabel pengawas. Cari request bernama 'datatable?...' -> Klik Kanan -> Copy as cURL (bash) -> Paste ke: assign/curl_pengawas.txt",
        "4. cURL Sampel: Klik/filter tabel sampel. Cari request bernama 'datatable?...' -> Klik Kanan -> Copy as cURL (bash) -> Paste ke: assign/curl_sampel.txt",
        "5. cURL Assign: Uji coba assign manual 1x di web. Cari request 'assign-by-selection/...' -> Copy as cURL (bash) -> Paste ke: assign/curl_assign.txt",
        "6. Excel: Siapkan berkas Excel di assign/assign.xlsx dengan kolom header: idsbr, email_pencacah, email_pengawas, perusahaan."
    ]
}

def show_help(target_name=None):
    if target_name:
        # Tampilkan bantuan untuk modul tertentu
        target_name = target_name.lower()
        if target_name in HELP_STEPS:
            print("\n" + "=" * 60)
            print(f" LANGKAH PERSIAPAN UNTUK MODUL: {target_name.upper()}")
            print("=" * 60)
            for step in HELP_STEPS[target_name]:
                print(step)
            print("=" * 60)
        else:
            print(f"[!] Modul '{target_name}' tidak dikenal.")
    else:
        # Tampilkan menu bantuan interaktif
        while True:
            print("\n" + "=" * 60)
            print("           MENU BANTUAN - PERSIAPAN MODUL")
            print("=" * 60)
            print("Pilih modul untuk melihat langkah-langkah persiapan sebelum run:")
            for key, info in MODULES.items():
                print(f" {key}. {info['title']}")
            print(" q. Kembali ke menu utama")
            print("-" * 60)
            choice = input("Masukkan pilihan bantuan (1/2/3/4/q): ").strip().lower()
            if choice == 'q':
                break
            elif choice in MODULES:
                mod_name = MODULES[choice]["name"]
                show_help(mod_name)
                input("\nTekan [Enter] untuk kembali ke menu bantuan...")
            else:
                print("[!] Pilihan tidak valid.")

def run_module(module_name):
    # Dapatkan path absolut direktori root dan sub-modul
    root_dir = os.path.dirname(os.path.abspath(__file__))
    module_dir = os.path.join(root_dir, module_name)
    
    if not os.path.exists(module_dir):
        print(f"[!] Folder modul '{module_name}' tidak ditemukan!")
        sys.exit(1)
        
    print(f"\n[*] Menjalankan modul: {module_name}...")
    print(f"[*] Berpindah direktori kerja ke: {module_dir}\n")
    
    # Berpindah cwd (current working directory) agar file curl.txt, ids.json, dll. dibaca dari folder modul
    os.chdir(module_dir)
    
    # Tambahkan folder modul ke sys.path agar Python bisa mengimpor modul di dalamnya
    sys.path.insert(0, module_dir)
    
    try:
        # Impor hit_endpoint dari folder modul secara dinamis
        hit_endpoint = importlib.import_module("hit_endpoint")
        # Panggil fungsi main() utama dari modul tersebut
        hit_endpoint.main()
    except Exception as e:
        print(f"\n[!] Terjadi kesalahan saat mengeksekusi modul: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Kembalikan direktori kerja ke root
        os.chdir(root_dir)

def show_menu():
    print("=" * 60)
    print("   AUTOMATION RUNNER - FASIH BPS SCRIPTS")
    print("=" * 60)
    print("Pilih modul script yang ingin dijalankan:")
    for key, info in MODULES.items():
        print(f" {key}. {info['title']}")
        print(f"    Desc: {info['desc']}")
    print("-" * 60)
    print(" h. Bantuan (Langkah persiapan masing-masing modul)")
    print(" q. Keluar")
    print("-" * 60)
    
    choice = input("Masukkan pilihan Anda (1/2/3/4/h/q): ").strip().lower()
    if choice == 'q':
        print("[*] Selesai.")
        sys.exit(0)
    elif choice == 'h':
        show_help()
    elif choice in MODULES:
        run_module(MODULES[choice]["name"])
    else:
        print("[!] Pilihan tidak valid.")

def main():
    # Jika argument diberikan di terminal (misal: python main.py help atau python main.py help approve)
    if len(sys.argv) > 1:
        arg_action = sys.argv[1].lower()
        if arg_action in ['h', 'help', '--help', '-h']:
            if len(sys.argv) > 2:
                target_mod = sys.argv[2].lower()
                show_help(target_mod)
            else:
                # Tampilkan daftar modul yang ada bantuan langkahnya
                print("\nBantuan Persiapan Modul FASIH BPS.")
                print("Jalankan: python main.py help <nama_modul>")
                print("Nama modul yang tersedia:")
                for info in MODULES.values():
                    print(f" - {info['name']}")
                print("\nAtau jalankan 'python main.py' untuk menu bantuan interaktif.")
            sys.exit(0)
        else:
            # Cari berdasarkan nama modul
            found = False
            for info in MODULES.values():
                if info["name"] == arg_action:
                    run_module(arg_action)
                    found = True
                    break
            if not found:
                print(f"[!] Modul '{arg_action}' tidak dikenal.")
                print("Pilihan modul yang tersedia:")
                for info in MODULES.values():
                    print(f" - {info['name']}")
                print("Gunakan 'python main.py help' untuk melihat bantuan langkah-langkah persiapan.")
                sys.exit(1)
    else:
        # Tampilkan menu interaktif jika tanpa argumen
        while True:
            show_menu()
            print()

if __name__ == "__main__":
    main()
