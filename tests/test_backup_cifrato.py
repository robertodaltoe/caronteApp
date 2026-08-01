"""
Test del modulo di backup cifrato: verifica che cifratura/decifratura
funzionino correttamente (roundtrip) e che la pulizia dei vecchi backup
mantenga solo gli ultimi N, senza toccare file di altro tipo.

Usa sempre file temporanei (tmp_path) — non tocca mai la chiave o i
backup reali dell'applicazione in data/backup/.
"""
import os
import time
import pytest
import modules.backup_cifrato as bc


@pytest.fixture
def backup_dirs(tmp_path, monkeypatch):
    """Reindirizza KEY_FILE/SALT_FILE del modulo verso una cartella
    temporanea, cosi' il test non genera né legge mai la chiave reale
    dell'applicazione."""
    key_file = tmp_path / '.backup_key'
    salt_file = tmp_path / '.backup_salt'
    monkeypatch.setattr(bc, 'KEY_FILE', str(key_file))
    monkeypatch.setattr(bc, 'SALT_FILE', str(salt_file))
    return tmp_path


def test_backup_roundtrip_cifra_e_decifra(backup_dirs, tmp_path):
    db_originale = tmp_path / 'database.db'
    contenuto = b'contenuto finto di un database sqlite \x00\x01\x02 con byte binari'
    db_originale.write_bytes(contenuto)

    backup_dir = tmp_path / 'backup'
    dest = bc.crea_backup_cifrato(str(db_originale), str(backup_dir))

    assert os.path.exists(dest)
    assert dest.endswith('.db.enc')
    # Il file cifrato non deve contenere il contenuto originale in chiaro.
    cifrato = open(dest, 'rb').read()
    assert contenuto not in cifrato

    ripristinato = tmp_path / 'ripristinato.db'
    bc.decifra_backup(dest, str(ripristinato))
    assert ripristinato.read_bytes() == contenuto


def test_chiave_e_riutilizzata_tra_backup_diversi(backup_dirs, tmp_path):
    """La chiave deve essere generata una sola volta e riutilizzata,
    altrimenti i vecchi backup non sarebbero più decifrabili."""
    db_originale = tmp_path / 'database.db'
    db_originale.write_bytes(b'versione 1')
    backup_dir = tmp_path / 'backup'

    dest1 = bc.crea_backup_cifrato(str(db_originale), str(backup_dir), suffisso='_a')
    key_dopo_primo_backup = open(bc.KEY_FILE, 'rb').read()

    db_originale.write_bytes(b'versione 2')
    dest2 = bc.crea_backup_cifrato(str(db_originale), str(backup_dir), suffisso='_b')
    key_dopo_secondo_backup = open(bc.KEY_FILE, 'rb').read()

    assert key_dopo_primo_backup == key_dopo_secondo_backup

    # Entrambi i backup restano decifrabili con la stessa chiave.
    out1 = tmp_path / 'out1.db'
    out2 = tmp_path / 'out2.db'
    bc.decifra_backup(dest1, str(out1))
    bc.decifra_backup(dest2, str(out2))
    assert out1.read_bytes() == b'versione 1'
    assert out2.read_bytes() == b'versione 2'


def test_pulisci_vecchi_backup_mantiene_solo_gli_ultimi_n(tmp_path):
    backup_dir = tmp_path / 'backup'
    backup_dir.mkdir()

    # Crea 10 finti backup con nomi ordinabili cronologicamente.
    nomi = [f'database_2026060{i}_1200.db.enc' for i in range(10)]
    for nome in nomi:
        (backup_dir / nome).write_bytes(b'x')

    # File che NON deve essere toccato dalla pulizia (non è un backup).
    altro_file = backup_dir / 'launchd_out.log'
    altro_file.write_text('log non correlato')

    bc.pulisci_vecchi_backup(str(backup_dir), max_backup=5)

    rimasti = sorted(f for f in os.listdir(backup_dir) if f.startswith('database_'))
    assert len(rimasti) == 5
    # Devono restare i 5 più recenti (ordine alfabetico == cronologico
    # per via del formato timestamp nel nome).
    assert rimasti == sorted(nomi)[-5:]
    assert altro_file.exists()  # file non correlato mai toccato
