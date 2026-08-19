"""
Test di regressione: registrare un'assenza con il tab "Più giorni" o
"Periodico" del form (data di inizio futura, diversa da quella con cui
il form si era aperto) deve usare la data scelta in quel tab, non la
data del campo "Un giorno" residuo — vedi templates/assenza_form.html
(campi data_range_ini/data_per_ini disabilitati quando il tab non è
attivo, così il browser non li invia più insieme al campo 'data').

Qui si verifica lo stesso contratto lato server: registra_assenze_form
controlla 'data' prima di 'data_range_ini'/'data_per_ini' (vedi
modules/assenze_registrazione.py), quindi la correttezza dipende dal
fatto che 'data' non arrivi affatto quando si usa un altro tab — non
dal solo backend, che si fida di quello che il form invia.
"""
from datetime import date, timedelta
from flask import g

from models import db
from models.assenza import Assenza
from modules.assenze_registrazione import registra_assenze_form
from tests.conftest import crea_docente


def _crea_tabelle(app):
    with app.app_context():
        from models.attivita_ist import AttivitaIst, AttivitaIstPartecipante, AttivitaIstPresenza  # noqa
        from models.scambio_orario import ScambioOrario, ScambioSlot  # noqa
        db.create_all()


class _UtenteFinto:
    def __init__(self, ruolo, username='test'):
        self.ruolo = ruolo
        self.username = username


class _Form(dict):
    def getlist(self, k):
        v = self.get(k)
        return v if isinstance(v, list) else ([v] if v else [])


def test_registra_range_futuro_ignora_campo_data_assente(app, db_session):
    _crea_tabelle(app)
    with app.app_context():
        d = crea_docente('Bruni')
        futura = date(2027, 3, 16)  # martedì, fisso per non dipendere da quando gira il test
        form = _Form({
            'id_docente': str(d.id),
            'data_range_ini': futura.isoformat(),
            'data_range_fin': futura.isoformat(),
            'ora_inizio': '1', 'ora_fine': '2',
            'motivo': 'ferie', 'note': '',
        })
        with app.test_request_context():
            g.utente = _UtenteFinto('ds')
            risultato = registra_assenze_form(form)
        assert risultato['data_inizio'] == futura
        creata = Assenza.query.filter_by(id_docente=d.id).first()
        assert creata is not None
        assert creata.data == futura


def test_registra_periodico_futuro_ignora_campo_data_assente(app, db_session):
    _crea_tabelle(app)
    with app.app_context():
        d = crea_docente('Sarti')
        # Data fissa su un lunedì (2027-03-15): la generazione del periodo
        # esclude di proposito le domeniche, un giorno scelto a caso
        # potrebbe cadere di domenica e far slittare la prima riga creata.
        futuro_ini = date(2027, 3, 15)
        futuro_fin = futuro_ini + timedelta(days=6)
        form = _Form({
            'id_docente': str(d.id),
            'data_per_ini': futuro_ini.isoformat(),
            'data_per_fin': futuro_fin.isoformat(),
            'ora_inizio': '1', 'ora_fine': '2',
            'motivo': 'ferie', 'note': '',
        })
        with app.test_request_context():
            g.utente = _UtenteFinto('ds')
            risultato = registra_assenze_form(form)
        assert risultato['data_inizio'] == futuro_ini
        creata = Assenza.query.filter_by(id_docente=d.id).order_by(Assenza.data).first()
        assert creata is not None
        assert creata.data == futuro_ini
