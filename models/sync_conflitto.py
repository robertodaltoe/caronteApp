"""
Conflitti rilevati dal sync automatico additivo (vedi modules/auto_sync.py).

Quando il sync in background trova, per la stessa riga logica (stessa
chiave naturale, es. stesso docente+data+fascia oraria per un'assenza),
un contenuto diverso tra il database locale e quello pubblicato su
Google Drive dall'altra postazione, NON sceglie da solo quale tenere:
registra il conflitto qui e lo lascia in sospeso finché una persona
non lo rivede dalla pagina /sync/conflitti.
"""
from models import db
from datetime import datetime


class SyncConflitto(db.Model):
    __tablename__ = 'sync_conflitti'

    id            = db.Column(db.Integer, primary_key=True)
    tabella       = db.Column(db.String(40), nullable=False)
    # JSON dict {colonna: valore} — identifica la riga in modo stabile
    # tra le due macchine (non l'id autoincrementale, che può coincidere
    # per righe diverse su database indipendenti).
    chiave_logica = db.Column(db.Text, nullable=False)
    descrizione   = db.Column(db.String(200))
    # JSON: elenco dei nomi di colonna che differiscono
    campi_diversi = db.Column(db.Text)
    dati_locali   = db.Column(db.Text)   # JSON: riga così come vista in locale
    dati_remoti   = db.Column(db.Text)   # JSON: riga così come vista su Drive
    rilevato_il   = db.Column(db.DateTime, default=datetime.utcnow)
    aggiornato_il = db.Column(db.DateTime, default=datetime.utcnow,
                               onupdate=datetime.utcnow)
    risolto       = db.Column(db.Boolean, default=False, nullable=False, index=True)
    risolto_il    = db.Column(db.DateTime)
    risolto_da    = db.Column(db.String(80))
    scelta        = db.Column(db.String(20))   # 'locale' | 'remoto'

    def __repr__(self):
        return f"<SyncConflitto {self.tabella} {self.chiave_logica} risolto={self.risolto}>"
