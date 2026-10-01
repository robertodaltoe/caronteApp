"""modules/navigazione.py — elenco unico delle funzioni raggiungibili
dall'interfaccia, usato per la navigazione (Sessione 71).

Prima ogni punto d'ingresso (navbar, pagina Impostazioni, Dashboard,
ricerca) aveva il suo elenco di link scritto a mano, e alcune pagine
funzionanti erano rimaste senza alcun link (Import banca ore,
Indisponibilità ricorrenti) o raggiungibili solo attraversando altre
pagine (Assegnazioni, Cambi turno). Qui c'è una sola fonte, da cui
derivano:

- il menu a tendina "Impostazioni" in navbar (gruppi con in_menu=True);
- la ricerca delle funzioni ("Vai a...", Ctrl+K) nella casella Cerca;
- la sezione "Funzioni" nella pagina dei risultati di /ricerca;
- la voce di navbar evidenziata e il percorso sopra il titolo;
- le scorciatoie per ruolo in cima alla Dashboard.

Una voce compare solo a chi può aprirla: stessa regola di puo_vedere()
in app.py (la visibilità dei link non è la difesa — quella resta
check_auth — serve solo a non mostrare link che porterebbero a un
rifiuto). Una funzione nuova aggiunta all'app va aggiunta anche qui per
comparire nel menu e nella ricerca.
"""
import unicodedata

# Area della navbar da evidenziare per ciascun gruppo (vedi base.html,
# attributo data-area sulle voci). None = nessuna voce dedicata.
GRUPPI = [
    # chiave,          etichetta,                         area navbar,   in menu Impostazioni
    ('giornata',      'Assenze e supplenze',             'dashboard',    False),
    ('attivita',      'Attività',                        'attivita',     False),
    ('banca_report',  'Banca ore e report',              None,           False),
    ('orario',        'Orario',                          'orario',       False),
    ('differite',     'Attività differite',              'attivita',     False),
    ('anno',          'Anno scolastico',                 'impostazioni', True),
    ('docenti',       'Docenti',                         'impostazioni', True),
    ('contrattazione', 'Contrattazione integrativa',     'impostazioni', True),
    ('istituto',      'Istituto e calendario',           'impostazioni', True),
    ('sistema',       'Sistema',                         'impostazioni', True),
    ('fse',           'Progetti FSE/FESR',               'progetti_fse', False),
    ('aiuto',         'Aiuto',                           'guida',        False),
]
GRUPPI_LABEL = {g[0]: g[1] for g in GRUPPI}
GRUPPI_AREA = {g[0]: g[2] for g in GRUPPI}

# Ogni voce: label, endpoint, gruppo, sezione (permessi, vedi
# models/permesso_ruolo.SEZIONI; None = aperta a chi è loggato), icona,
# parole (sinonimi per la ricerca). Chiavi facoltative:
#   azione=True    -> crea/modifica: nascosta a chi ha sola lettura
#   ruoli=(...)    -> visibile solo a questi ruoli (controlli hardcoded)
#   permesso='x'   -> visibile solo se utente.ha_permesso('x')
#   blueprint=True -> la voce rappresenta tutto il suo blueprint per il
#                     percorso/voce attiva (vedi voce_per_endpoint)
FUNZIONI = [
    # ── Assenze e supplenze ──────────────────────────────────────────
    dict(label='Dashboard supplenze del giorno', endpoint='dashboard.index', gruppo='giornata',
         sezione=None, icona='home', parole='home oggi supplenze giornata', blueprint=True),
    dict(label='Registra assenza', endpoint='assenze.nuova', gruppo='giornata',
         sezione='assenze', icona='edit', parole='nuova assenza malattia permesso', azione=True, blueprint=True),
    dict(label='Nuova indisponibilità', endpoint='indisponibilita.nuova', gruppo='giornata',
         sezione='indisponibilita', icona='forbidden', parole='indisponibile', azione=True, blueprint=True),
    dict(label='Indisponibilità ricorrenti', endpoint='indisponibilita.lista_ricorrenti', gruppo='giornata',
         sezione='indisponibilita', icona='swap', parole='settimanali ripetute ricorrenza'),
    dict(label='Nuova supplenza', endpoint='supplenze.nuova', gruppo='giornata',
         sezione='supplenze', icona='plus', parole='sostituzione ora buca', azione=True, blueprint=True),
    dict(label='Potenziamento / compresenza', endpoint='supplenze.nuovo_potenziamento', gruppo='giornata',
         sezione='supplenze', icona='school', parole='potenziamento compresenza', azione=True),
    dict(label='Agenda supplenze e indisponibilità', endpoint='agenda.index', gruppo='giornata',
         sezione='agenda', icona='calendar', parole='agenda calendario settimana', blueprint=True),
    dict(label='Cambi turno', endpoint='cambi.lista', gruppo='giornata',
         sezione='cambi', icona='swap', parole='cambio quadro scambio ore restituzione', blueprint=True),
    dict(label='Display', endpoint='display.display', gruppo='giornata',
         sezione=None, icona='monitor', parole='schermo tabellone sala docenti', blueprint=True),
    dict(label='Prospetto supplenze', endpoint='report.prospetto_web', gruppo='giornata',
         sezione='report', icona='list', parole='prospetto stampa giornata'),

    # ── Attività ─────────────────────────────────────────────────────
    dict(label='Attività fuori aula', endpoint='attivita.lista', gruppo='attivita',
         sezione='attivita', icona='compass', parole='uscite visite viaggi progetti', blueprint=True),
    dict(label='Attività istituzionali', endpoint='attivita_ist.lista', gruppo='attivita',
         sezione='attivita_istituzionali', icona='building', parole='scrutini collegi consigli di classe riunioni', blueprint=True),
    dict(label='Piano delle attività', endpoint='attivita_ist.piano_annuale', gruppo='attivita',
         sezione='attivita_istituzionali', icona='list', parole='piano annuale 40 ore'),
    dict(label='Riepilogo ore attività', endpoint='attivita_ist.riepilogo_ore', gruppo='attivita',
         sezione='attivita_istituzionali', icona='clock', parole='ore 40 presenze'),
    dict(label='Piano attività personale', endpoint='piano_personale.lista', gruppo='attivita',
         sezione='piano_personale', icona='person', parole='cattedra incompleta', blueprint=True),
    dict(label='Genera piano delle attività', endpoint='generatore_cdc.index', gruppo='attivita',
         sezione='attivita_istituzionali', icona='compass', parole='generatore consigli di classe calendario', blueprint=True),
    dict(label='Piano della formazione', endpoint='formazione.lista', gruppo='attivita',
         sezione='attivita_istituzionali', icona='layers', parole='corsi formazione aggiornamento', blueprint=True),

    # ── Attività differite ───────────────────────────────────────────
    dict(label='Attività differite', endpoint='att_differite.index', gruppo='differite',
         sezione='attivita_differite', icona='clock', parole='giugno agosto estate', blueprint=True),
    dict(label='Corsi di recupero', endpoint='recupero.index', gruppo='differite',
         sezione='recupero', icona='graduation', parole='recupero debiti giugno agosto sospensione giudizio', blueprint=True),
    dict(label='Rientro dall\'estero', endpoint='rientro.index', gruppo='differite',
         sezione='rientro', icona='graduation', parole='anno all estero colloqui', blueprint=True),
    dict(label='Esami integrativi', endpoint='esami_integrativi.index', gruppo='differite',
         sezione='esami_integrativi', icona='graduation', parole='idoneita passaggio', blueprint=True),

    # ── Banca ore e report ───────────────────────────────────────────
    dict(label='Banca ore', endpoint='banca_ore.index', gruppo='banca_report',
         sezione='banca_ore', icona='coin', parole='saldo ore debito credito', blueprint=True),
    dict(label='Report', endpoint='report.index', gruppo='banca_report',
         sezione='report', icona='chart', parole='statistiche riepiloghi', blueprint=True),
    dict(label='Report per il dirigente', endpoint='report.dirigente', gruppo='banca_report',
         sezione='report', icona='chart', parole='ds dirigente sintesi'),
    dict(label='Pianifica permessi', endpoint='report.pianifica_permessi', gruppo='banca_report',
         sezione='report', icona='calendar', parole='permessi brevi recupero'),
    dict(label='Report incarichi docenti', endpoint='report.incarichi_docenti', gruppo='banca_report',
         sezione='report', icona='star', parole='incarichi'),
    dict(label='Bozze email', endpoint='mail_bozze.index', gruppo='banca_report',
         sezione='mail_bozze', icona='mail', parole='mail posta comunicazioni', blueprint=True),

    # ── Orario ───────────────────────────────────────────────────────
    dict(label='Orario globale', endpoint='sync.orario_globale', gruppo='orario',
         sezione='orario_globale', icona='grid', parole='orario docenti classi'),
    dict(label='Orario sostegno', endpoint='orario_sostegno.index', gruppo='orario',
         sezione='orario', icona='support', parole='sostegno', blueprint=True),
    dict(label='Alternativa IRC', endpoint='alternativa_irc.index', gruppo='orario',
         sezione='alternativa_irc', icona='school', parole='religione alternativa', blueprint=True),
    dict(label='Importa / modifica orario', endpoint='sync.index', gruppo='orario',
         sezione=None, ruoli=('ds', 'dsga'), icona='download', parole='sincronizzazione import orario'),
    dict(label='Mappa aule', endpoint='aule.mappa', gruppo='orario',
         sezione='aule', icona='door', parole='aule piano edificio'),

    # ── Anno scolastico ──────────────────────────────────────────────
    dict(label='Prepara / attiva nuovo anno', endpoint='cambio_anno.index', gruppo='anno',
         sezione='cambio_anno', icona='refresh', parole='cambio anno scolastico', blueprint=True),
    dict(label='Hub impostazione anno', endpoint='impostazione_anno.index', gruppo='anno',
         sezione='organico', icona='list', parole='wizard passi preparazione organico', blueprint=True),
    dict(label='Dashboard anno', endpoint='dashboard_anno.index', gruppo='anno',
         sezione='dashboard_anno', icona='chart', parole='riepilogo anno classi', blueprint=True),
    dict(label='Assegnazioni classi', endpoint='assegnazioni.index', gruppo='anno',
         sezione='assegnazioni', icona='grid-alt', parole='cattedre docenti classi assegnazione', blueprint=True),
    dict(label='Docenti per anno (TI/TD/uscite)', endpoint='impostazione_anno.docenti_anno', gruppo='anno',
         sezione='organico', icona='person', parole='ruolo determinato indeterminato'),
    dict(label='Classi attive', endpoint='impostazione_anno.classi_attive', gruppo='anno',
         sezione='organico', icona='building', parole='sezioni classi'),
    dict(label='Piano di studi', endpoint='impostazione_anno.piano_studi', gruppo='anno',
         sezione='organico', icona='layers', parole='quadro orario materie'),
    dict(label='Calcolo organico', endpoint='impostazione_anno.calcolo_organico', gruppo='anno',
         sezione='organico', icona='grid-alt', parole='organico coi coe cattedre'),
    dict(label='Confronto organico TI ↔ USR', endpoint='impostazione_anno.confronto_organico', gruppo='anno',
         sezione='organico', icona='diamond', parole='usr bollettino confronto'),
    dict(label='Incarichi docenti', endpoint='incarichi.index', gruppo='anno',
         sezione='incarichi', icona='star', parole='coordinatore referente funzione strumentale', blueprint=True),
    dict(label='Aule per classe', endpoint='aule.lista', gruppo='anno',
         sezione='aule', icona='door', parole='aule', blueprint=True),

    # ── Docenti ──────────────────────────────────────────────────────
    dict(label='Anagrafica docenti', endpoint='docenti.lista', gruppo='docenti',
         sezione='docenti', icona='person', parole='docenti insegnanti elenco', blueprint=True),
    dict(label='Sostituzioni docenti', endpoint='sostituzioni.index', gruppo='docenti',
         sezione='sostituzioni', icona='refresh', parole='supplente titolare temporanea definitiva', blueprint=True),
    dict(label='Docenti ↔ Classi di concorso', endpoint='impostazione_anno.docenti_classi_concorso', gruppo='docenti',
         sezione='organico', icona='diamond', parole='cdc classe di concorso'),
    dict(label='Docenti ↔ Materie', endpoint='impostazione_anno.docenti_materie', gruppo='docenti',
         sezione='organico', icona='layers', parole='materie insegnate'),
    dict(label='Dipartimenti e materie', endpoint='attivita_ist.dipartimenti', gruppo='docenti',
         sezione='dipartimenti', icona='layers', parole='dipartimento'),

    # ── Contrattazione ───────────────────────────────────────────────
    dict(label='Fondi e capitoli', endpoint='contrattazione.index', gruppo='contrattazione',
         sezione='contrattazione', icona='coin', parole='fis fmof economie contrattazione', blueprint=True),
    dict(label='Lettere di incarico', endpoint='contrattazione.lettere_index', gruppo='contrattazione',
         sezione='contrattazione', icona='mail', parole='lettere nomina incarico'),
    dict(label='Catalogo incarichi', endpoint='contrattazione.catalogo', gruppo='contrattazione',
         sezione='contrattazione', icona='list', parole='catalogo compensi'),
    dict(label='Personale ATA', endpoint='contrattazione.ata_lista', gruppo='contrattazione',
         sezione='contrattazione', icona='person', parole='ata collaboratori scolastici amministrativi'),

    # ── Istituto e calendario ────────────────────────────────────────
    dict(label='Sospensioni didattiche', endpoint='impostazioni.sospensioni', gruppo='istituto',
         sezione='calendario', icona='calendar', parole='festivita vacanze calendario'),
    dict(label='Periodi (recupero, rientro…)', endpoint='impostazioni.periodi', gruppo='istituto',
         sezione='calendario', icona='calendar', parole='periodi calendario quadrimestre'),
    dict(label='Dati istituto', endpoint='impostazioni.dati_istituto', gruppo='istituto',
         sezione='istituto', icona='building', parole='istituto costo ora supplenza parametri economici'),
    dict(label='Tipi di incarico', endpoint='incarichi.tipi', gruppo='istituto',
         sezione='tipi_incarico', icona='star', parole='categorie incarico'),
    dict(label='Importa piano delle attività', endpoint='attivita_ist.import_piano_xlsx', gruppo='istituto',
         sezione='attivita_istituzionali', icona='download', parole='import excel piano', azione=True),

    # ── Sistema ──────────────────────────────────────────────────────
    dict(label='Panoramica impostazioni', endpoint='impostazioni.index', gruppo='sistema',
         sezione=None, icona='gear', parole='impostazioni configurazione'),
    dict(label='Gestione utenti e PIN', endpoint='auth.lista_utenti', gruppo='sistema',
         sezione=None, permesso='gestione_utenti', icona='person', parole='utenti account accesso'),
    dict(label='Log accessi', endpoint='auth.log_accessi', gruppo='sistema',
         sezione=None, permesso='gestione_utenti', icona='list', parole='log accessi negati'),
    dict(label='Scarica backup database', endpoint='impostazioni.backup', gruppo='sistema',
         sezione='istituto', icona='download', parole='backup copia cifrata'),
    dict(label='Permessi per ruolo', endpoint='impostazioni.permessi', gruppo='sistema',
         sezione=None, ruoli=('ds',), icona='key', parole='permessi ruoli matrice'),
    dict(label='Conflitti di sincronizzazione', endpoint='sync_conflitti.index', gruppo='sistema',
         sezione=None, ruoli=('ds', 'dsga'), icona='warning', parole='sync conflitti postazioni', blueprint=True),
    dict(label='Cambia PIN', endpoint='auth.cambia_pin', gruppo='sistema',
         sezione=None, icona='key', parole='password pin'),

    # ── Altro ────────────────────────────────────────────────────────
    dict(label='Progetti FSE/FESR', endpoint='progetti_fse.index', gruppo='fse',
         sezione='progetti_fse', icona='layers', parole='pon fse fesr piano estate', blueprint=True),
    dict(label='Guida', endpoint='guida.index', gruppo='aiuto',
         sezione=None, icona='help', parole='aiuto manuale istruzioni', blueprint=True),
]

# Scorciatoie in cima alla Dashboard, per ruolo: le sezioni che quel
# ruolo apre più spesso (ognuna resta comunque filtrata dai permessi).
SCORCIATOIE_RUOLO = {
    'ds': ['report.dirigente', 'dashboard_anno.index', 'attivita_ist.piano_annuale',
           'banca_ore.index', 'docenti.lista', 'agenda.index'],
    'segreteria': ['banca_ore.index', 'report.index', 'mail_bozze.index',
                   'contrattazione.lettere_index', 'docenti.lista', 'sostituzioni.index'],
    'collaboratore': ['agenda.index', 'cambi.lista', 'attivita_ist.lista', 'attivita.lista',
                      'assegnazioni.index', 'sync.orario_globale'],
    'dsga': ['agenda.index', 'cambi.lista', 'assegnazioni.index', 'impostazione_anno.index',
             'attivita_ist.lista', 'banca_ore.index', 'report.index'],
}


def normalizza(testo):
    """Minuscolo e senza accenti: "attività" e "attivita" si trovano a
    vicenda nella ricerca."""
    t = unicodedata.normalize('NFKD', testo or '')
    return ''.join(c for c in t if not unicodedata.combining(c)).lower()


def _visibile(voce, utente, puo_vedere, sola_lettura):
    if utente is None:
        return False
    if voce.get('ruoli') and utente.ruolo not in voce['ruoli']:
        return False
    if voce.get('permesso') and not utente.ha_permesso(voce['permesso']):
        return False
    sez = voce.get('sezione')
    if sez and not puo_vedere(sez):
        return False
    if voce.get('azione') and sez and sola_lettura(sez):
        return False
    return True


def funzioni_visibili(utente, puo_vedere, sola_lettura):
    """Voci che l'utente può aprire, nell'ordine di FUNZIONI."""
    return [v for v in FUNZIONI if _visibile(v, utente, puo_vedere, sola_lettura)]


def cerca_funzioni(q, voci):
    """Voci in cui compaiono tutte le parole di q (etichetta, gruppo,
    sinonimi), senza distinzione di maiuscole/accenti."""
    parole = normalizza(q).split()
    if not parole:
        return []
    trovate = []
    for v in voci:
        testo = normalizza(' '.join([v['label'], GRUPPI_LABEL.get(v['gruppo'], ''), v.get('parole', '')]))
        if all(p in testo for p in parole):
            trovate.append(v)
    return trovate


def voce_per_endpoint(endpoint):
    """Voce che rappresenta la pagina corrente: prima per endpoint
    esatto, poi per blueprint (la voce con blueprint=True di quel
    blueprint), così anche le pagine di dettaglio/modifica hanno un
    percorso e una voce di navbar attiva."""
    if not endpoint:
        return None
    for v in FUNZIONI:
        if v['endpoint'] == endpoint:
            return v
    bp = endpoint.split('.')[0]
    for v in FUNZIONI:
        if v.get('blueprint') and v['endpoint'].split('.')[0] == bp:
            return v
    return None


def area_navbar(endpoint):
    """Voce della navbar da evidenziare (attributo data-area in
    base.html) per la pagina corrente."""
    if not endpoint:
        return None
    # Voci di navbar con un endpoint proprio, prima della regola per gruppo.
    diretti = {
        'banca_ore': 'banca_ore',
        'report': 'report', 'mail_bozze': 'report',
        'impostazioni': 'impostazioni', 'auth': None,
        'display': 'display',
    }
    bp = endpoint.split('.')[0]
    if endpoint == 'sync.orario_globale':
        return 'orario'
    if bp in diretti:
        return diretti[bp]
    voce = voce_per_endpoint(endpoint)
    if voce:
        return GRUPPI_AREA.get(voce['gruppo'])
    return None


def menu_impostazioni(voci):
    """[(etichetta gruppo, [voci])] per il menu a tendina Impostazioni."""
    out = []
    for chiave, etichetta, _area, in_menu in GRUPPI:
        if not in_menu:
            continue
        del_gruppo = [v for v in voci if v['gruppo'] == chiave
                      and v['endpoint'] != 'impostazioni.index']
        if del_gruppo:
            out.append((etichetta, del_gruppo))
    return out


def scorciatoie(utente, voci):
    """Scorciatoie della Dashboard per il ruolo dell'utente."""
    if utente is None:
        return []
    per_endpoint = {v['endpoint']: v for v in voci}
    elenco = SCORCIATOIE_RUOLO.get(utente.ruolo, SCORCIATOIE_RUOLO['dsga'])
    return [per_endpoint[e] for e in elenco if e in per_endpoint]
