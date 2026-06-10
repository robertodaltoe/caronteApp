from models import db

class MigrazioneSlot(db.Model):
    """
    Pianificazione migrazione del gruppo rimanente per ora.
    Quando una classe è parzialmente in gita, il gruppo rimasto
    può migrare in classi diverse a seconda dell'ora.
    """
    __tablename__ = 'migrazione_slots'

    id              = db.Column(db.Integer, primary_key=True)
    id_attivita     = db.Column(db.Integer, db.ForeignKey('attivita_fuori_aula.id'), nullable=False)
    ora             = db.Column(db.Integer, nullable=False)  # 1-9
    classe_dest     = db.Column(db.String(30), nullable=True)   # es. "2A LSU"
    note            = db.Column(db.String(200), nullable=True)
    # Docente automaticamente associato alla gestione del gruppo in quell'ora
    id_docente_assegnato = db.Column(db.Integer, db.ForeignKey('docenti.id'), nullable=True)
    # True = usa il docente della classe destinazione in quell'ora automaticamente
    usa_docente_automatico = db.Column(db.Boolean, default=False)

    attivita = db.relationship('AttivitaFuoriAula', backref='migrazione_slots')
