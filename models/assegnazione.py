"""
Assegnazione nominativa docente → classe per anno scolastico.

Per ogni CC e anno scolastico, registra quante ore ogni docente
(o placeholder supplente) copre su ogni classe specifica.

Regole:
- id_docente NULL + nome_placeholder → supplente non ancora nominato
- id_docente valorizzato → docente reale
- Le CC dei placeholder vengono da MateriaClasseConcorso della materia
- Controlli: ore_docente <= ore_max_effettive, somma ore per classe
  = ore piano studi, cattedre assegnate <= organico USR fatto
"""
from datetime import datetime
from models import db


class AssegnazioneDocente(db.Model):
    __tablename__ = 'assegnazioni_docenti'

    id                  = db.Column(db.Integer, primary_key=True)
    anno_scol           = db.Column(db.String(9),  nullable=False)
    id_classe_concorso  = db.Column(db.Integer,
                                    db.ForeignKey('classi_concorso.id'),
                                    nullable=False)
    # Docente reale o placeholder
    id_docente          = db.Column(db.Integer,
                                    db.ForeignKey('docenti.id'),
                                    nullable=True)
    nome_placeholder    = db.Column(db.String(80), nullable=True)
    # 'titolare'|'coe_entrata'|'coe_uscita'|'supplente'|'part_time'|'eccedenza'
    tipo                = db.Column(db.String(20), nullable=False,
                                    default='titolare')
    note                = db.Column(db.String(200), nullable=True)
    creato_il           = db.Column(db.DateTime, default=datetime.utcnow)
    aggiornato_il       = db.Column(db.DateTime, default=datetime.utcnow,
                                    onupdate=datetime.utcnow)

    classe_concorso = db.relationship('ClasseConcorso')
    docente         = db.relationship('Docente',
                                      backref=db.backref('assegnazioni',
                                                         lazy='dynamic'))

    __table_args__ = (
        db.CheckConstraint(
            '(id_docente IS NOT NULL) OR (nome_placeholder IS NOT NULL)',
            name='ck_assegnazione_docente_o_placeholder'),
    )

    @property
    def display_name(self):
        if self.docente:
            return f'{self.docente.cognome} {self.docente.nome}'
        return self.nome_placeholder or '—'

    def __repr__(self):
        return (f'<Assegnazione {self.anno_scol} '
                f'{self.classe_concorso.codice if self.classe_concorso else "?"} '
                f'{self.display_name}>')


class AssegnazioneClasse(db.Model):
    """
    Ore che un docente (o placeholder) copre su una specifica classe.
    Molti-a-uno con AssegnazioneDocente: un docente può coprire più classi.
    """
    __tablename__ = 'assegnazioni_classi'

    id                   = db.Column(db.Integer, primary_key=True)
    id_assegnazione      = db.Column(db.Integer,
                                     db.ForeignKey('assegnazioni_docenti.id',
                                                   ondelete='CASCADE'),
                                     nullable=False)
    indirizzo            = db.Column(db.String(10), nullable=False)
    anno_corso           = db.Column(db.Integer,    nullable=False)
    sezione              = db.Column(db.String(2),  nullable=False)
    ore                  = db.Column(db.Integer,    nullable=False)
    # Materia specifica (NULL = ore totali senza distinzione per materia)
    id_materia           = db.Column(db.Integer,
                                     db.ForeignKey('materie.id'),
                                     nullable=True)

    assegnazione = db.relationship('AssegnazioneDocente',
                                   backref=db.backref('classi',
                                                      cascade='all, delete-orphan'))
    materia      = db.relationship('Materia')

    __table_args__ = (
        db.UniqueConstraint('id_assegnazione', 'indirizzo',
                            'anno_corso', 'sezione', 'id_materia',
                            name='uq_assegnazione_classe_materia'),
    )

    @property
    def label_classe(self):
        return f'{self.anno_corso}{self.sezione} {self.indirizzo}'

    def __repr__(self):
        return (f'<AssegnazioneClasse {self.label_classe} '
                f'{self.ore}h asgn={self.id_assegnazione}>')


class CattedraPotenziamento(db.Model):
    """Ore di potenziamento assegnate a una CC per anno scolastico."""
    __tablename__ = 'cattedre_potenziamento'

    id                  = db.Column(db.Integer, primary_key=True)
    anno_scol           = db.Column(db.String(9), nullable=False)
    id_classe_concorso  = db.Column(db.Integer,
                                     db.ForeignKey('classi_concorso.id'),
                                     nullable=False)
    ore                 = db.Column(db.Integer, nullable=False, default=18)
    note                = db.Column(db.String(200), nullable=True)

    classe_concorso = db.relationship('ClasseConcorso')

    __table_args__ = (
        db.UniqueConstraint('anno_scol', 'id_classe_concorso',
                            name='uq_potenziamento_anno_cc'),
    )

    def __repr__(self):
        return f'<CattedraPotenziamento {self.anno_scol} {self.classe_concorso.codice} {self.ore}h>'
