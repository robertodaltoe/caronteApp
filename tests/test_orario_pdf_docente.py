"""
Test per la griglia oraria stampabile del singolo docente (Sessione 69
addendum 10): Roberto voleva poter stampare SOLO l'orario settimanale
(non tutto il report banca ore), e per i docenti con cattedra assegnata
ma senza orario importato (casi reali Rignanese/Mascolo, addendum 7)
un modulo vuoto da compilare a mano.
"""
from datetime import date

from models import db
from models.orario_docente import OrarioDocente, griglia_settimanale
from tests.conftest import crea_docente


def _crea_tabelle(app):
    with app.app_context():
        db.create_all()
    if 'report' not in app.blueprints:
        from routes.report import report_bp
        app.register_blueprint(report_bp)
    if not getattr(app, '_jinja_loader_reale', False):
        import os
        from jinja2 import FileSystemLoader
        templates_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'templates')
        app.jinja_loader = FileSystemLoader(templates_dir)
        app._jinja_loader_reale = True


# ── griglia_settimanale() ────────────────────────────────────────────

def test_griglia_settimanale_con_orario_reale(app, db_session):
    _crea_tabelle(app)
    with app.app_context():
        d = crea_docente('Santagata')
        db.session.add(OrarioDocente(id_docente=d.id, giorno=0, ora=1,
                                      classe='5ARIM', materia='DIRITTO', tipo_ora='lezione'))
        db.session.add(OrarioDocente(id_docente=d.id, giorno=2, ora=3,
                                      classe='4ALSP', materia='DIRITTO', tipo_ora='lezione'))
        db.session.commit()

        orario, ore_list, giorni_usati = griglia_settimanale(d.id)
        assert ore_list == [1, 3]
        assert giorni_usati == [0, 2]
        assert orario[0][1].classe == '5ARIM'
        assert orario[2][3].classe == '4ALSP'


def test_griglia_settimanale_vuota_senza_completa(app, db_session):
    _crea_tabelle(app)
    with app.app_context():
        d = crea_docente('Rignanese')
        orario, ore_list, giorni_usati = griglia_settimanale(d.id)
        assert orario == {}
        assert ore_list == []
        assert giorni_usati == []


def test_griglia_settimanale_vuota_completa_se_vuota(app, db_session):
    """Il caso Rignanese/Mascolo: nessun orario, ma per la stampa serve
    comunque un modello pieno (tutti i giorni, ore 1-9) da compilare a mano."""
    _crea_tabelle(app)
    with app.app_context():
        d = crea_docente('Mascolo')
        orario, ore_list, giorni_usati = griglia_settimanale(d.id, completa_se_vuota=True)
        assert orario == {}
        assert ore_list == list(range(1, 10))
        assert giorni_usati == list(range(6))


def test_griglia_settimanale_con_dati_ignora_completa_se_vuota(app, db_session):
    """completa_se_vuota non deve allargare la griglia di chi ha già
    un orario reale (solo i giorni/ore che usa davvero)."""
    _crea_tabelle(app)
    with app.app_context():
        d = crea_docente('Santagata')
        db.session.add(OrarioDocente(id_docente=d.id, giorno=0, ora=1,
                                      classe='5ARIM', materia='DIRITTO', tipo_ora='lezione'))
        db.session.commit()
        orario, ore_list, giorni_usati = griglia_settimanale(d.id, completa_se_vuota=True)
        assert ore_list == [1]
        assert giorni_usati == [0]


# ── route report.orario_pdf ──────────────────────────────────────────

def test_orario_pdf_docente_con_orario(app, db_session):
    _crea_tabelle(app)
    with app.app_context():
        d = crea_docente('Santagata')
        db.session.add(OrarioDocente(id_docente=d.id, giorno=0, ora=1,
                                      classe='5ARIM', materia='DIRITTO', tipo_ora='lezione'))
        db.session.commit()
        id_docente = d.id

    with app.test_client() as c:
        r = c.get(f'/report/docente/{id_docente}/orario-pdf')
        assert r.status_code == 200


def test_orario_pdf_docente_senza_orario_non_va_in_errore(app, db_session):
    """Il caso Rignanese/Mascolo: nessuna riga di orario, la pagina deve
    comunque rispondere (modulo vuoto), non andare in errore."""
    _crea_tabelle(app)
    with app.app_context():
        d = crea_docente('Rignanese')
        id_docente = d.id

    with app.test_client() as c:
        r = c.get(f'/report/docente/{id_docente}/orario-pdf')
        assert r.status_code == 200
        # WeasyPrint puo' essere disponibile o no a seconda dell'ambiente
        # (vedi routes/report.py): se genera un vero PDF, il corpo e'
        # binario e va verificato solo per tipo, non decodificato come
        # testo (altrimenti fallisce su byte non-UTF8 di un PDF vero).
        if r.mimetype == 'text/html':
            assert 'Nessun orario importato' in r.get_data(as_text=True)
        else:
            assert r.mimetype == 'application/pdf'
