"""modules/orario_da_drive.py — copia dell'orario (globale e sostegno) dal
database pubblicato su Drive dall'altra postazione.

L'orario non entra nell'autosync: l'import lo sostituisce per intero, e un
merge riga per riga mescolerebbe orari vecchi e nuovi. Qui la sostituzione è
esplicita: anteprima del confronto, backup cifrato, poi le tabelle locali
vengono rimpiazzate dal contenuto del file su Drive.

`confronta()` è sola lettura; `applica()` scrive (senza commit).
"""
import hashlib
import json
import sqlite3

from sqlalchemy import text

# tabella -> colonne di contenuto (senza id) e colonna che identifica il titolare
TABELLE = {
    'orario_docenti': {
        'colonne': ('id_docente', 'giorno', 'ora', 'classe', 'materia', 'tipo_ora',
                    'data_inizio_validita', 'data_fine_validita'),
        'titolare': 'id_docente', 'etichetta': 'Orario globale'},
    'orario_sostegno': {
        'colonne': ('id_docente', 'giorno', 'ora', 'classe', 'note'),
        'titolare': 'id_docente', 'etichetta': 'Orario di sostegno'},
    'orario_placeholder': {
        'colonne': ('nome_file', 'giorno', 'ora', 'classe', 'materia', 'tipo_ora',
                    'data_inizio_validita', 'data_fine_validita'),
        'titolare': 'nome_file', 'etichetta': 'Posti vacanti (orario)'},
}
GIORNI = ['lun', 'mar', 'mer', 'gio', 'ven', 'sab']


class RemotoSenzaOrario(ValueError):
    """Il file su Drive non contiene un orario utilizzabile."""


def _righe_remote(conn, tabella, colonne):
    """Righe del remoto come tuple (None se la tabella non esiste: file
    pubblicato da una versione più vecchia del codice)."""
    esistenti = {r[1] for r in conn.execute(f'PRAGMA table_info({tabella})')}
    if not esistenti:
        return None
    sel = ', '.join(c if c in esistenti else 'NULL' for c in colonne)
    return [tuple(r) for r in conn.execute(f'SELECT {sel} FROM {tabella}')]


def _righe_locali(db, tabella, colonne):
    return [tuple(r) for r in db.session.execute(
        text(f"SELECT {', '.join(colonne)} FROM {tabella}"))]


def _leggi_remoto(remoto_path):
    conn = sqlite3.connect(remoto_path)
    try:
        return {t: _righe_remote(conn, t, cfg['colonne']) for t, cfg in TABELLE.items()}
    finally:
        conn.close()


def _id_docenti(db):
    return {r[0] for r in db.session.execute(text('SELECT id FROM docenti'))}


def _nomi_docenti(db):
    return {r[0]: f'{r[1]} {r[2] or ""}'.strip()
            for r in db.session.execute(text('SELECT id, cognome, nome FROM docenti'))}


def _utilizzabili(cfg, righe, docenti_ok):
    """Separa le righe applicabili da quelle con docente inesistente in locale."""
    i = cfg['colonne'].index(cfg['titolare'])
    if cfg['titolare'] != 'id_docente':
        return list(righe), []
    buone = [r for r in righe if r[i] in docenti_ok]
    return buone, [r for r in righe if r[i] not in docenti_ok]


def impronta(remote):
    """Identifica il contenuto del remoto: l'anteprima e l'applicazione devono
    guardare gli stessi dati."""
    blob = json.dumps({t: sorted(map(repr, r or [])) for t, r in sorted(remote.items())})
    return hashlib.sha1(blob.encode()).hexdigest()


def confronta(db, remoto_path):
    """Differenze per tabella (aggiunte/rimosse, con il titolare)."""
    remote = _leggi_remoto(remoto_path)
    docenti_ok, nomi = _id_docenti(db), _nomi_docenti(db)
    esito = {'impronta': impronta(remote), 'tabelle': [], 'applicabile': True,
             'motivo': None}
    for tabella, cfg in TABELLE.items():
        righe_r = remote[tabella]
        if righe_r is None:
            esito['tabelle'].append({'nome': tabella, 'etichetta': cfg['etichetta'],
                                     'assente': True})
            continue
        buone, saltate = _utilizzabili(cfg, righe_r, docenti_ok)
        locali = _righe_locali(db, tabella, cfg['colonne'])
        s_loc, s_rem = set(locali), set(buone)
        i = cfg['colonne'].index(cfg['titolare'])
        per_titolare = {}
        for segno, righe in (('+', s_rem - s_loc), ('-', s_loc - s_rem)):
            for r in righe:
                t = nomi.get(r[i], f'#{r[i]}') if cfg['titolare'] == 'id_docente' else r[i]
                per_titolare.setdefault(t, {'+': 0, '-': 0})[segno] += 1
        esito['tabelle'].append({
            'nome': tabella, 'etichetta': cfg['etichetta'], 'assente': False,
            'locali': len(locali), 'remote': len(buone), 'saltate': len(saltate),
            'aggiunte': len(s_rem - s_loc), 'rimosse': len(s_loc - s_rem),
            'per_titolare': sorted(per_titolare.items()),
        })
    r_doc = remote['orario_docenti']
    if not r_doc:
        esito['applicabile'] = False
        esito['motivo'] = ("Il file su Drive non contiene un orario globale: "
                           "non lo copio per non cancellare quello di qui.")
    return esito


def applica(db, remoto_path, impronta_attesa):
    """Sostituisce le tabelle dell'orario con quelle del remoto. Non fa commit.
    Ritorna {tabella: righe scritte}. Solleva RemotoSenzaOrario se il file non
    ha un orario globale o se è cambiato dopo l'anteprima."""
    remote = _leggi_remoto(remoto_path)
    if not remote['orario_docenti']:
        raise RemotoSenzaOrario('Il file su Drive non contiene un orario globale.')
    if impronta(remote) != impronta_attesa:
        raise RemotoSenzaOrario('Il file su Drive è cambiato dopo l\'anteprima: ricontrolla.')
    docenti_ok = _id_docenti(db)
    scritte = {}
    for tabella, cfg in TABELLE.items():
        righe = remote[tabella]
        if righe is None:
            continue  # il remoto non ha la tabella: la lascio com'è
        buone, _ = _utilizzabili(cfg, righe, docenti_ok)
        cols = cfg['colonne']
        db.session.execute(text(f'DELETE FROM {tabella}'))
        for r in buone:
            db.session.execute(
                text(f"INSERT INTO {tabella} ({', '.join(cols)}) "
                     f"VALUES ({', '.join(':' + c for c in cols)})"),
                dict(zip(cols, r)))
        scritte[tabella] = len(buone)
    return scritte
