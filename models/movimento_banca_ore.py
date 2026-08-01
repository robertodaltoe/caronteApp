from models import db
from datetime import datetime
from sqlalchemy import event


def anno_scol_da_data(data):
    """
    Anno scolastico che contiene la data indicata (stessa regola usata in
    config_anno.py: settembre-agosto). Es. 15/10/2025 -> '2025-2026',
    15/03/2026 -> '2025-2026'.
    """
    if data is None:
        return None
    if data.month >= 9:
        return f'{data.year}-{data.year + 1}'
    return f'{data.year - 1}-{data.year}'


class MovimentoBancaOre(db.Model):
    __tablename__ = 'banca_ore'

    id           = db.Column(db.Integer, primary_key=True)
    id_docente   = db.Column(db.Integer, db.ForeignKey('docenti.id'), nullable=False, index=True)
    data         = db.Column(db.Date,    nullable=False, index=True)
    minuti       = db.Column(db.Integer, nullable=False)
    # positivo = credito (supplenza svolta)
    # negativo = debito  (assenza/permesso)
    tipo         = db.Column(db.String(30), nullable=False)
    # supplenza_recupero | supplenza_pagamento | supplenza_completamento
    # supplenza_potenziamento | assenza | permesso | civica | rettifica
    descrizione  = db.Column(db.String(200))
    id_supplenza = db.Column(db.Integer, db.ForeignKey('supplenze.id'), nullable=True)
    creato_il    = db.Column(db.DateTime, default=datetime.utcnow)
    # Anno scolastico del movimento — calcolato automaticamente dalla
    # colonna 'data' (vedi listener sotto), non serve impostarlo a mano
    # nei punti che creano un movimento. Permette al saldo banca ore di
    # essere calcolato per anno invece che come totale cumulativo infinito.
    anno_scol    = db.Column(db.String(9), index=True)

    supplenza    = db.relationship('Supplenza', backref='movimento', lazy=True)

    def __repr__(self):
        segno = "+" if self.minuti >= 0 else ""
        return f"<Movimento docente:{self.id_docente} {self.data} {segno}{self.minuti}min {self.tipo}>"


@event.listens_for(MovimentoBancaOre, 'before_insert')
def _imposta_anno_scol(mapper, connection, target):
    """Calcola anno_scol dalla data del movimento se non è già impostato
    esplicitamente. Centralizzato qui invece che in ogni singolo punto del
    codice che crea un MovimentoBancaOre, per non doverci pensare ogni
    volta e non rischiare di dimenticarlo in un punto nuovo futuro."""
    if not target.anno_scol:
        target.anno_scol = anno_scol_da_data(target.data)
