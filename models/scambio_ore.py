from models import db
from datetime import datetime

class ScambioOre(db.Model):
    """
    Traccia scambi di ore tra docenti.
    Docente A cede un'ora (va a fare altro / ferie concordate).
    Docente B copre la classe di A — accumula un credito.
    La restituzione può avvenire in data futura non determinata.
    """
    __tablename__ = 'scambi_ore'

    id               = db.Column(db.Integer, primary_key=True)

    # Chi cede l'ora
    id_docente_cede  = db.Column(db.Integer, db.ForeignKey('docenti.id'),
                                  nullable=False, index=True)
    # Chi copre (può essere None se non ancora definito)
    id_docente_copre = db.Column(db.Integer, db.ForeignKey('docenti.id'),
                                  nullable=True)

    # Ora ceduta
    data_cessione    = db.Column(db.Date,    nullable=False, index=True)
    ora_cessione     = db.Column(db.Integer, nullable=False)   # 1-9
    classe           = db.Column(db.String(20))

    # Tipo scambio
    tipo             = db.Column(db.String(30), default='scambio')
    # scambio | ferie_concordate | sorveglianza | simulazione |
    # attivita_alternativa | invalsi | commissione | altro

    # Restituzione (opzionale)
    data_restituzione_prevista = db.Column(db.Date, nullable=True)
    data_restituzione_effettiva= db.Column(db.Date, nullable=True)
    ora_restituzione           = db.Column(db.Integer, nullable=True)
    classe_restituzione        = db.Column(db.String(20), nullable=True)

    # Stato
    stato            = db.Column(db.String(20), default='aperto')
    # aperto | restituito | annullato

    # Note
    note_display     = db.Column(db.String(200))   # visibile nel display
    note_interne     = db.Column(db.Text)

    # FK alla supplenza generata (se applicabile)
    id_supplenza     = db.Column(db.Integer, db.ForeignKey('supplenze.id'),
                                  nullable=True)

    creato_il        = db.Column(db.DateTime, default=datetime.utcnow)
    modificato_il    = db.Column(db.DateTime, default=datetime.utcnow,
                                  onupdate=datetime.utcnow)

    # Relazioni
    docente_cede  = db.relationship('Docente', foreign_keys=[id_docente_cede],
                                     backref='ore_cedute',  lazy=True)
    docente_copre = db.relationship('Docente', foreign_keys=[id_docente_copre],
                                     backref='ore_coperte', lazy=True)
    supplenza     = db.relationship('Supplenza', backref='scambio', lazy=True)

    @property
    def giorni_aperti(self):
        if self.stato != 'aperto':
            return 0
        return (datetime.now().date() - self.data_cessione).days

    @property
    def restituzione_in_ritardo(self):
        """True se c'è una data prevista superata."""
        if not self.data_restituzione_prevista:
            return False
        return (self.stato == 'aperto' and
                datetime.now().date() > self.data_restituzione_prevista)

    def __repr__(self):
        return (f"<Scambio {self.data_cessione} "
                f"cede:{self.id_docente_cede} "
                f"copre:{self.id_docente_copre} "
                f"stato:{self.stato}>")
