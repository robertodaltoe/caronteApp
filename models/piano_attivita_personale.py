"""
models/piano_attivita_personale.py — piano delle attività funzionali
personale per i docenti con cattedra non completa in istituto (orario
ridotto, o cattedra completata in un'altra scuola).

Sessione 57, richiesto da Roberto: questi docenti devono partecipare
agli impegni collegiali (collegio, consigli di classe, dipartimenti...)
solo in proporzione alle ore di contratto qui — non per intero come un
docente a cattedra piena. Prima veniva gestito fuori dall'app (il
docente mandava il proprio piano su carta/email); qui il docente sceglie
gli impegni direttamente dal Piano delle Attività ufficiale (AttivitaIst,
già esistente) tramite un link personale con token — nessun login,
pensato per un uso occasionale una volta l'anno (vedi routes/
piano_personale.py).

La quota di ore dovute riusa i bucket CCNL art.44 già modellati in
models/attivita_ist.py (BUCKET_A/BUCKET_B, 40 ore/anno ciascuno per
un docente a cattedra piena — vedi LIMITE_BUCKET), proporzionata alla
frazione di cattedra del docente. Gli scrutini (BUCKET_NO) restano
sempre obbligatori per tutti, fuori da questo meccanismo.
"""
import secrets
from datetime import datetime
from models import db

STATI = [
    ('bozza',    'Bozza'),
    ('inviato',  'Inviato'),
    ('bloccato', 'Bloccato'),
]


def genera_token():
    """Token lungo e casuale per il link personale — non deve essere
    indovinabile: dà accesso in scrittura al piano di UN docente,
    senza nessun altro controllo (nessun login)."""
    return secrets.token_urlsafe(32)


def frazione_cattedra(docente, anno_scol):
    """
    Frazione di cattedra (0-1) di un docente per un dato anno scolastico:
    rapporto tra le ore effettive di servizio in istituto e il riferimento
    di "cattedra completa" configurabile in Impostazioni -> Dati istituto
    (config_istituto.py::ore_cattedra_piena, default 18).

    NON si può usare Docente.ore_contratto come riferimento di cattedra
    piena: per i part-time quel campo contiene già il valore ridotto
    (es. 15), non un nominale 18 — dividere per se stesso darebbe sempre
    frazione 1.0, nascondendo proprio i docenti che questo modulo deve
    intercettare. Riusa invece Docente.ore_max_effettive_per_anno(), già
    usata per il calcolo organico e per i limiti di banca ore, come
    numeratore (ore effettive, tiene già conto di part-time/override).
    """
    from config_istituto import get_dati_istituto
    piena = get_dati_istituto()['ore_cattedra_piena'] or 18
    ore_eff = docente.ore_max_effettive_per_anno(anno_scol) or 0
    return max(0.0, min(1.0, ore_eff / piena))


def cattedra_incompleta(docente, anno_scol):
    """True se il docente ha una frazione di cattedra < 1 per l'anno
    indicato — soglia con un piccolo margine per evitare falsi positivi
    da arrotondamenti in virgola mobile."""
    return frazione_cattedra(docente, anno_scol) < 0.999


def quota_ore_bucket(docente, anno_scol):
    """(quota_a, quota_b) — ore dovute per ciascun bucket CCNL,
    proporzionali alla frazione di cattedra del docente. Usa lo stesso
    limite configurabile (Impostazioni -> Dati istituto) già usato dal
    cruscotto ore istituzionali in routes/report.py::get_ore_ist_docente
    — lì è fisso a 40h per chiunque; qui viene proporzionato."""
    from config_istituto import get_dati_istituto
    limite = get_dati_istituto()['ore_ist_limite']
    f = frazione_cattedra(docente, anno_scol)
    quota = round(limite * f, 1)
    return quota, quota


class PianoAttivitaPersonale(db.Model):
    __tablename__ = 'piano_attivita_personale'

    id          = db.Column(db.Integer, primary_key=True)
    id_docente  = db.Column(db.Integer, db.ForeignKey('docenti.id'),
                            nullable=False, index=True)
    anno_scol   = db.Column(db.String(9), nullable=False)
    token       = db.Column(db.String(64), unique=True, nullable=False, index=True)
    stato       = db.Column(db.String(20), nullable=False, default='bozza')
    note        = db.Column(db.Text, nullable=True)  # note del docente in fase di invio
    inviato_il  = db.Column(db.DateTime, nullable=True)
    bloccato_il = db.Column(db.DateTime, nullable=True)
    bloccato_da = db.Column(db.String(80), nullable=True)
    creato_il   = db.Column(db.DateTime, default=datetime.utcnow)

    docente = db.relationship('Docente')
    voci    = db.relationship('PianoAttivitaPersonaleVoce', backref='piano',
                              cascade='all, delete-orphan', lazy='select')

    __table_args__ = (
        db.UniqueConstraint('id_docente', 'anno_scol', name='uq_piano_pers_docente_anno'),
    )

    @property
    def ids_attivita_scelte(self):
        return {v.id_attivita for v in self.voci}

    def ore_scelte_bucket(self):
        """(ore_a, ore_b) — somma delle ore delle voci scelte, per bucket."""
        from models.attivita_ist import BUCKET_A, BUCKET_B
        ore_a = ore_b = 0.0
        for v in self.voci:
            if not v.attivita:
                continue
            if v.attivita.bucket == BUCKET_A:
                ore_a += v.attivita.durata_ore
            elif v.attivita.bucket == BUCKET_B:
                ore_b += v.attivita.durata_ore
        return round(ore_a, 2), round(ore_b, 2)


class PianoAttivitaPersonaleVoce(db.Model):
    __tablename__ = 'piano_attivita_personale_voci'

    id          = db.Column(db.Integer, primary_key=True)
    id_piano    = db.Column(db.Integer, db.ForeignKey('piano_attivita_personale.id'),
                            nullable=False)
    id_attivita = db.Column(db.Integer, db.ForeignKey('attivita_ist.id'), nullable=False)

    attivita = db.relationship('AttivitaIst')

    __table_args__ = (
        db.UniqueConstraint('id_piano', 'id_attivita', name='uq_piano_pers_voce'),
    )
