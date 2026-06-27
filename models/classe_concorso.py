"""
Classi di concorso e organico — anagrafica stabile (cambia raramente,
solo per riforme ordinamentali) e dotazione organica annuale (cambia
ogni anno scolastico, su organico di diritto e poi di fatto).

Una ClasseConcorso (es. A026 - Matematica) raggruppa una o più Materia
(modello già esistente in models/materia.py) e può essere assegnata a
uno o più Docente come riferimento stabile, distinto dal vecchio campo
libero Docente.materia.

CattedraOrganico è la traduzione a database del prospetto ministeriale
(DOC / COI / COE / ore residue) che la scuola riceve a inizio anno per
la verifica dell'organico, separando esplicitamente diritto e fatto.
"""
from models import db
from datetime import datetime


class ClasseConcorso(db.Model):
    """
    Anagrafica delle classi di concorso (A011, A026, AS2B, ecc.). Stabile
    negli anni: cambia solo in caso di riforma ordinamentale del
    reclutamento, non a ogni anno scolastico.
    """
    __tablename__ = 'classi_concorso'

    id          = db.Column(db.Integer, primary_key=True)
    codice      = db.Column(db.String(10), nullable=False, unique=True)   # es. 'A026', 'AS2B'
    nome        = db.Column(db.String(150), nullable=False)               # es. 'Matematica'
    tipo_posto  = db.Column(db.String(20), default='cattedra')            # 'cattedra' | 'itp' | 'sostegno'
    note        = db.Column(db.String(200), nullable=True)
    attiva      = db.Column(db.Boolean, default=True)
    creato_il   = db.Column(db.DateTime, default=datetime.utcnow)

    materie  = db.relationship('Materia', back_populates='classe_concorso')
    docenti  = db.relationship('Docente', back_populates='classe_concorso',
                                foreign_keys='Docente.id_classe_concorso')
    cattedre = db.relationship('CattedraOrganico', back_populates='classe_concorso',
                                cascade='all, delete-orphan')
    abilitazioni = db.relationship('DocenteClasseConcorso', back_populates='classe_concorso',
                                    cascade='all, delete-orphan')

    def __repr__(self):
        return f'<ClasseConcorso {self.codice}>'


class CattedraOrganico(db.Model):
    """
    Una riga per ogni classe di concorso attiva nell'istituto, in un
    determinato anno scolastico, per organico di diritto o di fatto —
    cosi' restano entrambi tracciati e confrontabili, invece di
    sovrascrivere l'uno con l'altro.

    Rispecchia il prospetto ministeriale (SIDI): DOC = docenti titolari,
    COI = cattedre interamente interne, COE = cattedre che si completano
    con un'altra scuola, ore_residue = spezzoni che restano dopo aver
    formato tutte le COI/COE possibili (vanno a supplenze brevi).
    """
    __tablename__ = 'cattedre_organico'

    id                  = db.Column(db.Integer, primary_key=True)
    anno_scol           = db.Column(db.String(9), nullable=False)   # es. '2026-2027'
    tipo                = db.Column(db.String(10), nullable=False, default='diritto')  # 'diritto' | 'fatto'
    id_classe_concorso  = db.Column(db.Integer, db.ForeignKey('classi_concorso.id'), nullable=False)

    n_docenti     = db.Column(db.Integer, default=0)   # colonna DOC
    n_coi         = db.Column(db.Integer, default=0)   # colonna COI
    n_coe         = db.Column(db.Integer, default=0)   # colonna COE
    coe_direzione = db.Column(db.String(20), nullable=True)   # 'completa_con' | 'cede_a'
    coe_scuola    = db.Column(db.String(150), nullable=True)  # nome istituto di completamento/cessione
    coe_ore       = db.Column(db.Integer, nullable=True)       # ore della COE presso l'altra scuola

    ore_residue   = db.Column(db.Integer, default=0)   # spezzi liberi per supplenze brevi
    n_potenziamento = db.Column(db.Integer, default=0) # posti di potenziamento acquisiti

    note      = db.Column(db.String(300), nullable=True)
    creato_il = db.Column(db.DateTime, default=datetime.utcnow)

    classe_concorso = db.relationship('ClasseConcorso', back_populates='cattedre')

    __table_args__ = (
        db.UniqueConstraint('anno_scol', 'tipo', 'id_classe_concorso',
                            name='uq_cattedra_anno_tipo_classe'),
    )

    def __repr__(self):
        cc = self.classe_concorso.codice if self.classe_concorso else '?'
        return f'<CattedraOrganico {cc} {self.anno_scol} {self.tipo}>'


class DocenteClasseConcorso(db.Model):
    """
    Abilitazioni di un docente: un docente può essere abilitato su più
    classi di concorso (es. A026 + A050) e ricevere ore da entrambe.
    Una è marcata 'principale' — usata per etichette/badge rapidi e
    mantenuta in sync con il campo legacy Docente.id_classe_concorso.
    """
    __tablename__ = 'docente_classi_concorso'

    id                  = db.Column(db.Integer, primary_key=True)
    id_docente          = db.Column(db.Integer, db.ForeignKey('docenti.id'), nullable=False)
    id_classe_concorso  = db.Column(db.Integer, db.ForeignKey('classi_concorso.id'), nullable=False)
    principale          = db.Column(db.Boolean, default=False)
    creato_il           = db.Column(db.DateTime, default=datetime.utcnow)

    docente         = db.relationship('Docente', back_populates='abilitazioni')
    classe_concorso = db.relationship('ClasseConcorso', back_populates='abilitazioni')

    __table_args__ = (
        db.UniqueConstraint('id_docente', 'id_classe_concorso',
                            name='uq_docente_classe_concorso'),
    )

    def __repr__(self):
        cc = self.classe_concorso.codice if self.classe_concorso else '?'
        return f'<DocenteClasseConcorso docente={self.id_docente} {cc}>'


class MateriaClasseConcorso(db.Model):
    """
    Sostituisce Materia.id_classe_concorso (lasciato come campo legacy,
    sincronizzato sulla riga 'normativa' principale) per gestire le
    sovrapposizioni reali tra classi di concorso e materie — es. Filosofia
    insegnata sia da A018 sia da A019, secondo l'indirizzo.

    Distingue due livelli, come richiesto: collegamenti 'normativa'
    (verificabili su fonte primaria, validi per qualunque istituto) ed
    eventuali 'eccezione_istituto' (i casi atipici di questa scuola
    specifica, documentati con una nota sul perché esistono — la
    normativa stessa, per gli insegnamenti atipici, prevede che sia
    l'istituto a scegliere a quale classe di concorso attribuirli).
    """
    __tablename__ = 'materia_classi_concorso'

    id                  = db.Column(db.Integer, primary_key=True)
    id_materia          = db.Column(db.Integer, db.ForeignKey('materie.id'), nullable=False)
    id_classe_concorso  = db.Column(db.Integer, db.ForeignKey('classi_concorso.id'), nullable=False)
    fonte               = db.Column(db.String(20), default='normativa')  # 'normativa' | 'eccezione_istituto'
    riferimento         = db.Column(db.String(200), nullable=True)  # es. "DPR 19/2016, Tabella A"
    note                = db.Column(db.String(300), nullable=True)
    creato_il           = db.Column(db.DateTime, default=datetime.utcnow)

    materia         = db.relationship('Materia', backref='classi_concorso_ammesse')
    classe_concorso = db.relationship('ClasseConcorso', backref='materie_ammesse')

    __table_args__ = (
        db.UniqueConstraint('id_materia', 'id_classe_concorso',
                            name='uq_materia_classe_concorso'),
    )

    def __repr__(self):
        cc = self.classe_concorso.codice if self.classe_concorso else '?'
        return f'<MateriaClasseConcorso materia={self.id_materia} {cc} ({self.fonte})>'
