"""
Roberto: dopo aver aggiornato le date di alcune attività nel Piano
delle Attività, ha chiesto dove poter verificare se ci sono
sovrapposizioni con altre riunioni già impostate, con indicati anche i
docenti coinvolti su più riunioni — includendo anche i docenti
tutor/esperti delle attività dei Progetti FSE/FESR.

Copre:
1. modules/verifica_sovrapposizioni_riunioni.py::trova_sovrapposizioni_riunioni()
   (nuovo) — riunione vs riunione.
2. routes/attivita_ist.py::verifica_sovrapposizioni() — combina il
   punto 1 con modules/conflitti_progetti_fse.py::trova_conflitti_progetti_fse()
   (già esistente, riunione vs sessione Progetti FSE/FESR) in un'unica
   pagina raggiungibile da "Attività Istituzionali".
"""
from datetime import date

from models import db
from models.attivita_ist import AttivitaIst, AttivitaIstPartecipante
from tests.conftest import crea_docente
from modules.verifica_sovrapposizioni_riunioni import trova_sovrapposizioni_riunioni


def _crea_tabelle(app):
    with app.app_context():
        db.create_all()


def _registra_blueprint(app, monkeypatch=None):
    from routes.attivita_ist import attivita_ist_bp
    if 'attivita_ist' not in app.blueprints:
        app.register_blueprint(attivita_ist_bp)
    if monkeypatch is not None:
        # base.html si aspetta un'app completa (navbar con link a tutti
        # i blueprint, context processor csrf/permessi) che la fixture
        # 'app' leggera non ha -- si cattura direttamente cosa la route
        # passa al template invece di renderizzare l'HTML per intero,
        # stesso pattern di test_progetti_fse.py.
        import routes.attivita_ist as mod
        catturato = {}
        monkeypatch.setattr(mod, 'render_template',
                             lambda nome, **k: catturato.update(kwargs=k) or '<html></html>')
        return catturato
    return None


def _evento(tipo, titolo, data_ev, ora_ini, ora_fine, classe=None):
    ev = AttivitaIst(tipo=tipo, titolo=titolo, classe=classe, data=data_ev,
                      ora_inizio=ora_ini, ora_fine=ora_fine, origine='manuale')
    db.session.add(ev)
    db.session.flush()
    return ev


# ── trova_sovrapposizioni_riunioni() ───────────────────────────────

def test_trova_sovrapposizione_per_docente_su_due_riunioni(app, db_session):
    _crea_tabelle(app)
    d = crea_docente('Fontana')

    ev1 = _evento('consiglio_classe', 'CdC 3A LSU', date(2027, 5, 10), '14:00', '16:00', '3A LSU')
    ev2 = _evento('scrutinio', 'Scrutinio 2B CAT', date(2027, 5, 10), '15:00', '17:00', '2B CAT')
    db.session.add(AttivitaIstPartecipante(id_attivita=ev1.id, id_docente=d.id))
    db.session.add(AttivitaIstPartecipante(id_attivita=ev2.id, id_docente=d.id))
    db.session.commit()

    sovrapposizioni = trova_sovrapposizioni_riunioni()
    assert len(sovrapposizioni) == 1
    s = sovrapposizioni[0]
    assert s['docente'].id == d.id
    assert {s['evento1'].id, s['evento2'].id} == {ev1.id, ev2.id}


def test_nessuna_sovrapposizione_se_orari_non_si_accavallano(app, db_session):
    _crea_tabelle(app)
    d = crea_docente('Bianchi')

    ev1 = _evento('consiglio_classe', 'CdC 3A LSU', date(2027, 5, 10), '14:00', '15:00', '3A LSU')
    ev2 = _evento('scrutinio', 'Scrutinio 2B CAT', date(2027, 5, 10), '15:00', '16:00', '2B CAT')
    db.session.add(AttivitaIstPartecipante(id_attivita=ev1.id, id_docente=d.id))
    db.session.add(AttivitaIstPartecipante(id_attivita=ev2.id, id_docente=d.id))
    db.session.commit()

    assert trova_sovrapposizioni_riunioni() == []


def test_nessuna_sovrapposizione_se_docenti_diversi(app, db_session):
    _crea_tabelle(app)
    d1 = crea_docente('Verdi')
    d2 = crea_docente('Neri')

    ev1 = _evento('consiglio_classe', 'CdC 3A LSU', date(2027, 5, 10), '14:00', '16:00', '3A LSU')
    ev2 = _evento('scrutinio', 'Scrutinio 2B CAT', date(2027, 5, 10), '15:00', '17:00', '2B CAT')
    db.session.add(AttivitaIstPartecipante(id_attivita=ev1.id, id_docente=d1.id))
    db.session.add(AttivitaIstPartecipante(id_attivita=ev2.id, id_docente=d2.id))
    db.session.commit()

    assert trova_sovrapposizioni_riunioni() == []


def test_sovrapposizione_su_giorni_diversi_non_conta(app, db_session):
    _crea_tabelle(app)
    d = crea_docente('Gialli')

    ev1 = _evento('consiglio_classe', 'CdC 3A LSU', date(2027, 5, 10), '14:00', '16:00', '3A LSU')
    ev2 = _evento('scrutinio', 'Scrutinio 2B CAT', date(2027, 5, 11), '14:00', '16:00', '2B CAT')
    db.session.add(AttivitaIstPartecipante(id_attivita=ev1.id, id_docente=d.id))
    db.session.add(AttivitaIstPartecipante(id_attivita=ev2.id, id_docente=d.id))
    db.session.commit()

    assert trova_sovrapposizioni_riunioni() == []


def test_filtro_data_da_esclude_sovrapposizioni_passate(app, db_session):
    _crea_tabelle(app)
    d = crea_docente('Rossi')

    ev1 = _evento('consiglio_classe', 'CdC vecchio', date(2020, 5, 10), '14:00', '16:00')
    ev2 = _evento('scrutinio', 'Scrutinio vecchio', date(2020, 5, 10), '15:00', '17:00')
    db.session.add(AttivitaIstPartecipante(id_attivita=ev1.id, id_docente=d.id))
    db.session.add(AttivitaIstPartecipante(id_attivita=ev2.id, id_docente=d.id))
    db.session.commit()

    assert trova_sovrapposizioni_riunioni(data_da=date(2027, 1, 1)) == []
    assert len(trova_sovrapposizioni_riunioni()) == 1


# ── route: pagina combinata ─────────────────────────────────────────

def test_route_verifica_sovrapposizioni_mostra_entrambe_le_fonti(app, db_session, monkeypatch):
    """La pagina deve mostrare sia le sovrapposizioni riunione-riunione
    sia quelle riunione-sessione FSE (già coperte da
    trova_conflitti_progetti_fse, qui solo riusate)."""
    from models.progetto_fse import ProgettoFSE, ModuloFSE, IncaricoFSE, SessioneFSE

    with app.app_context():
        db.create_all()
    catturato = _registra_blueprint(app, monkeypatch)

    d1 = crea_docente('Fontana')
    d2 = crea_docente('Esperto')

    ev1 = _evento('consiglio_classe', 'CdC 3A LSU', date(2027, 5, 10), '14:00', '16:00', '3A LSU')
    ev2 = _evento('scrutinio', 'Scrutinio 2B CAT', date(2027, 5, 10), '15:00', '17:00', '2B CAT')
    db.session.add(AttivitaIstPartecipante(id_attivita=ev1.id, id_docente=d1.id))
    db.session.add(AttivitaIstPartecipante(id_attivita=ev2.id, id_docente=d1.id))

    p = ProgettoFSE(titolo='Piano Estate', codice_progetto='X', cup='Y', tipo_costo='ucs')
    db.session.add(p)
    db.session.flush()
    m = ModuloFSE(id_progetto=p.id, titolo='Modulo test', ore=30)
    db.session.add(m)
    db.session.flush()
    db.session.add(IncaricoFSE(id_modulo=m.id, id_docente=d2.id, ruolo='esperto'))
    db.session.add(SessioneFSE(id_modulo=m.id, data=date(2027, 5, 10),
                                ora_inizio='09:00', ora_fine='11:00'))
    ev3 = _evento('formazione', 'Corso formazione', date(2027, 5, 10), '10:00', '12:00')
    db.session.add(AttivitaIstPartecipante(id_attivita=ev3.id, id_docente=d2.id))
    db.session.commit()

    with app.test_client() as c:
        r = c.get('/attivita-ist/verifica-sovrapposizioni?solo_future=0')
        assert r.status_code == 200

    kwargs = catturato['kwargs']
    assert len(kwargs['sovrapposizioni']) == 1
    assert kwargs['sovrapposizioni'][0]['docente'].id == d1.id
    assert len(kwargs['conflitti_fse']) == 1
    assert kwargs['conflitti_fse'][0]['docente'].id == d2.id
    assert kwargs['conflitti_fse'][0]['modulo'].titolo == 'Modulo test'


def test_route_verifica_sovrapposizioni_reachable_senza_dati(app, db_session, monkeypatch):
    with app.app_context():
        db.create_all()
    catturato = _registra_blueprint(app, monkeypatch)

    with app.test_client() as c:
        r = c.get('/attivita-ist/verifica-sovrapposizioni')
        assert r.status_code == 200

    assert catturato['kwargs']['sovrapposizioni'] == []
    assert catturato['kwargs']['conflitti_fse'] == []
