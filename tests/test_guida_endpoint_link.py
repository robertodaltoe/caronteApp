"""
Audit usabilità (Sessione 66): ogni sezione della Guida ora porta un
link diretto "Vai alla pagina" verso l'endpoint reale che descrive
(modules/guida_content.py::SEZIONI[i]['endpoint'], usato in
templates/guida/sezione.html via url_for(sez.endpoint)).

Costruire quella mappa slug -> endpoint a mano, con 27 sezioni, è
proprio il tipo di errore silenzioso facile da introdurre (un nome di
blueprint o di funzione sbagliato non dà nessun errore finché qualcuno
non apre quella sezione specifica e clicca il pulsante) — per questo
un test che registra tutti i blueprint coinvolti e verifica che
OGNI endpoint dichiarato in SEZIONI sia risolvibile da url_for(),
senza bisogno di aprire la Guida sezione per sezione a mano.

Nota anche nel devlog: durante la verifica manuale di questa mappa
un controllo fatto con create_app() senza reindirizzare il DB ha
toccato per errore database.db reale (nessun danno, verificato riga
per riga) — da qui in avanti verificare gli endpoint di guida SOLO
con questo test o su una copia isolata del DB, mai con create_app()
diretto senza redirect esplicito del path.
"""
from flask import Flask
from modules.guida_content import SEZIONI


def _app_con_tutti_i_blueprint():
    app = Flask(__name__)
    app.config['SERVER_NAME'] = 'test.local'

    from routes.agenda import agenda_bp
    from routes.att_differite import att_differite_bp
    from routes.attivita import attivita_bp
    from routes.attivita_ist import attivita_ist_bp
    from routes.cambi_quadro import cambi_bp
    from routes.dashboard import dashboard_bp
    from routes.docenti import docenti_bp
    from routes.esami_integrativi import esami_integrativi_bp
    from routes.rientro import rientro_bp
    from routes.assegnazioni import assegnazioni_bp
    from routes.banca_ore import banca_ore_bp
    from routes.report import report_bp
    from routes.recupero import recupero_bp
    from routes.piano_personale import piano_personale_bp
    from routes.impostazione_anno import impostazione_anno_bp
    from routes.sync_conflitti import sync_conflitti_bp
    from routes.incarichi import incarichi_bp
    from routes.indisponibilita import indisp_bp
    from routes.supplenze import supplenze_bp
    from routes.assenze import assenze_bp
    from routes.impostazioni import impostazioni_bp
    from routes.cambio_anno import cambio_anno_bp
    from routes.sincronizzazione import sync_bp

    for bp in [agenda_bp, att_differite_bp, attivita_bp, attivita_ist_bp, cambi_bp,
               dashboard_bp, docenti_bp, esami_integrativi_bp, rientro_bp,
               assegnazioni_bp, banca_ore_bp, report_bp, recupero_bp,
               piano_personale_bp, impostazione_anno_bp, sync_conflitti_bp,
               incarichi_bp, indisp_bp, supplenze_bp, assenze_bp, impostazioni_bp,
               cambio_anno_bp, sync_bp]:
        app.register_blueprint(bp)
    return app


def test_ogni_sezione_con_endpoint_e_risolvibile():
    app = _app_con_tutti_i_blueprint()
    sezioni_con_endpoint = [s for s in SEZIONI if s.get('endpoint')]
    assert len(sezioni_con_endpoint) >= 20  # quasi tutte le 27 sezioni ne hanno uno

    falliti = []
    with app.test_request_context():
        from flask import url_for
        for s in sezioni_con_endpoint:
            try:
                url_for(s['endpoint'])
            except Exception as e:
                falliti.append((s['slug'], s['endpoint'], str(e)))

    assert falliti == [], f"Endpoint non risolvibili nella Guida: {falliti}"
