#!/usr/bin/env python3
"""sync_db.py - Sincronizza database.db con Google Drive (macOS/Windows/Linux)
Uso: python3 sync_db.py [scarica|carica|stato|lock-off] [--forza]

Ad ogni 'carica' viene salvata su Drive anche una copia storica
timestampata in CaronteApp/storico_db/, mantenendo solo le ultime
MAX_BACKUP versioni (le più vecchie vengono eliminate automaticamente).

Il database contiene dati personali dei docenti (inclusi, nel campo
motivo delle assenze, dati particolari ex art. 9 GDPR come "malattia").
Per questo motivo, dalla revisione del report GDPR di agosto 2026, il
file caricato/scaricato da Google Drive viene sempre cifrato con lo
stesso meccanismo del backup locale (modules/backup_cifrato.py, Fernet
AES-128+HMAC-SHA256) — su Drive non transita più il database in chiaro.
"""
import hashlib, os, sys, shutil, json, platform
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from modules.backup_cifrato import cifra_file, decifra_file
from cryptography.fernet import InvalidToken

DRIVE_SUBFOLDER  = "CaronteApp"
DRIVE_DB_NAME     = "database.db.enc"   # file cifrato condiviso su Drive
DRIVE_DB_NAME_OLD = "database.db"       # nome legacy (in chiaro, pre-agosto 2026)
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

def _hash_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()
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
    """Copia il DB locale nello storico, CIFRATO, con nome timestampato e applica la rotazione a MAX_BACKUP file."""
    s = cartella_storico(c)
    ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    macchina = platform.node().replace(" ", "_")
    nome_backup = f"database_{ts_str}_{macchina}.db.enc"
    dest = s / nome_backup
    cifra_file(str(db), str(dest))

    # Rotazione: mantieni solo le MAX_BACKUP versioni più recenti
    backups = sorted(s.glob("database_*.db.enc"), key=lambda p: p.stat().st_mtime, reverse=True)
    rimossi = 0
    for vecchio in backups[MAX_BACKUP:]:
        vecchio.unlink()
        rimossi += 1

    return nome_backup, len(backups) - rimossi if backups else 1

def scarica(db, forzato=False):
    c = cartella_drive()
    if not c: print("  Google Drive non trovato."); return False
    db_drive = c/DRIVE_DB_NAME
    db_drive_old = c/DRIVE_DB_NAME_OLD

    if not db_drive.exists() and not db_drive_old.exists():
        print("  Nessun DB su Drive."); return False

    # Migrazione: solo il vecchio file in chiaro presente su Drive.
    # Lo si usa una volta come sorgente, poi il prossimo 'carica' da
    # questa macchina lo sostituirà con la versione cifrata.
    if not db_drive.exists() and db_drive_old.exists():
        print("  Trovato solo il vecchio database.db in chiaro su Drive (formato pre-cifratura).")
        print(f"  Drive (legacy, non cifrato):  {_fmt(_ts(db_drive_old))}  ({db_drive_old.stat().st_size//1024} KB)")
        print(f"  Locale: {_fmt(_ts(db))}")
        lk = lock_info(c)
        if lk and not forzato:
            print(f"  ATTENZIONE: in uso da {lk.get('macchina')} dal {str(lk.get('dal',''))[:19]}")
            if input("  Procedere? (s/N): ").strip().lower() != "s":
                print("  Annullato."); return False
        if forzato or not Path(db).exists() or _hash_file(db_drive_old) != _hash_file(db):
            if Path(db).exists(): shutil.copy2(db, str(db)+".bak")
            shutil.copy2(db_drive_old, db)
        set_lock(c, True)
        print("  DB pronto (da formato legacy) - lock attivato")
        print("  Esegui 'carica' per pubblicare la versione cifrata e rimuovere quella in chiaro.")
        return True

    print(f"  Drive:  {_fmt(_ts(db_drive))}  ({db_drive.stat().st_size//1024} KB, cifrato)")
    print(f"  Locale: {_fmt(_ts(db))}")
    lk = lock_info(c)
    if lk and not forzato:
        print(f"  ATTENZIONE: in uso da {lk.get('macchina')} dal {str(lk.get('dal',''))[:19]}")
        if input("  Procedere? (s/N): ").strip().lower() != "s":
            print("  Annullato."); return False
    # Decifra sempre e confronta per CONTENUTO, non per data di
    # modifica — segnalato da Roberto (Sessione 66): il timestamp del
    # file locale avanza ad ogni giro del sync automatico additivo
    # (modules/auto_sync.py fa commit ogni 30s anche quando non arriva
    # nulla di nuovo per questa macchina), quindi può facilmente
    # risultare "più recente" del file appena pubblicato su Drive anche
    # quando il CONTENUTO di Drive è in realtà più aggiornato. Il
    # vecchio confronto `_ts(db_drive) > _ts(db)` in quel caso saltava
    # silenziosamente la sostituzione — 'scarica' stampava comunque "DB
    # pronto", dando l'impressione che l'aggiornamento fosse avvenuto
    # quando in realtà il contenuto locale restava quello vecchio.
    tmp_path = str(db) + ".scaricato_tmp"
    try:
        decifra_file(str(db_drive), tmp_path)
    except InvalidToken:
        # Non incolonnare mai un file locale non decifrabile sopra il
        # database esistente: la chiave di cifratura (data/backup/.backup_key)
        # non corrisponde a quella usata per cifrare il file su Drive —
        # tipicamente perché questa macchina ha generato la propria chiave
        # invece di ricevere quella condivisa dalle altre macchine che
        # usano questo Drive. Si prosegue con il DB locale esistente
        # (se presente) e si segnala l'errore con exit code diverso da 0,
        # così lo script di avvio può interrompersi invece di ripartire
        # con dati vecchi e poi ricaricarli su Drive sovrascrivendo la
        # cronologia buona.
        print("  ERRORE: impossibile decifrare il DB da Drive.")
        print("  La chiave di cifratura locale (data/backup/.backup_key) non è la stessa")
        print("  usata per cifrare il file su Drive. Copia il file .backup_key (e .backup_salt)")
        print("  dalla macchina che ha creato il backup dentro data/backup/ su questa macchina,")
        print("  poi riprova. NON procedere: il DB locale potrebbe essere superato.")
        return None

    if forzato or not Path(db).exists() or _hash_file(tmp_path) != _hash_file(db):
        if Path(db).exists(): shutil.copy2(db, str(db)+".bak")
        shutil.move(tmp_path, str(db))
        set_lock(c, True)
        print("  DB aggiornato da Drive - lock attivato")
    else:
        os.remove(tmp_path)
        set_lock(c, True)
        print("  Locale già allineato al contenuto su Drive (nessuna differenza) - lock attivato")
    return True

def carica(db):
    c = cartella_drive()
    if not c: print("  Google Drive non trovato."); return False
    if not Path(db).exists(): print("  DB locale non trovato."); return False

    cifra_file(str(db), str(c/DRIVE_DB_NAME))

    # Ripulisci il vecchio file in chiaro, se presente (migrazione da
    # formato pre-cifratura): non deve restare un doppione non cifrato
    # su Drive dopo che la versione cifrata è stata pubblicata.
    db_drive_old = c/DRIVE_DB_NAME_OLD
    if db_drive_old.exists():
        db_drive_old.unlink()
        print("  Rimosso il vecchio database.db in chiaro da Drive (migrazione a formato cifrato completata).")

    nome_backup, n_storico = salva_storico(c, db)
    set_lock(c, False)

    print(f"  DB caricato e cifrato ({Path(db).stat().st_size//1024} KB) - lock rimosso")
    print(f"  Percorso: {c/DRIVE_DB_NAME}")
    print(f"  Storico  : {nome_backup}  ({n_storico}/{MAX_BACKUP} versioni conservate, cifrate)")
    return True

def lista_storico():
    c = cartella_drive()
    if not c: print("  Google Drive non trovato."); return
    s = c / STORICO_SUBDIR
    if not s.exists():
        print("  Nessuno storico presente."); return
    backups = sorted(s.glob("database_*.db.enc"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not backups:
        print("  Nessuna versione storica presente."); return
    print("="*55)
    print(f"  Storico database ({len(backups)}/{MAX_BACKUP} versioni, cifrate)")
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
        dbd_old = c/DRIVE_DB_NAME_OLD
        if dbd.exists():
            print(f"  DB Drive : {_fmt(_ts(dbd))}  ({dbd.stat().st_size//1024} KB, cifrato)")
        elif dbd_old.exists():
            print(f"  DB Drive : {_fmt(_ts(dbd_old))}  ({dbd_old.stat().st_size//1024} KB, LEGACY NON CIFRATO — esegui 'carica' per migrare)")
        else:
            print("  DB Drive : non presente")
        lk = lock_info(c)
        print(f"  Lock     : {'IN USO da ' + lk.get('macchina','?') if lk else 'libero'}")
        s = c / STORICO_SUBDIR
        n_backup = len(list(s.glob("database_*.db.enc"))) if s.exists() else 0
        print(f"  Storico  : {n_backup}/{MAX_BACKUP} versioni conservate (cifrate)")
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
    if cmd == "scarica":
        print("Scarico DB da Drive...")
        esito = scarica(db, forzato)
        # esito: True = ok, False = niente da fare/annullato (non bloccante),
        # None = errore di decifratura (bloccante: chiave sbagliata)
        sys.exit(1 if esito is None else 0)
    elif cmd == "carica": print("Carico DB su Drive..."); carica(db)
    elif cmd == "stato": stato()
    elif cmd == "storico": lista_storico()
    elif cmd == "lock-off":
        c = cartella_drive()
        if c: set_lock(c, False); print("Lock rimosso.")
    else: print("Uso: python3 sync_db.py [scarica|carica|stato|storico|lock-off]")
