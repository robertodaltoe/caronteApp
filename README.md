# CaronteApp

Gestione supplenze, banca ore e recuperi — IIS Leonardo da Vinci Chiavenna.
Applicazione Flask/SQLite. Porta 5002.

## Primo avvio su nuova macchina

    python3 setup.py

Installa dipendenze Python e guida le librerie di sistema per WeasyPrint.

## Avvio quotidiano

- macOS / Linux:  ./avvia_caronte.sh
- Windows:        avvia_caronte.bat

Poi apri: http://localhost:5002

## WeasyPrint — librerie di sistema

- macOS:          brew install pango cairo gdk-pixbuf libffi
- Ubuntu/Debian:  sudo apt install libpango-1.0-0 libcairo2 libgdk-pixbuf2.0-0
- Windows:        GTK3 Runtime installer (vedi setup.py per il link)

## Database

database.db NON e incluso nel repo — va copiato manualmente sulla nuova macchina.

## Funzionalita macOS-only

- Invio bozze email via Mail.app: solo macOS.
  Su Windows/Linux restituisce avviso, le bozze .eml sono scaricabili.