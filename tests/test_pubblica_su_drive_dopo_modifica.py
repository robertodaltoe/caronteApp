"""
Test per modules/auto_sync.py::pubblica_su_drive_se_possibile() (Sessione
69 addendum 5): dopo che Roberto ha segnalato un falso "conflitto da
un'altra postazione" causato da una modifica in-place a una supplenza
gia' pubblicata su Drive (il giro periodico di sync ripubblica solo le
righe NUOVE, mai gli aggiornamenti a una riga esistente), le route che
modificano assenze/supplenze/indisponibilita' gia' esistenti ripubblicano
subito la copia locale su Drive dopo il commit.

Qui si verifica solo che ogni route interessata chiami la funzione dopo
il salvataggio -- il comportamento della funzione stessa (fallire in
silenzio se Drive non e' raggiungibile) è già quello, collaudato, di
routes/sync_conflitti.py::risolvi().
"""
from datetime import date

from models import db
from models.supplenza import Supplenza
from models.assenza import Assenza
from models.indisponibilita import Indisponibilita
from concorrenza import versione_str
from tests.conftest import crea_docente


def _crea_tabelle(app):
    with app.app_context():
        from models.attivita_ist import AttivitaIst, AttivitaIstPartecipante, AttivitaIstPresenza  # noqa
        from models.scambio_orario import ScambioOrario, ScambioSlot  # noqa
        db.create_all()
    for nome, bp_modulo, bp_nome in [
        ('supplenze', 'routes.supplenze', 'supplenze_bp'),
        ('assenze', 'routes.assenze', 'assenze_bp'),
        ('indisponibilita', 'routes.indisponibilita', 'indisp_bp'),
        ('dashboard', 'routes.dashboard', 'dashboard_bp'),
    ]:
        if nome not in app.blueprints:
            mod = __import__(bp_modulo, fromlist=[bp_nome])
            app.register_blueprint(getattr(mod, bp_nome))


def test_assegna_supplenza_ripubblica_su_drive(app, db_session, monkeypatch):
    _crea_tabelle(app)
    with app.app_context():
        assente = crea_docente('Assente')
        sostituto = crea_docente('Sostituto')
        s = Supplenza(data=date(2026, 9, 15), ora=1, classe='5ACAT',
                       id_assente=assente.id, stato='scoperta')
        db.session.add(s)
        db.session.commit()

        chiamate = []
        import routes.supplenze as mod_route
        monkeypatch.setattr(mod_route, 'pubblica_su_drive_se_possibile',
                             lambda: chiamate.append(1))

        with app.test_client() as c:
            r = c.post(f'/supplenze/{s.id}/assegna', data={
                'id_sostituto': str(sostituto.id), 'tipo': 'recupero',
                'versione': versione_str(s.modificato_il),
            }, follow_redirects=False)
            assert r.status_code in (302, 200)

        assert chiamate == [1]


def test_annulla_supplenza_ripubblica_su_drive(app, db_session, monkeypatch):
    _crea_tabelle(app)
    with app.app_context():
        assente = crea_docente('Assente')
        s = Supplenza(data=date(2026, 9, 15), ora=1, classe='5ACAT',
                       id_assente=assente.id, stato='scoperta')
        db.session.add(s)
        db.session.commit()

        chiamate = []
        import routes.supplenze as mod_route
        monkeypatch.setattr(mod_route, 'pubblica_su_drive_se_possibile',
                             lambda: chiamate.append(1))

        with app.test_client() as c:
            c.post(f'/supplenze/{s.id}/annulla', data={
                'versione': versione_str(s.modificato_il),
            })

        assert chiamate == [1]


def test_modifica_assenza_ripubblica_su_drive(app, db_session, monkeypatch):
    _crea_tabelle(app)
    with app.app_context():
        d = crea_docente('Bruni')
        a = Assenza(id_docente=d.id, data=date(2026, 9, 15), ora_inizio=1,
                     ora_fine=9, motivo='malattia')
        db.session.add(a)
        db.session.commit()
        id_ass = a.id

        chiamate = []
        import routes.assenze as mod_route
        monkeypatch.setattr(mod_route, 'pubblica_su_drive_se_possibile',
                             lambda: chiamate.append(1))

        with app.test_client() as c:
            c.post(f'/assenze/{id_ass}/modifica', data={
                'data': '2026-09-15', 'ora_inizio': '1', 'ora_fine': '9',
                'motivo': 'permesso_personale', 'id_docente': str(d.id),
            })

        assert chiamate == [1]


def test_modifica_indisponibilita_ripubblica_su_drive(app, db_session, monkeypatch):
    _crea_tabelle(app)
    with app.app_context():
        d = crea_docente('Bruni')
        i = Indisponibilita(id_docente=d.id, data=date(2026, 9, 15), ora=1,
                              motivo='colloqui')
        db.session.add(i)
        db.session.commit()
        id_indisp = i.id

        chiamate = []
        import routes.indisponibilita as mod_route
        monkeypatch.setattr(mod_route, 'pubblica_su_drive_se_possibile',
                             lambda: chiamate.append(1))

        with app.test_client() as c:
            c.post(f'/indisponibilita/{id_indisp}/modifica', data={
                'id_docente': str(d.id), 'data': '2026-09-16', 'ora': '2',
                'motivo': 'riunione',
            })

        assert chiamate == [1]


def test_pubblica_su_drive_se_possibile_non_solleva_se_drive_assente(app, db_session):
    """Se Google Drive non e' configurato/raggiungibile, la funzione non
    deve mai far fallire la richiesta che l'ha chiamata (fallisce solo in
    log) -- comportamento gia' in uso in sync_conflitti.py::risolvi."""
    with app.app_context():
        from modules.auto_sync import pubblica_su_drive_se_possibile
        pubblica_su_drive_se_possibile()  # non deve sollevare
