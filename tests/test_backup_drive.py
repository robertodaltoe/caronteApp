"""Copia dei backup cifrati su Drive: best effort, con retention, spenta nei test."""
import os

import pytest

from modules import backup_drive as bd


@pytest.fixture
def drive(tmp_path, monkeypatch):
    base = tmp_path / 'Drive'
    base.mkdir()
    monkeypatch.setenv('CARONTE_DRIVE_PATH', str(base))
    monkeypatch.delenv('PYTEST_CURRENT_TEST', raising=False)
    monkeypatch.setattr(bd, 'attivo', lambda: True)
    return base / 'CaronteApp' / 'Backup'


def _backup(tmp_path, nome='database_20261031_1200.db.enc'):
    p = tmp_path / nome
    p.write_bytes(b'cifrato')
    return str(p)


def test_copia_il_backup_nella_cartella_drive(drive, tmp_path):
    dest = bd.copia_su_drive(_backup(tmp_path))
    assert dest and os.path.basename(dest) == 'database_20261031_1200.db.enc'
    assert (drive / 'database_20261031_1200.db.enc').read_bytes() == b'cifrato'


def test_senza_drive_non_solleva_e_non_copia(tmp_path, monkeypatch):
    monkeypatch.setattr(bd, 'attivo', lambda: True)
    monkeypatch.setattr(bd, 'cartella_backup_drive', lambda: None)
    assert bd.copia_su_drive(_backup(tmp_path)) is None


def test_errore_di_copia_non_solleva(drive, tmp_path):
    assert bd.copia_su_drive(str(tmp_path / 'inesistente.db.enc')) is None


def test_spenta_di_default_nei_test(tmp_path):
    assert bd.copia_su_drive(_backup(tmp_path)) is None


def test_retention_ultimi_e_uno_al_mese():
    nomi = [f'database_202608{g:02d}_1000.db.enc' for g in range(1, 21)]      # agosto
    nomi += [f'database_202609{g:02d}_1000.db.enc' for g in range(1, 21)]     # settembre
    nomi += ['database_20261001_1000_pre_import.db.enc', 'altro.db.enc']
    tenere = bd.da_conservare(nomi, ultimi=3)
    assert 'database_20260820_1000.db.enc' in tenere       # ultimo di agosto
    assert 'database_20260920_1000.db.enc' in tenere       # ultimo di settembre
    assert 'database_20260815_1000.db.enc' not in tenere
    assert 'altro.db.enc' in tenere                        # nome non standard: intatto
    assert 'database_20261001_1000_pre_import.db.enc' in tenere


def test_pulisci_rimuove_solo_i_vecchi(drive, tmp_path):
    drive.mkdir(parents=True)
    for g in range(1, 21):
        (drive / f'database_20260801_{g:02d}00.db.enc').write_bytes(b'x')
    rimossi = bd.pulisci(str(drive), ultimi=2)
    # tiene gli ultimi 2 e il più recente del mese (già tra gli ultimi 2)
    assert len(os.listdir(drive)) == 2 and len(rimossi) == 18
