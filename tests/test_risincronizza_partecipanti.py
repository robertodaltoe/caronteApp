"""
Roberto: nelle presenze di un evento pianificato con largo anticipo
(es. un Collegio di settembre generato dall'import del piano a giugno)
compaiono docenti non più in servizio — segnalati col badge, ma mai
tolti dall'elenco, perché l'elenco partecipanti viene fissato una volta
sola alla creazione dell'evento (_preset_partecipanti(), chiamato solo
lì). Roberto ha fatto notare che il problema è simmetrico: nel
frattempo possono arrivare anche nuove assunzioni, non solo uscite.

Aggiunta una risincronizzazione esplicita (mai automatica): confronta
l'elenco congelato con quello che _preset_partecipanti() calcolerebbe
ORA, propone aggiunte/rimozioni, e li applica solo dopo conferma. Non
tocca mai le righe aggiunte/modificate a mano (preset=False), né chi ha
già una presenza modificata (in quel caso segnala soltanto, per non
perdere dati già inseriti).
"""
from datetime import date, timedelta
from models import db
from models.attivita_ist import AttivitaIst, AttivitaIstPartecipante, AttivitaIstPresenza
from tests.conftest import crea_docente


def _registra_blueprint(app):
    import routes.attivita_ist as mod
    if 'attivita_ist' not in app.blueprints:
        app.register_blueprint(mod.attivita_ist_bp)


def test_propone_in_aggiunta_un_docente_assunto_dopo_la_creazione(app, db_session, monkeypatch):
    _registra_blueprint(app)
    futuro = date.today() + timedelta(days=30)

    # Al momento della creazione esisteva solo Rossi.
    rossi = crea_docente('Rossi')
    ev = AttivitaIst(tipo='collegio', titolo='Collegio', data=futuro, origine='manuale')
    db.session.add(ev)
    db.session.flush()
    db.session.add(AttivitaIstPartecipante(id_attivita=ev.id, id_docente=rossi.id, preset=True))
    db.session.commit()

    # Bianchi viene assunto dopo — deve comparire come "da aggiungere".
    bianchi = crea_docente('Bianchi')

    import routes.attivita_ist as mod
    catturato = {}
    def _finto_render(template_name, **kwargs):
        catturato['kwargs'] = kwargs
        return '<html></html>'
    monkeypatch.setattr(mod, 'render_template', _finto_render)

    with app.test_client() as c:
        r = c.get(f'/attivita-ist/{ev.id}/risincronizza')
        assert r.status_code == 200
        assert [d.id for d in catturato['kwargs']['da_aggiungere']] == [bianchi.id]

        r2 = c.post(f'/attivita-ist/{ev.id}/risincronizza')
        assert r2.status_code == 302

    ids = {p.id_docente for p in AttivitaIstPartecipante.query.filter_by(id_attivita=ev.id).all()}
    assert bianchi.id in ids
    assert rossi.id in ids


def test_rimuove_chi_non_e_piu_in_servizio_se_presenza_ancora_vergine(app, db_session, monkeypatch):
    _registra_blueprint(app)
    futuro = date.today() + timedelta(days=30)

    rossi = crea_docente('Rossi')
    uscito = crea_docente('Verdi', attivo=False)
    ev = AttivitaIst(tipo='collegio', titolo='Collegio', data=futuro, origine='manuale')
    db.session.add(ev)
    db.session.flush()
    db.session.add(AttivitaIstPartecipante(id_attivita=ev.id, id_docente=rossi.id, preset=True))
    db.session.add(AttivitaIstPartecipante(id_attivita=ev.id, id_docente=uscito.id, preset=True))
    db.session.commit()

    import routes.attivita_ist as mod
    catturato = {}
    def _finto_render(template_name, **kwargs):
        catturato['kwargs'] = kwargs
        return '<html></html>'
    monkeypatch.setattr(mod, 'render_template', _finto_render)

    with app.test_client() as c:
        r = c.get(f'/attivita-ist/{ev.id}/risincronizza')
        assert [d.id for d in catturato['kwargs']['da_rimuovibili']] == [uscito.id]

        r2 = c.post(f'/attivita-ist/{ev.id}/risincronizza')
        assert r2.status_code == 302

    ids = {p.id_docente for p in AttivitaIstPartecipante.query.filter_by(id_attivita=ev.id).all()}
    assert uscito.id not in ids
    assert rossi.id in ids
    assert AttivitaIstPresenza.query.filter_by(id_attivita=ev.id, id_docente=uscito.id).count() == 0


def test_non_rimuove_chi_ha_gia_una_presenza_modificata_a_mano(app, db_session, monkeypatch):
    _registra_blueprint(app)
    futuro = date.today() + timedelta(days=30)

    uscito = crea_docente('Verdi', attivo=False)
    ev = AttivitaIst(tipo='collegio', titolo='Collegio', data=futuro, origine='manuale')
    db.session.add(ev)
    db.session.flush()
    db.session.add(AttivitaIstPartecipante(id_attivita=ev.id, id_docente=uscito.id, preset=True))
    db.session.add(AttivitaIstPresenza(id_attivita=ev.id, id_docente=uscito.id,
                                        stato='assente', note='già segnalato a mano'))
    db.session.commit()

    import routes.attivita_ist as mod
    catturato = {}
    def _finto_render(template_name, **kwargs):
        catturato['kwargs'] = kwargs
        return '<html></html>'
    monkeypatch.setattr(mod, 'render_template', _finto_render)

    with app.test_client() as c:
        r = c.get(f'/attivita-ist/{ev.id}/risincronizza')
        assert catturato['kwargs']['da_rimuovibili'] == []
        assert [d.id for d in catturato['kwargs']['non_rimovibili']] == [uscito.id]

        c.post(f'/attivita-ist/{ev.id}/risincronizza')

    # Non rimosso: la presenza aveva già una nota inserita a mano.
    ids = {p.id_docente for p in AttivitaIstPartecipante.query.filter_by(id_attivita=ev.id).all()}
    assert uscito.id in ids


def test_non_propone_mai_in_rimozione_un_partecipante_aggiunto_a_mano(app, db_session):
    _registra_blueprint(app)
    futuro = date.today() + timedelta(days=30)

    uscito = crea_docente('Verdi', attivo=False)
    ev = AttivitaIst(tipo='collegio', titolo='Collegio', data=futuro, origine='manuale')
    db.session.add(ev)
    db.session.flush()
    # preset=False: aggiunto a mano da Roberto (es. da "+ Aggiungi docente").
    db.session.add(AttivitaIstPartecipante(id_attivita=ev.id, id_docente=uscito.id, preset=False))
    db.session.commit()

    with app.test_client() as c:
        c.post(f'/attivita-ist/{ev.id}/risincronizza')

    ids = {p.id_docente for p in AttivitaIstPartecipante.query.filter_by(id_attivita=ev.id).all()}
    assert uscito.id in ids


def test_non_disponibile_per_un_evento_gia_svolto(app, db_session):
    _registra_blueprint(app)
    passato = date.today() - timedelta(days=5)

    ev = AttivitaIst(tipo='collegio', titolo='Collegio passato', data=passato, origine='manuale')
    db.session.add(ev)
    db.session.commit()

    with app.test_client() as c:
        r = c.get(f'/attivita-ist/{ev.id}/risincronizza')
        assert r.status_code == 302
        assert r.headers['Location'].endswith(f'/attivita-ist/{ev.id}/presenze')
