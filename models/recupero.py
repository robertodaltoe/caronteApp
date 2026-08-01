"""
Modulo Corsi di Recupero
"""
from models import db
from datetime import datetime


class RecuperoDocente(db.Model):
    """Docente disponibile per i corsi di recupero."""
    __tablename__ = 'recupero_docenti'

    id          = db.Column(db.Integer, primary_key=True)
    id_docente  = db.Column(db.Integer, db.ForeignKey('docenti.id'), nullable=False)
    anno_scol   = db.Column(db.String(9), nullable=False, default='2025-2026')
    note           = db.Column(db.String(200), nullable=True)
    materie_extra  = db.Column(db.String(500), nullable=True)  # materie aggiuntive per recupero
    creato_il      = db.Column(db.DateTime, default=datetime.utcnow)

    docente  = db.relationship('Docente')
    gruppi   = db.relationship('RecuperoGruppo', back_populates='docente_rec',
                               cascade='all, delete-orphan')

    __table_args__ = (
        db.UniqueConstraint('id_docente', 'anno_scol', name='uq_rec_docente'),
    )


class RecuperoGruppo(db.Model):
    """Gruppo di recupero: una materia, un docente, più classi."""
    __tablename__ = 'recupero_gruppi'

    id              = db.Column(db.Integer, primary_key=True)
    id_rec_docente  = db.Column(db.Integer, db.ForeignKey('recupero_docenti.id'), nullable=False)
    materia         = db.Column(db.String(100), nullable=False)   # es. "Matematica"
    classi          = db.Column(db.String(200), nullable=False)   # es. "2A LSC, 3A LLI"
    n_alunni        = db.Column(db.Integer, nullable=True)        # numero stimato alunni
    ore_totali      = db.Column(db.Integer, default=0)            # ore lezione già pianificate
    max_ore         = db.Column(db.Integer, default=10)           # limite ore totali (default 10)
    max_ore_giorno  = db.Column(db.Integer, default=2)            # limite ore per giorno (default 2)
    # Campi per prove di agosto
    tipo_prova      = db.Column(db.String(20), nullable=True)     # 'scritto'|'orale'|'pratico'|'scritto_orale'
    durata_ore      = db.Column(db.Float, default=2.0)            # durata prova in ore
    id_sorvegliante = db.Column(db.Integer, db.ForeignKey('docenti.id'), nullable=True)
    periodo_codice  = db.Column(db.String(20), default='corsi_giugno')  # quale periodo

    sorvegliante = db.relationship('Docente', foreign_keys=[id_sorvegliante])
    note            = db.Column(db.String(200), nullable=True)
    creato_il       = db.Column(db.DateTime, default=datetime.utcnow)

    docente_rec = db.relationship('RecuperoDocente', back_populates='gruppi')
    lezioni     = db.relationship('RecuperoLezione', back_populates='gruppo',
                                  cascade='all, delete-orphan',
                                  order_by='RecuperoLezione.data, RecuperoLezione.ora_inizio')

    @property
    def docente(self):
        return self.docente_rec.docente if self.docente_rec else None

    @property
    def ore_pianificate(self):
        return sum((l.durata_ore for l in self.lezioni), 0)


class RecuperoLezione(db.Model):
    """Singola lezione di recupero."""
    __tablename__ = 'recupero_lezioni'

    id          = db.Column(db.Integer, primary_key=True)
    id_gruppo   = db.Column(db.Integer, db.ForeignKey('recupero_gruppi.id'), nullable=False)
    data        = db.Column(db.Date, nullable=False)
    ora_inizio  = db.Column(db.String(5), nullable=False)   # HH:MM
    ora_fine    = db.Column(db.String(5), nullable=False)   # HH:MM
    aula        = db.Column(db.String(30), nullable=True)
    note        = db.Column(db.String(200), nullable=True)
    creato_il   = db.Column(db.DateTime, default=datetime.utcnow)

    gruppo = db.relationship('RecuperoGruppo', back_populates='lezioni')

    @property
    def durata_ore(self):
        try:
            h1, m1 = map(int, self.ora_inizio.split(':'))
            h2, m2 = map(int, self.ora_fine.split(':'))
            return round(((h2 * 60 + m2) - (h1 * 60 + m1)) / 60, 1)
        except Exception:
            return 0


class RecuperoAlunno(db.Model):
    """Alunno iscritto a un gruppo di recupero."""
    __tablename__ = 'recupero_alunni'

    id          = db.Column(db.Integer, primary_key=True)
    id_gruppo   = db.Column(db.Integer, db.ForeignKey('recupero_gruppi.id'), nullable=False)
    classe      = db.Column(db.String(20), nullable=False)
    cognome     = db.Column(db.String(80), nullable=False)
    nome        = db.Column(db.String(80), nullable=False)
    codice_fisc = db.Column(db.String(16), nullable=True)
    email       = db.Column(db.String(120), nullable=True)
    creato_il   = db.Column(db.DateTime, default=datetime.utcnow)

    gruppo = db.relationship('RecuperoGruppo', backref=db.backref('alunni',
                             cascade='all, delete-orphan', lazy='select'))

    @property
    def nome_completo(self):
        return f'{self.cognome} {self.nome}'.strip()


class RecuperoVincolo(db.Model):
    """
    Singola fascia di disponibilità di un docente.
    Un docente può avere più righe, ciascuna con giorno + fascia oraria.
    Es: giovedì 8:00-10:00 + giovedì 12:00-13:00 = due righe.
    Se nessuna riga → disponibile tutti i giorni 08:00-13:00 (default).
    """
    __tablename__ = 'recupero_vincoli'

    id              = db.Column(db.Integer, primary_key=True)
    id_rec_docente  = db.Column(db.Integer, db.ForeignKey('recupero_docenti.id'), nullable=False)
    anno_scol       = db.Column(db.String(9), nullable=False, default='2025-2026')
    giorno          = db.Column(db.Integer, nullable=True)     # 0=lun…4=ven (None=tutti i giorni della fascia date)
    ora_inizio      = db.Column(db.String(5), nullable=False)  # HH:MM
    ora_fine        = db.Column(db.String(5), nullable=False)  # HH:MM
    data_inizio     = db.Column(db.Date, nullable=True)        # dal (None=tutto il periodo)
    data_fine       = db.Column(db.Date, nullable=True)        # al
    classi_vincolo  = db.Column(db.String(200), nullable=True)  # es. "1ACAT,2ACAT" o vuoto=tutte
    materia_vincolo = db.Column(db.String(200), nullable=True)  # es. "Fisica" o vuoto=tutte le materie
    note            = db.Column(db.String(200), nullable=True)
    creato_il       = db.Column(db.DateTime, default=datetime.utcnow)

    docente_rec = db.relationship('RecuperoDocente',
                                  backref=db.backref('vincoli', cascade='all, delete-orphan',
                                                     order_by='RecuperoVincolo.giorno, RecuperoVincolo.ora_inizio'))

    NOMI_GIORNI = ['Lunedì','Martedì','Mercoledì','Giovedì','Venerdì']

    @property
    def giorno_label(self):
        if self.giorno is None: return 'Tutti i giorni'
        return self.NOMI_GIORNI[self.giorno] if 0 <= self.giorno < 5 else '?'

    @property
    def label(self):
        base = f'{self.giorno_label} {self.ora_inizio}–{self.ora_fine}'
        if self.data_inizio and self.data_fine:
            base += f' ({self.data_inizio.strftime("%d/%m")}–{self.data_fine.strftime("%d/%m")})'
        return base


class RecuperoImport(db.Model):
    """
    Tabella staging per i recuperi importati dal registro elettronico.
    Mantiene i dati grezzi prima che vengano abbinati ai gruppi.
    """
    __tablename__ = 'recupero_import'

    id              = db.Column(db.Integer, primary_key=True)
    anno_scol       = db.Column(db.String(9), nullable=False, default='2025-2026')
    classe          = db.Column(db.String(20), nullable=False)
    cognome         = db.Column(db.String(80), nullable=False)
    nome            = db.Column(db.String(80), nullable=False)
    codice_fisc     = db.Column(db.String(16), nullable=True)
    email           = db.Column(db.String(120), nullable=True)
    materia_raw     = db.Column(db.String(200), nullable=False)  # da file
    materia_norm    = db.Column(db.String(200), nullable=False)  # normalizzata
    docente_raw     = db.Column(db.String(200), nullable=True)   # da file
    cognome_docente  = db.Column(db.String(80), nullable=True)   # primo cognome
    nome_ini_docente = db.Column(db.String(5),  nullable=True)   # iniziale nome (es. 'S')
    stato_adesione  = db.Column(db.String(20), default='sconosciuto')  # aderisce|studio_ind|non_risposto|non_aderisce
    tipo_prova_raw  = db.Column(db.String(50),  nullable=True)   # testo grezzo colonna 'recupero' (scritto/orale/etc)
    creato_il       = db.Column(db.DateTime, default=datetime.utcnow)


class RecuperoPeriodo(db.Model):
    """
    Periodo di recupero: corsi estivi o prove di agosto.
    Permette di gestire i due cicli separatamente con parametri diversi.
    """
    __tablename__ = 'recupero_periodi'

    id          = db.Column(db.Integer, primary_key=True)
    anno_scol   = db.Column(db.String(9), nullable=False, default='2025-2026')
    codice      = db.Column(db.String(20), nullable=False)  # 'corsi_giugno' | 'prove_agosto'
    label       = db.Column(db.String(80), nullable=False)
    data_inizio = db.Column(db.Date, nullable=False)
    data_fine   = db.Column(db.Date, nullable=False)
    ora_inizio  = db.Column(db.String(5), default='08:00')
    ora_fine    = db.Column(db.String(5), default='16:00')
    note        = db.Column(db.String(200), nullable=True)
    creato_il   = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('anno_scol', 'codice', name='uq_periodo'),
    )
