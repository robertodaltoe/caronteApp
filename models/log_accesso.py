"""models/log_accesso.py — Log di accesso per compliance GDPR."""
from models import db
from datetime import datetime


class LogAccesso(db.Model):
    __tablename__ = 'log_accessi'

    id          = db.Column(db.Integer, primary_key=True)
    id_utente   = db.Column(db.Integer, db.ForeignKey('utenti.id'), nullable=True)
    username    = db.Column(db.String(50))
    nome_completo = db.Column(db.String(160))           # salvato anche se utente eliminato
    ruolo       = db.Column(db.String(20))
    azione      = db.Column(db.String(100))           # es. 'login', 'visualizza_report', ecc.
    dettaglio   = db.Column(db.String(300))           # es. nome docente visualizzato
    ip          = db.Column(db.String(45))
    timestamp   = db.Column(db.DateTime, default=datetime.utcnow)
    esito       = db.Column(db.String(10), default='ok')  # 'ok' o 'denied'

    utente = db.relationship('Utente', backref='log_accessi')

    def __repr__(self):
        return f'<Log {self.username} {self.azione} {self.timestamp}>'
