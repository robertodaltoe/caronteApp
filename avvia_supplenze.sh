#!/bin/zsh
# avvia_supplenze.sh — avvia Flask + Cloudflare Tunnel
# Eseguire con: zsh ~/SupplenzeApp/avvia_supplenze.sh

LOG="$HOME/SupplenzeApp/data/backup/tunnel.log"
mkdir -p "$(dirname $LOG)"

echo "$(date '+%Y-%m-%d %H:%M') Avvio SupplenzeApp..." >> "$LOG"

# Avvia Flask in background
cd "$HOME/SupplenzeApp"
source venv/bin/activate
nohup python app.py >> "$LOG" 2>&1 &
FLASK_PID=$!
echo "Flask PID: $FLASK_PID" >> "$LOG"

# Aspetta che Flask sia pronto
sleep 3

# Avvia Cloudflare Tunnel
nohup cloudflared tunnel --url http://localhost:5001 --no-autoupdate >> "$LOG" 2>&1 &
CF_PID=$!
echo "Cloudflare Tunnel PID: $CF_PID" >> "$LOG"

# Aspetta l'URL
sleep 6
URL=$(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' "$LOG" | tail -1)

echo ""
echo "✅ SupplenzeApp avviata!"
echo "   Locale:   http://localhost:5001"
echo "   Internet: $URL"
echo ""
echo "⚠️  Tieni questo terminale aperto (o il Mac sveglio)."
echo "   Per fermare: pkill -f 'python app.py'; pkill cloudflared"
