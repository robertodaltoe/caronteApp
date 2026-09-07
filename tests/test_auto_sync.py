"""
Test per modules/auto_sync.py (_merge_additivo): il sync automatico
additivo multi-postazione. Nessuno dei test tocca Google Drive né
database.db reale — il "remoto" è un file SQLite temporaneo con lo
stesso schema, costruito da models.db.metadata.

Copre i 5 bug distinti già corretti a mano in collaudo reale (vedi
CLAUDE.md, Task 46, e DEVLOG Sessione 66 addendum 54), per evitare che
si ripresentino silenziosamente in futuro:
1. la chiave logica non deve includere il campo di contenuto ('motivo')
   — due varianti della stessa riga vanno in conflitto, non sommate;
2. le lapidi (tombstone) impediscono che un'eliminazione locale venga
   "resuscitata" da una riga ancora presente sul remoto;
3. la pubblicazione deve scattare anche quando le novità sono SOLO
   locali (nessuna riga arrivata dal remoto) — qui verificato tramite
   il contatore 'solo_locali' che pilota quella decisione in
   esegui_sync_automatico();
4. la risoluzione "tieni locale" di un conflitto non deve ricreare lo
   stesso conflitto al giro successivo (altrimenti ciclo infinito);
5. un vero conflitto (stessa chiave, contenuto diverso) finisce in
   SyncConflitto, mai risolto in automatico.

In più: una riga remota la cui FK non esiste in locale viene saltata,
non inserita con una FK rotta.
"""
import sqlite3
from datetime import date, datetime

import pytest
from sqlalchemy import create_engine

from models import db
from models.assenza import Assenza
from models.supplenza import Supplenza
from models.sync_conflitto import SyncConflitto
from models.sync_tombstone import SyncTombstone
from modules.auto_sync import _merge_additivo, registra_eliminazione

from tests.conftest import crea_docente


@pytest.fixture
def remoto_path(tmp_path):
    """Crea un file SQLite temporaneo con lo stesso schema del locale
    (stesse tabelle di models.db.metadata), inizialmente vuoto."""
    path = tmp_path / 'remoto.db'
    engine = create_engine(f'sqlite:///{path}')
    db.metadata.create_all(engine)
    engine.dispose()
    return str(path)


def _inserisci_remoto(path, tabella, righe):
    """Inserisce righe (liste di dict) nel file remoto via SQL grezzo,
    così come farebbe il DB scaricato da un'altra postazione."""
    conn = sqlite3.connect(path)
    try:
        for riga in righe:
            colonne = list(riga.keys())
            placeholders = ', '.join('?' for _ in colonne)
            conn.execute(
                f"INSERT INTO {tabella} ({', '.join(colonne)}) VALUES ({placeholders})",
                [riga[c] for c in colonne])
        conn.commit()
    finally:
        conn.close()


def test_riga_nuova_dal_remoto_viene_inserita(app, db_session, remoto_path):
    """Comportamento base: una riga che esiste solo sul remoto va
    importata in locale (merge 'additivo')."""
    doc = crea_docente('Rossi')
    db.session.commit()

    _inserisci_remoto(remoto_path, 'assenze', [{
        'id_docente': doc.id, 'data': '2026-10-10', 'ora_inizio': 1, 'ora_fine': 2,
        'motivo': 'malattia', 'creato_il': datetime.utcnow().isoformat(),
    }])

    risultato = _merge_additivo(db, remoto_path)

    assert risultato['inserite'] == 1
    assert risultato['conflitti_nuovi'] == 0
    assenze = Assenza.query.filter_by(id_docente=doc.id).all()
    assert len(assenze) == 1
    assert assenze[0].motivo == 'malattia'


def test_stesso_docente_stessa_fascia_motivo_diverso_va_in_conflitto_non_sommato(app, db_session, remoto_path):
    """Il 'motivo' non fa parte della chiave logica: la stessa assenza
    con un motivo diverso sulle due macchine è UN conflitto, non due
    righe distinte."""
    doc = crea_docente('Bianchi')
    db.session.add(Assenza(id_docente=doc.id, data=date(2026, 10, 10),
                            ora_inizio=1, ora_fine=2, motivo='lutto'))
    db.session.commit()

    _inserisci_remoto(remoto_path, 'assenze', [{
        'id_docente': doc.id, 'data': '2026-10-10', 'ora_inizio': 1, 'ora_fine': 2,
        'motivo': 'malattia', 'creato_il': datetime.utcnow().isoformat(),
    }])

    risultato = _merge_additivo(db, remoto_path)

    assert risultato['inserite'] == 0
    assert risultato['conflitti_nuovi'] == 1
    assert Assenza.query.filter_by(id_docente=doc.id).count() == 1  # non sommata
    conflitto = SyncConflitto.query.filter_by(tabella='assenze').first()
    assert conflitto is not None
    assert 'motivo' in conflitto.campi_diversi


def test_lapide_locale_impedisce_di_reintrodurre_la_riga_dal_remoto(app, db_session, remoto_path):
    """Una riga eliminata in locale (con lapide registrata) non deve
    ricomparire solo perché il remoto la ha ancora — il bug più
    importante trovato in collaudo (Task 46)."""
    doc = crea_docente('Verdi')
    a = Assenza(id_docente=doc.id, data=date(2026, 10, 12), ora_inizio=3, ora_fine=4,
                motivo='malattia')
    db.session.add(a)
    db.session.commit()
    creato_il_originale = a.creato_il.isoformat()  # PRIMA della lapide

    riga_dict = {'id_docente': doc.id, 'data': a.data.isoformat(), 'ora_inizio': a.ora_inizio,
                 'ora_fine': a.ora_fine}
    registra_eliminazione('assenze', riga_dict)
    db.session.delete(a)
    db.session.commit()

    assert Assenza.query.filter_by(id_docente=doc.id).count() == 0

    # Il remoto (un'altra postazione che non ha ancora ricevuto
    # l'eliminazione) ha ancora la riga, con il suo creato_il ORIGINALE
    # (precedente alla lapide) — non un dato nuovo creato dopo la
    # cancellazione, che invece dovrebbe superare la lapide (vedi test
    # dedicato più sotto).
    _inserisci_remoto(remoto_path, 'assenze', [{
        'id_docente': doc.id, 'data': '2026-10-12', 'ora_inizio': 3, 'ora_fine': 4,
        'motivo': 'malattia', 'creato_il': creato_il_originale,
    }])

    risultato = _merge_additivo(db, remoto_path)

    assert risultato['inserite'] == 0
    assert Assenza.query.filter_by(id_docente=doc.id).count() == 0


def test_riga_remota_piu_recente_della_lapide_supera_la_lapide(app, db_session, remoto_path):
    """Se sul remoto compare una riga con la STESSA chiave di una lapide
    ma creata DOPO l'eliminazione (es. l'utente ha rifatto apposta
    l'inserimento su un'altra postazione dopo aver cancellato qui), la
    lapide è superata e la riga va importata — non ignorata per sempre
    (bug reale corretto in DEVLOG Sessione 66 addendum 54: una nomina
    appena salvata spariva di nuovo per colpa di una lapide vecchia)."""
    doc = crea_docente('Superata')
    db.session.commit()

    registra_eliminazione('assenze', {
        'id_docente': doc.id, 'data': '2026-10-18', 'ora_inizio': 1, 'ora_fine': 2,
    })
    db.session.commit()
    lapide = SyncTombstone.query.filter_by(tabella='assenze').first()
    lapide.eliminato_il = datetime(2020, 1, 1)  # nel passato, senza ambiguità di orologio
    db.session.commit()

    # Riga remota con la stessa chiave, ma creata DOPO la lapide.
    _inserisci_remoto(remoto_path, 'assenze', [{
        'id_docente': doc.id, 'data': '2026-10-18', 'ora_inizio': 1, 'ora_fine': 2,
        'motivo': 'malattia', 'creato_il': datetime.utcnow().isoformat(),
    }])

    risultato = _merge_additivo(db, remoto_path)

    assert risultato['inserite'] == 1
    assert Assenza.query.filter_by(id_docente=doc.id).count() == 1


def test_lapide_remota_elimina_la_riga_ancora_presente_in_locale(app, db_session, remoto_path):
    """Speculare al test precedente: una lapide arrivata dall'altra
    macchina deve eliminare la riga se è ancora presente qui."""
    doc = crea_docente('Neri')
    a = Assenza(id_docente=doc.id, data=date(2026, 10, 13), ora_inizio=1, ora_fine=2,
                motivo='permesso_personale')
    db.session.add(a)
    db.session.commit()

    chiave_json = ('{"data": "2026-10-13", "id_docente": %d, '
                   '"ora_fine": 2, "ora_inizio": 1}' % doc.id)
    _inserisci_remoto(remoto_path, 'sync_tombstones', [{
        'tabella': 'assenze', 'chiave_logica': chiave_json,
        'eliminato_il': datetime.utcnow().isoformat(), 'eliminato_da': 'altra_postazione',
    }])

    risultato = _merge_additivo(db, remoto_path)

    assert risultato['eliminate'] == 1
    assert Assenza.query.filter_by(id_docente=doc.id).count() == 0
    assert SyncTombstone.query.filter_by(tabella='assenze').count() == 1


def test_solo_locali_segnala_che_serve_ripubblicare_anche_senza_novita_dal_remoto(app, db_session, remoto_path):
    """Se l'unica novità è una riga presente SOLO in locale (creata qui,
    non ancora vista dall'altra postazione), 'solo_locali' deve
    comunque risultare positivo: è il segnale che pilota la
    ripubblicazione su Drive in esegui_sync_automatico() — senza,
    nessuna delle due macchine vedrebbe mai i dati dell'altra finché
    qualcuno non riavvia."""
    doc = crea_docente('Gialli')
    db.session.add(Assenza(id_docente=doc.id, data=date(2026, 10, 14),
                            ora_inizio=1, ora_fine=2, motivo='malattia'))
    db.session.commit()

    risultato = _merge_additivo(db, remoto_path)  # remoto vuoto

    assert risultato['inserite'] == 0
    assert risultato['solo_locali'] >= 1


def test_risoluzione_tieni_locale_non_ricrea_lo_stesso_conflitto(app, db_session, remoto_path):
    """Un conflitto già risolto con 'tieni versione locale' non deve
    ripresentarsi identico al giro successivo — altrimenti ciclo
    infinito (bug riprodotto e corretto in collaudo)."""
    doc = crea_docente('Rosa')
    db.session.add(Supplenza(data=date(2026, 10, 15), ora=3, classe='2A',
                              id_assente=doc.id, id_sostituto=None,
                              tipo='recupero', stato='scoperta', origine='manuale'))
    db.session.commit()

    riga_remota = {
        'data': '2026-10-15', 'ora': 3, 'classe': '2A', 'id_assente': doc.id,
        'id_sostituto': doc.id, 'tipo': 'recupero', 'stato': 'coperta',
        'origine': 'manuale', 'note_display': None, 'note': None,
        'creato_il': datetime.utcnow().isoformat(),
        'modificato_il': datetime.utcnow().isoformat(),
    }
    _inserisci_remoto(remoto_path, 'supplenze', [dict(riga_remota)])

    # Primo giro: nasce il conflitto (stato diverso: scoperta vs coperta).
    r1 = _merge_additivo(db, remoto_path)
    assert r1['conflitti_nuovi'] == 1

    conflitto = SyncConflitto.query.filter_by(tabella='supplenze').first()
    conflitto.risolto = True
    conflitto.scelta = 'locale'
    conflitto.risolto_il = datetime.utcnow()
    db.session.commit()

    # Secondo giro: STESSA proposta remota, identica a quella già rifiutata —
    # non deve ricreare un nuovo conflitto.
    r2 = _merge_additivo(db, remoto_path)
    assert r2['conflitti_nuovi'] == 0
    assert SyncConflitto.query.filter_by(tabella='supplenze').count() == 1


def test_conflitto_genuinamente_nuovo_dopo_una_risoluzione_locale_viene_comunque_segnalato(app, db_session, remoto_path):
    """Se invece il valore remoto cambia rispetto a quello già
    rifiutato, è un conflitto NUOVO e va segnalato di nuovo — la
    soppressione vale solo per la proposta identica già vista."""
    doc = crea_docente('Blu')
    db.session.add(Supplenza(data=date(2026, 10, 16), ora=2, classe='3B',
                              id_assente=doc.id, tipo='recupero', stato='scoperta',
                              origine='manuale'))
    db.session.commit()

    base = {'data': '2026-10-16', 'ora': 2, 'classe': '3B', 'id_assente': doc.id,
            'id_sostituto': None, 'tipo': 'recupero', 'origine': 'manuale',
            'note_display': None, 'note': None,
            'creato_il': datetime.utcnow().isoformat(),
            'modificato_il': datetime.utcnow().isoformat()}

    _inserisci_remoto(remoto_path, 'supplenze', [dict(base, stato='coperta')])
    r1 = _merge_additivo(db, remoto_path)
    assert r1['conflitti_nuovi'] == 1

    conflitto = SyncConflitto.query.filter_by(tabella='supplenze').first()
    conflitto.risolto = True
    conflitto.scelta = 'locale'
    conflitto.risolto_il = datetime.utcnow()
    db.session.commit()

    # Un valore remoto DIVERSO da quello rifiutato in precedenza.
    import os
    os.remove(remoto_path)
    engine = create_engine(f'sqlite:///{remoto_path}')
    db.metadata.create_all(engine)
    engine.dispose()
    _inserisci_remoto(remoto_path, 'supplenze', [dict(base, stato='annullata')])

    r2 = _merge_additivo(db, remoto_path)
    assert r2['conflitti_nuovi'] == 1
    assert SyncConflitto.query.filter_by(tabella='supplenze', risolto=False).count() == 1


def test_riga_remota_con_fk_mancante_viene_saltata_non_inserita(app, db_session, remoto_path):
    """Una riga remota che referenzia un docente non ancora presente in
    locale (es. arrivato con id diverso sulle due macchine) va saltata
    per questo giro, non inserita con una FK rotta."""
    _inserisci_remoto(remoto_path, 'assenze', [{
        'id_docente': 999999, 'data': '2026-10-17', 'ora_inizio': 1, 'ora_fine': 2,
        'motivo': 'malattia', 'creato_il': datetime.utcnow().isoformat(),
    }])

    risultato = _merge_additivo(db, remoto_path)

    assert risultato['inserite'] == 0
    assert Assenza.query.count() == 0
