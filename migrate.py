"""
migrate.py — Gestione migrazioni database
Eseguire ogni volta che si aggiornano i modelli:
    python migrate.py

Aggiunge colonne mancanti senza toccare i dati esistenti.
Sicuro da eseguire più volte (idempotente).
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from models import db
from sqlalchemy import text, inspect

def col_exists(conn, table, column):
    """Controlla se una colonna esiste già nella tabella."""
    result = conn.execute(text(f"PRAGMA table_info({table})"))
    return any(row[1] == column for row in result)

def table_exists(conn, table):
    """Controlla se una tabella esiste."""
    result = conn.execute(text(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=:t"
    ), {'t': table})
    return result.fetchone() is not None

def add_column(conn, table, column, col_type, default=None):
    """Aggiunge una colonna se non esiste già."""
    if col_exists(conn, table, column):
        return False
    sql = f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"
    if default is not None:
        sql += f" DEFAULT {default}"
    conn.execute(text(sql))
    print(f"   ✓ {table}.{column} ({col_type})")
    return True

# ─────────────────────────────────────────────────────────────
# MIGRAZIONI — aggiungi qui ogni nuova colonna
# Formato: (tabella, colonna, tipo_sql, default_opzionale)
# ─────────────────────────────────────────────────────────────
MIGRATIONS = [
    # assenze
    ('assenze', 'note_interne',    'TEXT',          None),
    ('assenze', 'ora_inizio',      'INTEGER',       1),
    ('assenze', 'ora_fine',        'INTEGER',       9),

    # supplenze
    ('supplenze', 'note_display',  'VARCHAR(200)',  None),
    ('supplenze', 'modificato_il', 'DATETIME',      None),

    # banca_ore
    ('banca_ore', 'id_supplenza',  'INTEGER',       None),

    # docenti
    ('docenti', 'nome_display',    'VARCHAR(80)',   None),
    ('docenti', 'materia',         'VARCHAR(120)',  None),
    ('docenti', 'email',           'VARCHAR(120)',  None),
    ('docenti', 'note',            'TEXT',          None),

    # orario_docenti — creata da db.create_all se non esiste
    # scambi_ore — creata da db.create_all se non esiste
    # variazioni_orario — creata da db.create_all se non esiste
]

def run():
    app = create_app()
    with app.app_context():
        print("🔧  Migrazione database...")

        # Prima crea tutte le tabelle nuove (quelle che non esistono ancora)
        db.create_all()
        print("   ✓ Tabelle nuove create (se mancanti)")

        with db.engine.connect() as conn:
            aggiunte = 0
            saltate  = 0

            for migration in MIGRATIONS:
                table   = migration[0]
                column  = migration[1]
                coltype = migration[2]
                default = migration[3] if len(migration) > 3 else None

                if not table_exists(conn, table):
                    print(f"   ⚠ Tabella '{table}' non trovata — skip")
                    continue

                if add_column(conn, table, column, coltype, default):
                    aggiunte += 1
                else:
                    saltate += 1

            conn.commit()

        print(f"\n✅  Migrazione completata:")
        print(f"   Colonne aggiunte: {aggiunte}")
        print(f"   Già esistenti:    {saltate}")

        # Verifica finale — mostra struttura tabelle principali
        print("\n📋  Struttura tabelle:")
        with db.engine.connect() as conn:
            for table in ['assenze', 'supplenze', 'docenti', 'banca_ore',
                          'orario_docenti', 'scambi_ore']:
                if table_exists(conn, table):
                    result = conn.execute(text(f"PRAGMA table_info({table})"))
                    cols = [row[1] for row in result]
                    print(f"   {table}: {', '.join(cols)}")

if __name__ == '__main__':
    run()
