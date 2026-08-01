"""
Test della migrazione automatica che corregge il vincolo UNIQUE della
tabella 'aule' da UNIQUE(classe) a UNIQUE(anno_scol, classe).

Simula lo schema storico reale (quello effettivamente presente nel
database di produzione prima della correzione) su un file SQLite
temporaneo, poi verifica che _migra_vincolo_aule():
 - preservi tutti i dati esistenti senza perdite o duplicati,
 - applichi il nuovo vincolo corretto,
 - sia idempotente (rieseguita non fa nulla e non rompe nulla).
"""
import os
import sqlite3
import pytest
from flask import Flask
from models import db


def _crea_db_schema_vecchio(path):
    """Crea un file SQLite con lo schema storico: UNIQUE(classe) da sola,
    con qualche riga di dati di esempio (come nel database reale)."""
    con = sqlite3.connect(path)
    con.execute("""
        CREATE TABLE aule (
            id INTEGER NOT NULL,
            classe VARCHAR(20) NOT NULL,
            aula VARCHAR(50) NOT NULL,
            sede VARCHAR(60) NOT NULL, anno_scol VARCHAR(9),
            PRIMARY KEY (id),
            UNIQUE (classe)
        )
    """)
    con.executemany(
        "INSERT INTO aule (id, anno_scol, classe, aula, sede) VALUES (?,?,?,?,?)",
        [
            (1, '2025-2026', '1A AFM', '10', 'Sede Centrale - Piano Terra'),
            (2, '2025-2026', '2B CAT', '20', 'Sede Centrale - 1° Piano'),
            (3, '2026-2027', '3A LSU', 'Aula Magna', 'Sede Centrale - Piano Terra'),
        ]
    )
    con.commit()
    con.close()


@pytest.fixture
def db_path(tmp_path):
    path = str(tmp_path / 'test_migrazione.db')
    _crea_db_schema_vecchio(path)
    return path


def _app_su_db(path):
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + path
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)
    return app


def test_migrazione_preserva_dati_e_corregge_vincolo(db_path):
    from app import _migra_vincolo_aule

    # Righe presenti PRIMA della migrazione (lette con sqlite3 puro,
    # indipendente da SQLAlchemy, per un confronto affidabile).
    con = sqlite3.connect(db_path)
    righe_prima = con.execute(
        'SELECT id, anno_scol, classe, aula, sede FROM aule ORDER BY id').fetchall()
    con.close()
    assert len(righe_prima) == 3

    app = _app_su_db(db_path)
    with app.app_context():
        _migra_vincolo_aule()

    con = sqlite3.connect(db_path)
    sql_tabella = con.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='aule'"
    ).fetchone()[0]
    righe_dopo = con.execute(
        'SELECT id, anno_scol, classe, aula, sede FROM aule ORDER BY id').fetchall()
    con.close()

    assert 'UNIQUE (anno_scol, classe)' in sql_tabella
    assert righe_dopo == righe_prima


def test_migrazione_e_idempotente(db_path):
    from app import _migra_vincolo_aule

    app = _app_su_db(db_path)
    with app.app_context():
        _migra_vincolo_aule()
        # Seconda esecuzione: non deve sollevare errori né alterare i dati.
        _migra_vincolo_aule()

    con = sqlite3.connect(db_path)
    n_righe = con.execute('SELECT COUNT(*) FROM aule').fetchone()[0]
    con.close()
    assert n_righe == 3


def test_dopo_migrazione_stessa_classe_anni_diversi_e_permessa(db_path):
    """Verifica end-to-end: dopo la migrazione, il nuovo vincolo permette
    davvero quello che prima era bloccato."""
    from app import _migra_vincolo_aule
    from models.aula import Aula

    app = _app_su_db(db_path)
    with app.app_context():
        _migra_vincolo_aule()
        # '1A AFM' esiste già per il 2025-2026 (vedi fixture): aggiungere
        # la stessa classe per un anno diverso ora deve funzionare.
        db.session.add(Aula(anno_scol='2026-2027', classe='1A AFM',
                             aula='30', sede='Sede Staccata'))
        db.session.commit()

        righe = Aula.query.filter_by(classe='1A AFM').order_by(Aula.anno_scol).all()
        assert len(righe) == 2
