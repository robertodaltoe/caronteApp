"""
Quando si assegna una classe a un docente (routes/assegnazioni.py:
salva/aggiorna_ore/nomina) o gli si sincronizza una materia in un
dipartimento (_sync_docente_materie), il docente deve iscriversi da
solo agli eventi futuri di Consiglio di classe/scrutinio (per la
classe) e dipartimento/riunione materia (per il dipartimento) già
creati — vedi routes/attivita_ist.py::iscrivi_docente_a_eventi_classe
e iscrivi_docente_a_eventi_dipartimento.
"""
from datetime import date, timedelta
from models import db
from models.attivita_ist import AttivitaIst, AttivitaIstPartecipante
from models.classe_concorso import ClasseConcorso
from models.assegnazione import AssegnazioneDocente, AssegnazioneClasse
from models.materia import Dipartimento, Materia
from routes.attivita_ist import (iscrivi_docente_a_eventi_classe,
                                  iscrivi_docente_a_eventi_dipartimento)
from tests.conftest import crea_docente

DOMANI = date.today() + timedelta(days=10)
IERI   = date.today() - timedelta(days=10)


def _cc(codice='A026'):
    cc = ClasseConcorso(codice=codice, nome='Matematica')
    db.session.add(cc)
    db.session.commit()
    return cc


def _dipartimento():
    dip = Dipartimento(nome='Matematica e Fisica', sigla='MATFIS')
    db.session.add(dip)
    db.session.commit()
    mat = Materia(nome='Matematica', sigla='MAT', id_dipartimento=dip.id)
    db.session.add(mat)
    db.session.commit()
    return dip, mat


# ── Consigli di classe / scrutini ────────────────────────────────────────────

def test_assegnazione_classe_iscrive_a_consiglio_futuro(db_session):
    ev = AttivitaIst(tipo='consiglio_classe', titolo='CdC 3A LLI',
                      data=DOMANI, classe='3A LLI', origine='manuale')
    db.session.add(ev)
    db.session.commit()

    d = crea_docente('Rossi')
    n = iscrivi_docente_a_eventi_classe(d.id, ['3A LLI'])
    assert n == 1
    assert AttivitaIstPartecipante.query.filter_by(
        id_attivita=ev.id, id_docente=d.id).first() is not None


def test_assegnazione_classe_iscrive_anche_a_scrutinio(db_session):
    AttivitaIst(tipo='scrutinio', titolo='Scrutinio', data=DOMANI, classe='2B AFM')
    ev = AttivitaIst(tipo='scrutinio', titolo='Scrutinio', data=DOMANI, classe='2B AFM')
    db.session.add(ev)
    db.session.commit()

    d = crea_docente('Bianchi')
    n = iscrivi_docente_a_eventi_classe(d.id, ['2B AFM'])
    assert n == 1


def test_non_iscrive_a_classe_diversa_o_evento_passato(db_session):
    AttivitaIst.query.delete()
    ev_altra_classe = AttivitaIst(tipo='consiglio_classe', titolo='CdC 1A CAT',
                                   data=DOMANI, classe='1A CAT', origine='manuale')
    ev_passato = AttivitaIst(tipo='consiglio_classe', titolo='CdC vecchio',
                              data=IERI, classe='3A LLI', origine='manuale')
    db.session.add_all([ev_altra_classe, ev_passato])
    db.session.commit()

    d = crea_docente('Verdi')
    n = iscrivi_docente_a_eventi_classe(d.id, ['3A LLI'])
    assert n == 0


def _registra_blueprint(app):
    from routes.assegnazioni import assegnazioni_bp
    if 'assegnazioni' not in app.blueprints:
        app.register_blueprint(assegnazioni_bp)
    return app


def test_route_salva_iscrive_docente_a_consiglio_esistente(app, db_session):
    _registra_blueprint(app)
    ev = AttivitaIst(tipo='consiglio_classe', titolo='CdC 4A RIM',
                      data=DOMANI, classe='4A RIM', origine='manuale')
    db.session.add(ev)
    cc = _cc()
    d = crea_docente('Neri')
    db.session.commit()

    with app.test_client() as c:
        r = c.post('/assegnazioni/salva', data={
            'anno_scol': '2026-2027', 'id_cc': str(cc.id), 'tipo': 'titolare',
            'id_docente': str(d.id), 'ore_4A RIM': '4',
        }, follow_redirects=False)
        assert r.status_code == 302, r.data

    assert AttivitaIstPartecipante.query.filter_by(
        id_attivita=ev.id, id_docente=d.id).first() is not None


def test_route_nomina_placeholder_iscrive_docente_reale(app, db_session):
    _registra_blueprint(app)
    ev = AttivitaIst(tipo='consiglio_classe', titolo='CdC 5A CAT',
                      data=DOMANI, classe='5A CAT', origine='manuale')
    db.session.add(ev)
    cc = _cc('A040')
    db.session.commit()

    asgn = AssegnazioneDocente(anno_scol='2026-2027', id_classe_concorso=cc.id,
                                nome_placeholder='DA NOMINARE', tipo='TD')
    db.session.add(asgn)
    db.session.flush()
    db.session.add(AssegnazioneClasse(id_assegnazione=asgn.id, indirizzo='CAT',
                                       anno_corso=5, sezione='A', ore=6))
    db.session.commit()

    d = crea_docente('Gialli')
    # Nessuna iscrizione finché è solo un placeholder
    assert AttivitaIstPartecipante.query.filter_by(id_attivita=ev.id).count() == 0

    with app.test_client() as c:
        r = c.post(f'/assegnazioni/{asgn.id}/nomina',
                    data={'id_docente': str(d.id)}, follow_redirects=False)
        assert r.status_code == 302, r.data
    assert AttivitaIstPartecipante.query.filter_by(
        id_attivita=ev.id, id_docente=d.id).first() is not None


# ── Dipartimenti / riunioni materia ──────────────────────────────────────────

def test_iscrizione_dipartimento_diretta(db_session):
    dip, mat = _dipartimento()
    ev = AttivitaIst(tipo='dipartimento', titolo='Dip. Matematica',
                      data=DOMANI, id_dipartimento=dip.id, origine='manuale')
    db.session.add(ev)
    db.session.commit()

    d = crea_docente('Azzurri')
    n = iscrivi_docente_a_eventi_dipartimento(d.id, dip.id)
    assert n == 1


def test_sync_docente_materie_iscrive_a_riunione_materia(app, db_session):
    _registra_blueprint(app)
    dip, mat = _dipartimento()
    ev = AttivitaIst(tipo='riunione_materia', titolo='Riunione materia',
                      data=DOMANI, id_dipartimento=dip.id, origine='manuale')
    db.session.add(ev)
    cc = _cc('A027')
    d = crea_docente('Marroni')
    db.session.commit()

    with app.test_client() as c:
        r = c.post('/assegnazioni/salva', data={
            'anno_scol': '2026-2027', 'id_cc': str(cc.id), 'tipo': 'titolare',
            'id_docente': str(d.id), f'ore_3A LLI_{mat.id}': '4',
        }, follow_redirects=False)
        assert r.status_code == 302, r.data

    assert AttivitaIstPartecipante.query.filter_by(
        id_attivita=ev.id, id_docente=d.id).first() is not None


def test_non_duplica_se_gia_iscritto_via_classe(db_session):
    ev = AttivitaIst(tipo='consiglio_classe', titolo='CdC 1A LSU',
                      data=DOMANI, classe='1A LSU', origine='manuale')
    db.session.add(ev)
    db.session.commit()

    d = crea_docente('Blu')
    db.session.add(AttivitaIstPartecipante(
        id_attivita=ev.id, id_docente=d.id, preset=True))
    db.session.commit()

    n = iscrivi_docente_a_eventi_classe(d.id, ['1A LSU'])
    assert n == 0
    assert AttivitaIstPartecipante.query.filter_by(id_attivita=ev.id).count() == 1
