"""models/aula.py — Aula assegnata a ogni classe per l'anno scolastico."""
from models import db

SEDI = [
    'Sede Centrale - Piano Interrato',
    'Sede Centrale - Piano Terra',
    'Sede Centrale - 1° Piano',
    'Sede Centrale - Torretta',
    'Sede Staccata',
    'Sede Staccata - Sportivo',
    'Sede Staccata - Cappuccini',
]

AULE_NUMERATE = [str(i) for i in range(1, 39)]
AULE_SPECIALI = [
    'Aula Magna', 'Lab. Informatica', 'Lab. Linguistico',
    'Lab. BIM', 'Palestrone', 'Palestrina',
]
AULE_LIST = AULE_NUMERATE + AULE_SPECIALI


class Aula(db.Model):
    __tablename__ = 'aule'

    id        = db.Column(db.Integer, primary_key=True)
    anno_scol = db.Column(db.String(9),  nullable=False)
    classe    = db.Column(db.String(20), nullable=False)
    aula      = db.Column(db.String(50), nullable=False)
    sede      = db.Column(db.String(60), nullable=False)

    __table_args__ = (
        db.UniqueConstraint('anno_scol', 'classe', name='uq_aula_anno_classe'),
    )

    def __repr__(self):
        return f'<Aula {self.anno_scol} {self.classe} -> {self.aula} ({self.sede})>'

    @property
    def label(self):
        return f'Aula {self.aula} — {self.sede}'
