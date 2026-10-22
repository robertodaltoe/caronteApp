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


# ── export Excel ─────────────────────────────────────────────────────

def test_genera_xlsx_sovrapposizioni_contiene_tutti_i_fogli(app, db_session):
    """genera_xlsx_sovrapposizioni() non passa da render_template (nessun
    problema di template_folder/base.html) -- verificabile direttamente."""
    from modules.verifica_sovrapposizioni_riunioni import genera_xlsx_sovrapposizioni

    _crea_tabelle(app)
    d = crea_docente('Novelli')
    ev1 = _evento('consiglio_classe', 'CdC 3A LSU', date(2027, 5, 10), '14:00', '16:00', '3A LSU')
    ev2 = _evento('scrutinio', 'Scrutinio 2B CAT', date(2027, 5, 10), '15:00', '17:00', '2B CAT')
    db.session.add(AttivitaIstPartecipante(id_attivita=ev1.id, id_docente=d.id))
    db.session.add(AttivitaIstPartecipante(id_attivita=ev2.id, id_docente=d.id))
    db.session.commit()

    sovrapposizioni = trova_sovrapposizioni_riunioni()
    wb = genera_xlsx_sovrapposizioni(sovrapposizioni, [])

    assert wb.sheetnames == ['Riunione - riunione', 'Riunione - sessione FSE-FESR',
                              'Riunione - lezione', 'Stessa classe', 'Presenza DS']
    ws1 = wb['Riunione - riunione']
    assert ws1['A1'].value == 'Data'
    assert ws1.cell(row=2, column=1).value == '10/05/2027'
    assert 'Novelli' in ws1.cell(row=2, column=6).value


def test_route_verifica_sovrapposizioni_xlsx_scarica_un_file_valido(app, db_session):
    with app.app_context():
        db.create_all()
    _registra_blueprint(app)
    d = crea_docente('Novelli')
    ev1 = _evento('consiglio_classe', 'CdC 3A LSU', date(2027, 5, 10), '14:00', '16:00', '3A LSU')
    ev2 = _evento('scrutinio', 'Scrutinio 2B CAT', date(2027, 5, 10), '15:00', '17:00', '2B CAT')
    db.session.add(AttivitaIstPartecipante(id_attivita=ev1.id, id_docente=d.id))
    db.session.add(AttivitaIstPartecipante(id_attivita=ev2.id, id_docente=d.id))
    db.session.commit()

    with app.test_client() as c:
        r = c.get('/attivita-ist/verifica-sovrapposizioni/xlsx?solo_future=0')
        assert r.status_code == 200
        assert r.mimetype == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        assert r.data[:2] == b'PK'  # xlsx è uno zip


# ── nuove verifiche: classe, DS, lezioni, multi-giorno ───────────────

def test_sovrapposizione_stessa_classe_senza_docenti_in_comune(app, db_session):
    from modules.verifica_sovrapposizioni_riunioni import trova_sovrapposizioni_classe
    _crea_tabelle(app)
    _evento('consiglio_classe', 'CdC', date(2027, 5, 10), '14:00', '16:00', '3A LSU')
    _evento('scrutinio', 'Scrutinio', date(2027, 5, 10), '15:00', '17:00', '3ALSU')
    _evento('scrutinio', 'Altra classe', date(2027, 5, 10), '15:00', '17:00', '2B CAT')
    db.session.commit()
    ris = trova_sovrapposizioni_classe()
    assert len(ris) == 1
    assert ris[0]['classe'] == '3A LSU'
    assert trova_sovrapposizioni_riunioni() == []


def test_sovrapposizione_ds_solo_se_entrambi_lo_richiedono(app, db_session):
    from modules.verifica_sovrapposizioni_riunioni import trova_sovrapposizioni_ds
    _crea_tabelle(app)
    a = _evento('consiglio_classe', 'A', date(2027, 5, 10), '14:00', '16:00', '3A LSU')
    b = _evento('consiglio_classe', 'B', date(2027, 5, 10), '15:00', '17:00', '2B CAT')
    c = _evento('collegio', 'C', date(2027, 5, 10), '15:00', '17:00')
    a.richiede_ds = b.richiede_ds = True
    db.session.commit()
    ris = trova_sovrapposizioni_ds()
    assert len(ris) == 1
    assert {ris[0]['evento1'].id, ris[0]['evento2'].id} == {a.id, b.id}


def test_sovrapposizione_considera_le_giornate_di_attivita_multigiorno(app, db_session):
    from models.attivita_ist import AttivitaIstSessione
    _crea_tabelle(app)
    d = crea_docente('Multi')
    corso = _evento('formazione', 'Corso', date(2027, 5, 10), '09:00', '10:00')
    db.session.add_all([
        AttivitaIstSessione(id_attivita=corso.id, data=date(2027, 5, 10), ora_inizio='09:00', ora_fine='10:00'),
        AttivitaIstSessione(id_attivita=corso.id, data=date(2027, 5, 12), ora_inizio='14:00', ora_fine='16:00'),
    ])
    cdc = _evento('consiglio_classe', 'CdC', date(2027, 5, 12), '15:00', '17:00', '3A LSU')
    for ev in (corso, cdc):
        db.session.add(AttivitaIstPartecipante(id_attivita=ev.id, id_docente=d.id))
    db.session.commit()
    ris = trova_sovrapposizioni_riunioni()
    assert len(ris) == 1
    assert ris[0]['data'] == date(2027, 5, 12)
    assert ris[0]['ora1'] == ('14:00', '16:00')


def test_riunione_vs_lezione_pomeridiana_anche_in_giornata_di_sessione(app, db_session):
    from models.attivita_ist import AttivitaIstSessione
    from models.orario_docente import OrarioDocente
    from modules.verifica_orario_riunioni import trova_conflitti_orario_riunioni
    _crea_tabelle(app)
    d = crea_docente('Lezione')
    ev = _evento('formazione', 'Corso', date(2027, 5, 10), '09:00', '10:00')
    db.session.add_all([
        AttivitaIstSessione(id_attivita=ev.id, data=date(2027, 5, 10), ora_inizio='09:00', ora_fine='10:00'),
        # mercoledi' 12/05/2027 = giorno 2, 7ª ora 13:25-14:25
        AttivitaIstSessione(id_attivita=ev.id, data=date(2027, 5, 12), ora_inizio='14:00', ora_fine='16:00'),
        AttivitaIstPartecipante(id_attivita=ev.id, id_docente=d.id),
        OrarioDocente(id_docente=d.id, giorno=2, ora=7, classe='3A LSU', materia='Storia', tipo_ora='lezione'),
        # lunedi' mattina: non controllato
        OrarioDocente(id_docente=d.id, giorno=0, ora=2, classe='3A LSU', materia='Storia', tipo_ora='lezione'),
    ])
    db.session.commit()
    ris = trova_conflitti_orario_riunioni()
    assert len(ris) == 1
    assert ris[0]['data'] == date(2027, 5, 12)
    assert ris[0]['ora_lezione'] == 7


def test_route_passa_alla_pagina_tutte_le_verifiche(app, db_session, monkeypatch):
    with app.app_context():
        db.create_all()
    catturato = _registra_blueprint(app, monkeypatch)
    with app.test_client() as c:
        assert c.get('/attivita-ist/verifica-sovrapposizioni?solo_future=0').status_code == 200
    k = catturato['kwargs']
    for chiave in ('conflitti_lezioni', 'sovrapposizioni_classe', 'sovrapposizioni_ds'):
        assert k[chiave] == []
