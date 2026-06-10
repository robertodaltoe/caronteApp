"""
Sostituzione scrutinio — traccia il docente nominato al posto dell'assente
con riferimento al protocollo.
"""
from models import db
from datetime import datetime


class SostituzioneScrutinio(db.Model):
    __tablename__ = 'sostituzioni_scrutinio'

    id              = db.Column(db.Integer, primary_key=True)
    id_attivita     = db.Column(db.Integer, db.ForeignKey('attivita_ist.id'), nullable=False)
    id_assente      = db.Column(db.Integer, db.ForeignKey('docenti.id'), nullable=False)
    id_sostituto    = db.Column(db.Integer, db.ForeignKey('docenti.id'), nullable=True)
    n_protocollo    = db.Column(db.String(40), nullable=True)   # numero protocollo nomina
    data_nomina     = db.Column(db.Date, nullable=True)
    note            = db.Column(db.String(200), nullable=True)
    creato_il       = db.Column(db.DateTime, default=datetime.utcnow)

    attivita  = db.relationship('AttivitaIst')
    assente   = db.relationship('Docente', foreign_keys=[id_assente])
    sostituto = db.relationship('Docente', foreign_keys=[id_sostituto])

    __table_args__ = (
        db.UniqueConstraint('id_attivita', 'id_assente',
                            name='uq_sost_scrutinio'),
    )
