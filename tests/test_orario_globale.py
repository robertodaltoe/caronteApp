"""
Roberto: nella griglia "Orario globale" (routes/sincronizzazione.py::orario_globale,
/orario/globale) un docente titolare e il suo ITP in compresenza
risultavano scambiati -- caso reale segnalato: 3ALLI, martedì 4ª ora,
MAY (anagrafica: ruolo='itp') mostrata come titolare (nome principale
in cella) e STRAMBINI (anagrafica: ruolo='titolare') mostrato con
l'etichetta "+ cognome" riservata all'ITP.

Causa reale: `slots_giorno = OrarioDocente.query.filter_by(...)` non ha
un ORDER BY, quindi l'ordine delle righe nella cella (slots[0] = nome
principale nel template, slots[1:] = etichetta "+ cognome" ITP)
dipendeva da quale riga capitava prima nella query -- di fatto
l'ordine di importazione, non il campo Docente.ruolo. Fix: ordinare
esplicitamente ogni cella mettendo sempre prima chi NON ha ruolo='itp'.

Verificato sui kwargs passati a render_template (l'app di test non ha
il template_folder reale, stesso pattern di test_progetti_fse.py).
"""
from models import db
from models.orario_docente import OrarioDocente
from tests.conftest import crea_docente


def _registra_blueprint(app, monkeypatch=None):
    from routes.sincronizzazione import sync_bp
    if 'sync' not in app.blueprints:
        app.register_blueprint(sync_bp)
    if monkeypatch is not None:
        import routes.sincronizzazione as mod
        catturato = {}
        monkeypatch.setattr(mod, 'render_template',
                             lambda nome, **k: catturato.update(kwargs=k) or '<html></html>')
        return catturato
    return None


def test_orario_globale_mostra_titolare_prima_dellitp_anche_se_importato_dopo(app, db_session, monkeypatch):
    """Riproduce esattamente il caso reale: la riga dell'ITP (MAY) è
    stata importata PRIMA di quella del titolare (STRAMBINI) -- id
    riga più basso, quindi verrebbe letta per prima da una query senza
    ORDER BY. La griglia deve comunque mettere il titolare per primo."""
    catturato = _registra_blueprint(app, monkeypatch)
    itp = crea_docente('May', ruolo='itp')
    titolare = crea_docente('Strambini', ruolo='titolare')

    # Ordine di inserimento = ITP prima del titolare, come nel caso
    # reale (id riga più basso per l'ITP).
    db.session.add(OrarioDocente(id_docente=itp.id, giorno=1, ora=4,
                                  classe='3ALLI', materia='TEDESCO', tipo_ora='lezione'))
    db.session.add(OrarioDocente(id_docente=titolare.id, giorno=1, ora=4,
                                  classe='3ALLI', materia='TEDESCO', tipo_ora='lezione'))
    db.session.commit()

    with app.test_client() as c:
        r = c.get('/orario/globale?giorno=1')
        assert r.status_code == 200

    slots = catturato['kwargs']['griglia']['3ALLI'][4]
    assert [s.id_docente for s in slots] == [titolare.id, itp.id], (
        "il titolare deve stare in prima posizione (slots[0], nome principale nel "
        "template), l'ITP in seconda (etichetta '+ cognome'), indipendentemente "
        "dall'ordine di importazione")


def test_orario_globale_ordine_invariato_se_gia_corretto(app, db_session, monkeypatch):
    """Nessuna regressione quando l'ordine di importazione è già
    corretto (titolare prima dell'ITP)."""
    catturato = _registra_blueprint(app, monkeypatch)
    titolare = crea_docente('Strambini', ruolo='titolare')
    itp = crea_docente('May', ruolo='itp')

    db.session.add(OrarioDocente(id_docente=titolare.id, giorno=1, ora=4,
                                  classe='3ALLI', materia='TEDESCO', tipo_ora='lezione'))
    db.session.add(OrarioDocente(id_docente=itp.id, giorno=1, ora=4,
                                  classe='3ALLI', materia='TEDESCO', tipo_ora='lezione'))
    db.session.commit()

    with app.test_client() as c:
        r = c.get('/orario/globale?giorno=1')
        assert r.status_code == 200

    slots = catturato['kwargs']['griglia']['3ALLI'][4]
    assert [s.id_docente for s in slots] == [titolare.id, itp.id]


def test_orario_globale_cella_con_un_solo_docente_non_si_rompe(app, db_session, monkeypatch):
    """Una cella con un solo docente (nessuna compresenza) non deve
    subire alcun riordino ne' errori."""
    catturato = _registra_blueprint(app, monkeypatch)
    solo = crea_docente('Rossi', ruolo='titolare')
    db.session.add(OrarioDocente(id_docente=solo.id, giorno=1, ora=2,
                                  classe='3ALLI', materia='STORIA', tipo_ora='lezione'))
    db.session.commit()

    with app.test_client() as c:
        r = c.get('/orario/globale?giorno=1')
        assert r.status_code == 200

    slots = catturato['kwargs']['griglia']['3ALLI'][2]
    assert [s.id_docente for s in slots] == [solo.id]
