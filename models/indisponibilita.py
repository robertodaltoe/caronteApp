from models import db
from datetime import datetime

class Indisponibilita(db.Model):
    __tablename__ = 'indisponibilita'

    id          = db.Column(db.Integer, primary_key=True)
    id_docente  = db.Column(db.Integer, db.ForeignKey('docenti.id'), nullable=False, index=True)
    data        = db.Column(db.Date,    nullable=False, index=True)
    ora         = db.Column(db.Integer, nullable=True)   # None = tutta la giornata
    motivo      = db.Column(db.String(50), default='altro')
    # colloqui | consiglio | uscita | progetto | gara | formazione | altro
    note        = db.Column(db.Text)
    creato_il   = db.Column(db.DateTime, default=datetime.utcnow)
    # Username di chi ha inserito — vedi models/assenza.py::creato_da.
    creato_da   = db.Column(db.String(80), nullable=True)

    def __repr__(self):
        return f"<Indisponibilita docente:{self.id_docente} {self.data} ora:{self.ora}>"
