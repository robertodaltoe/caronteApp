from models import db

class Docente(db.Model):
    __tablename__ = 'docenti'

    id            = db.Column(db.Integer, primary_key=True)
    cognome       = db.Column(db.String(80),  nullable=False)
    nome          = db.Column(db.String(80),  nullable=False)
    nome_display  = db.Column(db.String(80))   # es. "FERRARI M."
    materia       = db.Column(db.String(120))
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
    colloqui_giorno      = db.Column(db.Integer)   # 0=lun…5=sab, None=nessuno
    colloqui_ora_inizio  = db.Column(db.Integer)   # ora inizio (1-9)
    colloqui_ora_fine    = db.Column(db.Integer)   # ora fine (1-9)

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

    supplenze_svolte  = db.relationship('Supplenza',        foreign_keys='Supplenza.id_sostituto',  backref='sostituto',  lazy=True)
    supplenze_assente = db.relationship('Supplenza',        foreign_keys='Supplenza.id_assente',    backref='assente',    lazy=True)
    assenze           = db.relationship('Assenza',          backref='docente',  lazy=True)
    movimenti         = db.relationship('MovimentoBancaOre',backref='docente',  lazy=True)
    indisponibilita   = db.relationship('Indisponibilita',  backref='docente',  lazy=True)
    materie_ist       = db.relationship('DocenteMateria', back_populates='docente',
                                         cascade='all, delete-orphan', lazy='select')

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
