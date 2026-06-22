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

# SYNC DB: scarica da Drive prima di avviare
echo ""
echo "Sincronizzazione DB con Google Drive..."
python3 sync_db.py scarica
echo ""

echo "Avvio CaronteApp su http://localhost:5002"
echo "Per fermare: CTRL+C"
echo ""

SYNC_FATTO=0
sync_finale() {
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
        echo "Carico DB aggiornato su Drive..."
        python3 sync_db.py carica
        echo ""
        echo "Arrivederci!"
    fi
}
# Intercetta CTRL+C (INT) e chiusura terminale (TERM): esegue il sync e poi esce
trap 'sync_finale; exit 0' INT TERM

# Avvia Flask in un nuovo process group (set -m attiva il job control anche
# in script non interattivi) cosi' il reloader e il suo processo figlio
# possono essere chiusi insieme con un solo segnale al gruppo.
set -m
python3 app.py &
FLASK_PID=$!
wait $FLASK_PID
EXIT_CODE=$?

sync_finale
exit $EXIT_CODE
