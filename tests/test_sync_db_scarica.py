"""
Bug reale trovato da Roberto (Sessione 66): 'python3 sync_db.py scarica'
sul Mac mini stampava "DB pronto - lock attivato" ma il contenuto
locale restava quello vecchio. Causa: scarica() decideva se sostituire
il file locale confrontando le DATE DI MODIFICA (_ts(db_drive) >
_ts(db)) invece del contenuto — il file locale viene però toccato
continuamente dal sync automatico additivo (modules/auto_sync.py fa
commit ogni 30s), quindi la sua data di modifica avanza anche senza
novità rilevanti, finendo per superare quella del file appena
pubblicato su Drive. Risultato: 'scarica' saltava silenziosamente la
sostituzione pur dichiarando successo.

Questi test verificano scarica()/carica() direttamente, isolati dal
vero database.db e dalla vera cartella Drive (CARONTE_DRIVE_PATH
punta a una cartella temporanea).
"""
import os
import time
import pytest
import sync_db


@pytest.fixture
def drive_finto(tmp_path, monkeypatch):
    cartella = tmp_path / "drive"
    cartella.mkdir()
    monkeypatch.setenv("CARONTE_DRIVE_PATH", str(cartella))
    return cartella


def test_scarica_aggiorna_anche_se_il_locale_ha_data_piu_recente(tmp_path, drive_finto):
    """Riproduce esattamente il bug: contenuto locale vecchio ma con
    mtime PIU' RECENTE del file appena pubblicato su Drive (simula il
    file locale "toccato" dal sync automatico dopo l'ultimo download)."""
    db_locale = tmp_path / "database.db"
    db_locale.write_bytes(b"contenuto VECCHIO")

    # Pubblica il contenuto NUOVO da un'altra macchina.
    db_altra_macchina = tmp_path / "database_altra_macchina.db"
    db_altra_macchina.write_bytes(b"contenuto NUOVO")
    assert sync_db.carica(str(db_altra_macchina)) is True

    # Il file locale ha una data di modifica più recente di quella del
    # file appena caricato su Drive (mtime avanzato da attività locale
    # successiva, es. il sync automatico) — il vecchio bug lo avrebbe
    # fatto risultare "già aggiornato" e non lo avrebbe toccato.
    ora = time.time()
    os.utime(db_locale, (ora + 60, ora + 60))

    # Nessun lock attivo (carica lo rimuove) -> nessun prompt interattivo.
    esito = sync_db.scarica(str(db_locale))

    assert esito is True
    assert db_locale.read_bytes() == b"contenuto NUOVO"


def test_scarica_non_tocca_il_file_se_il_contenuto_e_identico(tmp_path, drive_finto):
    db_locale = tmp_path / "database.db"
    db_locale.write_bytes(b"stesso contenuto")

    db_altra_macchina = tmp_path / "database_altra_macchina.db"
    db_altra_macchina.write_bytes(b"stesso contenuto")
    assert sync_db.carica(str(db_altra_macchina)) is True

    prima = db_locale.stat().st_mtime
    time.sleep(0.05)
    esito = sync_db.scarica(str(db_locale))

    assert esito is True
    assert db_locale.read_bytes() == b"stesso contenuto"
    # Non riscritto: nessun file .bak creato per un download che non ha
    # cambiato nulla.
    assert not (tmp_path / "database.db.bak").exists()


def test_scarica_con_forza_sostituisce_anche_se_identico(tmp_path, drive_finto):
    db_locale = tmp_path / "database.db"
    db_locale.write_bytes(b"contenuto A")

    db_altra_macchina = tmp_path / "database_altra_macchina.db"
    db_altra_macchina.write_bytes(b"contenuto A")
    assert sync_db.carica(str(db_altra_macchina)) is True

    esito = sync_db.scarica(str(db_locale), forzato=True)
    assert esito is True
    assert db_locale.read_bytes() == b"contenuto A"
