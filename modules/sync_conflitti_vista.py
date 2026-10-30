"""modules/sync_conflitti_vista.py — rende leggibile la pagina /sync/conflitti.

Nei conflitti salvati (models/sync_conflitto.py) le righe sono dizionari
grezzi: id del docente, date ISO, 0/1 per i booleani. Qui si traducono in
nomi e testo comprensibile. Solo lettura: non scrive nulla.

Gli id dei docenti si risolvono sul database locale: il sync suppone gia'
(vedi i controlli FK in modules/auto_sync.py) che gli id dei docenti siano
gli stessi sulle due postazioni.
"""
import json
from datetime import date, datetime

from models import db

GIORNI = ['lun', 'mar', 'mer', 'gio', 'ven', 'sab', 'dom']

CAMPI_DOCENTE = {'id_docente', 'id_assente', 'id_sostituto'}
CAMPI_DATA = {'data', 'data_nomina'}
CAMPI_ORARIO = {'creato_il', 'modificato_il'}
CAMPI_BOOL = {'classe_libera'}
CAMPI_ORA_ISTITUZIONALE = {'ora_ist_inizio', 'ora_ist_fine'}


def _data(v):
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    try:
        return date.fromisoformat(str(v)[:10])
    except (TypeError, ValueError):
        return None


def _data_it(v):
    d = _data(v)
    return f'{GIORNI[d.weekday()]} {d.strftime("%d/%m/%Y")}' if d else (str(v) if v else '—')


def _datetime_it(v):
    if not v:
        return None
    try:
        return datetime.fromisoformat(str(v).replace(' ', 'T', 1)).strftime('%d/%m/%Y %H:%M')
    except ValueError:
        return str(v)


def carica_nomi_docenti(ids):
    """{id: 'COGNOME Nome'} per gli id richiesti (ignora None / non numerici)."""
    puliti = set()
    for i in ids:
        try:
            if i is not None:
                puliti.add(int(i))
        except (TypeError, ValueError):
            continue
    if not puliti:
        return {}
    from models.docente import Docente
    return {d.id: f'{(d.cognome or "").upper()} {d.nome or ""}'.strip()
            for d in Docente.query.filter(Docente.id.in_(puliti)).all()}


def _nome(nomi, i):
    if i is None or i == '':
        return 'nessuno'
    try:
        return nomi.get(int(i), f'docente #{i} (non in anagrafica qui)')
    except (TypeError, ValueError):
        return str(i)


def valore_leggibile(campo, valore, nomi):
    """Testo da mostrare per il valore di un campo (None -> '—')."""
    if campo in CAMPI_DOCENTE:
        return _nome(nomi, valore)
    if valore is None or valore == '':
        return '—'
    if campo in CAMPI_BOOL:
        return 'Sì' if str(valore).lower() in ('1', 'true') else 'No'
    if campo in CAMPI_DATA:
        return _data_it(valore)
    if campo in CAMPI_ORARIO:
        return _datetime_it(valore) or '—'
    if campo in ('stato', 'tipo', 'origine'):
        return str(valore).replace('_', ' ')
    return str(valore)


def _ore(r):
    a, b = r.get('ora_inizio'), r.get('ora_fine')
    if a is None:
        return '—'
    return f'{a}ª ora' if a == b or b is None else f'dalla {a}ª alla {b}ª ora'


def contesto_e_titolo(tabella, riga, nomi):
    """(titolo, [(etichetta, valore), ...]) con le informazioni che
    identificano la riga, indipendenti da cosa differisce."""
    if tabella == 'assenze':
        chi = _nome(nomi, riga.get('id_docente'))
        return (f'Assenza di {chi} — {_data_it(riga.get("data"))}',
                [('Docente', chi), ('Data', _data_it(riga.get('data'))), ('Ore', _ore(riga))])
    if tabella == 'indisponibilita':
        chi = _nome(nomi, riga.get('id_docente'))
        ora = riga.get('ora')
        quando = 'tutta la giornata' if ora is None else f'{ora}ª ora'
        return (f'Indisponibilità di {chi} — {_data_it(riga.get("data"))}',
                [('Docente', chi), ('Data', _data_it(riga.get('data'))), ('Quando', quando)])
    if tabella == 'supplenze':
        assente = _nome(nomi, riga.get('id_assente'))
        return (f'Supplenza per {assente} — {_data_it(riga.get("data"))}, '
                f'{riga.get("ora")}ª ora, classe {riga.get("classe") or "—"}',
                [('Docente assente', assente), ('Data', _data_it(riga.get('data'))),
                 ('Ora', f'{riga.get("ora")}ª'), ('Classe', riga.get('classe') or '—')])
    if tabella == 'sostituzioni_scrutinio':
        from models.attivita_ist import AttivitaIst
        assente = _nome(nomi, riga.get('id_assente'))
        evento = None
        try:
            evento = db.session.get(AttivitaIst, int(riga.get('id_attivita')))
        except (TypeError, ValueError):
            pass
        nome_evento = (f'{evento.titolo} — {_data_it(evento.data)}' if evento
                       else f'evento #{riga.get("id_attivita")}')
        return (f'Sostituto di {assente} allo scrutinio ({nome_evento})',
                [('Docente assente', assente), ('Evento', nome_evento)])
    if tabella == 'docenti':
        nome = f'{riga.get("cognome", "")} {riga.get("nome", "")}'.strip()
        return (f'Anagrafica di {nome}', [('Docente', nome)])
    return (riga.get('descrizione') or tabella, [])


def _meta_riga(riga):
    """Ultima modifica / inserimento / autore di una delle due versioni."""
    parti = []
    mod = _datetime_it(riga.get('modificato_il'))
    cre = _datetime_it(riga.get('creato_il'))
    if mod:
        parti.append(f'modificata il {mod}')
    elif cre:
        parti.append(f'inserita il {cre}')
    if riga.get('creato_da'):
        parti.append(f'da {riga["creato_da"]}')
    return ' · '.join(parti)


def prepara_conflitti(conflitti, campo_label, tabella_label):
    """Lista di dict pronti per il template, a partire dai SyncConflitto."""
    caricati = []
    ids = set()
    for c in conflitti:
        chiave = json.loads(c.chiave_logica) if c.chiave_logica else {}
        locale = {**chiave, **(json.loads(c.dati_locali) if c.dati_locali else {})}
        remoto = {**chiave, **(json.loads(c.dati_remoti) if c.dati_remoti else {})}
        caricati.append((c, locale, remoto))
        for r in (locale, remoto):
            for campo in CAMPI_DOCENTE:
                ids.add(r.get(campo))
    nomi = carica_nomi_docenti(ids)

    vista = []
    for c, locale, remoto in caricati:
        diversi = json.loads(c.campi_diversi) if c.campi_diversi else []
        titolo, contesto = contesto_e_titolo(c.tabella, locale, nomi)
        confronto = [{
            'label': campo_label.get(campo, campo),
            'locale': valore_leggibile(campo, locale.get(campo), nomi),
            'remoto': valore_leggibile(campo, remoto.get(campo), nomi),
        } for campo in diversi]
        vista.append({
            'id': c.id,
            'tabella': c.tabella,
            'tabella_label': tabella_label.get(c.tabella, c.tabella),
            'titolo': titolo,
            'contesto': contesto,
            'confronto': confronto,
            'meta_locale': _meta_riga(locale),
            'meta_remoto': _meta_riga(remoto),
            'rilevato_il': c.rilevato_il,
            'aggiornato_il': c.aggiornato_il,
        })
    return vista
