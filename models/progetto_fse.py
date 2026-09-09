"""
models/progetto_fse.py — Progetti finanziati da fondi strutturali europei
(FSE+/FESR, es. PN "Scuola e competenze" 2021-2027 — Piano Estate e
progetti simili) gestiti in un'area amministrativa isolata, separata
dal Piano delle Attività didattico (Roberto: "non vorrei si mischiasse
dentro quello che è l'iter delle attività didattiche propriamente
dette" — un'area a sé per la segreteria, con le sole date dei moduli
che compaiono in sola lettura nell'Agenda per il controllo incrociato
con gli impegni didattici).

Modello volutamente generico, non legato a "Piano Estate": un
ProgettoFSE ha più ModuloFSE, ogni modulo ha più IncaricoFSE (esperto/
tutor/altro), più SessioneFSE (le date/ore del calendario) e più
PresenzaFSE (i partecipanti, per stimare il rimborso).

Il calcolo dei costi segue lo schema UCS (Unità di Costo Standard) del
PN Scuola e Competenze 2021-2027 quando il progetto è di questo tipo
(tariffa oraria fissa per esperto/tutor + costo di gestione per ora di
presenza di ogni partecipante — verificato sulla lettera di
autorizzazione reale del progetto "Menti in Movimento", CUP
D94D26002650007: 70€/h esperto, 30€/h tutor, 5,10€/h/partecipante),
ma resta configurabile per progetto: un bando "a costi reali" può
impostare percentuale_costi_indiretti invece delle tariffe UCS.
"""
from datetime import datetime
from models import db

STATI_PROGETTO = [
    ('bozza',       'Bozza'),
    ('autorizzato', 'Autorizzato'),
    ('in_corso',    'In corso'),
    ('chiuso',      'Chiuso'),
]

STATI_MODULO = [
    ('bozza',                  'Bozza'),
    ('avviato',                'Avviato'),
    ('chiuso',                 'Chiuso'),
    ('chiuso_anticipatamente', 'Chiuso anticipatamente'),
]

RUOLI_INCARICO = [
    ('esperto',           'Esperto'),
    ('tutor',              'Tutor'),
    ('figura_aggiuntiva',  'Figura aggiuntiva'),
    ('project_manager',    'Project manager / Direzione e coordinamento'),
    ('altro',              'Altro'),
]
RUOLI_INCARICO_LABEL = dict(RUOLI_INCARICO)

TIPI_RAPPORTO = [
    ('dipendente_interno',    'Dipendente interno'),
    ('collaborazione_plurima', 'Dipendente di altra scuola/PA (collaborazione plurima)'),
    ('lavoro_autonomo',       'Lavoro autonomo (esterno)'),
]
TIPI_RAPPORTO_LABEL = dict(TIPI_RAPPORTO)

TIPI_COSTO = [
    ('ucs',   'Costi standard (UCS)'),
    ('reale', 'Costi reali (rendicontazione a piè di lista)'),
]

STATI_INCARICO = [
    ('candidato',   'Candidato'),
    ('incaricato',  'Incaricato'),
    ('rinunciato',  'Rinunciato'),
]

STATI_DOCUMENTO = [
    ('bozza',    'Bozza'),
    ('pronto',   'Pronto'),
    ('protocollato', 'Protocollato'),
    ('caricato', 'Caricato su SIF2127'),
]

# Tipi di documento generabili da modello (vedi routes/progetti_fse.py e
# templates/progetti_fse/documenti/) — fisso perché lega ogni tipo a un
# template HTML specifico, non ai dati del singolo progetto.
TIPI_DOCUMENTO_GENERABILI = [
    ('nomina_commissione',            'Nomina e convocazione commissione di valutazione'),
    ('avviso_selezione',              'Avviso di selezione interna (bando)'),
    ('verbale_commissione',           'Verbale della commissione di valutazione'),
    ('pubblicazione_graduatoria',     'Pubblicazione graduatoria'),
    ('decreto_nomina',                'Decreto di nomina esperti/tutor'),
    ('lettera_incarico',              'Lettera di incarico (personale interno/altra scuola)'),
    ('contratto_autonomo',            'Contratto di lavoro autonomo (esterni)'),
    ('decreto_assunzione_bilancio',   'Decreto di assunzione al bilancio'),
    ('decreto_direzione_coordinamento', 'Decreto incarico Direzione e Coordinamento (Project Manager)'),
    ('dichiarazione_avvio_modulo',    'Dichiarazione di avvio modulo'),
    ('dichiarazione_insussistenza',   'Dichiarazione DS insussistenza conflitto di interessi'),
]
TIPI_DOCUMENTO_GENERABILI_LABEL = dict(TIPI_DOCUMENTO_GENERABILI)


class ProgettoFSE(db.Model):
    __tablename__ = 'progetti_fse'

    id                  = db.Column(db.Integer, primary_key=True)
    titolo              = db.Column(db.String(200), nullable=False)
    codice_progetto     = db.Column(db.String(80))
    cup                 = db.Column(db.String(30))
    programma           = db.Column(db.String(120))   # es. 'PN "Scuola e competenze" 2021-2027'
    fondo               = db.Column(db.String(40))     # es. 'FSE+', 'FESR'
    obiettivo_specifico = db.Column(db.String(40))     # es. 'ESO4.6'
    azione              = db.Column(db.String(40))     # es. 'ESO4.6.A4.A'
    anno_scol           = db.Column(db.String(9))
    importo_autorizzato = db.Column(db.Numeric(10, 2))
    stato               = db.Column(db.String(20), default='bozza')

    tipo_costo                       = db.Column(db.String(10), default='ucs')
    tariffa_esperto                  = db.Column(db.Numeric(6, 2))   # es. 70.00 €/h
    tariffa_tutor                    = db.Column(db.Numeric(6, 2))   # es. 30.00 €/h
    costo_gestione_ora_partecipante  = db.Column(db.Numeric(6, 2))   # es. 5.10 €/h/partecipante
    # Costi indiretti: solo per progetti "a costi reali" che li prevedono
    # esplicitamente nel bando — NULL/0 = non previsti (es. Piano Estate,
    # che essendo a UCS li incorpora già nelle tariffe sopra).
    percentuale_costi_indiretti      = db.Column(db.Numeric(5, 2))
    importo_costi_indiretti_fisso    = db.Column(db.Numeric(10, 2))

    riferimento_avviso        = db.Column(db.String(300))  # estremi avviso ministeriale
    riferimento_bando_interno = db.Column(db.String(300))
    note_ammissibilita        = db.Column(db.Text)  # spese ammissibili/non ammissibili (testo libero)

    # Premesse amministrative specifiche del progetto: confrontando i
    # modelli reali del DS (avviso di selezione e decreto di nomina di
    # "Menti in Movimento"), le quattro frasi seguenti ricorrono
    # IDENTICHE parola per parola in entrambi i documenti — cambiano
    # solo gli estremi (protocollo/data/importo). Il testo delle frasi è
    # quindi fisso nel template del documento generato; qui si
    # registrano SOLO i dati pienamente variabili, una volta per
    # progetto, invece di farli ridigitare per intero ad ogni
    # generazione. Tutti opzionali: una frase compare nel documento solo
    # se i suoi estremi sono stati compilati.
    prot_nota_autorizzazione       = db.Column(db.String(60))   # "VISTO il documento autorizzativo, nota di autorizzazione prot. n. ..."
    data_nota_autorizzazione       = db.Column(db.Date)
    prot_decreto_assunzione_bilancio = db.Column(db.String(60))  # "VISTO il decreto ... di formale assunzione al Programma Annuale ..."
    data_decreto_assunzione_bilancio = db.Column(db.Date)
    anno_esercizio_finanziario     = db.Column(db.String(9))    # es. '2026' — anno del Programma Annuale citato
    prot_azione_disseminazione     = db.Column(db.String(60))   # "VISTA la propria azione di disseminazione ..."
    data_azione_disseminazione     = db.Column(db.Date)
    # La delibera del CdI di adesione ha una struttura a due estremi
    # (numero+data della delibera, protocollo+data della trascrizione)
    # troppo composita per due soli campi puliti: resta una citazione
    # atomica in un unico campo, con lo stesso trattamento già usato per
    # riferimento_avviso/riferimento_bando_interno.
    riferimento_delibera_adesione_cdi = db.Column(db.String(200))  # es. "n. 191 del 18.05.2026, prot. 8311 del 29.05.2026"

    # Capitoli di bilancio dove viene iscritto il finanziamento — usati
    # solo dal decreto di assunzione al bilancio.
    capitolo_entrata = db.Column(db.String(300))
    capitolo_spesa    = db.Column(db.String(300))

    # Premesse ulteriori non coperte dalle quattro frasi standard sopra
    # (bandi con formulazioni atipiche) — usarlo solo in casi non
    # standard: la via principale resta compilare i campi strutturati.
    premesse_specifiche       = db.Column(db.Text)

    creato_il = db.Column(db.DateTime, default=datetime.utcnow)
    creato_da = db.Column(db.String(80))

    moduli    = db.relationship('ModuloFSE', backref='progetto',
                                 cascade='all, delete-orphan', order_by='ModuloFSE.id')
    documenti = db.relationship('DocumentoFSE', backref='progetto',
                                 cascade='all, delete-orphan')

    @property
    def importo_totale_moduli(self):
        return sum((m.importo_autorizzato or 0) for m in self.moduli)


class ModuloFSE(db.Model):
    __tablename__ = 'moduli_fse'

    id                       = db.Column(db.Integer, primary_key=True)
    id_progetto              = db.Column(db.Integer, db.ForeignKey('progetti_fse.id'), nullable=False)
    codice_esterno           = db.Column(db.String(30))  # codice piattaforma (es. SIF2127)
    titolo                   = db.Column(db.String(200), nullable=False)
    tipologia                = db.Column(db.String(200))
    ore                      = db.Column(db.Integer, nullable=False, default=30)
    n_partecipanti_previsti  = db.Column(db.Integer)
    n_partecipanti_minimo    = db.Column(db.Integer, default=9)
    importo_autorizzato      = db.Column(db.Numeric(10, 2))
    stato                    = db.Column(db.String(30), default='bozza')
    data_inizio              = db.Column(db.Date)
    data_fine                = db.Column(db.Date)
    note                     = db.Column(db.Text)

    incarichi = db.relationship('IncaricoFSE', backref='modulo',
                                 cascade='all, delete-orphan')
    sessioni  = db.relationship('SessioneFSE', backref='modulo',
                                 cascade='all, delete-orphan', order_by='SessioneFSE.data')
    presenze  = db.relationship('PresenzaFSE', backref='modulo',
                                 cascade='all, delete-orphan')

    @property
    def ore_totali_presenza(self):
        return sum((p.ore_presenza or 0) for p in self.presenze)

    def costo_gestione_stimato(self):
        """Stima del costo di gestione UCS: € per ora di presenza dei
        migliori N partecipanti (N = n_partecipanti_previsti dichiarati
        in candidatura) — replica la logica di SIF2127 descritta nella
        lettera di autorizzazione (ordina per ore di presenza
        decrescenti, riconosce solo i primi N)."""
        tariffa = self.progetto.costo_gestione_ora_partecipante if self.progetto else None
        if not tariffa:
            return None
        ore_ordinate = sorted((float(p.ore_presenza or 0) for p in self.presenze), reverse=True)
        n = self.n_partecipanti_previsti or len(ore_ordinate)
        return round(sum(ore_ordinate[:n]) * float(tariffa), 2)

    def costo_formazione_previsto(self):
        """Somma dei costi previsti (tariffa × ore previste) di tutti
        gli incarichi del modulo."""
        totale = 0.0
        ha_dati = False
        for inc in self.incarichi:
            if inc.costo_previsto is not None:
                totale += inc.costo_previsto
                ha_dati = True
        return totale if ha_dati else None


class IncaricoFSE(db.Model):
    __tablename__ = 'incarichi_fse'

    id               = db.Column(db.Integer, primary_key=True)
    id_modulo        = db.Column(db.Integer, db.ForeignKey('moduli_fse.id'), nullable=False)
    id_docente       = db.Column(db.Integer, db.ForeignKey('docenti.id'), nullable=True)
    nome_esterno     = db.Column(db.String(120))  # se non è un docente già censito in CaronteApp
    ruolo            = db.Column(db.String(30), nullable=False)
    tipo_rapporto    = db.Column(db.String(30))
    tariffa_oraria   = db.Column(db.Numeric(6, 2))
    ore_previste     = db.Column(db.Numeric(6, 2))
    ore_rendicontate = db.Column(db.Numeric(6, 2))
    stato            = db.Column(db.String(30), default='incaricato')
    note             = db.Column(db.Text)

    # Dati anagrafici necessari solo per generare il contratto di lavoro
    # autonomo (esterni/lavoratori autonomi) — non richiesti per il
    # personale interno, che riceve una lettera di incarico.
    luogo_nascita        = db.Column(db.String(120))
    data_nascita         = db.Column(db.Date)
    codice_fiscale       = db.Column(db.String(16))
    indirizzo_residenza  = db.Column(db.String(200))

    docente = db.relationship('Docente')

    @property
    def nome_completo(self):
        if self.docente:
            return f'{self.docente.cognome} {self.docente.nome}'
        return self.nome_esterno or '—'

    @property
    def costo_previsto(self):
        if self.tariffa_oraria is None or self.ore_previste is None:
            return None
        return round(float(self.tariffa_oraria) * float(self.ore_previste), 2)

    @property
    def costo_rendicontato(self):
        if self.tariffa_oraria is None or self.ore_rendicontate is None:
            return None
        return round(float(self.tariffa_oraria) * float(self.ore_rendicontate), 2)

    @property
    def tipo_rapporto_label(self):
        etichette = {
            'dipendente_interno':     'dipendente in servizio presso questa Amministrazione scolastica',
            'collaborazione_plurima': 'dipendente in servizio presso altra Istituzione scolastica (collaborazione plurima)',
            'lavoro_autonomo':        'soggetto privato esterno persona fisica (lavoratore autonomo)',
        }
        return etichette.get(self.tipo_rapporto, TIPI_RAPPORTO_LABEL.get(self.tipo_rapporto, '—'))


class SessioneFSE(db.Model):
    """Singolo incontro/lezione del modulo — usata sia per il calendario
    interno sia per la voce di sola consultazione nell'Agenda didattica
    (controllo sovrapposizioni con gli impegni scolastici dei docenti
    incaricati)."""
    __tablename__ = 'sessioni_fse'

    id         = db.Column(db.Integer, primary_key=True)
    id_modulo  = db.Column(db.Integer, db.ForeignKey('moduli_fse.id'), nullable=False)
    data       = db.Column(db.Date, nullable=False)
    ora_inizio = db.Column(db.String(5))
    ora_fine   = db.Column(db.String(5))
    note       = db.Column(db.Text)


class PresenzaFSE(db.Model):
    """Anagrafica + ore di presenza di ciascun partecipante (studente) al
    modulo — usata per stimare il costo di gestione (UCS) e per
    verificare la soglia del 75% necessaria per l'attestato finale."""
    __tablename__ = 'presenze_fse'

    id             = db.Column(db.Integer, primary_key=True)
    id_modulo      = db.Column(db.Integer, db.ForeignKey('moduli_fse.id'), nullable=False)
    cognome        = db.Column(db.String(80), nullable=False)
    nome           = db.Column(db.String(80), nullable=False)
    codice_fiscale = db.Column(db.String(16))
    ore_presenza   = db.Column(db.Numeric(6, 2), default=0)

    def frequenza_percentuale(self, ore_modulo):
        if not ore_modulo:
            return 0
        return round(float(self.ore_presenza or 0) / ore_modulo * 100, 1)


class DocumentoFSE(db.Model):
    """Un documento del ciclo di vita del progetto (avviso, decreto,
    verbale, dichiarazione, incarico, ecc.) — generato da modello o
    caricato a mano, tracciato per fase/stato."""
    __tablename__ = 'documenti_fse'

    id             = db.Column(db.Integer, primary_key=True)
    id_progetto    = db.Column(db.Integer, db.ForeignKey('progetti_fse.id'), nullable=False)
    id_modulo      = db.Column(db.Integer, db.ForeignKey('moduli_fse.id'), nullable=True)
    id_incarico    = db.Column(db.Integer, db.ForeignKey('incarichi_fse.id'), nullable=True)
    tipo           = db.Column(db.String(60), nullable=False)  # slug tipo documento
    fase           = db.Column(db.String(40))
    titolo         = db.Column(db.String(200))
    protocollo     = db.Column(db.String(60))
    data_documento = db.Column(db.Date)
    file_path      = db.Column(db.String(300))
    stato          = db.Column(db.String(20), default='bozza')
    note           = db.Column(db.Text)
    creato_il      = db.Column(db.DateTime, default=datetime.utcnow)

    modulo   = db.relationship('ModuloFSE')
    incarico = db.relationship('IncaricoFSE')
