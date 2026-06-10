"""models/attivita_accompagnatore.py
Dettaglio ore per ogni accompagnatore in un'attività FSL o simile.
Permette di differenziare data e ore per ogni docente.
"""
from models import db

class AttivitaAccompagnatore(db.Model):
    __tablename__ = 'attivita_accompagnatori_dettaglio'

    id           = db.Column(db.Integer, primary_key=True)
    id_attivita  = db.Column(db.Integer, db.ForeignKey('attivita_fuori_aula.id'), nullable=False)
    id_docente   = db.Column(db.Integer, db.ForeignKey('docenti.id'), nullable=False)
    data         = db.Column(db.Date, nullable=False)
    ora_inizio   = db.Column(db.Integer, nullable=False)
    ora_fine     = db.Column(db.Integer, nullable=False)
    ore_json     = db.Column(db.String(50))  # es. '1,2,4,5' — ore esatte selezionate

    attivita = db.relationship('AttivitaFuoriAula',
                               backref=db.backref('slot_accompagnatori', lazy='dynamic'))
    docente  = db.relationship('Docente',
                               backref=db.backref('slot_attivita', lazy='dynamic'))

    def __repr__(self):
        return f'<AttivitaAcc {self.id_docente} {self.data} {self.ora_inizio}-{self.ora_fine}>'
