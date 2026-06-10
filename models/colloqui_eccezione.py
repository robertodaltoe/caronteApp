"""models/colloqui_eccezione.py
Date in cui i colloqui di un docente si svolgono al pomeriggio/online
e quindi NON generano indisponibilità mattutina.
"""
from models import db

class ColloquiEccezione(db.Model):
    __tablename__ = 'colloqui_eccezioni'

    id         = db.Column(db.Integer, primary_key=True)
    id_docente = db.Column(db.Integer, db.ForeignKey('docenti.id'), nullable=False)
    data       = db.Column(db.Date, nullable=False)   # data inizio periodo
    data_fine  = db.Column(db.Date, nullable=True)    # data fine (None = giornata singola)
    note       = db.Column(db.String(200))

    docente = db.relationship('Docente', backref='colloqui_eccezioni')

    def __repr__(self):
        return f'<ColloquiEccezione {self.id_docente} {self.data}>'
