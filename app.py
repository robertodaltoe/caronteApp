from flask import Flask, redirect, url_for, flash, request
from flask_wtf import CSRFProtect
from flask_wtf.csrf import CSRFError
from models import db
import os, locale, secrets, shutil

# WeasyPrint: su macOS assicura che le librerie Homebrew siano trovate
import sys as _sys
if _sys.platform == 'darwin':
    os.environ.setdefault('DYLD_LIBRARY_PATH',
        '/opt/homebrew/lib:' + os.environ.get('DYLD_LIBRARY_PATH', ''))
from datetime import datetime, timedelta

def _ottieni_secret_key(base_dir):
    """
    Ordine di preferenza:
    1. Variabile d'ambiente CARONTE_SECRET_KEY, se impostata esplicitamente.
    2. File locale secret_key.txt (creato da questa stessa funzione al
       primo avvio, MAI committato — è già in .gitignore): letto tale e
       quale se esiste, cosi' le sessioni sopravvivono ai riavvii.
    3. Se nessuno dei due esiste ancora (primissimo avvio su una macchina):
       genera una chiave casuale e la scrive nel file per i prossimi avvii.

    Sostituisce la vecchia chiave fissa 'suplenzeapp-chiave-locale-2025'
    scritta nel codice sorgente (quindi nota a chiunque avesse accesso al
    repository): da questo avvio in poi tutte le sessioni già aperte
    vengono invalidate una tantum (bastera' un nuovo login, le sessioni
    durano comunque solo 8 ore — vedi PERMANENT_SESSION_LIFETIME).
    """
    env = os.environ.get('CARONTE_SECRET_KEY')
    if env:
        return env

    percorso = os.path.join(base_dir, 'secret_key.txt')
    if os.path.exists(percorso):
        with open(percorso, 'r', encoding='utf-8') as f:
            chiave = f.read().strip()
        if chiave:
            return chiave

    chiave = secrets.token_hex(32)
    with open(percorso, 'w', encoding='utf-8') as f:
        f.write(chiave)
    try:
        os.chmod(percorso, 0o600)  # leggibile solo dall'utente proprietario
    except OSError:
        pass  # es. Windows: chmod non garantisce questa granularità, non bloccante
    print(f"[INFO] Generata una nuova chiave di sessione locale in {percorso} "
          "(primo avvio su questa macchina, o file mancante). Non va mai "
          "committata né condivisa.", flush=True)
    return chiave


def create_app(avvio_con_reloader=True):
    """
    avvio_con_reloader: dice a create_app() se il chiamante avvierà poi
    l'app con il reloader Werkzeug (use_reloader=True in app.run() —
    il caso normale di questo file, vedi '__main__' in fondo). Serve solo
    a decidere COME evitare il doppio avvio del thread di sync automatico
    (vedi sotto): con reloader attivo, Werkzeug esegue create_app() due
    volte in due processi diversi e va scelto solo quello giusto; senza
    reloader (es. un ipotetico futuro deploy con gunicorn, che non passa
    da qui) non c'è alcun doppio avvio da evitare, quindi il thread deve
    partire subito — un eventuale entrypoint diverso da questo dovrebbe
    chiamare create_app(avvio_con_reloader=False) esplicitamente.
    """
    app = Flask(__name__)

    base_dir = os.path.abspath(os.path.dirname(__file__))
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(base_dir, 'database.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = _ottieni_secret_key(base_dir)
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=8)  # fine giornata lavorativa
    # Ricarica i template ad ogni richiesta invece di tenerli in cache.
    # Va impostato esplicitamente perché di default segue app.debug, ora
    # spento (vedi fondo file) — senza questa riga, con debug=False una
    # modifica a un template non si vedrebbe più senza riavviare il processo.
    app.config['TEMPLATES_AUTO_RELOAD'] = True

    db.init_app(app)

    # Protezione CSRF su tutte le route POST/PUT/PATCH/DELETE.
    # Il token viene iniettato lato client automaticamente (vedi
    # templates/base.html) per non dover modificare ogni singolo form.
    CSRFProtect(app)

    @app.errorhandler(CSRFError)
    def _csrf_error(e):
        """
        Mostra un messaggio comprensibile invece della pagina bianca
        "Bad Request: The CSRF tokens do not match" di Werkzeug.

        Il mismatch capita quasi sempre per un token ormai superato:
        due richieste quasi simultanee alla stessa pagina al primo
        caricamento (tipico di prefetch/precaricamento del browser),
        una scheda rimasta aperta da prima, o una sessione scaduta.
        Non è quasi mai un problema dei dati: basta ricaricare la
        pagina (che genera un token nuovo, coerente con la sessione
        corrente) e riprovare.
        """
        flash('La sessione era scaduta o non più valida: la pagina è stata '
              'ricaricata, riprova ad inviare il modulo.', 'warning')
        if request.path.startswith('/login'):
            return redirect(url_for('auth.login'))
        return redirect(request.referrer or url_for('dashboard.index'))

    try:
        locale.setlocale(locale.LC_TIME, 'it_IT.UTF-8')
    except locale.Error:
        try:
            locale.setlocale(locale.LC_TIME, 'it_IT')
        except locale.Error:
            pass

    from routes.dashboard    import dashboard_bp
    from routes.display      import display_bp
    from routes.docenti      import docenti_bp
    from routes.supplenze    import supplenze_bp
    from routes.banca_ore    import banca_ore_bp
    from routes.assenze      import assenze_bp
    from routes.cambi_quadro import cambi_bp
    from routes.sincronizzazione import sync_bp
    from routes.report import report_bp
    from routes.mail_bozze import mail_bozze_bp
    from routes.auth import auth_bp
    from routes.indisponibilita import indisp_bp
    from routes.attivita import attivita_bp
    from routes.agenda import agenda_bp
    from routes.import_banca_ore import import_bp
    from routes.aule import aule_bp

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(display_bp)
    app.register_blueprint(docenti_bp)
    app.register_blueprint(supplenze_bp)
    app.register_blueprint(banca_ore_bp)
    app.register_blueprint(assenze_bp)
    app.register_blueprint(cambi_bp)
    app.register_blueprint(sync_bp)
    app.register_blueprint(report_bp)
    app.register_blueprint(mail_bozze_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(indisp_bp)
    app.register_blueprint(attivita_bp)
    app.register_blueprint(agenda_bp)
    app.register_blueprint(import_bp)
    app.register_blueprint(aule_bp)
    from routes.attivita_ist import attivita_ist_bp
    app.register_blueprint(attivita_ist_bp)
    from routes.impostazioni import impostazioni_bp
    from routes.cambio_anno import cambio_anno_bp
    from routes.assegnazioni import assegnazioni_bp
    from routes.incarichi import incarichi_bp
    from routes.export_xlsx import export_bp
    from routes.dashboard_anno import dashboard_anno_bp
    app.register_blueprint(impostazioni_bp)
    app.register_blueprint(cambio_anno_bp)
    app.register_blueprint(assegnazioni_bp)
    app.register_blueprint(incarichi_bp)
    app.register_blueprint(export_bp)
    app.register_blueprint(dashboard_anno_bp)
    from routes.impostazione_anno import impostazione_anno_bp, _nav_steps
    app.register_blueprint(impostazione_anno_bp)
    # Globale (non solo sul blueprint impostazione_anno): serve anche nelle
    # pagine "4b. Aule" e "9. Assegnazioni", che vivono in altri blueprint.
    app.context_processor(lambda: dict(nav_steps=_nav_steps))
    # Etichette tipo_contratto — unica fonte di verità (models/docente.py),
    # usata dai dropdown in più blueprint (docenti, impostazione_anno).
    from models.docente import TIPO_CONTRATTO_LABELS
    app.context_processor(lambda: dict(tipo_contratto_labels=TIPO_CONTRATTO_LABELS))
    from routes.recupero import recupero_bp
    app.register_blueprint(recupero_bp)
    from routes.rientro import rientro_bp
    app.register_blueprint(rientro_bp)
    from routes.esami_integrativi import esami_integrativi_bp
    app.register_blueprint(esami_integrativi_bp)
    from routes.att_differite import att_differite_bp
    app.register_blueprint(att_differite_bp)
    from routes.ricerca import ricerca_bp
    app.register_blueprint(ricerca_bp)
    from routes.orario_sostegno import orario_sostegno_bp
    app.register_blueprint(orario_sostegno_bp)
    from routes.sync_conflitti import sync_conflitti_bp
    app.register_blueprint(sync_conflitti_bp)
    from routes.guida import guida_bp
    app.register_blueprint(guida_bp)

    # Filtro Jinja per decodificare JSON nei template
    import json
    app.jinja_env.filters['from_json'] = lambda s: json.loads(s) if s else []
    app.jinja_env.filters['enumerate'] = enumerate

    # Protezione accesso — tutte le route tranne display e auth
    ROUTE_PUBBLICHE = {'display.display', 'auth.login', 'auth.logout',
                        'auth.privacy', 'static'}

    # Mappe blueprint/endpoint -> sezione: vivono in models/permesso_ruolo.py
    # (non qui) cosi' la pagina Permessi può segnalare le sezioni non ancora
    # collegate leggendo la stessa fonte usata dal controllo reale sotto,
    # invece di duplicarla e rischiare che le due si disallineino.
    from models.permesso_ruolo import BLUEPRINT_DSGA_ONLY, BLUEPRINT_SEZIONE, ENDPOINT_SEZIONE

    def _nega_accesso(u, endpoint, messaggio):
        from flask import flash, request
        from models.log_accesso import LogAccesso
        db.session.add(LogAccesso(
            id_utente=u.id, username=u.username, ruolo=u.ruolo,
            azione='accesso_negato', dettaglio=endpoint,
            ip=request.remote_addr, esito='denied'
        ))
        db.session.commit()
        flash(messaggio, 'error')

    @app.before_request
    def check_auth():
        from flask import session, redirect, url_for, request, g
        from routes.auth import get_utente_corrente, log
        endpoint = request.endpoint or ''

        if endpoint in ROUTE_PUBBLICHE or endpoint.startswith('static'):
            return None

        # ── BYPASS SOLO PER VERIFICA VISIVA IN LOCALE ──────────────────
        # Attivo SOLO se CARONTE_SKIP_LOGIN=1 *e* CARONTE_DEBUG=1 sono
        # entrambe impostate esplicitamente prima dell'avvio (il secondo
        # requisito evita che un CARONTE_SKIP_LOGIN=1 dimenticato in una
        # shell disattivi da solo il login — serve un'intenzione doppia).
        # Simula login come utente 'dsga'. NON usare in produzione/rete
        # condivisa: disattivare subito dopo il test.
        if (os.environ.get('CARONTE_SKIP_LOGIN') == '1'
                and os.environ.get('CARONTE_DEBUG') == '1'
                and not session.get('utente_id')):
            from models.utente import Utente
            u_bypass = Utente.query.filter_by(username='dsga', attivo=True).first()
            if u_bypass:
                session['utente_id'] = u_bypass.id
                session['ruolo'] = u_bypass.ruolo
                session.permanent = True

        u = get_utente_corrente()
        if not u or not u.attivo:
            session.clear()
            return redirect(url_for('auth.login', next=request.url))

        g.utente = u

        # L'utente "display" vede SOLO la pagina display, sempre — qualunque
        # altra route provi a raggiungere (anche digitando l'URL a mano) lo
        # riporta lì, invece di affidarsi solo a nascondere i link in nav.
        if u.ruolo == 'display':
            if endpoint not in ('display.display', 'auth.logout'):
                return redirect(url_for('display.display'))
            return None

        blueprint = endpoint.split('.')[0] if '.' in endpoint else ''

        if blueprint in BLUEPRINT_DSGA_ONLY:
            if u.ruolo not in ('ds', 'dsga'):
                _nega_accesso(u, endpoint, 'Accesso riservato al DSGA.')
                return redirect(url_for('dashboard.index'))
            return None

        if blueprint == 'auth':
            return None  # gestito dai singoli @login_required(...) sulle route

        if endpoint in ENDPOINT_SEZIONE:
            sezione = ENDPOINT_SEZIONE[endpoint]  # può essere None = nessun cancello
        else:
            sezione = BLUEPRINT_SEZIONE.get(blueprint)
        if sezione and u.ruolo != 'dsga':
            from models.permesso_ruolo import livello_per
            livello = livello_per(u.ruolo, sezione)
            if livello == 'esclusa' or (livello == 'visualizza' and request.method != 'GET'):
                _nega_accesso(u, endpoint, 'Non hai i permessi per questa sezione.')
                return redirect(url_for('dashboard.index'))

    with app.app_context():
        from models.colloqui_eccezione import ColloquiEccezione  # noqa
        from models.aula import Aula  # noqa
        from models.attivita_accompagnatore import AttivitaAccompagnatore  # noqa
        from models.aula_override import AulaOverride  # noqa
        from models.utente import Utente  # noqa
        from models.log_accesso import LogAccesso  # noqa
        from models.classe_concorso import ClasseConcorso, CattedraOrganico  # noqa
        from models.materia import Dipartimento, Materia, DocenteMateria  # noqa
        from models.attivita_ist import AttivitaIst, AttivitaIstPartecipante, AttivitaIstPresenza  # noqa
        from models.sostituzione_scrutinio import SostituzioneScrutinio  # noqa
        from models.sospensione import SospensioneDidattica  # noqa
        from models.recupero import RecuperoDocente, RecuperoGruppo, RecuperoLezione, RecuperoAlunno, RecuperoVincolo, RecuperoImport, RecuperoPeriodo  # noqa
        from models.sync_conflitto import SyncConflitto  # noqa
        from models.sync_tombstone import SyncTombstone  # noqa
        from models.permesso_ruolo import PermessoRuolo  # noqa
        # Crea tabelle nuove + applica migrazioni colonne
        db.create_all()
        _auto_migrate()
        _migra_vincolo_aule()
        _backfill_anno_scol_banca_ore()
        _seed_dipartimenti_materie()
        _seed_sospensioni()
        from models.permesso_ruolo import _seed_permessi_ruolo
        _seed_permessi_ruolo()
        _backup_automatico(base_dir)
        _pulizia_log(base_dir)

    @app.template_global()
    def puo_vedere(sezione):
        """Per nascondere le voci di menu che l'utente corrente non può
        aprire (vedi templates/base.html) — stessa logica di check_auth,
        usata qui solo per la visibilità dei link, non come controllo di
        sicurezza a sé stante (quello resta check_auth, invariabile
        anche digitando l'URL a mano)."""
        from flask import g
        u = getattr(g, 'utente', None)
        if not u or u.ruolo in ('dsga', 'display'):
            return True
        from models.permesso_ruolo import livello_per
        return livello_per(u.ruolo, sezione) != 'esclusa'

    @app.context_processor
    def _inject_dati_istituto():
        """
        Rende nome_istituto/indirizzo_istituto disponibili in tutti i
        template senza doverli passare esplicitamente da ogni singola
        route (che prima ripetevano la stringa "IIS Leonardo da Vinci —
        Chiavenna" a mano in oltre 10 punti diversi). Vedi config_istituto.py.
        """
        try:
            from config_istituto import get_dati_istituto
            dati = get_dati_istituto()
            return {
                'nome_istituto': dati['nome_istituto'],
                'indirizzo_istituto': dati['indirizzo_istituto'],
            }
        except Exception:
            # Fuori da un contesto applicativo con DB pronto (es. primissimo
            # avvio prima di create_all): usa i default statici, non rompere.
            from config_istituto import DEFAULTS
            return {
                'nome_istituto': DEFAULTS['nome_istituto'],
                'indirizzo_istituto': DEFAULTS['indirizzo_istituto'],
            }

    @app.context_processor
    def _inject_conflitti_sync():
        """Conteggio conflitti non risolti del sync automatico (banner in
        base.html). Vedi modules/auto_sync.py."""
        try:
            from models.sync_conflitto import SyncConflitto
            n = SyncConflitto.query.filter_by(risolto=False).count()
            return {'n_conflitti_sync': n}
        except Exception:
            return {'n_conflitti_sync': 0}

    # Sync automatico additivo in background (ogni 30s, solo su
    # 'assenze'/'supplenze' — vedi modules/auto_sync.py e DEVLOG Task 46).
    if avvio_con_reloader:
        # Guardia contro il doppio avvio: con use_reloader=True Werkzeug
        # esegue create_app() due volte — una nel processo "guardiano" che
        # si limita a sorvegliare i file e rilanciare, una in quello che
        # serve davvero le richieste (quest'ultimo, solo, ha
        # WERKZEUG_RUN_MAIN=true). NOTA: qui non si può usare app.debug per
        # distinguere i due casi — a questo punto della funzione è sempre
        # False, perché diventa True solo dentro app.run(), chiamato DOPO
        # che create_app() è già tornato: ci si affida solo a WERKZEUG_RUN_MAIN.
        avvia_ora = os.environ.get('WERKZEUG_RUN_MAIN') == 'true'
    else:
        # Nessun reloader di mezzo (vedi docstring sopra): nessun processo
        # "guardiano" duplicato da escludere, si parte direttamente.
        avvia_ora = True

    if avvia_ora:
        from modules.auto_sync import avvia_thread_autosync
        avvia_thread_autosync(app)
        print('[auto_sync] thread avviato — primo giro tra ~10s, poi ogni 30s.', flush=True)

    return app


def _auto_migrate():
    """
    Applica automaticamente le migrazioni pendenti all'avvio.
    Sicuro — aggiunge solo colonne mancanti, non modifica dati.
    """
    from sqlalchemy import text

    MIGRATIONS = [
        ('assenze',   'note_interne',    'TEXT',         None),
        ('assenze',   'ora_inizio',      'INTEGER',      1),
        ('assenze',   'ora_fine',        'INTEGER',      9),
        ('supplenze', 'note_display',    'VARCHAR(200)', None),
        ('supplenze', 'modificato_il',   'DATETIME',     None),
        ('banca_ore', 'id_supplenza',    'INTEGER',      None),
        ('docenti',   'nome_display',    'VARCHAR(80)',  None),
        ('docenti',   'materia',         'VARCHAR(120)', None),
        ('docenti',   'email',           'VARCHAR(120)', None),
        ('docenti',   'note',            'TEXT',         None),
        ('docenti',   'tipo_contratto',      'VARCHAR(30)', None),
        ('docenti',   'colloqui_giorno',     'INTEGER',     None),
        ('docenti',   'colloqui_ora_inizio', 'INTEGER',     None),
        ('docenti',   'colloqui_ora_fine',   'INTEGER',     None),
        ('utenti',    'cognome',             'VARCHAR(80)', "''"),
        ('attivita_fuori_aula', 'riconosci_ore_acc', 'BOOLEAN',  0),
        ('attivita_accompagnatori_dettaglio', 'ore_json', 'VARCHAR(50)', None),
        ('attivita_fuori_aula', 'ore_acc_inizio',    'INTEGER',  None),
        ('attivita_fuori_aula', 'ore_acc_fine',       'INTEGER',  None),
        ('attivita_fuori_aula', 'gruppo_rimanente',    'BOOLEAN',  0),
        ('attivita_fuori_aula', 'ore_singole_json',    'VARCHAR(30)', None),
        ('attivita_fuori_aula', 'id_attivita_gruppo',  'INTEGER',  None),
        ('migrazione_slots',    'usa_docente_automatico', 'BOOLEAN', 0),
        ('migrazione_slots',    'id_docente_assegnato',  'INTEGER', None),
        ('docenti',             'ruolo',                 'VARCHAR(20)', 'titolare'),
        ('docenti',             'altra_scuola',          'VARCHAR(120)', None),
        ('docenti',             'giorni_presenza',       'VARCHAR(20)',  None),
        ('docenti',             'part_time',             'BOOLEAN',     0),
        ('docenti',             'ore_contratto_pt',      'INTEGER',     None),
        ('docenti',             'ora_uscita_json',       'VARCHAR(60)',  None),
        ('assenze',              'classe_libera',          'BOOLEAN',    0),
        ('colloqui_eccezioni',  'data_fine',             'DATE',       None),
        ('utenti',    'nome',                'VARCHAR(80)', "''"),
        ('log_accessi', 'nome_completo',        'VARCHAR(160)', None),
        ('docenti',   'id_classe_concorso',  'INTEGER',     None),
        ('materie',   'id_classe_concorso',  'INTEGER',     None),
        ('banca_ore', 'anno_scol',           'VARCHAR(9)',  None),
        ('docenti',   'modificato_il',       'DATETIME',    None),
        ('esami_integrativi_materie', 'tipologia', 'VARCHAR(10)', None),
        ('docente_materie', 'origine', "VARCHAR(10)", "'manuale'"),
        ('docenti', 'part_time_prog',           'BOOLEAN',    None),
        ('docenti', 'ore_contratto_pt_prog',     'INTEGER',    None),
        ('docenti', 'anno_scol_part_time_prog',  'VARCHAR(9)', None),
        ('assenze',         'creato_da', 'VARCHAR(80)', None),
        ('supplenze',       'creato_da', 'VARCHAR(80)', None),
        ('indisponibilita', 'creato_da', 'VARCHAR(80)', None),
    ]

    with db.engine.connect() as conn:
        for table, column, coltype, default in MIGRATIONS:
            # Verifica tabella
            t_exists = conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=:t"
            ), {'t': table}).fetchone()
            if not t_exists:
                continue

            # Verifica colonna
            cols = [row[1] for row in conn.execute(text(f"PRAGMA table_info({table})"))]
            if column in cols:
                continue

            # Aggiunge colonna
            sql = f"ALTER TABLE {table} ADD COLUMN {column} {coltype}"
            if default is not None:
                sql += f" DEFAULT {default}"
            conn.execute(text(sql))

        conn.commit()


def _migra_vincolo_aule():
    """
    Corregge il vincolo UNIQUE della tabella 'aule'.

    Storicamente il vincolo reale nel database era UNIQUE(classe) da solo,
    mentre il modello Python dichiara UNIQUE(anno_scol, classe) — SQLite non
    permette di alterare un vincolo UNIQUE con ALTER TABLE, quindi la vecchia
    tabella non veniva mai corretta automaticamente (vedi DEVLOG Sessione 4).

    Le classi devono poter avere aule diverse in anni diversi: questa
    migrazione ricrea la tabella con il vincolo corretto, preservando tutti
    i dati esistenti (sempre validi per il nuovo vincolo, essendo questo
    meno restrittivo del precedente). Idempotente: se il vincolo è già
    corretto, non fa nulla.
    """
    from sqlalchemy import text

    with db.engine.connect() as conn:
        row = conn.execute(text(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='aule'"
        )).fetchone()
        if not row or not row[0]:
            return  # tabella non ancora creata, nulla da migrare

        # Copie del database molto vecchie (precedenti anche all'introduzione
        # della colonna anno_scol su 'aule') possono arrivare qui senza quella
        # colonna — la aggiunge prima di procedere, così il resto della
        # migrazione (che presuppone la colonna presente) non fallisce con
        # "no such column: anno_scol". Le righe esistenti ricevono l'anno
        # scolastico corrente come valore di partenza (da correggere a mano
        # se in realtà appartenevano a un anno diverso).
        cols = [r[1] for r in conn.execute(text("PRAGMA table_info(aule)"))]
        if 'anno_scol' not in cols:
            from config_anno import get_anno_corrente
            anno_default = get_anno_corrente()
            conn.execute(text(
                f"ALTER TABLE aule ADD COLUMN anno_scol VARCHAR(9) NOT NULL DEFAULT '{anno_default}'"
            ))
            conn.commit()
            print(f"Migrazione: aggiunta colonna 'anno_scol' a 'aule' "
                  f"(valore di partenza per le righe esistenti: '{anno_default}').")
            row = conn.execute(text(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='aule'"
            )).fetchone()

        sql_tabella = row[0]
        # Se il vincolo combinato è già presente, non c'è nulla da fare.
        if 'UNIQUE (anno_scol, classe)' in sql_tabella or \
           'uq_aula_anno_classe' in sql_tabella:
            return

        # Migrazione: ricrea la tabella con il vincolo corretto (pattern
        # standard SQLite per modificare un vincolo su tabella esistente).
        # DROP IF EXISTS difensivo: se un tentativo precedente si è
        # interrotto a metà (es. errore durante l'INSERT), può restare
        # una 'aule_new' vuota da un run passato — altrimenti la CREATE
        # TABLE fallirebbe con "aule_new already exists" senza mai
        # arrivare a completare la migrazione.
        conn.execute(text("DROP TABLE IF EXISTS aule_new"))
        conn.execute(text("""
            CREATE TABLE aule_new (
                id INTEGER NOT NULL,
                anno_scol VARCHAR(9) NOT NULL,
                classe VARCHAR(20) NOT NULL,
                aula VARCHAR(50) NOT NULL,
                sede VARCHAR(60) NOT NULL,
                PRIMARY KEY (id),
                CONSTRAINT uq_aula_anno_classe UNIQUE (anno_scol, classe)
            )
        """))
        conn.execute(text("""
            INSERT INTO aule_new (id, anno_scol, classe, aula, sede)
            SELECT id, anno_scol, classe, aula, sede FROM aule
        """))
        conn.execute(text("DROP TABLE aule"))
        conn.execute(text("ALTER TABLE aule_new RENAME TO aule"))
        conn.commit()
        print("Migrazione: vincolo tabella 'aule' corretto a UNIQUE(anno_scol, classe).")


def _backfill_anno_scol_banca_ore():
    """
    Popola la colonna 'anno_scol' per i movimenti di banca ore storici
    che non ce l'hanno ancora (creati prima che questa colonna esistesse).

    Prima di questa correzione il saldo banca ore era un totale cumulativo
    infinito, senza alcun concetto di anno scolastico: due docenti con
    movimenti di anni diversi venivano sommati insieme in un unico saldo
    perenne. Da qui in avanti ogni movimento nuovo riceve anno_scol
    automaticamente dalla propria data (vedi models/movimento_banca_ore.py),
    ma i movimenti già esistenti nel database vanno corretti una volta sola.

    Idempotente: aggiorna solo le righe con anno_scol ancora NULL.
    """
    from sqlalchemy import text
    from models.movimento_banca_ore import anno_scol_da_data

    with db.engine.connect() as conn:
        t_exists = conn.execute(text(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='banca_ore'"
        )).fetchone()
        if not t_exists:
            return

        cols = [row[1] for row in conn.execute(text("PRAGMA table_info(banca_ore)"))]
        if 'anno_scol' not in cols:
            return  # _auto_migrate() non ancora passata da qui

        righe = conn.execute(text(
            "SELECT id, data FROM banca_ore WHERE anno_scol IS NULL"
        )).fetchall()
        if not righe:
            return

        for id_riga, data_str in righe:
            if not data_str:
                continue
            anno_iso, mese, giorno = data_str.split('-')
            from datetime import date as _date
            data_obj = _date(int(anno_iso), int(mese), int(giorno))
            anno_scol = anno_scol_da_data(data_obj)
            conn.execute(text(
                "UPDATE banca_ore SET anno_scol = :a WHERE id = :id"
            ), {'a': anno_scol, 'id': id_riga})

        conn.commit()
        print(f"Migrazione: anno_scol assegnato a {len(righe)} movimenti banca ore storici.")


def _pulizia_log(base_dir):
    """Elimina log accessi più vecchi di 180 giorni (Provvedimento Garante 27/11/2008)."""
    from datetime import timezone
    GIORNI_CONSERVAZIONE = 180
    try:
        with db.engine.connect() as conn:
            from sqlalchemy import text
            conn.execute(text(
                "DELETE FROM log_accessi WHERE timestamp < datetime('now', :delta)"
            ), {'delta': f'-{GIORNI_CONSERVAZIONE} days'})
            conn.commit()
    except Exception as e:
        print(f'Pulizia log fallita: {e}')


def _backup_automatico(base_dir):
    """Crea backup giornaliero cifrato del database all'avvio."""
    db_path    = os.path.join(base_dir, 'database.db')
    backup_dir = os.path.join(base_dir, 'data', 'backup')
    os.makedirs(backup_dir, exist_ok=True)
    if not os.path.exists(db_path):
        return
    oggi = datetime.now().strftime('%Y%m%d')
    # Controlla se esiste già un backup di oggi (cifrato)
    gia_fatto = any(
        f.startswith(f'database_{oggi}') and f.endswith('.db.enc')
        for f in os.listdir(backup_dir)
    )
    if not gia_fatto:
        from modules.backup_cifrato import crea_backup_cifrato, pulisci_vecchi_backup
        try:
            dest = crea_backup_cifrato(db_path, backup_dir)
            pulisci_vecchi_backup(backup_dir, max_backup=60)
        except Exception as e:
            print(f'Backup cifrato fallito: {e}')
            # Fallback: backup non cifrato
            bk_path = os.path.join(backup_dir, f'database_{oggi}.db')
            if not os.path.exists(bk_path):
                shutil.copy2(db_path, bk_path)



def _seed_dipartimenti_materie():
    """
    Inserisce dipartimenti e materie se non esistono ancora.
    Idempotente: non sovrascrive record esistenti.
    """
    from models.materia import Dipartimento, Materia
    if Dipartimento.query.first():
        return  # Già popolato

    import json

    DIPS = [
        {'sigla': 'LING-LET',  'nome': 'Linguistico-Letterario',       'ordine': 1},
        {'sigla': 'LINGUE',    'nome': 'Lingue Straniere',              'ordine': 2},
        {'sigla': 'MAT-SCI',   'nome': 'Matematico-Scientifico',        'ordine': 3},
        {'sigla': 'SC-UM',     'nome': 'Scienze Umane e Sociali',       'ordine': 4},
        {'sigla': 'TEC-AFM',   'nome': 'Tecnico AFM-RIM',               'ordine': 5},
        {'sigla': 'TEC-CAT',   'nome': 'Tecnico Costruzioni (CAT)',     'ordine': 6},
        {'sigla': 'SC-MOT',    'nome': 'Scienze Motorie e Sportive',    'ordine': 7},
        {'sigla': 'SOS',      'nome': 'Sostegno',                      'ordine': 8},
    ]

    dip_map = {}
    for d in DIPS:
        obj = Dipartimento(nome=d['nome'], sigla=d['sigla'], ordine=d['ordine'])
        db.session.add(obj)
        db.session.flush()
        dip_map[d['sigla']] = obj.id

    # (nome, sigla, sigla_dip, codice_orario, indirizzi)
    MATERIE = [
        # ── LINGUISTICO-LETTERARIO ────────────────────────────────────────
        ('Lingua e letteratura italiana',   'ITA',      'LING-LET', 'ITALIANO',        ['LLI','LSC','LSP','LSU','AFM','RIM','CAT']),
        ('Lingua e cultura latina',         'LAT',      'LING-LET', 'LATINO',          ['LLI','LSC','LSU']),
        ('Storia e geografia',              'STO-GEO',  'LING-LET', 'FILO-STO',        ['LLI','LSC','LSP','LSU','AFM','RIM','CAT']),
        ('Storia',                          'STO',      'LING-LET', 'STORIA',          ['LLI','LSC','LSP','LSU','AFM','RIM','CAT']),
        ('Disegno e storia dell\'arte',     'DIS-ARTE', 'LING-LET', 'DIS-ST.ARTE',    ['LSC']),
        ('Storia dell\'arte',               'ST-ARTE',  'LING-LET', 'ST.ARTE',         ['LLI','LSU']),
        # ── LINGUE STRANIERE ──────────────────────────────────────────────
        ('Inglese',                         'ING',      'LINGUE',   'INGLESE',         ['LLI','LSC','LSP','LSU','AFM','RIM','CAT']),
        ('Inglese conversazione',           'ING-CONV', 'LINGUE',   'INGL. CONV.',     ['LLI']),
        ('Tedesco',                         'TED',      'LINGUE',   'TEDESCO',         ['LLI','AFM','RIM']),
        ('Tedesco conversazione',           'TED-CONV', 'LINGUE',   'TED CONV',        ['LLI']),
        ('Spagnolo',                        'SPA',      'LINGUE',   'SPAGNOLO',        ['LLI','RIM']),
        ('Spagnolo conversazione',          'SPA-CONV', 'LINGUE',   'SPA CONV',        ['LLI']),
        # ── MATEMATICO-SCIENTIFICO ────────────────────────────────────────
        ('Matematica',                      'MAT',      'MAT-SCI',  'MATEMATICA',      ['LLI','LSC','LSP','LSU','AFM','RIM','CAT']),
        ('Matematica e Fisica',             'MAT-FIS',  'MAT-SCI',  'MATE-FIS',        ['LLI','LSC','LSU']),
        ('Fisica',                          'FIS',      'MAT-SCI',  'FISICA',          ['LLI','LSC','LSP','AFM','CAT']),
        ('Scienze naturali',                'SCI',      'MAT-SCI',  'SCIENZE',         ['LLI','LSC','LSP','LSU','AFM','CAT']),
        ('Chimica',                         'CHI',      'MAT-SCI',  'CHIMICA',         ['AFM','CAT']),
        ('Informatica',                     'INFO',     'MAT-SCI',  'INFORMATICA',     ['AFM','RIM','CAT']),
        ('Tecnologie informatiche',         'TEC-INFO', 'MAT-SCI',  None,              ['CAT']),
        # Riforma 2026-27: nelle classi prime AFM e CAT Scienze integrate → Scienze sperimentali
        ('Scienze sperimentali',            'SCI-SPER', 'MAT-SCI',  'SCI.SPERIM.',     ['AFM','CAT']),
        # ── SCIENZE UMANE E SOCIALI ───────────────────────────────────────
        ('Scienze umane',                   'SC-UM',    'SC-UM',    'SC.UMANE',        ['LSU']),
        ('Filosofia',                       'FILO',     'SC-UM',    'FILOSOFIA',       ['LLI','LSC','LSP','LSU']),
        ('Religione cattolica / att. alt.', 'REL',      'SC-UM',    'RELIGIONE',       ['LLI','LSC','LSP','LSU','AFM','RIM','CAT']),
        # ── TECNICO AFM-RIM ───────────────────────────────────────────────
        ('Diritto ed economia',             'DIR-ECO',  'TEC-AFM',  'DIR-ECO',         ['AFM','CAT','LSP','LSU']),
        ('Diritto',                         'DIR',      'TEC-AFM',  None,              ['RIM']),
        ('Relazioni internazionali',        'REL-INT',  'TEC-AFM',  'DIR-ECO-REL INT', ['RIM']),
        ('Economia aziendale',              'EC-AZ',    'TEC-AFM',  'EC.AZ.',          ['AFM','RIM']),
        ('Economia aziendale e geopolitica','EC-AZ-GEO','TEC-AFM',  None,              ['RIM']),
        ('Diritto ed economia dello sport', 'DIR-SPORT','TEC-AFM',  None,              ['LSP']),
        # ── TECNICO-COSTRUZIONI CAT ───────────────────────────────────────
        ('Topografia',                      'TOPO',     'TEC-CAT',  'TOPOGRAFIA',      ['CAT']),
        ('Geopodologia ed estimo',          'GEO-EST',  'TEC-CAT',  'GEOP.',           ['CAT']),
        ('Progettazione Costruzioni Impianti','PCI',    'TEC-CAT',  'PCI',             ['CAT']),
        ('Gestione cantiere e sicurezza',   'CANT-SIC', 'TEC-CAT',  'CANTIERE',        ['CAT']),
        ('Tecnologie e tecniche di rappres. grafica','TTRG','TEC-CAT','T.T.R.G.',      ['CAT']),
        ('TTRG Stato avanzamento lavori',   'TTRG-SAL', 'TEC-CAT',  'T.T.R.G. STA',   ['CAT']),
        ('Topografia e cantiere',           'TOPO-CANT','TEC-CAT',  'TOPO-CANT',       ['CAT']),
        # ── SCIENZE MOTORIE ───────────────────────────────────────────────
        ('Scienze motorie e sportive',      'SC-MOT',   'SC-MOT',   'SC.MOTORIE',      ['LLI','LSC','LSP','LSU','AFM','RIM','CAT']),
        ('Discipline sportive',             'DISC-SP',  'SC-MOT',   'DISC.SPORTIVE',   ['LSP']),
        ('Scienze e discipline sportive',   'SC-DISC-SP','SC-MOT',  'SC.DISC.SPORTIVE',['LSP']),
        # ── SOSTEGNO ─────────────────────────────────────────────────────
        ('Sostegno',                        'SOS',      'SOS',    'SOSTEGNO',        ['LLI','LSC','LSP','LSU','AFM','RIM','CAT']),
    ]

    for nome, sigla, dip_sigla, cod_orario, indirizzi in MATERIE:
        m = Materia(
            nome            = nome,
            sigla           = sigla,
            id_dipartimento = dip_map[dip_sigla],
            codice_orario   = cod_orario,
            indirizzi_json  = json.dumps(indirizzi),
        )
        db.session.add(m)

    db.session.commit()
    print(f"Seed: {len(DIPS)} dipartimenti, {len(MATERIE)} materie inserite.")



def _seed_sospensioni():
    """Inserisce le sospensioni didattiche standard 2025-26 se non esistono."""
    from models.sospensione import SospensioneDidattica
    if SospensioneDidattica.query.count() > 0:
        return
    from datetime import date
    SOSPENSIONI = [
        # Festività nazionali fisse
        ('2025-11-01', '2025-11-01', 'Tutti i Santi',              'festività_nazionale'),
        ('2025-12-08', '2025-12-08', 'Immacolata Concezione',      'festività_nazionale'),
        ('2026-01-06', '2026-01-06', 'Epifania',                   'festività_nazionale'),
        ('2026-04-25', '2026-04-25', 'Festa della Liberazione',    'festività_nazionale'),
        ('2026-05-01', '2026-05-01', 'Festa del Lavoro',           'festività_nazionale'),
        ('2026-06-02', '2026-06-02', 'Festa della Repubblica',     'festività_nazionale'),
        # Vacanze natalizie
        ('2025-12-22', '2026-01-07', 'Vacanze natalizie',          'vacanze_natale'),
        # Vacanze pasquali (indicative — da aggiornare)
        ('2026-04-02', '2026-04-07', 'Vacanze pasquali',           'vacanze_pasqua'),
    ]
    for ini, fin, desc, tipo in SOSPENSIONI:
        db.session.add(SospensioneDidattica(
            data_inizio = date.fromisoformat(ini),
            data_fine   = date.fromisoformat(fin),
            descrizione = desc,
            tipo        = tipo,
        ))
    db.session.commit()
    print(f"Seed: {len(SOSPENSIONI)} sospensioni inserite.")


if __name__ == '__main__':
    app = create_app()
    if os.environ.get('CARONTE_SKIP_LOGIN') == '1':
        if os.environ.get('CARONTE_DEBUG') == '1':
            print('\n' + '=' * 60)
            print('  ATTENZIONE: CARONTE_SKIP_LOGIN=1 — login DISATTIVATO')
            print('  Accesso automatico come utente "dsga". Solo per test locali.')
            print('=' * 60 + '\n')
        else:
            print('\n' + '=' * 60)
            print('  CARONTE_SKIP_LOGIN=1 impostata ma IGNORATA: serve anche')
            print('  CARONTE_DEBUG=1 per attivare il bypass del login.')
            print('=' * 60 + '\n')
    # Debugger interattivo Werkzeug SPENTO di default: se acceso (debug=True)
    # e l'app è raggiungibile da altri dispositivi in LAN (host=0.0.0.0,
    # necessario perché più postazioni — segreteria/DSGA/DS — accedono alla
    # stessa istanza), chiunque sulla rete può eseguire codice arbitrario
    # sul server dalla pagina di errore. Per il debug locale: CARONTE_DEBUG=1.
    # use_reloader resta sempre attivo (riavvio automatico ai salvataggi),
    # è indipendente dal debugger e non ha questo rischio.
    debug_attivo = os.environ.get('CARONTE_DEBUG') == '1'
    app.run(debug=debug_attivo, use_reloader=True, host='0.0.0.0', port=5002)
