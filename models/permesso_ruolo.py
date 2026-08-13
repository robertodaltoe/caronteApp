"""
models/permesso_ruolo.py — matrice permessi per ruolo, configurabile dal DS
in Impostazioni > Sistema > Permessi (invece che fissa nel codice).

Copre solo i ruoli 'ds', 'collaboratore', 'segreteria': 'dsga' ha sempre
accesso pieno ovunque (bypass hardcoded, vedi models/utente.py Utente.
ha_permesso — 'tutto' in PERMESSI['dsga']) e non è modificabile da qui,
cosi' come 'display' non passa mai da questa matrice (redirect fisso alla
sola pagina /display, vedi app.py check_auth). Tenerli fuori dalla tabella
evita che una configurazione sbagliata blocchi l'intera app.

Le sezioni qui sotto sono raggruppamenti "di significato" (corrispondono
a come le pagine sono organizzate in nav/Impostazioni), non ai singoli
blueprint Flask — un blueprint può contenere route di sezioni diverse
(es. attivita_ist ha sia "Attività istituzionali" che "Dipartimenti"),
la mappa endpoint -> sezione è in app.py.
"""
from models import db

SEZIONI = [
    ('assenze',      'Assenze e indisponibilità'),
    ('supplenze',    'Supplenze'),
    ('attivita',     'Attività (fuori aula, istituzionali, differite)'),
    ('banca_ore',    'Banca ore'),
    ('report',       'Report'),
    ('orario',       'Orario di sostegno'),
    ('recupero',     'Recupero, rientro dall\'estero, esami integrativi'),
    ('organico',     'Organico, classi di concorso, piano di studi'),
    ('docenti',      'Anagrafica docenti e dipartimenti'),
    ('cambio_anno',  'Cambio anno scolastico'),
    ('calendario',   'Sospensioni e periodi calendario'),
    ('istituto',     'Dati istituto, backup, tipi incarico'),
    ('incarichi',    'Assegna incarichi ai docenti'),
    ('assegnazioni', 'Assegnazioni classi e aule'),
]
SEZIONI_LABEL = dict(SEZIONI)

RUOLI_CONFIGURABILI = [
    ('ds', 'Dirigente Scolastico'),
    ('collaboratore', 'Collaboratore DS'),
    ('segreteria', 'Segreteria Personale'),
]

LIVELLI = [
    ('esclusa', 'Esclusa'),
    ('visualizza', 'Visualizza'),
    ('modifica', 'Modifica'),
]
LIVELLI_VALIDI = {codice for codice, _ in LIVELLI}

# Configurazione iniziale: riflette quanto i commenti nel codice dicevano
# già di voler fare (vedi Sessione 49 nel DEVLOG) — non è arbitraria, è
# la stessa matrice discussa e approvata prima di costruire questa pagina.
DEFAULT_MATRICE = {
    'assenze':      {'ds': 'visualizza', 'collaboratore': 'modifica',   'segreteria': 'modifica'},
    'supplenze':    {'ds': 'visualizza', 'collaboratore': 'modifica',   'segreteria': 'visualizza'},
    'attivita':     {'ds': 'visualizza', 'collaboratore': 'modifica',   'segreteria': 'modifica'},
    'banca_ore':    {'ds': 'visualizza', 'collaboratore': 'visualizza', 'segreteria': 'modifica'},
    'report':       {'ds': 'visualizza', 'collaboratore': 'visualizza', 'segreteria': 'modifica'},
    'orario':       {'ds': 'visualizza', 'collaboratore': 'modifica',   'segreteria': 'visualizza'},
    'recupero':     {'ds': 'visualizza', 'collaboratore': 'modifica',   'segreteria': 'modifica'},
    'organico':     {'ds': 'visualizza', 'collaboratore': 'visualizza', 'segreteria': 'esclusa'},
    'docenti':      {'ds': 'visualizza', 'collaboratore': 'visualizza', 'segreteria': 'visualizza'},
    'cambio_anno':  {'ds': 'esclusa',    'collaboratore': 'esclusa',    'segreteria': 'esclusa'},
    'calendario':   {'ds': 'visualizza', 'collaboratore': 'modifica',   'segreteria': 'modifica'},
    'istituto':     {'ds': 'esclusa',    'collaboratore': 'esclusa',    'segreteria': 'esclusa'},
    'incarichi':    {'ds': 'visualizza', 'collaboratore': 'esclusa',    'segreteria': 'esclusa'},
    'assegnazioni': {'ds': 'visualizza', 'collaboratore': 'modifica',   'segreteria': 'visualizza'},
}


class PermessoRuolo(db.Model):
    __tablename__ = 'permessi_ruolo'

    id      = db.Column(db.Integer, primary_key=True)
    ruolo   = db.Column(db.String(20), nullable=False)
    sezione = db.Column(db.String(30), nullable=False)
    livello = db.Column(db.String(12), nullable=False, default='esclusa')

    __table_args__ = (
        db.UniqueConstraint('ruolo', 'sezione', name='uq_permesso_ruolo_sezione'),
    )


_cache = None


def _seed_permessi_ruolo():
    """Popola la tabella con la configurazione iniziale, solo se vuota
    (prima esecuzione dopo l'aggiornamento) — non sovrascrive mai
    personalizzazioni già salvate dal DS."""
    if PermessoRuolo.query.first():
        return
    for sezione, per_ruolo in DEFAULT_MATRICE.items():
        for ruolo, livello in per_ruolo.items():
            db.session.add(PermessoRuolo(ruolo=ruolo, sezione=sezione, livello=livello))
    db.session.commit()
    print(f"Seed: matrice permessi ruoli inizializzata ({len(DEFAULT_MATRICE)} sezioni).")


def invalida_cache():
    global _cache
    _cache = None


def matrice_permessi():
    """{ruolo: {sezione: livello}}, con fallback 'esclusa' per qualunque
    combinazione non presente in tabella (es. una sezione aggiunta in
    futuro non compare finché il DS non la configura esplicitamente)."""
    global _cache
    if _cache is None:
        m = {ruolo: {} for ruolo, _ in RUOLI_CONFIGURABILI}
        for p in PermessoRuolo.query.all():
            m.setdefault(p.ruolo, {})[p.sezione] = p.livello
        _cache = m
    return _cache


def livello_per(ruolo, sezione):
    if not sezione:
        return 'modifica'  # sezioni non mappate: nessun cancello, invariato
    return matrice_permessi().get(ruolo, {}).get(sezione, 'esclusa')
