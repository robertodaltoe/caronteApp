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

# Avvia Flask e aspetta - trap su SIGINT/SIGTERM per garantire il sync finale
trap '' INT
python3 app.py
EXIT_CODE=$?

# SYNC DB: carica su Drive dopo la chiusura (eseguito sempre, anche dopo CTRL+C)
echo ""
echo "Carico DB aggiornato su Drive..."
python3 sync_db.py carica
echo ""
echo "Arrivederci!"
exit $EXIT_CODE
