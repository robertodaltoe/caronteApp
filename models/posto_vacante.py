"""
Posti vacanti nell'orario: righe dell'orario importato che appartengono a
un docente non ancora nominato (placeholder di Assegnazioni, oppure un
nome che esiste solo nel file orario).

OrarioDocente richiede un docente reale (id_docente NOT NULL, letto da 20+
moduli): per non toccarlo, le ore dei posti vacanti vivono qui, in una
tabella a parte ricreata a ogni import. Il collegamento nome-nel-file ->
posto vacante e' salvato in AliasPostoVacante, cosi' i reimport settimanali
lo riconoscono da soli.
"""
from datetime import datetime
from models import db

PREFISSO_NOTE_SUPPLENZA = 'POSTO_VACANTE|'


class AliasPostoVacante(db.Model):
    __tablename__ = 'alias_posti_vacanti'

    id             = db.Column(db.Integer, primary_key=True)
    nome_file      = db.Column(db.String(100), nullable=False, unique=True)
    # Placeholder di Assegnazioni a cui il nome e' collegato; NULL = posto
    # "nuovo", identificato dal solo nome nel file.
    id_assegnazione = db.Column(db.Integer, db.ForeignKey('assegnazioni_docenti.id'),
                                nullable=True)
    ignora         = db.Column(db.Boolean, default=False, nullable=False)
    creato_il      = db.Column(db.DateTime, default=datetime.utcnow)

    assegnazione   = db.relationship('AssegnazioneDocente')

    @property
    def chiave_posto(self):
        return (f'A{self.id_assegnazione}' if self.id_assegnazione
                else f'N:{self.nome_file}')

    @property
    def nome_posto(self):
        if self.assegnazione is not None and self.assegnazione.nome_placeholder:
            return self.assegnazione.nome_placeholder
        return self.nome_file


class OrarioPlaceholder(db.Model):
    __tablename__ = 'orario_placeholder'

    id         = db.Column(db.Integer, primary_key=True)
    nome_file  = db.Column(db.String(100), nullable=False, index=True)
    giorno     = db.Column(db.Integer, nullable=False)
    ora        = db.Column(db.Integer, nullable=False)
    classe     = db.Column(db.String(20))
    materia    = db.Column(db.String(80))
    tipo_ora   = db.Column(db.String(20), default='lezione')
    data_inizio_validita = db.Column(db.Date, nullable=True)
    data_fine_validita   = db.Column(db.Date, nullable=True)
