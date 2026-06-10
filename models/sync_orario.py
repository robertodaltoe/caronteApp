from models import db
from datetime import datetime

class AliasDocente(db.Model):
    """
    Mappa nomi nel file Excel -> docente nel database.
    Es. 'MONTEMANARO' -> id=60 (MONTEMARANO)
    """
    __tablename__ = 'alias_docenti'

    id           = db.Column(db.Integer, primary_key=True)
    nome_file    = db.Column(db.String(100), nullable=False, unique=True)
    id_docente   = db.Column(db.Integer, db.ForeignKey('docenti.id'),
                              nullable=False)
    note         = db.Column(db.String(200))
    creato_il    = db.Column(db.DateTime, default=datetime.utcnow)

    docente      = db.relationship('Docente', backref='aliases', lazy=True)

    def __repr__(self):
        return f"<Alias '{self.nome_file}' -> {self.id_docente}>"


class LogImportazione(db.Model):
    """
    Tiene traccia delle importazioni orario.
    """
    __tablename__ = 'log_importazioni'

    id           = db.Column(db.Integer, primary_key=True)
    data_ora     = db.Column(db.DateTime, default=datetime.utcnow)
    file_nome    = db.Column(db.String(200))
    slot_totali  = db.Column(db.Integer, default=0)
    docenti_nuovi= db.Column(db.Integer, default=0)
    non_riconosciuti = db.Column(db.Text)   # JSON list
    note         = db.Column(db.Text)
    esito        = db.Column(db.String(20), default='ok')
    # ok | warning | errore

    def __repr__(self):
        return f"<Log {self.data_ora} slot={self.slot_totali}>"
