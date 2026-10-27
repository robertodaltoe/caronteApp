"""
Docenti "Più scuole" (giorni di presenza + orario spezzato): funzione
unica docente_in_sede/motivo_non_in_sede, esclusione dai suggerimenti
supplenza (con "mostra comunque") e avvisi di incoerenza nella scheda.
"""
from datetime import date

from models import db
from models.orario_docente import OrarioDocente
from modules.suggerimenti_supplenza import (avvisi_multi_sede, docente_in_sede,
                                            motivo_non_in_sede)
from tests.conftest import crea_docente

LUNEDI = date(2026, 9, 21)
MARTEDI = date(2026, 9, 22)


def _multi(cognome, giorni='0', uscita=None):
    d = crea_docente(cognome)
    d.altra_scuola = 'IIS Altrove'
    d.giorni_presenza = giorni
    d.ora_uscita_json = uscita
    db.session.commit()
    return d


def test_funzione_giorni_e_orario_spezzato(app, db_session):
    d = _multi('Multi', giorni='0,2', uscita='{"0": 3}')
    assert docente_in_sede(d, 0, 3)
    assert not docente_in_sede(d, 0, 4)          # dopo l'ora di uscita
    assert not docente_in_sede(d, 1, 2)          # martedì non presente
    assert not docente_in_sede(d, 1)             # anche senza ora


def test_docente_normale_sempre_in_sede(app, db_session):
    d = crea_docente('Normale')
    assert docente_in_sede(d, 3, 7)


def test_multi_sede_senza_giorni_non_filtra(app, db_session):
    d = _multi('SenzaGiorni', giorni=None)
    assert motivo_non_in_sede(d, 4, 1) is None


def test_avvisi_scheda(app, db_session):
    senza = _multi('Senza', giorni=None)
    assert any('Nessun giorno' in a for a in avvisi_multi_sede(senza))
    incoerente = _multi('Incoerente', giorni='0', uscita='{"2": 3}')
    assert any('Mercoledì' in a for a in avvisi_multi_sede(incoerente))
    ok = _multi('Ok', giorni='0', uscita='{"0": 3}')
    assert avvisi_multi_sede(ok) == []
    assert avvisi_multi_sede(crea_docente('Normale')) == []


def _prepara(app):
    from routes.supplenze import supplenze_bp
    from models.indisponibilita_ricorrente import IndisponibilitaRicorrente  # noqa
    from models.attivita_fuori_aula import AttivitaFuoriAula, AttivitaClasse  # noqa
    db.create_all()
    if 'supplenze' not in app.blueprints:
        app.register_blueprint(supplenze_bp)


def _slot(d, giorno, ora):
    db.session.add(OrarioDocente(id_docente=d.id, giorno=giorno, ora=ora,
                                 classe='1A TEST', materia='T', tipo_ora='lezione'))


def _ids(payload):
    return {d['id'] for g in payload['gruppi'] for d in g['docenti']}


def test_suggerimenti_escludono_fuori_sede_e_mostra_comunque(app, db_session):
    _prepara(app)
    uscita = _multi('Spezzato', giorni='0,1', uscita='{"0": 3}')
    altro_giorno = _multi('Altrove', giorni='1')       # lunedì altrove
    normale = crea_docente('Normale')
    for d in (uscita, altro_giorno, normale):
        _slot(d, 0, 8)                                   # ha ore il lunedì
    db.session.commit()

    with app.test_client() as c:
        p = c.get(f'/api/suggerimenti?data={LUNEDI.isoformat()}&ora=5').get_json()
        assert _ids(p) == {normale.id}
        assert p['n_non_in_sede_nascosti'] == 2

        p = c.get(f'/api/suggerimenti?data={LUNEDI.isoformat()}&ora=5&mostra_comunque=1').get_json()
        assert _ids(p) == {normale.id, uscita.id, altro_giorno.id}
        g = next(g for g in p['gruppi'] if g['key'] == 'non_in_sede')
        assert {d['id'] for d in g['docenti']} == {uscita.id, altro_giorno.id}
        assert p['n_non_in_sede_nascosti'] == 0

        # ora 3 (entro l'uscita): "Spezzato" è in sede, "Altrove" no
        p = c.get(f'/api/suggerimenti?data={LUNEDI.isoformat()}&ora=3').get_json()
        assert _ids(p) == {normale.id, uscita.id}


def test_adiacenza_prec_succ_pura():
    from modules.suggerimenti_supplenza import adiacenza_prec_succ
    assert adiacenza_prec_succ({2, 3}, 4) == (True, False)
    assert adiacenza_prec_succ({5}, 4) == (False, True)
    assert adiacenza_prec_succ({3, 5}, 4) == (True, True)
    assert adiacenza_prec_succ({1, 7}, 4) == (False, False)


def test_suggerimenti_indicano_prec_succ_e_codice_cc(app, db_session):
    _prepara(app)
    from models.classe_concorso import ClasseConcorso
    cc = ClasseConcorso(codice='A012', nome='Discipline letterarie')
    db.session.add(cc)
    db.session.flush()
    solo_prec = crea_docente('SoloPrec')
    solo_prec.id_classe_concorso = cc.id
    entrambe = crea_docente('Entrambe')
    lontano = crea_docente('Lontano')
    for d, ore in ((solo_prec, (4,)), (entrambe, (4, 6)), (lontano, (1,))):
        for o in ore:
            _slot(d, 0, o)
    db.session.commit()

    with app.test_client() as c:
        p = c.get(f'/api/suggerimenti?data={LUNEDI.isoformat()}&ora=5').get_json()
    per_id = {d['id']: d for g in p['gruppi'] for d in g['docenti']}
    assert (per_id[solo_prec.id]['ora_prec'], per_id[solo_prec.id]['ora_succ']) == (True, False)
    assert (per_id[entrambe.id]['ora_prec'], per_id[entrambe.id]['ora_succ']) == (True, True)
    assert (per_id[lontano.id]['ora_prec'], per_id[lontano.id]['ora_succ']) == (False, False)
    assert per_id[solo_prec.id]['materia'] == 'A012'


def test_prec_succ_ignora_ore_non_in_servizio(app, db_session):
    """Regressione (Tramontana): un'ora di orario in cui il docente è
    assente o con validità scaduta non deve dare il badge 'prec.' né
    far considerare il docente 'in servizio' quel giorno."""
    from models.assenza import Assenza
    _prepara(app)
    assente_ora1 = crea_docente('AssenteOra1')
    _slot(assente_ora1, 0, 1)
    _slot(assente_ora1, 0, 4)                 # unica ora davvero in servizio
    scaduto = crea_docente('Scaduto')
    _slot(scaduto, 0, 1)
    db.session.flush()
    OrarioDocente.query.filter_by(id_docente=scaduto.id).update(
        {'data_fine_validita': date(2026, 9, 1)})
    db.session.add(Assenza(id_docente=assente_ora1.id, data=LUNEDI,
                           ora_inizio=1, ora_fine=1, motivo='permesso_orario'))
    db.session.commit()

    with app.test_client() as c:
        p = c.get(f'/api/suggerimenti?data={LUNEDI.isoformat()}&ora=2').get_json()
    per_id = {d['id']: d for g in p['gruppi'] for d in g['docenti']}
    assert per_id[assente_ora1.id]['ora_prec'] is False
    assert scaduto.id not in per_id           # nessuna ora valida: non in servizio
