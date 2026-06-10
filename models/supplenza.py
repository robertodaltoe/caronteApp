from models import db
from datetime import datetime

class Supplenza(db.Model):
    __tablename__ = 'supplenze'

    id               = db.Column(db.Integer, primary_key=True)
    data             = db.Column(db.Date,    nullable=False, index=True)
    ora              = db.Column(db.Integer, nullable=False)
    classe           = db.Column(db.String(20))
    id_assente       = db.Column(db.Integer, db.ForeignKey('docenti.id'), nullable=True)
    id_sostituto     = db.Column(db.Integer, db.ForeignKey('docenti.id'), nullable=True)
    tipo             = db.Column(db.String(20), default='recupero')
    # recupero | pagamento | completamento | potenziamento | disposizione
    stato            = db.Column(db.String(20), default='scoperta')
    # scoperta | assegnata | annullata | non_assegnabile
    origine          = db.Column(db.String(20), default='manuale')
    # manuale | automatica
    note_display     = db.Column(db.String(200))   # visibile nel display
    note             = db.Column(db.Text)           # solo interne
    creato_il        = db.Column(db.DateTime, default=datetime.utcnow)
    modificato_il    = db.Column(db.DateTime, default=datetime.utcnow,
                                  onupdate=datetime.utcnow)

    @property
    def assegnabile(self):
        return self.stato not in ('annullata', 'non_assegnabile')

    def __repr__(self):
        return f"<Supplenza {self.data} ora {self.ora} cl.{self.classe} stato:{self.stato}>"
