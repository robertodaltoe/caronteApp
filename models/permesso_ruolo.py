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


# ── Mappa blueprint/endpoint -> sezione, usata da app.py::check_auth ──
# Vive qui (non in app.py) cosi' la pagina Permessi può fare la diagnostica
# "sezioni non collegate" leggendo la STESSA fonte usata per il controllo
# reale, invece di duplicarla e rischiare che le due si disallineino.
#
# Blueprint riservati DSGA (+ DS): cancellano/ricreano dati (import
# orario, risoluzione conflitti), troppo rischiosi per essere
# configurabili dalla matrice.
BLUEPRINT_DSGA_ONLY = {'sync', 'sync_conflitti'}

# Blueprint intenzionalmente aperti a chiunque sia loggato, qualunque
# ruolo: non contengono azioni specifiche di un ruolo (home, aiuto,
# ricerca, la pagina display stessa, export in sola lettura di dati già
# visibili altrove) oppure sono già gestiti internamente ('auth', via i
# singoli @login_required(...) sulle route sensibili).
BLUEPRINT_APERTI = {'dashboard', 'guida', 'ricerca', 'display', 'export_xlsx', 'auth'}

BLUEPRINT_SEZIONE = {
    'assenze':            'assenze',
    'indisponibilita':    'assenze',
    'supplenze':          'supplenze',
    'cambi':              'supplenze',
    'agenda':             'supplenze',
    'attivita':           'attivita',
    'attivita_ist':       'attivita',
    'att_differite':      'attivita',
    'banca_ore':          'banca_ore',
    'import_banca':       'banca_ore',
    'report':             'report',
    'mail_bozze':         'report',
    'orario_sostegno':    'orario',
    'recupero':           'recupero',
    'rientro':            'recupero',
    'esami_integrativi':  'recupero',
    'impostazione_anno':  'organico',
    'dashboard_anno':     'organico',
    'docenti':            'docenti',
    'cambio_anno':        'cambio_anno',
    'impostazioni':       'istituto',
    'incarichi':          'incarichi',
    'assegnazioni':       'assegnazioni',
    'aule':               'assegnazioni',
}
ENDPOINT_SEZIONE = {
    'attivita_ist.dipartimenti':                 'docenti',
    'attivita_ist.salva_dipartimento':           'docenti',
    'attivita_ist.salva_materia':                'docenti',
    'attivita_ist.assegna_materia_dipartimento': 'docenti',
    'impostazioni.sospensioni':                  'calendario',
    'impostazioni.periodi':                      'calendario',
    'incarichi.tipi':                            'istituto',
    'incarichi.salva_tipo':                      'istituto',
    'incarichi.salva_categoria':                 'istituto',
    # None = nessun cancello di sezione: ha un controllo interno suo.
    'impostazioni.permessi':                     None,
    'impostazioni.index':                        None,
}


def blueprint_non_mappati(app):
    """Blueprint registrati nell'app ma assenti da tutte le mappe sopra
    (BLUEPRINT_SEZIONE, BLUEPRINT_DSGA_ONLY, BLUEPRINT_APERTI) — quindi
    di fatto aperti a chiunque sia loggato senza che sia una scelta
    esplicita. Usata solo per l'avviso in Impostazioni > Permessi: una
    sezione nuova aggiunta in futuro non entra qui da sola, va collegata
    a mano (vedi commento in cima a questo file)."""
    conosciuti = (set(BLUEPRINT_SEZIONE) | BLUEPRINT_DSGA_ONLY | BLUEPRINT_APERTI)
    registrati = set(app.blueprints.keys())
    return sorted(registrati - conosciuti)


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
