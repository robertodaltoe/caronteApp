#!/usr/bin/env python3
"""
Setup CaronteApp — primo avvio su una nuova macchina.
Eseguire con: python3 setup.py
"""
import subprocess, sys, os, platform

def run(cmd, **kw):
    print(f"  > {' '.join(cmd) if isinstance(cmd, list) else cmd}")
    return subprocess.run(cmd, shell=isinstance(cmd, str), **kw)

def main():
    print("=" * 55)
    print("  CaronteApp — Setup primo avvio")
    print(f"  Python {sys.version.split()[0]}  |  {platform.system()} {platform.machine()}")
    print("=" * 55)

    base = os.path.dirname(os.path.abspath(__file__))
    os.chdir(base)

    # 1. Crea venv
    venv = os.path.join(base, "venv")
    if not os.path.exists(venv):
        print("\n[1/4] Creo venv...")
        run([sys.executable, "-m", "venv", "venv"])
    else:
        print("\n[1/4] Venv esistente — ok")

    # 2. Determina pip e python del venv
    if platform.system() == "Windows":
        pip    = os.path.join(venv, "Scripts", "pip.exe")
        python = os.path.join(venv, "Scripts", "python.exe")
    else:
        pip    = os.path.join(venv, "bin", "pip3")
        python = os.path.join(venv, "bin", "python3")
        if not os.path.exists(pip):
            pip = os.path.join(venv, "bin", "pip")

    # 3. Installa dipendenze Python
    print("\n[2/4] Installo dipendenze Python...")
    run([pip, "install", "--upgrade", "pip"], capture_output=True)
    r = run([pip, "install", "-r", "requirements.txt"])
    if r.returncode != 0:
        print("  ERRORE nell'installazione dipendenze")
        sys.exit(1)
    print("  Dipendenze OK")

    # 4. Istruzioni WeasyPrint per sistema
    print("\n[3/4] Dipendenze di sistema per WeasyPrint:")
    if platform.system() == "Darwin":
        print("  macOS rilevato.")
        brew = subprocess.run(["which", "brew"], capture_output=True).returncode == 0
        if brew:
            print("  Homebrew trovato — installo librerie...")
            run(["brew", "install", "pango", "cairo", "gdk-pixbuf", "libffi"])
        else:
            print("  Homebrew NON trovato.")
            print("  Installalo con:")
            print('  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"')
            print("  Poi: brew install pango cairo gdk-pixbuf libffi")
    elif platform.system() == "Windows":
        print("  Windows rilevato.")
        print("  Installa GTK3 Runtime da:")
        print("  https://github.com/tschoonj/GTK-for-Windows-Runtime-Environment-Installer/releases")
        print("  Scarica e lancia l'installer .exe, poi riavvia il terminale.")
    elif platform.system() == "Linux":
        print("  Linux rilevato.")
        run("sudo apt-get install -y libpango-1.0-0 libcairo2 libgdk-pixbuf2.0-0 libffi-dev", shell=True)

    # 5. Inizializza DB se non esiste
    print("\n[4/4] Verifico database...")
    db_path = os.path.join(base, "database.db")
    if not os.path.exists(db_path):
        print("  database.db non trovato — inizializzo struttura vuota...")
        r = run([python, "-c",
            "from app import create_app; from models import db; "
            "app = create_app(); "
            "app.app_context().push(); db.create_all(); "
            "print('  DB inizializzato.')"])
        if r.returncode != 0:
            print("  ATTENZIONE: errore init DB — verifica le librerie WeasyPrint prima di avviare.")
    else:
        size = os.path.getsize(db_path)
        print(f"  database.db trovato ({size // 1024} KB) — ok")

    print("\n" + "=" * 55)
    print("  Setup completato.")
    print()
    if platform.system() == "Windows":
        print("  Per avviare:  avvia_caronte.bat")
    else:
        print("  Per avviare:  ./avvia_caronte.sh")
        print("     oppure:   python3 app.py")
    print("=" * 55)

if __name__ == "__main__":
    main()
