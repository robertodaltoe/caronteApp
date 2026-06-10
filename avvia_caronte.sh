#!/bin/bash
# Avvia CaronteApp su porta 5002
# Funziona su macOS e Linux (percorso relativo alla directory dello script)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# WeasyPrint su macOS: aggiungi librerie Homebrew
if [[ "$OSTYPE" == "darwin"* ]]; then
    export DYLD_LIBRARY_PATH="/opt/homebrew/lib:${DYLD_LIBRARY_PATH:-}"
fi

# Attiva venv
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
else
    echo "Venv non trovato. Eseguire prima: python3 -m venv venv && pip3 install -r requirements.txt"
    exit 1
fi

echo "Avvio CaronteApp su http://localhost:5002"
python3 app.py
