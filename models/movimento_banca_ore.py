from models import db
from datetime import datetime

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

    supplenza    = db.relationship('Supplenza', backref='movimento', lazy=True)

    def __repr__(self):
        segno = "+" if self.minuti >= 0 else ""
        return f"<Movimento docente:{self.id_docente} {self.data} {segno}{self.minuti}min {self.tipo}>"
