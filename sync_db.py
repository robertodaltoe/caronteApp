#!/usr/bin/env python3
"""sync_db.py - Sincronizza database.db con Google Drive (macOS/Windows/Linux)
Uso: python3 sync_db.py [scarica|carica|stato|lock-off] [--forza]

Ad ogni 'carica' viene salvata su Drive anche una copia storica
timestampata in CaronteApp/storico_db/, mantenendo solo le ultime
MAX_BACKUP versioni (le più vecchie vengono eliminate automaticamente).
"""
import os, sys, shutil, json, platform
from datetime import datetime
from pathlib import Path

DRIVE_SUBFOLDER  = "CaronteApp"
DRIVE_DB_NAME    = "database.db"
DRIVE_LOCK_NAME  = "caronte.lock"
STORICO_SUBDIR   = "storico_db"
MAX_BACKUP       = 10

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

def cartella_storico(c):
    s = c / STORICO_SUBDIR
    s.mkdir(parents=True, exist_ok=True)
    return s

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

def salva_storico(c, db):
    """Copia il DB locale nello storico con nome timestampato e applica la rotazione a MAX_BACKUP file."""
    s = cartella_storico(c)
    ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    macchina = platform.node().replace(" ", "_")
    nome_backup = f"database_{ts_str}_{macchina}.db"
    dest = s / nome_backup
    shutil.copy2(db, dest)

    # Rotazione: mantieni solo le MAX_BACKUP versioni più recenti
    backups = sorted(s.glob("database_*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
    rimossi = 0
    for vecchio in backups[MAX_BACKUP:]:
        vecchio.unlink()
        rimossi += 1

    return nome_backup, len(backups) - rimossi if backups else 1

def scarica(db, forzato=False):
    c = cartella_drive()
    if not c: print("  Google Drive non trovato."); return False
    db_drive = c/DRIVE_DB_NAME
    if not db_drive.exists(): print("  Nessun DB su Drive."); return False
    print(f"  Drive:  {_fmt(_ts(db_drive))}  ({db_drive.stat().st_size//1024} KB)")
    print(f"  Locale: {_fmt(_ts(db))}")
    lk = lock_info(c)
    if lk and not forzato:
        print(f"  ATTENZIONE: in uso da {lk.get('macchina')} dal {str(lk.get('dal',''))[:19]}")
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

    nome_backup, n_storico = salva_storico(c, db)
    set_lock(c, False)

    print(f"  DB caricato ({Path(db).stat().st_size//1024} KB) - lock rimosso")
    print(f"  Percorso: {c/DRIVE_DB_NAME}")
    print(f"  Storico  : {nome_backup}  ({n_storico}/{MAX_BACKUP} versioni conservate)")
    return True

def lista_storico():
    c = cartella_drive()
    if not c: print("  Google Drive non trovato."); return
    s = c / STORICO_SUBDIR
    if not s.exists():
        print("  Nessuno storico presente."); return
    backups = sorted(s.glob("database_*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not backups:
        print("  Nessuna versione storica presente."); return
    print("="*55)
    print(f"  Storico database ({len(backups)}/{MAX_BACKUP} versioni)")
    print("="*55)
    for p in backups:
        print(f"  {_fmt(p.stat().st_mtime)}  —  {p.name}  ({p.stat().st_size//1024} KB)")
    print("="*55)

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
        print(f"  Lock     : {'IN USO da ' + lk.get('macchina','?') if lk else 'libero'}")
        s = c / STORICO_SUBDIR
        n_backup = len(list(s.glob("database_*.db"))) if s.exists() else 0
        print(f"  Storico  : {n_backup}/{MAX_BACKUP} versioni conservate")
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
    elif cmd == "storico": lista_storico()
    elif cmd == "lock-off":
        c = cartella_drive()
        if c: set_lock(c, False); print("Lock rimosso.")
    else: print("Uso: python3 sync_db.py [scarica|carica|stato|storico|lock-off]")
