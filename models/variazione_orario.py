from models import db
from datetime import datetime

class VariazioneOrario(db.Model):
    """
    Variazioni al quadro orario che NON sono assenze docente:
    sorveglianza prove, simulazioni esame, attività alternativa,
    cambi orario concordati, viaggi istruzione (classe intera).
    Non impattano la banca ore.
    Appaiono nel display con colore distinto (blu).
    """
    __tablename__ = 'variazioni_orario'

    id          = db.Column(db.Integer, primary_key=True)
    data        = db.Column(db.Date,    nullable=False, index=True)
    ora_inizio  = db.Column(db.Integer, nullable=False, default=1)
    ora_fine    = db.Column(db.Integer, nullable=False, default=9)
    classe      = db.Column(db.String(20))
    tipo        = db.Column(db.String(40), nullable=False, default='altro')
    # sorveglianza_prove | simulazione_esame | viaggio_istruzione
    # attivita_alternativa | cambio_orario | progetto | altro
    id_docente_coinvolto = db.Column(db.Integer, db.ForeignKey('docenti.id'), nullable=True)
    descrizione = db.Column(db.String(200))
    note        = db.Column(db.Text)
    creato_il   = db.Column(db.DateTime, default=datetime.utcnow)

    docente_coinvolto = db.relationship('Docente', backref='variazioni', lazy=True)

    def __repr__(self):
        return f"<Variazione {self.data} cl.{self.classe} {self.tipo}>"
