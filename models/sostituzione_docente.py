"""
Modelli per modules/sostituzione_docente.py -- vedi la docstring di
quel modulo per il disegno completo (Sessione 69 addendum 2).
"""
from datetime import datetime
from models import db


class SostituzioneDocente(db.Model):
    __tablename__ = 'sostituzioni_docenti'

    id            = db.Column(db.Integer, primary_key=True)
    id_titolare   = db.Column(db.Integer, db.ForeignKey('docenti.id'), nullable=False)
    id_sostituto  = db.Column(db.Integer, db.ForeignKey('docenti.id'), nullable=False)
    tipo          = db.Column(db.String(20), nullable=False)   # 'temporanea' | 'definitiva'
    data_inizio   = db.Column(db.Date, nullable=False)
    data_fine     = db.Column(db.Date, nullable=True)          # NULL solo per 'definitiva'
    stato         = db.Column(db.String(20), nullable=False, default='attiva')  # 'attiva'|'conclusa'
    note          = db.Column(db.Text, nullable=True)
    creato_il     = db.Column(db.DateTime, default=datetime.utcnow)
    creato_da     = db.Column(db.String(80), nullable=True)
    concluso_il   = db.Column(db.DateTime, nullable=True)
    concluso_da   = db.Column(db.String(80), nullable=True)

    titolare  = db.relationship('Docente', foreign_keys=[id_titolare])
    sostituto = db.relationship('Docente', foreign_keys=[id_sostituto])

    slot_orario = db.relationship('SostituzioneOrarioSlot', backref='sostituzione',
                                   cascade='all, delete-orphan')
    eventi_swap = db.relationship('SostituzioneEventoSwap', backref='sostituzione',
                                   cascade='all, delete-orphan')

    def __repr__(self):
        return (f'<SostituzioneDocente {self.tipo} #{self.id} '
                f'{self.id_titolare}->{self.id_sostituto} {self.stato}>')


class SostituzioneOrarioSlot(db.Model):
    """Una riga di OrarioDocente spostata dal titolare al sostituto per
    questa sostituzione -- id_orario_docente punta alla riga originale
    (il suo id non cambia quando si sposta id_docente), cosi'
    termina_sostituzione() sa esattamente quali righe rimettere a posto.
    giorno/ora/classe sono duplicati qui solo per leggibilita' in
    eventuali query/audit, non sono la fonte di verita'."""
    __tablename__ = 'sostituzioni_orario_slot'

    id                = db.Column(db.Integer, primary_key=True)
    id_sostituzione   = db.Column(db.Integer,
                                  db.ForeignKey('sostituzioni_docenti.id'), nullable=False)
    id_orario_docente = db.Column(db.Integer,
                                  db.ForeignKey('orario_docenti.id'), nullable=False)
    giorno            = db.Column(db.Integer, nullable=True)
    ora               = db.Column(db.Integer, nullable=True)
    classe            = db.Column(db.String(20), nullable=True)


class SostituzioneEventoSwap(db.Model):
    """Un evento istituzionale (Consiglio di classe/scrutinio) in cui il
    sostituto e' stato messo al posto del titolare per la durata della
    sostituzione -- titolare_era_presente ricorda se il titolare andava
    ripristinato al rientro (potrebbe non essere mai stato tra i
    partecipanti, es. evento creato durante l'assenza)."""
    __tablename__ = 'sostituzioni_eventi_swap'

    id                     = db.Column(db.Integer, primary_key=True)
    id_sostituzione        = db.Column(db.Integer,
                                       db.ForeignKey('sostituzioni_docenti.id'), nullable=False)
    id_attivita            = db.Column(db.Integer,
                                       db.ForeignKey('attivita_ist.id'), nullable=False)
    titolare_era_presente  = db.Column(db.Boolean, default=False)
