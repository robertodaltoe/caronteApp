"""
Materie e Dipartimenti — roster stabile, modificabile dall'interfaccia.
"""
from models import db


class Dipartimento(db.Model):
    __tablename__ = 'dipartimenti'

    id     = db.Column(db.Integer, primary_key=True)
    nome   = db.Column(db.String(120), nullable=False, unique=True)
    sigla  = db.Column(db.String(10),  nullable=False, unique=True)
    ordine = db.Column(db.Integer, default=0)

    materie = db.relationship('Materia', back_populates='dipartimento',
                               order_by='Materia.nome')

    def __repr__(self):
        return f'<Dipartimento {self.sigla}>'


class Materia(db.Model):
    __tablename__ = 'materie'

    id              = db.Column(db.Integer, primary_key=True)
    nome            = db.Column(db.String(120), nullable=False)
    sigla           = db.Column(db.String(20),  nullable=False, unique=True)
    id_dipartimento = db.Column(db.Integer, db.ForeignKey('dipartimenti.id'),
                                nullable=False)
    # Indirizzi in cui compare (JSON list, es. '["LLI","LSC"]')
    indirizzi_json  = db.Column(db.String(200), default='[]')
    # Codice materia nel DB orario (per matching automatico con OrarioDocente.materia)
    codice_orario   = db.Column(db.String(40), nullable=True)
    nome_breve      = db.Column(db.String(60),  nullable=True)  # es. 'Storia' — per stampe e badge
    alias           = db.Column(db.String(20),  nullable=True)  # es. 'STO' — visibile all'utente
    attiva          = db.Column(db.Boolean, default=True)
    # Classe di concorso che insegna questa materia (es. A026 - Matematica)
    id_classe_concorso = db.Column(db.Integer, db.ForeignKey('classi_concorso.id'), nullable=True)

    dipartimento    = db.relationship('Dipartimento', back_populates='materie')
    docenti_mat     = db.relationship('DocenteMateria', back_populates='materia',
                                    cascade='all, delete-orphan')
    classe_concorso = db.relationship('ClasseConcorso', back_populates='materie')

    @property
    def indirizzi(self):
        import json
        try:
            return json.loads(self.indirizzi_json or '[]')
        except Exception:
            return []

    def __repr__(self):
        return f'<Materia {self.sigla}>'


class DocenteMateria(db.Model):
    """Assegnazione docente-materia per anno scolastico."""
    __tablename__ = 'docente_materie'

    id          = db.Column(db.Integer, primary_key=True)
    id_docente  = db.Column(db.Integer, db.ForeignKey('docenti.id'), nullable=False)
    id_materia  = db.Column(db.Integer, db.ForeignKey('materie.id'),  nullable=False)
    anno_scol   = db.Column(db.String(9), nullable=False)   # es. '2025-2026'

    docente = db.relationship('Docente', back_populates='materie_ist')
    materia = db.relationship('Materia', back_populates='docenti_mat')

    __table_args__ = (
        db.UniqueConstraint('id_docente', 'id_materia', 'anno_scol',
                            name='uq_docente_materia_anno'),
    )
