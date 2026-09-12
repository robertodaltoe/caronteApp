"""
Test per modules/sostituzione_docente.py (Sessione 69 addendum 2):
sostituzione temporanea/definitiva di un docente titolare con un altro,
vedi la docstring del modulo per il disegno completo.
"""
from datetime import date

import pytest

from models import db
from models.orario_docente import OrarioDocente
from models.assegnazione import AssegnazioneDocente, AssegnazioneClasse
from models.assenza import Assenza
from models.supplenza import Supplenza
from models.movimento_banca_ore import MovimentoBancaOre
from models.attivita_ist import AttivitaIst, AttivitaIstPartecipante
from models.sostituzione_docente import SostituzioneDocente, SostituzioneOrarioSlot
from modules.sostituzione_docente import (
    avvia_sostituzione, termina_sostituzione, SostituzioneDocenteErrore,
)
from tests.conftest import crea_docente


def _crea_tabelle(app):
    with app.app_context():
        from models.attivita_ist import AttivitaIstPresenza  # noqa
        from models.scambio_orario import ScambioOrario, ScambioSlot  # noqa
        from models.classe_concorso import ClasseConcorso  # noqa
        db.create_all()


def _crea_cc(codice='A026'):
    from models.classe_concorso import ClasseConcorso
    cc = ClasseConcorso(codice=codice, nome='Matematica')
    db.session.add(cc)
    db.session.flush()
    return cc


def _crea_orario(id_docente, righe):
    """righe: lista di (giorno, ora, classe)."""
    for giorno, ora, classe in righe:
        db.session.add(OrarioDocente(
            id_docente=id_docente, giorno=giorno, ora=ora, classe=classe,
            materia='TEST', tipo_ora='lezione',
        ))
    db.session.commit()


def _crea_cattedra(id_docente, cc, anno_scol, classi_ore):
    """classi_ore: lista di (anno_corso, sezione, indirizzo, ore) -> AssegnazioneClasse."""
    asgn = AssegnazioneDocente(anno_scol=anno_scol, id_classe_concorso=cc.id,
                                id_docente=id_docente, tipo='titolare')
    db.session.add(asgn)
    db.session.flush()
    for anno_corso, sezione, indirizzo, ore in classi_ore:
        db.session.add(AssegnazioneClasse(
            id_assegnazione=asgn.id, indirizzo=indirizzo,
            anno_corso=anno_corso, sezione=sezione, ore=ore,
        ))
    db.session.commit()
    return asgn


def _anno_scol_oggi():
    from config_anno import get_anno_corrente
    return get_anno_corrente()


# ── Temporanea ────────────────────────────────────────────────────────

def test_temporanea_sposta_orario_genera_assenze_e_supplenze_preassegnate(app, db_session):
    _crea_tabelle(app)
    with app.app_context():
        titolare = crea_docente('Santagata')
        sostituto = crea_docente('Prova')
        lunedi = date(2026, 9, 14)  # giorno=0
        _crea_orario(titolare.id, [(0, 1, '5ARIM'), (0, 2, '5ARIM')])

        risultato = avvia_sostituzione(
            id_titolare=titolare.id, id_sostituto=sostituto.id, tipo='temporanea',
            data_inizio=lunedi, data_fine=lunedi, motivo='malattia',
            creato_da='test',
        )

        assert risultato['n_slot_orario'] == 2
        assert risultato['n_assenze'] == 1
        assert risultato['n_supplenze'] == 2

        # L'orario ora appartiene al sostituto, non più al titolare.
        assert OrarioDocente.query.filter_by(id_docente=titolare.id).count() == 0
        righe_sost = OrarioDocente.query.filter_by(id_docente=sostituto.id).all()
        assert {r.classe for r in righe_sost} == {'5ARIM'}

        # L'assenza del titolare è stata registrata.
        assert Assenza.query.filter_by(id_docente=titolare.id, data=lunedi).count() == 1

        # Le supplenze nascono già assegnate al sostituto, con credito banca ore.
        supplenze = Supplenza.query.filter_by(id_assente=titolare.id, data=lunedi).all()
        assert len(supplenze) == 2
        assert all(s.id_sostituto == sostituto.id and s.stato == 'assegnata' for s in supplenze)
        movimenti = MovimentoBancaOre.query.filter_by(id_docente=sostituto.id).all()
        assert len(movimenti) == 2
        assert all(m.minuti == 60 for m in movimenti)


def test_temporanea_senza_data_fine_solleva_errore(app, db_session):
    _crea_tabelle(app)
    with app.app_context():
        titolare = crea_docente('Santagata')
        sostituto = crea_docente('Prova')
        _crea_orario(titolare.id, [(0, 1, '5ARIM')])
        with pytest.raises(SostituzioneDocenteErrore):
            avvia_sostituzione(id_titolare=titolare.id, id_sostituto=sostituto.id,
                                tipo='temporanea', data_inizio=date(2026, 9, 14))


def test_titolare_senza_orario_solleva_errore(app, db_session):
    _crea_tabelle(app)
    with app.app_context():
        titolare = crea_docente('Santagata')
        sostituto = crea_docente('Prova')
        with pytest.raises(SostituzioneDocenteErrore):
            avvia_sostituzione(id_titolare=titolare.id, id_sostituto=sostituto.id,
                                tipo='temporanea', data_inizio=date(2026, 9, 14),
                                data_fine=date(2026, 9, 14))


def test_titolare_uguale_sostituto_solleva_errore(app, db_session):
    _crea_tabelle(app)
    with app.app_context():
        titolare = crea_docente('Santagata')
        with pytest.raises(SostituzioneDocenteErrore):
            avvia_sostituzione(id_titolare=titolare.id, id_sostituto=titolare.id,
                                tipo='definitiva', data_inizio=date(2026, 9, 14))


def test_termina_sostituzione_ripristina_orario_e_partecipanti(app, db_session):
    _crea_tabelle(app)
    with app.app_context():
        titolare = crea_docente('Santagata')
        sostituto = crea_docente('Prova')
        cc = _crea_cc()
        _crea_cattedra(titolare.id, cc, _anno_scol_oggi(), [(5, 'A', 'RIM', 6)])
        _crea_orario(titolare.id, [(0, 1, '5ARIM')])

        nella_finestra = date(2026, 9, 16)  # dentro il periodo 14-18/9 della sostituzione
        ev = AttivitaIst(tipo='consiglio_classe', titolo='CdC 5A RIM',
                          data=nella_finestra, classe='5A RIM')
        db.session.add(ev)
        db.session.flush()
        db.session.add(AttivitaIstPartecipante(id_attivita=ev.id, id_docente=titolare.id))
        db.session.commit()
        id_evento = ev.id

        risultato = avvia_sostituzione(
            id_titolare=titolare.id, id_sostituto=sostituto.id, tipo='temporanea',
            data_inizio=date(2026, 9, 14), data_fine=date(2026, 9, 18),
        )
        id_sost = risultato['sostituzione'].id
        assert risultato['n_eventi_ist'] == 1

        partecipanti = {p.id_docente for p in AttivitaIstPartecipante.query.filter_by(id_attivita=id_evento).all()}
        assert partecipanti == {sostituto.id}

        esito = termina_sostituzione(id_sost, creato_da='test')
        assert esito['n_orario_ripristinato'] == 1

        assert OrarioDocente.query.filter_by(id_docente=titolare.id).count() == 1
        assert OrarioDocente.query.filter_by(id_docente=sostituto.id).count() == 0

        partecipanti_dopo = {p.id_docente for p in AttivitaIstPartecipante.query.filter_by(id_attivita=id_evento).all()}
        assert partecipanti_dopo == {titolare.id}

        sost_row = SostituzioneDocente.query.get(id_sost)
        assert sost_row.stato == 'conclusa'


def test_termina_su_definitiva_solleva_errore(app, db_session):
    _crea_tabelle(app)
    with app.app_context():
        titolare = crea_docente('Santagata')
        sostituto = crea_docente('Prova')
        _crea_orario(titolare.id, [(0, 1, '5ARIM')])
        risultato = avvia_sostituzione(id_titolare=titolare.id, id_sostituto=sostituto.id,
                                        tipo='definitiva', data_inizio=date(2026, 9, 14))
        with pytest.raises(SostituzioneDocenteErrore):
            termina_sostituzione(risultato['sostituzione'].id)


def test_termina_due_volte_solleva_errore(app, db_session):
    _crea_tabelle(app)
    with app.app_context():
        titolare = crea_docente('Santagata')
        sostituto = crea_docente('Prova')
        _crea_orario(titolare.id, [(0, 1, '5ARIM')])
        risultato = avvia_sostituzione(id_titolare=titolare.id, id_sostituto=sostituto.id,
                                        tipo='temporanea', data_inizio=date(2026, 9, 14),
                                        data_fine=date(2026, 9, 14))
        id_sost = risultato['sostituzione'].id
        termina_sostituzione(id_sost)
        with pytest.raises(SostituzioneDocenteErrore):
            termina_sostituzione(id_sost)


# ── Definitiva ────────────────────────────────────────────────────────

def test_definitiva_sposta_orario_e_cattedra_senza_registrare_assenze(app, db_session):
    _crea_tabelle(app)
    with app.app_context():
        titolare = crea_docente('Margarita')
        sostituto = crea_docente('Prova')
        cc = _crea_cc()
        anno = _anno_scol_oggi()
        asgn = _crea_cattedra(titolare.id, cc, anno, [(5, 'A', 'RIM', 6)])
        _crea_orario(titolare.id, [(0, 1, '5ARIM'), (0, 2, '5ARIM')])

        risultato = avvia_sostituzione(
            id_titolare=titolare.id, id_sostituto=sostituto.id, tipo='definitiva',
            data_inizio=date(2026, 9, 14),
        )

        assert risultato['n_assenze'] == 0
        assert risultato['n_supplenze'] == 0
        assert risultato['n_cattedre_trasferite'] == 1
        assert Assenza.query.filter_by(id_docente=titolare.id).count() == 0

        # Orario spostato per sempre, nessuna riga di tracciamento (non reversibile).
        assert OrarioDocente.query.filter_by(id_docente=titolare.id).count() == 0
        assert OrarioDocente.query.filter_by(id_docente=sostituto.id).count() == 2
        assert SostituzioneOrarioSlot.query.count() == 2  # tracciate comunque, per audit

        # La cattedra ora appartiene al sostituto.
        asgn_dopo = AssegnazioneDocente.query.get(asgn.id)
        assert asgn_dopo.id_docente == sostituto.id


def test_definitiva_iscrive_sostituto_a_eventi_futuri_della_classe(app, db_session):
    _crea_tabelle(app)
    with app.app_context():
        titolare = crea_docente('Margarita')
        sostituto = crea_docente('Prova')
        cc = _crea_cc()
        anno = _anno_scol_oggi()
        _crea_cattedra(titolare.id, cc, anno, [(5, 'A', 'RIM', 6)])
        _crea_orario(titolare.id, [(0, 1, '5ARIM')])

        futuro = date(2026, 12, 14)
        ev = AttivitaIst(tipo='scrutinio', titolo='Scrutinio 5A RIM',
                          data=futuro, classe='5A RIM')
        db.session.add(ev)
        db.session.commit()
        id_evento = ev.id

        avvia_sostituzione(id_titolare=titolare.id, id_sostituto=sostituto.id,
                            tipo='definitiva', data_inizio=date(2026, 9, 14))

        partecipanti = {p.id_docente for p in AttivitaIstPartecipante.query.filter_by(id_attivita=id_evento).all()}
        assert sostituto.id in partecipanti
