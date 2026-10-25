"""
Notifiche email ai docenti: supplenze del giorno dopo.

Flusso manuale (pagina "Notifiche supplenze" in Bozze email): Caronte
calcola per ogni docente il messaggio con TUTTE le sue supplenze assegnate
per il giorno scelto; Roberto vede l'anteprima e preme Invia. Lo stesso
calcolo potra' essere lanciato da un job pianificato (invio automatico).

Modalita', da variabile d'ambiente CARONTE_EMAIL_MODE:
  off       (default) l'anteprima si vede ma non si invia/registra nulla;
  simulato  registra in email_uscita senza inviare;
  reale     invia con modules/gmail_invio.py. Se CARONTE_EMAIL_SOLO_A e'
            impostata (indirizzi separati da virgola) si invia solo a
            quegli indirizzi: gli altri risultano 'saltata'.

Variazioni: se per (docente, giorno) e' gia' stato inviato un messaggio
e l'elenco poi cambia, la proposta diventa "variazione"; se l'elenco
si svuota, "annullamento". Nel testo: data, ora, classe, assente; mai
nomi di alunni.
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


def modalita():
    m = (os.environ.get('CARONTE_EMAIL_MODE') or 'off').strip().lower()
    return m if m in MODALITA_VALIDE else 'off'


def _solo_a():
    raw = os.environ.get('CARONTE_EMAIL_SOLO_A') or ''
    return {x.strip().lower() for x in raw.split(',') if x.strip()}


def giorno_default(oggi=None):
    """Prossimo giorno feriale (lun-ven) dopo oggi."""
    g = (oggi or date.today()) + timedelta(days=1)
    while g.weekday() >= 5:
        g += timedelta(days=1)
    return g


def _etichetta_ora(ora):
    from routes.supplenze import ORA_LABEL
    return ORA_LABEL.get(ora, f'{ora}ª').replace('  ', ' ')


def _riga(s, assenti):
    testo = f'- {_etichetta_ora(s.ora)}'
    if s.classe:
        testo += f', classe {s.classe}'
    ass = assenti.get(s.id_assente)
    if ass is not None:
        testo += f' (in sostituzione di {ass.cognome})'
    extra = _TIPI_DA_MOSTRARE.get(s.tipo)
    if extra:
        testo += f' [{extra}]'
    return testo


def _hash(righe):
    return hashlib.sha1('\n'.join(righe).encode('utf-8')).hexdigest()[:16]


def _quando(giorno):
    return f'{_GIORNI[giorno.weekday()]} {giorno.strftime("%d/%m/%Y")}'


def _saluto(d):
    return f'Gentile {" ".join(x for x in (d.nome, d.cognome) if x)},'


def componi(docente, giorno, righe, variante):
    """Ritorna (oggetto, corpo). variante: nuova | variazione | annullamento."""
    quando = _quando(giorno)
    firma = ['', 'Messaggio automatico di Caronte: in caso di dubbi contatta la vicepresidenza.']
    if variante == 'annullamento':
        oggetto = f'ANNULLAMENTO supplenze di {quando}'
        corpo = [_saluto(docente), '',
                 f'le supplenze che ti erano state comunicate per {quando} sono state annullate.']
    else:
        prefisso = 'VARIAZIONE supplenze' if variante == 'variazione' else 'Supplenze'
        oggetto = f'{prefisso} di {quando}'
        intro = (f'l\'elenco delle tue supplenze per {quando} è stato aggiornato; '
                 f'questo sostituisce il messaggio precedente:'
                 if variante == 'variazione'
                 else f'ti sono state assegnate le seguenti supplenze per {quando}:')
        corpo = [_saluto(docente), '', intro, ''] + righe
    return oggetto, '\n'.join(corpo + firma)


def _ultimo_inviato(id_docente, giorno):
    return (EmailUscita.query
            .filter_by(tipo='supplenze', id_docente=id_docente, giorno=giorno)
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
    assenti = {d.id: d for d in Docente.query.filter(
        Docente.id.in_({s.id_assente for s in supp if s.id_assente})).all()} if supp else {}

    out = []
    for id_doc in ids:
        d = docenti.get(id_doc)
        if d is None:
            continue
        righe = [_riga(s, assenti) for s in per_doc.get(id_doc, [])]
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


def _registra(p, giorno, stato, dettaglio=None):
    db.session.add(EmailUscita(
        tipo='supplenze', giorno=giorno, hash_contenuto=p['hash'],
        chiave=f'supplenze:{p["docente"].id}:{giorno.isoformat()}:{p["hash"]}:{time.time_ns()}',
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
