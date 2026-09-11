"""
Test di regressione per il bug segnalato da Roberto (Sessione 68/69): un'assenza
registrata PRIMA di un import orario non genera mai la supplenza per una
lezione comparsa solo nel nuovo orario, perché _genera_supplenze() incrocia
Assenza con OrarioDocente una sola volta, al momento della registrazione
(modules/assenze_registrazione.py::registra_assenze_form). Un import
successivo di un nuovo orario (routes/sincronizzazione.py) sovrascrive
OrarioDocente ma non ricalcola le supplenze già "perse".

rigenera_supplenze_mancanti() va richiamata dopo ogni import orario per
colmare il buco, riusando _genera_supplenze() (già idempotente: salta gli
slot che hanno già una supplenza).
"""
from datetime import date

from models import db
from models.assenza import Assenza
from models.orario_docente import OrarioDocente
from models.supplenza import Supplenza
from modules.assenze_registrazione import rigenera_supplenze_mancanti
from tests.conftest import crea_docente


def _crea_tabelle(app):
    with app.app_context():
        from models.attivita_ist import AttivitaIst, AttivitaIstPartecipante, AttivitaIstPresenza  # noqa
        from models.scambio_orario import ScambioOrario, ScambioSlot  # noqa
        db.create_all()


def test_genera_supplenza_per_assenza_precedente_al_nuovo_orario(app, db_session):
    """Riproduce esattamente il caso Santagata: assenza registrata quando
    OrarioDocente non aveva ancora la lezione, orario importato dopo."""
    _crea_tabelle(app)
    with app.app_context():
        d = crea_docente('Santagata')
        lunedi = date(2026, 9, 14)  # confermato lunedì (giorno=0)

        # L'assenza esiste già, ma il "vecchio" orario non aveva nulla per
        # questo docente quel giorno: nessuna riga OrarioDocente ancora.
        a = Assenza(
            id_docente=d.id, data=lunedi, ora_inizio=1, ora_fine=9,
            motivo='permesso_personale',
        )
        db.session.add(a)
        db.session.commit()

        assert Supplenza.query.filter_by(id_assente=d.id, data=lunedi).count() == 0

        # Arriva il nuovo orario (come farebbe applica_importazione()):
        # ora il docente risulta in 5ARIM alle prime due ore del lunedì.
        db.session.add(OrarioDocente(
            id_docente=d.id, giorno=0, ora=1, classe='5ARIM',
            materia='DIR ECO-REL INT', tipo_ora='lezione',
        ))
        db.session.add(OrarioDocente(
            id_docente=d.id, giorno=0, ora=2, classe='5ARIM',
            materia='DIR ECO-REL INT', tipo_ora='lezione',
        ))
        db.session.commit()

        creati = rigenera_supplenze_mancanti(data_da=date(2026, 9, 1))
        assert creati == 2

        supplenze = Supplenza.query.filter_by(id_assente=d.id, data=lunedi).order_by(Supplenza.ora).all()
        assert [s.ora for s in supplenze] == [1, 2]
        assert all(s.classe == '5ARIM' for s in supplenze)
        assert all(s.stato == 'scoperta' for s in supplenze)


def test_rigenera_e_idempotente_non_duplica_supplenze_gia_esistenti(app, db_session):
    _crea_tabelle(app)
    with app.app_context():
        d = crea_docente('Bruni')
        lunedi = date(2026, 9, 14)

        db.session.add(Assenza(
            id_docente=d.id, data=lunedi, ora_inizio=1, ora_fine=2,
            motivo='malattia',
        ))
        db.session.add(OrarioDocente(
            id_docente=d.id, giorno=0, ora=1, classe='3ALLI',
            materia='ITALIANO', tipo_ora='lezione',
        ))
        db.session.commit()

        primo_giro = rigenera_supplenze_mancanti(data_da=date(2026, 9, 1))
        assert primo_giro == 1

        secondo_giro = rigenera_supplenze_mancanti(data_da=date(2026, 9, 1))
        assert secondo_giro == 0
        assert Supplenza.query.filter_by(id_assente=d.id, data=lunedi).count() == 1


def test_ignora_assenze_con_motivo_che_non_genera_supplenza(app, db_session):
    _crea_tabelle(app)
    with app.app_context():
        d = crea_docente('Vedovato')
        lunedi = date(2026, 9, 14)

        db.session.add(Assenza(
            id_docente=d.id, data=lunedi, ora_inizio=1, ora_fine=9,
            motivo='ferie',  # cat_genera_supplenza('ferie') è False
        ))
        db.session.add(OrarioDocente(
            id_docente=d.id, giorno=0, ora=1, classe='2ACAT',
            materia='STORIA', tipo_ora='lezione',
        ))
        db.session.commit()

        creati = rigenera_supplenze_mancanti(data_da=date(2026, 9, 1))
        assert creati == 0
        assert Supplenza.query.filter_by(id_assente=d.id, data=lunedi).count() == 0


def test_ignora_assenze_precedenti_a_data_da(app, db_session):
    _crea_tabelle(app)
    with app.app_context():
        d = crea_docente('Colombo')

        db.session.add(Assenza(
            id_docente=d.id, data=date(2026, 9, 7), ora_inizio=1, ora_fine=9,
            motivo='malattia',
        ))
        db.session.add(OrarioDocente(
            id_docente=d.id, giorno=0, ora=1, classe='1AAFM',
            materia='MATEMATICA', tipo_ora='lezione',
        ))
        db.session.commit()

        creati = rigenera_supplenze_mancanti(data_da=date(2026, 9, 14))
        assert creati == 0
