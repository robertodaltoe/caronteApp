from models import db

GIORNI = ['Lunedì','Martedì','Mercoledì','Giovedì','Venerdì','Sabato']

class OrarioDocente(db.Model):
    __tablename__ = 'orario_docenti'

    id          = db.Column(db.Integer, primary_key=True)
    id_docente  = db.Column(db.Integer, db.ForeignKey('docenti.id'), nullable=False, index=True)
    giorno      = db.Column(db.Integer, nullable=False)  # 0=lun … 5=sab
    ora         = db.Column(db.Integer, nullable=False)  # 1-9
    classe      = db.Column(db.String(20))
    materia     = db.Column(db.String(60))
    tipo_ora    = db.Column(db.String(20), default='lezione')
    # lezione | compresenza | potenziamento | disposizione | altro

    docente     = db.relationship('Docente', backref='orario', lazy=True)

    @property
    def giorno_nome(self):
        return GIORNI[self.giorno] if 0 <= self.giorno <= 5 else ''

    def __repr__(self):
        return f"<Orario {self.docente.cognome if self.docente else '?'} {self.giorno_nome} {self.ora}ª {self.classe}>"


def griglia_settimanale(id_docente, completa_se_vuota=False):
    """
    {giorno: {ora: OrarioDocente}} per un docente, più l'elenco delle
    ore e dei giorni da mostrare in una griglia -- riusata sia dalla
    scheda banca ore (routes/banca_ore.py::singolo, solo i giorni/ore
    che il docente usa davvero) sia dalla stampa dell'orario a sé
    stante (routes/report.py::orario_pdf).

    completa_se_vuota=True (usato solo dalla stampa): se il docente non
    ha nessuna ora reale in OrarioDocente (es. una cattedra assegnata
    ma l'orario non ancora arrivato/importato per lui, casi reali
    Rignanese/Mascolo — Sessione 69 addendum 7), ore_list/giorni_usati
    ricadono su un modello completo (tutti i giorni Lun-Sab, ore 1-9)
    invece di una griglia vuota inutilizzabile: serve a stampare un
    modulo bianco da compilare a mano.

    Ritorna (orario, ore_list, giorni_usati).
    """
    slots = OrarioDocente.query.filter_by(id_docente=id_docente).order_by(
        OrarioDocente.giorno, OrarioDocente.ora).all()
    orario = {}
    ore_usate = set()
    giorni_usati_set = set()
    for s in slots:
        if s.classe and s.classe not in ('---', '-x-', ''):
            orario.setdefault(s.giorno, {})[s.ora] = s
            ore_usate.add(s.ora)
            giorni_usati_set.add(s.giorno)

    if ore_usate:
        ore_list = sorted(ore_usate)
        giorni_usati = sorted(giorni_usati_set)
    elif completa_se_vuota:
        ore_list = list(range(1, 10))
        giorni_usati = list(range(6))
    else:
        ore_list = []
        giorni_usati = []

    return orario, ore_list, giorni_usati


def classi_attive():
    """
    Elenco ordinato delle classi presenti nell'orario corrente (es.
    '3A LSC'), usato per popolare i <datalist> di autocompletamento nei
    vari form che chiedono una classe in un campo di testo libero
    (supplenze, recupero, cambio ore, orario sostegno, ecc.), invece di
    duplicare la query in ogni route.
    """
    return sorted({
        c for (c,) in OrarioDocente.query.with_entities(OrarioDocente.classe)
            .distinct().all() if c
    })
