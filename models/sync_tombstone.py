"""
"Lapidi" (tombstone) per le eliminazioni, usate dal sync automatico
additivo (vedi modules/auto_sync.py).

Il merge additivo, da solo, non saprebbe mai distinguere "questa riga
non è ancora arrivata qui" da "questa riga è stata eliminata qui": in
entrambi i casi la riga è assente in locale. Senza questa tabella, una
riga eliminata su una postazione ricompariva al giro successivo perché
l'altra macchina (o Drive) la aveva ancora e veniva vista come "nuova".

Quando una riga di 'assenze' o 'supplenze' viene eliminata fisicamente
dall'app (vedi modules/auto_sync.py::registra_eliminazione, chiamata
dalle route prima del db.session.delete), si registra qui la sua
chiave logica. Il sync automatico:
- unisce le lapidi tra le macchine (sono "solo aggiunta", non c'è mai
  conflitto possibile su una eliminazione);
- non reintroduce mai una riga la cui chiave ha una lapide;
- elimina anche in locale una riga ancora presente la cui chiave ha
  una lapide arrivata dall'altra macchina.
"""
from models import db
from datetime import datetime


class SyncTombstone(db.Model):
    __tablename__ = 'sync_tombstones'

    id            = db.Column(db.Integer, primary_key=True)
    tabella       = db.Column(db.String(40), nullable=False)
    chiave_logica = db.Column(db.Text, nullable=False)
    eliminato_il  = db.Column(db.DateTime, default=datetime.utcnow)
    eliminato_da  = db.Column(db.String(80))

    __table_args__ = (
        db.UniqueConstraint('tabella', 'chiave_logica',
                             name='uq_tombstone_tabella_chiave'),
    )

    def __repr__(self):
        return f"<SyncTombstone {self.tabella} {self.chiave_logica}>"
