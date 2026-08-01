"""
fix_date_storico.py
Corregge le date approssimate dei movimenti banca ore importati dall'Excel,
sostituendole con le date reali delle settimane dal foglio 'fogli'.

Mappa sett.N -> data lunedì della settimana reale.
Eseguire una sola volta con venv attivo:
    python fix_date_storico.py
"""
import sys, os
# Percorso della cartella radice del progetto (questo script vive in
# scripts/legacy/, due livelli sotto la radice dove sta app.py).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app import create_app
from models import db
from models.movimento_banca_ore import MovimentoBancaOre
from openpyxl import load_workbook
from datetime import date

EXCEL_PATH = os.path.join(os.path.dirname(__file__),
             'data', 'Banca_Ore_Docenti_v3.xlsm')

# Date lunedì reali per ogni settimana (dal foglio 'fogli')
# Anno scolastico 2025/2026
SETT_DATE = {
    'sett.1':  date(2025, 10, 20),
    'sett.2':  date(2025, 10, 27),
    'sett.3':  date(2025, 11,  3),
    'sett.4':  date(2025, 11, 10),
    'sett.5':  date(2025, 11, 17),
    'sett.6':  date(2025, 11, 24),
    'sett.7':  date(2025, 12,  1),
    'sett.8':  date(2025, 12,  8),
    'sett.9':  date(2025, 12, 15),
    'sett.10': date(2026,  1,  7),
    'sett.11': date(2026,  1, 12),
    'sett.12': date(2026,  1, 19),
    'sett.13': date(2026,  1, 26),
    'sett.14': date(2026,  2,  2),
    'sett.15': date(2026,  2,  9),
    'sett.16': date(2026,  2, 18),
    'sett.17': date(2026,  2, 23),
    'sett.18': date(2026,  3,  2),
    'sett.19': date(2026,  3,  9),
    'sett.20': date(2026,  3, 16),
    'sett.21': date(2026,  3, 23),
    'sett.22': date(2026,  3, 30),
    'sett.23': date(2026,  4,  9),
    'sett.24': date(2026,  4, 13),
    'sett.25': date(2026,  4, 20),
    'sett.26': date(2026,  4, 27),
    'sett.27': date(2026,  5,  4),
    'sett.28': date(2026,  5, 11),
    'sett.29': date(2026,  5, 18),
    'sett.30': date(2026,  5, 25),
}

def run():
    print("📂  Lettura movimenti da database...")
    app = create_app()
    with app.app_context():
        # I movimenti importati hanno descrizione tipo:
        # "Supplenza svolta — sett.12"
        # "Permesso/assenza oraria — sett.5"
        # "Libero Ed. Civica — sett.17"
        # "Ore richieste a pagamento (da Riepilogo)"

        movimenti = MovimentoBancaOre.query.filter(
            MovimentoBancaOre.descrizione.like('%sett.%')
        ).all()

        print(f"   Movimenti con riferimento settimana: {len(movimenti)}")

        aggiornati = 0
        non_trovati = set()

        for m in movimenti:
            # Estrai il nome della settimana dalla descrizione
            # Es. "Supplenza svolta — sett.12" -> "sett.12"
            desc = m.descrizione or ''
            sett_nome = None
            for parte in desc.split():
                parte_clean = parte.strip('—').strip()
                if parte_clean.startswith('sett.'):
                    sett_nome = parte_clean
                    break

            if not sett_nome:
                continue

            data_reale = SETT_DATE.get(sett_nome)
            if data_reale is None:
                non_trovati.add(sett_nome)
                continue

            if m.data != data_reale:
                m.data = data_reale
                aggiornati += 1

        db.session.commit()

        print(f"\n✅  Aggiornamento completato:")
        print(f"   Movimenti aggiornati: {aggiornati}")
        print(f"   Settimane non trovate: {non_trovati if non_trovati else 'nessuna'}")

        # Verifica: mostra alcuni movimenti aggiornati
        print("\n📋  Verifica — ultimi 5 movimenti aggiornati:")
        campione = MovimentoBancaOre.query.filter(
            MovimentoBancaOre.descrizione.like('%sett.%')
        ).order_by(MovimentoBancaOre.data).limit(5).all()
        for m in campione:
            from models.docente import Docente
            d = db.session.get(Docente, m.id_docente)
            print(f"   {d.cognome if d else '?':15s} | {m.data} | {m.tipo:20s} | {m.descrizione}")

if __name__ == '__main__':
    run()
