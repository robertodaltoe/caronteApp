from datetime import date, timedelta

from models import db
from models.orario_docente import OrarioDocente
from models.posto_vacante import OrarioPlaceholder, AliasPostoVacante
from models.supplenza import Supplenza
from modules.posti_vacanti import (
    salva_slot_posti, collega_nome, ricalcola_supplenze_posti, nomina_posto,
    nomi_in_attesa)
from tests.conftest import crea_docente


def _slot(nome, giorno, ora, classe, tipo='lezione'):
    return {'cognome_file': nome, 'giorno': giorno, 'ora': ora,
            'classe': classe, 'materia': 'FISICA', 'tipo_ora': tipo}


def _giorno_feriale_futuro(giorni_avanti=3):
    d = date.today() + timedelta(days=giorni_avanti)
    while d.weekday() > 4:
        d += timedelta(days=1)
    return d


def _prepara(app):
    d = _giorno_feriale_futuro()
    salva_slot_posti([_slot('ITP FISICA', d.weekday(), 2, '1ACAT'),
                      _slot('ITP FISICA', d.weekday(), 3, '---'),
                      _slot('ITP FISICA', d.weekday(), 4, '1ACAT', 'compresenza')],
                     date.today(), date.today() + timedelta(days=14))
    db.session.commit()
    return d


def test_nome_non_collegato_resta_in_attesa_e_senza_supplenze(app, db_session):
    _prepara(app)
    assert [n for n, *_ in nomi_in_attesa()] == ['ITP FISICA']
    assert ricalcola_supplenze_posti() == {'create': 0, 'cancellate': 0}


def test_collegato_genera_supplenze_solo_da_oggi_e_reimport_non_duplica(app, db_session):
    d = _prepara(app)
    collega_nome('itp fisica', 'nuovo')
    esito = ricalcola_supplenze_posti()
    assert esito['create'] >= 1
    sup = Supplenza.query.all()
    assert all(s.id_assente is None and s.stato == 'scoperta' and s.data >= date.today()
               for s in sup)
    assert all(s.classe == '1ACAT' and s.ora == 2 for s in sup)  # solo la lezione vera
    assert d in {s.data for s in sup}
    n = len(sup)
    assert ricalcola_supplenze_posti() == {'create': 0, 'cancellate': 0}
    assert Supplenza.query.count() == n


def test_ignora_non_genera_nulla(app, db_session):
    _prepara(app)
    collega_nome('ITP FISICA', 'ignora')
    assert ricalcola_supplenze_posti()['create'] == 0
    assert nomi_in_attesa() == []


def test_nomina_porta_le_ore_e_cancella_le_supplenze_anche_assegnate(app, db_session):
    d = _prepara(app)
    collega_nome('ITP FISICA', 'nuovo')
    ricalcola_supplenze_posti()
    doc = crea_docente('Nuovo')
    sost = crea_docente('Sostituto')
    db.session.commit()
    s = Supplenza.query.first()
    s.id_sostituto, s.stato = sost.id, 'assegnata'
    db.session.commit()

    esito = nomina_posto('N:ITP FISICA', doc.id)

    assert esito['supplenze_cancellate'] >= 1
    assert Supplenza.query.count() == 0
    assert OrarioPlaceholder.query.count() == 0
    assert AliasPostoVacante.query.count() == 0
    ore = OrarioDocente.query.filter_by(id_docente=doc.id).all()
    assert {(r.giorno, r.ora) for r in ore} >= {(d.weekday(), 2)}
