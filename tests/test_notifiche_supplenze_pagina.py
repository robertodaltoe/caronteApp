"""Render reale (copia del DB in /tmp) della pagina Notifiche supplenze e
del suo invio simulato, passando da CSRF e permessi veri."""
import re
from datetime import date, timedelta

from test_docente_nuovo_render import app_reale  # noqa: F401  (fixture)


def test_pagina_e_invio_simulato(app_reale, monkeypatch):
    from models import db
    from models.docente import Docente
    from models.supplenza import Supplenza
    from models.email_uscita import EmailUscita

    monkeypatch.setenv('CARONTE_EMAIL_MODE', 'simulato')
    g = date.today() + timedelta(days=2)
    with app_reale.app_context():
        s = Docente(cognome='ProvaSost', nome='T', email='prova.sost@davincichiavenna.edu.it', attivo=True)
        a = Docente(cognome='ProvaAss', nome='T', attivo=True)
        db.session.add_all([s, a]); db.session.flush()
        db.session.add(Supplenza(data=g, ora=2, classe='1Z', id_assente=a.id,
                                 id_sostituto=s.id, stato='assegnata'))
        db.session.commit()
        id_s = s.id

    with app_reale.test_client() as c:
        r = c.get(f'/mail-bozze/notifiche-supplenze?data={g.isoformat()}')
        assert r.status_code == 200
        corpo = r.get_data(as_text=True)
        assert 'ProvaSost' in corpo and 'classe 1Z' in corpo and 'simulato' in corpo
        tok = re.search(r'name="csrf_token" value="([^"]+)"', corpo).group(1)
        r = c.post('/mail-bozze/notifiche-supplenze/invia',
                   data={'csrf_token': tok, 'data': g.isoformat(), 'docenti': [id_s]})
        assert r.status_code == 200 and 'simulata' in r.get_data(as_text=True)

    with app_reale.app_context():
        e = EmailUscita.query.filter_by(id_docente=id_s).one()
        assert e.stato == 'simulata'
        db.session.delete(e); db.session.commit()
