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
        """Usa l'importo liquidato dove già noto (più vicino alla spesa
        reale), altrimenti il previsto — così il saldo del capitolo
        riflette le liquidazioni via via che avvengono."""
        return round(sum(
            (a.importo_liquidato if a.importo_liquidato is not None else a.importo) or 0
            for a in self.assegnazioni), 2)

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


class PersonaleAta(db.Model):
    """Anagrafica minima del personale ATA, SOLO per poter assegnare
    incarichi di contrattazione a chi non è un docente (Docente è un
    modello pensato per l'orario/le lezioni, non adatto all'ATA) —
    Roberto: "l'inserimento è finalizzato alla sola assegnazione degli
    incarichi in questa parte di Caronte", niente orario/assenze/altro
    per queste persone, solo nome e cognome per comparire nelle
    assegnazioni e nella lettera di incarico."""
    __tablename__ = 'personale_ata'

    id        = db.Column(db.Integer, primary_key=True)
    cognome   = db.Column(db.String(60), nullable=False)
    nome      = db.Column(db.String(60), nullable=True)
    attivo    = db.Column(db.Boolean, default=True)
    note      = db.Column(db.String(200), nullable=True)
    creato_il = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<PersonaleAta {self.cognome} {self.nome or ""}>'


class AssegnazioneContrattazione(db.Model):
    """Importo assegnato a un docente O a un ATA (esattamente uno dei
    due, vedi il vincolo CHECK sotto) dentro un capitolo — la riga da
    cui nasce (in futuro) la lettera di incarico."""
    __tablename__ = 'contrattazione_assegnazioni'

    id            = db.Column(db.Integer, primary_key=True)
    id_capitolo   = db.Column(db.Integer, db.ForeignKey('contrattazione_capitoli.id'), nullable=False, index=True)
    id_docente    = db.Column(db.Integer, db.ForeignKey('docenti.id'), nullable=True, index=True)
    id_personale_ata = db.Column(db.Integer, db.ForeignKey('personale_ata.id'), nullable=True, index=True)
    # Riferimento al catalogo (models.TipoIncaricoContrattazione) per
    # recuperare il testo descrittivo esteso nella lettera di incarico —
    # nullable: un'assegnazione può restare solo testo libero se non c'è
    # ancora una voce di catalogo corrispondente.
    id_tipo_incarico = db.Column(db.Integer, db.ForeignKey('contrattazione_tipi_incarico.id'), nullable=True)
    descrizione   = db.Column(db.String(200), nullable=False)   # es. "Collaboratore del DS", "Tutor PCTO 4ALSP"
    unita         = db.Column(db.Float, nullable=True)          # es. n. ore, n. unità — solo informativo
    # Importo PREVISTO, quello comunicato nella lettera di incarico —
    # non viene mai sovrascritto in silenzio quando si liquida (vedi
    # importo_liquidato sotto): Roberto lo ha chiesto esplicitamente,
    # "potrebbe subire variazioni" e la differenza deve restare
    # visibile, non persa riscrivendo lo stesso campo.
    importo       = db.Column(db.Float, nullable=False, default=0.0)
    stato         = db.Column(db.String(20), nullable=False, default='previsto')
    # Valorizzati solo quando l'incarico passa a 'liquidato' (azione
    # dedicata "Liquida", vedi routes/contrattazione.py::assegnazione_liquida):
    # l'importo definitivo, se diverso da quello previsto, e quando.
    # Da qui nascera' il documento "Retribuzione fondi MOF" (per ora non
    # ancora generato: manca il modello che Roberto fornira').
    importo_liquidato  = db.Column(db.Float, nullable=True)
    data_liquidazione  = db.Column(db.Date, nullable=True)
    note          = db.Column(db.Text, nullable=True)
    creato_il     = db.Column(db.DateTime, default=datetime.utcnow)
    creato_da     = db.Column(db.String(80), nullable=True)
    modificato_il = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    docente = db.relationship('Docente')
    personale_ata = db.relationship('PersonaleAta')
    tipo_incarico = db.relationship('TipoIncaricoContrattazione')
    storico_spostamenti = db.relationship('StoricoSpostamentoCapitolo',
                                           backref='assegnazione', cascade='all, delete-orphan',
                                           lazy=True, order_by='StoricoSpostamentoCapitolo.data.desc()')

    __table_args__ = (
        db.CheckConstraint('(id_docente IS NOT NULL) OR (id_personale_ata IS NOT NULL)',
                           name='ck_contrattazione_assegnazione_beneficiario'),
    )

    @property
    def beneficiario(self):
        """Il Docente o il PersonaleAta a cui è assegnato l'incarico —
        esattamente uno dei due, mai nessuno (vincolo CHECK sopra)."""
        return self.docente if self.id_docente else self.personale_ata

    @property
    def beneficiario_tipo(self):
        return 'docente' if self.id_docente else 'ata'

    @property
    def beneficiario_nome_completo(self):
        b = self.beneficiario
        return f'{b.cognome} {b.nome or ""}'.strip() if b else '—'


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


class TipoIncaricoContrattazione(db.Model):
    """Catalogo dei tipi di incarico, con il testo descrittivo esteso
    ('mansionario') che la lettera di incarico riporta nella sezione
    'Elenco descrittivo attività' — SOLO per gli incarichi davvero
    assegnati a qualcuno, mai l'intero catalogo (Roberto: "nella tabella
    dobbiamo riportare solo i punti relativi agli incarichi che
    effettivamente andremo ad assegnare").

    Gestito a mano dalla segreteria (anche con l'import massivo da testo
    incollato, vedi routes/contrattazione.py::catalogo_importa): il
    testo è materia legale/contrattuale, non lo si genera né lo si
    trascrive in automatico da fonti esterne.
    """
    __tablename__ = 'contrattazione_tipi_incarico'

    id                  = db.Column(db.Integer, primary_key=True)
    numero_riferimento  = db.Column(db.String(20), nullable=True)   # es. "1", "2", "28 bis" — come nel modello del DS
    nome                = db.Column(db.String(150), nullable=False)
    testo_riferimento   = db.Column(db.Text, nullable=False)
    attivo              = db.Column(db.Boolean, default=True)
    creato_il           = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<TipoIncaricoContrattazione {self.nome}>'


class ImpostazioniLetteraContrattazione(db.Model):
    """Riferimenti normativi/anno che cambiano di anno in anno nella
    lettera di incarico (VISTI, delibere del Collegio, scadenza della
    relazione finale) — una riga per anno scolastico, compilata dalla
    segreteria. I VISTI di legge nazionale (d.lgs. 165/2001, DPR
    275/1999) non cambiano quasi mai: restano fissi nel template."""
    __tablename__ = 'contrattazione_impostazioni_lettera'

    id                       = db.Column(db.Integer, primary_key=True)
    anno_scol                = db.Column(db.String(9), nullable=False, unique=True)
    riferimento_ccnl         = db.Column(db.String(200), nullable=True)
    riferimento_ptof         = db.Column(db.String(200), nullable=True)
    riferimento_delibere     = db.Column(db.Text, nullable=True)
    scadenza_relazione       = db.Column(db.String(100), nullable=True)   # es. "10 maggio"
    nota_valorizzazione      = db.Column(db.Text, nullable=True)
    aggiornato_il            = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class LetteraIncaricoProtocollo(db.Model):
    """Numero/data di protocollo della lettera di incarico CUMULATIVA di
    un docente per un anno scolastico — Roberto: "dobbiamo tenere
    traccia dei numeri di protocollo delle lettere di assegnazione in
    seguito alla loro elaborazione". Una riga per (docente, anno): la
    lettera generata da routes/contrattazione.py::lettera_genera resta
    sempre una sola per persona per anno (cumulativa di tutti i suoi
    incarichi), quindi un solo protocollo la riguarda."""
    __tablename__ = 'contrattazione_lettere_protocollo'

    id                 = db.Column(db.Integer, primary_key=True)
    id_docente         = db.Column(db.Integer, db.ForeignKey('docenti.id'), nullable=True, index=True)
    id_personale_ata   = db.Column(db.Integer, db.ForeignKey('personale_ata.id'), nullable=True, index=True)
    anno_scol          = db.Column(db.String(9), nullable=False)
    numero_protocollo  = db.Column(db.String(40), nullable=True)
    data_protocollo    = db.Column(db.Date, nullable=True)
    note               = db.Column(db.Text, nullable=True)
    creato_il          = db.Column(db.DateTime, default=datetime.utcnow)
    aggiornato_il      = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    docente = db.relationship('Docente')
    personale_ata = db.relationship('PersonaleAta')

    # Due UNIQUE separati invece di uno solo su entrambe le colonne:
    # SQLite (come lo standard SQL) non considera duplicati due NULL,
    # quindi ciascun vincolo di fatto si applica solo alle righe del
    # proprio tipo (docente con id_personale_ata sempre NULL, e
    # viceversa) — stesso principio del CHECK su AssegnazioneContrattazione.
    __table_args__ = (
        db.UniqueConstraint('id_docente', 'anno_scol', name='uq_contrattazione_lettera_protocollo_docente'),
        db.UniqueConstraint('id_personale_ata', 'anno_scol', name='uq_contrattazione_lettera_protocollo_ata'),
        db.CheckConstraint('(id_docente IS NOT NULL) OR (id_personale_ata IS NOT NULL)',
                           name='ck_contrattazione_lettera_protocollo_beneficiario'),
    )

    @property
    def beneficiario(self):
        return self.docente if self.id_docente else self.personale_ata
