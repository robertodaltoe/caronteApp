from flask import Flask
from models import db
import os, locale, shutil

# WeasyPrint: su macOS assicura che le librerie Homebrew siano trovate
import sys as _sys
if _sys.platform == 'darwin':
    os.environ.setdefault('DYLD_LIBRARY_PATH',
        '/opt/homebrew/lib:' + os.environ.get('DYLD_LIBRARY_PATH', ''))
from datetime import datetime, timedelta

def create_app():
    app = Flask(__name__)

    base_dir = os.path.abspath(os.path.dirname(__file__))
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(base_dir, 'database.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SECRET_KEY'] = 'suplenzeapp-chiave-locale-2025'
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=8)  # fine giornata lavorativa

    db.init_app(app)

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
    from routes.email_report import email_bp
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
    app.register_blueprint(email_bp)
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
    app.register_blueprint(impostazioni_bp)
    from routes.impostazione_anno import impostazione_anno_bp
    app.register_blueprint(impostazione_anno_bp)
    from routes.recupero import recupero_bp
    app.register_blueprint(recupero_bp)
    from routes.rientro import rientro_bp
    app.register_blueprint(rientro_bp)
    from routes.att_differite import att_differite_bp
    app.register_blueprint(att_differite_bp)

    # Filtro Jinja per decodificare JSON nei template
    import json
    app.jinja_env.filters['from_json'] = lambda s: json.loads(s) if s else []
    app.jinja_env.filters['enumerate'] = enumerate

    # Protezione accesso — tutte le route tranne display e auth
    ROUTE_PUBBLICHE = {'display.display', 'auth.login', 'auth.logout',
                        'auth.privacy', 'static'}

    # Mappa blueprint -> permesso minimo richiesto
    BLUEPRINT_PERMESSI = {
        'report':        'report_r',
        'banca_ore':     'banca_ore_r',
        'docenti':       'docenti_r',
        'aule':          'aule_r',
        'supplenze':     'supplenze_r',    # lettura supplenze per tutti
        'assenze':       'assenze',         # segreteria e collaboratore
        'cambi':         'supplenze',       # solo collaboratore/dsga
        'attivita':      'attivita',        # segreteria e collaboratore
        'indisponibilita': 'assenze',       # segreteria e collaboratore
        'agenda':        'supplenze_r',
        'sync':          'dsga_only',   # solo DSGA
        'import_banca':  'banca_ore',
        'recupero':      'recupero_r',      # corsi/prove di recupero (lettura per DS, scrittura per collaboratore/segreteria/dsga)
        'rientro':       'recupero_r',      # colloqui di rientro dall'estero
        'att_differite': 'recupero_r',      # hub di selezione, nessuna azione propria
        'impostazione_anno': 'organico_r',  # classi di concorso, organico diritto/fatto
        'auth':          None,          # gestito internamente
    }

    @app.before_request
    def check_auth():
        from flask import session, redirect, url_for, request, g
        from routes.auth import get_utente_corrente, log
        endpoint = request.endpoint or ''

        if endpoint in ROUTE_PUBBLICHE or endpoint.startswith('static'):
            return None

        u = get_utente_corrente()
        if not u or not u.attivo:
            session.clear()
            return redirect(url_for('auth.login', next=request.url))

        g.utente = u

        # Controlla permesso per blueprint
        blueprint = endpoint.split('.')[0] if '.' in endpoint else ''
        permesso_richiesto = BLUEPRINT_PERMESSI.get(blueprint)

        if permesso_richiesto == 'dsga_only':
            if u.ruolo not in ('ds', 'dsga'):
                from models.log_accesso import LogAccesso
                from datetime import datetime
                db.session.add(LogAccesso(
                    id_utente=u.id, username=u.username, ruolo=u.ruolo,
                    azione='accesso_negato', dettaglio=endpoint,
                    ip=request.remote_addr, esito='denied'
                ))
                db.session.commit()
                from flask import flash
                flash('Accesso riservato al DSGA.', 'error')
                return redirect(url_for('dashboard.index'))

        elif permesso_richiesto and not u.ha_permesso(permesso_richiesto):
            from models.log_accesso import LogAccesso
            from datetime import datetime
            db.session.add(LogAccesso(
                id_utente=u.id, username=u.username, ruolo=u.ruolo,
                azione='accesso_negato', dettaglio=endpoint,
                ip=request.remote_addr, esito='denied'
            ))
            db.session.commit()
            from flask import flash
            flash('Non hai i permessi per questa sezione.', 'error')
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
        # Crea tabelle nuove + applica migrazioni colonne
        db.create_all()
        _auto_migrate()
        _seed_dipartimenti_materie()
        _seed_sospensioni()
        _backup_automatico(base_dir)
        _pulizia_log(base_dir)

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
        ('assenze',              'motivo_interno',        'VARCHAR(200)', None),
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
    app.run(debug=True, use_reloader=True, host='0.0.0.0', port=5002)
