"""
Roberto: per protocollare le sostituzioni degli scrutini deve aprire
ogni evento (una classe per volta) e cercare il campo protocollo — per
un blocco di scrutini con molte classi vuole invece un riepilogo unico.

La vista è raggruppata per SOSTITUTO, non per assente: in segreteria il
decreto si prepara per ogni docente che sostituisce qualcuno,
elencando tutte le sue coperture (classi/orari diversi, anche di
assenti diversi) sotto lo stesso numero di protocollo — un solo
documento per persona, non uno per ogni singola sostituzione. Il campo
protocollo è lo stesso record SostituzioneScrutinio.n_protocollo usato
nella pagina per-evento: non serve nessuna sincronizzazione, sono le
stesse righe viste da due pagine diverse.
"""
from datetime import date
from models import db
from models.attivita_ist import AttivitaIst
from models.sostituzione_scrutinio import SostituzioneScrutinio
from tests.conftest import crea_docente


def _evento(classe, data=date(2026, 8, 31), ora_inizio='10:00'):
    ev = AttivitaIst(tipo='scrutinio', titolo=f'Scrutinio {classe}', classe=classe,
                      data=data, ora_inizio=ora_inizio, ora_fine='11:00', origine='manuale')
    db.session.add(ev)
    db.session.flush()
    return ev


def _cattura(monkeypatch, modulo):
    catturato = {}
    def _finto_render(template_name, **kwargs):
        catturato['kwargs'] = kwargs
        return '<html></html>'
    monkeypatch.setattr(modulo, 'render_template', _finto_render)
    return catturato


def test_senza_filtro_data_mostra_solo_le_non_protocollate(app, db_session, monkeypatch):
    import routes.attivita_ist as mod
    if 'attivita_ist' not in app.blueprints:
        app.register_blueprint(mod.attivita_ist_bp)
    catturato = _cattura(monkeypatch, mod)

    assente = crea_docente('Assente')
    sost1 = crea_docente('Sostituto1')
    sost2 = crea_docente('Sostituto2')
    db.session.commit()

    ev1 = _evento('3A LSC')
    ev2 = _evento('3B LSC')
    db.session.add(SostituzioneScrutinio(id_attivita=ev1.id, id_assente=assente.id,
                                          id_sostituto=sost1.id, n_protocollo=None))
    db.session.add(SostituzioneScrutinio(id_attivita=ev2.id, id_assente=assente.id,
                                          id_sostituto=sost2.id, n_protocollo='42/2026'))
    db.session.commit()

    with app.test_client() as c:
        r = c.get('/attivita-ist/protocollazione')
        assert r.status_code == 200

    gruppi = catturato['kwargs']['gruppi']
    sostituti_id = {g['sostituto'].id for g in gruppi}
    assert sost1.id in sostituti_id
    assert sost2.id not in sostituti_id  # già protocollata, esclusa senza filtro data


def test_con_filtro_data_mostra_anche_le_gia_protocollate(app, db_session, monkeypatch):
    import routes.attivita_ist as mod
    if 'attivita_ist' not in app.blueprints:
        app.register_blueprint(mod.attivita_ist_bp)
    catturato = _cattura(monkeypatch, mod)

    assente = crea_docente('Assente2')
    sost = crea_docente('Sostituto3')
    db.session.commit()

    ev = _evento('4A CAT', data=date(2026, 8, 30))
    db.session.add(SostituzioneScrutinio(id_attivita=ev.id, id_assente=assente.id,
                                          id_sostituto=sost.id, n_protocollo='7/2026'))
    db.session.commit()

    with app.test_client() as c:
        r = c.get('/attivita-ist/protocollazione?data_da=2026-08-30&data_a=2026-08-31')
        assert r.status_code == 200

    gruppi = catturato['kwargs']['gruppi']
    assert len(gruppi) == 1
    assert gruppi[0]['sostituto'].id == sost.id
    assert gruppi[0]['protocollo'] == '7/2026'


def test_stesso_sostituto_su_piu_classi_forma_un_solo_gruppo(app, db_session, monkeypatch):
    """Caso reale descritto da Roberto: Dal Toè sostituisce due
    assenti diversi in due classi/orari diversi lo stesso giorno — un
    solo decreto, un solo gruppo con entrambe le coperture."""
    import routes.attivita_ist as mod
    if 'attivita_ist' not in app.blueprints:
        app.register_blueprint(mod.attivita_ist_bp)
    catturato = _cattura(monkeypatch, mod)

    tizio = crea_docente('Tizio')
    caio = crea_docente('Caio')
    dal_toe = crea_docente("Dal Toè")
    db.session.commit()

    ev1 = _evento('1A CAT', ora_inizio='10:00')
    ev2 = _evento('5A RIM', ora_inizio='16:00')
    db.session.add(SostituzioneScrutinio(id_attivita=ev1.id, id_assente=tizio.id,
                                          id_sostituto=dal_toe.id, n_protocollo=None))
    db.session.add(SostituzioneScrutinio(id_attivita=ev2.id, id_assente=caio.id,
                                          id_sostituto=dal_toe.id, n_protocollo=None))
    db.session.commit()

    with app.test_client() as c:
        r = c.get('/attivita-ist/protocollazione')
        assert r.status_code == 200

    gruppi = catturato['kwargs']['gruppi']
    assert len(gruppi) == 1
    assert gruppi[0]['sostituto'].id == dal_toe.id
    assert len(gruppi[0]['righe']) == 2
    assert gruppi[0]['righe'][0].attivita.ora_inizio == '10:00'
    assert gruppi[0]['righe'][1].attivita.ora_inizio == '16:00'


def test_salvataggio_protocollo_aggiorna_tutte_le_righe_del_gruppo(app, db_session):
    import routes.attivita_ist as mod
    if 'attivita_ist' not in app.blueprints:
        app.register_blueprint(mod.attivita_ist_bp)

    tizio = crea_docente('Tizio2')
    caio = crea_docente('Caio2')
    sost = crea_docente('Sostituto4')
    db.session.commit()

    ev1 = _evento('1A RIM')
    ev2 = _evento('2A RIM')
    sost1 = SostituzioneScrutinio(id_attivita=ev1.id, id_assente=tizio.id,
                                   id_sostituto=sost.id, n_protocollo=None)
    sost2 = SostituzioneScrutinio(id_attivita=ev2.id, id_assente=caio.id,
                                   id_sostituto=sost.id, n_protocollo=None)
    db.session.add_all([sost1, sost2])
    db.session.commit()
    ids = f'{sost1.id},{sost2.id}'

    with app.test_client() as c:
        r = c.post('/attivita-ist/protocollazione', data={
            'ids_sostituzione': ids, 'n_protocollo': '99/2026',
            'data_da': '', 'data_a': '',
        })
        assert r.status_code == 302

    db.session.refresh(sost1)
    db.session.refresh(sost2)
    assert sost1.n_protocollo == '99/2026'
    assert sost2.n_protocollo == '99/2026'


def test_protocolli_diversi_nel_gruppo_vengono_segnalati(app, db_session, monkeypatch):
    """Dati residui inseriti prima di questa vista (protocolli diversi
    per lo stesso sostituto): non deve essere scelto in automatico un
    valore — il gruppo va segnalato come tale."""
    import routes.attivita_ist as mod
    if 'attivita_ist' not in app.blueprints:
        app.register_blueprint(mod.attivita_ist_bp)
    catturato = _cattura(monkeypatch, mod)

    tizio = crea_docente('Tizio3')
    caio = crea_docente('Caio3')
    sost = crea_docente('Sostituto5')
    db.session.commit()

    ev1 = _evento('3A LSU', data=date(2026, 8, 30))
    ev2 = _evento('4A LSU', data=date(2026, 8, 30))
    db.session.add(SostituzioneScrutinio(id_attivita=ev1.id, id_assente=tizio.id,
                                          id_sostituto=sost.id, n_protocollo='10/2026'))
    db.session.add(SostituzioneScrutinio(id_attivita=ev2.id, id_assente=caio.id,
                                          id_sostituto=sost.id, n_protocollo='11/2026'))
    db.session.commit()

    with app.test_client() as c:
        r = c.get('/attivita-ist/protocollazione?data_da=2026-08-30&data_a=2026-08-30')
        assert r.status_code == 200

    gruppi = catturato['kwargs']['gruppi']
    assert len(gruppi) == 1
    assert gruppi[0]['protocolli_diversi'] is True
    assert gruppi[0]['protocollo'] == ''


def test_export_excel_produce_un_file_xlsx(app, db_session):
    import routes.attivita_ist as mod
    if 'attivita_ist' not in app.blueprints:
        app.register_blueprint(mod.attivita_ist_bp)

    assente = crea_docente('Assente4')
    sost = crea_docente('Sostituto6')
    db.session.commit()

    ev = _evento('2B AFM')
    db.session.add(SostituzioneScrutinio(id_attivita=ev.id, id_assente=assente.id,
                                          id_sostituto=sost.id, n_protocollo=None))
    db.session.commit()

    with app.test_client() as c:
        r = c.get('/attivita-ist/protocollazione/export')
        assert r.status_code == 200
        assert r.mimetype == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
