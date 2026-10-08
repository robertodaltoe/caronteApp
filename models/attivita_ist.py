"""
Attività Istituzionali — Modulo C.
Gestisce Collegio, Consigli di Classe, Dipartimenti, GLO, Scrutini,
Incontri famiglie, Formazione, con conteggio ore CCNL art.44.
"""
from models import db
from datetime import datetime


# ── Bucket CCNL ──────────────────────────────────────────────────────────────
BUCKET_A  = 'A'   # max 40h (art.44 c.3 lett.a): Collegio e sue articolazioni (dipartimenti, materie, referenti), info famiglie, formazione residua
BUCKET_B  = 'B'   # max 40h (art.44 c.3 lett.b): CdC, GLO
BUCKET_NO = None  # fuori conteggio: scrutini, esami, riunioni ad hoc (Commissione/Staff...)

TIPI_ATTIVITA = {
    'collegio':           {'label': 'Collegio docenti',          'bucket': BUCKET_A,  'emoji': '▨︎'},
    'consiglio_classe':   {'label': 'Consiglio di classe',       'bucket': BUCKET_B,  'emoji': '◍︎'},
    'dipartimento':       {'label': 'Riunione dipartimento',     'bucket': BUCKET_A,  'emoji': '▥︎'},
    'riunione_materia':   {'label': 'Riunione per materia',      'bucket': BUCKET_A,  'emoji': '▥︎'},
    'glo':                {'label': 'GLO',                       'bucket': BUCKET_B,  'emoji': '◍︎'},
    'incontro_famiglie':  {'label': 'Incontro scuola-famiglia',  'bucket': BUCKET_A,  'emoji': '◍◍◍'},
    'scrutinio':          {'label': 'Scrutinio',                 'bucket': BUCKET_NO, 'emoji': '✎︎'},
    'formazione':         {'label': 'Formazione',                'bucket': BUCKET_A,  'emoji': '△︎'},
    'riunione_referenti': {'label': 'Riunione referenti dip.',   'bucket': BUCKET_A,  'emoji': '◆︎'},
    # 'altro': il bucket si sceglie evento per evento (bucket_altro);
    # il valore qui è solo il default per gli eventi già esistenti.
    'altro':              {'label': 'Altro',                     'bucket': BUCKET_A,  'emoji': '◆︎'},
    # Commissione, Staff o altro gruppo ad hoc — titolo libero scelto
    # da Roberto, mai un bucket normativo (art.44 lett.a/b): non è un
    # obbligo contrattuale che rientra nelle 40+40h, stesso principio
    # di "fuori conteggio" già usato per gli scrutini.
    'riunione_extra':     {'label': 'Altra riunione',            'bucket': BUCKET_NO, 'emoji': '◇︎'},
}

LIMITE_BUCKET = 40  # ore annue per bucket A e B

# Nota delle presenze 'giustificato' generate automaticamente per i docenti
# esonerati dal proprio Piano Attività Personale (vedi routes/attivita_ist.py).
NOTA_ESONERO_PIANO = 'Piano attività individuale'


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
    # True se l'elenco partecipanti è stato deliberatamente modificato a
    # mano dal form (selezione diversa da quella che _preset_partecipanti()
    # calcolerebbe in quel momento) — impostato in routes/attivita_ist.py
    # ::form(). Una volta True, la risincronizzazione smette di proporre
    # "da aggiungere" per questo evento (Roberto: "non è ammissibile che
    # se tolgo tutti o seleziono i partecipanti il sistema mi chieda di
    # inserirli di nuovo") — continua però a proporre "da rimuovibili"
    # per chi nel frattempo non è più in servizio, quello resta un
    # controllo di sicurezza, non un'opinione sul numero di partecipanti.
    partecipanti_manuali = db.Column(db.Boolean, default=False, nullable=False)

    # Solo per tipo 'altro': 'A' | 'B' | 'N' (fuori conteggio). NULL = eventi
    # precedenti alla scelta, trattati come A.
    bucket_altro = db.Column(db.String(1), nullable=True)

    dipartimento  = db.relationship('Dipartimento')
    partecipanti  = db.relationship('AttivitaIstPartecipante',
                                    back_populates='attivita',
                                    cascade='all, delete-orphan')
    presenze      = db.relationship('AttivitaIstPresenza',
                                    back_populates='attivita',
                                    cascade='all, delete-orphan')
    # Giornate aggiuntive per eventi su più date con orari diversi (es.
    # corso di formazione su 3 giorni) — vuota per la stragrande
    # maggioranza degli eventi (una sola giornata, i campi data/
    # ora_inizio/ora_fine sopra bastano). Quando valorizzata, la prima
    # riga rispecchia sempre data/ora_inizio/ora_fine di questo stesso
    # evento (sincronizzata al salvataggio in routes/attivita_ist.py::
    # form()) — vedi durata_ore sotto per il motivo.
    sessioni      = db.relationship('AttivitaIstSessione',
                                    back_populates='attivita',
                                    cascade='all, delete-orphan',
                                    order_by='AttivitaIstSessione.data')

    @property
    def partecipanti_convocati_ids(self):
        """Id dei partecipanti realmente convocati: esclude chi è in elenco
        solo come assente giustificato dal proprio piano individuale
        (NOTA_ESONERO_PIANO) — per i controlli di sovrapposizione/orario,
        dove non è un conflitto reale."""
        esonerati = {p.id_docente for p in self.presenze
                     if p.stato == 'giustificato' and p.note == NOTA_ESONERO_PIANO}
        return {p.id_docente for p in self.partecipanti
                if p.id_docente and p.id_docente not in esonerati}

    @property
    def bucket(self):
        if self.tipo == 'altro' and self.bucket_altro:
            return {'A': BUCKET_A, 'B': BUCKET_B}.get(self.bucket_altro, BUCKET_NO)
        return TIPI_ATTIVITA.get(self.tipo, {}).get('bucket')

    @property
    def tipo_label(self):
        return TIPI_ATTIVITA.get(self.tipo, {}).get('label', self.tipo)

    @property
    def tipo_emoji(self):
        return TIPI_ATTIVITA.get(self.tipo, {}).get('emoji', '◆︎')

    @property
    def durata_ore(self):
        """
        Durata in ore (float). Se l'evento ha più giornate (sessioni),
        somma le ore di ciascuna — prima si doveva forzare un totale
        finto su durata_min con un'unica data (segnalato da Roberto per
        un corso di formazione su 3 giorni con orari diversi), ora il
        totale è la somma reale delle giornate.
        """
        if self.sessioni:
            return round(sum(s.durata_ore for s in self.sessioni), 2)
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


class AttivitaIstSessione(db.Model):
    """
    Una singola giornata di un evento che si svolge su più date con
    orari diversi (es. un corso di formazione su 3 giorni) — Roberto:
    prima non c'era modo di rappresentarlo, si forzava il totale ore
    reale su un'unica data fittizia. Popolata solo per i pochi eventi
    davvero multi-giorno: la maggioranza degli AttivitaIst non ne ha
    nessuna e usa solo i propri campi data/ora_inizio/ora_fine.
    """
    __tablename__ = 'attivita_ist_sessioni'

    id          = db.Column(db.Integer, primary_key=True)
    id_attivita = db.Column(db.Integer,
                            db.ForeignKey('attivita_ist.id'), nullable=False)
    data        = db.Column(db.Date, nullable=False)
    ora_inizio  = db.Column(db.String(5), nullable=True)
    ora_fine    = db.Column(db.String(5), nullable=True)

    attivita = db.relationship('AttivitaIst', back_populates='sessioni')

    @property
    def durata_ore(self):
        if self.ora_inizio and self.ora_fine:
            try:
                hi, mi = map(int, self.ora_inizio.split(':'))
                hf, mf = map(int, self.ora_fine.split(':'))
                return round(((hf * 60 + mf) - (hi * 60 + mi)) / 60, 2)
            except Exception:
                pass
        return 0.0


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

    # Presenze delle giornate successive alla prima di un evento
    # multi-data (vedi AttivitaIstSessione): la riga di questa tabella
    # vale per la prima giornata, quelle in più stanno in per_data.
    per_data = db.relationship('AttivitaIstPresenzaGiornata',
                               back_populates='presenza',
                               cascade='all, delete-orphan')

    def _giornata(self, data):
        for g in self.per_data:
            if g.data == data:
                return g
        return None

    def stato_il(self, data):
        """Stato alla data indicata. Per la prima giornata (o un evento
        a data singola) è lo stato della riga stessa; per le giornate
        successive quello salvato in per_data, 'presente' se nessuno."""
        if not self.attivita or not self.attivita.sessioni \
                or data == self.attivita.sessioni[0].data:
            return self.stato
        g = self._giornata(data)
        return g.stato if g else 'presente'

    @property
    def ore_conteggiate(self):
        """Ore che contano per il monte ore (solo giornate 'presente').
        Evento a data singola: come prima (ore_effettive se presente,
        altrimenti 0). Evento multi-data: somma delle sole giornate in
        cui il docente era presente, ciascuna con il proprio orario
        effettivo se parziale."""
        ev = self.attivita
        if not ev or len(ev.sessioni) <= 1:
            return self.ore_effettive if self.stato == 'presente' else 0.0
        tot = 0.0
        for i, s in enumerate(ev.sessioni):
            if i == 0:
                stato, ini_e, fin_e = self.stato, self.ora_inizio_eff, self.ora_fine_eff
            else:
                g = self._giornata(s.data)
                stato = g.stato if g else 'presente'
                ini_e = g.ora_inizio_eff if g else None
                fin_e = g.ora_fine_eff if g else None
            if stato != 'presente':
                continue
            tot += _ore_tra(ini_e or s.ora_inizio, fin_e or s.ora_fine)
        return round(tot, 2)

    @property
    def presente_in_qualche_giornata(self):
        ev = self.attivita
        if not ev or len(ev.sessioni) <= 1:
            return self.stato == 'presente'
        return any(self.stato_il(s.data) == 'presente' for s in ev.sessioni)

    __table_args__ = (
        db.UniqueConstraint('id_attivita', 'id_docente',
                            name='uq_ist_presenza'),
    )


def _ore_tra(ini, fin):
    try:
        hi, mi = map(int, ini.split(':'))
        hf, mf = map(int, fin.split(':'))
        return ((hf * 60 + mf) - (hi * 60 + mi)) / 60
    except Exception:
        return 0.0


class AttivitaIstPresenzaGiornata(db.Model):
    """
    Presenza di un docente in una giornata successiva alla prima di un
    evento multi-data (es. corso di formazione su 4 date): la riga di
    AttivitaIstPresenza resta quella della prima giornata, qui stanno
    stato/nota/orario parziale delle altre. Chiavata per data e non per
    id della sessione perché le sessioni vengono rigenerate da zero a
    ogni salvataggio del form evento (_salva_sessioni_extra).
    """
    __tablename__ = 'attivita_ist_presenze_giornata'

    id          = db.Column(db.Integer, primary_key=True)
    id_presenza = db.Column(db.Integer,
                            db.ForeignKey('attivita_ist_presenze.id'), nullable=False)
    data        = db.Column(db.Date, nullable=False)
    stato       = db.Column(db.String(20), default='presente')
    note        = db.Column(db.String(200), nullable=True)
    ora_inizio_eff = db.Column(db.String(5), nullable=True)
    ora_fine_eff   = db.Column(db.String(5), nullable=True)

    presenza = db.relationship('AttivitaIstPresenza', back_populates='per_data')

    __table_args__ = (
        db.UniqueConstraint('id_presenza', 'data', name='uq_ist_presenza_giornata'),
    )
