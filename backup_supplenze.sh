#!/bin/zsh
# backup_supplenze.sh — backup serale cifrato alle 20:00
BACKUP_DIR="$HOME/SupplenzeApp/data/backup"
DB_PATH="$HOME/SupplenzeApp/database.db"
LOG="$BACKUP_DIR/backup.log"
PYTHON="$HOME/SupplenzeApp/venv/bin/python3"

mkdir -p "$BACKUP_DIR"

if [ ! -f "$DB_PATH" ]; then
    echo "$(date '+%Y-%m-%d %H:%M') ERROR: database.db non trovato" >> "$LOG"
    exit 1
fi

# Usa il modulo Python per backup cifrato
"$PYTHON" - << 'PYEOF'
import sys, os
sys.path.insert(0, os.path.expanduser('~/SupplenzeApp'))
from modules.backup_cifrato import crea_backup_cifrato, pulisci_vecchi_backup
import os

db_path    = os.path.expanduser('~/SupplenzeApp/database.db')
backup_dir = os.path.expanduser('~/SupplenzeApp/data/backup')

dest = crea_backup_cifrato(db_path, backup_dir, suffisso='_2000')
pulisci_vecchi_backup(backup_dir, max_backup=60)
print(dest)
PYEOF

if [ $? -eq 0 ]; then
    echo "$(date '+%Y-%m-%d %H:%M') OK: backup cifrato creato" >> "$LOG"
else
    echo "$(date '+%Y-%m-%d %H:%M') ERROR: backup cifrato fallito" >> "$LOG"
    # Fallback non cifrato
    NOME="database_$(date '+%Y%m%d')_2000_fallback.db"
    cp "$DB_PATH" "$BACKUP_DIR/$NOME"
    echo "$(date '+%Y-%m-%d %H:%M') FALLBACK: $NOME" >> "$LOG"
fi

exit 0
