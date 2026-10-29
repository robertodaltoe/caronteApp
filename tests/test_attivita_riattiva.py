"""Un'attività fuori aula annullata si può riattivare."""
from datetime import date, timedelta
from models import db
from models.attivita_fuori_aula import AttivitaFuoriAula
import models.attivita_accompagnatore  # noqa
import models.migrazione_slot  # noqa


def test_annullata_in_lista_e_riattivabile(app, db_session):
    with app.app_context():
        db.create_all()
    from routes.attivita import attivita_bp
    app.register_blueprint(attivita_bp)
    app.add_url_rule('/', 'index', lambda: '')
    d = date.today() + timedelta(days=3)
    with app.app_context():
        a = AttivitaFuoriAula(tipo='progetto', descrizione='X', data_inizio=d,
                              data_fine=d, stato='annullata')
        db.session.add(a); db.session.commit()
        aid = a.id
    c = app.test_client()
    r = c.post(f'/attivita/{aid}/riattiva')
    assert r.status_code == 302
    with app.app_context():
        assert db.session.get(AttivitaFuoriAula, aid).stato == 'attiva'
