from models import db

GIORNI = ['Lunedì','Martedì','Mercoledì','Giovedì','Venerdì','Sabato']

class OrarioDocente(db.Model):
    __tablename__ = 'orario_docenti'

    id          = db.Column(db.Integer, primary_key=True)
    id_docente  = db.Column(db.Integer, db.ForeignKey('docenti.id'), nullable=False, index=True)
    giorno      = db.Column(db.Integer, nullable=False)  # 0=lun … 5=sab
    ora         = db.Column(db.Integer, nullable=False)  # 1-9
    classe      = db.Column(db.String(20))
    materia     = db.Column(db.String(60))
    tipo_ora    = db.Column(db.String(20), default='lezione')
    # lezione | compresenza | potenziamento | disposizione | altro

    docente     = db.relationship('Docente', backref='orario', lazy=True)

    @property
    def giorno_nome(self):
        return GIORNI[self.giorno] if 0 <= self.giorno <= 5 else ''

    def __repr__(self):
        return f"<Orario {self.docente.cognome if self.docente else '?'} {self.giorno_nome} {self.ora}ª {self.classe}>"
