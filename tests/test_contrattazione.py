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


def test_liquida_non_sovrascrive_il_previsto(app, db_session):
    from routes.contrattazione import contrattazione_bp
    if 'contrattazione' not in app.blueprints:
        app.register_blueprint(contrattazione_bp)

    with app.app_context():
        f = FondoContrattazione(anno_scol='2026-2027', nome='FIS')
        db.session.add(f)
        db.session.flush()
        cap = CapitoloContrattazione(id_fondo=f.id, nome='PCTO', importo_assegnato=1000)
        db.session.add(cap)
        db.session.flush()
        d = _docente('BIANCHI')
        asg = AssegnazioneContrattazione(id_capitolo=cap.id, id_docente=d.id,
                                          descrizione='Tutor', importo=300, stato='comunicato')
        db.session.add(asg)
        db.session.commit()

        c = app.test_client()
        r = c.post(f'/contrattazione/assegnazione/{asg.id}/liquida', data={'importo_liquidato': '350'})
        assert r.status_code == 302

        db.session.refresh(asg)
        assert asg.importo == 300          # il previsto resta inalterato
        assert asg.importo_liquidato == 350
        assert asg.stato == 'liquidato'
        assert asg.data_liquidazione is not None
        assert cap.totale_assegnato_docenti == 350  # usa il liquidato, non il previsto


def test_protocollo_lettera_una_riga_per_docente_anno(app, db_session):
    from routes.contrattazione import contrattazione_bp
    from models.contrattazione import LetteraIncaricoProtocollo
    if 'contrattazione' not in app.blueprints:
        app.register_blueprint(contrattazione_bp)

    with app.app_context():
        d = _docente('VERDI')
        c = app.test_client()
        r = c.post(f'/contrattazione/lettere/docente/{d.id}/protocollo',
                   data={'anno': '2026-2027', 'numero_protocollo': '42',
                         'data_protocollo': '2026-10-01'})
        assert r.status_code == 302
        assert LetteraIncaricoProtocollo.query.count() == 1

        # Riaggiornare lo stesso docente/anno aggiorna la riga, non ne crea una seconda.
        r = c.post(f'/contrattazione/lettere/docente/{d.id}/protocollo',
                   data={'anno': '2026-2027', 'numero_protocollo': '43',
                         'data_protocollo': '2026-10-02'})
        assert r.status_code == 302
        assert LetteraIncaricoProtocollo.query.count() == 1
        riga = LetteraIncaricoProtocollo.query.first()
        assert riga.numero_protocollo == '43'


def test_catalogo_importa_accetta_blocco_senza_numero(app, db_session):
    from models.contrattazione import TipoIncaricoContrattazione

    with app.app_context():
        c = app.test_client()
        r = c.post('/contrattazione/catalogo/importa',
                   data={'testo': 'Referente biblioteca\nCatalogazione del patrimonio librario.'})
        assert r.status_code == 302
        voce = TipoIncaricoContrattazione.query.filter_by(nome='Referente biblioteca').first()
        assert voce is not None
        assert voce.numero_riferimento is None


def test_catalogo_form_senza_numero_si_salva(app, db_session):
    from models.contrattazione import TipoIncaricoContrattazione
    from routes.contrattazione import contrattazione_bp
    if 'contrattazione' not in app.blueprints:
        app.register_blueprint(contrattazione_bp)

    with app.app_context():
        c = app.test_client()
        r = c.post('/contrattazione/catalogo/nuovo',
                   data={'nome': 'Referente orientamento', 'testo_riferimento': 'Testo.'})
        assert r.status_code == 302
        voce = TipoIncaricoContrattazione.query.filter_by(nome='Referente orientamento').first()
        assert voce is not None and voce.numero_riferimento is None


def test_assegnazione_a_personale_ata(app, db_session):
    from models.contrattazione import PersonaleAta
    from routes.contrattazione import contrattazione_bp
    if 'contrattazione' not in app.blueprints:
        app.register_blueprint(contrattazione_bp)

    with app.app_context():
        f = FondoContrattazione(anno_scol='2026-2027', nome='FIS')
        db.session.add(f)
        db.session.flush()
        cap = CapitoloContrattazione(id_fondo=f.id, nome='Incarichi specifici', importo_assegnato=1000)
        db.session.add(cap)
        ata = PersonaleAta(cognome='PEPE', nome='Giusy')
        db.session.add(ata)
        db.session.commit()

        c = app.test_client()
        r = c.post(f'/contrattazione/capitolo/{cap.id}/assegnazione/nuova', data={
            'tipo_beneficiario': 'ata', 'id_personale_ata': str(ata.id),
            'descrizione': 'Primo soccorso', 'importo': '300', 'stato': 'previsto',
        })
        assert r.status_code == 302

        asg = AssegnazioneContrattazione.query.filter_by(id_personale_ata=ata.id).first()
        assert asg is not None
        assert asg.id_docente is None
        assert asg.beneficiario_tipo == 'ata'
        assert asg.beneficiario_nome_completo == 'PEPE Giusy'

        from routes.contrattazione import _assegnazioni_beneficiario
        assegnazioni = _assegnazioni_beneficiario('ata', ata.id, '2026-2027')
        assert len(assegnazioni) == 1
        assert assegnazioni[0].importo == 300


def test_ata_non_eliminabile_se_ha_assegnazioni(app, db_session):
    from models.contrattazione import PersonaleAta
    from routes.contrattazione import contrattazione_bp
    if 'contrattazione' not in app.blueprints:
        app.register_blueprint(contrattazione_bp)

    with app.app_context():
        f = FondoContrattazione(anno_scol='2026-2027', nome='FIS')
        db.session.add(f)
        db.session.flush()
        cap = CapitoloContrattazione(id_fondo=f.id, nome='Cap', importo_assegnato=100)
        db.session.add(cap)
        ata = PersonaleAta(cognome='NICOLIELLO')
        db.session.add(ata)
        db.session.flush()
        db.session.add(AssegnazioneContrattazione(id_capitolo=cap.id, id_personale_ata=ata.id,
                                                    descrizione='Assistenza', importo=150))
        db.session.commit()

        c = app.test_client()
        r = c.post(f'/contrattazione/ata/{ata.id}/elimina')
        assert r.status_code == 302
        assert PersonaleAta.query.get(ata.id) is not None  # non eliminato
