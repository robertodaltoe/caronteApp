#!/bin/bash
# Avvia CaronteApp su porta 5002 — macOS / Linux

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [[ "$OSTYPE" == "darwin"* ]]; then
    export DYLD_LIBRARY_PATH="/opt/homebrew/lib:${DYLD_LIBRARY_PATH:-}"
fi

if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
else
    echo "Venv non trovato. Esegui prima: python3 setup.py"
    exit 1
fi

# SYNC DB: scarica da Drive prima di avviare.
# Se lo script esce con codice 1 (errore di decifratura: chiave locale
# non corrispondente a quella usata su Drive), ci si ferma qui: avviare
# comunque userebbe un DB locale superato e, allo spegnimento, lo
# ricaricherebbe su Drive sovrascrivendo la cronologia buona con dati
# vecchi/sbagliati.
echo ""
echo "Sincronizzazione DB con Google Drive..."
python3 sync_db.py scarica
SYNC_SCARICA_ESITO=$?
echo ""
if [ "$SYNC_SCARICA_ESITO" -ne 0 ]; then
    echo "Sincronizzazione fallita — avvio interrotto (vedi errore sopra)."
    echo "L'app NON viene avviata per evitare di sovrascrivere il DB su Drive con dati vecchi."
    exit 1
fi

echo "Avvio CaronteApp su http://localhost:5002"
echo "Per fermare: CTRL+C"
echo ""

SYNC_FATTO=0
sync_finale() {
    local salta_upload="${1:-0}"
    if [ "$SYNC_FATTO" -eq 0 ]; then
        SYNC_FATTO=1
        # Termina TUTTO il process group di Flask (watcher del reloader +
        # processo figlio che serve davvero le richieste). Il segnale a
        # -$FLASK_PID (con il meno) va a tutto il gruppo, non solo al padre.
        if [ -n "$FLASK_PID" ] && kill -0 "$FLASK_PID" 2>/dev/null; then
            kill -TERM "-$FLASK_PID" 2>/dev/null || kill -TERM "$FLASK_PID" 2>/dev/null
            sleep 1
            # Pulizia extra: se il reloader ha lasciato un figlio orfano
            # ancora in ascolto sulla porta, lo termina esplicitamente.
            PORTA_PID=$(lsof -ti tcp:5002 2>/dev/null)
            if [ -n "$PORTA_PID" ]; then
                kill -TERM $PORTA_PID 2>/dev/null
            fi
            wait "$FLASK_PID" 2>/dev/null
        fi
        echo ""
        if [ "$salta_upload" -eq 1 ]; then
            echo "L'app si è chiusa con un errore: NON ricarico il DB su Drive"
            echo "(potrebbe riflettere uno stato a metà di una migrazione fallita)."
            echo "Correggi il problema indicato sopra e rilancia — i dati locali restano quelli"
            echo "scaricati a inizio sessione, nessuna modifica viene pubblicata su Drive."
        else
            echo "Carico DB aggiornato su Drive..."
            python3 sync_db.py carica
        fi
        echo ""
        echo "Arrivederci!"
    fi
}
# Intercetta CTRL+C (INT) e chiusura terminale (TERM): esegue il sync e poi esce
trap 'sync_finale 0; exit 0' INT TERM

# Avvia Flask in un nuovo process group (set -m attiva il job control anche
# in script non interattivi) cosi' il reloader e il suo processo figlio
# possono essere chiusi insieme con un solo segnale al gruppo.
set -m
python3 app.py &
FLASK_PID=$!
wait $FLASK_PID
EXIT_CODE=$?

# Se Flask è terminato da solo con un errore (es. crash a un'eccezione non
# gestita in fase di avvio/migrazione) invece che per CTRL+C/chiusura
# terminale, non ricarichiamo automaticamente il DB su Drive: potrebbe
# riflettere una migrazione andata a metà, come accaduto il 3/8/2026.
if [ "$EXIT_CODE" -ne 0 ]; then
    sync_finale 1
else
    sync_finale 0
fi
exit $EXIT_CODE
