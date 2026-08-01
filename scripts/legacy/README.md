# Script storici — una tantum

Questi script sono stati usati **una sola volta** durante l'avvio del
progetto (import iniziale di orari, banca ore, classi di concorso e
piano di studi da file Excel). Non fanno parte del funzionamento normale
dell'app: nessuna route o comando li richiama automaticamente.

**Non rilanciarli senza aver capito bene cosa fanno.** Molti creano
righe nel database ogni volta che vengono eseguiti (non hanno controlli
di idempotenza come `_auto_migrate()` in `app.py`), quindi rilanciarli
su un database già popolato può creare doppioni. Alcuni contengono
anche date scritte a mano (es. `fix_date_storico.py`,
`import_banca_ore.py`) legate a un momento storico preciso, non più
valide oggi.

**Attenzione particolare** — `scripts_seed_piano_studi.py` e
`scripts_collega_piano_materie.py` eseguono la scrittura sul database
**appena il file viene importato** (non hanno un blocco
`if __name__ == '__main__':` a protezione): anche solo un `import` di
questi moduli da un altro script o da un tool di analisi del codice fa
partire subito le scritture. Vanno eseguiti solo direttamente da riga
di comando, mai importati da altro codice.

## File

- `import_orario.py` — import iniziale dell'orario docenti da Excel.
- `import_banca_ore.py` — import iniziale banca ore + creazione docenti
  da `data/Banca_Ore_Docenti_v3.xlsm`.
- `fix_date_storico.py` — correzione una tantum delle date approssimate
  dei movimenti importati.
- `scripts_seed_classi_concorso.py` — seed classi di concorso da organico
  di diritto USR Sondrio 2026/27.
- `scripts_seed_piano_studi.py` — seed piano di studi 2026/27 da
  "Monteore OD.xlsx".
- `scripts_collega_piano_materie.py` — collegamento piano studi ↔
  tabella Materia.
- `migrate.py` — vecchio script di migrazione manuale del database
  (colonne mancanti). Caso diverso dagli altri: non è "una tantum" ma
  **superato**, non "storico" — tutte le sue migrazioni sono un
  sottoinsieme di quelle applicate automaticamente ad ogni avvio da
  `_auto_migrate()` in `app.py` (che ne contiene molte di più e resta
  l'unica fonte da tenere aggiornata). Non serve più lanciarlo: tenuto
  qui solo come riferimento storico.

Se in futuro serve reimportare dati da zero su una macchina nuova,
questi script vanno letti riga per riga prima di rilanciarli — non sono
pensati per un uso ripetuto.
