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
    }
}

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
    print(" q. Keluar")
    print("-" * 60)
    
    choice = input("Masukkan pilihan Anda (1/2/3/q): ").strip()
    if choice.lower() == 'q':
        print("[*] Selesai.")
        sys.exit(0)
    elif choice in MODULES:
        run_module(MODULES[choice]["name"])
    else:
        print("[!] Pilihan tidak valid.")

def main():
    # Jika argument diberikan di terminal (misal: python main.py approve)
    if len(sys.argv) > 1:
        target_name = sys.argv[1].lower()
        # Cari berdasarkan nama modul
        found = False
        for info in MODULES.values():
            if info["name"] == target_name:
                run_module(target_name)
                found = True
                break
        if not found:
            print(f"[!] Modul '{target_name}' tidak dikenal.")
            print("Pilihan modul yang tersedia:")
            for info in MODULES.values():
                print(f" - {info['name']}")
            sys.exit(1)
    else:
        # Tampilkan menu interaktif jika tanpa argumen
        while True:
            show_menu()
            print()

if __name__ == "__main__":
    main()
