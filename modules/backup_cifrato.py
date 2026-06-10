"""
modules/backup_cifrato.py

Backup del database cifrato con Fernet (AES-128-CBC + HMAC-SHA256).
La chiave è derivata da una password con PBKDF2 e salvata in data/backup/.key
"""
import os
import shutil
import base64
from datetime import datetime
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes


KEY_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                        'data', 'backup', '.backup_key')
SALT_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                         'data', 'backup', '.backup_salt')


def _get_or_create_key():
    """Crea o carica la chiave di cifratura. La chiave è generata una volta e salvata."""
    os.makedirs(os.path.dirname(KEY_FILE), exist_ok=True)

    if os.path.exists(KEY_FILE) and os.path.exists(SALT_FILE):
        with open(KEY_FILE, 'rb') as f:
            key = f.read()
        return Fernet(key)

    # Prima esecuzione — genera chiave casuale
    key = Fernet.generate_key()
    with open(KEY_FILE, 'wb') as f:
        f.write(key)
    # Imposta permessi restrittivi (solo proprietario)
    try:
        os.chmod(KEY_FILE, 0o600)
    except Exception:
        pass
    # Crea salt file come marker
    with open(SALT_FILE, 'wb') as f:
        f.write(os.urandom(16))
    try:
        os.chmod(SALT_FILE, 0o600)
    except Exception:
        pass

    return Fernet(key)


def crea_backup_cifrato(db_path, backup_dir, suffisso=''):
    """
    Crea un backup cifrato del database.
    Restituisce il path del file .db.enc creato.
    """
    os.makedirs(backup_dir, exist_ok=True)
    f = _get_or_create_key()

    timestamp = datetime.now().strftime('%Y%m%d_%H%M')
    nome = f'database_{timestamp}{suffisso}.db.enc'
    dest = os.path.join(backup_dir, nome)

    with open(db_path, 'rb') as src:
        dati = src.read()

    cifrato = f.encrypt(dati)

    with open(dest, 'wb') as out:
        out.write(cifrato)

    # Rimuovi eventuale backup non cifrato con stesso timestamp
    vecchio = dest.replace('.db.enc', '.db')
    if os.path.exists(vecchio):
        os.remove(vecchio)

    return dest


def decifra_backup(backup_enc_path, dest_path):
    """
    Decifra un backup .db.enc e lo salva in dest_path.
    Usare per ripristino manuale.
    """
    f = _get_or_create_key()
    with open(backup_enc_path, 'rb') as src:
        cifrato = src.read()
    dati = f.decrypt(cifrato)
    with open(dest_path, 'wb') as out:
        out.write(dati)
    return dest_path


def pulisci_vecchi_backup(backup_dir, max_backup=60):
    """Mantieni solo gli ultimi N backup cifrati."""
    files = sorted([
        f for f in os.listdir(backup_dir)
        if f.startswith('database_') and f.endswith('.db.enc')
    ])
    while len(files) > max_backup:
        os.remove(os.path.join(backup_dir, files.pop(0)))
