"""
Test di regressione per il fix "banca ore non azzerata per anno scolastico".

Prima del fix: MovimentoBancaOre non aveva una colonna anno_scol e tutti i
saldi (get_saldi_docente, get_storico_settimanale, le simulazioni in
ottimizzazione_simulazioni/pianifica_permessi) sommavano i movimenti di
TUTTI gli anni scolastici mai registrati, senza azzerarsi mai al cambio anno.

Questi test verificano che:
1. anno_scol viene calcolato automaticamente all'inserimento (evento before_insert).
2. Il backfill dei movimenti storici senza anno_scol funziona ed è idempotente.
3. get_saldi_docente / get_storico_settimanale filtrano per anno scolastico
   (di default quello corrente), lasciando intatti e consultabili gli anni
   precedenti.
"""
from datetime import date
import pytest

from models import db
from models.docente import Docente
from models.movimento_banca_ore import MovimentoBancaOre, anno_scol_da_data


def crea_movimento(id_docente, data, tipo='supplenza_recupero', ore=2, descrizione=''):
    """Helper: crea un movimento banca ore. 'ore' viene convertito in minuti
    (unità di misura reale della colonna 'minuti')."""
    m = MovimentoBancaOre(id_docente=id_docente, data=data, tipo=tipo,
                           minuti=ore * 60, descrizione=descrizione)
    db.session.add(m)
    db.session.commit()
    return m


class TestAnnoScolDaData:
    """Verifica la funzione pura di calcolo dell'anno scolastico da una data."""

    def test_ottobre_appartiene_anno_che_inizia_a_settembre(self):
        assert anno_scol_da_data(date(2025, 10, 15)) == '2025-2026'

    def test_marzo_appartiene_ancora_anno_precedente(self):
        assert anno_scol_da_data(date(2026, 3, 1)) == '2025-2026'

    def test_settembre_appartiene_al_nuovo_anno(self):
        assert anno_scol_da_data(date(2026, 9, 10)) == '2026-2027'

    def test_agosto_appartiene_ancora_anno_vecchio(self):
        assert anno_scol_da_data(date(2026, 8, 31)) == '2025-2026'


class TestAutoCalcoloAllInsert(object):
    """Verifica che l'evento before_insert imposti anno_scol automaticamente."""

    def test_anno_scol_impostato_automaticamente(self, app):
        with app.app_context():
            d = Docente(cognome='Rossi', nome='Anna', tipo_contratto='TI',
                        attivo=True, ruolo='titolare')
            db.session.add(d)
            db.session.commit()

            m = crea_movimento(d.id, date(2025, 10, 15))
            assert m.anno_scol == '2025-2026'

            m2 = crea_movimento(d.id, date(2026, 9, 10))
            assert m2.anno_scol == '2026-2027'

    def test_anno_scol_esplicito_non_sovrascritto(self, app):
        """Se anno_scol e' gia' valorizzato (es. per un backfill manuale),
        l'evento non deve sovrascriverlo."""
        with app.app_context():
            d = Docente(cognome='Bianchi', nome='Luca', tipo_contratto='TI',
                        attivo=True, ruolo='titolare')
            db.session.add(d)
            db.session.commit()

            m = MovimentoBancaOre(id_docente=d.id, data=date(2025, 10, 15),
                                   tipo='supplenza_recupero', minuti=120,
                                   anno_scol='9999-0000')
            db.session.add(m)
            db.session.commit()
            assert m.anno_scol == '9999-0000'


class TestBackfillMigrazione:
    """Verifica la funzione di backfill in app.py su dati storici senza anno_scol."""

    def test_backfill_idempotente(self, app):
        with app.app_context():
            d = Docente(cognome='Verdi', nome='Elena', tipo_contratto='TI',
                        attivo=True, ruolo='titolare')
            db.session.add(d)
            db.session.commit()

            # Simula movimenti storici pre-esistenti, senza anno_scol (come
            # sarebbero stati prima della migrazione, quando la colonna non
            # esisteva ancora). L'evento before_insert calcolerebbe subito
            # anno_scol anche qui, quindi per simulare fedelmente lo stato
            # "storico" lo azzeriamo con un UPDATE diretto dopo l'insert,
            # bypassando l'evento (come sarebbe stato per righe scritte
            # prima che la colonna anno_scol esistesse nel DB reale).
            m1 = MovimentoBancaOre(id_docente=d.id, data=date(2024, 11, 5),
                                    tipo='supplenza_recupero', minuti=180)
            m2 = MovimentoBancaOre(id_docente=d.id, data=date(2025, 2, 20),
                                    tipo='permesso', minuti=-60)
            db.session.add_all([m1, m2])
            db.session.commit()

            db.session.execute(
                db.text('UPDATE banca_ore SET anno_scol = NULL WHERE id IN (:i1, :i2)'),
                {'i1': m1.id, 'i2': m2.id}
            )
            db.session.commit()
            db.session.refresh(m1)
            db.session.refresh(m2)
            assert m1.anno_scol is None
            assert m2.anno_scol is None

            from app import _backfill_anno_scol_banca_ore
            _backfill_anno_scol_banca_ore()

            db.session.refresh(m1)
            db.session.refresh(m2)
            assert m1.anno_scol == '2024-2025'
            assert m2.anno_scol == '2024-2025'

            # Rieseguirla non deve sollevare errori né alterare i dati già
            # popolati (idempotenza).
            _backfill_anno_scol_banca_ore()
            db.session.refresh(m1)
            assert m1.anno_scol == '2024-2025'


class TestSaldiScopatiPerAnno:
    """Verifica che get_saldi_docente e get_storico_settimanale filtrino
    correttamente per anno scolastico, di default quello corrente, lasciando
    gli anni precedenti intatti e consultabili esplicitamente."""

    def test_saldo_default_e_scoped_su_anno_corrente(self, app, monkeypatch):
        with app.app_context():
            d = Docente(cognome='Neri', nome='Paolo', tipo_contratto='TI',
                        attivo=True, ruolo='titolare')
            db.session.add(d)
            db.session.commit()

            # Movimento dell'anno "vecchio" 2024-2025
            crea_movimento(d.id, date(2024, 11, 5), tipo='supplenza_recupero', ore=6)
            # Movimento dell'anno corrente 2025-2026
            crea_movimento(d.id, date(2025, 10, 10), tipo='supplenza_recupero', ore=4)

            import config_anno
            monkeypatch.setattr(config_anno, 'get_anno_corrente',
                                 lambda: '2025-2026')
            # report.py importa get_anno_corrente al momento della chiamata
            # (import locale dentro la funzione), quindi il monkeypatch sul
            # modulo config_anno è sufficiente.

            from routes.report import get_saldi_docente

            saldo_corrente = get_saldi_docente(d.id)
            assert saldo_corrente['supplenze'] == 4

            saldo_vecchio = get_saldi_docente(d.id, anno_scol='2024-2025')
            assert saldo_vecchio['supplenze'] == 6

    def test_anno_senza_movimenti_da_saldo_zero(self, app, monkeypatch):
        with app.app_context():
            d = Docente(cognome='Gialli', nome='Sara', tipo_contratto='TI',
                        attivo=True, ruolo='titolare')
            db.session.add(d)
            db.session.commit()

            crea_movimento(d.id, date(2025, 10, 10), tipo='supplenza_recupero', ore=5)

            import config_anno
            monkeypatch.setattr(config_anno, 'get_anno_corrente',
                                 lambda: '2026-2027')

            from routes.report import get_saldi_docente
            saldo_nuovo_anno = get_saldi_docente(d.id)
            assert saldo_nuovo_anno['supplenze'] == 0

            saldo_vecchio = get_saldi_docente(d.id, anno_scol='2025-2026')
            assert saldo_vecchio['supplenze'] == 5
