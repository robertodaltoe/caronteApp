"""
Attività Istituzionali — Modulo C.
Gestisce Collegio, Consigli di Classe, Dipartimenti, GLO, Scrutini,
Incontri famiglie, Formazione, con conteggio ore CCNL art.44.
"""
from models import db
from datetime import datetime


# ── Bucket CCNL ──────────────────────────────────────────────────────────────
BUCKET_A  = 'A'   # max 40h: Collegio, info famiglie, formazione residua
BUCKET_B  = 'B'   # max 40h: CdC, dipartimenti, GLO
BUCKET_NO = None  # fuori conteggio: scrutini, esami, riunioni ad hoc (Commissione/Staff...)

TIPI_ATTIVITA = {
    'collegio':           {'label': 'Collegio docenti',          'bucket': BUCKET_A,  'emoji': '▨︎'},
    'consiglio_classe':   {'label': 'Consiglio di classe',       'bucket': BUCKET_B,  'emoji': '◍︎'},
    'dipartimento':       {'label': 'Riunione dipartimento',     'bucket': BUCKET_B,  'emoji': '▥︎'},
    'riunione_materia':   {'label': 'Riunione per materia',      'bucket': BUCKET_B,  'emoji': '▥︎'},
    'glo':                {'label': 'GLO',                       'bucket': BUCKET_B,  'emoji': '◍︎'},
    'incontro_famiglie':  {'label': 'Incontro scuola-famiglia',  'bucket': BUCKET_A,  'emoji': '◍◍◍'},
    'scrutinio':          {'label': 'Scrutinio',                 'bucket': BUCKET_NO, 'emoji': '✎︎'},
    'formazione':         {'label': 'Formazione',                'bucket': BUCKET_A,  'emoji': '△︎'},
    'riunione_referenti': {'label': 'Riunione referenti dip.',   'bucket': BUCKET_B,  'emoji': '◆︎'},
    'altro':              {'label': 'Altro',                     'bucket': BUCKET_A,  'emoji': '◆︎'},
    # Commissione, Staff o altro gruppo ad hoc — titolo libero scelto
    # da Roberto, mai un bucket normativo (art.44 lett.a/b): non è un
    # obbligo contrattuale che rientra nelle 40+40h, stesso principio
    # di "fuori conteggio" già usato per gli scrutini.
    'riunione_extra':     {'label': 'Altra riunione',            'bucket': BUCKET_NO, 'emoji': '◇︎'},
}

LIMITE_BUCKET = 40  # ore annue per bucket A e B


def label_bucket(bucket):
    """Etichette dei tipi che appartengono a un bucket, nell'ordine di
    TIPI_ATTIVITA — usata per spiegare esplicitamente cosa conta in
    ciascun bucket (es. nel Piano Attività Personale, Sessione 57)
    senza duplicare a mano l'elenco in più punti/template."""
    return [info['label'] for info in TIPI_ATTIVITA.values() if info['bucket'] == bucket]


class AttivitaIst(db.Model):
    """Singolo evento istituzionale (una data, un orario)."""
    __tablename__ = 'attivita_ist'

    id          = db.Column(db.Integer, primary_key=True)
    tipo        = db.Column(db.String(30), nullable=False)       # chiave TIPI_ATTIVITA
    titolo      = db.Column(db.String(200), nullable=False)
    data        = db.Column(db.Date, nullable=False)
    ora_inizio  = db.Column(db.String(5), nullable=True)         # es. '13:30'
    ora_fine    = db.Column(db.String(5), nullable=True)         # es. '15:30'
    durata_min  = db.Column(db.Integer, nullable=True)           # minuti (calcolato o manuale)
    note        = db.Column(db.Text, nullable=True)
    creato_il   = db.Column(db.DateTime, default=datetime.utcnow)
    # Solo per CdC e scrutini
    classe      = db.Column(db.String(20), nullable=True)
    # Solo per dipartimenti/materie
    id_dipartimento = db.Column(db.Integer,
                                db.ForeignKey('dipartimenti.id'), nullable=True)
    # Origine: 'manuale' | 'import_piano'
    origine     = db.Column(db.String(20), default='manuale')
    # Presenza del Dirigente Scolastico richiesta — vincolo forte di
    # sovrapposizione per il generatore CdC (Fase 3 Piano Annuale):
    # se richiesta in due eventi, non possono stare nello stesso slot.
    richiede_ds = db.Column(db.Boolean, default=False)

    dipartimento  = db.relationship('Dipartimento')
    partecipanti  = db.relationship('AttivitaIstPartecipante',
                                    back_populates='attivita',
                                    cascade='all, delete-orphan')
    presenze      = db.relationship('AttivitaIstPresenza',
                                    back_populates='attivita',
                                    cascade='all, delete-orphan')

    @property
    def bucket(self):
        return TIPI_ATTIVITA.get(self.tipo, {}).get('bucket')

    @property
    def tipo_label(self):
        return TIPI_ATTIVITA.get(self.tipo, {}).get('label', self.tipo)

    @property
    def tipo_emoji(self):
        return TIPI_ATTIVITA.get(self.tipo, {}).get('emoji', '◆︎')

    @property
    def durata_ore(self):
        """Durata in ore (float), calcolata da ora_inizio/ora_fine o da durata_min."""
        if self.durata_min:
            return round(self.durata_min / 60, 2)
        if self.ora_inizio and self.ora_fine:
            try:
                hi, mi = map(int, self.ora_inizio.split(':'))
                hf, mf = map(int, self.ora_fine.split(':'))
                return round(((hf * 60 + mf) - (hi * 60 + mi)) / 60, 2)
            except Exception:
                pass
        return 0.0

    def __repr__(self):
        return f'<AttivitaIst {self.tipo} {self.data} {self.titolo[:30]}>'


class AttivitaIstPartecipante(db.Model):
    """Docenti previsti per l'evento (preset automatico + aggiustamenti manuali)."""
    __tablename__ = 'attivita_ist_partecipanti'

    id          = db.Column(db.Integer, primary_key=True)
    id_attivita = db.Column(db.Integer,
                            db.ForeignKey('attivita_ist.id'), nullable=False)
    id_docente  = db.Column(db.Integer,
                            db.ForeignKey('docenti.id'), nullable=False)
    preset      = db.Column(db.Boolean, default=True)  # True=generato auto

    attivita = db.relationship('AttivitaIst', back_populates='partecipanti')
    docente  = db.relationship('Docente')

    __table_args__ = (
        db.UniqueConstraint('id_attivita', 'id_docente',
                            name='uq_ist_partecipante'),
    )


class AttivitaIstPresenza(db.Model):
    """Registro presenze effettivo per ogni evento."""
    __tablename__ = 'attivita_ist_presenze'

    id          = db.Column(db.Integer, primary_key=True)
    id_attivita = db.Column(db.Integer,
                            db.ForeignKey('attivita_ist.id'), nullable=False)
    id_docente  = db.Column(db.Integer,
                            db.ForeignKey('docenti.id'), nullable=False)
    # presente | assente | giustificato
    stato       = db.Column(db.String(20), default='presente')
    note        = db.Column(db.String(200), nullable=True)
    # Se assente per assenza già registrata nel sistema →︎ link automatico
    id_assenza_collegata = db.Column(db.Integer,
                                     db.ForeignKey('assenze.id'), nullable=True)
    # Presenza parziale: ore effettive di partecipazione (None = intera durata evento)
    ora_inizio_eff = db.Column(db.String(5), nullable=True)   # es. '13:30'
    ora_fine_eff   = db.Column(db.String(5), nullable=True)   # es. '14:30'

    attivita = db.relationship('AttivitaIst', back_populates='presenze')
    docente  = db.relationship('Docente')
    assenza  = db.relationship('Assenza')

    @property
    def ore_effettive(self):
        """Ore di presenza effettiva: usa ore_inizio/fine_eff se specificate,
        altrimenti la durata intera dell'evento collegato."""
        ini = self.ora_inizio_eff or (self.attivita.ora_inizio if self.attivita else None)
        fin = self.ora_fine_eff   or (self.attivita.ora_fine   if self.attivita else None)
        if ini and fin:
            try:
                hi, mi = map(int, ini.split(':'))
                hf, mf = map(int, fin.split(':'))
                return round(((hf * 60 + mf) - (hi * 60 + mi)) / 60, 2)
            except Exception:
                pass
        return self.attivita.durata_ore if self.attivita else 0.0

    __table_args__ = (
        db.UniqueConstraint('id_attivita', 'id_docente',
                            name='uq_ist_presenza'),
    )
