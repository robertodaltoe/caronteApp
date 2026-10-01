"""Contrattazione integrativa: fondo -> capitolo -> assegnazione, con
spostamento tra capitoli tracciato nello storico (vedi
models/contrattazione.py per il flusso completo)."""
import pytest

from models import db
from models.docente import Docente
from models.contrattazione import (
    FondoContrattazione, CapitoloContrattazione, AssegnazioneContrattazione,
    StoricoSpostamentoCapitolo,
)
from routes.contrattazione import contrattazione_bp


@pytest.fixture(autouse=True)
def _registra_blueprint(app):
    if 'contrattazione' not in app.blueprints:
        app.register_blueprint(contrattazione_bp)


def _docente(cognome='ROSSI'):
    d = Docente(cognome=cognome, nome='Mario', nome_display=cognome)
    db.session.add(d)
    db.session.flush()
    return d


def test_fondo_calcoli(app, db_session):
    with app.app_context():
        f = FondoContrattazione(anno_scol='2026-2027', nome='FMOF',
                                 economie_pregresse=9191.81, importo_assegnato=71000,
                                 quota_dsga=4250.47)
        db.session.add(f)
        db.session.commit()
        assert f.totale_disponibile == round(9191.81 + 71000, 2)
        assert f.importo_contrattabile == round(9191.81 + 71000 - 4250.47, 2)
        assert f.saldo_non_ripartito == f.importo_contrattabile  # nessun capitolo ancora


def test_capitolo_saldo_e_sforamento(app, db_session):
    with app.app_context():
        f = FondoContrattazione(anno_scol='2026-2027', nome='FIS')
        db.session.add(f)
        db.session.flush()
        cap = CapitoloContrattazione(id_fondo=f.id, nome='PCTO', importo_assegnato=1000)
        db.session.add(cap)
        db.session.flush()
        d = _docente()
        db.session.add(AssegnazioneContrattazione(id_capitolo=cap.id, id_docente=d.id,
                                                    descrizione='Tutor', importo=600))
        db.session.commit()
        assert cap.totale_assegnato_docenti == 600
        assert cap.saldo_residuo == 400
        assert not cap.sforato

        db.session.add(AssegnazioneContrattazione(id_capitolo=cap.id, id_docente=d.id,
                                                    descrizione='Tutor 2', importo=500))
        db.session.commit()
        assert cap.saldo_residuo == -100
        assert cap.sforato


def test_spostamento_tra_capitoli_via_route(app, db_session):
    with app.app_context():
        f = FondoContrattazione(anno_scol='2026-2027', nome='FIS')
        db.session.add(f)
        db.session.flush()
        cap1 = CapitoloContrattazione(id_fondo=f.id, nome='Valorizzazione', importo_assegnato=1000)
        cap2 = CapitoloContrattazione(id_fondo=f.id, nome='PCTO', importo_assegnato=1000)
        db.session.add_all([cap1, cap2])
        db.session.flush()
        d = _docente()
        asg = AssegnazioneContrattazione(id_capitolo=cap1.id, id_docente=d.id,
                                          descrizione='Commissione', importo=250)
        db.session.add(asg)
        db.session.commit()

        c = app.test_client()
        r = c.post(f'/contrattazione/assegnazione/{asg.id}/sposta',
                   data={'id_capitolo_nuovo': str(cap2.id), 'motivo': 'rettifica criteri'})
        assert r.status_code == 302

        db.session.refresh(asg)
        assert asg.id_capitolo == cap2.id
        storico = StoricoSpostamentoCapitolo.query.filter_by(id_assegnazione=asg.id).all()
        assert len(storico) == 1
        assert storico[0].id_capitolo_precedente == cap1.id
        assert storico[0].id_capitolo_nuovo == cap2.id
        assert storico[0].importo_al_momento == 250
        assert storico[0].motivo == 'rettifica criteri'


def test_eliminare_fondo_elimina_a_cascata(app, db_session):
    with app.app_context():
        f = FondoContrattazione(anno_scol='2026-2027', nome='FIS')
        db.session.add(f)
        db.session.flush()
        cap = CapitoloContrattazione(id_fondo=f.id, nome='PCTO', importo_assegnato=100)
        db.session.add(cap)
        db.session.flush()
        d = _docente()
        db.session.add(AssegnazioneContrattazione(id_capitolo=cap.id, id_docente=d.id,
                                                    descrizione='Tutor', importo=50))
        db.session.commit()

        db.session.delete(f)
        db.session.commit()
        assert CapitoloContrattazione.query.count() == 0
        assert AssegnazioneContrattazione.query.count() == 0


def test_catalogo_importa_salta_nomi_duplicati(app, db_session):
    from models.contrattazione import TipoIncaricoContrattazione

    with app.app_context():
        db.session.add(TipoIncaricoContrattazione(nome='Collaboratore DS', testo_riferimento='vecchio testo'))
        db.session.commit()
        c = app.test_client()
        r = c.post('/contrattazione/catalogo/importa',
                   data={'testo': 'Collaboratore DS\nnuovo testo che non deve sostituire.'})
        assert r.status_code == 302
        assert TipoIncaricoContrattazione.query.count() == 1
        assert TipoIncaricoContrattazione.query.first().testo_riferimento == 'vecchio testo'
