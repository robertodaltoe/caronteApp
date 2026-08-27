"""
Roberto: le riunioni pomeridiane (Consiglio di classe/scrutinio) si
programmano dalle Assegnazioni, che si stabilizzano molto prima
dell'orario reale — quando l'orario arriva, potrebbe smentire una
riunione già fissata (un docente coinvolto ha in realtà lezione in
quell'ora). Prima non c'era nessun controllo, né automatico né a
richiesta.

modules/verifica_orario_riunioni.py confronta AttivitaIst (orario
reale HH:MM) con OrarioDocente (numero d'ora 1-9, senza corrispondenza
a un orario reale in nessun'altra parte del codice) usando
MAPPA_ORE_POMERIDIANE, fornita da Roberto per la sua scuola.
"""
from datetime import date, timedelta
from models import db
from models.attivita_ist import AttivitaIst, AttivitaIstPartecipante
from models.orario_docente import OrarioDocente
from modules.verifica_orario_riunioni import trova_conflitti_orario_riunioni
from tests.conftest import crea_docente

MARTEDI = date(2026, 9, 15)
assert MARTEDI.weekday() == 1


def _crea_evento(data, ora_inizio, ora_fine, docenti, classe='1A CAT'):
    ev = AttivitaIst(tipo='consiglio_classe', titolo=f'CdC {classe}', classe=classe,
                      data=data, ora_inizio=ora_inizio, ora_fine=ora_fine, origine='manuale')
    db.session.add(ev)
    db.session.flush()
    for d in docenti:
        db.session.add(AttivitaIstPartecipante(id_attivita=ev.id, id_docente=d.id, preset=True))
    db.session.commit()
    return ev


def test_conflitto_rilevato_quando_docente_ha_lezione_reale_sovrapposta(app, db_session):
    doc = crea_docente('Rossi')
    _crea_evento(MARTEDI, '14:00', '15:00', [doc])
    # 7ª ora martedì = 13:25-14:25 (MAPPA_ORE_POMERIDIANE) — si
    # sovrappone a 14:00-15:00.
    db.session.add(OrarioDocente(id_docente=doc.id, giorno=1, ora=7,
                                  classe='2A LSC', materia='Matematica', tipo_ora='lezione'))
    db.session.commit()

    conflitti = trova_conflitti_orario_riunioni()
    assert len(conflitti) == 1
    assert conflitti[0]['docente'].id == doc.id
    assert conflitti[0]['classe_lezione'] == '2A LSC'
    assert conflitti[0]['ora_lezione'] == 7


def test_nessun_conflitto_se_gli_orari_non_si_sovrappongono(app, db_session):
    doc = crea_docente('Rossi')
    _crea_evento(MARTEDI, '14:30', '15:30', [doc])
    # 7ª ora finisce alle 14:25, prima che inizi la riunione (14:30).
    db.session.add(OrarioDocente(id_docente=doc.id, giorno=1, ora=7,
                                  classe='2A LSC', materia='Matematica', tipo_ora='lezione'))
    db.session.commit()

    assert trova_conflitti_orario_riunioni() == []


def test_nessun_conflitto_per_ora_buco_o_disposizione(app, db_session):
    doc = crea_docente('Rossi')
    _crea_evento(MARTEDI, '14:00', '15:00', [doc])
    db.session.add_all([
        OrarioDocente(id_docente=doc.id, giorno=1, ora=7, classe=None, tipo_ora='disposizione'),
        OrarioDocente(id_docente=doc.id, giorno=1, ora=8, classe='POTENZIAMENTO', tipo_ora='potenziamento'),
    ])
    db.session.commit()

    assert trova_conflitti_orario_riunioni() == []


def test_nessun_conflitto_per_docente_non_convocato(app, db_session):
    """Un docente con lezione reale sovrapposta ma NON tra i
    partecipanti della riunione non genera un conflitto — non è lui a
    doverci essere."""
    doc_convocato = crea_docente('Rossi')
    doc_altro = crea_docente('Bianchi')
    _crea_evento(MARTEDI, '14:00', '15:00', [doc_convocato])
    db.session.add(OrarioDocente(id_docente=doc_altro.id, giorno=1, ora=7,
                                  classe='2A LSC', materia='Matematica', tipo_ora='lezione'))
    db.session.commit()

    assert trova_conflitti_orario_riunioni() == []


def test_data_da_esclude_riunioni_passate(app, db_session):
    doc = crea_docente('Rossi')
    passato = MARTEDI - timedelta(weeks=52)  # stesso giorno della settimana, un anno fa
    while passato.weekday() != 1:
        passato -= timedelta(days=1)
    _crea_evento(passato, '14:00', '15:00', [doc])
    db.session.add(OrarioDocente(id_docente=doc.id, giorno=1, ora=7,
                                  classe='2A LSC', materia='Matematica', tipo_ora='lezione'))
    db.session.commit()

    assert trova_conflitti_orario_riunioni(data_da=date.today()) == []
    assert len(trova_conflitti_orario_riunioni()) == 1  # senza filtro, lo trova


def test_pagina_verifica_orario_mostra_i_conflitti_trovati(app, db_session, monkeypatch):
    import routes.generatore_cdc as mod
    if 'generatore_cdc' not in app.blueprints:
        app.register_blueprint(mod.generatore_cdc_bp)

    futuro = date.today() + timedelta(days=30)
    while futuro.weekday() != 1:
        futuro += timedelta(days=1)
    doc = crea_docente('Rossi')
    _crea_evento(futuro, '14:00', '15:00', [doc])
    db.session.add(OrarioDocente(id_docente=doc.id, giorno=1, ora=7,
                                  classe='2A LSC', materia='Matematica', tipo_ora='lezione'))
    db.session.commit()

    catturato = {}

    def _finto_render(template_name, **kwargs):
        catturato['kwargs'] = kwargs
        return '<html></html>'
    monkeypatch.setattr(mod, 'render_template', _finto_render)

    with app.test_client() as c:
        r = c.get('/generatore-cdc/verifica-orario')
        assert r.status_code == 200

    conflitti = catturato['kwargs']['conflitti']
    assert len(conflitti) == 1
    assert conflitti[0]['docente'].id == doc.id
    assert conflitti[0]['classe_lezione'] == '2A LSC'
