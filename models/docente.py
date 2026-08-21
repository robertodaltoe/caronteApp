from models import db
from datetime import datetime

# Etichette leggibili per Docente.tipo_contratto — unica fonte di verità,
# usata da tutti i form e le pagine che mostrano il tipo di contratto.
# Nota (chiarito da Roberto, sessione Task 47): i valori memorizzati non
# cambiano (nessuna migrazione sui dati esistenti), è cambiata solo
# l'etichetta mostrata, perché due punti dell'app la mostravano diversa
# e comunque imprecisa:
#   - valore 'TD_GS'     -> è un TD con contratto fisso fino al 30 giugno
#                            (nessuna proroga), NON fino al giorno scrutini
#                            come il nome lasciava intendere.
#   - valore 'supplente' -> è in realtà il supplente breve la cui supplenza,
#                            se rientra nell'art. 37 CCNL, viene prorogata
#                            d'ufficio dal termine delle lezioni fino al
#                            giorno conclusivo degli scrutini (GS).
TIPO_CONTRATTO_LABELS = {
    'TI':            'TI — Indeterminato',
    'IRC':           'IRC — Religione',
    'TD_annuale':    'TD annuale',
    'TD_GS':         'TD 30 giugno',
    'supplente':     'TD fino a GS',
    'potenziamento': 'Potenziamento',
}

# Versione compatta della stessa etichetta, per colonne strette (es.
# elenco docenti) dove il testo esteso forza lo scroll orizzontale.
TIPO_CONTRATTO_LABELS_BREVI = {
    'TI':            'TI',
    'IRC':           'IRC',
    'TD_annuale':    'TD ann.',
    'TD_GS':         'TD 30/6',
    'supplente':     'TD-GS',
    'potenziamento': 'Pot.',
}


class Docente(db.Model):
    __tablename__ = 'docenti'

    id            = db.Column(db.Integer, primary_key=True)
    cognome       = db.Column(db.String(80),  nullable=False)
    nome          = db.Column(db.String(80),  nullable=False)
    nome_display  = db.Column(db.String(80))   # es. "FERRARI M."
    materia       = db.Column(db.String(120))   # campo legacy testuale, vedi id_classe_concorso
    # Usato come "versione" per il controllo di concorrenza ottimistico
    # nel form di modifica (vedi routes/docenti.py::modifica): se due
    # persone aprono la scheda dello stesso docente, chi salva per
    # secondo viene avvisato invece di sovrascrivere in silenzio.
    modificato_il = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    # Classe di concorso ufficiale del docente (es. A026 - Matematica).
    # Sostituisce gradualmente il campo libero 'materia' qui sopra.
    id_classe_concorso = db.Column(db.Integer, db.ForeignKey('classi_concorso.id'), nullable=True)
    ore_contratto = db.Column(db.Integer, default=18)
    attivo        = db.Column(db.Boolean, default=True)
    # Ruolo didattico: 'titolare' (docente della materia) o 'itp' (ITP — compresenza laboratorio)
    ruolo         = db.Column(db.String(20), default='titolare')
    # Per gli ITP: titolare della cattedra abbinata. I debiti che l'ITP
    # assegna (es. nei recuperi) confluiscono nel conteggio del titolare.
    id_titolare_riferimento = db.Column(db.Integer, db.ForeignKey('docenti.id'), nullable=True)
    titolare_riferimento    = db.relationship('Docente', remote_side=[id], foreign_keys=[id_titolare_riferimento])
    # Docenti su più scuole
    altra_scuola    = db.Column(db.String(120), nullable=True)   # nome istituto secondario
    giorni_presenza = db.Column(db.String(20),  nullable=True)   # es. '0,2,4' = lun/mer/ven
    # Part-time esclusivo (solo questa scuola, contratto ridotto)
    part_time         = db.Column(db.Boolean, default=False)
    ore_contratto_pt  = db.Column(db.Integer, nullable=True)  # ore effettive contratto PT
    # Orario spezzato: JSON es. {'0':3,'3':2} = lun dalla 3a, gio dalla 2a va all'altra sede
    ora_uscita_json   = db.Column(db.String(60), nullable=True)

    @property
    def tipo_contratto_label(self):
        return TIPO_CONTRATTO_LABELS.get(self.tipo_contratto, self.tipo_contratto)

    @property
    def tipo_contratto_label_breve(self):
        return TIPO_CONTRATTO_LABELS_BREVI.get(self.tipo_contratto, self.tipo_contratto)

    @property
    def ora_uscita_map(self):
        import json
        if not self.ora_uscita_json:
            return {}
        try:
            return {int(k): int(v) for k,v in json.loads(self.ora_uscita_json).items()}
        except:
            return {}

    @property
    def giorni_presenza_list(self):
        if not self.giorni_presenza:
            return []
        return [int(g) for g in self.giorni_presenza.split(',') if g.strip().isdigit()]

    @property
    def multi_sede(self):
        return bool(self.altra_scuola and self.altra_scuola.strip())
    email         = db.Column(db.String(120))
    note           = db.Column(db.Text)
    tipo_contratto       = db.Column(db.String(30))
    # Gestione pluriennale: quando è arrivato e se/quando esce
    anno_scol_inizio  = db.Column(db.String(9), nullable=True)   # es. '2025-2026'; NULL = TI storico
    anno_scol_uscita  = db.Column(db.String(9), nullable=True)   # NULL = ancora in servizio
    motivo_uscita     = db.Column(db.String(20), nullable=True)  # 'trasferimento'|'pensionamento'|'fine_td'
    # Ore max assegnabili per un anno specifico (sovrascrive ore_contratto/ore_contratto_pt)
    # NULL = usa ore_contratto_pt se presente, altrimenti ore_contratto
    ore_max_anno      = db.Column(db.Integer, nullable=True)
    # Anno scolastico a cui si riferisce ore_max_anno (es. '2026-2027')
    anno_scol_ore_max = db.Column(db.String(9), nullable=True)

    def ore_max_effettive_per_anno(self, anno_scol=None):
        """
        Ore massime assegnabili per un dato anno scolastico.
        Se ore_max_anno è impostato e si riferisce all'anno richiesto, lo usa.
        Altrimenti usa ore_contratto_pt > ore_contratto (già risolti per l'anno,
        vedi part_time_effettivo_per_anno/ore_contratto_pt_effettive_per_anno).
        """
        if (self.ore_max_anno is not None and
                (anno_scol is None or self.anno_scol_ore_max == anno_scol)):
            return self.ore_max_anno
        ore_pt = self.ore_contratto_pt_effettive_per_anno(anno_scol)
        if ore_pt is not None:
            return ore_pt
        return self.ore_contratto or 18

    # Cambio di regime part-time già noto per un anno scolastico futuro
    # (es. oggi a tempo pieno, ma dal 2027-2028 passerà part-time): permette
    # di "preparare" oggi il dato senza toccare il valore usato per l'anno
    # in corso. NULL = nessun cambio programmato, valgono sempre part_time/
    # ore_contratto_pt correnti. Stesso pattern di ore_max_anno/anno_scol_ore_max.
    part_time_prog          = db.Column(db.Boolean, nullable=True)
    ore_contratto_pt_prog   = db.Column(db.Integer, nullable=True)
    anno_scol_part_time_prog = db.Column(db.String(9), nullable=True)

    def part_time_effettivo_per_anno(self, anno_scol=None):
        """Stato part-time per un dato anno scolastico (usa il cambio
        programmato solo se anno_scol coincide con anno_scol_part_time_prog)."""
        if (anno_scol is not None and self.anno_scol_part_time_prog == anno_scol
                and self.part_time_prog is not None):
            return self.part_time_prog
        return self.part_time

    def ore_contratto_pt_effettive_per_anno(self, anno_scol=None):
        """Ore contratto part-time per un dato anno scolastico (idem sopra)."""
        if (anno_scol is not None and self.anno_scol_part_time_prog == anno_scol
                and self.ore_contratto_pt_prog is not None):
            return self.ore_contratto_pt_prog
        return self.ore_contratto_pt

    @property
    def ore_max_effettive(self):
        """Compatibilità: usa ore_max_effettive_per_anno senza filtro anno."""
        return self.ore_max_effettive_per_anno()
    # Presenza fisica nell'anno scolastico corrente
    # 'presente'    = insegna fisicamente qui (default)
    # 'ap_entrante' = assegnazione provvisoria in entrata (titolare altrove, insegna qui)
    # 'ap_uscente'  = assegnazione provvisoria in uscita (titolare qui, insegna altrove)
    # 'aspettativa' = titolare qui ma in aspettativa
    status_presenza   = db.Column(db.String(20), nullable=True, default='presente')
    scuola_ap         = db.Column(db.String(150), nullable=True)  # scuola di provenienza/destinazione AP
    colloqui_giorno      = db.Column(db.Integer)   # 0=lun…5=sab, None=nessuno
    colloqui_ora_inizio  = db.Column(db.Integer)   # ora inizio (1-9)
    colloqui_ora_fine    = db.Column(db.Integer)   # ora fine (1-9)

    @property
    def materia_effettiva(self):
        """
        Materia/disciplina da mostrare nell'interfaccia, presa dal dato
        relazionale univoco (classe di concorso collegata) invece del
        vecchio campo libero 'materia' — che poteva essere scritto a mano
        una volta (es. da un import) e restare disallineato per sempre,
        dato che non si aggiorna mai da solo quando cambia la classe di
        concorso. Fallback sul campo libero solo se la CC non è ancora
        stata impostata (docenti non ancora classificati), per non
        lasciare la visualizzazione vuota.
        """
        if self.classe_concorso:
            return f"{self.classe_concorso.codice} — {self.classe_concorso.nome}"
        return self.materia

    @property
    def colloqui_label(self):
        GIORNI = ['Lunedì','Martedì','Mercoledì','Giovedì','Venerdì','Sabato']
        if self.colloqui_giorno is None:
            return None
        g = GIORNI[self.colloqui_giorno]
        if self.colloqui_ora_inizio and self.colloqui_ora_fine:
            return f"{g} {self.colloqui_ora_inizio}ª–{self.colloqui_ora_fine}ª ora"
        elif self.colloqui_ora_inizio:
            return f"{g} {self.colloqui_ora_inizio}ª ora"
        return g

    @property
    def colloqui_label_breve(self):
        """Come colloqui_label ma compatta (es. "Lun 1ª–2ª"), per colonne
        strette dove "Lunedì 1ª–2ª ora" costringe la tabella a scrollare."""
        GIORNI_BREVI = ['Lun','Mar','Mer','Gio','Ven','Sab']
        if self.colloqui_giorno is None:
            return None
        g = GIORNI_BREVI[self.colloqui_giorno]
        if self.colloqui_ora_inizio and self.colloqui_ora_fine:
            return f"{g} {self.colloqui_ora_inizio}ª–{self.colloqui_ora_fine}ª"
        elif self.colloqui_ora_inizio:
            return f"{g} {self.colloqui_ora_inizio}ª"
        return g

    supplenze_svolte  = db.relationship('Supplenza',        foreign_keys='Supplenza.id_sostituto',  backref='sostituto',  lazy=True)
    supplenze_assente = db.relationship('Supplenza',        foreign_keys='Supplenza.id_assente',    backref='assente',    lazy=True)
    assenze           = db.relationship('Assenza',          backref='docente',  lazy=True)
    movimenti         = db.relationship('MovimentoBancaOre',backref='docente',  lazy=True)
    indisponibilita   = db.relationship('Indisponibilita',  backref='docente',  lazy=True)
    materie_ist       = db.relationship('DocenteMateria', back_populates='docente',
                                         cascade='all, delete-orphan', lazy='select')
    classe_concorso   = db.relationship('ClasseConcorso', back_populates='docenti',
                                         foreign_keys=[id_classe_concorso])
    abilitazioni      = db.relationship('DocenteClasseConcorso', back_populates='docente',
                                         cascade='all, delete-orphan', lazy='select')

    @property
    def classi_concorso_abilitate(self):
        """Tutte le classi di concorso su cui il docente è abilitato
        (sostituisce id_classe_concorso quando servono più abilitazioni)."""
        return [a.classe_concorso for a in self.abilitazioni]

    @property
    def nome_completo(self):
        return f"{self.cognome} {self.nome}".strip()

    @property
    def saldo_banca_ore(self):
        """Somma tutti i minuti dei movimenti (positivi = credito, negativi = debito)."""
        return sum(m.minuti for m in self.movimenti)

    def __repr__(self):
        return f"<Docente {self.cognome} {self.nome}>"


class CoppiaDocenteItp(db.Model):
    """
    Abbinamento esplicito titolare↔ITP sulla stessa cattedra/materia.
    Usato per il recupero estivo: i debiti assegnati dall'ITP vanno
    conteggiati insieme a quelli del titolare quando lo si propone
    come responsabile del gruppo prova.
    Es. Informatica: Landi (titolare) + Luzzi (ITP)
        Tedesco: Fumagalli (titolare) + May (ITP) — anche se May non è
        più disponibile (contratto scaduto), l'abbinamento resta utile
        per il conteggio storico dei debiti assegnati.
    """
    __tablename__ = 'coppie_docente_itp'

    id            = db.Column(db.Integer, primary_key=True)
    id_titolare   = db.Column(db.Integer, db.ForeignKey('docenti.id'), nullable=False)
    id_itp        = db.Column(db.Integer, db.ForeignKey('docenti.id'), nullable=False)
    materia       = db.Column(db.String(100), nullable=True)  # etichetta libera, informativa
    note          = db.Column(db.String(200), nullable=True)
    attiva        = db.Column(db.Boolean, default=True)  # disattivabile senza eliminare lo storico

    titolare = db.relationship('Docente', foreign_keys=[id_titolare])
    itp      = db.relationship('Docente', foreign_keys=[id_itp])

    __table_args__ = (
        db.UniqueConstraint('id_titolare', 'id_itp', name='uq_coppia_titolare_itp'),
    )

    def __repr__(self):
        return f"<CoppiaDocenteItp {self.titolare.cognome if self.titolare else '?'} + {self.itp.cognome if self.itp else '?'}>"


class DocenteContrattoAnno(db.Model):
    """
    Tipo di contratto di un docente PER UN ANNO SCOLASTICO SPECIFICO.

    Docente.tipo_contratto è un campo unico, sempre sovrascritto: va bene
    per "qual è il contratto attuale/più recente", ma un docente con
    contratto annuale (IRC, TD annuale, TD fino a GS...) può cambiare
    tipo da un anno all'altro pur restando la stessa persona — es. un TD
    che entra in ruolo e diventa TI l'anno dopo (caso reale: Agrò,
    TD 30/6 nel 2025-2026, TI dal 2026-2027). Se si limita ad aggiornare
    Docente.tipo_contratto per preparare il nuovo anno, si perde il
    contratto vero dell'anno che sta ancora finendo — sbagliando i
    calcoli "in servizio a questa data" per quell'anno (es. idoneità
    per i recuperi/scrutini di agosto, che guardano proprio il tipo di
    contratto — vedi routes/attivita_ist.py::_non_in_servizio_per_data
    e routes/recupero_costanti.py::CONTRATTI_OK).

    Una riga per docente per anno: se esiste, ha priorità sul campo
    Docente.tipo_contratto (sempre "corrente") per i calcoli relativi a
    quello specifico anno_scol.
    """
    __tablename__ = 'docenti_contratti_anno'

    id             = db.Column(db.Integer, primary_key=True)
    id_docente     = db.Column(db.Integer, db.ForeignKey('docenti.id'), nullable=False)
    anno_scol      = db.Column(db.String(9), nullable=False)
    tipo_contratto = db.Column(db.String(20), nullable=False)
    note           = db.Column(db.String(200), nullable=True)
    creato_il      = db.Column(db.DateTime, default=datetime.utcnow)

    docente = db.relationship('Docente', backref=db.backref(
        'contratti_anno', cascade='all, delete-orphan'))

    __table_args__ = (
        db.UniqueConstraint('id_docente', 'anno_scol', name='uq_docente_contratto_anno'),
    )

    def __repr__(self):
        return f"<DocenteContrattoAnno {self.docente.cognome if self.docente else '?'} {self.anno_scol} {self.tipo_contratto}>"


def tipo_contratto_per_anno(docente, anno_scol):
    """
    Tipo di contratto di un docente PER UN ANNO SCOLASTICO SPECIFICO:
    usa la riga storica (DocenteContrattoAnno) se esiste, altrimenti
    ricade su Docente.tipo_contratto "corrente" — stesso fallback già
    usato in routes/attivita_ist.py::_non_in_servizio_per_data e
    routes/recupero_costanti.py::docenti_idonei_periodo. Da usare
    ovunque si mostri/valuti il contratto di un docente in una vista
    esplicitamente legata a un anno diverso da quello corrente (export,
    riepiloghi) — altrimenti si rischia di mostrare il contratto
    sbagliato per chi ha cambiato tipo tra un anno e l'altro (es. un TD
    che entra in ruolo, caso reale Agrò).
    """
    riga = DocenteContrattoAnno.query.filter_by(
        id_docente=docente.id, anno_scol=anno_scol).first()
    return riga.tipo_contratto if riga else docente.tipo_contratto


def tipo_contratto_label_per_anno(docente, anno_scol):
    """Etichetta leggibile dell'esito di tipo_contratto_per_anno()."""
    tipo = tipo_contratto_per_anno(docente, anno_scol)
    return TIPO_CONTRATTO_LABELS.get(tipo, tipo) if tipo else ''
