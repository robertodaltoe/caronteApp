"""
Piano della Formazione — corsi di aggiornamento/formazione docenti
(Piano Annuale delle Attività, Fase 1).

Ogni corso genera un evento AttivitaIst collegato (tipo='formazione'):
le ore rientrano così nello stesso bucket A del Collegio docenti e nello
stesso meccanismo di presenze/Piano Attività Personale già usato per gli
altri eventi istituzionali (_preset_partecipanti, quota_ore_bucket) —
niente conteggio bucket parallelo da mantenere allineato a mano.

Le "iscrizioni per singola voce" sono le stesse righe
AttivitaIstPartecipante dell'evento collegato (preset=True per i corsi
obbligatori per tutti, preset=False per le iscrizioni volontarie) — non
una tabella a parte, per lo stesso motivo.
"""
from models import db
from datetime import datetime


MODALITA = {
    'presenza': 'In presenza',
    'online':   'Online',
    'mista':    'Mista',
}


class CorsoFormazione(db.Model):
    __tablename__ = 'corsi_formazione'

    id                  = db.Column(db.Integer, primary_key=True)
    id_attivita         = db.Column(db.Integer,
                                    db.ForeignKey('attivita_ist.id'), nullable=False)
    titolo              = db.Column(db.String(200), nullable=False)
    tipologia           = db.Column(db.String(100), nullable=True)
    ore                 = db.Column(db.Float, nullable=False)
    modalita            = db.Column(db.String(20), default='presenza')
    data_inizio         = db.Column(db.Date, nullable=False)
    data_fine           = db.Column(db.Date, nullable=False)
    obbligatorio_tutti  = db.Column(db.Boolean, default=False)
    anno_scol           = db.Column(db.String(9), nullable=False, index=True)
    note                = db.Column(db.Text, nullable=True)
    creato_il           = db.Column(db.DateTime, default=datetime.utcnow)

    attivita = db.relationship('AttivitaIst')

    @property
    def modalita_label(self):
        return MODALITA.get(self.modalita, self.modalita)

    @property
    def n_iscritti(self):
        return len(self.attivita.partecipanti) if self.attivita else 0

    @property
    def periodo_label(self):
        if self.data_inizio == self.data_fine:
            return self.data_inizio.strftime('%d/%m/%Y')
        return f"{self.data_inizio.strftime('%d/%m/%Y')}–{self.data_fine.strftime('%d/%m/%Y')}"

    def __repr__(self):
        return f'<CorsoFormazione {self.titolo[:30]} {self.data_inizio}>'
