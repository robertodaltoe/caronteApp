"""
models/contrattazione.py — Contrattazione integrativa d'istituto (FIS,
FMOF, PCTO, valorizzazione, supporto organizzativo/didattico...), per
l'uso della segreteria/ufficio contabilità.

Flusso reale (vedi DEVLOG, confermato da Roberto):
1. Si quantificano le economie avanzate dagli anni precedenti per un
   fondo (es. FIS) e si somma l'importo assegnato per l'anno in corso
   (es. il FMOF comunicato dal Dirigente) — FondoContrattazione.
2. Da quel totale si sottrae l'eventuale quota dovuta al DSGA
   (solo per i fondi dove si applica): resta l'importo contrattabile.
3. In contrattazione il contrattabile si divide in capitoli di spesa
   (Valorizzazione, PCTO, Supporto organizzativo, ecc.) — CapitoloContrattazione,
   ciascuno con un proprio importo assegnato.
4. Dentro ogni capitolo si assegna un importo a ciascun docente —
   AssegnazioneContrattazione — con cui si genera la lettera di
   incarico (provvisoria: "potrebbe variare").
5. Un'assegnazione può essere spostata da un capitolo all'altro anche
   dopo la lettera (Roberto: "potrebbero esserci spostamenti tra i vari
   capitoli") — non serve una lettera di rettifica, ma la segreteria
   deve poter vedere che lo spostamento è avvenuto e i saldi devono
   restare sempre coerenti: StoricoSpostamentoCapitolo tiene la traccia,
   mai sovrascritta.

Importi e saldi non sono mai calcolati "a mano" nei template: vedi le
property sotto (saldo_capitolo, importo_contrattabile) — stesso principio
già seguito per Progetti FSE/FESR, per non ripetere l'errore delle
formule Excel che restano indietro quando qualcosa cambia a monte.
"""
from datetime import datetime
from models import db

STATI_ASSEGNAZIONE = [
    ('previsto',   'Previsto'),
    ('comunicato', 'Comunicato (lettera inviata)'),
    ('liquidato',  'Liquidato'),
]
STATI_ASSEGNAZIONE_LABEL = dict(STATI_ASSEGNAZIONE)


class FondoContrattazione(db.Model):
    """Un fondo per anno scolastico (es. 'FMOF', 'FIS', 'Altri fondi').
    Inserito dalla segreteria non appena l'importo è comunicato."""
    __tablename__ = 'contrattazione_fondi'

    id                 = db.Column(db.Integer, primary_key=True)
    anno_scol          = db.Column(db.String(9), nullable=False, index=True)
    nome               = db.Column(db.String(100), nullable=False)
    economie_pregresse = db.Column(db.Float, nullable=False, default=0.0)
    importo_assegnato  = db.Column(db.Float, nullable=False, default=0.0)
    quota_dsga         = db.Column(db.Float, nullable=False, default=0.0)
    note               = db.Column(db.Text, nullable=True)
    creato_il          = db.Column(db.DateTime, default=datetime.utcnow)
    creato_da          = db.Column(db.String(80), nullable=True)

    capitoli = db.relationship('CapitoloContrattazione', backref='fondo',
                                cascade='all, delete-orphan', lazy=True,
                                order_by='CapitoloContrattazione.nome')

    @property
    def totale_disponibile(self):
        """Economie pregresse + importo assegnato quest'anno."""
        return round((self.economie_pregresse or 0) + (self.importo_assegnato or 0), 2)

    @property
    def importo_contrattabile(self):
        """Quanto resta da dividere nei capitoli, dopo la quota DSGA."""
        return round(self.totale_disponibile - (self.quota_dsga or 0), 2)

    @property
    def totale_capitoli_assegnato(self):
        return round(sum(c.importo_assegnato or 0 for c in self.capitoli), 2)

    @property
    def saldo_non_ripartito(self):
        """Quanto del contrattabile non è ancora stato messo in un capitolo."""
        return round(self.importo_contrattabile - self.totale_capitoli_assegnato, 2)


class CapitoloContrattazione(db.Model):
    """Una voce di spesa dentro un fondo (es. 'Valorizzazione', 'PCTO',
    'Supporto alle attività organizzative')."""
    __tablename__ = 'contrattazione_capitoli'

    id                = db.Column(db.Integer, primary_key=True)
    id_fondo          = db.Column(db.Integer, db.ForeignKey('contrattazione_fondi.id'), nullable=False, index=True)
    nome              = db.Column(db.String(150), nullable=False)
    importo_assegnato = db.Column(db.Float, nullable=False, default=0.0)
    note              = db.Column(db.Text, nullable=True)
    creato_il         = db.Column(db.DateTime, default=datetime.utcnow)

    assegnazioni = db.relationship('AssegnazioneContrattazione', backref='capitolo',
                                    lazy=True, foreign_keys='AssegnazioneContrattazione.id_capitolo',
                                    cascade='all, delete-orphan')

    @property
    def totale_assegnato_docenti(self):
        return round(sum(a.importo or 0 for a in self.assegnazioni), 2)

    @property
    def saldo_residuo(self):
        """Positivo = ancora disponibile; negativo = già assegnato più
        di quanto il capitolo preveda (va segnalato, non impedito: la
        segreteria può dover registrare un'assegnazione anche prima di
        aver sistemato l'importo del capitolo)."""
        return round(self.importo_assegnato - self.totale_assegnato_docenti, 2)

    @property
    def sforato(self):
        return self.saldo_residuo < -0.004  # tolleranza arrotondamento


class AssegnazioneContrattazione(db.Model):
    """Importo assegnato a un docente dentro un capitolo — la riga da
    cui nasce (in futuro) la lettera di incarico."""
    __tablename__ = 'contrattazione_assegnazioni'

    id            = db.Column(db.Integer, primary_key=True)
    id_capitolo   = db.Column(db.Integer, db.ForeignKey('contrattazione_capitoli.id'), nullable=False, index=True)
    id_docente    = db.Column(db.Integer, db.ForeignKey('docenti.id'), nullable=False, index=True)
    descrizione   = db.Column(db.String(200), nullable=False)   # es. "Collaboratore del DS", "Tutor PCTO 4ALSP"
    unita         = db.Column(db.Float, nullable=True)          # es. n. ore, n. unità — solo informativo
    importo       = db.Column(db.Float, nullable=False, default=0.0)
    stato         = db.Column(db.String(20), nullable=False, default='previsto')
    note          = db.Column(db.Text, nullable=True)
    creato_il     = db.Column(db.DateTime, default=datetime.utcnow)
    creato_da     = db.Column(db.String(80), nullable=True)
    modificato_il = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    docente = db.relationship('Docente')
    storico_spostamenti = db.relationship('StoricoSpostamentoCapitolo',
                                           backref='assegnazione', cascade='all, delete-orphan',
                                           lazy=True, order_by='StoricoSpostamentoCapitolo.data.desc()')


class StoricoSpostamentoCapitolo(db.Model):
    """Traccia (mai sovrascritta) ogni spostamento di un'assegnazione da
    un capitolo all'altro — Roberto: "l'importante è che la segreteria
    tenga traccia dello spostamento", nessuna lettera di rettifica
    richiesta, ma deve restare visibile chi ha spostato cosa e quando."""
    __tablename__ = 'contrattazione_storico_spostamenti'

    id                     = db.Column(db.Integer, primary_key=True)
    id_assegnazione        = db.Column(db.Integer, db.ForeignKey('contrattazione_assegnazioni.id'), nullable=False, index=True)
    id_capitolo_precedente = db.Column(db.Integer, db.ForeignKey('contrattazione_capitoli.id'), nullable=True)
    id_capitolo_nuovo      = db.Column(db.Integer, db.ForeignKey('contrattazione_capitoli.id'), nullable=True)
    importo_al_momento     = db.Column(db.Float, nullable=False)
    motivo                 = db.Column(db.String(200), nullable=True)
    data                   = db.Column(db.DateTime, default=datetime.utcnow)
    utente                 = db.Column(db.String(80), nullable=True)

    capitolo_precedente = db.relationship('CapitoloContrattazione', foreign_keys=[id_capitolo_precedente])
    capitolo_nuovo      = db.relationship('CapitoloContrattazione', foreign_keys=[id_capitolo_nuovo])
