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
la mappa endpoint -> sezione è più sotto in questo stesso file.

Sessione 53: Roberto ha chiesto sezioni più granulari (una per ciascuna
pagina/funzione distinta, non raggruppate per "area" come prima) e di
poter configurare anche "Orario globale" (prima nascosto dietro un
controllo hardcoded ds/dsga in nav, mai passato dalla matrice). Vedi
SEZIONI_GRUPPI più sotto per come sono organizzate nella pagina Permessi
(la Sezione 53 le raggruppa solo visivamente, la granularità di accesso
resta quella elencata in SEZIONI).
"""
from models import db

SEZIONI = [
    ('assenze',                'Assenze'),
    ('indisponibilita',        'Indisponibilità'),
    ('supplenze',              'Supplenze'),
    ('cambi',                  'Cambi turno'),
    ('agenda',                 'Agenda supplenze/indisponibilità'),
    ('attivita',               'Attività fuori aula'),
    ('attivita_istituzionali', 'Attività istituzionali (scrutini, collegi...)'),
    ('attivita_differite',     'Attività differite'),
    ('dipartimenti',           'Dipartimenti e materie'),
    ('piano_personale',        'Piano attività personale (cattedra incompleta)'),
    ('banca_ore',              'Banca ore'),
    ('import_banca_ore',       'Import banca ore da file'),
    ('report',                 'Report'),
    ('mail_bozze',             'Bozze email'),
    ('orario',                 'Orario di sostegno'),
    ('orario_globale',         'Orario globale'),
    ('recupero',               'Recupero (corsi giugno/agosto)'),
    ('rientro',                'Rientro dall\'estero'),
    ('esami_integrativi',      'Esami integrativi'),
    ('organico',               'Impostazione anno / organico'),
    ('dashboard_anno',         'Dashboard anno'),
    ('docenti',                'Anagrafica docenti'),
    ('cambio_anno',            'Cambio anno scolastico'),
    ('calendario',             'Sospensioni e periodi calendario'),
    ('istituto',               'Dati istituto e backup'),
    ('tipi_incarico',          'Tipi e categorie di incarico'),
    ('incarichi',              'Assegna incarichi ai docenti'),
    ('assegnazioni',           'Assegnazioni classi'),
    ('aule',                   'Aule per classe'),
]
SEZIONI_LABEL = dict(SEZIONI)

# Solo per raggruppare visivamente le righe nella pagina Permessi (non
# cambia in nulla il controllo di accesso, che resta sempre per singola
# sezione elencata in SEZIONI) — un gruppo per ciascuna voce della navbar/
# Impostazioni, cosi' la tabella (28 righe) resta orientabile.
SEZIONI_GRUPPI = [
    ('Assenze e supplenze', ['assenze', 'indisponibilita', 'supplenze', 'cambi', 'agenda']),
    ('Attività', ['attivita', 'attivita_istituzionali', 'attivita_differite', 'dipartimenti', 'piano_personale']),
    ('Banca ore e report', ['banca_ore', 'import_banca_ore', 'report', 'mail_bozze']),
    ('Orario', ['orario', 'orario_globale']),
    ('Recupero', ['recupero', 'rientro', 'esami_integrativi']),
    ('Anno scolastico e organico', ['organico', 'dashboard_anno', 'cambio_anno']),
    ('Docenti e incarichi', ['docenti', 'incarichi', 'tipi_incarico']),
    ('Istituto e calendario', ['calendario', 'istituto']),
    ('Assegnazioni', ['assegnazioni', 'aule']),
]

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

# Configurazione iniziale (solo per un DB nuovo/vuoto — vedi
# _seed_permessi_ruolo). Ogni sezione nata da uno scorporo (Sessione 53,
# vedi SPLIT_DA più sotto) eredita qui lo stesso valore che aveva la
# sezione genitore in Sessione 49/50, cosi' un'installazione nuova parte
# con lo stesso comportamento "di fatto" di quella già in uso da Roberto.
DEFAULT_MATRICE = {
    'assenze':                {'ds': 'visualizza', 'collaboratore': 'modifica',   'segreteria': 'modifica'},
    'indisponibilita':        {'ds': 'visualizza', 'collaboratore': 'modifica',   'segreteria': 'modifica'},
    'supplenze':               {'ds': 'visualizza', 'collaboratore': 'modifica',   'segreteria': 'visualizza'},
    'cambi':                   {'ds': 'visualizza', 'collaboratore': 'modifica',   'segreteria': 'visualizza'},
    'agenda':                  {'ds': 'visualizza', 'collaboratore': 'modifica',   'segreteria': 'visualizza'},
    'attivita':                {'ds': 'visualizza', 'collaboratore': 'modifica',   'segreteria': 'modifica'},
    'attivita_istituzionali':  {'ds': 'visualizza', 'collaboratore': 'modifica',   'segreteria': 'modifica'},
    'attivita_differite':      {'ds': 'visualizza', 'collaboratore': 'modifica',   'segreteria': 'modifica'},
    'dipartimenti':            {'ds': 'visualizza', 'collaboratore': 'visualizza', 'segreteria': 'visualizza'},
    'piano_personale':         {'ds': 'visualizza', 'collaboratore': 'modifica',   'segreteria': 'modifica'},
    'banca_ore':               {'ds': 'visualizza', 'collaboratore': 'visualizza', 'segreteria': 'modifica'},
    'import_banca_ore':        {'ds': 'visualizza', 'collaboratore': 'visualizza', 'segreteria': 'modifica'},
    'report':                  {'ds': 'visualizza', 'collaboratore': 'visualizza', 'segreteria': 'modifica'},
    'mail_bozze':               {'ds': 'visualizza', 'collaboratore': 'visualizza', 'segreteria': 'modifica'},
    'orario':                  {'ds': 'visualizza', 'collaboratore': 'modifica',   'segreteria': 'visualizza'},
    # Prima hardcoded ds/dsga: non deriva da nessuna sezione precedente,
    # il default riflette lo stesso comportamento ("solo il DS lo vedeva").
    'orario_globale':          {'ds': 'modifica',   'collaboratore': 'esclusa',    'segreteria': 'esclusa'},
    'recupero':                {'ds': 'visualizza', 'collaboratore': 'modifica',   'segreteria': 'modifica'},
    'rientro':                  {'ds': 'visualizza', 'collaboratore': 'modifica',   'segreteria': 'modifica'},
    'esami_integrativi':       {'ds': 'visualizza', 'collaboratore': 'modifica',   'segreteria': 'modifica'},
    'organico':                {'ds': 'visualizza', 'collaboratore': 'visualizza', 'segreteria': 'esclusa'},
    'dashboard_anno':          {'ds': 'visualizza', 'collaboratore': 'visualizza', 'segreteria': 'esclusa'},
    'docenti':                 {'ds': 'visualizza', 'collaboratore': 'visualizza', 'segreteria': 'visualizza'},
    'cambio_anno':             {'ds': 'esclusa',    'collaboratore': 'esclusa',    'segreteria': 'esclusa'},
    'calendario':              {'ds': 'visualizza', 'collaboratore': 'modifica',   'segreteria': 'modifica'},
    'istituto':                {'ds': 'esclusa',    'collaboratore': 'esclusa',    'segreteria': 'esclusa'},
    'tipi_incarico':           {'ds': 'esclusa',    'collaboratore': 'esclusa',    'segreteria': 'esclusa'},
    'incarichi':               {'ds': 'visualizza', 'collaboratore': 'esclusa',    'segreteria': 'esclusa'},
    'assegnazioni':            {'ds': 'visualizza', 'collaboratore': 'modifica',   'segreteria': 'visualizza'},
    'aule':                    {'ds': 'visualizza', 'collaboratore': 'modifica',   'segreteria': 'visualizza'},
}

# Sezioni nate da uno scorporo di una sezione più ampia (Sessione 53):
# {sezione_nuova: sezione_genitore_da_cui_ereditare_il_livello_gia'_salvato}.
# 'orario_globale' non compare qui apposta: non deriva da nessuna sezione
# esistente (prima era hardcoded ds/dsga), quindi usa direttamente
# DEFAULT_MATRICE invece di ereditare da un genitore — vedi
# _migra_split_sezioni_permessi().
SPLIT_DA = {
    'indisponibilita':       'assenze',
    'cambi':                 'supplenze',
    'agenda':                'supplenze',
    'attivita_istituzionali': 'attivita',
    'attivita_differite':    'attivita',
    'dipartimenti':          'docenti',
    'import_banca_ore':      'banca_ore',
    'mail_bozze':            'report',
    'rientro':               'recupero',
    'esami_integrativi':     'recupero',
    'dashboard_anno':        'organico',
    'tipi_incarico':         'istituto',
    'aule':                  'assegnazioni',
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

# Endpoint dentro un blueprint DSGA-only che invece SONO configurabili
# dalla matrice (in check_auth vengono esclusi dal blocco hardcoded e
# passano dal controllo normale per sezione): solo la vista di sola
# lettura 'sync.orario_globale' — l'import/modifica orario
# (sync.index/sync.importa) resta intenzionalmente hardcoded DSGA/DS,
# troppo rischioso per essere configurabile (sovrascrive dati).
BLUEPRINT_DSGA_ONLY_ECCEZIONI = {'sync.orario_globale'}

# Blueprint intenzionalmente aperti a chiunque sia loggato, qualunque
# ruolo: non contengono azioni specifiche di un ruolo (home, aiuto,
# ricerca, la pagina display stessa, export in sola lettura di dati già
# visibili altrove) oppure sono già gestiti internamente ('auth', via i
# singoli @login_required(...) sulle route sensibili).
BLUEPRINT_APERTI = {'dashboard', 'guida', 'ricerca', 'display', 'export_xlsx', 'auth'}

BLUEPRINT_SEZIONE = {
    'assenze':            'assenze',
    'indisponibilita':    'indisponibilita',
    'supplenze':          'supplenze',
    'cambi':              'cambi',
    'agenda':             'agenda',
    'attivita':           'attivita',
    'attivita_ist':       'attivita_istituzionali',
    'att_differite':      'attivita_differite',
    'banca_ore':          'banca_ore',
    'import_banca':       'import_banca_ore',
    'report':             'report',
    'mail_bozze':         'mail_bozze',
    'orario_sostegno':    'orario',
    'recupero':           'recupero',
    'rientro':            'rientro',
    'esami_integrativi':  'esami_integrativi',
    'impostazione_anno':  'organico',
    'dashboard_anno':     'dashboard_anno',
    'docenti':            'docenti',
    'cambio_anno':        'cambio_anno',
    'impostazioni':       'istituto',
    'incarichi':          'incarichi',
    'assegnazioni':       'assegnazioni',
    'aule':               'aule',
    'piano_personale':    'piano_personale',
}
ENDPOINT_SEZIONE = {
    'attivita_ist.dipartimenti':                 'dipartimenti',
    'attivita_ist.salva_dipartimento':           'dipartimenti',
    'attivita_ist.salva_materia':                'dipartimenti',
    'attivita_ist.assegna_materia_dipartimento': 'dipartimenti',
    'impostazioni.sospensioni':                  'calendario',
    'impostazioni.periodi':                      'calendario',
    'incarichi.tipi':                            'tipi_incarico',
    'incarichi.salva_tipo':                      'tipi_incarico',
    'incarichi.salva_categoria':                 'tipi_incarico',
    'sync.orario_globale':                       'orario_globale',
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


def _migra_split_sezioni_permessi():
    """
    Sessione 53: diverse sezioni accorpate sono state scorporate in
    sezioni singole (es. 'attivita' -> 'attivita' + 'attivita_istituzionali'
    + 'attivita_differite'), e aggiunta 'orario_globale' (prima hardcoded
    ds/dsga, mai passata dalla matrice).

    Su un'installazione già in uso, senza questa migrazione le sezioni
    nuove non avrebbero nessuna riga in tabella e matrice_permessi() le
    tratterebbe come 'esclusa' per tutti — bloccando di colpo un accesso
    che prima funzionava (es. Attività istituzionali per un collaboratore
    che aveva 'modifica' su 'attivita'). Per ogni sezione figlia, se non
    ha già una riga propria (perché già configurata a mano), eredita il
    livello attualmente salvato per la sezione genitore — altrimenti
    ricade sul default. Idempotente: non tocca righe già presenti.
    """
    cambiato = False
    for figlia, madre in SPLIT_DA.items():
        for ruolo, _ in RUOLI_CONFIGURABILI:
            if PermessoRuolo.query.filter_by(ruolo=ruolo, sezione=figlia).first():
                continue
            riga_madre = PermessoRuolo.query.filter_by(ruolo=ruolo, sezione=madre).first()
            livello = riga_madre.livello if riga_madre else DEFAULT_MATRICE.get(figlia, {}).get(ruolo, 'esclusa')
            db.session.add(PermessoRuolo(ruolo=ruolo, sezione=figlia, livello=livello))
            cambiato = True

    # Sezioni nuove indipendenti, non nate da uno scorporo: seed diretto
    # dal default, come per una sezione mai vista prima da questa
    # installazione ('orario_globale', Sessione 53; 'piano_personale',
    # Sessione 57).
    for sezione in ('orario_globale', 'piano_personale'):
        for ruolo, _ in RUOLI_CONFIGURABILI:
            if not PermessoRuolo.query.filter_by(ruolo=ruolo, sezione=sezione).first():
                db.session.add(PermessoRuolo(ruolo=ruolo, sezione=sezione,
                                livello=DEFAULT_MATRICE[sezione][ruolo]))
                cambiato = True

    if cambiato:
        db.session.commit()
        invalida_cache()
        print("Migrazione: sezioni permessi scorporate (Sessione 53) popolate.")


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
