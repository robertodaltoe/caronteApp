#!/usr/bin/env python3
"""sync_db.py - Sincronizza database.db con Google Drive (macOS/Windows/Linux)
Uso: python3 sync_db.py [scarica|carica|stato|lock-off] [--forza]
"""
import os, sys, shutil, json, platform
from datetime import datetime
from pathlib import Path

DRIVE_SUBFOLDER = "CaronteApp"
DRIVE_DB_NAME   = "database.db"
DRIVE_LOCK_NAME = "caronte.lock"

def trova_drive():
    env = os.environ.get("CARONTE_DRIVE_PATH")
    if env and Path(env).exists(): return Path(env)
    sistema = platform.system()
    home = Path.home()
    if sistema == "Darwin":
        cs = home / "Library" / "CloudStorage"
        candidati = []
        if cs.exists():
            for e in cs.iterdir():
                if e.name.startswith("GoogleDrive-"):
                    for sub in ["Il mio Drive", "My Drive"]:
                        pp = e / sub
                        if pp.exists(): candidati.append(pp)
        candidati += [home/"Google Drive"/"Il mio Drive",
                      home/"Google Drive"/"My Drive",
                      home/"Google Drive",
                      Path("/Volumes/Google Drive")]
    elif sistema == "Windows":
        up = Path(os.environ.get("USERPROFILE", "C:/Users/Roberto"))
        candidati = [up/"Google Drive"/"My Drive", up/"Google Drive", up/"My Drive", Path("G:/My Drive")]
    else:
        candidati = [home/"Google Drive", home/"GoogleDrive"]
    for p in candidati:
        if p.exists(): return p
    return None

def cartella_drive():
    d = trova_drive()
    if not d: return None
    c = d / DRIVE_SUBFOLDER
    c.mkdir(parents=True, exist_ok=True)
    return c

def _ts(p): return Path(p).stat().st_mtime if Path(p).exists() else 0.0
def _fmt(ts): return datetime.fromtimestamp(ts).strftime("%d/%m/%Y %H:%M:%S") if ts else "non esiste"

def lock_info(c):
    lk = Path(c)/DRIVE_LOCK_NAME
    if not lk.exists(): return None
    try: return json.loads(lk.read_text(encoding="utf-8"))
    except: return None

def set_lock(c, attivo):
    lk = Path(c)/DRIVE_LOCK_NAME
    if attivo:
        lk.write_text(json.dumps({"macchina":platform.node(),"sistema":platform.system(),
            "utente":os.environ.get("USER") or os.environ.get("USERNAME",""),
            "dal":datetime.now().isoformat()}, ensure_ascii=False), encoding="utf-8")
    elif lk.exists(): lk.unlink()

def scarica(db, forzato=False):
    c = cartella_drive()
    if not c: print("  Google Drive non trovato."); return False
    db_drive = c/DRIVE_DB_NAME
    if not db_drive.exists(): print("  Nessun DB su Drive."); return False
    print(f"  Drive:  {_fmt(_ts(db_drive))}  ({db_drive.stat().st_size//1024} KB)")
    print(f"  Locale: {_fmt(_ts(db))}")
    lk = lock_info(c)
    if lk and not forzato:
        print(f"  ATTENZIONE: in uso da {lk.get(chr(109)+chr(97)+chr(99)+chr(99)+chr(104)+chr(105)+chr(110)+chr(97))} dal {str(lk.get(chr(100)+chr(97)+chr(108),""))[:19]}")
        if input("  Procedere? (s/N): ").strip().lower() != "s":
            print("  Annullato."); return False
    if _ts(db_drive) > _ts(db) or forzato:
        if Path(db).exists(): shutil.copy2(db, str(db)+".bak")
        shutil.copy2(db_drive, db)
    set_lock(c, True)
    print("  DB pronto - lock attivato"); return True

def carica(db):
    c = cartella_drive()
    if not c: print("  Google Drive non trovato."); return False
    if not Path(db).exists(): print("  DB locale non trovato."); return False
    shutil.copy2(db, c/DRIVE_DB_NAME)
    set_lock(c, False)
    print(f"  DB caricato ({Path(db).stat().st_size//1024} KB) - lock rimosso")
    print(f"  Percorso: {c/DRIVE_DB_NAME}"); return True

def stato():
    base = Path(__file__).parent
    db = base/"database.db"
    c = cartella_drive()
    print("="*55)
    print("  CaronteApp - Stato sincronizzazione DB")
    print(f"  {platform.system()} - {platform.node()}")
    print("="*55)
    if c:
        print(f"  Drive    : {c}")
        dbd = c/DRIVE_DB_NAME
        print(f"  DB Drive : {_fmt(_ts(dbd))}" + (f"  ({dbd.stat().st_size//1024} KB)" if dbd.exists() else ""))
        lk = lock_info(c)
        print(f"  Lock     : {chr(73)+chr(78)+chr(32)+chr(85)+chr(83)+chr(79)+chr(32)+chr(100)+chr(97)+chr(32)+lk.get(chr(109)+chr(97)+chr(99)+chr(99)+chr(104)+chr(105)+chr(110)+chr(97)) if lk else chr(108)+chr(105)+chr(98)+chr(101)+chr(114)+chr(111)}")
    else:
        print("  Drive    : NON TROVATO")
        print("  Imposta CARONTE_DRIVE_PATH oppure installa Google Drive for Desktop")
    print(f"  DB Locale: {_fmt(_ts(db))}" + (f"  ({db.stat().st_size//1024} KB)" if db.exists() else ""))
    print("="*55)

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "stato"
    base = Path(__file__).parent
    db = base/"database.db"
    forzato = "--forza" in sys.argv
    if cmd == "scarica": print("Scarico DB da Drive..."); scarica(db, forzato)
    elif cmd == "carica": print("Carico DB su Drive..."); carica(db)
    elif cmd == "stato": stato()
    elif cmd == "lock-off":
        c = cartella_drive()
        if c: set_lock(c, False); print("Lock rimosso.")
    else: print("Uso: python3 sync_db.py [scarica|carica|stato|lock-off]")
