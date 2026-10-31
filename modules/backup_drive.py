"""modules/backup_drive.py — copia dei backup cifrati nella cartella locale di
Google Drive Desktop (CaronteApp/Backup), senza API né token.

Si aggancia a `crea_backup_cifrato`: dopo ogni backup locale, la stessa copia
(già cifrata) viene duplicata su Drive. Non sostituisce la copia locale e non
solleva mai errori: se Drive non c'è o la copia fallisce, il backup locale
resta valido e si scrive solo un avviso nel log.

Spento nei test (PYTEST_CURRENT_TEST) e con CARONTE_BACKUP_DRIVE=0.
"""
import logging
import os
import re
import shutil
from pathlib import Path

log = logging.getLogger(__name__)

SOTTOCARTELLA = 'Backup'
ULTIMI_DA_TENERE = 14           # i più recenti, comunque
UNO_AL_MESE = True              # più il più recente di ogni mese
_NOME = re.compile(r'^database_(\d{4})(\d{2})(\d{2})_(\d{4})')


def attivo():
    return (os.environ.get('CARONTE_BACKUP_DRIVE', '1') != '0'
            and 'PYTEST_CURRENT_TEST' not in os.environ)


def cartella_backup_drive():
    """Cartella Drive/CaronteApp/Backup, o None se Drive non c'è."""
    from sync_db import cartella_drive
    base = cartella_drive()
    if not base:
        return None
    dest = Path(base) / SOTTOCARTELLA
    dest.mkdir(parents=True, exist_ok=True)
    return dest


def da_conservare(nomi, ultimi=ULTIMI_DA_TENERE, uno_al_mese=UNO_AL_MESE):
    """Nomi da tenere: gli ultimi N e il più recente di ogni mese. I file
    il cui nome non segue il modello database_AAAAMMGG_HHMM... non si toccano."""
    datati = sorted(n for n in nomi if _NOME.match(n))
    tenere = set(datati[-ultimi:])
    if uno_al_mese:
        per_mese = {}
        for n in datati:
            m = _NOME.match(n)
            per_mese[(m.group(1), m.group(2))] = n   # l'ultimo del mese vince
        tenere.update(per_mese.values())
    return tenere | {n for n in nomi if not _NOME.match(n)}


def pulisci(cartella, **kw):
    nomi = [n for n in os.listdir(cartella) if n.endswith('.db.enc')]
    tenere = da_conservare(nomi, **kw)
    rimossi = []
    for n in nomi:
        if n not in tenere:
            try:
                os.remove(os.path.join(cartella, n))
                rimossi.append(n)
            except OSError as e:
                log.warning('Backup Drive: impossibile rimuovere %s: %s', n, e)
    return rimossi


def copia_su_drive(backup_path):
    """Copia il backup cifrato su Drive. Ritorna il path creato o None."""
    if not attivo():
        return None
    try:
        cartella = cartella_backup_drive()
        if not cartella:
            log.warning('Backup Drive: Google Drive non trovato, copia saltata.')
            return None
        dest = cartella / os.path.basename(backup_path)
        shutil.copyfile(backup_path, dest)
        pulisci(cartella)
        return str(dest)
    except Exception as e:  # il backup locale resta valido
        log.warning('Backup Drive: copia fallita (%s).', e)
        return None
