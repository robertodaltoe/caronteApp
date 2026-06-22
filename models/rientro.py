"""
Modulo Colloqui di Rientro dall'estero.

Studenti che hanno svolto l'anno (o il secondo semestre) all'estero
sostengono, prima dell'inizio del nuovo anno scolastico, un colloquio
non selettivo davanti a una commissione (4 docenti delle materie scelte
dal consiglio di classe + 1 membro DS/vicario) per verificare il
raggiungimento delle competenze. L'esito è sempre positivo e viene
verbalizzato a mano su registro cartaceo — qui si gestisce solo
l'organizzazione (materie, candidati, commissione, calendario).
"""
from models import db
from datetime import datetime


class RientroMateriaClasse(db.Model):
    """
    Una riga per ciascuna delle 4 materie scelte dal consiglio di classe
    per i colloqui di rientro di una determinata classe.
    """
    __tablename__ = 'rientro_materie_classe'

    id          = db.Column(db.Integer, primary_key=True)
    anno_scol   = db.Column(db.String(9), nullable=False, default='2025-2026')
    classe      = db.Column(db.String(20), nullable=False)
    materia     = db.Column(db.String(100), nullable=False)
    creato_il   = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('anno_scol', 'classe', 'materia', name='uq_rientro_materia_classe'),
    )


class RientroCandidato(db.Model):
    """Studente che deve sostenere il colloquio di rientro."""
    __tablename__ = 'rientro_candidati'

    id               = db.Column(db.Integer, primary_key=True)
    anno_scol        = db.Column(db.String(9), nullable=False, default='2025-2026')
    cognome          = db.Column(db.String(80), nullable=False)
    nome             = db.Column(db.String(80), nullable=False)
    classe           = db.Column(db.String(20), nullable=False)  # classe di provenienza
    note             = db.Column(db.String(200), nullable=True)
    creato_il        = db.Column(db.DateTime, default=datetime.utcnow)

    colloquio = db.relationship('RientroColloquio', back_populates='candidato',
                                 uselist=False, cascade='all, delete-orphan')


class RientroColloquio(db.Model):
    """
    Calendarizzazione del colloquio: data/ora + i 5 membri della
    commissione (4 docenti di materia + 1 membro DS/vicario).
    """
    __tablename__ = 'rientro_colloqui'

    id              = db.Column(db.Integer, primary_key=True)
    id_candidato    = db.Column(db.Integer, db.ForeignKey('rientro_candidati.id'), nullable=False)

    data            = db.Column(db.Date, nullable=True)
    ora_inizio      = db.Column(db.String(5), nullable=True)   # HH:MM
    ora_fine        = db.Column(db.String(5), nullable=True)   # HH:MM

    # 4 membri docenti di materia (uno per ciascuna delle 4 materie scelte
    # per la classe di provenienza) + 1 membro DS/vicario.
    id_docente_1    = db.Column(db.Integer, db.ForeignKey('docenti.id'), nullable=True)
    id_docente_2    = db.Column(db.Integer, db.ForeignKey('docenti.id'), nullable=True)
    id_docente_3    = db.Column(db.Integer, db.ForeignKey('docenti.id'), nullable=True)
    id_docente_4    = db.Column(db.Integer, db.ForeignKey('docenti.id'), nullable=True)
    id_membro_ds    = db.Column(db.Integer, db.ForeignKey('docenti.id'), nullable=True)

    creato_il       = db.Column(db.DateTime, default=datetime.utcnow)

    candidato    = db.relationship('RientroCandidato', back_populates='colloquio')
    docente_1    = db.relationship('Docente', foreign_keys=[id_docente_1])
    docente_2    = db.relationship('Docente', foreign_keys=[id_docente_2])
    docente_3    = db.relationship('Docente', foreign_keys=[id_docente_3])
    docente_4    = db.relationship('Docente', foreign_keys=[id_docente_4])
    membro_ds    = db.relationship('Docente', foreign_keys=[id_membro_ds])

    @property
    def membri_commissione(self):
        """Tutti i membri (4 docenti + DS/vicario) con un id valido."""
        return [d for d in (self.docente_1, self.docente_2, self.docente_3,
                            self.docente_4, self.membro_ds) if d is not None]
