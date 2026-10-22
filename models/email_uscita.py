"""
Registro delle email generate da Caronte (notifiche ai docenti).

Ogni riga e' un messaggio composto: in modalita' 'simulato' resta qui
senza partire; in modalita' 'reale' (non ancora collegata) riporta
l'esito dell'invio. 'chiave' e' unica per evitare doppi invii dello
stesso evento (vedi modules/notifiche_email.py).
"""
from models import db
from datetime import datetime


class EmailUscita(db.Model):
    __tablename__ = 'email_uscita'

    id           = db.Column(db.Integer, primary_key=True)
    creato_il    = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    tipo         = db.Column(db.String(30), nullable=False)    # es. supplenza
    chiave       = db.Column(db.String(120), nullable=False, unique=True)
    id_docente   = db.Column(db.Integer, db.ForeignKey('docenti.id'), nullable=True)
    destinatario = db.Column(db.String(200))
    oggetto      = db.Column(db.String(250))
    corpo        = db.Column(db.Text)
    stato        = db.Column(db.String(20), nullable=False)
    # simulata | inviata | errore | saltata
    dettaglio    = db.Column(db.String(250))   # motivo di 'saltata' o testo errore
