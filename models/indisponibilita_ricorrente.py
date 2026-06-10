from models import db
from datetime import datetime

class IndisponibilitaRicorrente(db.Model):
    """
    Indisponibilità fissa settimanale (es. colloqui ogni lunedì 3ª ora).
    Viene consultata automaticamente dai suggerimenti supplenze.
    """
    __tablename__ = 'indisponibilita_ricorrenti'

    id          = db.Column(db.Integer, primary_key=True)
    id_docente  = db.Column(db.Integer, db.ForeignKey('docenti.id'),
                             nullable=False, index=True)
    giorno      = db.Column(db.Integer, nullable=False)  # 0=lun…5=sab
    ora         = db.Column(db.Integer, nullable=True)   # None = tutta la giornata
    motivo      = db.Column(db.String(50), default='colloqui')
    note        = db.Column(db.String(200))
    attiva      = db.Column(db.Boolean, default=True)
    creato_il   = db.Column(db.DateTime, default=datetime.utcnow)

    docente     = db.relationship('Docente',
                                   backref='indisp_ricorrenti', lazy=True)

    GIORNI = ['Lunedì','Martedì','Mercoledì','Giovedì','Venerdì','Sabato']

    @property
    def giorno_nome(self):
        return self.GIORNI[self.giorno] if 0 <= self.giorno <= 5 else ''

    def __repr__(self):
        return (f"<IndispRicorrente doc:{self.id_docente} "
                f"{self.giorno_nome} ora:{self.ora}>")
