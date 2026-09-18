"""
Roberto: poter aggiungere a un evento del Piano delle Attività interi
gruppi di docenti che hanno un incarico (referenti di dipartimento,
coordinatori, membri di una commissione...) invece di spuntarli a mano
uno per uno.

Il modello dati (CategoriaIncarico/TipoIncarico/IncaricaDocente,
menu "Incarichi") esisteva già e non è mai stato vuoto: riusa la
stessa funzione già scritta per la checklist di "Altra riunione" nel
generatore CdC (routes/generatore_cdc.py::_docenti_per_riunione_extra),
qui solo per popolare un selettore rapido nel form dell'evento.

Copre solo il filo che collega form() -> selettori_incarico (i test di
_docenti_per_riunione_extra stessa vivono già in
tests/test_eventi_unici.py, non duplicati qui).
"""
from datetime import date

from models import db
from models.incarico import CategoriaIncarico, TipoIncarico, IncaricaDocente
from tests.conftest import crea_docente


def _crea_tabelle(app):
    with app.app_context():
        from models.attivita_ist import AttivitaIst  # noqa
        db.create_all()


def _registra_blueprint(app, monkeypatch):
    from routes.attivita_ist import attivita_ist_bp
    if 'attivita_ist' not in app.blueprints:
        app.register_blueprint(attivita_ist_bp)
    import routes.attivita_ist as mod
    catturato = {}
    monkeypatch.setattr(mod, 'render_template',
                         lambda nome, **k: catturato.update(kwargs=k) or '<html></html>')
    return catturato


def test_form_passa_selettori_incarico_con_dati_reali(app, db_session, monkeypatch):
    _crea_tabelle(app)
    catturato = _registra_blueprint(app, monkeypatch)

    d = crea_docente('Novelli')
    cat = CategoriaIncarico(codice='strutturale', nome='Incarichi strutturali', ordine=1)
    db.session.add(cat)
    db.session.flush()
    tipo = TipoIncarico(nome='Referente di dipartimento', categoria=cat.codice,
                         collegato_a='dipartimento', attivo=True)
    db.session.add(tipo)
    db.session.flush()
    anno_corrente = f'{date.today().year}-{date.today().year + 1}' \
        if date.today().month >= 9 else f'{date.today().year - 1}-{date.today().year}'
    db.session.add(IncaricaDocente(anno_scol=anno_corrente, id_tipo_incarico=tipo.id,
                                    id_docente=d.id))
    db.session.commit()

    with app.test_client() as c:
        r = c.get('/attivita-ist/nuova')
        assert r.status_code == 200

    selettori = catturato['kwargs']['selettori_incarico']
    labels = {s['label']: s['docenti_ids'] for s in selettori}
    assert 'Referente di dipartimento' in labels
    assert d.id in labels['Referente di dipartimento']


def test_form_selettori_incarico_vuoto_se_nessun_incarico_assegnato(app, db_session, monkeypatch):
    _crea_tabelle(app)
    catturato = _registra_blueprint(app, monkeypatch)
    crea_docente('Bianchi')

    with app.test_client() as c:
        r = c.get('/attivita-ist/nuova')
        assert r.status_code == 200

    assert catturato['kwargs']['selettori_incarico'] == []
