"""
Modulo Esami Integrativi (passaggi e trasferimenti di settembre).

Studenti che chiedono il passaggio da un altro indirizzo o il
trasferimento da un'altra scuola devono sostenere, prima dell'inizio
del nuovo anno scolastico, un esame integrativo nelle materie non
coincidenti con il proprio percorso di provenienza. A differenza dei
colloqui di rientro dall'estero (dove le 4 materie sono le stesse per
tutta la classe), qui le materie da sostenere sono specifiche di
ciascun candidato: ognuno può avere un elenco diverso, con date e
commissioni indipendenti per ciascuna materia.

Come per il modulo Rientro, l'esito viene verbalizzato a mano su
registro cartaceo — qui si gestisce solo l'organizzazione (materie,
candidati, commissione, calendario).
"""
from models import db
from datetime import datetime


class EsameIntegrativoCandidato(db.Model):
    """Studente che deve sostenere uno o più esami integrativi."""
    __tablename__ = 'esami_integrativi_candidati'

    id                  = db.Column(db.Integer, primary_key=True)
    anno_scol           = db.Column(db.String(9), nullable=False, default='2025-2026')
    cognome             = db.Column(db.String(80), nullable=False)
    nome                = db.Column(db.String(80), nullable=False)
    classe_destinazione = db.Column(db.String(20), nullable=False)  # classe a cui aspira
    provenienza         = db.Column(db.String(150), nullable=True)  # scuola/indirizzo di provenienza
    note                = db.Column(db.String(200), nullable=True)
    creato_il           = db.Column(db.DateTime, default=datetime.utcnow)

    materie = db.relationship('EsameIntegrativoMateria', back_populates='candidato',
                               cascade='all, delete-orphan',
                               order_by='EsameIntegrativoMateria.materia')

    @property
    def nome_completo(self):
        return f'{self.cognome} {self.nome}'


class EsameIntegrativoMateria(db.Model):
    """
    Una materia da sostenere per un candidato, con la propria
    commissione (2 docenti) e il proprio calendario — indipendente
    dalle altre materie dello stesso candidato.
    """
    __tablename__ = 'esami_integrativi_materie'

    id           = db.Column(db.Integer, primary_key=True)
    id_candidato = db.Column(db.Integer, db.ForeignKey('esami_integrativi_candidati.id'), nullable=False)
    materia      = db.Column(db.String(100), nullable=False)
    tipologia    = db.Column(db.String(10), nullable=True)  # 'scritta' | 'orale'

    data         = db.Column(db.Date, nullable=True)
    ora_inizio   = db.Column(db.String(5), nullable=True)   # HH:MM
    ora_fine     = db.Column(db.String(5), nullable=True)   # HH:MM

    id_docente_1 = db.Column(db.Integer, db.ForeignKey('docenti.id'), nullable=True)
    id_docente_2 = db.Column(db.Integer, db.ForeignKey('docenti.id'), nullable=True)

    creato_il    = db.Column(db.DateTime, default=datetime.utcnow)

    candidato = db.relationship('EsameIntegrativoCandidato', back_populates='materie')
    docente_1 = db.relationship('Docente', foreign_keys=[id_docente_1])
    docente_2 = db.relationship('Docente', foreign_keys=[id_docente_2])

    @property
    def membri_commissione(self):
        return [d for d in (self.docente_1, self.docente_2) if d is not None]
