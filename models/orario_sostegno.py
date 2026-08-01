from models import db
from types import SimpleNamespace

GIORNI = ['Lunedì', 'Martedì', 'Mercoledì', 'Giovedì', 'Venerdì', 'Sabato']


class OrarioSostegno(db.Model):
    """
    Orario dei docenti di sostegno, tenuto in una tabella SEPARATA da
    OrarioDocente (l'orario "principale" di titolari/ITP).

    Motivo della separazione: quando si importa l'orario generale da
    file, modules/parser_orario.py cancella e ricrea per intero la
    tabella OrarioDocente (OrarioDocente.query.delete()). Se l'orario
    di sostegno vivesse nella stessa tabella, un nuovo import
    dell'orario principale lo cancellerebbe insieme al resto — qui
    invece resta intatto, inserito e gestito a parte (vedi
    routes/orario_sostegno.py).

    Un docente di sostegno presente in classe con il titolare, se il
    titolare è assente, può coprire la classe esattamente come un ITP
    in compresenza. Questa equivalenza è implementata in
    modules/compresenze.py, che include le righe di questa tabella nel
    calcolo delle compresenze insieme a quelle di OrarioDocente — non
    serve quindi un campo tipo_ora qui, è sempre implicitamente una
    "compresenza".
    """
    __tablename__ = 'orario_sostegno'

    id         = db.Column(db.Integer, primary_key=True)
    id_docente = db.Column(db.Integer, db.ForeignKey('docenti.id'), nullable=False, index=True)
    giorno     = db.Column(db.Integer, nullable=False)  # 0=lun … 5=sab
    ora        = db.Column(db.Integer, nullable=False)  # 1-9
    classe     = db.Column(db.String(20), nullable=False)
    note       = db.Column(db.String(120))  # facoltativo, es. riferimento alunno/PEI

    docente = db.relationship('Docente', backref='orario_sostegno', lazy=True)

    __table_args__ = (
        # Un docente di sostegno non può essere in due classi nella
        # stessa ora dello stesso giorno.
        db.UniqueConstraint('id_docente', 'giorno', 'ora',
                             name='uq_orario_sostegno_docente_slot'),
    )

    @property
    def giorno_nome(self):
        return GIORNI[self.giorno] if 0 <= self.giorno <= 5 else ''

    def __repr__(self):
        nome = self.docente.cognome if self.docente else '?'
        return f"<OrarioSostegno {nome} {self.giorno_nome} {self.ora}ª {self.classe}>"


def slots_come_orario_docente(giorno=None):
    """
    Ritorna le righe di OrarioSostegno "travestite" da OrarioDocente
    (stessi attributi usati altrove: id_docente, giorno, ora, classe,
    tipo_ora, materia), con tipo_ora fissato a 'compresenza'.

    Serve per riusare, senza duplicarla, tutta la logica già scritta
    altrove (routes/supplenze.py::api_suggerimenti, in particolare) che
    legge OrarioDocente per sapere "chi è in classe X in quell'ora" —
    basta unire questa lista a quella di OrarioDocente.query... nei
    punti che ne hanno bisogno, invece di riscrivere quella logica per
    una seconda tabella.
    """
    query = OrarioSostegno.query
    if giorno is not None:
        query = query.filter_by(giorno=giorno)
    return [
        SimpleNamespace(
            id_docente=r.id_docente, giorno=r.giorno, ora=r.ora,
            classe=r.classe, tipo_ora='compresenza', materia=None,
        )
        for r in query.all()
    ]
