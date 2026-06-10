"""
Sospensioni didattiche — date in cui le lezioni sono sospese per tutto l'istituto.
In questi giorni non vengono generate supplenze e l'inserimento di assenze/permessi
è bloccato con avviso.
"""
from models import db
from datetime import datetime


TIPI_SOSPENSIONE = {
    'festività_nazionale': 'Festività nazionale',
    'sospensione_regionale': 'Sospensione regionale',
    'sospensione_istituto': 'Sospensione istituto',
    'vacanze_natale': 'Vacanze natalizie',
    'vacanze_pasqua': 'Vacanze pasquali',
    'vacanze_estate': 'Vacanze estive',
    'altro': 'Altro',
}


class SospensioneDidattica(db.Model):
    __tablename__ = 'sospensioni_didattiche'

    id          = db.Column(db.Integer, primary_key=True)
    data_inizio = db.Column(db.Date, nullable=False, index=True)
    data_fine   = db.Column(db.Date, nullable=False, index=True)
    descrizione = db.Column(db.String(200), nullable=False)
    tipo        = db.Column(db.String(40), default='festività_nazionale')
    creato_il   = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def tipo_label(self):
        return TIPI_SOSPENSIONE.get(self.tipo, self.tipo)

    @property
    def is_singolo(self):
        return self.data_inizio == self.data_fine

    def __repr__(self):
        return f'<Sospensione {self.data_inizio}–{self.data_fine} {self.descrizione}>'
