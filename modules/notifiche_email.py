"""
Notifiche email ai docenti (per ora: supplenza assegnata).

Modalita', da variabile d'ambiente CARONTE_EMAIL_MODE:
  off       (default) non fa nulla;
  simulato  compone il messaggio e lo registra in email_uscita, senza inviare;
  reale     riservato: l'invio via Gmail API non e' ancora collegato, quindi
            registra 'errore' invece di spedire.

Nel messaggio compaiono solo data, ora, classe e aula: mai nomi di alunni.
La funzione non solleva mai eccezioni verso la route chiamante.
"""
import os
from datetime import date

from models import db
from models.docente import Docente
from models.email_uscita import EmailUscita

DOMINIO_AMMESSO = '@davincichiavenna.edu.it'
MODALITA_VALIDE = ('off', 'simulato', 'reale')

_GIORNI = ['lunedì', 'martedì', 'mercoledì', 'giovedì', 'venerdì', 'sabato', 'domenica']


def modalita():
    m = (os.environ.get('CARONTE_EMAIL_MODE') or 'off').strip().lower()
    return m if m in MODALITA_VALIDE else 'off'


def componi_supplenza(s, docente, assente=None):
    """Ritorna (oggetto, corpo) per la notifica di supplenza assegnata."""
    quando = f'{_GIORNI[s.data.weekday()]} {s.data.strftime("%d/%m/%Y")}, ora {s.ora}'
    oggetto = f'Supplenza {s.data.strftime("%d/%m/%Y")} - {s.ora}ª ora'
    righe = [
        f'Gentile {docente.nome or ""} {docente.cognome},'.replace('  ', ' '),
        '',
        f'ti è stata assegnata una supplenza: {quando}'
        + (f', classe {s.classe}.' if s.classe else '.'),
    ]
    if assente is not None:
        righe.append(f'In sostituzione di: {assente.cognome}.')
    righe += ['', 'Messaggio automatico di Caronte: in caso di dubbi contatta la vicepresidenza.']
    return oggetto, '\n'.join(righe)


def _registra(chiave, tipo, docente, destinatario, oggetto, corpo, stato, dettaglio=None):
    db.session.add(EmailUscita(
        tipo=tipo, chiave=chiave, id_docente=docente.id if docente else None,
        destinatario=destinatario, oggetto=oggetto, corpo=corpo,
        stato=stato, dettaglio=dettaglio))
    db.session.commit()


def notifica_supplenza_assegnata(s):
    """Registra (o invia, quando sara' collegato) la notifica al sostituto.
    Ritorna lo stato scritto, o None se non fa nulla."""
    try:
        mod = modalita()
        if mod == 'off' or not s.id_sostituto:
            return None
        chiave = f'supplenza:{s.id}:{s.id_sostituto}:{s.data.isoformat()}:{s.ora}'
        if EmailUscita.query.filter_by(chiave=chiave).first():
            return None  # gia' notificata: nessun doppio invio
        docente = db.session.get(Docente, s.id_sostituto)
        assente = db.session.get(Docente, s.id_assente) if s.id_assente else None
        if docente is None:
            return None
        oggetto, corpo = componi_supplenza(s, docente, assente)
        dest = (docente.email or '').strip().lower()
        if not dest:
            stato, det = 'saltata', 'email mancante'
        elif not dest.endswith(DOMINIO_AMMESSO):
            stato, det = 'saltata', 'indirizzo fuori dominio'
        elif s.data < date.today():
            stato, det = 'saltata', 'data passata'
        elif mod == 'simulato':
            stato, det = 'simulata', None
        else:
            stato, det = 'errore', 'invio reale non ancora collegato'
        _registra(chiave, 'supplenza', docente, dest, oggetto, corpo, stato, det)
        return stato
    except Exception:
        db.session.rollback()
        return None
