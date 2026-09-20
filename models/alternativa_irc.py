"""
Attività alternativa all'insegnamento della religione cattolica (IRC):
adesioni per classe, disponibilità dei docenti, gruppi (uno per slot
orario in cui le classi hanno religione) con il docente assegnato per
tutto l'anno scolastico. Vedi modules/alternativa_irc.py.

Il "quando" NON è duplicato qui: gli slot sono quelli di religione già
presenti in OrarioDocente. Delle adesioni si conserva solo il NUMERO di
studenti per classe, mai i nominativi (dato sulle convinzioni religiose).
"""
from datetime import datetime
from models import db

TIPI_DISPONIBILITA = [
    ('completamento', 'Completamento del contratto (supplente con altro contratto)'),
    ('ore_eccedenti', 'Ore eccedenti l\'orario d\'obbligo'),
]
TIPI_DISPONIBILITA_LABEL = dict(TIPI_DISPONIBILITA)


class AlternativaIrcAdesione(db.Model):
    __tablename__ = 'alternativa_irc_adesioni'

    id         = db.Column(db.Integer, primary_key=True)
    anno_scol  = db.Column(db.String(9), nullable=False)
    classe     = db.Column(db.String(20), nullable=False)   # forma compatta, es. '3ALLI'
    # Studenti che chiedono un docente (attività didattiche/formative o
    # studio con assistenza): sono gli unici che generano ore da coprire.
    n_con_docente = db.Column(db.Integer, nullable=False, default=0)
    # Altre scelte (uscita/ingresso, studio senza assistenza): solo
    # informativo, non genera ore da coprire.
    n_altre       = db.Column(db.Integer, nullable=False, default=0)
    note       = db.Column(db.String(200))

    __table_args__ = (
        db.UniqueConstraint('anno_scol', 'classe', name='uq_alt_irc_adesione'),
    )


class AlternativaIrcDisponibilita(db.Model):
    """Docente che ha dato la propria disponibilità (volontaria) per
    l'anno: solo questi vengono proposti dopo chi completa l'orario."""
    __tablename__ = 'alternativa_irc_disponibilita'

    id         = db.Column(db.Integer, primary_key=True)
    anno_scol  = db.Column(db.String(9), nullable=False)
    id_docente = db.Column(db.Integer, db.ForeignKey('docenti.id'), nullable=False, index=True)
    tipo       = db.Column(db.String(20), nullable=False, default='ore_eccedenti')
    max_ore    = db.Column(db.Integer, nullable=True)   # ore/settimana, NULL = nessun limite dichiarato
    note       = db.Column(db.String(200))

    docente = db.relationship('Docente')

    __table_args__ = (
        db.UniqueConstraint('anno_scol', 'id_docente', name='uq_alt_irc_disp'),
    )


class AlternativaIrcGruppo(db.Model):
    """Un gruppo = uno slot (giorno, ora) in cui una o più classi hanno
    religione. Il docente assegnato è lo stesso per tutto l'anno."""
    __tablename__ = 'alternativa_irc_gruppi'

    id         = db.Column(db.Integer, primary_key=True)
    anno_scol  = db.Column(db.String(9), nullable=False)
    giorno     = db.Column(db.Integer, nullable=False)   # 0=lun … 5=sab
    ora        = db.Column(db.Integer, nullable=False)
    id_docente = db.Column(db.Integer, db.ForeignKey('docenti.id'), nullable=True, index=True)
    # Ultimo livello di priorità della circolare: nuovo contratto da
    # stipulare, docente non ancora noto.
    da_nominare = db.Column(db.Boolean, default=False)
    aula       = db.Column(db.String(50))
    note       = db.Column(db.String(200))
    creato_il  = db.Column(db.DateTime, default=datetime.utcnow)

    docente = db.relationship('Docente')
    classi  = db.relationship('AlternativaIrcGruppoClasse', backref='gruppo',
                              cascade='all, delete-orphan', lazy=True)

    @property
    def classi_list(self):
        return sorted(c.classe for c in self.classi)


class AlternativaIrcGruppoClasse(db.Model):
    __tablename__ = 'alternativa_irc_gruppo_classi'

    id         = db.Column(db.Integer, primary_key=True)
    id_gruppo  = db.Column(db.Integer, db.ForeignKey('alternativa_irc_gruppi.id'), nullable=False, index=True)
    classe     = db.Column(db.String(20), nullable=False)
