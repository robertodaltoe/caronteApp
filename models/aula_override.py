"""models/aula_override.py — Override temporaneo aula per una supplenza specifica."""
from models import db

class AulaOverride(db.Model):
    __tablename__ = 'aule_override'

    id          = db.Column(db.Integer, primary_key=True)
    id_supplenza = db.Column(db.Integer, db.ForeignKey('supplenze.id'), nullable=False, unique=True)
    aula        = db.Column(db.String(50), nullable=False)
    sede        = db.Column(db.String(60), nullable=False)
    note        = db.Column(db.String(200))

    supplenza = db.relationship('Supplenza', backref=db.backref('aula_override', uselist=False))

    @property
    def label(self):
        return f'Aula {self.aula} — {self.sede}'
