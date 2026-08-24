"""
Roberto: per protocollare le sostituzioni degli scrutini deve aprire
ogni evento (una classe per volta) e cercare il campo protocollo — per
un blocco di scrutini con molte classi vuole invece un riepilogo unico
(docente assente | classe | sostituto | n. protocollo), modificabile e
esportabile in Excel. Il campo protocollo è lo stesso record
SostituzioneScrutinio.n_protocollo usato nella pagina per-evento: non
serve nessuna sincronizzazione, sono le stesse righe viste da due
pagine diverse.
"""
from datetime import date
from models import db
from models.attivita_ist import AttivitaIst
from models.sostituzione_scrutinio import SostituzioneScrutinio
from tests.conftest import crea_docente


def _evento(classe, data=date(2026, 8, 31)):
    ev = AttivitaIst(tipo='scrutinio', titolo=f'Scrutinio {classe}', classe=classe,
                      data=data, ora_inizio='10:00', ora_fine='11:00', origine='manuale')
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

    righe = catturato['kwargs']['righe']
    sostituti_id = {s.id_sostituto for s in righe}
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

    righe = catturato['kwargs']['righe']
    assert len(righe) == 1
    assert righe[0].id_sostituto == sost.id
    assert righe[0].n_protocollo == '7/2026'


def test_salvataggio_protocollo_aggiorna_la_stessa_riga_vista_altrove(app, db_session):
    import routes.attivita_ist as mod
    if 'attivita_ist' not in app.blueprints:
        app.register_blueprint(mod.attivita_ist_bp)

    assente = crea_docente('Assente3')
    sost = crea_docente('Sostituto4')
    db.session.commit()

    ev = _evento('1A RIM')
    sostituzione = SostituzioneScrutinio(id_attivita=ev.id, id_assente=assente.id,
                                          id_sostituto=sost.id, n_protocollo=None)
    db.session.add(sostituzione)
    db.session.commit()
    sost_id = sostituzione.id

    with app.test_client() as c:
        r = c.post('/attivita-ist/protocollazione', data={
            'id_sostituzione': sost_id, 'n_protocollo': '99/2026',
            'data_da': '', 'data_a': '',
        })
        assert r.status_code == 302

    db.session.refresh(sostituzione)
    assert sostituzione.n_protocollo == '99/2026'


def test_export_excel_produce_un_file_xlsx(app, db_session):
    import routes.attivita_ist as mod
    if 'attivita_ist' not in app.blueprints:
        app.register_blueprint(mod.attivita_ist_bp)

    assente = crea_docente('Assente4')
    sost = crea_docente('Sostituto5')
    db.session.commit()

    ev = _evento('2B AFM')
    db.session.add(SostituzioneScrutinio(id_attivita=ev.id, id_assente=assente.id,
                                          id_sostituto=sost.id, n_protocollo=None))
    db.session.commit()

    with app.test_client() as c:
        r = c.get('/attivita-ist/protocollazione/export')
        assert r.status_code == 200
        assert r.mimetype == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
