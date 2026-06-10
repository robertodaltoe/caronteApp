from models import db
from datetime import datetime

class ScambioOrario(db.Model):
    """
    Scambio / variazione orario tra due docenti.
    - Non muove la banca ore per nessuno dei due.
    - Il sostituto (docente B) è già nominato.
    - Supporta più slot cede e più slot recupero.
    """
    __tablename__ = 'scambi_orario'

    id           = db.Column(db.Integer, primary_key=True)
    # Docente che cede le ore
    id_docente_a = db.Column(db.Integer, db.ForeignKey('docenti.id'), nullable=False)
    # Docente che riceve / copre
    id_docente_b = db.Column(db.Integer, db.ForeignKey('docenti.id'), nullable=False)
    # Tipo: 'scambio' (con recupero) | 'ferie' (senza recupero)
    tipo         = db.Column(db.String(20), default='scambio')
    note         = db.Column(db.String(300), nullable=True)
    creato_il    = db.Column(db.DateTime, default=datetime.utcnow)

    docente_a    = db.relationship('Docente', foreign_keys=[id_docente_a])
    docente_b    = db.relationship('Docente', foreign_keys=[id_docente_b])
    slots_cede   = db.relationship('ScambioSlot',
                                   foreign_keys='ScambioSlot.id_scambio',
                                   primaryjoin='ScambioSlot.id_scambio == ScambioOrario.id',
                                   back_populates='scambio',
                                   cascade='all, delete-orphan')


class ScambioSlot(db.Model):
    """
    Singolo slot di uno scambio orario.
    tipo_slot: 'cede' | 'recupero'
    """
    __tablename__ = 'scambio_slots'

    id          = db.Column(db.Integer, primary_key=True)
    id_scambio  = db.Column(db.Integer, db.ForeignKey('scambi_orario.id'), nullable=False)
    tipo_slot   = db.Column(db.String(20), default='cede')  # 'cede' | 'recupero'
    data        = db.Column(db.Date, nullable=False)
    ora         = db.Column(db.Integer, nullable=False)
    classe      = db.Column(db.String(30), nullable=True)
    note        = db.Column(db.String(200), nullable=True)

    scambio     = db.relationship('ScambioOrario',
                                  foreign_keys=[id_scambio],
                                  back_populates='slots_cede')
