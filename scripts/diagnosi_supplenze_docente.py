"""Diagnosi in SOLA LETTURA: perché un docente non ha supplenze generate in una data.

Uso (su una COPIA del db, mai sul reale):
    cp database.db /tmp/diag.db
    python scripts/diagnosi_supplenze_docente.py /tmp/diag.db Grassi 2026-10-30
"""
import sqlite3
import sys
from datetime import date

db_path, cognome, data_s = sys.argv[1:4]
data = date.fromisoformat(data_s)
giorno = data.weekday()
con = sqlite3.connect(f'file:{db_path}?mode=ro', uri=True)
con.row_factory = sqlite3.Row
q = lambda sql, *a: con.execute(sql, a).fetchall()

docs = q("SELECT id, cognome, nome, attivo, ora_uscita_json FROM docenti WHERE cognome LIKE ?", f'%{cognome}%')
print(f'Docenti con cognome ~ {cognome!r}:')
for d in docs:
    print('  ', dict(d))
for d in docs:
    i = d['id']
    print(f"\n=== {d['cognome']} {d['nome']} (id {i}) — {data} (giorno {giorno}) ===")
    print('Sospensioni:', [tuple(r) for r in q(
        "SELECT descrizione, data_inizio, data_fine FROM sospensioni_didattiche WHERE data_inizio<=? AND data_fine>=?", data_s, data_s)] or 'nessuna')
    print('Validità orario:', [tuple(r) for r in q(
        "SELECT DISTINCT data_inizio_validita, data_fine_validita FROM orario_docenti")])
    slots = q("SELECT ora, classe, materia, tipo_ora FROM orario_docenti WHERE id_docente=? AND giorno=? ORDER BY ora", i, giorno)
    print('Orario del giorno:')
    for s in slots:
        comp = q("""SELECT id_docente, tipo_ora FROM orario_docenti WHERE giorno=? AND ora=? AND classe=?
                    AND id_docente<>? AND tipo_ora IN ('lezione','compresenza')""", giorno, s['ora'], s['classe'], i)
        sost = q("SELECT id_docente FROM orario_sostegno WHERE giorno=? AND ora=? AND classe=?", giorno, s['ora'], s['classe'])
        print(f"  ora {s['ora']} {s['classe']} [{s['tipo_ora']}] compagni: {[tuple(c) for c in comp]} sostegno: {[tuple(c) for c in sost]}")
    print('Indisponibilità:', [dict(r) for r in q("SELECT ora, motivo, genera_supplenza FROM indisponibilita WHERE id_docente=? AND data=?", i, data_s)])
    print('Assenze:', [dict(r) for r in q("SELECT ora_inizio, ora_fine, motivo FROM assenze WHERE id_docente=? AND data=?", i, data_s)])
    print('Supplenze a suo nome:', [dict(r) for r in q("SELECT ora, classe, stato, origine FROM supplenze WHERE id_assente=? AND data=?", i, data_s)])
print('\nAttività fuori aula attive nel giorno:')
for r in q("SELECT id, tipo, descrizione, ora_inizio, ora_fine, ricorrenza FROM attivita_fuori_aula WHERE data_inizio<=? AND data_fine>=? AND stato='attiva'", data_s, data_s):
    cl = [c[0] for c in q("SELECT classe FROM attivita_classi WHERE id_attivita=?", r['id'])]
    print('  ', dict(r), 'classi:', cl)
