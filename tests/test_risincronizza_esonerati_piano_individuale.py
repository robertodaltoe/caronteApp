"""
Risincronizzazione: un docente con Piano Attività Personale che NON ha
scelto l'evento non è "da rimuovere" — resta in elenco e viene segnato
automaticamente assente giustificato (segnalato da Roberto, ottobre 2026).
"""
from datetime import date, timedelta

from models import db
from tests.conftest import crea_docente


def _setup(app):
    with app.app_context():
        from models.attivita_ist import AttivitaIst, AttivitaIstPartecipante, AttivitaIstPresenza  # noqa
        from models.materia import Dipartimento, Materia, DocenteMateria  # noqa
        from models.piano_attivita_personale import PianoAttivitaPersonale, PianoAttivitaPersonaleVoce  # noqa
        from models.config_app import ConfigApp  # noqa
        db.create_all()


def _scenario():
    from models.attivita_ist import AttivitaIst, AttivitaIstPartecipante
    from models.piano_attivita_personale import (
        PianoAttivitaPersonale, PianoAttivitaPersonaleVoce, genera_token)
    d = crea_docente('Gialli')
    d.ore_contratto = 9
    d.part_time = True
    d.ore_contratto_pt = 9
    altro = crea_docente('Rossi')
    db.session.commit()
    giorno = date.today() + timedelta(days=30)
    ev = AttivitaIst(tipo='collegio', titolo='Collegio', data=giorno,
                     ora_inizio='15:00', ora_fine='17:00')
    scelto = AttivitaIst(tipo='collegio', titolo='Altro collegio',
                         data=giorno + timedelta(days=1),
                         ora_inizio='15:00', ora_fine='17:00')
    db.session.add_all([ev, scelto])
    db.session.commit()
    anno = ev.data.year if ev.data.month >= 9 else ev.data.year - 1
    p = PianoAttivitaPersonale(id_docente=d.id, anno_scol=f'{anno}-{anno + 1}',
                               token=genera_token())
    db.session.add(p)
    db.session.commit()
    db.session.add(PianoAttivitaPersonaleVoce(id_piano=p.id, id_attivita=scelto.id))
    # Il docente era già in elenco (convocato prima di compilare il piano)
    for did in (d.id, altro.id):
        db.session.add(AttivitaIstPartecipante(id_attivita=ev.id, id_docente=did, preset=True))
    db.session.commit()
    return d, altro, ev


def test_esonerato_dal_piano_non_e_da_rimuovere_ma_giustificato(app, db_session):
    _setup(app)
    with app.app_context():
        d, altro, ev = _scenario()
        from routes.attivita_ist import (_diff_risincronizzazione,
                                         _esonerati_da_giustificare,
                                         _applica_scelte_risincronizzazione,
                                         _giustifica_esonerati_da_piano)
        da_agg, da_rim, non_rim = _diff_risincronizzazione(ev)
        assert d.id not in [x.id for x in da_rim + non_rim]
        assert [x.id for x in _esonerati_da_giustificare(ev)] == [d.id]

        _applica_scelte_risincronizzazione(ev, da_agg, da_rim)
        assert _giustifica_esonerati_da_piano(ev) == 1
        db.session.commit()

        from models.attivita_ist import AttivitaIstPartecipante, AttivitaIstPresenza
        assert AttivitaIstPartecipante.query.filter_by(
            id_attivita=ev.id, id_docente=d.id).count() == 1
        pres = AttivitaIstPresenza.query.filter_by(
            id_attivita=ev.id, id_docente=d.id).one()
        assert pres.stato == 'giustificato'
        # idempotente, e non segna manuale l'evento
        assert _esonerati_da_giustificare(ev) == []
        assert not ev.partecipanti_manuali


def test_presenza_modificata_a_mano_non_viene_toccata(app, db_session):
    _setup(app)
    with app.app_context():
        d, altro, ev = _scenario()
        from models.attivita_ist import AttivitaIstPresenza
        db.session.add(AttivitaIstPresenza(id_attivita=ev.id, id_docente=d.id,
                                           stato='presente', note='arriva alle 16'))
        db.session.commit()
        from routes.attivita_ist import _esonerati_da_giustificare
        assert _esonerati_da_giustificare(ev) == []


# ── Eventi nuovi: l'esonerato compare subito come giustificato ───────────────

def _registra_blueprint(app):
    import routes.attivita_ist as mod
    if 'attivita_ist' not in app.blueprints:
        app.register_blueprint(mod.attivita_ist_bp)


def test_evento_nuovo_dal_form_include_esonerato_come_giustificato(app, db_session):
    _setup(app)
    _registra_blueprint(app)
    with app.app_context():
        d, altro, ev = _scenario()
        from models.attivita_ist import AttivitaIst, AttivitaIstPartecipante, AttivitaIstPresenza
        giorno = ev.data + timedelta(days=5)
        with app.test_client() as c:
            r = c.post('/attivita-ist/nuova', data={
                'tipo': 'collegio', 'titolo': 'Collegio nuovo', 'data': giorno.isoformat()})
            assert r.status_code == 302
        nuovo = AttivitaIst.query.filter_by(titolo='Collegio nuovo').one()
        assert AttivitaIstPartecipante.query.filter_by(
            id_attivita=nuovo.id, id_docente=d.id).count() == 1
        pres = AttivitaIstPresenza.query.filter_by(
            id_attivita=nuovo.id, id_docente=d.id).one()
        assert pres.stato == 'giustificato'
        assert pres.note == 'Piano attività individuale'
        altro_pres = AttivitaIstPresenza.query.filter_by(
            id_attivita=nuovo.id, id_docente=altro.id).first()
        assert altro_pres is None or altro_pres.stato == 'presente'
        # l'esonerato non è un convocato per i controlli di sovrapposizione
        assert d.id not in nuovo.partecipanti_convocati_ids
        assert altro.id in nuovo.partecipanti_convocati_ids


def test_risincronizza_aggiunge_esonerato_mancante_come_giustificato(app, db_session):
    _setup(app)
    with app.app_context():
        d, altro, ev = _scenario()
        from models.attivita_ist import AttivitaIstPartecipante, AttivitaIstPresenza
        AttivitaIstPartecipante.query.filter_by(id_attivita=ev.id, id_docente=d.id).delete()
        db.session.commit()
        from routes.attivita_ist import (_diff_risincronizzazione,
                                         _applica_scelte_risincronizzazione,
                                         _giustifica_esonerati_da_piano)
        da_agg, da_rim, _ = _diff_risincronizzazione(ev)
        assert d.id in [x.id for x in da_agg]
        _applica_scelte_risincronizzazione(ev, da_agg, da_rim)
        db.session.flush()
        _giustifica_esonerati_da_piano(ev)
        db.session.commit()
        assert AttivitaIstPresenza.query.filter_by(
            id_attivita=ev.id, id_docente=d.id).one().stato == 'giustificato'
        assert not ev.partecipanti_manuali
