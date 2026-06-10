from models import db
from datetime import datetime

GIORNI = ['Lunedì','Martedì','Mercoledì','Giovedì','Venerdì','Sabato']

# Tabella associativa attività <-> classi
attivita_classi = db.Table('attivita_classi',
    db.Column('id_attivita', db.Integer, db.ForeignKey('attivita_fuori_aula.id'), primary_key=True),
    db.Column('classe', db.String(20), primary_key=True),
)

# Tabella associativa attività <-> docenti accompagnatori
attivita_accompagnatori = db.Table('attivita_accompagnatori',
    db.Column('id_attivita', db.Integer, db.ForeignKey('attivita_fuori_aula.id'), primary_key=True),
    db.Column('id_docente', db.Integer, db.ForeignKey('docenti.id'), primary_key=True),
)


class AttivitaFuoriAula(db.Model):
    __tablename__ = 'attivita_fuori_aula'

    id           = db.Column(db.Integer, primary_key=True)
    tipo         = db.Column(db.String(20), nullable=False)
    # gita | progetto | fsl

    descrizione  = db.Column(db.String(200))
    data_inizio  = db.Column(db.Date, nullable=False)
    data_fine    = db.Column(db.Date, nullable=False)

    # Ricorrenza: 'giornaliera' o 'settimanale'
    ricorrenza   = db.Column(db.String(20), default='giornaliera')
    # Per ricorrenza settimanale: stringa dei giorni selezionati es. "0,2,4" (lun,mer,ven)
    giorni_sett  = db.Column(db.String(20))

    ora_inizio   = db.Column(db.Integer)   # ora inizio (1-9), None = tutta la giornata
    ora_fine     = db.Column(db.Integer)   # ora fine (1-9)

    stato        = db.Column(db.String(20), default='attiva')

    # Ore singole non consecutive (es. '1,3,5')
    ore_singole_json = db.Column(db.String(30), nullable=True)

    @property
    def ore_list(self):
        if self.ore_singole_json:
            return [int(o) for o in self.ore_singole_json.split(',') if o.strip()]
        if self.ora_inizio and self.ora_fine:
            return list(range(self.ora_inizio, self.ora_fine + 1))
        return []

    # Gruppo rimanente: sottogruppo della classe che resta a scuola
    # mentre la classe principale è fuori aula (FSL, gita, ecc.)
    gruppo_rimanente = db.Column(db.Boolean, default=False)
    # Se True: i docenti accompagnatori sono indisponibili,
    # ma la classe NON genera supplenze scoperte (è gestita da questi docenti)
    # Attività collegata al gruppo rimanente (es. Progetto BIM per gli studenti rimasti)
    id_attivita_gruppo = db.Column(db.Integer, db.ForeignKey('attivita_fuori_aula.id'), nullable=True)
    # Ore fuori servizio da riconoscere come credito banca ore
    riconosci_ore_acc = db.Column(db.Boolean, default=False)  # True = riconosci
    ore_acc_inizio    = db.Column(db.Integer)   # prima ora da accreditare
    ore_acc_fine      = db.Column(db.Integer)   # ultima ora da accreditare
    # attiva | annullata

    creato_il    = db.Column(db.DateTime, default=datetime.utcnow)
    note         = db.Column(db.Text)

    # Relazioni
    classi = db.relationship('AttivitaClasse', backref='attivita',
                              cascade='all, delete-orphan', lazy=True)
    accompagnatori = db.relationship('Docente',
                                      secondary=attivita_accompagnatori,
                                      backref='attivita_accompagnate',
                                      lazy=True)

    @property
    def tipo_label(self):
        return {'gita': '✈ Gita', 'progetto': '📐 Progetto',
                'fsl': '🏫 FSL', 'simulazione': '📝 Simulazione'}.get(self.tipo, self.tipo)

    @property
    def classi_list(self):
        return [c.classe for c in self.classi]

    @property
    def giorni_sett_list(self):
        if not self.giorni_sett:
            return []
        return [int(g) for g in self.giorni_sett.split(',') if g]

    def __repr__(self):
        return f"<AttivitaFuoriAula {self.tipo} {self.data_inizio}–{self.data_fine}>"


class AttivitaClasse(db.Model):
    __tablename__ = 'attivita_classi_detail'

    id           = db.Column(db.Integer, primary_key=True)
    id_attivita  = db.Column(db.Integer, db.ForeignKey('attivita_fuori_aula.id'),
                              nullable=False)
    classe       = db.Column(db.String(20), nullable=False)
