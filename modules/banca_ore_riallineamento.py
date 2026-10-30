"""modules/banca_ore_riallineamento.py — supplenze a recupero con sostituto
ma senza il movimento di banca ore (+60 min) che dovrebbe accompagnarle.

Il saldo legge la tabella `banca_ore`, non le supplenze: una supplenza
'recupero' assegnata conta solo se esiste un movimento con id_supplenza.
Il movimento manca quando la supplenza arriva da un percorso che scrive
solo la riga (autosync, conflitto risolto "tieni remoto").

`trova()` è sola lettura; `riallinea()` scrive solo le righe scelte.
"""
from models import db
from models.supplenza import Supplenza
from models.movimento_banca_ore import MovimentoBancaOre

TIPO_RECUPERO = 'recupero'


def trova():
    """Supplenze assegnate, a recupero, con sostituto e senza movimento."""
    con_movimento = db.session.query(MovimentoBancaOre.id_supplenza).filter(
        MovimentoBancaOre.id_supplenza.isnot(None))
    return (Supplenza.query
            .filter(Supplenza.tipo == TIPO_RECUPERO,
                    Supplenza.stato == 'assegnata',
                    Supplenza.id_sostituto.isnot(None),
                    ~Supplenza.id.in_(con_movimento))
            .order_by(Supplenza.data, Supplenza.ora)
            .all())


def crea_movimento(supplenza):
    """Stesso movimento che crea routes.supplenze._registra_movimento."""
    m = MovimentoBancaOre(
        id_docente=supplenza.id_sostituto,
        data=supplenza.data,
        minuti=60,
        tipo=f'supplenza_{TIPO_RECUPERO}',
        descrizione=f'Supplenza {TIPO_RECUPERO}',
        id_supplenza=supplenza.id,
    )
    db.session.add(m)
    return m


def riallinea(id_supplenze):
    """Crea il movimento mancante per le supplenze indicate (solo se ancora
    senza movimento). Non fa commit. Ritorna il numero di movimenti creati."""
    ids = {int(i) for i in id_supplenze}
    creati = 0
    for s in trova():
        if s.id in ids:
            crea_movimento(s)
            creati += 1
    return creati
