"""
Notifiche email ai docenti: supplenze del giorno dopo.

Flusso manuale (pagina "Notifiche supplenze" in Bozze email): Caronte
calcola per ogni docente il messaggio con TUTTE le sue supplenze assegnate
per il giorno scelto; Roberto vede l'anteprima e preme Invia. Lo stesso
calcolo potra' essere lanciato da un job pianificato (invio automatico).

Modalita' (impostabile dalla pagina Notifiche supplenze; in mancanza vale la
variabile d'ambiente CARONTE_EMAIL_MODE):
  off       (default) l'anteprima si vede ma non si invia/registra nulla;
  simulato  registra in email_uscita senza inviare;
  reale     invia con modules/gmail_invio.py. Se la lista di prova
            (CARONTE_EMAIL_SOLO_A o impostazione) e' compilata (indirizzi separati da virgola) si invia solo a
            quegli indirizzi: gli altri risultano 'saltata'.

Il nome del docente assente non compare mai (dato potenzialmente sensibile).
Variazioni: se per (docente, giorno) e' gia' stato inviato un messaggio
e l'elenco poi cambia, la proposta diventa "variazione"; se l'elenco
si svuota, "annullamento". Nel testo: data, ora, classe, materia, tipo di ora; mai
nomi di alunni ne' del docente assente. Il testo e' personalizzabile (modello()).
"""
import hashlib
import os
import time
from datetime import date, timedelta

from models import db
from models.docente import Docente
from models.email_uscita import EmailUscita
from models.supplenza import Supplenza

DOMINIO_AMMESSO = '@davincichiavenna.edu.it'
MODALITA_VALIDE = ('off', 'simulato', 'reale')
MAX_PER_INVIO = 80
STATI_INVIATI = ('simulata', 'inviata')

_GIORNI = ['lunedì', 'martedì', 'mercoledì', 'giovedì', 'venerdì', 'sabato', 'domenica']
_TIPI_DA_MOSTRARE = {'disposizione': 'a disposizione', 'potenziamento': 'potenziamento'}


def _config(chiave):
    from models.config_app import ConfigApp
    r = ConfigApp.query.filter_by(chiave=chiave).first()
    return r.valore if r and r.valore is not None else None


def imposta(modalita_nuova, solo_a=''):
    """Salva modalita' e lista di prova nelle impostazioni dell'app."""
    from models.config_app import ConfigApp
    if modalita_nuova not in MODALITA_VALIDE:
        raise ValueError('modalita non valida')
    for chiave, valore in (('email_modalita', modalita_nuova),
                           ('email_solo_a', (solo_a or '').strip())):
        r = ConfigApp.query.filter_by(chiave=chiave).first()
        if r is None:
            db.session.add(ConfigApp(chiave=chiave, valore=valore))
        else:
            r.valore = valore
    db.session.commit()


def modalita():
    """Impostazione salvata in Caronte; in mancanza, CARONTE_EMAIL_MODE; poi 'off'."""
    m = (_config('email_modalita') or os.environ.get('CARONTE_EMAIL_MODE') or 'off')
    m = m.strip().lower()
    return m if m in MODALITA_VALIDE else 'off'


def _solo_a():
    raw = _config('email_solo_a')
    if raw is None:
        raw = os.environ.get('CARONTE_EMAIL_SOLO_A') or ''
    return {x.strip().lower() for x in raw.replace(';', ',').split(',') if x.strip()}


def giorno_default(oggi=None):
    """Prossimo giorno di lezione (lun-sab) dopo oggi: il sabato notifica per lunedi'."""
    g = (oggi or date.today()) + timedelta(days=1)
    while g.weekday() == 6:
        g += timedelta(days=1)
    return g


MODELLO_DEFAULT = {
    'saluto': 'Gentile collega,',
    'apertura': 'ti sono state assegnate le seguenti supplenze per {GIORNO}:',
    'chiusura': ('Messaggio automatico del gestionale supplenze: '
                 'in caso di dubbi contatta la vicepresidenza.'),
}
_CHIAVI_MODELLO = {k: f'email_modello_{k}' for k in MODELLO_DEFAULT}
SEGNAPOSTO = '{GIORNO} {NOME} {COGNOME}'


def modello():
    """Testi del messaggio supplenze: impostazione salvata, altrimenti default."""
    out = {}
    for k, d in MODELLO_DEFAULT.items():
        v = _config(_CHIAVI_MODELLO[k])
        out[k] = v if v and v.strip() else d
    return out


def imposta_modello(saluto, apertura, chiusura):
    """Salva i testi; un campo vuoto ripristina il default."""
    from models.config_app import ConfigApp
    for k, v in (('saluto', saluto), ('apertura', apertura), ('chiusura', chiusura)):
        v = (v or '').strip()[:1000]
        r = ConfigApp.query.filter_by(chiave=_CHIAVI_MODELLO[k]).first()
        if r is None:
            db.session.add(ConfigApp(chiave=_CHIAVI_MODELLO[k], valore=v))
        else:
            r.valore = v
    db.session.commit()


BANCA_ORE_DEFAULT = {
    'oggetto': 'Report banca ore — {MESE}',
    'corpo': ("Gentile prof. {COGNOME},\n\n"
              "in allegato trovi il tuo report individuale della banca ore, "
              "con date e tipologia delle supplenze.\n\n"
              "Ti preghiamo di verificare i dati e di comunicare eventuali "
              "discrepanze alla vicepresidenza.\n\n"
              "Cordiali saluti,\nVicepresidenza"),
}
_CHIAVI_BANCA_ORE = {k: f'email_bo_{k}' for k in BANCA_ORE_DEFAULT}
SEGNAPOSTO_BANCA_ORE = '{COGNOME} {NOME} {EMAIL} {MESE}'


def modello_banca_ore():
    """Oggetto e testo del report banca ore: impostazione salvata, altrimenti default."""
    out = {}
    for k, d in BANCA_ORE_DEFAULT.items():
        v = _config(_CHIAVI_BANCA_ORE[k])
        out[k] = v if v and v.strip() else d
    return out


def imposta_modello_banca_ore(oggetto, corpo):
    """Salva oggetto e testo; un campo vuoto ripristina il default."""
    from models.config_app import ConfigApp
    for k, v, lim in (('oggetto', oggetto, 200), ('corpo', corpo, 4000)):
        v = (v or '').strip()[:lim]
        r = ConfigApp.query.filter_by(chiave=_CHIAVI_BANCA_ORE[k]).first()
        if r is None:
            db.session.add(ConfigApp(chiave=_CHIAVI_BANCA_ORE[k], valore=v))
        else:
            r.valore = v
    db.session.commit()


def _sostituisci_banca_ore(testo, docente, mese):
    return (testo.replace('{COGNOME}', docente.cognome or '')
                 .replace('{NOME}', docente.nome or '')
                 .replace('{EMAIL}', docente.email or '')
                 .replace('{MESE}', f'{mese.month:02d}/{mese.year}'))


def _sostituisci(testo, docente, giorno):
    return (testo.replace('{GIORNO}', _quando(giorno))
                 .replace('{NOME}', docente.nome or '')
                 .replace('{COGNOME}', docente.cognome or ''))


def _etichetta_ora(ora):
    from routes.supplenze import ORA_LABEL
    return ORA_LABEL.get(ora, f'{ora}ª').replace('  ', ' ')


_TIPO_ORA = {'recupero': 'recupero', 'pagamento': 'pagamento',
             'completamento': 'completamento', 'potenziamento': 'potenziamento',
             'disposizione': 'a disposizione'}


def _materia(s):
    """Materia della lezione scoperta, dall'orario del docente assente."""
    if not s.id_assente:
        return None
    from models.orario_docente import OrarioDocente
    q = (OrarioDocente.query
         .filter_by(id_docente=s.id_assente, giorno=s.data.weekday(), ora=s.ora)
         .filter(db.or_(OrarioDocente.data_inizio_validita.is_(None),
                        OrarioDocente.data_inizio_validita <= s.data))
         .filter(db.or_(OrarioDocente.data_fine_validita.is_(None),
                        OrarioDocente.data_fine_validita >= s.data)))
    righe = q.all()
    for r in righe:
        if r.classe == s.classe and r.materia:
            return r.materia
    return next((r.materia for r in righe if r.materia), None)


def _riga(s):
    """Solo dati non sensibili: ora, classe, materia, tipo di ora.
    Il nome del docente assente non compare mai."""
    testo = f'- {_etichetta_ora(s.ora)}'
    if s.classe:
        testo += f', classe {s.classe}'
    materia = _materia(s)
    if materia:
        testo += f', {materia}'
    tipo = _TIPO_ORA.get(s.tipo)
    if tipo:
        testo += f' ({tipo})'
    return testo


def _hash(righe):
    return hashlib.sha1('\n'.join(righe).encode('utf-8')).hexdigest()[:16]


def _quando(giorno):
    return f'{_GIORNI[giorno.weekday()]} {giorno.strftime("%d/%m/%Y")}'


def _saluto(d):
    return f'Gentile {" ".join(x for x in (d.nome, d.cognome) if x)},'


def componi(docente, giorno, righe, variante):
    """Ritorna (oggetto, corpo). variante: nuova | variazione | annullamento."""
    m = modello()
    quando = _quando(giorno)
    saluto = _sostituisci(m['saluto'], docente, giorno)
    firma = ['', _sostituisci(m['chiusura'], docente, giorno)]
    if variante == 'annullamento':
        oggetto = f'ANNULLAMENTO supplenze di {quando}'
        corpo = [saluto, '',
                 f'le supplenze che ti erano state comunicate per {quando} sono state annullate.']
    else:
        prefisso = 'VARIAZIONE supplenze' if variante == 'variazione' else 'Supplenze'
        oggetto = f'{prefisso} di {quando}'
        intro = (f'l\'elenco delle tue supplenze per {quando} è stato aggiornato; '
                 f'questo sostituisce il messaggio precedente:'
                 if variante == 'variazione'
                 else _sostituisci(m['apertura'], docente, giorno))
        corpo = [saluto, '', intro, ''] + righe
    return oggetto, '\n'.join(corpo + firma)


def _ultimo_inviato(id_docente, giorno, tipo='supplenze'):
    return (EmailUscita.query
            .filter_by(tipo=tipo, id_docente=id_docente, giorno=giorno)
            .filter(EmailUscita.stato.in_(STATI_INVIATI))
            .order_by(EmailUscita.id.desc()).first())


def proposte_supplenze(giorno):
    """Una proposta per docente con supplenze assegnate nel giorno, piu'
    i docenti gia' avvisati il cui elenco ora e' vuoto (annullamento)."""
    supp = (Supplenza.query
            .filter(Supplenza.data == giorno, Supplenza.stato == 'assegnata',
                    Supplenza.id_sostituto.isnot(None))
            .order_by(Supplenza.ora).all())
    per_doc = {}
    for s in supp:
        per_doc.setdefault(s.id_sostituto, []).append(s)

    gia = (db.session.query(EmailUscita.id_docente)
           .filter_by(tipo='supplenze', giorno=giorno)
           .filter(EmailUscita.stato.in_(STATI_INVIATI)).distinct().all())
    ids = set(per_doc) | {r[0] for r in gia if r[0]}
    if not ids:
        return []
    docenti = {d.id: d for d in Docente.query.filter(Docente.id.in_(ids)).all()}

    out = []
    for id_doc in ids:
        d = docenti.get(id_doc)
        if d is None:
            continue
        righe = [_riga(s) for s in per_doc.get(id_doc, [])]
        h = _hash(righe)
        prec = _ultimo_inviato(id_doc, giorno)
        if prec is None:
            if not righe:
                continue
            variante = 'nuova'
        elif prec.hash_contenuto == h:
            variante = 'gia_inviata'
        else:
            variante = 'annullamento' if not righe else 'variazione'
        oggetto, corpo = componi(d, giorno, righe, 'nuova' if variante == 'gia_inviata' else variante)
        email = (d.email or '').strip().lower()
        blocco = None
        if not email:
            blocco = 'email mancante'
        elif not email.endswith(DOMINIO_AMMESSO):
            blocco = 'indirizzo fuori dominio'
        out.append(dict(docente=d, email=email, righe=righe, variante=variante,
                        oggetto=oggetto, corpo=corpo, hash=h, blocco=blocco))
    out.sort(key=lambda p: (p['docente'].cognome or '', p['docente'].nome or ''))
    return out


def _registra(p, giorno, stato, dettaglio=None, tipo='supplenze'):
    db.session.add(EmailUscita(
        tipo=tipo, giorno=giorno, hash_contenuto=p['hash'],
        chiave=f'{tipo}:{p["docente"].id}:{giorno.isoformat()}:{p["hash"]}:{time.time_ns()}',
        id_docente=p['docente'].id, destinatario=p['email'],
        oggetto=p['oggetto'], corpo=p['corpo'], stato=stato, dettaglio=dettaglio))
    db.session.commit()


def invia_supplenze(giorno, ids_docenti, mittente=None):
    """Invia/registra le proposte selezionate. Ricalcola tutto dal DB (non
    si fida del contenuto della form). Ritorna lista di (cognome, stato, dettaglio)."""
    mod = modalita()
    if mod == 'off':
        return [('—', 'errore', 'invio disattivato (CARONTE_EMAIL_MODE=off)')]
    if giorno < date.today():
        return [('—', 'errore', 'il giorno scelto è passato')]
    scelti = {int(i) for i in ids_docenti}
    risultati = []
    solo_a = _solo_a()
    for p in proposte_supplenze(giorno):
        if p['docente'].id not in scelti:
            continue
        if len(risultati) >= MAX_PER_INVIO:
            risultati.append(('—', 'errore', f'tetto di {MAX_PER_INVIO} messaggi per invio'))
            break
        nome = p['docente'].cognome
        if p['variante'] == 'gia_inviata':
            risultati.append((nome, 'saltata', 'già inviata'))
            continue
        if p['blocco']:
            _registra(p, giorno, 'saltata', p['blocco'])
            risultati.append((nome, 'saltata', p['blocco']))
            continue
        if mod == 'simulato':
            _registra(p, giorno, 'simulata')
            risultati.append((nome, 'simulata', None))
            continue
        if solo_a and p['email'] not in solo_a:
            _registra(p, giorno, 'saltata', 'fuori lista di prova')
            risultati.append((nome, 'saltata', 'fuori lista di prova'))
            continue
        try:
            from modules.gmail_invio import invia
            invia(p['email'], p['oggetto'], p['corpo'])
        except Exception as e:  # esito registrato, la proposta resta reinviabile
            db.session.rollback()
            _registra(p, giorno, 'errore', str(e)[:240])
            risultati.append((nome, 'errore', str(e)[:120]))
            continue
        _registra(p, giorno, 'inviata')
        risultati.append((nome, 'inviata', None))
    return risultati


# ── Report banca ore (mensile, tutti i docenti) ───────────────
def primo_del_mese(oggi=None):
    o = oggi or date.today()
    return o.replace(day=1)


def _saldi_testo(saldi):
    lordo = saldi['supplenze'] - saldi['permessi'] - saldi['civica']
    netto = lordo - saldi['pagamento']
    righe = [
        f'- Supplenze svolte: {saldi["supplenze"]} h',
        f'- Permessi orari: -{saldi["permessi"]} h',
        f'- Ed. Civica: -{saldi["civica"]} h',
        f'- Ore a pagamento: -{saldi["pagamento"]} h',
        f'- Saldo lordo: {lordo} h',
        f'- Saldo netto: {netto} h',
    ]
    return righe


def proposte_banca_ore(mese):
    """Una proposta per ogni docente attivo, mese = primo giorno del mese.
    Un solo invio per mese; se i saldi cambiano si propone un aggiornamento."""
    from routes.report import get_saldi_docente
    mod = modello_banca_ore()
    out = []
    for d in Docente.query.filter_by(attivo=True).order_by(Docente.cognome, Docente.nome).all():
        saldi = get_saldi_docente(d.id)
        righe = _saldi_testo(saldi)
        h = _hash(righe)
        prec = _ultimo_inviato(d.id, mese, 'banca_ore')
        variante = 'nuova' if prec is None else ('gia_inviata' if prec.hash_contenuto == h else 'aggiornamento')
        agg = 'AGGIORNAMENTO ' if variante == 'aggiornamento' else ''
        oggetto = agg + _sostituisci_banca_ore(mod['oggetto'], d, mese)
        corpo = _sostituisci_banca_ore(mod['corpo'], d, mese)
        email = (d.email or '').strip().lower()
        blocco = None
        if not email:
            blocco = 'email mancante'
        elif not email.endswith(DOMINIO_AMMESSO):
            blocco = 'indirizzo fuori dominio'
        out.append(dict(docente=d, email=email, righe=righe, variante=variante,
                        oggetto=oggetto, corpo=corpo, hash=h, blocco=blocco))
    return out


def _pdf_banca_ore(docente):
    from routes.mail_bozze import _genera_pdf_bytes
    return _genera_pdf_bytes(docente)


class _AllegatiParziali(Exception):
    """Un allegato non si e' potuto creare: si invia comunque con quelli riusciti."""
    def __init__(self, allegati):
        super().__init__('allegati parziali')
        self.allegati = allegati


def _invia_con_pdf(proposte, ids_docenti, periodo, tipo, allegati_fn, messaggio_gia_inviata):
    """Invio comune ai messaggi con allegati per docente (banca ore, orario, calendario).
    allegati_fn(docente) -> lista di (nome_file, bytes).
    Rispetta modalita', lista di prova, tetto e anti-duplicato; un errore resta riinviabile."""
    mod = modalita()
    if mod == 'off':
        return [('—', 'errore', 'invio disattivato')]
    scelti = {int(i) for i in ids_docenti}
    solo_a = _solo_a()
    risultati = []
    for p in proposte:
        if p['docente'].id not in scelti:
            continue
        if len(risultati) >= MAX_PER_INVIO:
            risultati.append(('—', 'errore', f'tetto di {MAX_PER_INVIO} messaggi per invio'))
            break
        nome = p['docente'].cognome
        if p['variante'] == 'gia_inviata':
            risultati.append((nome, 'saltata', messaggio_gia_inviata))
            continue
        if p['blocco']:
            _registra(p, periodo, 'saltata', p['blocco'], tipo)
            risultati.append((nome, 'saltata', p['blocco']))
            continue
        if mod == 'simulato':
            _registra(p, periodo, 'simulata', None, tipo)
            risultati.append((nome, 'simulata', None))
            continue
        if solo_a and p['email'] not in solo_a:
            _registra(p, periodo, 'saltata', 'fuori lista di prova', tipo)
            risultati.append((nome, 'saltata', 'fuori lista di prova'))
            continue
        note = None
        try:
            allegati = []
            try:
                allegati = allegati_fn(p['docente'])
            except _AllegatiParziali as parz:
                allegati, note = parz.allegati, 'inviato senza PDF'
            except Exception:
                note = 'inviato senza PDF'
            from modules.gmail_invio import invia
            invia(p['email'], p['oggetto'], p['corpo'], allegati)
        except Exception as e:
            db.session.rollback()
            _registra(p, periodo, 'errore', str(e)[:240], tipo)
            risultati.append((nome, 'errore', str(e)[:120]))
            continue
        _registra(p, periodo, 'inviata', note, tipo)
        risultati.append((nome, 'inviata', note))
    return risultati


def invia_banca_ore(mese, ids_docenti, oggetto=None, corpo=None):
    """Se oggetto/corpo sono passati dalla pagina, diventano il modello salvato."""
    if oggetto is not None or corpo is not None:
        imposta_modello_banca_ore(oggetto, corpo)
    if modalita() == 'off':
        return [('—', 'errore', 'invio disattivato')]
    return _invia_con_pdf(proposte_banca_ore(mese), ids_docenti, mese, 'banca_ore',
                          lambda d: [(f'Banca_ore_{d.cognome}.pdf', _pdf_banca_ore(d))],
                          'già inviato questo mese')


# ── ORARIO DEI DOCENTI (invio una tantum a ogni nuova versione) ──
ORARIO_DEFAULT = {
    'oggetto': 'Il tuo orario delle lezioni — valido dal {DATA}',
    'corpo': ("Gentile prof. {COGNOME},\n\n"
              "in allegato trovi il tuo orario settimanale delle lezioni, valido dal {DATA}.\n\n"
              "Se noti errori o sovrapposizioni, scrivi alla vicepresidenza.\n\n"
              "Cordiali saluti,\nVicepresidenza"),
}
_CHIAVI_ORARIO = {k: f'email_orario_{k}' for k in ORARIO_DEFAULT}
SEGNAPOSTO_ORARIO = '{COGNOME} {NOME} {EMAIL} {DATA}'


def modello_orario():
    out = {}
    for k, d in ORARIO_DEFAULT.items():
        v = _config(_CHIAVI_ORARIO[k])
        out[k] = v if v and v.strip() else d
    return out


def imposta_modello_orario(oggetto, corpo):
    from models.config_app import ConfigApp
    for k, v, lim in (('oggetto', oggetto, 200), ('corpo', corpo, 4000)):
        v = (v or '').strip()[:lim]
        r = ConfigApp.query.filter_by(chiave=_CHIAVI_ORARIO[k]).first()
        if r is None:
            db.session.add(ConfigApp(chiave=_CHIAVI_ORARIO[k], valore=v))
        else:
            r.valore = v
    db.session.commit()


def _sostituisci_orario(testo, docente, valido_dal):
    return (testo.replace('{COGNOME}', docente.cognome or '')
                 .replace('{NOME}', docente.nome or '')
                 .replace('{EMAIL}', docente.email or '')
                 .replace('{DATA}', valido_dal.strftime('%d/%m/%Y')))


def valido_dal_default():
    """Inizio di validita' dell'orario caricato, se noto; altrimenti oggi."""
    from models.orario_docente import validita_orario_corrente
    ini, _ = validita_orario_corrente()
    return ini or date.today()


def _righe_orario(id_docente):
    from models.orario_docente import OrarioDocente
    righe = []
    for s in (OrarioDocente.query.filter_by(id_docente=id_docente)
              .order_by(OrarioDocente.giorno, OrarioDocente.ora).all()):
        if s.classe and s.classe not in ('---', '-x-', ''):
            righe.append(f'{s.giorno}-{s.ora}-{s.classe}-{s.materia or ""}')
    return righe


def proposte_orario(valido_dal):
    """Una proposta per ogni docente attivo. Chiave di versione = data 'valido dal';
    stessa data e stesso orario = gia' inviato; stessa data ma orario diverso = aggiornamento."""
    mod = modello_orario()
    out = []
    for d in Docente.query.filter_by(attivo=True).order_by(Docente.cognome, Docente.nome).all():
        righe = _righe_orario(d.id)
        h = _hash(righe)
        prec = _ultimo_inviato(d.id, valido_dal, 'orario')
        variante = 'nuova' if prec is None else ('gia_inviata' if prec.hash_contenuto == h else 'aggiornamento')
        agg = 'AGGIORNAMENTO ' if variante == 'aggiornamento' else ''
        oggetto = agg + _sostituisci_orario(mod['oggetto'], d, valido_dal)
        corpo = _sostituisci_orario(mod['corpo'], d, valido_dal)
        email = (d.email or '').strip().lower()
        blocco = None
        if not righe:
            blocco = 'orario non caricato'
        elif not email:
            blocco = 'email mancante'
        elif not email.endswith(DOMINIO_AMMESSO):
            blocco = 'indirizzo fuori dominio'
        out.append(dict(docente=d, email=email, righe=righe, variante=variante,
                        oggetto=oggetto, corpo=corpo, hash=h, blocco=blocco))
    return out


def invia_orario(valido_dal, ids_docenti, oggetto=None, corpo=None):
    if oggetto is not None or corpo is not None:
        imposta_modello_orario(oggetto, corpo)
    if modalita() == 'off':
        return [('—', 'errore', 'invio disattivato')]
    from routes.report import orario_pdf_bytes
    return _invia_con_pdf(proposte_orario(valido_dal), ids_docenti, valido_dal, 'orario',
                          lambda d: [(f'Orario_{d.cognome}.pdf', orario_pdf_bytes(d, valido_dal))],
                          'già inviato per questa versione')


# ── CALENDARIO MENSILE DEGLI IMPEGNI (PDF agenda + file .ics) ─────
CALENDARIO_DEFAULT = {
    'oggetto': 'I tuoi impegni di {MESE} — promemoria',
    'corpo': ("Gentile prof. {COGNOME},\n\n"
              "in allegato trovi il calendario dei tuoi impegni di {MESE}: il PDF da consultare o "
              "stampare e il file .ics da importare nel tuo calendario (Google, Outlook, Apple).\n\n"
              "È un promemoria: fanno fede le circolari pubblicate sul registro elettronico. "
              "Se gli impegni cambiano dopo questo invio, riceverai un aggiornamento.\n\n"
              "Cordiali saluti,\nVicepresidenza"),
}
_CHIAVI_CALENDARIO = {k: f'email_cal_{k}' for k in CALENDARIO_DEFAULT}
SEGNAPOSTO_CALENDARIO = '{COGNOME} {NOME} {EMAIL} {MESE}'


def modello_calendario():
    out = {}
    for k, d in CALENDARIO_DEFAULT.items():
        v = _config(_CHIAVI_CALENDARIO[k])
        out[k] = v if v and v.strip() else d
    return out


def imposta_modello_calendario(oggetto, corpo):
    from models.config_app import ConfigApp
    for k, v, lim in (('oggetto', oggetto, 200), ('corpo', corpo, 4000)):
        v = (v or '').strip()[:lim]
        r = ConfigApp.query.filter_by(chiave=_CHIAVI_CALENDARIO[k]).first()
        if r is None:
            db.session.add(ConfigApp(chiave=_CHIAVI_CALENDARIO[k], valore=v))
        else:
            r.valore = v
    db.session.commit()


def mese_calendario_default(oggi=None):
    """Dal 15 del mese si propone il mese dopo, prima il mese in corso."""
    oggi = oggi or date.today()
    if oggi.day >= 15:
        return (oggi.replace(day=1) + timedelta(days=32)).replace(day=1)
    return oggi.replace(day=1)


def _sostituisci_calendario(testo, docente, mese):
    from modules.calendario_agenda import nome_mese
    return (testo.replace('{COGNOME}', docente.cognome or '')
                 .replace('{NOME}', docente.nome or '')
                 .replace('{EMAIL}', docente.email or '')
                 .replace('{MESE}', nome_mese(mese)))


def proposte_calendario(mese):
    """Una proposta per ogni docente attivo con almeno un impegno nel mese.
    Un invio per mese; se gli impegni cambiano dopo l'invio, AGGIORNAMENTO."""
    from modules.calendario_agenda import impegni_mese_tutti
    mod = modello_calendario()
    tutti = impegni_mese_tutti(mese)
    out = []
    for d in Docente.query.filter_by(attivo=True).order_by(Docente.cognome, Docente.nome).all():
        imp = tutti.get(d.id, [])
        righe = [f"{e['data']}|{e['ora_inizio']}|{e['ora_fine']}|{e['titolo']}|{e['classe']}" for e in imp]
        h = _hash(righe)
        prec = _ultimo_inviato(d.id, mese, 'calendario')
        variante = 'nuova' if prec is None else ('gia_inviata' if prec.hash_contenuto == h else 'aggiornamento')
        agg = 'AGGIORNAMENTO ' if variante == 'aggiornamento' else ''
        oggetto = agg + _sostituisci_calendario(mod['oggetto'], d, mese)
        corpo = _sostituisci_calendario(mod['corpo'], d, mese)
        email = (d.email or '').strip().lower()
        blocco = None
        if not imp:
            blocco = 'nessun impegno nel mese'
        elif not email:
            blocco = 'email mancante'
        elif not email.endswith(DOMINIO_AMMESSO):
            blocco = 'indirizzo fuori dominio'
        out.append(dict(docente=d, email=email, righe=righe, variante=variante, n_impegni=len(imp),
                        oggetto=oggetto, corpo=corpo, hash=h, blocco=blocco))
    return out


def invia_calendario(mese, ids_docenti, oggetto=None, corpo=None):
    if oggetto is not None or corpo is not None:
        imposta_modello_calendario(oggetto, corpo)
    if modalita() == 'off':
        return [('—', 'errore', 'invio disattivato')]
    from modules.calendario_agenda import agenda_pdf_bytes, ics_mese, impegni_mese

    def allegati(d):
        imp = impegni_mese(d, mese)
        base = f'Impegni_{mese.year}-{mese.month:02d}_{d.cognome}'
        lista = [(f'{base}.ics', ics_mese(d, mese, imp))]
        try:
            lista.insert(0, (f'{base}.pdf', agenda_pdf_bytes(d, mese, imp)))
        except Exception:
            raise _AllegatiParziali(lista)   # il file .ics parte comunque
        return lista

    return _invia_con_pdf(proposte_calendario(mese), ids_docenti, mese, 'calendario',
                          allegati, 'già inviato per questo mese')
