"""
Modelli per gli incarichi annuali dei docenti:
strutturali, funzioni strumentali, FIS, MOF.
"""
from models import db


class CategoriaIncarico(db.Model):
    __tablename__ = 'categorie_incarico'

    id     = db.Column(db.Integer, primary_key=True)
    codice = db.Column(db.String(30), nullable=False, unique=True)
    nome   = db.Column(db.String(80), nullable=False)
    colore = db.Column(db.String(10), default='#1e40af')
    ordine = db.Column(db.Integer, default=0)

    tipi = db.relationship('TipoIncarico', back_populates='categoria_obj', lazy='dynamic')

    def __repr__(self):
        return f'<CategoriaIncarico {self.codice}>'


class TipoIncarico(db.Model):
    __tablename__ = 'tipi_incarico'

    id              = db.Column(db.Integer, primary_key=True)
    nome            = db.Column(db.String(100), nullable=False)
    categoria       = db.Column(db.String(30), nullable=False)  # codice categoria
    id_categoria    = db.Column(db.Integer, db.ForeignKey('categorie_incarico.id'), nullable=True)
    collegato_a     = db.Column(db.String(20), nullable=True)
    # 'classe' | 'dipartimento' | 'istituto' | NULL
    compenso_tipo   = db.Column(db.String(20), nullable=True)
    # 'forfait' | 'orario' | NULL
    importo_default = db.Column(db.Float, nullable=True)
    attivo          = db.Column(db.Boolean, default=True)
    ordine          = db.Column(db.Integer, default=0)

    categoria_obj = db.relationship('CategoriaIncarico', back_populates='tipi')
    nomine = db.relationship('IncaricaDocente', back_populates='tipo',
                             lazy='dynamic')

    def __repr__(self):
        return f'<TipoIncarico {self.nome}>'


class IncaricaDocente(db.Model):
    __tablename__ = 'incarichi_docenti'

    id               = db.Column(db.Integer, primary_key=True)
    anno_scol        = db.Column(db.String(9), nullable=False)
    id_tipo_incarico = db.Column(db.Integer,
                                  db.ForeignKey('tipi_incarico.id'),
                                  nullable=False)
    id_docente       = db.Column(db.Integer,
                                  db.ForeignKey('docenti.id'),
                                  nullable=False)
    # Contesto dell'incarico (opzionale)
    indirizzo        = db.Column(db.String(10), nullable=True)
    anno_corso       = db.Column(db.Integer, nullable=True)
    sezione          = db.Column(db.String(2), nullable=True)
    id_dipartimento  = db.Column(db.Integer,
                                  db.ForeignKey('dipartimenti.id'),
                                  nullable=True)
    # Compenso
    ore              = db.Column(db.Float, nullable=True)
    importo          = db.Column(db.Float, nullable=True)
    # Extra
    note             = db.Column(db.String(300), nullable=True)
    data_inizio      = db.Column(db.Date, nullable=True)
    data_fine        = db.Column(db.Date, nullable=True)

    tipo         = db.relationship('TipoIncarico', back_populates='nomine')
    docente      = db.relationship('Docente',
                                    backref=db.backref('incarichi', lazy='dynamic'))
    dipartimento = db.relationship('Dipartimento')

    __table_args__ = (
        db.UniqueConstraint('anno_scol', 'id_tipo_incarico',
                            'id_docente', 'indirizzo', 'anno_corso', 'sezione',
                            'id_dipartimento',
                            name='uq_incarico_docente'),
    )

    @property
    def label_classe(self):
        if self.anno_corso and self.sezione and self.indirizzo:
            return f'{self.anno_corso}{self.sezione} {self.indirizzo}'
        return None

    @property
    def compenso_display(self):
        if self.importo:
            return f'€ {self.importo:.2f}'
        if self.ore and self.tipo.importo_default:
            return f'{self.ore}h × € {self.tipo.importo_default:.2f}/h'
        return '—'

    def __repr__(self):
        return (f'<IncaricaDocente {self.anno_scol} '
                f'{self.tipo.nome} → {self.docente.cognome}>')
