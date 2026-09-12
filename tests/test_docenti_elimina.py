"""
Test di regressione per l'eliminazione definitiva di un docente (Sessione 69):
Roberto ha segnalato pagina di errore eliminando un docente con una cattedra
assegnata (Margarita Raoul, inserito per errore in anagrafica).

Causa: routes/docenti.py::elimina() cancellava solo ColloquiEccezione e
OrarioDocente prima di eliminare il Docente, ma non toccava
AssegnazioneDocente. SQLAlchemy mette a NULL id_docente su quella riga
prima del delete, violando il vincolo ck_assegnazione_docente_o_placeholder
(un'assegnazione deve avere sempre o un docente reale o un placeholder).

Fix: prima di eliminare il docente, ogni sua AssegnazioneDocente viene
trasformata in un placeholder (nome_placeholder = nome del docente,
id_docente = None) invece di essere cancellata — Roberto: "ho bisogno che
resti il placeholder sul quale lo avevo assegnato ma che in anagrafica non
compaia più". Le supplenze in cui compariva come sostituto restano (sono
storico), ma il riferimento id_sostituto viene scollegato. Elenchi/preset
senza senso senza l'anagrafica (materie, classe di concorso, partecipazioni
a riunioni istituzionali) vengono invece cancellati.
"""
from datetime import date
from flask import g

from models import db
from models.assegnazione import AssegnazioneDocente
from models.classe_concorso import ClasseConcorso
from models.supplenza import Supplenza
from models.attivita_ist import AttivitaIstPartecipante
from tests.conftest import crea_docente


def _crea_tabelle(app):
    with app.app_context():
        from models.attivita_ist import AttivitaIst, AttivitaIstPresenza  # noqa
        from models.scambio_orario import ScambioOrario, ScambioSlot  # noqa
        db.create_all()
    if 'docenti' not in app.blueprints:
        from routes.docenti import docenti_bp
        app.register_blueprint(docenti_bp)


class _UtenteFinto:
    def __init__(self, ruolo='ds', username='test'):
        self.ruolo = ruolo
        self.username = username


def _crea_cc(codice='A026'):
    cc = ClasseConcorso(codice=codice, nome='Matematica')
    db.session.add(cc)
    db.session.flush()
    return cc


def test_elimina_docente_con_cattedra_diventa_placeholder(app, db_session):
    _crea_tabelle(app)
    with app.app_context():
        d = crea_docente('Margarita', nome='Raoul')
        cc = _crea_cc()
        asg = AssegnazioneDocente(anno_scol='2026-2027', id_classe_concorso=cc.id,
                                   id_docente=d.id, tipo='supplente')
        db.session.add(asg)
        db.session.commit()
        id_docente, id_asg = d.id, asg.id

        from routes.docenti import elimina
        with app.test_request_context(f'/docenti/{id_docente}/elimina',
                                       method='POST', data={'forza': '1'}):
            g.utente = _UtenteFinto()
            elimina(id_docente)

        from models.docente import Docente
        assert Docente.query.get(id_docente) is None

        asg_dopo = AssegnazioneDocente.query.get(id_asg)
        assert asg_dopo is not None, "la cattedra non deve essere cancellata"
        assert asg_dopo.id_docente is None
        assert asg_dopo.nome_placeholder == 'Margarita Raoul'


def test_elimina_docente_scollega_supplenze_come_sostituto_senza_cancellarle(app, db_session):
    _crea_tabelle(app)
    with app.app_context():
        d = crea_docente('Bruni')
        s = Supplenza(data=date(2026, 9, 14), ora=1, classe='5ARIM',
                       id_assente=999, id_sostituto=d.id, stato='annullata')
        db.session.add(s)
        db.session.commit()
        id_docente, id_sup = d.id, s.id

        from routes.docenti import elimina
        with app.test_request_context(f'/docenti/{id_docente}/elimina',
                                       method='POST', data={'forza': '1'}):
            g.utente = _UtenteFinto()
            elimina(id_docente)

        sup_dopo = Supplenza.query.get(id_sup)
        assert sup_dopo is not None, "la supplenza (storico) non va cancellata"
        assert sup_dopo.id_sostituto is None


def test_elimina_docente_rimuove_partecipazioni_a_riunioni_ist(app, db_session):
    _crea_tabelle(app)
    with app.app_context():
        from models.attivita_ist import AttivitaIst
        d = crea_docente('Novelli')
        ev = AttivitaIst(tipo='dipartimento', titolo='Riunione dip.',
                          data=date(2026, 9, 25))
        db.session.add(ev)
        db.session.flush()
        db.session.add(AttivitaIstPartecipante(id_attivita=ev.id, id_docente=d.id))
        db.session.commit()
        id_docente = d.id

        from routes.docenti import elimina
        with app.test_request_context(f'/docenti/{id_docente}/elimina',
                                       method='POST', data={'forza': '1'}):
            g.utente = _UtenteFinto()
            elimina(id_docente)

        assert AttivitaIstPartecipante.query.filter_by(id_docente=id_docente).count() == 0


def test_elimina_docente_senza_dati_collegati_non_richiede_conferma(app, db_session):
    """Un docente senza cattedra/banca ore/assenze/supplenze si elimina subito,
    senza dover passare forza=1 (comportamento preesistente, non toccato dal fix)."""
    _crea_tabelle(app)
    with app.app_context():
        d = crea_docente('Colombo')
        id_docente = d.id

        from routes.docenti import elimina
        with app.test_request_context(f'/docenti/{id_docente}/elimina', method='POST'):
            g.utente = _UtenteFinto()
            elimina(id_docente)

        from models.docente import Docente
        assert Docente.query.get(id_docente) is None
