"""
Modelli per il calcolo dell'organico di diritto interno.

Tre tabelle:
  ClasseSezione   — dato variabile: quali sezioni sono attive per anno scolastico
  PianoStudi      — dato stabile (confermato anno per anno): ore settimanali
                    per classe di concorso + materia + indirizzo + anno di corso
  CalcoloOrganico — calcolato automaticamente + confermabile a mano:
                    COI / COE / residue per ogni classe di concorso

I laboratori ITP (B003, B012, B014, B016, B017) hanno il proprio record in
PianoStudi con id_cc_laboratorio. Il campo 'id_cc_madre' in PianoStudi indica
la classe di concorso "madre" per la sola adiacenza nell'export XLSX — non
influenza il calcolo delle ore.
"""
from datetime import datetime
from models import db


class ClasseSezione(db.Model):
    """
    Quale sezioni sono attive per ogni indirizzo/anno di corso
    nell'anno scolastico. E' il dato variabile da confermare ogni anno.
    """
    __tablename__ = 'classi_sezioni'

    id          = db.Column(db.Integer, primary_key=True)
    anno_scol   = db.Column(db.String(9), nullable=False)   # es. '2026-2027'
    indirizzo   = db.Column(db.String(10), nullable=False)  # LSC, LSU, LLI, LSP, AFM, RIM, CAT
    anno_corso  = db.Column(db.Integer, nullable=False)     # 1..5
    sezione     = db.Column(db.String(2), nullable=False)   # A, B, C...
    attiva      = db.Column(db.Boolean, default=True)

    __table_args__ = (
        db.UniqueConstraint('anno_scol', 'indirizzo', 'anno_corso', 'sezione',
                            name='uq_classe_sezione'),
    )

    @property
    def etichetta(self):
        return f'{self.anno_corso}{self.sezione} {self.indirizzo}'

    def __repr__(self):
        return f'<ClasseSezione {self.etichetta} {self.anno_scol}>'


class PianoStudi(db.Model):
    """
    Ore settimanali per classe di concorso + materia + indirizzo + anno di corso.
    Stabile: cambia solo se cambia il piano ministeriale o una scelta d'istituto.
    Viene 'confermato' anno per anno con anno_scol.

    Per i laboratori ITP (B003, B012 ecc.) id_cc_madre indica la classe di
    concorso teorica adiacente nell'export (A020 per B003, A034 per B012, ecc.):
    solo informazione grafica, non incide sul calcolo.
    """
    __tablename__ = 'piano_studi'

    id                  = db.Column(db.Integer, primary_key=True)
    anno_scol           = db.Column(db.String(9), nullable=False)
    indirizzo           = db.Column(db.String(10), nullable=False)
    anno_corso          = db.Column(db.Integer, nullable=False)
    id_classe_concorso  = db.Column(db.Integer, db.ForeignKey('classi_concorso.id'), nullable=False)
    id_materia          = db.Column(db.Integer, db.ForeignKey('materie.id'), nullable=True)
    nome_materia_locale = db.Column(db.String(100), nullable=True)  # etichetta nell'export (es. "lingua e cult.latina")
    ore_settimanali     = db.Column(db.Integer, nullable=False)
    id_cc_madre         = db.Column(db.Integer, db.ForeignKey('classi_concorso.id'), nullable=True)  # solo per laboratori ITP
    id_cc_default       = db.Column(db.Integer, db.ForeignKey('classi_concorso.id'), nullable=True)  # CC normativa originale del seed
    atipica             = db.Column(db.Boolean, default=False)  # True se la CC è stata cambiata rispetto al default

    classe_concorso = db.relationship('ClasseConcorso', foreign_keys=[id_classe_concorso])
    cc_madre        = db.relationship('ClasseConcorso', foreign_keys=[id_cc_madre])
    cc_default      = db.relationship('ClasseConcorso', foreign_keys=[id_cc_default])
    materia         = db.relationship('Materia')

    __table_args__ = (
        db.UniqueConstraint('anno_scol', 'indirizzo', 'anno_corso',
                            'id_classe_concorso', 'id_materia',
                            name='uq_piano_studi'),
    )

    def __repr__(self):
        cc = self.classe_concorso.codice if self.classe_concorso else '?'
        return f'<PianoStudi {cc} {self.indirizzo}{self.anno_corso} {self.ore_settimanali}h>'


class CalcoloOrganico(db.Model):
    """
    Calcolo delle cattedre per ogni classe di concorso nell'anno scolastico.
    Viene ricalcolato ogni volta che cambiano ClasseSezione o PianoStudi.

    Logica automatica (sovrascrivibile a mano):
      n_coi   = ore_totali // 18
      resto   = ore_totali % 18
      tipo    = 'COI' se resto==0,
                'COE' se 8 <= resto <= 17,
                'residue' se 1 <= resto <= 7
      (casi eccezionali: tipo_confermato sovrascrive tipo_calcolato)

    Al primo bollettino USR si conferma l'articolazione reale; al secondo
    si aggiunge la specificazione COE ('completa con X' / 'cede a Y').
    """
    __tablename__ = 'calcolo_organico'

    id                  = db.Column(db.Integer, primary_key=True)
    anno_scol           = db.Column(db.String(9), nullable=False)
    id_classe_concorso  = db.Column(db.Integer, db.ForeignKey('classi_concorso.id'), nullable=False)

    # Calcolato automaticamente
    ore_totali_calcolate = db.Column(db.Integer, default=0)
    n_coi_calcolato      = db.Column(db.Integer, default=0)  # ore_totali // 18
    ore_resto_calcolato  = db.Column(db.Integer, default=0)  # ore_totali % 18
    tipo_calcolato       = db.Column(db.String(20), nullable=True)  # 'COI'/'COE'/'residue'

    # Confermato/sovrascritto a mano
    tipo_confermato      = db.Column(db.String(20), nullable=True)   # sovrascrive tipo_calcolato
    note_eccezione       = db.Column(db.String(300), nullable=True)  # motivo sovrascrittura
    confermato           = db.Column(db.Boolean, default=False)       # flag validazione

    aggiornato_il        = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    classe_concorso = db.relationship('ClasseConcorso')

    __table_args__ = (
        db.UniqueConstraint('anno_scol', 'id_classe_concorso',
                            name='uq_calcolo_organico'),
    )

    @property
    def tipo_effettivo(self):
        """Tipo realmente usato: confermato se presente, altrimenti calcolato."""
        return self.tipo_confermato or self.tipo_calcolato

    @property
    def ore_coe(self):
        """Ore dello spezzone COE (resto che non completa una cattedra intera)."""
        if self.tipo_effettivo == 'COE':
            return self.ore_resto_calcolato
        return 0

    @property
    def ore_residue(self):
        """Ore residue (troppo poche anche per una COE)."""
        if self.tipo_effettivo == 'residue':
            return self.ore_resto_calcolato
        return 0

    def __repr__(self):
        cc = self.classe_concorso.codice if self.classe_concorso else '?'
        return f'<CalcoloOrganico {cc} {self.anno_scol} {self.ore_totali_calcolate}h → {self.tipo_effettivo}>'
